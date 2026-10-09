"""osu! TikTok edit engine.

Reads a storyboard (edit.json), analyses every clip (BPM / beat grid / downbeats,
action tracking), builds a beat-synced timeline (hook -> parts -> outro) and renders
a 1080x1920 edit. Every part has its own editing style (see parts.py); the audio
glues the clips' songs together with transitions and motion-synced SFX.

    python3 edit.py                 # full render using edit.json (parallel)
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

import layers as L
import parts as PARTS
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
    phase = downbeat_phase(y, mono, period, off)
    return dict(bpm=60 / period, period=float(period), offset=float(off), downbeat=phase)


def downbeat_phase(y, mono, period, off):
    """Which beat (0..3) of the grid is the bar line: chord changes + kick energy."""
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
    return phase


def beats_from_presses(y, presses, period_hint):
    """Beat grid from replay key presses. Notes sit on 1/2 or 1/4 of the beat, so search
    every tempo in 120..300 BPM for the grid that explains the presses best; the audio
    breaks ties, picks which subdivision is the beat and finds the bar line."""
    pt = np.asarray(presses)
    Ts = np.arange(120, 300, 0.02)
    scores = np.zeros((len(Ts), 2))
    for j, div in enumerate((2, 4)):
        sub = (60 / Ts) / div
        for i0 in range(0, len(Ts), 1000):
            ph = np.exp(2j * np.pi * pt[None, :] / sub[i0:i0 + 1000, None]).mean(1)
            scores[i0:i0 + 1000, j] = np.abs(ph)
    R = scores.max(1)
    mono = librosa.resample(y.mean(1), orig_sr=SR, target_sr=22050)
    env = librosa.onset.onset_strength(y=mono, sr=22050, n_fft=512, hop_length=64)
    env = np.convolve(env, np.hanning(9) / np.hanning(9).sum(), mode="same")
    te = np.arange(len(env)) * 64 / 22050
    low = np.abs(S.lowpass(y.mean(1), 150, 4))

    def audio_score(P, o):
        g = np.arange(o, len(y) / SR - 0.05, P)
        k = np.array([low[int(x * SR): int(x * SR) + int(0.04 * SR)].mean() for x in g])
        return np.interp(g, te, env).mean() / (env.mean() + 1e-9) + k.mean() / (low.mean() + 1e-9)
    # candidate tempos: local maxima within 85 % of the best press fit
    cands = []
    for i in np.argsort(-R):
        if R[i] < 0.85 * R.max() or len(cands) >= 8:
            break
        if all(abs(Ts[i] - c) > 1.0 for c in cands):
            cands.append(Ts[i])
    best = None
    for T in cands:
        P = 60 / T
        div = (2, 4)[int(np.argmax(scores[int(round((T - 120) / 0.02)) if T < 300 else -1]))]
        ph = np.exp(2j * np.pi * pt / (P / div)).mean()
        sub = P / div
        off_sub = (np.angle(ph) / (2 * np.pi)) * sub % sub
        for j in range(div):
            o = (off_sub + j * sub) % P
            sc = abs(ph) * audio_score(P, o)
            if best is None or sc > best[0]:
                best = (sc, T, o, abs(ph))
    _, T, off, Rb = best
    P = 60 / T
    phase = downbeat_phase(y, mono, P, off)
    return dict(bpm=T, period=float(P), offset=float(off), downbeat=phase, press_R=float(Rb))


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
    def __init__(self, path, bpm_hint=None, shift=0, replay=None):
        self.shift = shift  # manual downbeat correction in beats
        self.path = os.path.join(HERE, path)
        self.info = analyse_clip(self.path, bpm_hint)
        self._audio = None
        self.w, self.h = self.info["w"], self.info["h"]
        self.period = self.info["period"]
        self.fps = self.info["fps"]
        self.track = np.array(self.info["track"])
        self.presses = np.array([])
        self.cap = cv2.VideoCapture(self.path)
        self.n_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.pos = -1
        self.cache = collections.OrderedDict()
        if replay:
            self._use_replay(replay)

    @property
    def audio(self):
        if self._audio is None:
            self._audio = extract_audio(self.path)
        return self._audio

    def downbeat_near(self, t, bars=1):
        """Snap a time to the nearest downbeat of the beat grid."""
        i = self.info
        first = i["offset"] + (i["downbeat"] + self.shift) * self.period
        bar = 4 * self.period * bars
        return first + round((t - first) / bar) * bar

    def frame(self, t):
        i = int(np.clip(round(t * self.fps), 0, self.n_frames - 1))
        if i in self.cache:
            self.cache.move_to_end(i)
            return self.cache[i]
        if not (self.pos < i <= self.pos + 30):
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

    def _use_replay(self, rc):
        """Drive the camera with the real cursor from the .osr replay.
        rc: {"file": ..., "offset": map time (s) at video t=0, "rate": 1.5 for DT}"""
        import osr
        from scipy.ndimage import gaussian_filter1d
        o = osr.parse(os.path.join(HERE, rc["file"]))
        fr = np.array(o["frames"], float)
        rate = rc.get("rate", 1.5 if any(m in osr.mods_str(o["mods"]) for m in ("DT", "NC")) else 1.0)
        n = max(self.n_frames, len(self.track))
        vt = np.arange(n) / self.fps
        mt = rc["offset"] * 1000 + vt * 1000 * rate
        s = 0.8 * self.h / 384  # danser/osu! playfield: 80% of the height, centred
        sx = (self.w - 512 * s) / 2 + np.interp(mt, fr[:, 0], fr[:, 1]) * s
        sy = (self.h - 384 * s) / 2 + np.interp(mt, fr[:, 0], fr[:, 2]) * s
        self.cursor = np.stack([sx, sy], 1)
        sig = self.fps * rc.get("smooth", 0.05)
        self.track = np.stack([gaussian_filter1d(sx, sig), gaussian_filter1d(sy, sig)], 1)
        z = fr[:, 3].astype(int)
        presses = []
        for mask in (5, 10):
            k = (z & mask) > 0
            presses.append(fr[1:, 0][k[1:] & ~k[:-1]])
        pt = (np.sort(np.concatenate(presses)) - rc["offset"] * 1000) / 1000 / rate
        self.presses = pt[(pt >= 0) & (pt <= vt[-1])]
        self.replay = o
        if len(self.presses) > 40 and rc.get("beats_from_replay", True):
            info = beats_from_presses(self.audio, self.presses, self.period)
            print(f"  {os.path.basename(self.path)}: replay beat grid {info['bpm']:.2f} bpm, offset "
                  f"{info['offset'] * 1000:.1f} ms, downbeat {info['downbeat']} (fit {info['press_R']:.2f})")
            self.info = dict(self.info, **info)
            self.period = info["period"]

    def cursor_at(self, t):
        if getattr(self, "cursor", None) is None:
            return None
        return self.cursor[int(np.clip(round(t * self.fps), 0, len(self.cursor) - 1))]

    def centre(self, t):
        i = int(np.clip(round(t * self.fps), 0, len(self.track) - 1))
        return self.track[i]


# ======================================================================= timeline
class Seg:
    """A stretch of output time fed by one clip through a sample-accurate time map."""

    def __init__(self, kind, style, clip, t0, smap, cfg, period):
        self.kind, self.style, self.clip, self.t0, self.smap, self.cfg = kind, style, clip, t0, smap, cfg
        self.period = period
        self.dur = len(smap) / SR
        self.t1 = t0 + self.dur

    def src(self, t):
        i = int(np.clip((t - self.t0) * SR, 0, len(self.smap) - 1))
        return float(self.smap[i])


def pulse(pc, clip):
    """Edit beats per audio beat: very fast songs (DT!) are cut in half time."""
    return pc.get("pulse", 2 if 60 / clip.period > 230 else 1)


def build_timeline(cfg, clips):
    pcs = cfg["parts"]
    starts = [clips[pc["clip"]].downbeat_near(pc["start"]) for pc in pcs]  # bar lines of the audio
    segs, t = [], 0.0
    # hook: the bars right before part 1 in part 1's own song, so the drop lands naturally
    hc = cfg["hook"]
    c0 = clips[pcs[0]["clip"]]
    P0 = c0.period
    P0 *= pulse(pcs[0], c0)
    hb = hc.get("beats", 4)
    smap = starts[0] - hb * P0 + np.arange(S.n_samples(hb * P0)) / SR
    segs.append(Seg("hook", "hook", c0, t, smap, hc, P0))
    t += segs[-1].dur
    for k, pc in enumerate(pcs):
        clip = clips[pc["clip"]]
        P = clip.period * pulse(pc, clip)
        s0 = starts[k]
        n = S.n_samples(pc["beats"] * P)
        smap = s0 + np.arange(n) / SR
        out = pc.get("out", "cut")
        if out == "stutter":  # last beat: 1/4,1/4,1/8 x4 repeats of the beat's first slice
            b0 = S.n_samples((pc["beats"] - 1) * P)
            pos = b0
            for i, ln_b in enumerate([0.25, 0.25, 0.125, 0.125, 0.125, 0.125]):
                ln = S.n_samples(ln_b * P)
                sl = S.n_samples((0.25 if i < 2 else 0.125) * P)
                smap[pos:pos + ln] = s0 + b0 / SR + (np.arange(len(smap[pos:pos + ln])) % sl) / SR
                pos += ln
        elif out == "tapestop":  # last beat slows to a stop, then silence
            b0 = S.n_samples((pc["beats"] - 1) * P)
            ln = n - b0
            stop = int(ln * 0.75)
            rate = np.concatenate([np.linspace(1, 0, stop) ** 1.6, np.zeros(ln - stop)])
            smap[b0:] = s0 + b0 / SR + np.cumsum(rate) / SR
        seg = Seg("part", pc["style"], clip, t, smap, pc, P)
        seg.index = k
        segs.append(seg)
        t += seg.dur
    oc = cfg["outro"]
    last = segs[-1]
    segs.append(Seg("outro", "outro", last.clip, t, np.full(S.n_samples(oc.get("dur", 1.6)), last.smap[-1]), oc,
                    last.period))
    return segs


# ======================================================================= audio
_snd_cache = {}


def sound(name, dur=None):
    if name == "riser":
        return S.riser(dur or 1.0)
    if name == "rev":
        return S.reverse_cymbal(dur or 0.6)
    if name == "scramble":
        return S.sfx_scramble(dur or 0.3)
    if name not in _snd_cache:
        _snd_cache[name] = S.stereo(S.SFX[name]())
    return _snd_cache[name]


def render_audio(segs, cfg):
    total = segs[-1].t1
    out = np.zeros((S.n_samples(total) + SR * 4, 2))
    target = 0.18

    def read(seg):
        src = seg.clip.audio
        pos = seg.smap * SR
        a = np.stack([np.interp(pos, np.arange(len(src)), src[:, c]) for c in range(2)], 1)
        jumps = np.where(np.diff(seg.smap) < 0)[0]  # de-click stutter repeats
        env = np.ones(len(a))
        fl = S.n_samples(0.003)
        for j in jumps:
            env[max(0, j - fl): j + 1] *= np.linspace(1, 0, min(j + 1, fl + 1))
            env[j + 1: j + 1 + fl] *= np.linspace(0, 1, len(env[j + 1: j + 1 + fl]))
        return a * env[:, None]

    parts = [s for s in segs if s.kind == "part"]
    for seg in segs:
        at = S.n_samples(seg.t0)
        P = seg.period
        if seg.kind == "hook":
            a = read(seg)
            a *= target * 0.8 / max(S.rms(a), 1e-6)
            a = S.stft_filter_sweep(a, 250, 16000, "low", curve=2.4)
            S.place(out, S.fade(a, 0.004, 0.002), at)
            S.place(out, S.riser(seg.dur) * 0.35, at)
            rv = min(0.8, seg.dur)
            S.place(out, S.reverse_cymbal(rv) * 0.6, S.n_samples(seg.t1 - rv))
            continue
        if seg.kind == "outro":
            continue
        a = read(seg)
        a *= target / max(S.rms(a), 1e-6)
        fx = PARTS.AUDIO_FX.get(seg.style)
        if fx:
            a = fx(a, seg)
        mode = seg.cfg.get("out", "cut")
        n = len(a)
        if mode == "sweep":  # last 2 beats: low-pass sweep down + riser; tail bleeds into the next part
            bl = S.n_samples(2 * P)
            a[n - bl:] = S.stft_filter_sweep(a[n - bl:], 18000, 260, "low", curve=1.6)
            S.place(out, S.riser(2 * P) * 0.55, at + n - bl)
            tail = S.reverb(S.lowpass(a[n - S.n_samples(P):], 1200), 1.4, 1.0)
            S.place(out, tail[S.n_samples(P):] * 0.6, at + n)
        elif mode == "stutter":
            bl = S.n_samples(P)
            a[n - bl:] = S.stft_filter_sweep(a[n - bl:], 20, 1800, "high", curve=1.2)
            S.place(out, S.reverse_cymbal(P * 2) * 0.7, at + n - S.n_samples(P * 2))
        elif mode == "tapestop":
            bl = S.n_samples(P)
            a[n - bl:] = S.stft_filter_sweep(a[n - bl:], 16000, 500, "low", curve=1.0)
        S.place(out, S.fade(a, 0.002, 0.006), at)
        S.place(out, S.impact() * (0.8 if seg is parts[0] else 0.55), at)

    # outro: freeze + boom + reverb tail of the last beat + sub drone
    oc, last = segs[-1], parts[-1]
    tail_src = read(last)[-S.n_samples(last.period * 0.5):]
    tail_src *= target / max(S.rms(tail_src), 1e-6)
    S.place(out, S.impact(2.5) * 0.9, S.n_samples(oc.t0))
    S.place(out, S.reverb(S.lowpass(tail_src, 2500), 3.0, 1.0) * 0.5, S.n_samples(oc.t0))
    dt = np.arange(S.n_samples(oc.dur)) / SR
    S.place(out, np.sin(2 * np.pi * 41.2 * dt) * np.exp(-dt / 1.2) * 0.4, S.n_samples(oc.t0))

    # motion-synced sound effects from every part
    sfx_gain = cfg.get("sfx_gain", 1.0)
    for seg in segs:
        fn = PARTS.SFX.get(seg.style)
        if not fn:
            continue
        for ev in fn(seg):
            t_ev, name, gain = ev[:3]
            dur = ev[3] if len(ev) > 3 else (4 * seg.period if name == "riser" else None)
            S.place(out, sound(name, dur) * gain * sfx_gain, S.n_samples(t_ev))

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


# ======================================================================= video
class Ctx:
    pass


def make_ctx(cfg, preview):
    ctx = Ctx()
    ctx.W, ctx.H = (540, 960) if preview else tuple(cfg.get("size", (1080, 1920)))
    ctx.fps = 30 if preview else cfg.get("fps", 60)
    ctx.k = ctx.W / 1080
    ctx.clips = {}
    for name, cc in cfg["clips"].items():
        ctx.clips[name] = Clip(cc["file"], cc.get("bpm"), cc.get("downbeat_shift", 0), cc.get("replay"))
    segs = build_timeline(cfg, ctx.clips)
    ctx.src_start, ctx.grade_name = {}, {}
    for s in segs:
        if s.kind == "part":
            name = s.cfg["clip"]
            ctx.src_start.setdefault(name, float(s.smap[0]))
            ctx.grade_name.setdefault(name, PARTS.PART_GRADE.get(s.style, "gold"))
    ctx.post = L.Post(ctx.W, ctx.H)
    ctx.fi = 0
    return ctx, segs


def seg_at(segs, t):
    for s in segs:
        if s.t0 <= t < s.t1:
            return s
    return segs[-1]


def draw(ctx, segs, t, fi):
    ctx.fi = fi
    seg = seg_at(segs, t)
    img = PARTS.RENDER[seg.style](ctx, seg, t)
    return ctx.post.finish(img, fi, grain=0.9)


def _worker(args):
    cfg, preview, f0, f1, path = args
    cv2.setNumThreads(1)
    ctx, segs = make_ctx(cfg, preview)
    ff = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{ctx.W}x{ctx.H}",
         "-r", str(ctx.fps), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "10",
         "-pix_fmt", "yuv420p", path], stdin=subprocess.PIPE)
    for fi in range(max(0, f0 - 8), f1):  # a few warm-up frames fill the echo buffers
        img = draw(ctx, segs, fi / ctx.fps, fi)
        if fi >= f0:
            ff.stdin.write(img.tobytes())
    ff.stdin.close()
    ff.wait()
    return path


def render(cfg, preview=False, frame_times=None, workers=4):
    ctx, segs = make_ctx(cfg, preview)
    total = segs[-1].t1
    print(f"timeline: {total:.2f}s")
    for s in segs:
        print(f"  {s.style:9s} {os.path.basename(s.clip.path):12s} {s.t0:6.2f} -> {s.t1:6.2f}"
              f"  ({s.cfg.get('beats', '-')} beats @ {60 / s.period:.1f} bpm)")
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    if frame_times:
        for ft in frame_times:
            fi = int(round(ft * ctx.fps))
            for j in range(max(0, fi - 7), fi):
                draw(ctx, segs, j / ctx.fps, j)
            img = draw(ctx, segs, fi / ctx.fps, fi)
            p = os.path.join(HERE, "out", f"frame_{ft:05.2f}.png")
            cv2.imwrite(p, img)
            print("wrote", p)
        return
    print("rendering audio...")
    audio = render_audio(segs, cfg)
    os.makedirs(CACHE, exist_ok=True)
    wav = os.path.join(CACHE, "edit_audio.wav")
    sf.write(wav, audio, SR)
    n = int(round(total * ctx.fps))
    bounds = np.linspace(0, n, workers + 1).astype(int)
    jobs = [(cfg, preview, int(bounds[i]), int(bounds[i + 1]), os.path.join(CACHE, f"chunk{i}.mp4"))
            for i in range(workers)]
    print(f"rendering {n} frames on {workers} workers...")
    import multiprocessing as mp
    with mp.get_context("spawn").Pool(workers) as pool:
        paths = pool.map(_worker, jobs)
    lst = os.path.join(CACHE, "chunks.txt")
    with open(lst, "w") as f:
        f.writelines(f"file '{p}'\n" for p in paths)
    out_path = os.path.join(HERE, cfg.get("output", "out/edit.mp4"))
    if preview:
        out_path = out_path.replace(".mp4", "_preview.mp4")
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-i", wav,
         "-c:v", "libx264", "-preset", "veryfast" if preview else "slow", "-crf", "23" if preview else "18",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "320k", "-af", "loudnorm=I=-9:TP=-1.0:LRA=6", "-ar", "44100",
         "-movflags", "+faststart", "-shortest", out_path], check=True)
    print("wrote", out_path)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(HERE, "edit.json"))
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--frames", default=None, help="comma separated output times to dump as PNG")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    cfg = json.load(open(a.config))
    ft = [float(x) for x in a.frames.split(",")] if a.frames else None
    render(cfg, preview=a.preview, frame_times=ft, workers=a.workers)
