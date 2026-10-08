"""osu! TikTok edit engine.

Reads a storyboard (edit.json), analyses every clip (BPM / beat grid / downbeats,
action tracking), builds a beat-synced timeline and renders a 1080x1920 edit with
audio transitions between the clips' songs.

    python3 edit.py                 # full render using edit.json
    python3 edit.py --preview       # half resolution, 30 fps (fast check)
    python3 edit.py --frames 3.1,7  # dump single frames at those output times
"""
import argparse
import collections
import json
import math
import os
import subprocess

import cv2
import librosa
import numpy as np
import soundfile as sf

import gfx
import synth as S

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")
SR = S.SR


# ======================================================================= analysis
def extract_audio(path):
    os.makedirs(CACHE, exist_ok=True)
    wav = os.path.join(CACHE, os.path.basename(path) + ".wav")
    if not os.path.exists(wav) or os.path.getmtime(wav) < os.path.getmtime(path):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-vn", "-ac", "2", "-ar", str(SR), wav], check=True)
    y, _ = sf.read(wav, always_2d=True)
    return y.astype(np.float64)


def analyse_beats(y, bpm_hint=None):
    """Beat grid (period, offset) + downbeat phase. osu! songs are (almost always)
    constant BPM, so detected beats are fitted to a straight grid."""
    mono = librosa.resample(y.mean(1), orig_sr=SR, target_sr=22050)
    env = librosa.onset.onset_strength(y=mono, sr=22050)
    tempo, beats = librosa.beat.beat_track(onset_envelope=env, sr=22050, start_bpm=bpm_hint or 180,
                                           tightness=400, units="time")
    tempo = float(np.atleast_1d(tempo)[0])
    if len(beats) < 4:
        return dict(bpm=tempo, period=60 / tempo, offset=0.0, downbeat=0)
    # least squares on beat index -> refined period/offset (at the tracker's tempo)
    period = 60 / tempo
    idx = np.round((beats - beats[0]) / period)
    A = np.stack([idx, np.ones_like(idx)], 1)
    period, off = np.linalg.lstsq(A, beats, rcond=None)[0]
    # resolve half/double tempo: use the hint, else fold into the usual osu! range
    bpm = 60 / period
    if bpm_hint:
        for k in (2, 0.5, 4, 0.25):
            if abs(bpm * k - bpm_hint) < abs(bpm - bpm_hint):
                bpm *= k
    else:
        while bpm < 130:
            bpm *= 2
        while bpm >= 260:
            bpm /= 2
    period = 60 / bpm
    # fine grid fit on a high-resolution spectral-flux onset curve
    hop = 64
    env_hr = librosa.onset.onset_strength(y=mono, sr=22050, n_fft=512, hop_length=hop, lag=1, max_size=1)
    env_hr = np.convolve(env_hr, np.hanning(9) / np.hanning(9).sum(), mode="same")
    t_hr = np.arange(len(env_hr)) * hop / 22050
    t_end = t_hr[-1] - 0.01

    def strength(o, pr):
        return np.interp(np.arange(o, t_end, pr), t_hr, env_hr).mean()
    best = (-1.0, period, off)
    for pr in period * (1 + np.linspace(-0.006, 0.006, 121)):
        for o in np.arange(0, pr, 0.002):
            sc = strength(o, pr)
            if sc > best[0]:
                best = (sc, pr, o)
    _, period, off = best
    for o in off + np.arange(-0.002, 0.002, 0.00025):
        sc = strength(o, period)
        if sc > best[0]:
            best = (sc, period, o)
    off = (best[2] - 0.006) % period  # onset curve lags the attack by ~6 ms
    # downbeat phase: chords change on bar lines -> compare whole bars either side of
    # each candidate bar line (harmonic chroma), plus a little kick energy
    grid = np.arange(off, len(y) / SR - period, period)
    harm = librosa.effects.harmonic(mono)
    chroma = librosa.feature.chroma_stft(y=harm, sr=22050, hop_length=512, n_fft=8192)
    ct = librosa.times_like(chroma, sr=22050, hop_length=512)
    pb = []
    for g in grid:
        m = (ct >= g) & (ct < g + period)
        pb.append(chroma[:, m].mean(1) if m.any() else np.full(12, 1e-3))
    pb = np.array(pb) + 1e-6
    pb /= np.linalg.norm(pb, axis=1, keepdims=True)
    low_env = np.abs(S.lowpass(y.mean(1), 150, 4))
    kick = np.array([low_env[int(g * SR): int(g * SR) + int(0.05 * SR)].mean() for g in grid])
    score = []
    for p in range(4):
        v = [np.linalg.norm(pb[b - 4:b].mean(0) - pb[b:b + 4].mean(0)) for b in range(p + 4, len(pb) - 3, 4)]
        score.append((np.mean(v) if v else 0) + 0.02 * kick[p::4].mean() / (kick.mean() + 1e-9))
    phase = int(np.argmax(score))
    return dict(bpm=60 / period, period=float(period), offset=float(off), downbeat=phase)


def analyse_track(path):
    """Per-frame 'action centre' (motion-weighted centroid), smoothed with look-ahead."""
    cap = cv2.VideoCapture(path)
    W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()
    sw, sh = 320, int(320 * H / W)
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", path, "-f", "rawvideo", "-pix_fmt", "gray",
                          "-vf", f"scale={sw}:{sh}", "-"], stdout=subprocess.PIPE)
    prev, pts = None, []
    yy, xx = np.mgrid[0:sh, 0:sw].astype(np.float32)
    last = np.array([W / 2, H / 2])
    while True:
        buf = p.stdout.read(sw * sh)
        if len(buf) < sw * sh:
            break
        g = np.frombuffer(buf, np.uint8).reshape(sh, sw).astype(np.float32)
        if prev is not None:
            d = np.abs(g - prev)
            d[d < 12] = 0
            # ignore HUD strips (top/bottom/right edges)
            d[: int(sh * 0.08)] = 0
            d[int(sh * 0.9):] = 0
            d[:, int(sw * 0.93):] = 0
            wsum = (d * d).sum()
            if wsum > 2e5:
                last = np.array([(xx * d * d).sum() / wsum * W / sw, (yy * d * d).sum() / wsum * H / sh])
        pts.append(last.copy())
        prev = g
    p.wait()
    pts = np.array(pts) if pts else np.array([[W / 2, H / 2]])
    from scipy.ndimage import gaussian_filter1d
    sm = np.stack([gaussian_filter1d(pts[:, i], sigma=fps * 0.18, mode="nearest") for i in range(2)], 1)
    # pull a little towards the playfield centre for stability
    sm = sm * 0.8 + np.array([W / 2, H / 2]) * 0.2
    return dict(w=W, h=H, fps=fps, track=sm.tolist())


def analyse_clip(path, bpm_hint=None):
    os.makedirs(CACHE, exist_ok=True)
    cpath = os.path.join(CACHE, os.path.basename(path) + ".json")
    if os.path.exists(cpath) and os.path.getmtime(cpath) > os.path.getmtime(path):
        info = json.load(open(cpath))
        if info.get("bpm_hint") == bpm_hint:
            return info
    print("analysing", path)
    y = extract_audio(path)
    info = dict(analyse_beats(y, bpm_hint), **analyse_track(path), bpm_hint=bpm_hint)
    json.dump(info, open(cpath, "w"))
    print(f"  bpm {info['bpm']:.2f}  offset {info['offset']:.3f}s  downbeat phase {info['downbeat']}")
    return info


# ======================================================================= clip access
class Clip:
    def __init__(self, path, bpm_hint=None, shift=0):
        self.shift = shift  # manual downbeat correction in beats
        self.path = os.path.join(HERE, path)
        self.info = analyse_clip(self.path, bpm_hint)
        self.audio = extract_audio(self.path)
        self.period = self.info["period"]
        self.fps = self.info["fps"]
        self.track = np.array(self.info["track"])
        self.cap = cv2.VideoCapture(self.path)
        self.n_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.pos = -1
        self.cache = collections.OrderedDict()

    def downbeat_near(self, t):
        """Snap a time to the nearest downbeat of the beat grid."""
        i = self.info
        first = i["offset"] + (i["downbeat"] + self.shift) * self.period
        bar = 4 * self.period
        return first + round((t - first) / bar) * bar

    def frame(self, t):
        i = int(np.clip(round(t * self.fps), 0, self.n_frames - 1))
        if i in self.cache:
            self.cache.move_to_end(i)
            return self.cache[i]
        if not (self.pos < i <= self.pos + 8):
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            self.pos = i - 1
        f = None
        while self.pos < i:
            ok, f = self.cap.read()
            self.pos += 1
            if not ok:
                f = self.cache[next(reversed(self.cache))] if self.cache else np.zeros((1080, 1920, 3), np.uint8)
                break
            self.cache[self.pos] = f
        while len(self.cache) > 120:
            self.cache.popitem(last=False)
        return f

    def centre(self, t):
        i = int(np.clip(round(t * self.fps), 0, len(self.track) - 1))
        return self.track[i]


# ======================================================================= timeline
class Seg:
    """A stretch of output time fed by one clip through a sample-accurate time map."""

    def __init__(self, clip, out_start, smap, cfg, kind="play"):
        self.clip, self.t0, self.smap, self.cfg, self.kind = clip, out_start, smap, cfg, kind
        self.dur = len(smap) / SR
        self.t1 = out_start + self.dur
        self.period = clip.period
        self.beats = []  # output-time beats: (time, strength)

    def src(self, t):
        i = int(np.clip((t - self.t0) * SR, 0, len(self.smap) - 1))
        return self.smap[i]

    def beat_pos(self, t):
        """Beat number (float) inside this segment."""
        return (t - self.t0) / self.period


def build_timeline(cfg, clips):
    segs, t = [], 0.0
    # ---- intro: slowed (rate < 1) section of a clip
    ic = cfg["intro"]
    clip = clips[ic["clip"]]
    rate = ic.get("rate", 0.8)
    s0 = clip.downbeat_near(ic["start"])
    dur = ic["beats"] * clip.period / rate
    smap = s0 + np.arange(S.n_samples(dur)) / SR * rate
    intro = Seg(clip, t, smap, ic, "intro")
    segs.append(intro)
    t += intro.dur

    plays = cfg["segments"]
    for k, sc in enumerate(plays):
        clip = clips[sc["clip"]]
        P = clip.period
        s0 = clip.downbeat_near(sc["start"])
        n = S.n_samples(sc["beats"] * P)
        smap = s0 + np.arange(n) / SR
        out = sc.get("out", "cut")
        if out == "stutter":  # last beat: 1/4,1/4,1/8 x4 repeats of the beat's first slice
            b0 = S.n_samples((sc["beats"] - 1) * P)
            pattern = [0.25, 0.25, 0.125, 0.125, 0.125, 0.125]
            pos = b0
            for i, L in enumerate(pattern):
                ln = S.n_samples(L * P)
                slice_len = S.n_samples((0.25 if i < 2 else 0.125) * P)
                smap[pos: pos + ln] = s0 + b0 / SR + (np.arange(ln) % slice_len) / SR
                pos += ln
        elif out == "tapestop":  # last beat slows to a stop, then a short silence
            b0 = S.n_samples((sc["beats"] - 1) * P)
            ln = n - b0
            stop = int(ln * 0.75)
            rate = np.concatenate([np.linspace(1, 0, stop) ** 1.6, np.zeros(ln - stop)])
            smap[b0:] = s0 + b0 / SR + np.cumsum(rate) / SR
        seg = Seg(clip, t, smap, sc)
        seg.index = k
        # beats in output time (only where the map runs at normal speed)
        for b in range(sc["beats"]):
            strength = 1.0 if b % 4 == 0 else 0.55
            seg.beats.append((t + b * P, strength))
        segs.append(seg)
        t += seg.dur

    oc = cfg["outro"]
    last = segs[-1]
    freeze = last.smap[-1] - last.clip.period * 0.02
    outro = Seg(last.clip, t, np.full(S.n_samples(oc["dur"]), freeze), oc, "outro")
    outro.period = last.period
    segs.append(outro)
    return segs


# ======================================================================= audio
def render_audio(segs, cfg):
    total = segs[-1].t1
    out = np.zeros((S.n_samples(total) + SR * 3, 2))
    target = 0.18  # RMS per segment

    def read(seg):
        src = seg.clip.audio
        pos = seg.smap * SR
        a = np.stack([np.interp(pos, np.arange(len(src)), src[:, c]) for c in range(2)], 1)
        # de-click where the map jumps (stutter repeats)
        jumps = np.where(np.diff(seg.smap) < 0)[0]
        env = np.ones(len(a))
        fl = S.n_samples(0.003)
        for j in jumps:
            env[max(0, j - fl): j + 1] *= np.linspace(1, 0, min(j + 1, fl + 1))
            env[j + 1: j + 1 + fl] *= np.linspace(0, 1, len(env[j + 1: j + 1 + fl]))
        return a * env[:, None]

    plays = [s for s in segs if s.kind == "play"]
    for seg in segs:
        at = S.n_samples(seg.t0)
        P = seg.period
        if seg.kind == "intro":
            a = read(seg)
            a *= target * 0.55 / max(S.rms(a), 1e-6)
            a = S.stft_filter_sweep(a, 900, 5000, "low", curve=3)  # muffled, opening up
            a = S.reverb(a, 2.2, 0.55)[: len(a)]
            n = len(a)
            drone_t = np.arange(n) / SR
            drone = (np.sin(2 * np.pi * 41.2 * drone_t) * 0.5 + S.lowpass(S.saw(82.4, drone_t), 300) * 0.25)
            drone *= np.minimum(1, drone_t / 0.8)
            a += S.stereo(drone) * 0.35
            S.place(out, S.fade(a, 0.002, 0.01), at)
            S.place(out, S.impact() * 0.5, at)
            r_len = min(seg.dur, 4 * P)
            S.place(out, S.riser(r_len) * 0.45, S.n_samples(seg.t1 - r_len))
            S.place(out, S.reverse_cymbal(1.0) * 0.6, S.n_samples(seg.t1 - 1.0))
            continue
        if seg.kind == "outro":
            continue
        a = read(seg)
        a *= target / max(S.rms(a), 1e-6)
        mode = seg.cfg.get("out", "cut")
        n = len(a)
        if mode == "sweep":  # last 2 beats: low-pass sweep down + riser, tail bleeds into next
            b = S.n_samples(2 * P)
            a[n - b:] = S.stft_filter_sweep(a[n - b:], 18000, 260, "low", curve=1.6)
            S.place(out, S.riser(2 * P) * 0.55, at + n - b)
            tail = S.reverb(S.lowpass(a[n - S.n_samples(P):], 1200), 1.4, 1.0)
            S.place(out, tail[S.n_samples(P):] * 0.6, at + n)
        elif mode == "stutter":
            b = S.n_samples(P)
            a[n - b:] = S.stft_filter_sweep(a[n - b:], 20, 1800, "high", curve=1.2)
            S.place(out, S.reverse_cymbal(P * 2) * 0.7, at + n - S.n_samples(P * 2))
        elif mode == "tapestop":
            b = S.n_samples(P)
            a[n - b:] = S.stft_filter_sweep(a[n - b:], 16000, 500, "low", curve=1.0)
        S.place(out, S.fade(a, 0.002, 0.006), at)
        # hit the downbeat of every segment start
        S.place(out, S.impact() * (0.75 if seg is plays[0] else 0.55), at)
        for w in seg.cfg.get("whoosh_beats", []):
            S.place(out, S.whoosh(P) * 0.5, at + S.n_samples((w - 0.5) * P))

    # outro: freeze + boom + reverb tail of the last beat + drone
    oc = segs[-1]
    last = plays[-1]
    tail_src = read(last)[-S.n_samples(last.period * 0.5):]
    tail_src *= target / max(S.rms(tail_src), 1e-6)
    tail = S.reverb(S.lowpass(tail_src, 2500), 3.0, 1.0)
    S.place(out, S.impact(2.5) * 0.9, S.n_samples(oc.t0))
    S.place(out, tail * 0.5, S.n_samples(oc.t0))
    n = S.n_samples(oc.dur)
    dt = np.arange(n) / SR
    drone = np.sin(2 * np.pi * 41.2 * dt) * np.exp(-dt / 1.2) * 0.4
    S.place(out, drone, S.n_samples(oc.t0))

    # voice-over slots (music ducks under the voice)
    for vo in cfg.get("voiceover", []):
        p = os.path.join(HERE, vo["file"])
        if not os.path.exists(p):
            print("  (voiceover file missing, skipped):", vo["file"])
            continue
        v = extract_audio(p)
        v *= 0.25 / max(S.rms(v), 1e-6) * 10 ** (vo.get("gain_db", 0) / 20)
        at = S.n_samples(vo["at"])
        duck = np.ones(len(out))
        lo, hi = at, min(len(out), at + len(v))
        ramp = S.n_samples(0.08)
        duck[lo:hi] = 0.35
        duck[max(0, lo - ramp):lo] = np.linspace(1, 0.35, lo - max(0, lo - ramp))
        duck[hi:hi + ramp] = np.linspace(0.35, 1, len(duck[hi:hi + ramp]))
        out *= duck[:, None]
        S.place(out, S.reverb(v, 0.8, 0.15)[: len(v)], at)

    out = out[: S.n_samples(total)]
    end_fade = S.n_samples(0.25)
    out[-end_fade:] *= np.linspace(1, 0, end_fade)[:, None] ** 2
    return S.master(out, 1.4, 0.9)


# ======================================================================= video fx
class FX:
    def __init__(self, OW, OH):
        self.OW, self.OH = OW, OH
        yy, xx = np.mgrid[0:OH, 0:OW].astype(np.float32)
        r = np.sqrt(((xx - OW / 2) / (OW / 2)) ** 2 + ((yy - OH / 2) / (OH / 2)) ** 2)
        v = np.clip(1 - 0.55 * np.clip(r - 0.55, 0, None) ** 1.5, 0, 1)
        self.vig = cv2.merge([(v * 255).astype(np.uint8)] * 3)
        rs = np.random.default_rng(1)
        self.grain = [rs.normal(0, 1, (OH // 2, OW // 2)).astype(np.float32) for _ in range(6)]
        self.luts = {}
        self.echo = collections.deque(maxlen=8)
        self.rs = np.random.default_rng(5)

    def lut(self, name, tint, contrast=1.25, lift=0.0, gamma=1.0):
        key = (name, tuple(tint), contrast, lift, gamma)
        if key not in self.luts:
            x = np.arange(256) / 255.0
            chans = []
            for c in range(3):
                y = (x ** gamma - 0.5) * contrast + 0.5 + lift
                y = np.clip(y, 0, 1) * tint[c]
                chans.append(np.clip(y * 255, 0, 255).astype(np.uint8))
            self.luts[key] = np.stack(chans, 1).reshape(256, 1, 3)
        return self.luts[key]

    def bloom(self, img, amount):
        small = cv2.resize(img, (self.OW // 6, self.OH // 6), interpolation=cv2.INTER_AREA)
        small = cv2.subtract(small, (110, 110, 110, 0))
        small = cv2.GaussianBlur(small, (0, 0), 6)
        big = cv2.resize(small, (self.OW, self.OH), interpolation=cv2.INTER_LINEAR)
        return cv2.addWeighted(img, 1.0, big, amount, 0)

    def rgb_split(self, img, amount):
        if amount < 0.5:
            return img
        b, g, r = cv2.split(img)
        c = (self.OW / 2, self.OH / 2)
        k = amount / (self.OW / 2)
        Mr = cv2.getRotationMatrix2D(c, 0, 1 + k)
        Mb = cv2.getRotationMatrix2D(c, 0, 1 - k)
        r = cv2.warpAffine(r, Mr, (self.OW, self.OH), borderMode=cv2.BORDER_REFLECT)
        b = cv2.warpAffine(b, Mb, (self.OW, self.OH), borderMode=cv2.BORDER_REFLECT)
        return cv2.merge([b, g, r])

    def vblur(self, img, length):
        L = int(length)
        if L < 3:
            return img
        return cv2.blur(img, (1, L))

    def zoom_blur(self, img, amount):
        if amount < 0.004:
            return img
        acc = img.astype(np.float32)
        c = (self.OW / 2, self.OH / 2)
        for i in range(1, 4):
            M = cv2.getRotationMatrix2D(c, 0, 1 + amount * i)
            acc += cv2.warpAffine(img, M, (self.OW, self.OH), borderMode=cv2.BORDER_REFLECT).astype(np.float32)
        return (acc / 4).astype(np.uint8)

    def glitch(self, img, amount, seed):
        if amount <= 0:
            return img
        rs = np.random.default_rng(seed)
        out = img.copy()
        for _ in range(int(4 + 8 * amount)):
            y = int(rs.integers(0, self.OH - 40))
            h = int(rs.integers(10, int(40 + 140 * amount)))
            dx = int(rs.integers(-1, 2) * rs.integers(20, int(40 + 160 * amount)))
            out[y:y + h] = np.roll(out[y:y + h], dx, axis=1)
            ch = int(rs.integers(0, 3))
            out[y:y + h, :, ch] = np.roll(out[y:y + h, :, ch], dx // 2, axis=1)
        return out

    def grain_vig(self, img, fi, grain=6.0):
        img = cv2.multiply(img, self.vig, scale=1 / 255)
        if grain > 0:
            gn = cv2.resize(self.grain[fi % 6], (self.OW, self.OH), interpolation=cv2.INTER_NEAREST)
            img = np.clip(img.astype(np.int16) + (gn * grain).astype(np.int16)[..., None], 0, 255).astype(np.uint8)
        return img


def flash(img, amount, color=(255, 255, 255)):
    if amount <= 0.01:
        return img
    layer = np.empty_like(img)
    layer[:] = color
    return cv2.addWeighted(img, 1 - amount, layer, amount, 0)


def decay(t, k):
    return math.exp(-max(0.0, t) * k) if t >= 0 else 0.0


# ======================================================================= text styles
RED, CYAN = (255, 40, 70), (0, 230, 255)


def slam(frame, text, u, end_u, cx, cy, size, color=(255, 255, 255), fname="black_i",
         glow=0, glow_color=None, tracking=0, exit_style="glitch", k_scale=1.0):
    """Big kinetic text: punches in from large, chromatic ghosts, glitch exit."""
    if u < 0 or u > end_u + 0.15:
        return
    spr = gfx.text_sprite(text, size, fname, color, glow=glow, glow_color=glow_color, tracking=tracking)
    a_in = gfx.ease_out_cubic(u / 0.09)
    scale = (1 + 1.6 * (1 - gfx.ease_out_cubic(u / 0.13))) * k_scale
    alpha = min(1, u / 0.05)
    jitter = 14 * decay(u, 18)
    dx = jitter * math.sin(u * 90)
    dy = jitter * math.cos(u * 77)
    if u > end_u:  # exit
        e = (u - end_u) / 0.15
        if exit_style == "glitch":
            dx += (40 if int(u * 60) % 2 else -40) * e
            alpha *= 1 - e
            scale *= 1 + 0.25 * e
        else:
            alpha *= 1 - e
            scale *= 1 + 0.6 * e
    ghost = 24 * (1 - a_in) + 6
    for col, off in ((RED, -ghost), (CYAN, ghost)):
        g = gfx.text_sprite(text, size, fname, col, tracking=tracking)
        gfx.blit(frame, g, cx + dx + off, cy + dy, scale, 0, alpha * 0.55, add=True)
    gfx.blit(frame, spr, cx + dx, cy + dy, scale, 0, alpha)


def typewriter(frame, text, u, end_u, cx, cy, size, cps=22, color=(235, 235, 235)):
    if u < 0 or u > end_u + 0.1:
        return
    n = min(len(text), int(u * cps) + 1)
    alpha = 1.0 if u <= end_u else 1 - (u - end_u) / 0.1
    shown = text[:n]
    cursor = "_" if int(u * 8) % 2 == 0 or n < len(text) else " "
    spr = gfx.text_sprite(shown + cursor, size, "mono", color)
    full = gfx.text_sprite(text + "_", size, "mono", color)
    x = cx - full.shape[1] / 2 + spr.shape[1] / 2
    flick = 0.75 + 0.25 * math.sin(u * 63) if u < 0.3 else 1
    gfx.blit(frame, spr, x, cy, 1.0, 0, alpha * flick)


def tag(frame, big, small, u, end_u, x, y, accent=(255, 70, 110), scale=1.0):
    """Stat tag: accent bar + big value + caption, slides in with blur."""
    if u < 0 or u > end_u + 0.2:
        return
    a = gfx.ease_out_back(u / 0.22, 1.4)
    off = (1 - a) * -700
    alpha = min(1, u / 0.08)
    if u > end_u:
        e = (u - end_u) / 0.2
        off += 900 * gfx.ease_in_cubic(e)
        alpha *= 1 - e
    big_s = gfx.text_sprite(big, int(118 * scale), "black_i", (255, 255, 255), glow=6, glow_color=accent)
    small_s = gfx.text_sprite(small, int(44 * scale), "bold", (255, 255, 255))
    vel = abs(off) / 700
    if vel > 0.05:
        k = int(1 + 60 * vel)
        big_s = cv2.blur(big_s, (k, 1))
        small_s = cv2.blur(small_s, (k, 1))
    bx = x + off
    h_bar = int(big_s.shape[0] * 0.62 + small_s.shape[0] * 0.8)
    bar = np.zeros((h_bar, 14, 4), np.uint8)
    bar[:] = (accent[2], accent[1], accent[0], 255)
    gfx.blit(frame, bar, bx - 18, y + h_bar / 2 - big_s.shape[0] * 0.33, 1, 0, alpha)
    gfx.blit(frame, big_s, bx + big_s.shape[1] / 2, y, 1, 0, alpha)
    gfx.blit(frame, small_s, bx + small_s.shape[1] / 2 + 6, y + big_s.shape[0] * 0.52, 1, 0, alpha)


def make_card(OW, item, scale):
    from PIL import Image, ImageDraw
    scale *= 1.2
    w, h = int(OW * 0.9), int(150 * scale)
    img = gfx.rounded_rect(w, h, int(18 * scale), (48, 42, 62, 236))
    d = ImageDraw.Draw(img)
    # grade badge
    gc = tuple(item.get("badge_color", (90, 200, 255)))
    r = int(44 * scale)
    cx, cy = int(70 * scale), h // 2
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=gc + (255,))
    badge = item.get("badge", "S")
    bf = gfx.font("black", int((52 if len(badge) < 3 else 34) * scale))
    d.text((cx, cy + 2), badge, font=bf, fill=(255, 255, 255, 255), anchor="mm")
    d.text((int(140 * scale), int(28 * scale)), item["title"], font=gfx.font("bold", int(38 * scale)), fill=(255, 255, 255, 255))
    d.text((int(140 * scale), int(82 * scale)), item["sub"], font=gfx.font("semi", int(30 * scale)), fill=(255, 204, 34, 255))
    d.text((w - int(30 * scale), h // 2), item["value"], font=gfx.font("black_i", int(56 * scale)),
           fill=tuple(item.get("value_color", (200, 140, 255))) + (255,), anchor="rm")
    return gfx.pil_to_bgra(img)


# ======================================================================= renderer
def render(cfg, preview=False, frame_times=None, out_path=None):
    OW, OH = (540, 960) if preview else tuple(cfg.get("size", (1080, 1920)))
    FPS = 30 if preview else cfg.get("fps", 60)
    k = OW / 1080  # layout scale
    clips = {}
    for sc in [cfg["intro"]] + cfg["segments"]:
        name = sc["clip"]
        if name not in clips:
            clips[name] = Clip(name, cfg.get("bpm_hints", {}).get(name), cfg.get("downbeat_shift", {}).get(name, 0))
    segs = build_timeline(cfg, clips)
    total = segs[-1].t1
    print(f"timeline: {total:.2f}s")
    for s in segs:
        print(f"  {s.kind:5s} {os.path.basename(s.clip.path):12s} {s.t0:6.2f} -> {s.t1:6.2f}"
              f"  ({s.cfg.get('beats', '-')} beats @ {60 / s.period:.1f} bpm)")

    fx = FX(OW, OH)
    cards = {}
    plays = [s for s in segs if s.kind == "play"]

    def seg_at(t):
        for s in segs:
            if s.t0 <= t < s.t1:
                return s
        return segs[-1]

    # ---------------------------------------------------------------- per-frame
    def draw(t, fi):
        seg = seg_at(t)
        cfg_s = seg.cfg
        clip = seg.clip
        P = seg.period
        u = t - seg.t0
        st = seg.src(t)
        src = clip.frame(st)
        sh, sw = src.shape[:2]
        bpos = seg.beat_pos(t)
        nbeats = cfg_s.get("beats", 0)
        is_play = seg.kind == "play"
        idx = plays.index(seg) if is_play else -1
        nxt = plays[idx + 1] if is_play and idx + 1 < len(plays) else None
        prv = plays[idx - 1] if idx > 0 else None
        out_mode = cfg_s.get("out", "cut")
        cam = cfg_s.get("cam", {})

        # ---- beat envelopes
        beat_i = math.floor(bpos + 1e-6)
        since_beat = (bpos - beat_i) * P
        strong = beat_i % 4 == 0
        punch = 0.0
        if is_play and seg.smap[int(min(len(seg.smap) - 1, u * SR))] - seg.smap[0] >= u - 0.02:
            punch = cam.get("punch", 0.1) * (1.9 if strong else 1) * decay(since_beat, 14)

        # ---- camera
        zoom = cam.get("zoom", 1.2)
        center = clip.centre(st).copy()
        rot = 0.0
        if is_play:
            rot = cam.get("roll", 2.0) * (1 if (beat_i // 4) % 2 else -1) * decay(since_beat, 7) * (1 if strong else 0.4)
        offy = 0.0
        shake = cam.get("shake", 0.0)
        vblur = 0.0
        zblur = 0.0
        rgb = cfg_s.get("rgb", 3.0) * k
        glitch = 0.0
        flash_amt = 0.0
        flash_col = (255, 255, 255)

        if seg.kind == "intro":
            prog = u / seg.dur
            zoom = 1.05 + 0.25 * prog + 0.9 * gfx.ease_in_expo(prog)
            shake = 2 + 30 * gfx.ease_in_expo(prog)
            rgb = 2 + 30 * gfx.ease_in_expo(prog)
            zblur = 0.03 * gfx.ease_in_expo(prog)
            flash_amt = 0.85 * decay(u, 5) + 0.9 * gfx.ease_in_expo((prog - 0.9) / 0.1)
        elif seg.kind == "outro":
            zoom = 1.0 + 0.06 * u
            center = np.array([sw / 2, sh / 2])
            flash_amt = 0.9 * decay(u, 4)
            rgb = 4 * k + 30 * decay(u, 6)
            zblur = 0.05 * decay(u, 5)
        else:
            # reveal: start zoomed out (whole playfield) then slam in
            rv = cfg_s.get("reveal_beats", 0)
            if rv and bpos < rv:
                fit = (OW / sw) / (OH / sh)
                zoom = fit * (1.3 + 0.06 * bpos)
                center = np.array([sw / 2, sh / 2])
                rot = 0
                punch *= 0.3
            elif rv and bpos < rv + 0.5:
                zblur = 0.06 * decay((bpos - rv) * P, 10)
            # jump-cut section: alternate framings every half beat
            jc = cfg_s.get("jumpcut")
            if jc and jc[0] <= bpos < jc[1]:
                h = int(bpos * 2)
                zoom *= (1.0, 1.45, 1.15, 1.7)[h % 4]
                center = center + np.array([(-90, 70, 120, -60)[h % 4], (40, -60, 30, -20)[h % 4]])
                rot += (-4, 3, 5, -3)[h % 4]
                flash_amt = max(flash_amt, 0.18 * decay(((bpos * 2) % 1) * P / 2, 25))
                rgb += 10 * k * decay(((bpos * 2) % 1) * P / 2, 20)
            # build: zoom & shake ramp
            bd = cfg_s.get("build")
            if bd and bpos >= bd[0]:
                p = (bpos - bd[0]) / (bd[1] - bd[0])
                zoom *= 1 + 0.5 * p ** 2
                shake = max(shake, 22 * p ** 2)
                rgb += 18 * k * p ** 2
            # segment entry: flash + zoom blur + RGB spike
            flash_amt = max(flash_amt, (0.45 if seg.cfg.get("reveal_beats") else 0.7) * decay(u, 9))
            rgb += 26 * k * decay(u, 8)
            zblur = max(zblur, 0.05 * decay(u, 10))
            glitch = max(glitch, 1.0 * (u < 0.07))
            # incoming whip from the previous transition
            if prv is not None and prv.cfg.get("out") == "sweep" and u < 0.5 * P:
                w = 1 - u / (0.5 * P)
                offy = -OH * 0.8 * w ** 2
                vblur = 260 * k * w
            # outgoing transitions
            left = (nbeats - bpos) * P  # seconds left
            if out_mode == "sweep" and left < 0.5 * P:
                w = 1 - left / (0.5 * P)
                offy = OH * 0.8 * w ** 2
                vblur = 260 * k * w
                rgb += 20 * k * w
            elif out_mode == "stutter" and bpos >= nbeats - 1:
                rep = int((bpos - (nbeats - 1)) * 8)
                zoom *= 1 + 0.08 * rep
                rot += (-3 if rep % 2 else 3)
                flash_amt = max(flash_amt, 0.25 * decay(((bpos * 8) % 1) * P / 8, 30))
                glitch = max(glitch, 0.3 + 0.1 * rep)
            elif out_mode == "tapestop" and bpos >= nbeats - 1:
                p = bpos - (nbeats - 1)
                zoom *= 1 - 0.1 * p
                rot = 0
                punch = 0
            # strobe section
            sb = cfg_s.get("strobe")
            if sb and sb[0] <= bpos < sb[1]:
                ph = (bpos * 2) % 1
                flash_amt = max(flash_amt, 0.35 * (ph < 0.12))

        zoom *= 1 + punch
        if shake:
            center = center + np.array([math.sin(t * 61.3) + math.sin(t * 23.1), math.cos(t * 53.7) + math.sin(t * 31.9)]) * shake / zoom
            rot += math.sin(t * 41) * shake * 0.05
        s_scale = (OH / sh) * zoom
        hw, hh = OW / 2 / s_scale, OH / 2 / s_scale
        if hw < sw / 2:
            center[0] = np.clip(center[0], hw, sw - hw)
        if hh < sh / 2:
            center[1] = np.clip(center[1], hh, sh - hh)

        # background fill (blurred cover) + warped foreground
        small = cv2.resize(src, (96, 54), interpolation=cv2.INTER_AREA)
        cw = int(54 * OW / OH)
        small = small[:, (96 - cw) // 2:(96 - cw) // 2 + cw]
        bg = cv2.resize(cv2.GaussianBlur(small, (0, 0), 2), (OW, OH), interpolation=cv2.INTER_LINEAR)
        bg = cv2.convertScaleAbs(bg, alpha=0.7)
        M = cv2.getRotationMatrix2D((float(center[0]), float(center[1])), rot, s_scale)
        M[0, 2] += OW / 2 - center[0]
        M[1, 2] += OH / 2 - center[1] + offy
        img = cv2.warpAffine(src, M, (OW, OH), dst=bg, flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_TRANSPARENT)

        # grade
        g = cfg_s.get("grade", {})
        bw = seg.kind in ("intro", "outro") or (out_mode == "tapestop" and is_play and bpos >= nbeats - 1)
        if bw:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            img = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        tint = g.get("tint", [1, 1, 1])
        img = cv2.LUT(img, fx.lut(seg.kind, tint[::-1], g.get("contrast", 1.25), g.get("lift", -0.04), g.get("gamma", 1.1)))

        # echo trails
        if cfg_s.get("echo") and (not isinstance(cfg_s["echo"], list) or cfg_s["echo"][0] <= bpos < cfg_s["echo"][1]):
            if len(fx.echo) >= 6:
                e1 = cv2.multiply(fx.echo[-3], (1.0, 0.45, 0.9, 0))
                e2 = cv2.multiply(fx.echo[-6], (0.3, 0.9, 1.0, 0))
                img = cv2.max(img, cv2.max(cv2.convertScaleAbs(e1, alpha=0.7), cv2.convertScaleAbs(e2, alpha=0.45)))
        fx.echo.append(img)

        img = fx.bloom(img, cfg_s.get("bloom", 0.9) + 0.8 * punch * 5)
        if vblur:
            img = fx.vblur(img, vblur)
        if zblur:
            img = fx.zoom_blur(img, zblur)
        img = fx.rgb_split(img, rgb)
        if glitch:
            img = fx.glitch(img, glitch, fi)
        img = flash(img, min(1, flash_amt), flash_col)
        if out_mode == "tapestop" and is_play and bpos >= nbeats - 0.25:
            img = (img * 0.15).astype(np.uint8)

        # ---- overlays
        overlays(img, t, seg, u, bpos, P)
        img = fx.grain_vig(img, fi, 7 if bw else 3.5)
        if seg.kind in ("intro", "outro"):
            bar = int(OH * 0.075)
            img[:bar] = 0
            img[-bar:] = 0
        if seg.kind == "outro" and u > seg.dur - 0.25:
            img = fx.glitch(img, 1.5, fi)
            img = (img * max(0, (seg.dur - u) / 0.25)).astype(np.uint8)
        return img

    def overlays(img, t, seg, u, bpos, P):
        for ev in seg.cfg.get("texts", []):
            st = ev.get("style", "slam")
            mul = 1 if ev.get("unit") == "sec" else P
            t_in = ev["at"] * mul
            t_end = ev.get("until", ev["at"] + 2) * mul
            uu = u - t_in
            cx = OW * ev.get("x", 0.5)
            cy = OH * ev.get("y", 0.5)
            size = int(ev.get("size", 150) * k)
            if st == "slam":
                slam(img, ev["text"], uu, t_end - t_in, cx, cy, size, tuple(ev.get("color", (255, 255, 255))),
                     ev.get("font", "black_i"), int(ev.get("glow", 0) * k), tuple(ev["glow_color"]) if "glow_color" in ev else None,
                     int(ev.get("tracking", 0) * k), ev.get("exit", "glitch"))
            elif st == "type":
                typewriter(img, ev["text"], uu, t_end - t_in, cx, cy, size, ev.get("cps", 22),
                           tuple(ev.get("color", (235, 235, 235))))
            elif st == "tag":
                tag(img, ev["text"], ev.get("sub", ""), uu, t_end - t_in, OW * ev.get("x", 0.08), cy,
                    tuple(ev.get("accent", (255, 70, 110))), k)
            elif st == "cards":
                draw_cards(img, ev, uu, t_end - t_in, P)

    def draw_cards(img, ev, uu, dur, P):
        if uu < 0 or uu > dur:
            return
        key = id(ev)
        if key not in cards:
            cards[key] = [make_card(OW, it, k) for it in ev["items"]]
        sprites = cards[key]
        # dim the gameplay behind the cards
        dim = min(1, uu / 0.1) * 0.55
        img[:] = cv2.convertScaleAbs(img, alpha=1 - dim)
        layer = np.zeros((OH, OW, 4), np.uint8)
        gap = int(200 * k)
        y0 = OH * ev.get("y", 0.42) - gap * (len(sprites) - 1) / 2
        for i, spr in enumerate(sprites):
            ti = uu - i * P * ev.get("stagger", 0.5)
            if ti < 0:
                continue
            a = gfx.ease_out_back(ti / 0.25, 1.3)
            x = OW / 2 + (1 - a) * -OW * 1.1
            vel = 1 - gfx.clamp01(ti / 0.25)
            s = spr
            if vel > 0.05:
                s = cv2.blur(spr, (int(1 + 90 * vel * k), 1))
            hl = 1.0 if i == 0 else 0.92
            gfx_blit_rgba(layer, s, x, y0 + i * gap, hl)
        # push into the top card at the end (perspective tilt + zoom)
        push_t = dur - P * ev.get("push_beats", 2)
        p = gfx.clamp01((uu - push_t) / (dur - push_t))
        if p > 0:
            e = gfx.ease_in_expo(p) * 0.6 + gfx.ease_in_cubic(p) * 0.4
            s = 1 + 3.5 * e
            ty = (OH / 2 - y0) * e
            tilt = 0.25 * e
            src_pts = np.float32([[0, 0], [OW, 0], [OW, OH], [0, OH]])
            dx = OW * tilt
            dst = np.float32([[-dx, 0], [OW + dx, 0], [OW, OH], [0, OH]])
            Mp = cv2.getPerspectiveTransform(src_pts, dst)
            S2 = np.array([[s, 0, OW / 2 * (1 - s)], [0, s, OH / 2 * (1 - s) + ty * s], [0, 0, 1]])
            layer = cv2.warpPerspective(layer, S2 @ Mp, (OW, OH))
            layer = cv2.blur(layer, (1, int(1 + 80 * e * k)))
        alpha = layer[:, :, 3:4].astype(np.float32) / 255 * (1 - gfx.clamp01((p - 0.85) / 0.15))
        img[:] = (img.astype(np.float32) * (1 - alpha) + layer[:, :, :3].astype(np.float32) * alpha).astype(np.uint8)

    def gfx_blit_rgba(layer, spr, cx, cy, bright=1.0):
        h, w = spr.shape[:2]
        x0, y0 = int(cx - w / 2), int(cy - h / 2)
        xs0, ys0 = max(0, -x0), max(0, -y0)
        x0c, y0c = max(0, x0), max(0, y0)
        x1c, y1c = min(OW, x0 + w), min(OH, y0 + h)
        if x1c <= x0c or y1c <= y0c:
            return
        part = spr[ys0:ys0 + (y1c - y0c), xs0:xs0 + (x1c - x0c)]
        roi = layer[y0c:y1c, x0c:x1c]
        a = part[:, :, 3:4].astype(np.float32) / 255
        roi[:, :, :3] = (roi[:, :, :3] * (1 - a) + part[:, :, :3] * a * bright).astype(np.uint8)
        roi[:, :, 3:4] = np.maximum(roi[:, :, 3:4], part[:, :, 3:4])

    # ---------------------------------------------------------------- output
    if frame_times:
        os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
        for ft in frame_times:
            fi = int(ft * FPS)
            # warm up echo buffer
            for j in range(max(0, fi - 7), fi):
                draw(j / FPS, j)
            img = draw(fi / FPS, fi)
            p = os.path.join(HERE, "out", f"frame_{ft:05.2f}.png")
            cv2.imwrite(p, img)
            print("wrote", p)
        return

    print("rendering audio...")
    audio = render_audio(segs, cfg)
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    wav = os.path.join(CACHE, "edit_audio.wav")
    sf.write(wav, audio, SR)
    out_path = out_path or os.path.join(HERE, cfg.get("output", "out/edit.mp4"))
    if preview:
        out_path = out_path.replace(".mp4", "_preview.mp4")
    ff = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{OW}x{OH}", "-r", str(FPS),
         "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "veryfast" if preview else "slow",
         "-crf", "23" if preview else "17", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "320k",
         "-af", "loudnorm=I=-9:TP=-1.0:LRA=6", "-ar", "44100", "-movflags", "+faststart", "-shortest", out_path],
        stdin=subprocess.PIPE)
    n = int(total * FPS)
    for fi in range(n):
        ff.stdin.write(draw(fi / FPS, fi).tobytes())
        if fi % (FPS * 2) == 0:
            print(f"  frame {fi}/{n}", flush=True)
    ff.stdin.close()
    ff.wait()
    print("wrote", out_path)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(HERE, "edit.json"))
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--frames", default=None, help="comma separated output times to dump as PNG")
    a = ap.parse_args()
    cfg = json.load(open(a.config))
    ft = [float(x) for x in a.frames.split(",")] if a.frames else None
    render(cfg, preview=a.preview, frame_times=ft)
