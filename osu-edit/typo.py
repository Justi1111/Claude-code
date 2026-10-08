"""Kinetic typography: per-letter animation, text scramble, odometer counters,
labels, stamps, strike-throughs, outline stacks, marquees and text masks.

All functions draw onto a BGR uint8 frame. `u` is the local time in seconds
since the element started. Colours are RGB tuples.
"""
import math
from functools import lru_cache

import cv2
import numpy as np

import gfx
from gfx import clamp01, ease_in_cubic, ease_out_back, ease_out_cubic, ease_out_expo

SCRAMBLE = "ABCDEFGHJKLMNPQRSTUVWXYZ0123456789#$%&*+=/<>?!"


def _hash(*a):
    h = 2166136261
    for v in a:
        h = (h ^ (int(v) & 0xFFFFFFFF)) * 16777619 & 0xFFFFFFFF
    return h


def _rand(*a):
    return (_hash(*a) % 100003) / 100003.0


def _line_metrics(size, fname):
    f = gfx.font(fname, size)
    asc, desc = f.getmetrics()
    return asc, desc


# ------------------------------------------------------------------ letters
def letters(frame, text, u, cx, cy, size, fname="anton", color=(255, 255, 255), style="rise",
            stagger=0.03, dur=0.3, tracking=0, stroke=0, stroke_color=(0, 0, 0), outline_only=False,
            glow=0, glow_color=None, exit_u=None, exit_style="fall", exit_dur=0.28, seed=0, alpha=1.0):
    """Per-letter animated line of text centred at (cx, cy)."""
    if u < 0 or alpha <= 0:
        return
    if exit_u is not None and u > exit_u + exit_dur + stagger * len(text):
        return
    xs, total = gfx.text_layout(text, size, fname, tracking)
    asc, desc = _line_metrics(size, fname)
    lh = asc + desc
    pad = stroke + glow * 3 + 6
    left = cx - total / 2
    top = cy - lh / 2
    n = len(text)
    for i, ch in enumerate(text):
        if ch == " ":
            continue
        spr = gfx.text_sprite(ch, size, fname, color, stroke, stroke_color, glow, glow_color, 0, outline_only)
        h, w = spr.shape[:2]
        gx = left + xs[i] - pad + w / 2
        gy = top - pad + h / 2
        ti = u - i * stagger
        if ti < 0:
            continue
        p = clamp01(ti / dur)
        r1, r2, r3 = _rand(seed, i, 1) * 2 - 1, _rand(seed, i, 2) * 2 - 1, _rand(seed, i, 3) * 2 - 1
        dx = dy = rot = 0.0
        sc, a, blur_v, blur_h = 1.0, 1.0, 0, 0
        clip = None
        if style == "rise":  # slide up from behind the baseline (mask reveal)
            e = ease_out_expo(p)
            dy = (1 - e) * lh * 1.05
            blur_v = (1 - e) * 30
            clip = (0, top + lh * 0.05, frame.shape[1], top + lh * 1.0)
        elif style == "drop":  # fall from above with a springy landing
            e = gfx.spring(ti * 1.0, 2.6, 9)
            dy = -(1 - e) * lh * 1.3
            rot = r1 * 25 * (1 - min(1, ti / dur))
            a = min(1, ti / 0.05)
            blur_v = max(0, (1 - p)) * 25
        elif style == "scale":
            sc = max(0.001, ease_out_back(p, 2.6))
            rot = r1 * 40 * (1 - ease_out_cubic(p))
            a = min(1, ti / 0.05)
        elif style == "slam":
            e = ease_out_cubic(p)
            sc = 1 + 2.2 * (1 - e)
            a = min(1, ti / 0.04)
            blur_v = (1 - e) * 20
        elif style == "scatter":
            e = ease_out_expo(p)
            dx = r1 * 520 * (1 - e)
            dy = r2 * 700 * (1 - e)
            rot = r3 * 160 * (1 - e)
            sc = 1 + 1.5 * (1 - e)
            a = min(1, ti / 0.06)
            blur_h = (1 - e) * 40
        elif style == "flicker":
            if ti < 0.14:
                a = 1.0 if (_hash(seed, i, int(ti * 60)) % 3) else 0.15
            sc = 1 + 0.15 * (1 - ease_out_cubic(p))
        elif style == "spin":
            e = ease_out_back(p, 1.6)
            ry = 90 * (1 - e)
            a = min(1, ti / 0.04)
            if exit_u is None or u <= exit_u:
                dst = gfx.project_rect(w, h, gx, gy, 1.0, 0, ry, 0, f=900)
                gfx.warp_sprite(frame, spr, dst, alpha * a)
                continue
        # exit
        if exit_u is not None and u > exit_u:
            te = u - exit_u - (n - 1 - i) * stagger * 0.5 if exit_style == "fall" else u - exit_u - i * stagger * 0.5
            e = clamp01(te / exit_dur)
            if e > 0:
                if exit_style == "fall":
                    dy += ease_in_cubic(e) * lh * 2.2
                    rot += r1 * 50 * e
                    a *= 1 - e
                elif exit_style == "up":
                    clip = (0, top + lh * 0.05, frame.shape[1], top + lh)
                    dy -= ease_in_cubic(e) * lh * 1.05
                elif exit_style == "scatter":
                    dx += r1 * 600 * ease_in_cubic(e)
                    dy += r2 * 800 * ease_in_cubic(e)
                    rot += r3 * 180 * e
                    a *= 1 - e
                    blur_h = e * 30
                elif exit_style == "glitch":
                    dx += (60 if _hash(seed, i, int(u * 60)) % 2 else -60) * e
                    a *= 1 - e
                else:
                    sc *= 1 + 0.6 * e
                    a *= 1 - e
        if blur_v >= 2:
            spr = gfx.vblur(spr, blur_v)
        if blur_h >= 2:
            spr = gfx.hblur(spr, blur_h)
        if clip is not None:
            gfx.blit_clip(frame, spr, gx + dx, gy + dy, clip, alpha * a)
        else:
            gfx.blit(frame, spr, gx + dx, gy + dy, sc, rot, alpha * a)


# ------------------------------------------------------------------ scramble
def scramble(frame, text, u, cx, cy, size, fname="mono", color=(255, 255, 255), dim_color=None,
             dur=0.45, exit_u=None, seed=0, align="center", tracking=0, alpha=1.0):
    """Decoding text: random glyphs resolve into the final string left to right."""
    if u < 0:
        return
    if exit_u is not None and u > exit_u + 0.2:
        return
    n = len(text)
    xs, total = gfx.text_layout(text, size, fname, tracking)
    asc, desc = _line_metrics(size, fname)
    left = cx - total / 2 if align == "center" else cx
    dim_color = dim_color or tuple(int(c * 0.55) for c in color)
    tick = int(u * 30)
    for i, ch in enumerate(text):
        if ch == " ":
            continue
        appear = i * dur * 0.35 / max(1, n)
        resolve = dur * (0.35 + 0.65 * i / max(1, n)) + 0.08 * _rand(seed, i)
        if u < appear:
            continue
        shown, col = ch, color
        if u < resolve:
            shown = SCRAMBLE[_hash(seed, i, tick) % len(SCRAMBLE)]
            col = dim_color
        if exit_u is not None and u > exit_u:
            e = (u - exit_u) / 0.2
            if _rand(seed, i, 7) < e:
                continue
            shown = SCRAMBLE[_hash(seed, i, tick, 9) % len(SCRAMBLE)]
            col = dim_color
        spr = gfx.text_sprite(shown, size, fname, col)
        pad = 6
        h, w = spr.shape[:2]
        gx = left + xs[i] - pad + w / 2
        gy = cy - (asc + desc) / 2 - pad + h / 2
        gfx.blit(frame, spr, gx, gy, 1.0, 0, alpha)


# ------------------------------------------------------------------ counter
@lru_cache(maxsize=32)
def _digit_strip(size, fname, color, glow, glow_color):
    sprs = [gfx.text_sprite(str(d % 10), size, fname, color, glow=glow, glow_color=glow_color) for d in range(11)]
    w = max(s.shape[1] for s in sprs)
    h = sprs[0].shape[0]
    strip = np.zeros((h * 11, w, 4), np.uint8)
    for i, s in enumerate(sprs):
        x = (w - s.shape[1]) // 2
        strip[i * h:i * h + s.shape[0], x:x + s.shape[1]] = s
    return strip, w, h


def counter(frame, value, cx, cy, size, fname="unb", color=(255, 255, 255), digits=4, prefix="", suffix="",
            vel=0.0, glow=0, glow_color=None, lead_zeros=True, alpha=1.0, scale=1.0, affix_size=None,
            affix_color=None, fps=60):
    """Odometer-style rolling number centred at (cx, cy). Returns the right edge x."""
    if alpha <= 0:
        return cx
    strip, dw, dh = _digit_strip(size, fname, color, glow, glow_color)
    f = gfx.font(fname, size)
    adv = max(f.getlength(str(d)) for d in range(10)) * 1.04
    win = int(dh * 0.74)
    affix_size = affix_size or int(size * 0.55)
    affix_color = affix_color or color
    fa = gfx.font(fname, affix_size)
    pre_w = fa.getlength(prefix) if prefix else 0
    suf_w = fa.getlength(suffix) + size * 0.08 if suffix else 0
    shown = digits
    if not lead_zeros:
        shown = max(1, len(str(int(max(0.0, value)))))
    width = (pre_w + shown * adv + suf_w) * scale
    x = cx - width / 2
    asc, desc = f.getmetrics()
    fasc, fdesc = fa.getmetrics()
    base_dy = (asc - fasc) * 0.5 * scale  # sit affixes on the digits' baseline (roughly)
    if prefix:
        pre = gfx.text_sprite(prefix, affix_size, fname, affix_color, glow=glow, glow_color=glow_color)
        gfx.blit(frame, pre, x + pre_w * scale / 2, cy + base_dy, scale, 0, alpha)
        x += pre_w * scale
    v = max(0.0, value)
    for j in range(digits):
        i = digits - 1 - j  # power of ten
        if not lead_zeros and i >= shown:
            continue
        if i == 0:
            pos = v % 10
        else:
            base = math.floor(v / 10 ** i) % 10
            frac = clamp01((v % 10 ** i) - (10 ** i - 1))
            pos = base + frac
        y0 = int(round(pos * dh + (dh - win) / 2))
        cell = strip[y0:y0 + win]
        if cell.shape[0] < win:
            cell = np.concatenate([cell, strip[: win - cell.shape[0]]], 0)
        speed = abs(vel) / 10 ** i * dh / fps
        if speed > 2:
            cell = gfx.vblur(cell, min(win * 0.8, speed))
        gfx.blit(frame, cell, x + adv * scale / 2, cy, scale, 0, alpha)
        x += adv * scale
    if suffix:
        suf = gfx.text_sprite(suffix, affix_size, fname, affix_color, glow=glow, glow_color=glow_color)
        x += size * 0.08 * scale
        gfx.blit(frame, suf, x + (suf_w - size * 0.08) * scale / 2, cy + base_dy, scale, 0, alpha)
        x += (suf_w - size * 0.08) * scale
    return x


def count_value(u, start, dur, v0=0.0, v1=100.0):
    """Ease-out-expo count from v0 to v1 between start..start+dur. Returns (value, velocity)."""
    p = (u - start) / dur
    if p <= 0:
        return v0, 0.0
    if p >= 1:
        return v1, 0.0
    e = gfx.ease_out_expo(p)
    de = 10 * math.log(2) * 2 ** (-10 * p) / dur
    return v0 + (v1 - v0) * e, (v1 - v0) * de


# ------------------------------------------------------------------ label
def label(frame, num, title, caption, u, x, y, k=1.0, accent=(255, 50, 80), exit_u=None, seed=0,
          title_font="anton", title_size=96):
    """Part label: hollow index number, growing accent line, title rising from a mask."""
    if u < 0:
        return
    if exit_u is not None and u > exit_u + 0.5:
        return
    out = 0.0 if exit_u is None else clamp01((u - exit_u) / 0.3)
    # accent bar grows downward
    g = ease_out_expo(u / 0.25) * (1 - out)
    bar_h = int(150 * k * g)
    if bar_h > 1:
        cv2.rectangle(frame, (int(x), int(y - 75 * k)), (int(x + 8 * k), int(y - 75 * k + bar_h)), accent[::-1], -1)
    # number
    nsz = int(110 * k)
    letters(frame, num, u - 0.04, x + 30 * k + gfx.text_layout(num, nsz, "unb")[1] / 2, y - 6 * k, nsz, "unb",
            (255, 255, 255), "rise", 0.05, 0.3, stroke=max(2, int(3 * k)), outline_only=True,
            exit_u=exit_u, exit_style="up", seed=seed)
    tx = x + 30 * k + gfx.text_layout(num, nsz, "unb")[1] + 26 * k
    tsz = int(title_size * k)
    letters(frame, title, u - 0.1, tx + gfx.text_layout(title, tsz, title_font)[1] / 2, y - 14 * k, tsz, title_font,
            (255, 255, 255), "rise", 0.022, 0.32, exit_u=exit_u, exit_style="up", seed=seed + 1)
    if caption:
        csz = int(30 * k)
        scramble(frame, caption, u - 0.18, tx, y + 52 * k, csz, "mono", accent, dur=0.4, exit_u=exit_u,
                 seed=seed + 2, align="left")


# ------------------------------------------------------------------ stamp
@lru_cache(maxsize=16)
def _stamp_sprite(text, size, color, k):
    f = gfx.font("anton", size)
    tw = int(f.getlength(text))
    asc, desc = f.getmetrics()
    padx, pady, bw = int(34 * k), int(10 * k), max(3, int(9 * k))
    w, h = tw + padx * 2, asc + desc + pady * 2
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle((bw // 2, bw // 2, w - bw // 2 - 1, h - bw // 2 - 1), outline=tuple(color) + (255,), width=bw)
    d.text((padx, pady - int(desc * 0.25)), text, font=f, fill=tuple(color) + (255,))
    a = np.array(img)
    # grungy ink: knock out random speckles
    rs = np.random.default_rng(len(text) * 7 + size)
    noise = cv2.GaussianBlur(rs.random((h, w)).astype(np.float32), (0, 0), 1.2)
    a[..., 3] = (a[..., 3] * np.clip((noise - 0.38) * 6, 0.25, 1)).astype(np.uint8)
    return np.ascontiguousarray(a[:, :, [2, 1, 0, 3]])


def stamp(frame, text, u, cx, cy, size, color=(255, 40, 60), angle=-9, k=1.0, exit_u=None):
    if u < 0 or (exit_u is not None and u > exit_u + 0.15):
        return
    spr = _stamp_sprite(text, int(size), tuple(color), round(k, 3))
    e = ease_out_cubic(u / 0.09)
    sc = 1 + 1.4 * (1 - e)
    a = min(1, u / 0.05)
    j = 10 * k * math.exp(-u * 20)
    if exit_u is not None and u > exit_u:
        a *= 1 - (u - exit_u) / 0.15
    gfx.blit(frame, spr, cx + j * math.sin(u * 90), cy + j * math.cos(u * 70), sc, angle, a)


# ------------------------------------------------------------------ strike
def strike(frame, p0, p1, u, dur=0.18, color=(255, 30, 50), thick=18):
    if u < 0:
        return
    e = ease_out_expo(u / dur)
    p0 = np.array(p0, float)
    p1 = p0 + (np.array(p1, float) - p0) * e
    cv2.line(frame, tuple(int(v) for v in p0), tuple(int(v) for v in p1), color[::-1], int(thick), cv2.LINE_AA)


# ------------------------------------------------------------------ outline stack
def outline_stack(frame, text, u, cx, cy, size, fname="anton", color=(255, 255, 255), n=5, spread=0.11,
                  stroke=3, dur=0.5, alpha=1.0, tracking=0):
    """Hollow copies of the text expanding outward (zoom echo)."""
    if u < 0 or alpha <= 0:
        return
    spr = gfx.text_sprite(text, size, fname, color, stroke=stroke, outline_only=True, tracking=tracking)
    e = ease_out_expo(u / dur)
    for i in range(1, n + 1):
        sc = 1 + i * spread * e
        a = alpha * (1 - i / (n + 1)) * (0.4 + 0.6 * (1 - e * 0.5))
        gfx.blit(frame, spr, cx, cy, sc, 0, a)


# ------------------------------------------------------------------ marquee
@lru_cache(maxsize=16)
def _band(text, size, fname, fg, bg, height, length):
    unit = gfx.text_sprite(text, size, fname, fg)
    uw = unit.shape[1]
    reps = int(length / uw) + 3
    band = np.zeros((height, uw * reps, 4), np.uint8)
    band[:, :, :3] = bg[::-1]
    band[:, :, 3] = 255 if bg is not None else 0
    y = (height - unit.shape[0]) // 2
    for r in range(reps):
        sub = band[max(0, y):max(0, y) + unit.shape[0], r * uw:(r + 1) * uw]
        uu = unit[max(0, -y):max(0, -y) + sub.shape[0]]
        a = uu[:, :, 3:4].astype(np.float32) / 255
        sub[:, :, :3] = (sub[:, :, :3] * (1 - a) + uu[:, :, :3] * a).astype(np.uint8)
    return band, uw


def marquee(frame, text, t, cx, cy, angle, speed, size, fname="anton", fg=(0, 0, 0), bg=(255, 255, 255),
            height=None, length=None, alpha=1.0, enter=1.0):
    """Scrolling text band rotated by `angle`. enter in 0..1 slides it in from the side."""
    if alpha <= 0 or enter <= 0:
        return
    H, W = frame.shape[:2]
    length = int(length or math.hypot(W, H) * 1.1)
    height = int(height or size * 1.35)
    band, uw = _band(text, int(size), fname, tuple(fg), tuple(bg), height, length)
    off = int((t * speed) % uw)
    win = band[:, off:off + length]
    shift = (1 - gfx.ease_out_expo(enter)) * length * (1 if speed > 0 else -1)
    rad = math.radians(angle)
    gfx.blit(frame, win, cx - shift * math.cos(rad), cy + shift * math.sin(rad), 1.0, angle, alpha)


# ------------------------------------------------------------------ text mask
@lru_cache(maxsize=16)
def _mask_full(text, size, fname, tracking, W, H, cx, cy):
    m = gfx.text_mask(text, size, fname, tracking)
    full = np.zeros((H, W), np.float32)
    h, w = m.shape
    x0, y0 = int(cx - w / 2), int(cy - h / 2)
    xs, ys = max(0, -x0), max(0, -y0)
    x1, y1 = min(W, x0 + w), min(H, y0 + h)
    full[max(0, y0):y1, max(0, x0):x1] = m[ys:ys + y1 - max(0, y0), xs:xs + x1 - max(0, x0)]
    return full


def mask_fill(canvas, text, size, fname, cx, cy, fill_img, alpha=1.0, tracking=0):
    """Show fill_img (full-canvas BGR) through the letters of `text`."""
    H, W = canvas.shape[:2]
    m = _mask_full(text, int(size), fname, int(tracking), W, H, int(cx), int(cy))[..., None] * alpha
    canvas[:] = (canvas.astype(np.float32) * (1 - m) + fill_img.astype(np.float32) * m).astype(np.uint8)
