"""Story edit engine: a chaptered narrative edit built from stream clips, voice lines and a music bed.

The timeline lives in a Python module (e.g. btmc_story.py) that exposes TIMELINE, a dict with
  size, fps, sources, music, shots, voices, events, chapters, sfx, rail
Times are output seconds; source times are seconds inside the source clip.

  python story.py btmc_story --frames 1.0,16.2      dump PNG stills
  python story.py btmc_story --preview               540x960 @30 fps draft
  python story.py btmc_story                         full render
"""
import argparse
import collections
import hashlib
import importlib
import math
import os
import subprocess
import sys

import cv2
import numpy as np
import soundfile as sf

import gfx
import layers as L
import synth as S
import typo
from gfx import clamp01, ease_in_cubic, ease_out_back, ease_out_cubic, ease_out_expo, lerp

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache", "story")
SR = S.SR

WHITE, BLACK = (255, 255, 255), (0, 0, 0)


# ------------------------------------------------------------------ sources
class Src:
    """A video file with a small decoded-frame cache (sequential reads are cheap, seeks are not)."""

    def __init__(self, name, spec):
        self.name = name
        self.path = os.path.join(HERE, spec["file"])
        self.cam = spec.get("cam")          # webcam rect in source pixels [x, y, w, h]
        self.spec = spec
        self.cap = cv2.VideoCapture(self.path)
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 60.0
        self.n = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.pos = -1
        self.cache = collections.OrderedDict()

    def frame(self, t):
        i = int(np.clip(round(t * self.fps), 0, max(0, self.n - 1)))
        if i in self.cache:
            self.cache.move_to_end(i)
            return self.cache[i]
        if not (self.pos < i <= self.pos + 40):
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            self.pos = i - 1
        f = None
        while self.pos < i:
            ok, f = self.cap.read()
            self.pos += 1
            if not ok:
                f = self.cache[next(reversed(self.cache))] if self.cache else np.zeros((self.h, self.w, 3), np.uint8)
                break
            self.cache[self.pos] = f
        while len(self.cache) > 90:
            self.cache.popitem(last=False)
        return f


def _cache_name(path, tag):
    h = hashlib.md5((os.path.abspath(path) + str(os.path.getmtime(path))).encode()).hexdigest()[:10]
    return os.path.join(CACHE, f"{os.path.basename(path)}.{h}.{tag}")


def load_audio(path):
    """Stereo float32 (N, 2) at SR, cached as .npy."""
    os.makedirs(CACHE, exist_ok=True)
    cp = _cache_name(path, "npy")
    if os.path.exists(cp):
        return np.load(cp)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True).stdout
    a = np.frombuffer(raw, np.float32).reshape(-1, 2).copy()
    np.save(cp, a)
    return a


def vocals(path):
    """Voice-only stem of a clip (demucs htdemucs), cached."""
    os.makedirs(CACHE, exist_ok=True)
    cp = _cache_name(path, "vocals.wav")
    if not os.path.exists(cp):
        import torch
        from demucs.apply import apply_model
        from demucs.pretrained import get_model
        x = load_audio(path).T.copy()
        torch.set_num_threads(4)
        model = get_model("htdemucs")
        model.eval()
        wav = torch.from_numpy(x)
        ref = wav.mean(0)
        wav = (wav - ref.mean()) / (ref.std() + 1e-8)
        with torch.no_grad():
            out = apply_model(model, wav[None], device="cpu", shifts=1, split=True, overlap=0.25, progress=False)[0]
        out = out * (ref.std() + 1e-8) + ref.mean()
        voc = out[model.sources.index("vocals")].numpy().T
        sf.write(cp, voc, SR)
    a, _ = sf.read(cp, dtype="float32", always_2d=True)
    return a


# ------------------------------------------------------------------ geometry helpers
def crop_of(src, crop):
    """Crop rect [x, y, w, h] given in 1920x1080 reference pixels, scaled to the source and clamped."""
    if crop is None:
        return 0, 0, src.w, src.h
    sx, sy = src.w / 1920, src.h / 1080
    x, y, w, h = crop[0] * sx, crop[1] * sy, crop[2] * sx, crop[3] * sy
    x, y = max(0, int(x)), max(0, int(y))
    return x, y, int(min(w, src.w - x)), int(min(h, src.h - y))


_MASKS = {}


def _round_mask(w, h, r):
    key = (w, h, r)
    m = _MASKS.get(key)
    if m is None:
        img = gfx.rounded_rect(w, h, r, (255, 255, 255, 255))
        m = np.array(img)[:, :, 3]
        _MASKS[key] = m
    return m


def window_sprite(img, w, h, radius=18, border=3, border_color=(255, 255, 255), border_alpha=0.85):
    """BGRA sprite of img resized to w x h with rounded corners and a thin border."""
    w, h = max(2, int(w)), max(2, int(h))
    body = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA if img.shape[1] > w else cv2.INTER_LINEAR)
    m = _round_mask(w, h, radius)
    spr = np.dstack([body, m])
    if border > 0:
        inner = _round_mask(w - 2 * border, h - 2 * border, max(1, radius - border))
        ring = m.copy()
        ring[border:h - border, border:w - border] = np.minimum(
            ring[border:h - border, border:w - border], 255 - inner)
        a = (ring.astype(np.float32) / 255 * border_alpha)[..., None]
        spr[:, :, :3] = (spr[:, :, :3] * (1 - a) + np.array(border_color[::-1], np.float32) * a).astype(np.uint8)
    return spr


def put_window(canvas, img, cx, cy, w, h, scale=1.0, rx=0.0, ry=0.0, rz=0.0, alpha=1.0, radius=18, border=3,
               border_color=(255, 255, 255), glow=None, shadow=0.55):
    """Draw img as a floating window (optionally tilted in 3D) centred at (cx, cy)."""
    if alpha <= 0.01 or scale <= 0.02:
        return
    k = canvas.shape[1] / 1080
    spr = window_sprite(img, w * k, h * k, int(radius * k), max(1, int(border * k)), border_color)
    hh, ww = spr.shape[:2]
    dst = gfx.project_rect(ww, hh, cx * k, cy * k, scale, rx, ry, rz, f=1800 * k)
    if shadow > 0:
        sh = np.zeros((hh, ww, 4), np.uint8)
        sh[:, :, 3] = (spr[:, :, 3].astype(np.float32) * shadow).astype(np.uint8)
        sh = gfx.hblur(gfx.vblur(sh, 40 * k), 40 * k)
        gfx.warp_sprite(canvas, sh, dst + np.float32([0, 24 * k]), alpha)
    if glow is not None:
        g = np.zeros((hh, ww, 4), np.uint8)
        g[:, :, :3] = glow[::-1]
        g[:, :, 3] = spr[:, :, 3]
        g = gfx.hblur(gfx.vblur(g, 34 * k), 34 * k)
        gfx.warp_sprite(canvas, g, dst, alpha * 0.8, add=True)
    gfx.warp_sprite(canvas, spr, dst, alpha)


def cover(img, W, H, cx=0.5, cy=0.5, zoom=1.0):
    """Centre-crop img to fill W x H (cx, cy = crop centre as fraction of the frame)."""
    h, w = img.shape[:2]
    s = max(W / w, H / h) * zoom
    cw, ch = W / s, H / s
    x0 = np.clip(cx * w - cw / 2, 0, w - cw)
    y0 = np.clip(cy * h - ch / 2, 0, h - ch)
    sub = img[int(y0):int(y0 + ch), int(x0):int(x0 + cw)]
    return cv2.resize(sub, (W, H), interpolation=cv2.INTER_LINEAR)


# ------------------------------------------------------------------ captions
def caption_lines(words, size, fname, max_w):
    """Greedy wrap of [(text, t, hl)] into lines of words."""
    lines, cur, cur_w = [], [], 0
    space = gfx.font(fname, size).getlength(" ")
    for wd in words:
        ww = gfx.font(fname, size).getlength(wd[0])
        if cur and cur_w + space + ww > max_w:
            lines.append(cur)
            cur, cur_w = [], 0
        cur.append(wd)
        cur_w += (space if cur_w else 0) + ww
    if cur:
        lines.append(cur)
    return lines


def draw_caption(ctx, canvas, voice, t):
    """Karaoke-style caption: words pop in as they are spoken; keywords are coloured."""
    k = ctx.k
    at, sin = voice["at"], voice["sin"]
    words = voice.get("words") or []
    if not words:
        return
    t_first = at + (words[0][1] - sin)
    t_last = at + (words[-1][2] - sin)
    end = t_last + voice.get("hold", 0.35)
    if "_next" in voice:
        end = max(t_last + 0.03, min(end, voice["_next"] - 0.13))
    if "until" in voice:
        end = min(end, voice["until"])
    if t < t_first - 0.05 or t > end + 0.1 or t >= voice.get("_next", 1e9) - 0.02:
        return
    size = voice.get("size", 84)
    fname = voice.get("font", "black")
    hl = {"".join(ch for ch in h.upper() if ch.isalnum() or ch in "%'") for h in voice.get("hl", [])}
    hl_color = tuple(voice.get("hl_color", (255, 79, 160)))
    items = []
    for text, s, e in words:
        clean = text.upper()
        key = "".join(ch for ch in clean if ch.isalnum() or ch in "%'")
        items.append((clean, at + (s - sin), key in hl))
    lines = caption_lines(items, size, fname, voice.get("max_w", 920))
    cy0 = voice.get("y", ctx.cap_y)
    lh = size * 1.12
    out_a = 1.0 - clamp01((t - end) / 0.1)
    y = cy0 - (len(lines) - 1) * lh / 2
    space = gfx.font(fname, size).getlength(" ")
    for line in lines:
        widths = [gfx.font(fname, size).getlength(w[0]) for w in line]
        total = sum(widths) + space * (len(line) - 1)
        x = 540 - total / 2
        for (text, ts, is_hl), ww in zip(line, widths):
            u = t - ts
            if u >= -0.02:
                p = clamp01((u + 0.02) / 0.16)
                sc = 0.6 + 0.4 * ease_out_back(p, 2.2)
                color = hl_color if is_hl else WHITE
                glow = 10 if is_hl else 0
                spr = gfx.text_sprite(text, int(size * k), fname, color, int(7 * k), (8, 8, 14), glow,
                                      hl_color if is_hl else None)
                lift = (1 - ease_out_cubic(p)) * 26
                gfx.blit(canvas, spr, (x + ww / 2) * k, (y + lift) * k, sc, 0, out_a * min(1.0, p * 2.5))
            x += ww + space
        y += lh
    sub = voice.get("sub")
    if sub and t >= t_first:
        ssz = voice.get("sub_size", 40)
        spr = gfx.text_sprite(sub, int(ssz * k), voice.get("sub_font", "kr_bold"), (190, 190, 205), int(4 * k), (8, 8, 14))
        gfx.blit(canvas, spr, 540 * k, (y - lh / 2 + ssz * 0.9 + 6) * k, 1.0, 0, out_a * clamp01((t - t_first) / 0.2))
    tag = voice.get("tag")
    if tag and t >= t_first - 0.05:
        spr = gfx.text_sprite(tag, int(24 * k), "mono", tuple(voice.get("tag_color", (160, 160, 175))))
        gfx.blit(canvas, spr, 540 * k, (cy0 - (len(lines) - 1) * lh / 2 - size * 0.95) * k, 1.0, 0, out_a)


# ------------------------------------------------------------------ chapter UI (rail + year)
def draw_rail(ctx, canvas, t):
    TL = ctx.tl
    rail = TL.get("rail")
    if not rail:
        return
    k = ctx.k
    a = ctx.track(t, "rail_alpha")
    if a <= 0.01:
        return
    y0, y1 = rail["years"]
    x0, x1, y = rail["x0"], rail["x1"], rail["y"]
    yr = ctx.track(t, "year")
    acc = ctx.track_color(t, "accent")
    # base line + ticks
    cv2.line(canvas, (int(x0 * k), int(y * k)), (int(x1 * k), int(y * k)), (90, 90, 100), max(1, int(2 * k)),
             cv2.LINE_AA)
    for yy in range(y0, y1 + 1):
        x = x0 + (x1 - x0) * (yy - y0) / (y1 - y0)
        big = yy in (y0, y1)
        hgt = 14 if big else 8
        col = (200, 200, 210) if yy <= yr + 1e-3 else (90, 90, 100)
        cv2.line(canvas, (int(x * k), int((y - hgt) * k)), (int(x * k), int((y + hgt) * k)), col,
                 max(1, int((3 if big else 2) * k)), cv2.LINE_AA)
    xp = x0 + (x1 - x0) * clamp01((yr - y0) / (y1 - y0))
    cv2.line(canvas, (int(x0 * k), int(y * k)), (int(xp * k), int(y * k)), acc[::-1], max(2, int(5 * k)),
             cv2.LINE_AA)
    L.glow_dot(canvas, (xp * k, y * k), 16 * k, acc, 0.9 * a)
    if rail.get("playhead") == "fish":
        draw_fish(canvas, xp * k, (y - 2 + 3 * math.sin(t * 7)) * k, 1.0 * k, acc, t)
    else:
        cv2.circle(canvas, (int(xp * k), int(y * k)), max(2, int(8 * k)), (255, 255, 255), -1, cv2.LINE_AA)
    for yy, align in ((y0, -1), (y1, 1)):
        spr = gfx.text_sprite(str(yy), int(26 * k), "mono", (170, 170, 185))
        x = x0 if align < 0 else x1
        gfx.blit(canvas, spr, x * k, (y + 34) * k, 1.0, 0, a)
    # big year odometer + chapter title
    ya = ctx.track(t, "year_alpha")
    if ya > 0.01:
        vel = (ctx.track(t + 1 / 120, "year") - ctx.track(t - 1 / 120, "year")) * 60
        typo.counter(canvas, round(yr, 3), (rail["year_x"] + 148) * k, rail["year_y"] * k,
                     int(132 * k), "anton", WHITE, digits=4, lead_zeros=False, vel=vel, alpha=ya * a)
    title, tu, tcol = ctx.chapter_title(t)
    if title:
        ts = int(rail.get("title_size", 44) * k)
        tw = gfx.text_layout(title, ts, "unb")[1]
        typo.letters(canvas, title, tu, rail["year_x"] * k + 22 * k + tw / 2, (rail["year_y"] + 96) * k, ts, "unb",
                     tcol, style="rise", stagger=0.018, dur=0.32, alpha=a * ya, seed=len(title))


def draw_fish(canvas, cx, cy, k, color, t):
    """Tiny tuna: body ellipse, wagging tail, eye. Faces right."""
    wag = math.sin(t * 16) * 5 * k
    body_w, body_h = int(26 * k), int(12 * k)
    tail = np.int32([[cx - 22 * k, cy], [cx - 38 * k, cy - 11 * k + wag], [cx - 38 * k, cy + 11 * k + wag]])
    col = color[::-1]
    cv2.fillConvexPoly(canvas, tail, col, cv2.LINE_AA)
    cv2.ellipse(canvas, (int(cx), int(cy)), (body_w, body_h), 0, 0, 360, col, -1, cv2.LINE_AA)
    fin = np.int32([[cx - 4 * k, cy - 10 * k], [cx + 8 * k, cy - 20 * k], [cx + 10 * k, cy - 9 * k]])
    cv2.fillConvexPoly(canvas, fin, col, cv2.LINE_AA)
    cv2.ellipse(canvas, (int(cx + 4 * k), int(cy + 3 * k)), (int(16 * k), int(5 * k)), 0, 0, 180, (255, 255, 255), -1,
                cv2.LINE_AA)
    cv2.circle(canvas, (int(cx + 15 * k), int(cy - 3 * k)), max(1, int(3 * k)), (20, 20, 20), -1, cv2.LINE_AA)


# ------------------------------------------------------------------ keyframe tracks
class Track:
    """Piecewise eased keyframes [(t, value, ease)] -> value(t)."""

    def __init__(self, keys):
        self.keys = sorted(keys, key=lambda k: k[0])

    def __call__(self, t):
        ks = self.keys
        if not ks:
            return 0.0
        if t <= ks[0][0]:
            return ks[0][1]
        for (t0, v0, *_), (t1, v1, *e) in zip(ks, ks[1:]):
            if t0 <= t <= t1:
                if t1 - t0 < 1e-6:
                    return v1
                p = (t - t0) / (t1 - t0)
                ease = e[0] if e else "io"
                if ease == "step":
                    p = 0.0 if p < 1 else 1.0
                elif ease == "out":
                    p = ease_out_expo(p)
                elif ease == "in":
                    p = ease_in_cubic(p)
                elif ease == "lin":
                    pass
                else:
                    p = gfx.ease_in_out_cubic(p)
                if isinstance(v0, tuple):
                    return tuple(a + (b - a) * p for a, b in zip(v0, v1))
                return v0 + (v1 - v0) * p
        return ks[-1][1]


# ------------------------------------------------------------------ context
class Ctx:
    pass


def make_ctx(tl, preview):
    ctx = Ctx()
    ctx.tl = tl
    ctx.W, ctx.H = (540, 960) if preview else tuple(tl.get("size", (1080, 1920)))
    ctx.fps = 30 if preview else tl.get("fps", 60)
    ctx.k = ctx.W / 1080
    ctx.cap_y = tl.get("cap_y", 1500)
    ctx.srcs = {n: Src(n, s) for n, s in tl["sources"].items()}
    ctx.tracks = {n: Track(v) for n, v in tl.get("tracks", {}).items()}
    ctx.post = L.Post(ctx.W, ctx.H)
    ctx.grades = {}
    # a caption must be gone before the next one starts
    caps = [v for v in tl.get("voices", []) if v.get("caption", True) and v.get("words")]
    caps.sort(key=lambda v: v["at"] + v["words"][0][1] - v["sin"])
    for a, b in zip(caps, caps[1:]):
        a["_next"] = b["at"] + b["words"][0][1] - b["sin"]
    chapters = tl.get("chapters", [])

    def chapter_title(t):
        for c in chapters:
            if c["t0"] <= t < c["t1"] and c.get("title"):
                return c["title"], t - c["t0"], tuple(c.get("color", WHITE))
        return None, 0, WHITE

    ctx.chapter_title = chapter_title

    def track(t, name, default=0.0):
        tr = ctx.tracks.get(name)
        return tr(t) if tr else default

    def track_color(t, name):
        tr = ctx.tracks.get(name)
        return tuple(int(v) for v in tr(t)) if tr else (255, 79, 160)

    ctx.track, ctx.track_color = track, track_color
    return ctx


def grade_fn(ctx, spec):
    if not spec:
        return None
    key = repr(spec)
    g = ctx.grades.get(key)
    if g is None:
        g = L.make_grade(spec)
        ctx.grades[key] = g
    return g


# ------------------------------------------------------------------ shot drawing
def shot_frame(ctx, shot, t):
    src = ctx.srcs[shot["src"]]
    u = t - shot["t0"]
    rate = shot.get("rate", 1.0)
    if "freeze" in shot and u >= shot["freeze"]:
        u = shot["freeze"]
    st = shot["sin"] + u * rate
    return src, src.frame(st), st


def shot_entry(shot, t):
    """0..1 entry progress and exit progress for the shot's own transitions."""
    u = t - shot["t0"]
    d_in = shot.get("in_dur", 0.28)
    e_in = clamp01(u / d_in) if d_in > 0 else 1.0
    v = shot["t1"] - t
    d_out = shot.get("out_dur", 0.0)
    e_out = 1 - clamp01(v / d_out) if d_out > 0 else 0.0
    return e_in, e_out


def draw_shot(ctx, canvas, shot, t):
    src, frame, st = shot_frame(ctx, shot, t)
    g = grade_fn(ctx, shot.get("grade"))
    lay = shot.get("layout", "window")
    e_in, e_out = shot_entry(shot, t)
    ei = ease_out_expo(e_in)
    acc = tuple(shot.get("accent", ctx.track_color(t, "accent")))
    u = t - shot["t0"]
    drift = shot.get("drift", 0.02) * u            # slow push-in
    beat = ctx.tl.get("beat")
    pulse = 0.0
    if shot.get("pulse", True):
        bt = ctx.tl.get("beat_times")
        if bt is not None:
            i = int(np.searchsorted(bt, t, "right")) - 1
            if i >= 0:
                pulse = math.exp(-(t - bt[i]) * 18) * 0.014
        elif beat:
            ph = ((t - ctx.tl.get("beat0", 0)) / beat) % 1.0
            pulse = math.exp(-ph * 9) * 0.012
    if lay == "full":
        if shot.get("crop") is not None:
            x, y, w, h = crop_of(src, shot["crop"])
            frame = frame[y:y + h, x:x + w]
        img = cover(frame, ctx.W, ctx.H, *shot.get("focus", (0.5, 0.5)), zoom=shot.get("zoom", 1.0) * (1 + drift))
        if g:
            img = g(img)
        a = ei if shot.get("fade_in") else 1.0
        if a >= 0.999:
            canvas[:] = img
        else:
            cv2.addWeighted(img, a, canvas, 1 - a, 0, canvas)
        return
    win = shot.get("win", {})
    if lay in ("window", "split"):
        x, y, w, h = crop_of(src, shot.get("crop"))
        img = frame[y:y + h, x:x + w]
        if g:
            img = g(img)
        ww = win.get("w", 1000)
        hh = ww * h / w
        cx, cy = win.get("cx", 540), win.get("cy", 880 if lay == "window" else 700)
        sc = (0.86 + 0.14 * ei) * (1 + drift + pulse) * (1 - 0.08 * e_out)
        rx = win.get("rx", 0) + (1 - ei) * win.get("in_rx", 16)
        ry = win.get("ry", 0) + (1 - ei) * win.get("in_ry", 0)
        rz = win.get("rz", 0) * (1 - ei) + win.get("tilt", 0)
        put_window(canvas, img, cx, cy + (1 - ei) * win.get("in_dy", 60), ww, hh, sc, rx, ry, rz,
                   alpha=min(1.0, e_in * 3) * (1 - e_out), radius=win.get("radius", 20),
                   border_color=win.get("border", WHITE), glow=acc if win.get("glow", True) else None)
    if lay in ("face", "split"):
        cam = shot.get("cam") or src.cam
        if cam is None:
            return
        x, y, w, h = crop_of(src, cam)
        img = frame[y:y + h, x:x + w]
        fg = grade_fn(ctx, shot.get("face_grade")) or g
        if fg:
            img = fg(img)
        fw = shot.get("face", {})
        u_f = t - shot["t0"] - fw.get("delay", 0.0 if lay == "face" else 0.12)
        ef = ease_out_back(clamp01(u_f / 0.32), 1.6) if u_f > 0 else 0.0
        ww = fw.get("w", 960 if lay == "face" else 560)
        hh = ww * h / w
        cx = fw.get("cx", 540 if lay == "face" else 700)
        cy = fw.get("cy", 860 if lay == "face" else 1120)
        sc = (0.7 + 0.3 * ef) * (1 + drift * 1.5 + pulse)
        put_window(canvas, img, cx, cy, ww, hh, sc, 0, 0, fw.get("tilt", -2 if lay == "split" else 0),
                   alpha=clamp01(u_f / 0.12) * (1 - e_out), radius=fw.get("radius", 24),
                   border_color=fw.get("border", acc), glow=acc)


def draw_background(ctx, canvas, t, shots):
    bgc = ctx.tl.get("bg", (7, 9, 18))
    canvas[:] = bgc[::-1]
    main = shots[0] if shots else None
    if main is not None and main.get("layout") != "full" and main.get("bg", True):
        if main.get("bg_from"):
            name, st = main["bg_from"]
            frame = ctx.srcs[name].frame(st + (t - main["t0"]))
        else:
            src, frame, _ = shot_frame(ctx, main, t)
        g = grade_fn(ctx, main.get("bg_grade", {"type": "tint", "tint": (0.55, 0.6, 1.0), "sat": 0.6}))
        bg = L.bg_blur(frame, ctx.W, ctx.H, g, dim=main.get("bg_dim", 0.45))
        cv2.add(canvas, bg, canvas)


# ------------------------------------------------------------------ frame
def active(items, t):
    return [it for it in items if it["t0"] <= t < it["t1"]]


def draw(ctx, t, fi):
    TL = ctx.tl
    canvas = np.zeros((ctx.H, ctx.W, 3), np.uint8)
    shots = sorted(active(TL["shots"], t), key=lambda s: s.get("z", 0))
    draw_background(ctx, canvas, t, shots)
    for ev in active(TL.get("events", []), t):
        if ev.get("under"):
            ev["fn"](ctx, canvas, ev, t)
    for s in shots:
        draw_shot(ctx, canvas, s, t)
    for ev in active(TL.get("events", []), t):
        if not ev.get("under") and not ev.get("top"):
            ev["fn"](ctx, canvas, ev, t)
    draw_rail(ctx, canvas, t)
    for v in TL.get("voices", []):
        if v.get("caption", True):
            draw_caption(ctx, canvas, v, t)
    for ev in active(TL.get("events", []), t):
        if ev.get("top"):
            ev["fn"](ctx, canvas, ev, t)
    # post: global fx tracks
    P = ctx.post
    bloom = ctx.track(t, "bloom", 0.35)
    canvas = P.bloom(canvas, bloom)
    zb = ctx.track(t, "zoom_blur", 0.0)
    if zb > 0.004:
        canvas = P.zoom_blur(canvas, zb)
    wh = ctx.track(t, "whip", 0.0)
    if wh > 2:
        canvas = P.dir_blur(canvas, wh * ctx.k, vertical=False)
    rgb = ctx.track(t, "rgb", 0.0)
    if rgb > 0.6:
        canvas = P.rgb_split(canvas, rgb * ctx.k)
    gl = ctx.track(t, "glitch", 0.0)
    if gl > 0.02:
        canvas = P.glitch(canvas, gl, fi // 2)
    fl = ctx.track(t, "flash", 0.0)
    if fl > 0.01:
        canvas = L.flash(canvas, fl, ctx.track_color(t, "flash_color") if "flash_color" in ctx.tracks else WHITE)
    dk = ctx.track(t, "dark", 0.0)
    if dk > 0.01:
        canvas = L.dim(canvas, dk)
    canvas = P.finish(canvas, fi, grain=TL.get("grain", 0.9))
    return canvas


# ------------------------------------------------------------------ audio
def render_audio(tl, total):
    n = int(total * SR) + SR
    music = np.zeros((n, 2), np.float32)
    voice = np.zeros((n, 2), np.float32)
    sfx = np.zeros((n, 2), np.float32)
    act = np.zeros(n, np.float32)
    cache = {}

    def get(path, kind):
        key = (path, kind)
        if key not in cache:
            p = os.path.join(HERE, path)
            cache[key] = vocals(p) if kind == "vocals" else load_audio(p)
        return cache[key]

    for pc in tl.get("music", []):
        a = get(pc["file"], "full")
        s0, s1 = int(pc["from"] * SR), int(pc["to"] * SR)
        seg = a[s0:s1].astype(np.float64) * pc.get("gain", 1.0)
        if pc.get("lp"):
            seg = S.lowpass(seg, pc["lp"], 4)
        if pc.get("hp"):
            seg = S.highpass(seg, pc["hp"], 2)
        if pc.get("reverb"):
            seg = S.reverb(seg, pc["reverb"], wet=0.4)[:len(seg)]
        fi_, fo = int(pc.get("fade_in", 0.006) * SR), int(pc.get("fade_out", 0.006) * SR)
        env = np.ones(len(seg))
        if fi_:
            env[:fi_] = np.linspace(0, 1, fi_) ** 2
        if fo:
            env[-fo:] *= np.linspace(1, 0, fo) ** 2
        S.place(music, seg * env[:, None], int(pc["at"] * SR))
    for v in tl.get("voices", []):
        a = get(tl["sources"][v["src"]]["file"], v.get("kind", "vocals"))
        s0, s1 = int(v["sin"] * SR), int(v["sout"] * SR)
        seg = a[s0:s1].astype(np.float64)
        r = np.sqrt(np.mean(seg ** 2)) + 1e-9
        seg = seg * (10 ** (v.get("db", -15) / 20) / r)
        if v.get("lp"):
            seg = S.lowpass(seg, v["lp"], 2)
        if v.get("hp", 90):
            seg = S.highpass(seg, v.get("hp", 90), 2)
        if v.get("echo"):
            dl = int(v["echo"] * SR)
            out = np.zeros((len(seg) + dl * 4, 2))
            for i in range(4):
                out[i * dl:i * dl + len(seg)] += seg * (0.55 ** i)
            seg = out
        if v.get("reverb"):
            seg = S.reverb(seg, v["reverb"], wet=0.3)
        f = int(0.012 * SR)
        env = np.ones(len(seg))
        env[:f] = np.linspace(0, 1, f)
        env[-f:] *= np.linspace(1, 0, f)
        at = int(v["at"] * SR)
        S.place(voice, seg * env[:, None], at)
        if v.get("duck", True):
            act[max(0, at):min(n, at + int((v["sout"] - v["sin"]) * SR))] = 1.0
    for e in tl.get("sfx", []):
        fn = S.SFX.get(e["name"])
        if fn is None:
            if e["name"] == "riser":
                x = S.riser(e.get("dur", 1.0))
            elif e["name"] == "rev_cymbal":
                x = S.reverse_cymbal(e.get("dur", 0.6))
            else:
                continue
        else:
            x = fn()
        S.place(sfx, np.asarray(x, np.float64) * e.get("gain", 0.5), int(e["at"] * SR))
    # ducking envelope (attack 40 ms, release 260 ms)
    duck_db = tl.get("duck_db", -9.0)
    env = np.zeros(n, np.float32)
    att, rel = 1 - math.exp(-1 / (0.04 * SR)), 1 - math.exp(-1 / (0.26 * SR))
    # vectorised one-pole smoothing in blocks of 64 samples
    blk = 64
    a_blk = act[: n // blk * blk].reshape(-1, blk).max(1)
    e_blk = np.zeros_like(a_blk)
    cur = 0.0
    ab, rb = 1 - (1 - att) ** blk, 1 - (1 - rel) ** blk
    for i, x in enumerate(a_blk):
        cur += (x - cur) * (ab if x > cur else rb)
        e_blk[i] = cur
    env[: len(e_blk) * blk] = np.repeat(e_blk, blk)
    gain = 10 ** (duck_db * env / 20)
    carve = tl.get("duck_carve")          # notch the vocal band of the music while someone talks
    if carve:
        band = S.bandpass(music.astype(np.float64), carve.get("lo", 500), carve.get("hi", 4000), 2)
        g = 10 ** (carve.get("db", -9) / 20)
        music = music - (band * (1 - g) * env[:, None]).astype(np.float32)
    mix = music * gain[:, None] + voice + sfx
    mix = S.master(mix[: int(total * SR)], drive=1.3, ceiling=0.95)
    return mix.astype(np.float32)


# ------------------------------------------------------------------ render
def load_tl(module):
    sys.path.insert(0, HERE)
    mod = importlib.import_module(module)
    return mod.TIMELINE


def _worker(args):
    module, preview, f0, f1, path = args
    cv2.setNumThreads(1)
    tl = load_tl(module)
    ctx = make_ctx(tl, preview)
    ff = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{ctx.W}x{ctx.H}",
         "-r", str(ctx.fps), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "10",
         "-pix_fmt", "yuv420p", path], stdin=subprocess.PIPE)
    for fi in range(f0, f1):
        img = draw(ctx, fi / ctx.fps, fi)
        ff.stdin.write(img.tobytes())
    ff.stdin.close()
    ff.wait()
    return path


def render(module, preview=False, frame_times=None, workers=4, audio_only=False):
    tl = load_tl(module)
    total = tl["duration"]
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    os.makedirs(CACHE, exist_ok=True)
    if frame_times:
        ctx = make_ctx(tl, preview)
        for ft in frame_times:
            img = draw(ctx, ft, int(round(ft * ctx.fps)))
            p = os.path.join(HERE, "out", f"story_{ft:05.2f}.png")
            cv2.imwrite(p, img)
            print("wrote", p)
        return
    print(f"timeline {total:.2f}s; rendering audio...")
    audio = render_audio(tl, total)
    wav = os.path.join(CACHE, f"{module}_audio.wav")
    sf.write(wav, audio, SR)
    if audio_only:
        print("wrote", wav)
        return
    fps = 30 if preview else tl.get("fps", 60)
    n = int(round(total * fps))
    bounds = np.linspace(0, n, workers + 1).astype(int)
    jobs = [(module, preview, int(bounds[i]), int(bounds[i + 1]), os.path.join(CACHE, f"{module}_chunk{i}.mp4"))
            for i in range(workers)]
    print(f"rendering {n} frames on {workers} workers...")
    import multiprocessing as mp
    with mp.get_context("spawn").Pool(workers) as pool:
        paths = pool.map(_worker, jobs)
    lst = os.path.join(CACHE, f"{module}_chunks.txt")
    with open(lst, "w") as f:
        f.writelines(f"file '{p}'\n" for p in paths)
    out_path = os.path.join(HERE, tl.get("output", f"out/{module}.mp4"))
    if preview:
        out_path = out_path.replace(".mp4", "_preview.mp4")
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-i", wav,
         "-c:v", "libx264", "-preset", "veryfast" if preview else "slow", "-crf", "23" if preview else "17",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "320k", "-af", "loudnorm=I=-10:TP=-1.0:LRA=7", "-ar", "44100",
         "-movflags", "+faststart", "-shortest", out_path], check=True)
    print("wrote", out_path)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("module", nargs="?", default="btmc_story")
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--frames", default=None)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--audio", action="store_true", help="only render the audio mix")
    a = ap.parse_args()
    ft = [float(x) for x in a.frames.split(",")] if a.frames else None
    render(a.module, a.preview, ft, a.workers, a.audio)
