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
from gfx import (clamp01, ease_in_cubic, ease_in_expo, ease_in_out_cubic, ease_in_out_expo, ease_out_back, ease_out_cubic,
                 ease_out_expo, lerp)
from layers import View

# ======================================================================= palettes
GRADE_SPECS = {
    "red": {"type": "duo", "dark": (16, 0, 6), "mid": (225, 22, 50), "light": (255, 238, 238), "contrast": 1.35, "mix": 0.72},
    "red_hard": {"type": "duo", "dark": (0, 0, 0), "mid": (150, 0, 25), "light": (255, 255, 255), "contrast": 1.9},
    "violet": {"type": "tint", "tint": (1.06, 0.78, 1.28), "sat": 1.35, "contrast": 1.3, "lift": -0.03},
    "cyan": {"type": "duo", "dark": (0, 8, 22), "mid": (0, 150, 235), "light": (225, 252, 255), "contrast": 1.35, "mix": 0.75},
    "magenta": {"type": "duo", "dark": (18, 0, 20), "mid": (250, 0, 160), "light": (255, 228, 250), "contrast": 1.35, "mix": 0.75},
    "ice": {"type": "duo", "dark": (2, 10, 22), "mid": (50, 140, 195), "light": (218, 246, 255), "contrast": 1.3, "mix": 0.7},
    "ice_hot": {"type": "duo", "dark": (0, 6, 18), "mid": (0, 185, 255), "light": (240, 255, 255), "contrast": 1.45, "mix": 0.72},
    "gold": {"type": "tint", "tint": (1.28, 1.0, 0.66), "sat": 1.35, "contrast": 1.3, "lift": -0.02},
    "gold_duo": {"type": "duo", "dark": (16, 8, 0), "mid": (230, 150, 22), "light": (255, 246, 215), "contrast": 1.35, "mix": 0.75},
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


def play_tag(ctx, canvas, seg, b):
    """Small tag with the play's real stats: accent bar, title rising, stats decoding."""
    tg = seg.cfg.get("tag")
    if not tg:
        return
    P, k = seg.period, ctx.k
    b0, b1 = tg.get("beats", [1, seg.cfg["beats"] - 1])
    if b < b0 or b > b1 + 2:
        return
    u, ex = (b - b0) * P, (b1 - b0) * P
    x, y = ctx.W * tg.get("x", 0.06), ctx.H * tg.get("y", 0.12)
    acc = ACCENT.get(seg.style, (255, 255, 255))
    g = ease_out_expo(u / 0.25) * (1 - clamp01((u - ex) / 0.25))
    if g > 0.01:
        cv2.rectangle(canvas, (int(x), int(y - 48 * k)), (int(x + 7 * k), int(y - 48 * k + 100 * k * g)), acc[::-1], -1)
    title = tg.get("title", "")
    tsz = int(60 * k)
    if title:
        typo.letters(canvas, title, u - 0.05, x + 24 * k + gfx.text_layout(title, tsz, "anton")[1] / 2, y - 14 * k, tsz,
                     "anton", (255, 255, 255), "rise", 0.02, 0.3, exit_u=ex, exit_style="up", seed=81)
    typo.scramble(canvas, tg.get("stats", ""), u - 0.15, x + 24 * k, y + 38 * k, int(30 * k), "mono", acc, dur=0.4,
                  exit_u=ex, seed=82, align="left")


def fit_size(text, fname, max_w, max_size, tracking=0):
    """Largest font size (<= max_size) at which `text` is at most max_w wide."""
    w = gfx.text_layout(text, int(max_size), fname, tracking)[1]
    return int(max_size if w <= max_w else max_size * max_w / max(w, 1))


CLIP_TINT = {"saveme": (255, 60, 80), "crystalia": (185, 95, 255), "eye": (0, 205, 255), "map172": (255, 190, 40)}


def tinted_fill(img, color):
    """Brighten a gameplay picture for use inside letters: colour gradient screen-blended with it."""
    h, w = img.shape[:2]
    top = tuple(min(255, int(c * 0.55 + 115)) for c in color)
    grad = L.bg_gradient(w, h, top, color)
    return L.screen(cv2.convertScaleAbs(grad, alpha=0.75), img)


@lru_cache(maxsize=32)
def pill_sprite(text, size, fill, fg, k, outline=False):
    """Rounded badge with text (BGRA)."""
    f = gfx.font("unb", size)
    tw = int(f.getlength(text))
    asc, desc = f.getmetrics()
    padx, pady = int(size * 0.62), int(size * 0.32)
    w, h = tw + 2 * padx, asc + desc + 2 * pady - int(desc * 0.6)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if outline:
        d.rounded_rectangle((1, 1, w - 2, h - 2), h // 2, outline=tuple(fill) + (255,), width=max(2, int(3 * k)))
    else:
        d.rounded_rectangle((0, 0, w - 1, h - 1), h // 2, fill=tuple(fill) + (255,))
    d.text((w // 2, h // 2 + int(size * 0.04)), text, font=f, fill=tuple(fg) + (255,), anchor="mm")
    return gfx.pil_to_bgra(img)


@lru_cache(maxsize=32)
def halo_sprite(text, size, fill, k):
    """Soft coloured glow matching a pill badge."""
    spr = pill_sprite(text, size, fill, (0, 0, 0), k)
    pad = int(size * 0.9)
    a = np.pad(spr[:, :, 3], pad).astype(np.float32)
    a = cv2.GaussianBlur(a, (0, 0), size * 0.45)
    out = np.zeros(a.shape + (4,), np.uint8)
    out[:, :, :3] = fill[::-1]
    out[:, :, 3] = np.clip(a * 1.2, 0, 255).astype(np.uint8)
    return out


def play_card(ctx, canvas, seg, b):
    """The same stat block for every play: TITLE [MODS] / big pp for the play / record badges.
    Shown at the top of the frame with one shared animation language (colour per part)."""
    card = seg.cfg.get("card")
    if not card:
        return
    W, H, k, P = ctx.W, ctx.H, ctx.k, seg.period
    acc = tuple(card.get("color", ACCENT.get(seg.style, (255, 255, 255))))
    b0, b1 = card.get("beats", [0.4, seg.cfg["beats"] - 0.7])
    if b < b0 or b > b1 + 3:
        return
    u, ex = (b - b0) * P, (b1 - b0) * P
    out = clamp01((u - ex) / 0.25)
    alpha = 1 - out
    lift = -60 * k * ease_in_cubic(out)
    y = H * card.get("y", 0.075) + lift
    # soft scrim at the top so the block reads on any footage
    scrim = 0.6 * clamp01(u / 0.3) * alpha
    if scrim > 0.01:
        hh = int(H * 0.34)
        ramp = (1 - scrim * np.clip(1 - np.arange(hh, dtype=np.float32) / hh, 0, 1) ** 1.3)[:, None, None]
        canvas[:hh] = (canvas[:hh].astype(np.float32) * ramp).astype(np.uint8)
    # title + mods pill
    title = card["title"]
    tsz = fit_size(title, "anton", W * 0.62, card.get("title_size", 78) * k)
    tw = gfx.text_layout(title, tsz, "anton")[1]
    mods = card.get("mods", "")
    msz = int(34 * k)
    pill = pill_sprite(mods, msz, acc, (12, 12, 16), round(k, 3)) if mods else None
    pw = pill.shape[1] if pill is not None else 0
    gap = 20 * k if pill is not None else 0
    x0 = W / 2 - (tw + gap + pw) / 2
    typo.letters(canvas, title, u, x0 + tw / 2, y, tsz, "anton", (255, 255, 255), "rise", 0.025, 0.3,
                 glow=int(8 * k), glow_color=acc, exit_u=ex, exit_style="up", seed=101)
    if pill is not None:
        pu = u - 0.18
        if pu > 0:
            s = max(0.01, ease_out_back(pu / 0.25, 2.4))
            gfx.blit(canvas, halo_sprite(mods, msz, acc, round(k, 3)), x0 + tw + gap + pw / 2, y + 6 * k, s, 0,
                     alpha * (0.55 + 0.35 * beat_env(b, P, 8)))
            gfx.blit(canvas, pill, x0 + tw + gap + pw / 2, y + 6 * k, s, 0, alpha)
    # big pp for the play
    pp = card.get("pp")
    py = y + 120 * k
    if pp:
        cu = u - 0.25
        val, vel = typo.count_value(cu, 0, 0.9, 0, pp)
        land = cu - 0.9
        pop = 1 + 0.16 * dec(land, 10) if land >= 0 else 1.0
        psz = int(card.get("pp_size", 150) * k)
        if land >= 0:
            typo.outline_stack(canvas, f"{pp}PP", land, W / 2, py, psz, "unb", acc, 4, 0.08, max(2, int(3 * k)), 0.6,
                               alpha * 0.9)
        typo.counter(canvas, val, W / 2, py, psz, "unb", (255, 255, 255), len(str(pp)), "", "PP", vel, int(16 * k), acc,
                     lead_zeros=False, alpha=alpha * clamp01(cu / 0.08), scale=pop * (1 + 0.03 * beat_env(b, P, 12)),
                     affix_color=acc, fps=ctx.fps)
        if land >= 0:
            L.flare(canvas, (W / 2, py), 1.0 * dec(land, 6) * alpha, acc, k)
    # record badges: pop in, pulse with the beat, a light sweep every two beats
    by = py + (105 if pp else 20) * k
    for i, text in enumerate(card.get("badges", [])):
        bu = u - 1.15 - 0.18 * i
        if bu < 0:
            continue
        bsz = int((40 if i == 0 else 30) * k)
        filled = i == 0
        spr = pill_sprite(text, bsz, acc if filled else acc, (12, 12, 16) if filled else acc, round(k, 3),
                          outline=not filled)
        sweep = ((b - b0 - 1.15) % 2) / 1.2
        spr = shine(spr, sweep)
        s = max(0.01, ease_out_back(bu / 0.25, 2.2)) * (1 + 0.04 * bar_env(b, P, 9))
        yy = by + i * (bsz * 1.9)
        if filled:
            gfx.blit(canvas, halo_sprite(text, bsz, acc, round(k, 3)), W / 2, yy, s, 0,
                     alpha * (0.6 + 0.4 * beat_env(b, P, 7)))
        gfx.blit(canvas, spr, W / 2 + 10 * k * dec(bu, 18) * math.sin(bu * 80), yy, s, 0, alpha * min(1, bu / 0.05))
        if bu < 0.2:
            L.flare(canvas, (W / 2, yy), 0.8 * (1 - bu / 0.2) * alpha, acc, k, 0.35)
    if card.get("stats"):
        n = len(card.get("badges", []))
        sy = by + (n * 1.9 * 36 * k if n else 0) + 10 * k
        typo.scramble(canvas, card["stats"], u - 1.0, W / 2, sy, int(28 * k), "mono", (225, 225, 235), dur=0.4,
                      exit_u=ex - 1.0 + 0.2, seed=104)


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


def shot_image(ctx, name, st, w, h, view, grade_fn=None):
    """A w x h picture of clip `name` at time st (for filling letters etc.)."""
    clip = ctx.clips[name]
    img = np.zeros((int(h), int(w), 3), np.uint8)
    L.put_shot(img, clip.frame(st), clip, st, view, L.rect_quad(0, 0, int(w), int(h)), grade_fn)
    return img


HUD_LABELS = [("REPLAY // MREKK.OSR", 0.06, 0.055, "l"), ("HD  DT  NM", 0.94, 0.055, "r"),
              ("60 FPS  //  1080 X 1920", 0.06, 0.945, "l"), ("OSU!STANDARD", 0.94, 0.945, "r")]


def render_hook(ctx, seg, t):
    W, H, k = ctx.W, ctx.H, ctx.k
    P, b = seg.period, bpos(seg, t)
    cfg = seg.cfg
    word = cfg.get("word", "MREKK")
    post = ctx.post
    canvas = L.bg_gradient(W, H, (14, 10, 18), (0, 0, 0))
    cuts = [1, 1.5, 2, 2.5, 3, 3.25, 3.5, 3.75]
    shots = cfg.get("flash", [])
    c = (W / 2, H * 0.46)
    u_cut = 9.0
    # ---- gameplay flash cuts behind the letters (pushed back: dim + soft)
    if b >= 1 and shots:
        ci = max(i for i, cc in enumerate(cuts) if b >= cc)
        name = shots[ci % len(shots)]
        clip = ctx.clips[name]
        st = ctx.src_start[name] + (b - 1) * P + ci * 0.37
        frame = clip.frame(st)
        g = grade(ctx.grade_name[name])
        u_cut = (b - cuts[ci]) * P
        if ci % 2 == 0:
            L.put_shot(canvas, frame, clip, st, View(1.9 + 0.2 * (ci % 3), 0.85, rot=-5 if ci % 4 == 0 else 4),
                       full(ctx), g)
        else:
            canvas[:] = L.bg_blur(frame, W, H, g, 0.4)
            ww, wh = window_dims(ctx, 0.9)
            dst = gfx.project_rect(ww, wh, W / 2, H * 0.46, 1.0 + 0.07 * dec(u_cut, 9), 7,
                                   -15 if ci % 4 == 1 else 15, 0, 1700 * k)
            L.put_shot(canvas, frame, clip, st, View(1.0, 0.3), dst, g)
            L.quad_outline(canvas, dst, (255, 255, 255), 3 * k)
        canvas = cv2.GaussianBlur(canvas, (0, 0), 1.6 * k + 5 * k * clamp01((b - 3) / 0.6))
        canvas = L.dim(canvas, 0.38 + 0.4 * clamp01((b - 3) / 0.5))
    # ---- the hit circle: particles stream in, it hits on beat 1
    r = 175 * k
    if b < 1:
        for i in range(40):
            ang = 2 * math.pi * i / 40 + 0.6 * math.sin(i * 7.3)
            dist = (r * 1.05 + 950 * k * (1 - b) ** 1.4 * (0.55 + 0.45 * ((i * 37) % 11) / 10))
            pos = (c[0] + math.cos(ang) * dist, c[1] + math.sin(ang) * dist)
            L.glow_dot(canvas, pos, 4.5 * k, (255, 110, 150), 0.75 * b)
        L.hit_circle(canvas, c, r * (1 - 0.05 * ease_in_cubic(b)), 1 - b, (230, 30, 60), min(1, 0.25 + b / 0.3), "1", k)
    else:
        u = (b - 1) * P
        if u < 0.22:
            e = u / 0.22
            L.hit_circle(canvas, c, r * (1 + 0.6 * ease_out_expo(e)), 0, (230, 30, 60), 1 - e, "1", k)
        for dly, sz in ((0.0, 1.5), (0.05, 1.0), (0.11, 0.7)):
            L.shockwave(canvas, c, u - dly, k, (255, 255, 255), sz, 0.5)
        L.sparks(canvas, c, u, 11, k, 60, (255, 225, 205), 2000, 0.6)
        L.speed_lines(canvas, c, 0.9 * dec(u, 6), ctx.fi, k)
    # ---- letters: five different entrances, one per half beat, then they fly together
    fsz = int(330 * k)
    targets = word_glyph_centres(word, fsz, "anton", W / 2, H * 0.46)
    fly = clamp01((b - 3.0) / 0.75)
    e = ease_in_out_expo(fly)
    fill_img = None
    for i, ch in enumerate(word):
        bi = 1 + 0.5 * i
        if b < bi:
            continue
        u = (b - bi) * P
        px, py, sz, rot = COLLAGE[i % len(COLLAGE)]
        fg, box, hollow = HOOK_LOOKS[i % len(HOOK_LOOKS)]
        style = ("slam", "flip", "slice", "fill", "pop")[i % 5]
        size_i = int(420 * k * sz)
        if style == "fill" and shots:
            if fill_img is None:
                nm = shots[i % len(shots)]
                gw, gh = int(size_i * 0.7), int(size_i * 1.1)
                fill_img = tinted_fill(shot_image(ctx, nm, ctx.src_start[nm] + 0.6 + b * P, gw, gh, View(1.4, 0.85),
                                                  grade(ctx.grade_name[nm])), CLIP_TINT.get(nm, (255, 60, 80)))
            spr = typo.glyph_fill_sprite(ch, size_i, "anton", fill_img)
            edge = gfx.text_sprite(ch, size_i, "anton", (255, 255, 255), stroke=max(2, int(4 * k)), outline_only=True)
        else:
            spr = boxed_letter(ch, size_i, fg, box, hollow)
            edge = None
        sc, ry = 1.0, 0.0
        if style == "slam":
            sc = 1 + 1.5 * (1 - ease_out_cubic(u / 0.09))
            spr = gfx.vblur(spr, 40 * k * (1 - clamp01(u / 0.1)))
        elif style == "flip":
            ry = 90 * (1 - ease_out_back(u / 0.18, 1.6))
        elif style == "slice":
            spr = typo.slice_sprite(spr, 7, 170 * k * (1 - ease_out_expo(u / 0.16)), seed=i)
        elif style == "fill":
            wf = ease_out_expo(u / 0.16)
            cut = max(1, int(spr.shape[1] * wf))
            spr = np.ascontiguousarray(np.pad(spr[:, :cut], ((0, 0), (0, spr.shape[1] - cut), (0, 0))))
            if edge is not None:
                ce = max(1, int(edge.shape[1] * wf))
                edge = np.ascontiguousarray(np.pad(edge[:, :ce], ((0, 0), (0, edge.shape[1] - ce), (0, 0))))
        elif style == "pop":
            sc = max(0.01, ease_out_back(u / 0.16, 2.6))
        j = 16 * k * dec(u, 18)
        p0 = np.array([px * W, py * H])
        p1 = np.array(targets[i])
        mid = (p0 + p1) / 2 + np.array([-(p1 - p0)[1], (p1 - p0)[0]]) * (0.35 if i % 2 else -0.35)

        def path(ev):
            return (1 - ev) ** 2 * p0 + 2 * (1 - ev) * ev * mid + ev ** 2 * p1
        rr = lerp(rot, 0, e)
        if 0 < fly < 1:  # motion trails along the curved flight
            for tr in (3, 2, 1):
                et = ease_in_out_expo(fly - tr * 0.06)
                q = path(et)
                gfx.blit(canvas, spr, q[0], q[1], sc * lerp(1, 0.75, et), lerp(rot, 0, et), 0.16 * (4 - tr) * (1 - e))
        pos = path(e) + np.array([j * math.sin(u * 90), j * math.cos(u * 71)])
        a_box = (1 - e) * min(1, u / 0.04)
        if a_box > 0.01:
            s_ = sc * lerp(1, 0.75, e)
            if abs(ry) > 0.5:
                dst = gfx.project_rect(spr.shape[1], spr.shape[0], pos[0], pos[1], s_, 0, ry, -rr, 900 * k)
                gfx.warp_sprite(canvas, spr, dst, a_box)
            else:
                gfx.blit(canvas, spr, pos[0], pos[1], s_, rr, a_box)
                if edge is not None:
                    gfx.blit(canvas, edge, pos[0], pos[1], s_, rr, a_box)
            idx = gfx.text_sprite(f"0{i + 1}", int(22 * k), "mono", (255, 255, 255))
            gfx.blit(canvas, idx, pos[0] - spr.shape[1] * 0.5 * s_ - 18 * k, pos[1] - spr.shape[0] * 0.5 * s_,
                     1, 0, a_box * 0.8)
        if e > 0:
            plain = gfx.text_sprite(ch, fsz, "anton", (255, 255, 255), glow=int(12 * k), glow_color=(230, 30, 60))
            ox, oy = glyph_offset(ch, fsz, "anton")
            gfx.blit(canvas, plain, pos[0] + ox, pos[1] + oy, lerp(1.35, 1.0, e), rr, e)
    # ---- lock-in: outline echoes, light sweep, anamorphic flare
    oy_w = glyph_offset("M", fsz, "anton")[1]
    if b >= 3.7:
        lu = (b - 3.7) * P
        typo.outline_stack(canvas, word, lu, W / 2, H * 0.46 + oy_w, fsz, "anton", (255, 60, 90), 5, 0.1,
                           max(2, int(3 * k)))
        typo.shine_text(canvas, word, fsz, "anton", W / 2, H * 0.46 + oy_w, lu / 0.22)
        L.flare(canvas, (W / 2, H * 0.46), 1.2 * dec(lu, 5), (255, 200, 210), k)
    if b >= 3.15 and cfg.get("sub"):
        typo.scramble(canvas, cfg["sub"], (b - 3.15) * P, W / 2, H * 0.57, int(40 * k), "mono", (255, 255, 255),
                      dur=0.35, tracking=int(5 * k), seed=5)
    # ---- camera: push in while the circle approaches, kick on every stamp
    z = 1 + 0.07 * gfx.ease_in_out(b) if b < 1 else 1.07 - 0.07 * ease_out_expo((b - 1) / 0.5)
    for i in range(len(word)):
        z += 0.025 * dec((b - 1 - 0.5 * i) * P, 14)
    shake = 9 * k * dec((b - 1) * P, 7) if b >= 1 else 0
    img = zoom_canvas(canvas, z, (W / 2 + shake * math.sin(t * 97), H * 0.46 + shake * math.cos(t * 83)))
    img = post.bloom(img, 0.6)
    img = post.rgb_split(img, 2 * k + 22 * k * dec(u_cut, 12) + (34 * k * dec((b - 1) * P, 8) if b >= 1 else 0))
    if u_cut < 0.05 and b < 3.2:  # keep the assembled word clean
        img = post.glitch(img, 0.7, ctx.fi)
    burst = 1.0 if 0 <= (b - 1) * P < 2.0 / ctx.fps else 0.85 * dec((b - 1) * P, 7) if b >= 1 else 0.0
    return L.flash(img, max(burst, 0.25 * dec(u_cut, 18) if b >= 1 else 0, ease_in_expo((b - 3.65) / 0.35)))


def sfx_hook(seg):
    P, t0 = seg.period, seg.t0
    out = [(t0, "scramble", 0.25), (t0 + 1 * P, "hit", 1.0), (t0 + 1 * P, "impact", 0.55)]
    word = seg.cfg.get("word", "MREKK")
    for i in range(len(word)):
        out.append((t0 + (1 + 0.5 * i) * P, "stamp", 0.7))
        out.append((t0 + (1 + 0.5 * i) * P, "glitch" if i == 2 else "swipe", 0.25))
    out += [(t0 + 3.0 * P, "whoosh", 0.7), (t0 + 3.7 * P, "ting", 0.5)]
    if seg.cfg.get("sub"):
        out.append((t0 + 3.15 * P, "scramble", 0.35))
    return out


# ======================================================================= RECORD
def render_record(ctx, seg, t):
    W, H, k = ctx.W, ctx.H, ctx.k
    P, b, cfg = seg.period, bpos(seg, t), seg.cfg
    nb = cfg["beats"]
    clip = seg.clip
    acc = ACCENT["record"]
    fz0 = cfg.get("freeze")
    zt0 = nb - cfg.get("zoom_beats", 2)
    frozen = fz0 is not None and b >= fz0
    st = seg.src(seg.t0 + fz0 * P) if frozen else seg.src(t)
    frame = clip.frame(st)
    g = grade("red_hard" if frozen else "red")
    canvas = L.bg_gradient(W, H, (52, 0, 12), (4, 0, 2))
    for yy, spd in ((0.18, -110), (0.5, 150), (0.82, -130)):
        if cfg.get("bg_word"):
            bg_type(canvas, cfg["bg_word"] + "  ", t, H * yy, spd * k, int(300 * k), (255, 50, 80), 0.12,
                    max(2, int(3 * k)))
    # swinging 3D card
    ww, wh = window_dims(ctx)
    cy = H * cfg.get("window_y", 0.425)
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
    ez = ease_in_expo((b - zt0) / max(0.5, nb - zt0)) if b >= zt0 else 0.0
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
    if frozen and cfg.get("stamp"):
        typo.stamp(canvas, cfg["stamp"], (b - fz0) * P, W / 2, cy, int(cfg.get("stamp_size", 165) * k), acc, -9, k,
                   exit_u=(zt0 - fz0) * P)
    # typography
    lab = cfg.get("label")
    if lab:
        typo.label(canvas, lab[0], lab[1], lab[2], (b - 0.35) * P, 56 * k, H * 0.1, k, acc, exit_u=(zt0 - 0.3) * P,
                   seed=11)
    cc = cfg.get("counter") or {"to": 0, "hidden": True}
    c0, c1 = cc.get("beats", [1.0, 6.5])
    live = clip.pp_at(seg.src(t)) if cc.get("live") else None
    target = live if live is not None else cc["to"]
    val, vel = typo.count_value(b * P, c0 * P, (c1 - c0) * P, cc.get("from", 0), target)
    if live is not None and b >= c1:
        val, vel = float(round(live)), 0.0
    land = (b - c1) * P
    pop = 1 + 0.2 * dec(land, 11) if land >= 0 else 1.0
    a_c = 0.0 if cc.get("hidden") else clamp01((b - c0 + 0.3) / 0.3) * (1 - clamp01((b - zt0) / 0.35))
    digits = max(1, len(str(int(round(target)))))
    typo.counter(canvas, val, W / 2, H * 0.735, int(185 * k), "unb", (255, 255, 255), digits, cc.get("prefix", ""),
                 cc.get("suffix", "PP"), vel, int(12 * k), acc, lead_zeros=False, alpha=a_c, scale=pop, affix_color=acc,
                 fps=ctx.fps)
    if land >= 0 and b < zt0 and a_c > 0:
        typo.outline_stack(canvas, f"{int(round(target))}", land, W / 2 - 40 * k, H * 0.735, int(185 * k), "unb",
                           acc, 4, 0.09, max(2, int(3 * k)), 0.5, 0.8)
    ex = (zt0 - 2) * P
    typo.scramble(canvas, cfg.get("caption", ""), (b - 2.0) * P, W / 2, H * 0.81, int(42 * k), "mono",
                  (255, 255, 255), exit_u=ex, seed=21)
    typo.scramble(canvas, cfg.get("sub", ""), (b - 2.6) * P, W / 2, H * 0.843, int(31 * k), "mono", (255, 130, 145),
                  exit_u=ex, seed=22)
    play_tag(ctx, canvas, seg, b)
    play_card(ctx, canvas, seg, b)
    # post
    img = ctx.post.bloom(canvas, 0.75 + 2 * punch)
    img = ctx.post.rgb_split(img, 1.5 * k + 14 * k * bar_env(b, P, 12) + 60 * k * ez)
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
    if cfg.get("counter"):
        c0, c1 = cfg["counter"].get("beats", [1.0, 6.5])
        to = cfg["counter"].get("to")
        if cfg["counter"].get("live"):
            pp = seg.clip.pp_at(seg.src(t0 + c1 * P))
            to = pp if pp is not None else to
        out += ticks(t0 + c0 * P, (c1 - c0) * P, cfg["counter"].get("from", 0), to or 0)
        out.append((t0 + c1 * P, "pop", 0.8))
    out.append((t0 + 2.0 * P, "scramble", 0.3))
    fz0 = cfg.get("freeze")
    if fz0 is not None and cfg.get("stamp"):
        out += [(t0 + fz0 * P, "stamp", 1.0), (t0 + fz0 * P, "glitch", 0.5)]
    out.append((t0 + (nb - cfg.get("zoom_beats", 2)) * P, "whoosh", 0.6))
    return out


def sfx_card(seg):
    card = seg.cfg.get("card")
    if not card:
        return []
    P, t0 = seg.period, seg.t0
    b0 = card.get("beats", [0.4, 0])[0]
    tc = t0 + b0 * P
    out = [(tc, "swipe", 0.4)]
    if card.get("pp"):
        out += ticks(tc + 0.25, 0.9, 0, card["pp"], 20)
        out += [(tc + 1.15, "pop", 0.8), (tc + 1.15, "stamp", 0.35)]
    for i, _ in enumerate(card.get("badges", [])):
        out.append((tc + 1.15 + 0.18 * i, "ting", 0.45))
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
    post = ctx.post
    gV, gC, gM = grade("violet"), grade("cyan"), grade("magenta")
    canvas = L.bg_gradient(W, H, (26, 0, 44), (0, 0, 0))
    gap = 10 * k
    bh = (H - 2 * gap) / 3
    ys = [0, bh + gap, 2 * (bh + gap)]
    VT, VM, VB = View(1.5, 0.95), View(1.0, 0.3), View(1.5, 0.95, flip=True)
    ww, wh = window_dims(ctx, 0.96)
    wcy = H * 0.47
    if b < 7:
        col = ease_in_out_cubic(clamp01(b - 6))
        swap = ease_out_expo(clamp01((b - 4) / 0.45))
        for i in range(3):
            enter = clamp01((b - 0.17 * i) / 0.5)
            ex = (1 - ease_out_expo(enter)) * W * (1 if i % 2 else -1)
            y0, y1 = ys[i], ys[i] + bh
            if i == 1:  # the full-playfield band becomes the final window
                y0, y1 = lerp(ys[1], wcy - wh / 2, col), lerp(ys[1] + bh, wcy + wh / 2, col)
                x0, x1 = lerp(0, (W - ww) / 2, col) + ex, lerp(W, (W + ww) / 2, col) + ex
                v = View(1.0 * (1 + 0.03 * beat_env(b, P, 12)), 0.3)
                L.put_shot(canvas, frame, clip, st, v, L.rect_quad(x0, y0, x1, y1), gV)
                if col > 0:
                    L.quad_outline(canvas, L.rect_quad(x0, y0, x1, y1), acc, 4 * k)
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
    else:  # clean neon window: the whole playfield, gentle 3D sway on the beat
        d = int(b // 4)
        tg = [-7, 6, -6, 7]
        prev = tg[(d - 1) % 4]
        ry = lerp(prev, tg[d % 4], ease_out_back(((b - 4 * d) * P) / 0.4, 1.6))
        dst = gfx.project_rect(ww, wh, W / 2, wcy, 1 + 0.025 * beat_env(b, P, 12), 3 * math.sin(t * 2.1), ry, 0,
                               1900 * k)
        L.put_shot(canvas, frame, clip, st, View(1.0, 0.3), dst, gV)
        L.quad_outline(canvas, dst, acc, 4 * k)
        L.brackets(canvas, dst, (44 + 30 * bar_env(b, P, 7)) * k, 18 * k, (255, 255, 255), 4 * k)
    # typography (kept off the playfield)
    cc = cfg.get("counter") or {"to": 0, "hidden": True}
    c0, c1 = cc.get("beats", [1.2, 5.0])
    val, vel = typo.count_value(b * P, c0 * P, (c1 - c0) * P, cc.get("from", 1), cc["to"])
    land = (b - c1) * P
    out_e = clamp01((b - 5.6) / 0.35)
    a_c = 0.0 if cc.get("hidden") else clamp01((b - c0 + 0.3) / 0.3) * (1 - out_e)
    cy = ys[0] + bh * 0.42
    pop = 1 + 0.18 * dec(land, 11) if land >= 0 else 1.0
    right = typo.counter(canvas, val, W / 2 - 30 * k, cy, int(165 * k), "unb", (255, 255, 255), len(str(cc["to"])),
                         cc.get("prefix", ""), "", vel, int(12 * k), acc, lead_zeros=cc.get("lead_zeros", True),
                         alpha=a_c, scale=pop, affix_size=int(70 * k), affix_color=acc, fps=ctx.fps)
    if land >= 0 and a_c > 0:
        plus = gfx.text_sprite(cc.get("after", "+"), int(150 * k), "unb", acc, glow=int(10 * k), glow_color=acc)
        gfx.blit(canvas, plus, right + plus.shape[1] * 0.35, cy - 6 * k, ease_out_back(land / 0.25, 3.0), 0, a_c)
        typo.outline_stack(canvas, f"{cc['to']}", land, W / 2 + 40 * k, cy, int(165 * k), "unb", acc, 4, 0.1,
                           max(2, int(3 * k)), 0.5, a_c)
    typo.letters(canvas, cfg.get("caption", ""), (b - 2.0) * P, W / 2, cy + 152 * k, int(64 * k),
                 "anton", (255, 255, 255), "rise", 0.022, 0.3, exit_u=(5.55 - 2.0) * P, exit_style="up", seed=32)
    if b >= 7:
        m1, m2 = cfg.get("marquee", ["MREKK  •  ", "OSU!  •  "])
        en = clamp01((b - 7) / 0.5)
        typo.marquee(canvas, m1, t, W / 2, H * 0.755, -7, 380 * k, int(58 * k), "anton", (10, 0, 20), acc, enter=en)
        typo.marquee(canvas, m2, t, W / 2, H * 0.815, 6, -320 * k, int(58 * k), "anton", acc, (255, 255, 255),
                     enter=clamp01((b - 7.15) / 0.5))
        typo.letters(canvas, cfg.get("big", ""), (b - 8) * P, W / 2, H * 0.205, int(150 * k), "anton",
                     (255, 255, 255), "scatter", 0.025, 0.35, glow=int(10 * k), glow_color=acc,
                     exit_u=(nb - 1 - 8) * P, exit_style="glitch", seed=33)
    play_tag(ctx, canvas, seg, b)
    play_card(ctx, canvas, seg, b)
    # post (light on the gameplay)
    img = post.bloom(canvas, 0.8)
    rgb = 1.5 * k + 10 * k * bar_env(b, P, 12)
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
    if cfg.get("counter"):
        c0, c1 = cfg["counter"].get("beats", [1.2, 5.0])
        out += ticks(t0 + c0 * P, (c1 - c0) * P, cfg["counter"].get("from", 1), cfg["counter"]["to"])
        out.append((t0 + c1 * P, "pop", 0.8))
    out += [(t0 + 4 * P, "swipe", 0.55), (t0 + 6 * P, "whoosh", 0.6),
            (t0 + 7 * P, "swipe", 0.5), (t0 + 8 * P, "whoosh", 0.4)]
    return out


# ======================================================================= TROPHIES
@lru_cache(maxsize=16)
def card_sprite(W, k, title, sub, value, badge, value_rgb, badge_rgb=None):
    w, h = int(W * 0.88), int(172 * k)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = int(22 * k)
    d.rounded_rectangle((0, 0, w - 1, h - 1), r, fill=(16, 20, 30, 232), outline=(255, 205, 80, 255),
                        width=max(2, int(3 * k)))
    d.rounded_rectangle((0, 0, int(12 * k), h - 1), r // 2, fill=(255, 195, 50, 255))
    bc = tuple(badge_rgb) if badge_rgb else (255, 195, 50)
    cx, cy, br = int(96 * k), h // 2, int(52 * k)
    d.ellipse((cx - br, cy - br, cx + br, cy + br), fill=bc + (255,))
    d.ellipse((cx - br + 6 * k, cy - br + 6 * k, cx + br - 6 * k, cy + br - 6 * k), outline=(255, 255, 255, 160),
              width=max(1, int(2 * k)))
    d.text((cx, cy + 2), badge, font=gfx.font("unb", int((40 if len(badge) > 2 else 50) * k)), fill=(15, 15, 20, 255),
           anchor="mm")
    if sub:
        d.text((int(172 * k), int(40 * k)), title, font=gfx.font("archivo", int(40 * k)), fill=(255, 255, 255, 255),
               anchor="lm")
        d.text((int(172 * k), int(106 * k)), sub, font=gfx.font("mono", int(31 * k)), fill=(255, 205, 80, 255),
               anchor="lm")
    else:
        d.text((int(172 * k), h // 2), title, font=gfx.font("archivo", int(52 * k)), fill=(255, 255, 255, 255),
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
    cards = cfg.get("cards", [])
    canvas = np.zeros((H, W, 3), np.uint8)
    u_cut = 9.0
    if b < cut_b:
        if cards:  # optional card stack over dimmed gameplay
            L.put_shot(canvas, frame, clip, st, View(1.95 * (1 + 0.03 * beat_env(b, P)), 0.6), full(ctx),
                       grade("ice"))
            canvas = L.dim(canvas, 0.5)
            gap = 205 * k
            y0 = H * 0.47 - gap * (len(cards) - 1) / 2
            for i, cd in enumerate(cards):
                bi = 0.5 + 0.38 * i
                if b < bi:
                    continue
                spr = card_sprite(W, round(k, 3), cd["title"], cd.get("sub", ""), cd["value"], cd.get("badge", ""),
                                  tuple(cd.get("value_color", (255, 205, 80))),
                                  tuple(cd["badge_color"]) if "badge_color" in cd else None)
                spr = shine(spr, (b - bi - 0.6) / 0.45)
                p_ = (b - bi) / 0.45
                ry = -100 * (1 - ease_out_back(p_, 1.5)) + 4 * math.sin(t * 2.3 + i)
                out = clamp01((b - (cut_b - 0.8) - 0.12 * i) / 0.5)
                x = W / 2 + ease_in_expo(out) * W * 1.3
                if out > 0:
                    spr = gfx.hblur(spr, 120 * k * out)
                fy = 7 * k * math.sin(t * 3.1 + i * 1.3)
                sc = 1.0 + 0.05 * dec((b - bi) * P, 10) + 0.025 * beat_env(b, P, 10)
                dst = gfx.project_rect(spr.shape[1], spr.shape[0], x, y0 + i * gap + fy, sc,
                                       3 * math.sin(t * 1.7 + i), ry, 0, 1400 * k)
                gfx.warp_sprite(canvas, spr, dst, min(1, (b - bi) / 0.15))
        else:  # clean ice window with the whole playfield, slow push-in, HUD frame
            canvas[:] = L.bg_blur(frame, W, H, grade("ice"), 0.35)
            ww, wh = window_dims(ctx, 0.95)
            push = 1 + 0.05 * b / max(1.0, cut_b) + 0.02 * beat_env(b, P, 12)
            dst = gfx.project_rect(ww, wh, W / 2, H * 0.47, push, 2 * math.sin(t * 1.6), 4 * math.sin(t * 1.1), 0,
                                   1900 * k)
            M = L.put_shot(canvas, frame, clip, st, View(1.0, 0.3), dst, grade("ice_hot"))
            L.quad_outline(canvas, dst, (230, 250, 255), 3 * k)
            L.brackets(canvas, dst, (40 + 30 * bar_env(b, P, 7)) * k, 18 * k, acc, 5 * k)
            act = L.map_point(M, clip.centre(st))
            for db in range(0, int(cut_b), 2):
                L.shockwave(canvas, act, (b - db) * P, k, (170, 235, 255), 0.6, 0.4)
            # a scanning line sweeping the window
            sy = int(lerp(dst[0][1], dst[3][1], (b * 0.5) % 1))
            cv2.line(canvas, (int(dst[0][0]), sy), (int(dst[1][0]), sy), (255, 240, 200), max(1, int(2 * k)),
                     cv2.LINE_AA)
        if b < 0.5:  # slice-in entrance
            e = ease_out_expo(b / 0.5)
            canvas = post.slices(canvas, 9, [W * (1 - e) * (-1 if i % 2 else 1) for i in range(9)])
    else:
        ci = int((b - cut_b) * 2)
        u_cut = (b - cut_b - ci / 2) * P
        views = [View(1.9, 0.9, rot=-4), View(2.3, 0.95, ox=0.04, rot=3, flip=True), View(1.95, 0.85, rot=5),
                 View(2.4, 0.95, oy=-0.03, rot=-5)]
        v = views[ci % 4]
        v.zoom *= 1 + 0.06 * dec(u_cut, 9)
        L.put_shot(canvas, frame, clip, st, v, full(ctx), grade("ice_hot"))
        if ci % 4 == 0 and u_cut < 1.5 / ctx.fps:
            canvas = cv2.bitwise_not(canvas)
        w = cfg.get("word", "")
        ws = int(min(170 * k, W * 0.9 / max(1, len(w)) / 0.47))
        wy = H * 0.19
        typo.letters(canvas, w, (b - cut_b - 0.4) * P, W / 2 + 6 * k, wy + 6 * k, ws, "anton", acc, "flicker",
                     P / 8, 0.15, outline_only=True, stroke=max(2, int(3 * k)), seed=43)
        typo.letters(canvas, w, (b - cut_b - 0.4) * P, W / 2, wy, ws, "anton", (255, 255, 255), "flicker",
                     P / 8, 0.15, glow=int(10 * k), glow_color=acc, seed=43)
        if cfg.get("word_sub"):
            typo.scramble(canvas, cfg["word_sub"], (b - cut_b - 1.6) * P, W / 2, wy + ws * 0.62, int(40 * k), "mono",
                          acc, tracking=int(8 * k), seed=44)
    play_tag(ctx, canvas, seg, b)
    play_card(ctx, canvas, seg, b)
    # tape stop: slow down, drain colour, wobble, black
    ts = clamp01(b - (nb - 1))
    img = post.bloom(canvas, 0.8)
    img = post.rgb_split(img, 1.5 * k + 14 * k * dec(u_cut, 14))
    if ts > 0:
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        img = cv2.addWeighted(img, 1 - ts, cv2.merge([g, g, g]), ts, 0)
        img = post.wobble(img, 22 * k * ts, t)
        img = post.scanlines(img)
        img = L.dim(img, 0.85 * ts)
        if ts > 0.75:
            img[:] = 0
    return L.flash(img, max(0.2 * dec(u_cut, 16), 0.5 * dec(b * P, 8)))


def sfx_trophies(seg):
    P, t0, cfg = seg.period, seg.t0, seg.cfg
    out = [(t0, "glitch", 0.6), (t0 + 0.3 * P, "swipe", 0.4), (t0 + 0.3 * P, "scramble", 0.25)]
    for i in range(len(cfg.get("cards", []))):
        bi = 0.6 + 0.5 * i
        out += [(t0 + bi * P, "whoosh", 0.45), (t0 + (bi + 0.6) * P, "ting", 0.4)]
    cut_b = cfg.get("cuts_from", 6)
    out.append((t0 + (cut_b - 0.8) * P, "whoosh", 0.55))
    for i in range(int((cfg["beats"] - 1 - cut_b) * 2)):
        out.append((t0 + (cut_b + i / 2) * P, "glitch", 0.22))
    return out


# ======================================================================= RETURN
def _fmt(s, clip, st, seg=None):
    """Expand {card_pp} with the play's pp and {pp} with the live pp danser shows at clip time st."""
    if s and "{card_pp}" in s and seg is not None:
        s = s.replace("{card_pp}", str((seg.cfg.get("card") or {}).get("pp") or ""))
    if s and "{pp}" in s:
        pp = clip.pp_at(st)
        s = s.replace("{pp}", str(int(round(pp))) if pp is not None else "")
    return s


def click_pulses(canvas, clip, st, M, k, color=(255, 225, 160), life=0.28):
    """A ring + glow at the real cursor for every key press in the last `life` seconds."""
    if not len(clip.presses) or getattr(clip, "cursor", None) is None:
        return 0.0
    i1 = np.searchsorted(clip.presses, st, side="right")
    i0 = np.searchsorted(clip.presses, st - life)
    env = 0.0
    for pt in clip.presses[i0:i1]:
        age = (st - pt) / life
        pos = L.map_point(M, clip.cursor_at(pt))
        L.ring(canvas, pos, (18 + 60 * gfx.ease_out_cubic(age)) * k, max(1, 4 * k * (1 - age)), color, (1 - age) ** 1.5)
        L.glow_dot(canvas, pos, 16 * k, color, 0.55 * (1 - age))
        env = max(env, math.exp(-age * 6))
    return env


def render_return(ctx, seg, t):
    W, H, k = ctx.W, ctx.H, ctx.k
    P, b, cfg = seg.period, bpos(seg, t), seg.cfg
    nb = cfg["beats"]
    clip = seg.clip
    acc = ACCENT["return"]
    st = seg.src(t)
    post = ctx.post
    lost_b = cfg.get("again_at", 4)
    grid_b, mont_b = cfg.get("grid_at", 6), cfg.get("montage_at", 8)
    show_b = cfg.get("showcase_at", grid_b)
    gold = grade("gold")
    if b < lost_b:  # ---------------- muffled black & white intro with the map name
        frame = clip.frame(st)
        canvas = L.bg_gradient(W, H, (24, 24, 26), (0, 0, 0))
        ww, wh = window_dims(ctx)
        dst = gfx.project_rect(ww, wh, W / 2, H * 0.44, 1 + 0.02 * b / lost_b, 3, 0, 0, 1700 * k)
        L.put_shot(canvas, frame, clip, st, View(1.0, 0.3), dst, grade("bw"))
        L.quad_outline(canvas, dst, (200, 200, 200), 2 * k)
        canvas = post.scanlines(canvas)
        it = cfg.get("intro", {})
        ex = (lost_b - 0.2) * P
        if it.get("top"):
            typo.scramble(canvas, _fmt(it["top"], clip, st), (b - 0.1) * P, W / 2, H * 0.12, int(56 * k), "mono",
                          (255, 255, 255), exit_u=ex, seed=51)
        u1 = (b - 0.4) * P
        big = _fmt(it.get("big", ""), clip, st)
        if u1 >= 0 and big:
            bsz = fit_size(big, "unb", W * 0.84, 400 * k)
            e = ease_out_cubic(u1 / 0.1)
            a = min(1, u1 / 0.05) * (1 - clamp01((b - (lost_b - 0.2)) / 0.2))
            j = 10 * k * dec(u1, 16)
            typo.outline_stack(canvas, big, u1, W / 2, H * 0.43, bsz, "unb", (200, 200, 200), 3, 0.1,
                               max(2, int(3 * k)), 0.5, a * 0.7)
            spr = gfx.text_sprite(big, bsz, "unb", (255, 255, 255))
            gfx.blit(canvas, spr, W / 2 + j * math.sin(t * 80), H * 0.43, 1 + 1.2 * (1 - e), 0, a)
        if it.get("word"):
            typo.letters(canvas, it["word"], (b - 1.6) * P, W / 2, H * 0.70, int(120 * k), "anton",
                         tuple(it.get("word_color", (235, 235, 235))), "drop", 0.035, 0.4,
                         exit_u=(lost_b - 0.25 - 1.6) * P, exit_style="glitch", seed=52)
        img = post.wobble(canvas, 3 * k, t)
        return post.rgb_split(img, 4 * k + 18 * k * dec(u1, 10))
    if b < show_b:  # ---------------- gold impact
        frame = clip.frame(st)
        u = (b - lost_b) * P
        e = ease_out_expo(u / (0.45 * P * 2))
        canvas = L.bg_blur(frame, W, H, gold, 0.5)
        ww, wh = window_dims(ctx)
        fw, fh = W, W * 0.75
        x0, y0 = lerp((W - ww) / 2, 0, e), lerp(H * 0.44 - wh / 2, H * 0.44 - fh / 2, e)
        x1, y1 = lerp((W + ww) / 2, W, e), lerp(H * 0.44 + wh / 2, H * 0.44 + fh / 2, e)
        M = L.put_shot(canvas, frame, clip, st, View(1.0 * (1 + 0.04 * beat_env(b, P)), 0.3),
                       L.rect_quad(x0, y0, x1, y1), gold)
        act = L.map_point(M, clip.centre(st))
        L.shockwave(canvas, (W / 2, H * 0.44), u, k, (255, 220, 120), 1.6, 0.6)
        L.speed_lines(canvas, (W / 2, H * 0.44), 1.1 * dec(u, 5), ctx.fi, k, 64, (255, 215, 140))
        for bb in range(int(lost_b), int(show_b)):
            L.sparks(canvas, act, (b - bb) * P, 500 + bb, k, 30, (255, 210, 120), 1700, 0.5)
        im = cfg.get("impact", {})
        ex = (show_b - 0.25 - lost_b) * P
        fade = 1 - clamp01((u - ex) / 0.15)
        if im.get("top"):
            typo.scramble(canvas, _fmt(im["top"], clip, st), u - 0.02, W / 2, H * 0.12, int(56 * k), "mono", acc,
                          exit_u=ex, seed=54)
        big = _fmt(im.get("big", ""), clip, seg.src(seg.t0 + lost_b * P), seg)
        if big in ("PP", ""):
            big = ""
        if big:
            bsz = fit_size(big, "unb", W * 0.84, 400 * k)
            spr = gfx.text_sprite(big, bsz, "unb", acc, glow=int(18 * k), glow_color=(255, 140, 0))
            typo.outline_stack(canvas, big, u, W / 2, H * 0.43, bsz, "unb", acc, 5, 0.12, max(2, int(4 * k)), 0.6, fade)
            e2 = ease_out_cubic(u / 0.1)
            gfx.blit(canvas, spr, W / 2, H * 0.43, 1 + 1.3 * (1 - e2), 0, min(1, u / 0.04) * fade)
        if im.get("word"):
            typo.letters(canvas, im["word"], u - 0.4 * P, W / 2, H * 0.70, int(140 * k), "anton", (255, 255, 255),
                         "spin", 0.04, 0.4, exit_u=ex - 0.4 * P, exit_style="scatter", seed=55)
        img = post.bloom(canvas, 1.0)
        img = post.rgb_split(img, 1.5 * k + 34 * k * dec(u, 8))
        img = post.zoom_blur(img, 0.08 * dec(u, 6))
        return L.flash(img, 0.95 * dec(u, 5), (255, 225, 150))
    if b < grid_b:  # ---------------- showcase: the play itself, clicks lighting up under the cursor
        frame = clip.frame(st)
        canvas = L.bg_blur(frame, W, H, gold, 0.4)
        fw, fh = W * 0.98, W * 0.98 * 0.75
        wcy = H * 0.47
        q0 = gfx.project_rect(fw, fh, W / 2, wcy, 1.0, 0, 0, 0, 2000 * k)
        src_q = L.view_quad(clip, st, View(1.0, 0.3), fw / fh)
        cenv = click_pulses(np.zeros((1, 1, 3), np.uint8), clip, st, cv2.getPerspectiveTransform(src_q, q0), k)
        sc = 1 + 0.02 * beat_env(b, P, 12) + 0.012 * cenv
        dst = gfx.project_rect(fw, fh, W / 2, wcy, sc, 2.5 * math.sin(t * 1.7), 4 * math.sin(t * 1.25), 0, 2000 * k)
        M = L.put_shot(canvas, frame, clip, st, View(1.0, 0.3), dst, gold)
        click_pulses(canvas, clip, st, M, k)
        L.quad_outline(canvas, dst, (255, 220, 150), 3 * k)
        L.brackets(canvas, dst, (40 + 30 * bar_env(b, P, 7)) * k, 18 * k, acc, 5 * k)
        if cfg.get("live_pp"):
            pp = clip.pp_at(st)
            if pp is not None:
                a_c = clamp01((b - show_b) / 0.4) * (1 - clamp01((b - (grid_b - 0.3)) / 0.3))
                typo.counter(canvas, float(round(pp)), W / 2, H * 0.2, int(130 * k), "unb", (255, 255, 255),
                             len(str(int(round(pp)))), "", "PP", 0.0, int(10 * k), acc, lead_zeros=False, alpha=a_c,
                             affix_color=acc, fps=ctx.fps)
        play_tag(ctx, canvas, seg, b)
        play_card(ctx, canvas, seg, b)
        img = post.bloom(canvas, 0.8)
        img = post.rgb_split(img, 1.5 * k + 10 * k * bar_env(b, P, 12) + 6 * k * cenv)
        return L.flash(img, 0.35 * dec((b - show_b) * P, 9))
    if b < mont_b:  # ---------------- 3x3 grid
        frame = clip.frame(st)
        canvas = np.zeros((H, W, 3), np.uint8)
        g8 = 8 * k
        tw, th = (W - 4 * g8) / 3, (H - 4 * g8) / 3
        zooms = [1.5, 1.3, 1.7, 1.4, 1.25, 1.35, 1.75, 1.45, 1.6]
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
            L.put_shot(canvas, frame, clip, st, View(zooms[idx] * (1 + 0.05 * beat_env(b, P)), 0.85,
                                                    flip=idx % 2 == 1), q, grade(gn))
        img = post.bloom(canvas, 0.8)
        img = post.rgb_split(img, 1.5 * k + 16 * k * beat_env(b, P, 10))
        if coll > 0:
            img = post.zoom_blur(img, 0.08 * ec)
        return L.flash(img, 0.25 * beat_env(b, P, 16))
    # ---------------- accelerating montage across every clip, the words take centre stage
    cuts = cfg.get("cuts") or [mont_b + c for c in (0, 1, 2, 3, 4, 4.5, 5, 5.5, 6, 6.25, 6.5, 6.75, 7, 7.25, 7.5, 7.75)]
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
    build = clamp01((b - (mont_b + 4)) / 4)
    if typ == 0:
        L.put_shot(canvas, frame, mclip, mst, View(1.9 * (1 + 0.05 * dec(u_cut, 9)), 0.9, rot=-3), full(ctx), g)
    elif typ == 1:
        canvas[:] = L.bg_blur(frame, W, H, g, 0.45)
        ww, wh = window_dims(ctx)
        dst = gfx.project_rect(ww, wh, W / 2, H * 0.45, 1 + 0.08 * dec(u_cut, 9), 6, 16 if ci % 8 == 1 else -16, 0,
                               1600 * k)
        L.put_shot(canvas, frame, mclip, mst, View(1.0, 0.35), dst, g)
        L.quad_outline(canvas, dst, (255, 255, 255), 3 * k)
        L.brackets(canvas, dst, 50 * k, 18 * k, acc, 5 * k)
    elif typ == 2:
        canvas[:] = L.bg_blur(frame, W, H, g, 0.45)
        fw, fh = W, W * 0.75
        L.put_shot(canvas, frame, mclip, mst, View(1.0 * (1 + 0.05 * dec(u_cut, 9)), 0.3, flip=ci % 3 == 0),
                   L.rect_quad(0, H * 0.47 - fh / 2, W, H * 0.47 + fh / 2), g)
    else:
        L.put_shot(canvas, frame, mclip, mst, View(1.3, 0.9), L.rect_quad(0, 0, W, H / 2 - 5 * k), g)
        L.put_shot(canvas, frame, mclip, mst, View(1.3, 0.9, flip=True), L.rect_quad(0, H / 2 + 5 * k, W, H),
                   grade("bw"))
    words = cfg.get("words", [])
    wcy = H * 0.45
    if words:  # focus: darken a soft band behind the words
        ys = np.arange(H, dtype=np.float32)
        band = 1 - 0.55 * np.exp(-((ys - wcy) / (H * 0.13)) ** 2)
        y0, y1 = int(wcy - H * 0.3), int(wcy + H * 0.3)
        canvas[y0:y1] = (canvas[y0:y1].astype(np.float32) * band[y0:y1, None, None]).astype(np.uint8)
    for wi, (wb, wtxt, wst) in enumerate(words):
        nxt = words[wi + 1][0] if wi + 1 < len(words) else nb
        if not (wb <= b < nxt + 0.3):
            continue
        u = (b - wb) * P
        size = int(min(360 * k, W * 0.92 / max(1, len(wtxt)) / 0.45))
        sh = 16 * k * build
        cx = W / 2 + sh * math.sin(t * 73)
        cy = wcy + sh * math.cos(t * 61)
        last = wi == len(words) - 1
        oy_w = glyph_offset(wtxt[0], size, "anton")[1]
        typo.outline_stack(canvas, wtxt, u, cx, cy, size, "anton", acc, 6 if last else 4, 0.1, max(2, int(4 * k)),
                           0.5, 1.0 if last else 0.7)
        typo.letters(canvas, wtxt, u, cx, cy, size, "anton", (255, 255, 255), wst, 0.03, 0.28, glow=int(16 * k),
                     glow_color=acc, exit_u=(nxt - wb) * P if not last else None, exit_style="scatter",
                     exit_dur=0.12, seed=60 + wi)
        L.flare(canvas, (W / 2, cy), 0.9 * dec(u, 7), (255, 215, 150), k)
        if last:
            typo.shine_text(canvas, wtxt, size, "anton", cx, cy + 0 * oy_w, ((b - wb) % 2) / 1.2)
    play_tag(ctx, canvas, seg, b)
    img = post.bloom(canvas, 0.8 + 0.4 * build)
    img = zoom_canvas(img, 1 + 0.12 * build ** 2, rot=3 * build * math.sin(t * 9))
    img = post.rgb_split(img, 1.5 * k + 16 * k * dec(u_cut, 14) + 14 * k * build)
    if u_cut < 0.04 and ci >= 8:
        img = post.glitch(img, 0.6, ctx.fi)
    fl = max(0.3 * dec(u_cut, 14) * (0.6 + build), ease_in_expo((b - (nb - 0.4)) / 0.4))
    return L.flash(img, fl)


def sfx_return(seg):
    P, t0, cfg = seg.period, seg.t0, seg.cfg
    lost_b, grid_b, mont_b = cfg.get("again_at", 4), cfg.get("grid_at", 6), cfg.get("montage_at", 8)
    show_b = cfg.get("showcase_at", grid_b)
    out = [(t0 + 0.4 * P, "stamp", 0.8), (t0 + 1.6 * P, "stamp", 0.45), (t0 + lost_b * P, "impact", 1.0),
           (t0 + lost_b * P, "ting", 0.6), (t0 + lost_b * P, "scramble", 0.3)]
    if show_b < grid_b:
        out += [(t0 + show_b * P, "swipe", 0.5)]
    out += [(t0 + (grid_b + 0.125 * i) * P, "tick", 0.45) for i in range(9)]
    out.append((t0 + (mont_b - 0.5) * P, "whoosh", 0.6))
    cuts = cfg.get("cuts") or [mont_b + c for c in (0, 1, 2, 3, 4, 4.5, 5, 5.5, 6, 6.25, 6.5, 6.75, 7, 7.25, 7.5, 7.75)]
    for c in cuts:
        late = c >= mont_b + 6
        out.append((t0 + c * P, "glitch" if late else "swipe", 0.3 if late else 0.35))
    for w in cfg.get("words", []):
        out.append((t0 + w[0] * P, "stamp", 0.45))
    out.append((t0 + (mont_b + 4) * P, "riser", 0.6, 4 * P))
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
    dur = seg.dur
    clip, st = seg.clip, seg.smap[0]
    frame = clip.frame(st)
    post = ctx.post
    canvas = L.dim(L.bg_blur(frame, W, H, grade("gold"), 0.5), 0.62)
    title = cfg.get("title", "MREKK")
    size = int(min(400 * k, W * 0.86 / max(1, len(title)) / 0.5))
    cy = H * 0.43
    cents = word_glyph_centres(title, size, "anton", W / 2, cy)
    names = cfg.get("letters_from") or list(ctx.src_start.keys())
    t_hit = dur - 0.38  # the closing hit circle
    shrink = ease_in_expo(clamp01((u - (t_hit - 0.42)) / 0.3))
    ws = 1 - 0.9 * shrink
    fade = 1 - shrink
    # 3D extrusion behind the word
    if fade > 0.01:
        depth = gfx.text_sprite(title, size, "anton", (70, 34, 6))
        oy0 = glyph_offset("M", size, "anton")[1]
        a_d = clamp01((u - 0.2) / 0.2) * fade
        for d in range(9, 0, -1):
            gfx.blit(canvas, depth, W / 2 + d * 3.2 * k * ws, cy + oy0 + d * 4.2 * k * ws, ws, 0, a_d * 0.9)
    # letters: each one filled with a different play, landing with a 3D flip
    for i, ch in enumerate(title):
        ti = u - i * 0.065
        if ti < 0 or fade <= 0.01:
            continue
        name = names[i % len(names)]
        gw, gh = int(size * 0.62), int(size * 1.05)
        fill = tinted_fill(shot_image(ctx, name, ctx.src_start[name] + 1.3 + 0.12 * i, gw, gh, View(1.45, 0.85),
                                      grade(ctx.grade_name.get(name, "gold"))), CLIP_TINT.get(name, (255, 190, 40)))
        spr = typo.glyph_fill_sprite(ch, size, "anton", fill)
        edge = gfx.text_sprite(ch, size, "anton", (255, 255, 255), stroke=max(2, int(4 * k)), outline_only=True)
        pe = ease_out_back(ti / 0.32, 1.5)
        ry = 85 * (1 - pe)
        drop = -160 * k * (1 - ease_out_expo(ti / 0.32))
        gx = W / 2 + (cents[i][0] - W / 2) * ws
        gy = cy + (cents[i][1] - cy) * ws + drop * fade
        ox, oy = glyph_offset(ch, size, "anton")
        mx, my = gx + ox * ws, gy + oy * ws
        a_l = min(1, ti / 0.06) * fade
        for s_img in (spr, edge):
            dst = gfx.project_rect(s_img.shape[1], s_img.shape[0], mx, my, ws, 0, ry, 0, 1100 * k)
            gfx.warp_sprite(canvas, s_img, dst, a_l)
    land = u - (len(title) - 1) * 0.065 - 0.25
    oy_w = glyph_offset("M", size, "anton")[1]
    if land >= 0 and fade > 0.01:
        typo.outline_stack(canvas, title, land, W / 2, cy + oy_w, size, "anton", (255, 200, 80), 6, 0.07,
                           max(2, int(4 * k)), 0.7, fade)
        if shrink <= 0:
            typo.shine_text(canvas, title, size, "anton", W / 2, cy + oy_w, (land - 0.12) / 0.3)
        L.flare(canvas, (W / 2, cy), 1.1 * dec(land, 5), (255, 215, 150), k)
    # "1 OF 1" with expanding tracking + underline, then the four maps
    if fade > 0.01:
        su = u - 0.42
        if su >= 0:
            tr = int(lerp(6 * k, 34 * k, ease_out_expo(su / 0.6)))
            typo.scramble(canvas, cfg.get("sub", "1 OF 1"), su, W / 2, H * 0.585, int(66 * k), "mono",
                          (255, 255, 255), dur=0.45, tracking=tr, seed=71, alpha=fade)
            lw = W * 0.32 * ease_out_expo((su - 0.15) / 0.4)
            if lw > 1:
                cv2.line(canvas, (int(W / 2 - lw), int(H * 0.622)), (int(W / 2 + lw), int(H * 0.622)),
                         tuple(int(v * fade) for v in (80, 200, 255)), max(1, int(3 * k)), cv2.LINE_AA)
        if cfg.get("credits"):
            typo.scramble(canvas, cfg["credits"], u - 0.75, W / 2, H * 0.655, int(25 * k), "mono", (255, 205, 120),
                          dur=0.5, seed=73, alpha=fade)
    # the closing hit circle: approach, hit, burst
    if u > t_hit - 0.45:
        appr = clamp01((t_hit - u) / 0.45)
        if u < t_hit:
            L.hit_circle(canvas, (W / 2, cy), 150 * k, appr, (255, 170, 40), min(1, (u - (t_hit - 0.45)) / 0.1), "1", k)
        else:
            hu = u - t_hit
            if hu < 0.2:
                L.hit_circle(canvas, (W / 2, cy), 150 * k * (1 + 0.6 * ease_out_expo(hu / 0.2)), 0, (255, 170, 40),
                             1 - hu / 0.2, "1", k)
            for dly, sz in ((0.0, 1.5), (0.05, 1.0)):
                L.shockwave(canvas, (W / 2, cy), hu - dly, k, (255, 230, 170), sz, 0.45)
            L.sparks(canvas, (W / 2, cy), hu, 77, k, 50, (255, 215, 150), 1900, 0.5)
            L.speed_lines(canvas, (W / 2, cy), dec(hu, 6), ctx.fi, k, 60, (255, 220, 160))
    img = post.bloom(canvas, 0.9)
    img = post.rgb_split(img, 2 * k + 30 * k * dec(u, 6) + (30 * k * dec(u - t_hit, 8) if u >= t_hit else 0))
    img = post.zoom_blur(img, 0.06 * dec(u, 6))
    flash = 0.9 * dec(u, 5)
    if u >= t_hit:
        flash = max(flash, 1.0 if u - t_hit < 2 / ctx.fps else 0.8 * dec(u - t_hit, 6))
    img = L.flash(img, flash)
    tail = clamp01((u - (t_hit + 0.14)) / max(0.05, dur - t_hit - 0.14))
    return L.dim(img, tail ** 0.7)


def sfx_outro(seg):
    t0, dur = seg.t0, seg.dur
    t_hit = dur - 0.38
    out = [(t0, "stamp", 0.6), (t0 + 0.42, "scramble", 0.35), (t0 + 0.6, "ting", 0.45),
           (t0 + t_hit, "hit", 1.0), (t0 + t_hit, "impact", 0.6)]
    if seg.cfg.get("credits"):
        out.append((t0 + 0.75, "scramble", 0.3))
    return out


RENDER = {"hook": render_hook, "record": render_record, "reign": render_reign, "trophies": render_trophies,
          "return": render_return, "outro": render_outro}
SFX = {"hook": sfx_hook, "record": sfx_record, "reign": sfx_reign, "trophies": sfx_trophies, "return": sfx_return,
       "outro": sfx_outro}
AUDIO_FX = {"return": audio_return}
