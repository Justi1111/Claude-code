"""Part styles. Every part of the edit has its own editing language:

  hook      hit circle pops -> flash cuts + ransom-note letters -> word assembles
  record    red duotone, gameplay on a swinging 3D card, rolling pp counter,
            freeze-frame stamp, zoom-through exit
  reign     violet neon, 3-band split screen that slides/swaps/collapses,
            day counter, crossing marquees, stutter + slice exit
  trophies  ice duotone, 3D flipping trophy cards with shine, close-up cut
            barrage with negative flashes, tape-stop exit
  return    muffled black & white "#1 lost" (strike-through), gold impact
            "#1 again", 3x3 grid, accelerating montage of every clip
  outro     gameplay inside the letters, outline echoes, glitch out

Each style renders a full canvas for output time t; SFX_* functions return the
sound effects that belong to its motion (time, name, gain).
"""
import math
from functools import lru_cache

import cv2
import numpy as np
from PIL import Image, ImageDraw

import gfx
import layers as L
import typo
from gfx import clamp01, ease_in_expo, ease_in_out_cubic, ease_in_out_expo, ease_out_back, ease_out_cubic, ease_out_expo, lerp
from layers import View

# ======================================================================= palettes
GRADE_SPECS = {
    "red": {"type": "duo", "dark": (16, 0, 6), "mid": (225, 22, 50), "light": (255, 238, 238), "contrast": 1.35},
    "red_hard": {"type": "duo", "dark": (0, 0, 0), "mid": (150, 0, 25), "light": (255, 255, 255), "contrast": 1.9},
    "violet": {"type": "tint", "tint": (1.06, 0.78, 1.28), "sat": 1.35, "contrast": 1.3, "lift": -0.03},
    "cyan": {"type": "duo", "dark": (0, 8, 22), "mid": (0, 150, 235), "light": (225, 252, 255), "contrast": 1.35},
    "magenta": {"type": "duo", "dark": (18, 0, 20), "mid": (250, 0, 160), "light": (255, 228, 250), "contrast": 1.35},
    "ice": {"type": "duo", "dark": (2, 10, 22), "mid": (50, 140, 195), "light": (218, 246, 255), "contrast": 1.3},
    "ice_hot": {"type": "duo", "dark": (0, 6, 18), "mid": (0, 185, 255), "light": (240, 255, 255), "contrast": 1.45},
    "gold": {"type": "tint", "tint": (1.28, 1.0, 0.66), "sat": 1.35, "contrast": 1.3, "lift": -0.02},
    "gold_duo": {"type": "duo", "dark": (16, 8, 0), "mid": (230, 150, 22), "light": (255, 246, 215), "contrast": 1.35},
    "bw": {"type": "bw", "contrast": 1.4, "tint": (0.92, 0.98, 1.06)},
}
ACCENT = {"record": (255, 40, 70), "reign": (185, 95, 255), "trophies": (0, 205, 255), "return": (255, 190, 40)}
PART_GRADE = {"record": "red", "reign": "violet", "trophies": "ice_hot", "return": "gold"}
_grades = {}


def grade(name):
    if name not in _grades:
        _grades[name] = L.make_grade(GRADE_SPECS[name])
    return _grades[name]


# ======================================================================= helpers
def bpos(seg, t):
    return (t - seg.t0) / seg.period


def dec(x, k):
    return math.exp(-x * k) if x >= 0 else 0.0


def beat_env(b, P, k=12.0):
    return dec((b - math.floor(b)) * P, k)


def bar_env(b, P, k=8.0):
    return dec((b - 4 * math.floor(b / 4)) * P, k)


def full(ctx):
    return L.rect_quad(0, 0, ctx.W, ctx.H)


def roll_env(b, P, amp):
    """Alternating camera roll kick on each beat."""
    i = math.floor(b)
    return amp * (1 if i % 2 else -1) * dec((b - i) * P, 7)


def zoom_canvas(img, s, c=None, rot=0.0):
    if abs(s - 1) < 1e-3 and rot == 0:
        return img
    H, W = img.shape[:2]
    c = c if c is not None else (W / 2, H / 2)
    M = cv2.getRotationMatrix2D((float(c[0]), float(c[1])), rot, s)
    return cv2.warpAffine(img, M, (W, H), borderMode=cv2.BORDER_REFLECT)


def hblur_rows(canvas, y0, y1, L_):
    y0, y1 = max(0, int(y0)), min(canvas.shape[0], int(y1))
    if L_ >= 3 and y1 > y0:
        canvas[y0:y1] = cv2.blur(canvas[y0:y1], (int(L_), 1))


@lru_cache(maxsize=64)
def glyph_offset(ch, size, fname):
    """Offset from a glyph's visual centre to its text_sprite centre."""
    f = gfx.font(fname, size)
    x0, y0, x1, y1 = f.getbbox(ch)
    asc, desc = f.getmetrics()
    return f.getlength(ch) / 2 - (x0 + x1) / 2, (asc + desc) / 2 - (y0 + y1) / 2


def word_glyph_centres(word, size, fname, cx, cy):
    xs, total = gfx.text_layout(word, size, fname)
    f = gfx.font(fname, size)
    out = []
    for i, ch in enumerate(word):
        x0, y0, x1, y1 = f.getbbox(ch)
        out.append((cx - total / 2 + xs[i] + (x0 + x1) / 2, cy))
    return out


def bg_type(canvas, text, t, y, speed, size, color, alpha=0.18, stroke=3):
    """Huge hollow background typography scrolling horizontally."""
    spr = gfx.text_sprite(text, size, "anton", color, stroke=stroke, outline_only=True)
    uw = spr.shape[1]
    W = canvas.shape[1]
    off = (t * speed) % uw
    x = -off
    while x < W + uw:
        gfx.blit(canvas, spr, x + uw / 2, y, 1.0, 0, alpha)
        x += uw


def window_dims(ctx, frac=0.92):
    ww = ctx.W * frac
    return ww, ww * 0.75


# ======================================================================= HOOK
HOOK_LOOKS = [  # (fg, box, hollow)
    ((10, 10, 10), (255, 255, 255), False),
    ((255, 255, 255), (230, 20, 48), False),
    ((255, 255, 255), None, True),
    ((255, 210, 60), (12, 12, 12), False),
    ((255, 255, 255), (120, 40, 255), False),
]
COLLAGE = [(0.28, 0.27, 1.0, -11), (0.72, 0.33, 0.85, 9), (0.32, 0.62, 0.95, 7), (0.70, 0.68, 1.05, -8),
           (0.50, 0.46, 1.15, 4)]


@lru_cache(maxsize=32)
def boxed_letter(ch, size, fg, box, hollow):
    f = gfx.font("anton", size)
    x0, y0, x1, y1 = f.getbbox(ch)
    pad = int(size * 0.1)
    w, h = int(x1 - x0 + 2 * pad), int(y1 - y0 + 2 * pad)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if box:
        d.rectangle((0, 0, w - 1, h - 1), fill=tuple(box) + (255,))
    if hollow:
        sw = max(3, size // 45)
        m1 = Image.new("L", (w, h), 0)
        m2 = Image.new("L", (w, h), 0)
        ImageDraw.Draw(m1).text((pad - x0, pad - y0), ch, font=f, fill=255, stroke_width=sw, stroke_fill=255)
        ImageDraw.Draw(m2).text((pad - x0, pad - y0), ch, font=f, fill=255)
        a = np.clip(np.array(m1, np.int16) - np.array(m2, np.int16), 0, 255).astype(np.uint8)
        col = Image.new("RGBA", (w, h), tuple(fg) + (255,))
        img.paste(col, (0, 0), Image.fromarray(a))
    else:
        d.text((pad - x0, pad - y0), ch, font=f, fill=tuple(fg) + (255,))
    return gfx.pil_to_bgra(img)


def render_hook(ctx, seg, t):
    W, H, k = ctx.W, ctx.H, ctx.k
    P, b = seg.period, bpos(seg, t)
    cfg = seg.cfg
    word = cfg.get("word", "MREKK")
    canvas = L.bg_gradient(W, H, (10, 8, 12), (0, 0, 0))
    cuts = [1, 1.5, 2, 2.5, 3, 3.25, 3.5, 3.75]
    shots = cfg.get("flash", [])
    u_cut, flash = 9.0, 0.0
    if b >= 1 and shots:
        ci = max(i for i, c in enumerate(cuts) if b >= c)
        name = shots[ci % len(shots)]
        clip = ctx.clips[name]
        st = ctx.src_start[name] + (b - 1) * P + ci * 0.37
        frame = clip.frame(st)
        g = grade(ctx.grade_name[name])
        u_cut = (b - cuts[ci]) * P
        if ci % 2 == 0:
            L.put_shot(canvas, frame, clip, st, View(2.2 + 0.35 * (ci % 3), 0.85, rot=-6 if ci % 4 == 0 else 5),
                       full(ctx), g)
        else:
            canvas[:] = L.bg_blur(frame, W, H, g, 0.4)
            ww, wh = window_dims(ctx, 0.9)
            dst = gfx.project_rect(ww, wh, W / 2, H * 0.46, 1.0 + 0.07 * dec(u_cut, 9), 7,
                                   -15 if ci % 4 == 1 else 15, 0, 1700 * k)
            L.put_shot(canvas, frame, clip, st, View(1.0, 0.3), dst, g)
            L.quad_outline(canvas, dst, (255, 255, 255), 3 * k)
        canvas = L.dim(canvas, 0.2 + 0.45 * clamp01((b - 3) / 0.5))
        flash = 0.35 * dec(u_cut, 16)
    # the hit circle
    c = (W / 2, H * 0.46)
    r = 175 * k
    if b < 1:
        L.hit_circle(canvas, c, r, 1 - b, (230, 30, 60), min(1, 0.25 + b / 0.3), "1", k)
    else:
        u = (b - 1) * P
        if u < 0.22:
            e = u / 0.22
            L.hit_circle(canvas, c, r * (1 + 0.6 * ease_out_expo(e)), 0, (230, 30, 60), 1 - e, "1", k)
        L.shockwave(canvas, c, u, k, (255, 255, 255), 1.4, 0.5)
        L.sparks(canvas, c, u, 11, k, 44, (255, 225, 205), 1900, 0.6)
        L.speed_lines(canvas, c, 0.9 * dec(u, 6), ctx.fi, k)
    # ransom-note letters stamped one per half beat, then they assemble
    fsz = int(330 * k)
    targets = word_glyph_centres(word, fsz, "anton", W / 2, H * 0.46)
    fly = clamp01((b - 3.0) / 0.8)
    e = ease_in_out_expo(fly)
    for i, ch in enumerate(word):
        bi = 1 + 0.5 * i
        if b < bi:
            continue
        u = (b - bi) * P
        px, py, sz, rot = COLLAGE[i % len(COLLAGE)]
        fg, box, hollow = HOOK_LOOKS[i % len(HOOK_LOOKS)]
        spr = boxed_letter(ch, int(420 * k * sz), fg, box, hollow)
        stamp = 1 + 1.3 * (1 - ease_out_cubic(u / 0.09))
        j = 14 * k * dec(u, 18)
        x = lerp(px * W, targets[i][0], e) + j * math.sin(u * 90)
        y = lerp(py * H, targets[i][1], e) + j * math.cos(u * 71)
        rr = lerp(rot, 0, e)
        if e < 1:
            s2 = spr if fly <= 0 or fly >= 1 else gfx.hblur(spr, 40 * k * math.sin(math.pi * fly))
            gfx.blit(canvas, s2, x, y, stamp * lerp(1, 0.75, e), rr, (1 - e) * min(1, u / 0.04))
        if e > 0:
            plain = gfx.text_sprite(ch, fsz, "anton", (255, 255, 255), glow=int(12 * k), glow_color=(230, 30, 60))
            ox, oy = glyph_offset(ch, fsz, "anton")
            gfx.blit(canvas, plain, x + ox, y + oy, lerp(1.35, 1.0, e), rr, e)
    if b >= 3.7:
        typo.outline_stack(canvas, word, (b - 3.7) * P, W / 2 + glyph_offset("M", fsz, "anton")[0] * 0,
                           H * 0.46 + glyph_offset("M", fsz, "anton")[1], fsz, "anton", (255, 60, 90), 4, 0.1, int(3 * k))
    if b >= 3.15:
        typo.scramble(canvas, cfg.get("sub", "THE STORY OF THE #1"), (b - 3.15) * P, W / 2, H * 0.57,
                      int(40 * k), "mono", (255, 255, 255), dur=0.35, tracking=int(5 * k), seed=5)
    img = ctx.post.bloom(canvas, 0.6)
    img = ctx.post.rgb_split(img, 3 * k + 26 * k * dec(u_cut, 12) + (30 * k * dec((b - 1) * P, 8) if b >= 1 else 0))
    if u_cut < 0.05:
        img = ctx.post.glitch(img, 0.8, ctx.fi)
    flash = max(flash, 0.8 * dec((b - 1) * P, 7) if b >= 1 else 0, ease_in_expo((b - 3.65) / 0.35))
    return L.flash(img, flash)


def sfx_hook(seg):
    P, t0 = seg.period, seg.t0
    out = [(t0 + 1 * P, "hit", 1.0), (t0 + 1 * P, "impact", 0.55)]
    word = seg.cfg.get("word", "MREKK")
    for i in range(len(word)):
        out.append((t0 + (1 + 0.5 * i) * P, "stamp", 0.7))
    out += [(t0 + 3.0 * P, "whoosh", 0.7), (t0 + 3.15 * P, "scramble", 0.35)]
    return out


# ======================================================================= RECORD
def render_record(ctx, seg, t):
    W, H, k = ctx.W, ctx.H, ctx.k
    P, b, cfg = seg.period, bpos(seg, t), seg.cfg
    nb = cfg["beats"]
    clip = seg.clip
    acc = ACCENT["record"]
    fz0 = cfg.get("freeze", nb - 4)
    zt0 = nb - 2
    frozen = b >= fz0
    st = seg.src(seg.t0 + fz0 * P) if frozen else seg.src(t)
    frame = clip.frame(st)
    g = grade("red_hard" if frozen else "red")
    canvas = L.bg_gradient(W, H, (52, 0, 12), (4, 0, 2))
    for yy, spd in ((0.18, -110), (0.5, 150), (0.82, -130)):
        bg_type(canvas, cfg.get("bg_word", "RECORD") + "  ", t, H * yy, spd * k, int(300 * k), (255, 50, 80), 0.12,
                max(2, int(3 * k)))
    # swinging 3D card
    ww, wh = window_dims(ctx)
    cy = H * 0.425
    d = int(b // 4)
    tg = [-14, 12, -10, 13]
    prev = tg[(d - 1) % 4] if d > 0 else 0.0
    sw = ease_out_back(((b - 4 * d) * P) / 0.42, 1.7)
    ry = lerp(prev, tg[d % 4], sw)
    rx = 5 * math.sin(t * 1.9)
    rz = 1.3 * math.sin(t * 1.3)
    punch = 0.03 * beat_env(b, P, 13) + 0.035 * bar_env(b, P, 9)
    scale = 1 + punch
    if b < 0.7:
        e = ease_out_expo(b / 0.7)
        scale *= 1 + 0.9 * (1 - e)
        rz += -12 * (1 - e)
    if frozen and b < zt0:
        scale *= 1 + 0.07 * (b - fz0) / max(0.1, zt0 - fz0)
        ry *= 0.4
    ez = ease_in_expo((b - zt0) / 2) if b >= zt0 else 0.0
    view = View(1.03, 0.35)
    src_q = L.view_quad(clip, st, view, ww / wh)
    dst0 = gfx.project_rect(ww, wh, W / 2, cy, scale, rx, ry, rz, 1700 * k)
    act0 = L.map_point(cv2.getPerspectiveTransform(src_q, dst0), clip.centre(st))
    scale *= 1 + 7 * ez
    offx, offy = (W / 2 - act0[0]) * ez * 7, (H * 0.48 - act0[1]) * ez * 7
    dst = gfx.project_rect(ww, wh, W / 2 + offx, cy + offy, scale, rx, ry, rz, 1700 * k)
    M = L.put_shot(canvas, frame, clip, st, view, dst, g)
    act = L.map_point(M, clip.centre(st))
    L.quad_outline(canvas, dst, (255, 255, 255), 3 * k)
    L.brackets(canvas, dst, (46 + 40 * bar_env(b, P, 7)) * k, 20 * k, acc, 5 * k)
    for db in range(0, nb, 4):
        L.shockwave(canvas, act, (b - db) * P, k, (255, 90, 110), 0.85)
        L.sparks(canvas, act, (b - db) * P, 100 + db, k, 22, (255, 120, 140), 1300, 0.45)
    L.speed_lines(canvas, act, 1.2 * ez, ctx.fi, k, 70, (255, 200, 210))
    if frozen:
        typo.stamp(canvas, cfg.get("stamp", "RECORD"), (b - fz0) * P, W / 2, cy, int(165 * k), acc, -9, k,
                   exit_u=(zt0 - fz0) * P)
    # typography
    lab = cfg.get("label", ["01", "THE RECORD", "PP RECORD // STD"])
    typo.label(canvas, lab[0], lab[1], lab[2], (b - 0.35) * P, 56 * k, H * 0.1, k, acc, exit_u=(zt0 - 0.3) * P, seed=11)
    cc = cfg["counter"]
    c0, c1 = cc.get("beats", [1.0, 6.5])
    val, vel = typo.count_value(b * P, c0 * P, (c1 - c0) * P, cc.get("from", 0), cc["to"])
    land = (b - c1) * P
    pop = 1 + 0.2 * dec(land, 11) if land >= 0 else 1.0
    a_c = clamp01((b - c0 + 0.3) / 0.3) * (1 - clamp01((b - zt0) / 0.35))
    digits = len(str(cc["to"]))
    typo.counter(canvas, val, W / 2, H * 0.735, int(185 * k), "unb", (255, 255, 255), digits, cc.get("prefix", ""),
                 cc.get("suffix", "PP"), vel, int(12 * k), acc, lead_zeros=False, alpha=a_c, scale=pop, affix_color=acc,
                 fps=ctx.fps)
    if land >= 0 and b < zt0:
        typo.outline_stack(canvas, f"{cc['to']}", land, W / 2 - 40 * k, H * 0.735, int(185 * k), "unb",
                           acc, 4, 0.09, max(2, int(3 * k)), 0.5, 0.8)
    ex = (zt0 - 2) * P
    typo.scramble(canvas, cfg.get("caption", ""), (b - 2.0) * P, W / 2, H * 0.81, int(42 * k), "mono",
                  (255, 255, 255), exit_u=ex, seed=21)
    typo.scramble(canvas, cfg.get("sub", ""), (b - 2.6) * P, W / 2, H * 0.843, int(31 * k), "mono", (255, 130, 145),
                  exit_u=ex, seed=22)
    # post
    img = ctx.post.bloom(canvas, 0.7 + 3 * punch)
    img = ctx.post.rgb_split(img, 3 * k + 24 * k * bar_env(b, P, 10) + 60 * k * ez)
    if b < 0.6:
        img = ctx.post.zoom_blur(img, 0.07 * (1 - b / 0.6))
    if ez > 0.01:
        img = ctx.post.zoom_blur(img, 0.13 * ez, act)
    fl = max(0.7 * dec(b * P, 7), 0.6 * dec((b - fz0) * P, 9) if frozen else 0.0,
             0.12 * beat_env(b, P, 20) if frozen and b < zt0 else 0.0, ease_in_expo((b - (nb - 0.3)) / 0.3))
    return L.flash(img, fl)


def sfx_record(seg):
    P, t0, cfg = seg.period, seg.t0, seg.cfg
    nb = cfg["beats"]
    out = [(t0 + 0.35 * P, "swipe", 0.5)]
    c0, c1 = cfg["counter"].get("beats", [1.0, 6.5])
    out += ticks(t0 + c0 * P, (c1 - c0) * P, cfg["counter"].get("from", 0), cfg["counter"]["to"])
    out.append((t0 + c1 * P, "pop", 0.8))
    out.append((t0 + 2.0 * P, "scramble", 0.3))
    fz0 = cfg.get("freeze", nb - 4)
    out += [(t0 + fz0 * P, "stamp", 1.0), (t0 + fz0 * P, "glitch", 0.5)]
    return out


def ticks(start, dur, v0, v1, max_rate=24):
    """Counter tick sounds: dense while the number races, sparse as it settles."""
    out, last = [], -1.0
    steps = 400
    prev_v = v0
    for i in range(steps):
        u = dur * i / steps
        v, _ = typo.count_value(u, 0, dur, v0, v1)
        if int(v) != int(prev_v) and u - last >= 1 / max_rate:
            out.append((start + u, "tick", 0.32))
            last = u
        prev_v = v
    return out


# ======================================================================= REIGN
def render_reign(ctx, seg, t):
    W, H, k = ctx.W, ctx.H, ctx.k
    P, b, cfg = seg.period, bpos(seg, t), seg.cfg
    nb = cfg["beats"]
    clip = seg.clip
    acc = ACCENT["reign"]
    st = seg.src(t)
    frame = clip.frame(st)
    gV, gC, gM = grade("violet"), grade("cyan"), grade("magenta")
    canvas = L.bg_gradient(W, H, (26, 0, 44), (0, 0, 0))
    gap = 10 * k
    bh = (H - 2 * gap) / 3
    ys = [0, bh + gap, 2 * (bh + gap)]
    VT, VM, VB = View(2.6, 0.92), View(1.12, 0.4), View(2.2, 0.92, flip=True)
    if b < 7:
        col = ease_in_out_cubic(clamp01(b - 6))
        swap = ease_out_expo(clamp01((b - 4) / 0.45))
        for i in range(3):
            enter = clamp01((b - 0.17 * i) / 0.5)
            ex = (1 - ease_out_expo(enter)) * W * (1 if i % 2 else -1)
            y0, y1 = ys[i], ys[i] + bh
            if i == 1:
                y0, y1 = lerp(ys[1], 0, col), lerp(ys[1] + bh, H, col)
                v = View(lerp(1.12, 2.05, col) * (1 + 0.04 * beat_env(b, P, 12)), lerp(0.4, 0.85, col))
                L.put_shot(canvas, frame, clip, st, v, L.rect_quad(ex, y0, ex + W, y1), gV)
            else:
                dy = (-1 if i == 0 else 1) * bh * 1.3 * col
                y0, y1 = y0 + dy, y1 + dy
                a_view, a_g = (VT, gC) if i == 0 else (VB, gM)
                b_view, b_g = (VB, gM) if i == 0 else (VT, gC)
                if swap <= 0:
                    L.put_shot(canvas, frame, clip, st, a_view, L.rect_quad(ex, y0, ex + W, y1), a_g)
                else:  # push transition: old slides out, new slides in
                    dirn = 1 if i == 0 else -1
                    if swap < 1:
                        o = swap * W * dirn
                        L.put_shot(canvas, frame, clip, st, a_view, L.rect_quad(o, y0, o + W, y1), a_g)
                    n = (swap - 1) * W * dirn
                    L.put_shot(canvas, frame, clip, st, b_view, L.rect_quad(n, y0, n + W, y1), b_g)
                    if 0 < swap < 1:
                        hblur_rows(canvas, y0, y1, 90 * k * (1 - swap))
            if 0 < enter < 1:
                hblur_rows(canvas, y0, y1, 140 * k * (1 - enter))
        if col <= 0:
            for yl in (bh + gap / 2, 2 * bh + 1.5 * gap):
                g_ = ease_out_expo(clamp01((b - 0.45) / 0.4))
                cv2.line(canvas, (int(W / 2 - W / 2 * g_), int(yl)), (int(W / 2 + W / 2 * g_), int(yl)),
                         (255, 255, 255), max(1, int(3 * k)), cv2.LINE_AA)
    else:
        v = View(2.05 * (1 + 0.06 * beat_env(b, P, 12)), 0.85, rot=roll_env(b, P, 4))
        L.put_shot(canvas, frame, clip, st, v, full(ctx), gV)
    # echo trails in the full-screen part
    post = ctx.post
    if b >= 7 and len(post.echo) >= 6:
        e1 = cv2.multiply(post.echo[-3], (1.0, 0.35, 0.95, 0))
        e2 = cv2.multiply(post.echo[-6], (1.0, 0.9, 0.2, 0))
        canvas = cv2.max(canvas, cv2.max(cv2.convertScaleAbs(e1, alpha=0.75), cv2.convertScaleAbs(e2, alpha=0.5)))
    post.echo.append(canvas.copy())
    # typography
    lab = cfg.get("label", ["02", "THE REIGN", "GLOBAL #1 // DAYS"])
    typo.label(canvas, lab[0], lab[1], lab[2], (b - 0.55) * P, 56 * k, H * 0.1, k, acc, exit_u=5.5 * P, seed=31)
    cc = cfg["counter"]
    c0, c1 = cc.get("beats", [1.2, 5.0])
    val, vel = typo.count_value(b * P, c0 * P, (c1 - c0) * P, cc.get("from", 1), cc["to"])
    land = (b - c1) * P
    out_e = clamp01((b - 5.6) / 0.35)
    a_c = clamp01((b - c0 + 0.3) / 0.3) * (1 - out_e)
    cy = ys[1] + bh / 2
    pop = 1 + 0.18 * dec(land, 11) if land >= 0 else 1.0
    right = typo.counter(canvas, val, W / 2 - 30 * k, cy, int(165 * k), "unb", (255, 255, 255), len(str(cc["to"])),
                         cc.get("prefix", "DAY "), "", vel, int(12 * k), acc, lead_zeros=True, alpha=a_c, scale=pop,
                         affix_size=int(70 * k), affix_color=acc, fps=ctx.fps)
    if land >= 0 and a_c > 0:
        plus = gfx.text_sprite(cc.get("after", "+"), int(150 * k), "unb", acc, glow=int(10 * k), glow_color=acc)
        gfx.blit(canvas, plus, right + plus.shape[1] * 0.35, cy - 6 * k, ease_out_back(land / 0.25, 3.0), 0, a_c)
        typo.outline_stack(canvas, f"{cc['to']}", land, W / 2 + 40 * k, cy, int(165 * k), "unb", acc, 4, 0.1,
                           max(2, int(3 * k)), 0.5, a_c)
    typo.letters(canvas, cfg.get("caption", "AS THE GLOBAL #1"), (b - 2.0) * P, W / 2, cy + 135 * k, int(74 * k),
                 "anton", (255, 255, 255), "rise", 0.022, 0.3, exit_u=(5.55 - 2.0) * P, exit_style="up", seed=32)
    if b >= 7:
        m1, m2 = cfg.get("marquee", ["GLOBAL #1  •  ", "1200+ DAYS  •  "])
        en = clamp01((b - 7) / 0.5)
        typo.marquee(canvas, m1, t, W / 2, H * 0.74, -9, 380 * k, int(64 * k), "anton", (10, 0, 20), acc, enter=en)
        typo.marquee(canvas, m2, t, W / 2, H * 0.80, 7, -320 * k, int(64 * k), "anton", acc, (255, 255, 255),
                     enter=clamp01((b - 7.15) / 0.5))
        typo.letters(canvas, cfg.get("big", "UNMATCHED"), (b - 8) * P, W / 2, H * 0.36, int(170 * k), "anton",
                     (255, 255, 255), "scatter", 0.025, 0.35, glow=int(10 * k), glow_color=acc,
                     exit_u=(nb - 1 - 8) * P, exit_style="glitch", seed=33)
    # post
    img = post.bloom(canvas, 1.0)
    rgb = 4 * k + 20 * k * bar_env(b, P, 10)
    if b < 0.5:  # zoom-out entrance (answers the record's zoom-through)
        e = ease_out_expo(b / 0.5)
        L.speed_lines(img, (W / 2, H / 2), 1 - e, ctx.fi, k, 60, (220, 180, 255))
        img = zoom_canvas(img, lerp(3.2, 1.0, e))
        img = post.zoom_blur(img, 0.09 * (1 - e))
        rgb += 30 * k * (1 - e)
    if b >= nb - 1:  # stutter: zoom steps synced with the repeats
        rep = int((b - (nb - 1)) * 8)
        img = zoom_canvas(img, 1 + 0.07 * rep, rot=(-3 if rep % 2 else 3))
        img = post.glitch(img, 0.4 + 0.12 * rep, ctx.fi)
        img = L.flash(img, 0.3 * dec(((b * 8) % 1) * P / 8, 30))
    img = post.rgb_split(img, rgb)
    if b >= nb - 0.5:
        e = ease_in_expo((b - (nb - 0.5)) / 0.5)
        img = post.slices(img, 9, [W * e * (1 if i % 2 else -1) for i in range(9)])
    return L.flash(img, 0.55 * dec(b * P, 8))


def sfx_reign(seg):
    P, t0, cfg = seg.period, seg.t0, seg.cfg
    out = [(t0 + 0.17 * i * P, "swipe", 0.45) for i in range(3)]
    out.append((t0 + 0.55 * P, "scramble", 0.25))
    c0, c1 = cfg["counter"].get("beats", [1.2, 5.0])
    out += ticks(t0 + c0 * P, (c1 - c0) * P, cfg["counter"].get("from", 1), cfg["counter"]["to"])
    out += [(t0 + c1 * P, "pop", 0.8), (t0 + 4 * P, "swipe", 0.55), (t0 + 6 * P, "whoosh", 0.6),
            (t0 + 7 * P, "swipe", 0.5), (t0 + 8 * P, "whoosh", 0.4)]
    return out


# ======================================================================= TROPHIES
@lru_cache(maxsize=16)
def card_sprite(W, k, title, sub, value, badge, value_rgb):
    w, h = int(W * 0.88), int(172 * k)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = int(22 * k)
    d.rounded_rectangle((0, 0, w - 1, h - 1), r, fill=(16, 20, 30, 232), outline=(255, 205, 80, 255),
                        width=max(2, int(3 * k)))
    d.rounded_rectangle((0, 0, int(12 * k), h - 1), r // 2, fill=(255, 195, 50, 255))
    bc = (255, 195, 50) if badge != "#1" else (0, 205, 255)
    cx, cy, br = int(96 * k), h // 2, int(52 * k)
    d.ellipse((cx - br, cy - br, cx + br, cy + br), fill=bc + (255,))
    d.ellipse((cx - br + 6 * k, cy - br + 6 * k, cx + br - 6 * k, cy + br - 6 * k), outline=(255, 255, 255, 160),
              width=max(1, int(2 * k)))
    d.text((cx, cy + 2), badge, font=gfx.font("unb", int((40 if len(badge) > 2 else 50) * k)), fill=(15, 15, 20, 255),
           anchor="mm")
    d.text((int(172 * k), int(40 * k)), title, font=gfx.font("archivo", int(40 * k)), fill=(255, 255, 255, 255),
           anchor="lm")
    d.text((int(172 * k), int(106 * k)), sub, font=gfx.font("mono", int(31 * k)), fill=(255, 205, 80, 255),
           anchor="lm")
    d.text((w - int(34 * k), h // 2 + int(4 * k)), value, font=gfx.font("anton", int(96 * k)),
           fill=tuple(value_rgb) + (255,), anchor="rm")
    return gfx.pil_to_bgra(img)


def shine(spr, p):
    """Diagonal light sweep across a sprite (p 0..1)."""
    if p <= 0 or p >= 1:
        return spr
    h, w = spr.shape[:2]
    out = spr.copy()
    xs = np.arange(w, dtype=np.float32)[None, :]
    ys = np.arange(h, dtype=np.float32)[:, None]
    pos = lerp(-0.3 * w, 1.3 * w, p)
    band = np.exp(-(((xs - pos) + ys * 0.6) / (0.06 * w)) ** 2) * 0.75
    a = out[:, :, 3:4].astype(np.float32) / 255
    out[:, :, :3] = np.clip(out[:, :, :3] + band[..., None] * 255 * a, 0, 255).astype(np.uint8)
    return out


def render_trophies(ctx, seg, t):
    W, H, k = ctx.W, ctx.H, ctx.k
    P, b, cfg = seg.period, bpos(seg, t), seg.cfg
    nb = cfg["beats"]
    clip = seg.clip
    acc = ACCENT["trophies"]
    st = seg.src(t)
    frame = clip.frame(st)
    post = ctx.post
    cut_b = cfg.get("cuts_from", 6)
    canvas = np.zeros((H, W, 3), np.uint8)
    u_cut = 9.0
    if b < cut_b:
        L.put_shot(canvas, frame, clip, st, View(1.95 * (1 + 0.03 * beat_env(b, P)), 0.6), full(ctx), grade("ice"))
        canvas = L.dim(canvas, 0.5)
        lab = cfg.get("label", ["03", "THE TROPHIES", "2026 // 1V1 SEASON"])
        typo.label(canvas, lab[0], lab[1], lab[2], (b - 0.3) * P, 56 * k, H * 0.1, k, acc, exit_u=(cut_b - 0.6) * P,
                   seed=41)
        cards = cfg["cards"]
        gap = 205 * k
        y0 = H * 0.47 - gap * (len(cards) - 1) / 2
        for i, cd in enumerate(cards):
            bi = 0.5 + 0.38 * i
            if b < bi:
                continue
            spr = card_sprite(W, round(k, 3), cd["title"], cd["sub"], cd["value"], cd.get("badge", "1ST"),
                              tuple(cd.get("value_color", (255, 205, 80))))
            spr = shine(spr, (b - bi - 0.6) / 0.45)
            p = (b - bi) / 0.45
            ry = -100 * (1 - ease_out_back(p, 1.5)) + 4 * math.sin(t * 2.3 + i)
            out = clamp01((b - (cut_b - 0.8) - 0.12 * i) / 0.5)
            x = W / 2 + ease_in_expo(out) * W * 1.3
            if out > 0:
                spr = gfx.hblur(spr, 120 * k * out)
            fy = 7 * k * math.sin(t * 3.1 + i * 1.3)
            sc = 1.0 + 0.05 * dec((b - bi) * P, 10) + 0.025 * beat_env(b, P, 10)
            dst = gfx.project_rect(spr.shape[1], spr.shape[0], x, y0 + i * gap + fy, sc,
                                   3 * math.sin(t * 1.7 + i), ry, 0, 1400 * k)
            gfx.warp_sprite(canvas, spr, dst, min(1, (b - bi) / 0.15))
        if b < 0.5:  # slice-in entrance
            e = ease_out_expo(b / 0.5)
            canvas = post.slices(canvas, 9, [W * (1 - e) * (-1 if i % 2 else 1) for i in range(9)])
    else:
        ci = int((b - cut_b) * 2)
        u_cut = (b - cut_b - ci / 2) * P
        views = [View(2.3, 0.9, rot=-5), View(3.1, 0.95, ox=0.05, rot=4, flip=True), View(2.0, 0.85, rot=7),
                 View(3.4, 0.95, oy=-0.04, rot=-6)]
        v = views[ci % 4]
        v.zoom *= 1 + 0.08 * dec(u_cut, 9)
        L.put_shot(canvas, frame, clip, st, v, full(ctx), grade("ice_hot"))
        if ci % 4 == 0 and u_cut < 2.5 / ctx.fps:
            canvas = cv2.bitwise_not(canvas)
        w = cfg.get("word", "UNTOUCHABLE")
        ws = int(min(200 * k, W * 0.93 / max(1, len(w)) / 0.47))
        typo.letters(canvas, w, (b - cut_b - 0.4) * P, W / 2 + 8 * k, H * 0.47 + 8 * k, ws, "anton", acc, "flicker",
                     P / 8, 0.15, outline_only=True, stroke=max(2, int(3 * k)), seed=43)
        typo.letters(canvas, w, (b - cut_b - 0.4) * P, W / 2, H * 0.47, ws, "anton", (255, 255, 255), "flicker",
                     P / 8, 0.15, glow=int(10 * k), glow_color=acc, seed=43)
        typo.scramble(canvas, cfg.get("word_sub", "NO ONE CLOSE"), (b - cut_b - 1.6) * P, W / 2, H * 0.555,
                      int(42 * k), "mono", acc, tracking=int(8 * k), seed=44)
    # tape stop: slow down, drain colour, wobble, black
    ts = clamp01(b - (nb - 1))
    img = post.bloom(canvas, 0.8)
    img = post.rgb_split(img, 4 * k + 22 * k * dec(u_cut, 12))
    if ts > 0:
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        img = cv2.addWeighted(img, 1 - ts, cv2.merge([g, g, g]), ts, 0)
        img = post.wobble(img, 22 * k * ts, t)
        img = post.scanlines(img)
        img = L.dim(img, 0.85 * ts)
        if ts > 0.75:
            img[:] = 0
    return L.flash(img, max(0.25 * dec(u_cut, 14), 0.5 * dec(b * P, 8)))


def sfx_trophies(seg):
    P, t0, cfg = seg.period, seg.t0, seg.cfg
    out = [(t0, "glitch", 0.6), (t0 + 0.3 * P, "swipe", 0.4), (t0 + 0.3 * P, "scramble", 0.25)]
    for i in range(len(cfg["cards"])):
        bi = 0.6 + 0.5 * i
        out += [(t0 + bi * P, "whoosh", 0.45), (t0 + (bi + 0.6) * P, "ting", 0.4)]
    cut_b = cfg.get("cuts_from", 6)
    out.append((t0 + (cut_b - 0.8) * P, "whoosh", 0.55))
    for i in range(int((cfg["beats"] - 1 - cut_b) * 2)):
        out.append((t0 + (cut_b + i / 2) * P, "glitch", 0.22))
    return out


# ======================================================================= RETURN
def render_return(ctx, seg, t):
    W, H, k = ctx.W, ctx.H, ctx.k
    P, b, cfg = seg.period, bpos(seg, t), seg.cfg
    nb = cfg["beats"]
    clip = seg.clip
    acc = ACCENT["return"]
    st = seg.src(t)
    post = ctx.post
    lost_b, grid_b, mont_b = cfg.get("again_at", 4), cfg.get("grid_at", 6), cfg.get("montage_at", 8)
    gold = grade("gold")
    rgb = 4 * k
    fl = 0.0
    if b < lost_b:  # ---------------- muffled, black & white: #1 lost
        frame = clip.frame(st)
        canvas = L.bg_gradient(W, H, (24, 24, 26), (0, 0, 0))
        ww, wh = window_dims(ctx)
        dst = gfx.project_rect(ww, wh, W / 2, H * 0.44, 1 + 0.02 * b / lost_b, 3, 0, 0, 1700 * k)
        L.put_shot(canvas, frame, clip, st, View(1.0, 0.3), dst, grade("bw"))
        L.quad_outline(canvas, dst, (200, 200, 200), 2 * k)
        canvas = post.scanlines(canvas)
        lost = cfg.get("lost", ["14.06.2026", "#1", "THRONE LOST", "cryshina takes #1"])
        ex = (lost_b - 0.2) * P
        typo.scramble(canvas, lost[0], (b - 0.1) * P, W / 2, H * 0.12, int(56 * k), "mono", (255, 255, 255),
                      exit_u=ex, seed=51)
        u1 = (b - 0.4) * P
        if u1 >= 0:
            struck = b >= 1.6
            col = (255, 255, 255) if not struck else (150, 150, 150)
            spr = gfx.text_sprite(lost[1], int(400 * k), "unb", col)
            e = ease_out_cubic(u1 / 0.1)
            j = (10 * k * dec(u1, 16)) + (16 * k * dec((b - 1.6) * P, 14) if struck else 0)
            a = min(1, u1 / 0.05) * (1 - clamp01((b - (lost_b - 0.2)) / 0.2))
            gfx.blit(canvas, spr, W / 2 + j * math.sin(t * 80), H * 0.43, 1 + 1.2 * (1 - e), 0, a)
            if struck and a > 0:
                typo.strike(canvas, (W * 0.12, H * 0.47), (W * 0.88, H * 0.39), (b - 1.6) * P, 0.16,
                            (255, 30, 50), 30 * k)
        typo.letters(canvas, lost[2], (b - 2.0) * P, W / 2, H * 0.735, int(130 * k), "anton", (255, 40, 60), "drop",
                     0.035, 0.4, exit_u=(lost_b - 0.25 - 2.0) * P, exit_style="glitch", seed=52)
        typo.scramble(canvas, lost[3], (b - 2.6) * P, W / 2, H * 0.80, int(40 * k), "mono", (190, 190, 190),
                      exit_u=(lost_b - 0.25 - 2.6) * P, seed=53)
        img = post.wobble(canvas, 3 * k, t)
        rgb += 5 * k + 30 * k * dec((b - 1.6) * P, 10)
        img = post.rgb_split(img, rgb)
        if 1.6 <= b < 1.75:
            img = post.glitch(img, 0.7, ctx.fi)
        return img
    if b < grid_b:  # ---------------- gold impact: #1 again
        frame = clip.frame(st)
        u = (b - lost_b) * P
        e = ease_out_expo(u / (0.45 * P * 2))
        canvas = L.bg_blur(frame, W, H, gold, 0.5)
        ww, wh = window_dims(ctx)
        x0, y0 = lerp((W - ww) / 2, 0, e), lerp(H * 0.44 - wh / 2, 0, e)
        x1, y1 = lerp((W + ww) / 2, W, e), lerp(H * 0.44 + wh / 2, H, e)
        v = View(lerp(1.0, 2.05, e) * (1 + 0.05 * beat_env(b, P)), lerp(0.3, 0.85, e), rot=roll_env(b, P, 3) * e)
        M = L.put_shot(canvas, frame, clip, st, v, L.rect_quad(x0, y0, x1, y1), gold)
        act = L.map_point(M, clip.centre(st))
        L.shockwave(canvas, (W / 2, H * 0.44), u, k, (255, 220, 120), 1.6, 0.6)
        L.speed_lines(canvas, (W / 2, H * 0.44), 1.1 * dec(u, 5), ctx.fi, k, 64, (255, 215, 140))
        for bb in range(int(lost_b), int(grid_b)):
            L.sparks(canvas, act, (b - bb) * P, 500 + bb, k, 30, (255, 210, 120), 1700, 0.5)
        again = cfg.get("again", ["11.07.2026", "#1", "AGAIN"])
        ex = (grid_b - 0.25 - lost_b) * P
        typo.scramble(canvas, again[0], u - 0.02, W / 2, H * 0.12, int(56 * k), "mono", acc, exit_u=ex, seed=54)
        spr = gfx.text_sprite(again[1], int(400 * k), "unb", acc, glow=int(18 * k), glow_color=(255, 140, 0))
        typo.outline_stack(canvas, again[1], u, W / 2, H * 0.43, int(400 * k), "unb", acc, 5, 0.12, max(2, int(4 * k)),
                           0.6, 1 - clamp01((u - ex) / 0.15))
        e2 = ease_out_cubic(u / 0.1)
        gfx.blit(canvas, spr, W / 2, H * 0.43, 1 + 1.3 * (1 - e2), 0, min(1, u / 0.04) * (1 - clamp01((u - ex) / 0.15)))
        typo.letters(canvas, again[2], u - 0.4 * P, W / 2, H * 0.70, int(160 * k), "anton", (255, 255, 255), "spin",
                     0.04, 0.4, exit_u=ex - 0.4 * P, exit_style="scatter", seed=55)
        img = post.bloom(canvas, 1.1)
        img = post.rgb_split(img, rgb + 40 * k * dec(u, 7))
        img = post.zoom_blur(img, 0.08 * dec(u, 6))
        return L.flash(img, 0.95 * dec(u, 5), (255, 225, 150))
    if b < mont_b:  # ---------------- 3x3 grid
        frame = clip.frame(st)
        canvas = np.zeros((H, W, 3), np.uint8)
        g8 = 8 * k
        tw, th = (W - 4 * g8) / 3, (H - 4 * g8) / 3
        zooms = [2.4, 2.0, 2.8, 2.2, 2.05, 2.1, 2.9, 2.3, 2.5]
        gnames = ["gold", "gold_duo", "bw"]
        coll = clamp01((b - (mont_b - 0.5)) / 0.5)
        ec = ease_in_expo(coll)
        order = [4, 1, 3, 5, 7, 0, 2, 6, 8]
        for idx in order[::-1]:
            r_, c_ = divmod(idx, 3)
            rank = order.index(idx)
            pin = (b - grid_b - rank * 0.125) / 0.3
            if pin <= 0:
                continue
            s = ease_out_back(pin, 2.2)
            cx = g8 + c_ * (tw + g8) + tw / 2
            cy = g8 + r_ * (th + g8) + th / 2
            w_, h_ = tw * s, th * s
            if idx == 4:
                cx, cy = lerp(cx, W / 2, ec), lerp(cy, H / 2, ec)
                w_, h_ = lerp(w_, W, ec), lerp(h_, H, ec)
            else:
                dx, dy = cx - W / 2, cy - H / 2
                cx, cy = cx + dx * 2.5 * ec, cy + dy * 2.5 * ec
            q = L.rect_quad(cx - w_ / 2, cy - h_ / 2, cx + w_ / 2, cy + h_ / 2)
            gn = "gold" if idx == 4 else gnames[idx % 3]
            L.put_shot(canvas, frame, clip, st, View(zooms[idx] * (1 + 0.05 * beat_env(b, P)), 0.5,
                                                    flip=idx % 2 == 1), q, grade(gn))
        img = post.bloom(canvas, 0.9)
        img = post.rgb_split(img, rgb + 20 * k * beat_env(b, P, 10))
        if coll > 0:
            img = post.zoom_blur(img, 0.08 * ec)
        return L.flash(img, 0.25 * beat_env(b, P, 16))
    # ---------------- accelerating montage across every clip
    cuts = cfg.get("cuts", [8, 9, 10, 11, 12, 12.5, 13, 13.5, 14, 14.25, 14.5, 14.75, 15, 15.25, 15.5, 15.75])
    ci = max(i for i, c in enumerate(cuts) if b >= c)
    u_cut = (b - cuts[ci]) * P
    mont = cfg.get("montage", [])
    n = len(cuts)
    name = mont[(ci - n + 1) % len(mont)] if mont else None
    mclip = ctx.clips[name] if name else clip
    mst = st if mclip is clip else ctx.src_start[name] + (b - mont_b) * P + ci * 0.21
    frame = mclip.frame(mst)
    g = grade(ctx.grade_name.get(name, "gold")) if name else gold
    canvas = np.zeros((H, W, 3), np.uint8)
    typ = ci % 4
    build = clamp01((b - 12) / 4)
    if typ == 0:
        L.put_shot(canvas, frame, mclip, mst, View(2.3 * (1 + 0.06 * dec(u_cut, 9)), 0.9, rot=-4), full(ctx), g)
    elif typ == 1:
        canvas[:] = L.bg_blur(frame, W, H, g, 0.45)
        ww, wh = window_dims(ctx)
        dst = gfx.project_rect(ww, wh, W / 2, H * 0.45, 1 + 0.08 * dec(u_cut, 9), 6, 16 if ci % 8 == 1 else -16, 0,
                               1600 * k)
        L.put_shot(canvas, frame, mclip, mst, View(1.0, 0.35), dst, g)
        L.quad_outline(canvas, dst, (255, 255, 255), 3 * k)
        L.brackets(canvas, dst, 50 * k, 18 * k, acc, 5 * k)
    elif typ == 2:
        L.put_shot(canvas, frame, mclip, mst, View(1.95 * (1 + 0.05 * dec(u_cut, 9)), 0.75, rot=5, flip=ci % 3 == 0),
                   full(ctx), g)
    else:
        L.put_shot(canvas, frame, mclip, mst, View(2.7, 0.95), L.rect_quad(0, 0, W, H / 2 - 5 * k), g)
        L.put_shot(canvas, frame, mclip, mst, View(2.7, 0.95, flip=True), L.rect_quad(0, H / 2 + 5 * k, W, H),
                   grade("bw"))
    words = cfg.get("words", [[8, "THE", "slam"], [9, "GREATEST", "drop"], [10.5, "OF ALL", "scatter"],
                              [12, "TIME.", "scale"]])
    for wi, (wb, wtxt, wst) in enumerate(words):
        nxt = words[wi + 1][0] if wi + 1 < len(words) else nb
        if not (wb <= b < nxt + 0.3):
            continue
        u = (b - wb) * P
        size = int(min(330 * k, W * 0.92 / max(1, len(wtxt)) / 0.45))
        sh = 18 * k * build
        cx = W / 2 + sh * math.sin(t * 73)
        cy = H * 0.44 + sh * math.cos(t * 61)
        if wi == len(words) - 1:
            typo.outline_stack(canvas, wtxt, u, cx, cy, size, "anton", acc, 5, 0.1, max(2, int(4 * k)), 0.5)
        typo.letters(canvas, wtxt, u, cx, cy, size, "anton", (255, 255, 255), wst, 0.03, 0.28, glow=int(12 * k),
                     glow_color=acc, exit_u=(nxt - wb) * P if wi < len(words) - 1 else None, exit_style="scatter",
                     exit_dur=0.12, seed=60 + wi)
    img = post.bloom(canvas, 0.9 + 0.5 * build)
    img = zoom_canvas(img, 1 + 0.25 * build ** 2, rot=6 * build * math.sin(t * 9))
    img = post.rgb_split(img, rgb + 26 * k * dec(u_cut, 12) + 30 * k * build)
    if u_cut < 0.04 and ci >= 8:
        img = post.glitch(img, 0.6, ctx.fi)
    fl = max(0.3 * dec(u_cut, 14) * (0.6 + build), ease_in_expo((b - (nb - 0.4)) / 0.4))
    return L.flash(img, fl)


def sfx_return(seg):
    P, t0, cfg = seg.period, seg.t0, seg.cfg
    lost_b, grid_b, mont_b = cfg.get("again_at", 4), cfg.get("grid_at", 6), cfg.get("montage_at", 8)
    out = [(t0 + 0.1 * P, "scramble", 0.3), (t0 + 0.4 * P, "stamp", 0.8), (t0 + 1.6 * P, "swipe", 0.7),
           (t0 + 1.6 * P, "glitch", 0.5), (t0 + 2.0 * P, "stamp", 0.5), (t0 + lost_b * P, "impact", 1.0),
           (t0 + lost_b * P, "ting", 0.6), (t0 + (lost_b + 0.4) * P, "whoosh", 0.5), (t0 + lost_b * P, "scramble", 0.3)]
    out += [(t0 + (grid_b + 0.125 * i) * P, "tick", 0.45) for i in range(9)]
    out.append((t0 + (mont_b - 0.5) * P, "whoosh", 0.6))
    cuts = cfg.get("cuts", [8, 9, 10, 11, 12, 12.5, 13, 13.5, 14, 14.25, 14.5, 14.75, 15, 15.25, 15.5, 15.75])
    for c in cuts:
        out.append((t0 + c * P, "swipe" if c < 14 else "glitch", 0.35 if c < 14 else 0.3))
    out.append((t0 + 12 * P, "riser", 0.6))
    return out


def audio_return(a, seg):
    """First part muffled (lowpass + vinyl crackle), then the filter slams open."""
    import synth as S
    n = S.n_samples(seg.cfg.get("again_at", 4) * seg.period)
    n = min(n, len(a))
    muff = S.lowpass(a[:n], 420, 4) * 1.6
    crackle = S.vinyl(n / S.SR) * 0.08
    xf = S.n_samples(0.01)
    a = a.copy()
    a[:n - xf] = muff[:n - xf] + crackle[:n - xf]
    ramp = np.linspace(0, 1, xf)[:, None]
    a[n - xf:n] = (muff[n - xf:n] + crackle[n - xf:n]) * (1 - ramp) + a[n - xf:n] * ramp
    return a


# ======================================================================= OUTRO
def render_outro(ctx, seg, t):
    W, H, k = ctx.W, ctx.H, ctx.k
    u = t - seg.t0
    cfg = seg.cfg
    clip, st = seg.clip, seg.smap[0]
    frame = clip.frame(st)
    post = ctx.post
    gold = grade("gold")
    canvas = L.dim(L.bg_blur(frame, W, H, gold, 0.5), 0.6)
    title = cfg.get("title", "MREKK")
    size = int(min(400 * k, W * 0.86 / max(1, len(title)) / 0.5))
    cy = H * 0.45
    # letters: gold gradient screen-blended with the bright frozen gameplay
    shot = np.zeros_like(canvas)
    L.put_shot(shot, frame, clip, st, View(2.0 + 0.15 * u, 0.85), full(ctx), gold)
    fill = L.screen(cv2.convertScaleAbs(L.bg_gradient(W, H, (255, 236, 170), (255, 140, 20)), alpha=0.8), shot)
    typo.outline_stack(canvas, title, u, W / 2, cy, size, "anton", (255, 200, 80), 6, 0.08, max(2, int(4 * k)), 0.8)
    a_in = min(1, u / 0.06)
    typo.mask_fill(canvas, title, size, "anton", W / 2, cy, fill, a_in)
    edge = gfx.text_sprite(title, size, "anton", (255, 255, 255), stroke=max(2, int(4 * k)), outline_only=True)
    gfx.blit(canvas, edge, W / 2, cy, 1.0, 0, a_in)
    typo.scramble(canvas, cfg.get("sub", "1 OF 1"), u - 0.3, W / 2, H * 0.58, int(68 * k), "mono", (255, 255, 255),
                  dur=0.5, tracking=int(30 * k), seed=71)
    typo.scramble(canvas, cfg.get("small", "#1 GLOBAL  //  2026"), u - 0.6, W / 2, H * 0.625, int(34 * k), "mono",
                  (255, 200, 80), dur=0.4, seed=72)
    end = seg.dur
    L.shockwave(canvas, (W / 2, cy), u - (end - 0.45), k, (255, 230, 160), 1.4, 0.45)
    L.speed_lines(canvas, (W / 2, cy), 0.8 * dec(u, 6), ctx.fi, k, 60, (255, 220, 150))
    img = post.bloom(canvas, 0.9)
    img = post.rgb_split(img, 3 * k + 40 * k * dec(u, 6))
    img = post.zoom_blur(img, 0.07 * dec(u, 6))
    tail = clamp01((u - (end - 0.35)) / 0.35)
    if tail > 0:
        img = post.glitch(img, 0.5 + tail * 1.5, ctx.fi)
        img = L.dim(img, tail)
    return L.flash(img, 0.9 * dec(u, 5))


def sfx_outro(seg):
    t0 = seg.t0
    return [(t0, "stamp", 0.6), (t0 + 0.3, "scramble", 0.35), (t0 + seg.dur - 0.45, "glitch", 0.6)]


RENDER = {"hook": render_hook, "record": render_record, "reign": render_reign, "trophies": render_trophies,
          "return": render_return, "outro": render_outro}
SFX = {"hook": sfx_hook, "record": sfx_record, "reign": sfx_reign, "trophies": sfx_trophies, "return": sfx_return,
       "outro": sfx_outro}
AUDIO_FX = {"return": audio_return}
