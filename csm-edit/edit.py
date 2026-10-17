"""Chainsaw Man collage edit: assets and the 43 scenes, timed to the reference sound (0-34.4 s).

Structure, timings, scales and cadence follow the reference breakdown (white collage edit); the subjects are swapped for
Chainsaw Man: puppet strings that snap and leave Denji on a leash, a chainsaw bar for the beam, a collage Chainsaw Man
head with Makima-ring HUD, Aki bowling, Pochita as the machine, the starter cord becoming a chainsaw, a blood splash,
Makima's ringed eyes, Reze's gerbera, a chainsaw arm dripping blood, and a recap totem on a chain.
"""
import math
import os
import sys

import cv2
import numpy as np
import skia

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from engine import core, fx, timeline as tl  # noqa: E402
from engine.core import (W, H, draw_image, to_image, paint, brush, ribbon, dotted, line, polyline, bezier, catenary,  # noqa: E402
                         chain, rings, splatter, text, mix, clamp01, prog, smooth, out_cubic, in_cubic, out_expo,
                         in_expo, in_out_cubic, out_back, c4, cint, tint_filter, mono_filter, invert_filter, layer,
                         sample_path, path_length, line_part)
from engine.cutout import Cut, full_frames, read_frames, SCRATCH, SRC  # noqa: E402

A = f"{SCRATCH}/assets"
FONT_LYR = f"{A}/fonts/OpenSans-Regular.ttf"
FONT_HEY = f"{A}/fonts/PermanentMarker-Regular.ttf"
FONT_MONO = f"{A}/fonts/JetBrainsMono-400.ttf"
AUDIO = f"{SCRATCH}/ref/ref.mp4"
END = 34.40

core.BG = (251 / 255,) * 3     # read at clear() time


def rgb(hexs):
    hexs = hexs.lstrip("#")
    return tuple(int(hexs[i:i + 2], 16) / 255 for i in (0, 2, 4))


WHITE = core.BG
GREYTXT = rgb("555555")
CYAN, CYAN_HI = rgb("55C0C9"), rgb("99E1E7")
RED, RED_HI = rgb("CC5946"), rgb("ECACA2")
TEAL, TEAL_HI = rgb("096265"), rgb("84BCC0")
HERO = rgb("E5210D")          # the reference's purple line/tube/stroke, as blood red
HERO_DK = rgb("8E0F06")
NAVY = rgb("1E1364")
MINT, MINT2 = rgb("40E19B"), rgb("64E7A9")
ECHO_CY, ECHO_CY2 = rgb("1DE3CE"), rgb("63EAD8")
BLOCK = rgb("5ADBB3")
INK = (0.06, 0.06, 0.07)

tl.BEATS[:] = [0.8, 1.47, 2.14, 2.82, 3.46, 4.13, 4.77, 5.44, 6.14, 6.82, 7.49, 8.16, 8.83, 9.5, 10.14, 10.82, 11.49,
               12.16, 12.8, 13.47, 14.24, 14.91, 15.58, 16.26, 16.93, 17.6, 18.21, 18.85, 19.62, 20.29, 20.96, 21.63,
               22.37, 23.17, 23.81, 24.48, 25.12, 25.86, 26.5, 27.17, 27.84, 28.51, 29.12, 29.82, 30.37, 31.01, 31.65,
               32.32, 32.99, 33.66]


def step(t, fps=12.0):
    """time quantised to animation 'on twos' (12 fps at 24)."""
    return math.floor(t * fps + 1e-6) / fps


# ------------------------------------------------------------------------------------------------ cut-outs

def _pochita_shape(shape):
    h, w = shape
    m = np.zeros((h, w), np.float32)
    cv2.ellipse(m, (885, 640), (415, 430), 0, 0, 360, 1.0, -1, cv2.LINE_AA)
    cv2.rectangle(m, (590, 0), (1200, 250), 1.0, -1)
    return m


def _edge_fade(shape):
    """soften the straight crop edges: fade the sides and the bottom of a close-up."""
    h, w = shape
    x = np.linspace(0, 1, w)[None, :]
    y = np.linspace(0, 1, h)[:, None]
    side = np.clip(np.minimum(x, 1 - x) / 0.10, 0, 1)
    bottom = np.clip((1 - y) / 0.30, 0, 1)
    return (side * bottom).astype(np.float32)


def _arm_shape(shape):
    m = np.ones(shape, np.float32)
    m[int(shape[0] * 0.45):, int(shape[1] * 0.78):] = 0
    return m


def _head_shape(shape):
    m = np.ones(shape, np.float32)
    m[:200, :740] = 0
    m[:165, :] = 0
    return m


def _bowl_shape(shape):
    m = np.ones(shape, np.float32)
    m[:, :170] = 0
    return m


CUTS = dict(
    duo=dict(vid="nced12_fight_song", t0=2.10),
    hand=dict(vid="pv_teaser_2020", t0=38.80),
    cordhand=dict(vid="pv_main_2022", t0=66.30, t1=66.80),
    puppet=dict(vid="ncop_kickback", t0=81.90, crop=(0, 0, 1180, 1080)),
    leash=dict(vid="ncop_kickback", t0=35.15, t1=35.45),
    kid=dict(vid="pv_teaser_2020", t0=16.50),
    head=dict(vid="pv2_2022", t0=81.90, gc_rect=(560, 0, 1500, 1080), mask_fn=_head_shape),
    bowl=dict(vid="ncop_kickback", t0=30.80, crop=(900, 0, 1920, 1080), mask_fn=_bowl_shape),
    power_fly=dict(vid="ncop_kickback", t0=56.40),
    saw=dict(vid="pv_main_2022", t0=72.00),
    pochita=dict(vid="cpv_denji", t0=10.90, crop=(0, 0, 1920, 985), gc_rect=(430, 0, 1380, 985), mask_fn=_pochita_shape),
    arm=dict(vid="ncop_kickback", t0=72.20, t1=72.70, lo=0.45, hi=0.85, erode=2, mask_fn=_arm_shape),
    swing=dict(vid="pv_main_2022", t0=91.45),
    face=dict(vid="ncop_kickback", t0=27.90),
    scream=dict(vid="pv_main_2022", t0=53.20, t1=53.70, crop=(150, 100, 1250, 1080), mask_fn=_edge_fade),
    sawarm=dict(vid="ncop_kickback", t0=72.45, crop=(100, 430, 1050, 800)),
    finger=dict(vid="pv_main_2022", t0=84.50),
    power_cu=dict(vid="nced12_fight_song", t0=1.40, t1=1.90),
    flower=dict(vid="reze_trailer_2025", t0=15.30, crop=(0, 138, 1920, 944)),
    makima=dict(vid="pv_main_2022", t0=31.00, crop=(350, 0, 1920, 1080)),
    eat=dict(vid="pv2_2022", t0=46.80),
)
_cuts = {}


def cut(name):
    c = _cuts.get(name)
    if c is None:
        kw = dict(CUTS[name])
        vid, t0 = kw.pop("vid"), kw.pop("t0")
        c = _cuts[name] = Cut(vid, t0, name=name, **kw)
    return c


def _load_tex(names, size=1024):
    return fx.load_textures([f"{A}/textures/{n}.jpg" for n in names], size)


_tex = {}


def tex(kind):
    if kind not in _tex:
        _tex[kind] = _load_tex({
            "stone": ["concrete_wall_008", "cracked_concrete_wall", "damaged_plaster", "factory_wall"],
            "metal": ["rusty_metal_02", "metal_plate", "green_metal_rust", "corrugated_iron_02", "painted_metal_shutter",
                      "box_profile_metal_sheet", "rust_coarse_01", "blue_metal_plate"],
            "paper": ["decrepit_wallpaper", "damaged_plaster", "concrete_wall_008"],
        }[kind])
    return _tex[kind]


def _thermal(rgba, cmap=cv2.COLORMAP_TURBO, shift=0):
    g = cv2.cvtColor(rgba[..., :3], cv2.COLOR_RGB2GRAY)
    g = ((g.astype(np.int32) + shift) % 256).astype(np.uint8)
    col = cv2.applyColorMap(g, cmap)[..., ::-1]
    return np.dstack([col, rgba[..., 3]])


def _mono(rgba, contrast=1.25, tex_kind="paper", seed=0):
    g = cv2.cvtColor(rgba[..., :3], cv2.COLOR_RGB2GRAY).astype(np.float32) / 255
    g = np.clip((g - 0.5) * contrast + 0.5, 0, 1)
    t = tex(tex_kind)[seed % len(tex(tex_kind))]
    th, tw = t.shape[:2]
    h, w = g.shape
    tt = cv2.resize(t, (max(w, int(tw * h / th)), h))[:h, :w].mean(axis=2) / 255
    g = g * (0.75 + 0.25 * tt / max(tt.mean(), 1e-3))
    v = (np.clip(g, 0, 1) * 255).astype(np.uint8)
    return np.dstack([v, v, v, rgba[..., 3]])


def _bright_tint(rgba, col):
    """bright flat single-hue tint keeping the drawing (the reference's mint/cyan afterimages)."""
    g = cv2.cvtColor(rgba[..., :3], cv2.COLOR_RGB2GRAY).astype(np.float32)
    lo, hi = np.percentile(g[rgba[..., 3] > 128], [3, 97]) if (rgba[..., 3] > 128).any() else (0, 255)
    gn = np.clip((g - lo) / max(hi - lo, 1), 0, 1)
    c = np.array(col, np.float32)[None, None]
    out = c * (0.62 + 0.50 * gn[..., None])
    return np.dstack([(np.clip(out, 0, 1) * 255).astype(np.uint8), rgba[..., 3]])


def _lift(rgba, gamma=0.7):
    out = rgba.copy()
    out[..., :3] = (255 * np.power(rgba[..., :3] / 255.0, gamma)).astype(np.uint8)
    return out


def _steel(rgba, seed=0):
    """light brushed-steel grey version (the reference's robot arm)."""
    src = rgba[..., :3].astype(np.float32) / 255
    g = cv2.cvtColor(src, cv2.COLOR_RGB2GRAY)
    g = 0.30 + 0.70 * np.power(np.clip(g, 0, 1), 0.6)
    tl_ = _tex_like(g.shape, "metal", seed + 3)
    out = np.dstack([g * 0.97, g * 0.99, g * 1.03]) * (0.82 + 0.18 * tl_[..., None])
    return np.dstack([(np.clip(out, 0, 1) * 255).astype(np.uint8), rgba[..., 3]])


def _flat(rgba, col, detail=0.35):
    """flat colour silhouette keeping a little luminance detail."""
    g = cv2.cvtColor(rgba[..., :3], cv2.COLOR_RGB2GRAY).astype(np.float32) / 255
    c = np.array(col, np.float32)[None, None]
    out = c * (1 - detail) + c * g[..., None] * detail * 1.6
    return np.dstack([(np.clip(out, 0, 1) * 255).astype(np.uint8), rgba[..., 3]])


def _silhouette(rgba, col=(1, 1, 1)):
    out = np.zeros_like(rgba)
    out[..., :3] = (np.array(col) * 255).astype(np.uint8)
    out[..., 3] = rgba[..., 3]
    return out


def _paint_tips(rgba, seed=0):
    """dabs of paint on the extremities (fingertips) of a collage hand."""
    out = rgba.copy()
    a = rgba[..., 3] > 128
    ys, xs = np.where(a)
    if len(xs) == 0:
        return out
    rng = np.random.default_rng(seed)
    cols = [HERO, CYAN, NAVY, rgb("7748CE"), rgb("2AB3EF")]
    h, w = a.shape
    ymax = ys.max()
    cand = [(x, y) for x, y in zip(xs[::97], ys[::97]) if y > ymax - h * 0.22]
    rng.shuffle(cand)
    for k, (x, y) in enumerate(cand[:5]):
        col = (np.array(cols[k % len(cols)]) * 255).astype(np.uint8)
        r = int(max(8, w * 0.035))
        m = np.zeros((h, w), np.uint8)
        cv2.circle(m, (int(x), int(y)), r, 1, -1)
        m = (m > 0) & a
        out[m, :3] = (out[m, :3] * 0.35 + col * 0.65).astype(np.uint8)
    return out


def _tex_like(shape, kind, seed):
    t = tex(kind)[seed % len(tex(kind))]
    h, w = shape
    th, tw = t.shape[:2]
    sc = max(h / th, w / tw)
    t2 = cv2.resize(t, (int(tw * sc) + 1, int(th * sc) + 1))[:h, :w].astype(np.float32) / 255
    lum = t2.mean(axis=2)
    return lum / max(lum.mean(), 1e-3)


def _stone(rgba, seed=0, tips=None):
    """grey stone/concrete version of a cut-out (keeps its drawing), optional painted fingertips."""
    src = rgba[..., :3].astype(np.float32) / 255
    g = cv2.cvtColor(src, cv2.COLOR_RGB2GRAY)
    tl_ = _tex_like(g.shape, "stone", seed)
    base = np.array(rgb("ABA29C"), np.float32)
    out = base[None, None] * (0.50 + 0.62 * g)[..., None] * (0.70 + 0.30 * tl_)[..., None]
    lines = np.clip((0.30 - cv2.GaussianBlur(g, (0, 0), 0.8)) / 0.18, 0, 1)[..., None]
    out = out * (1 - lines) + (out * 0.35) * lines
    res = rgba.copy()
    res[..., :3] = (np.clip(out, 0, 1) * 255).astype(np.uint8)
    if tips:
        a = rgba[..., 3] > 100
        hh, ww = a.shape
        for (x, y), col in zip(tips, [HERO, CYAN, NAVY]):
            m = np.zeros((hh, ww), np.uint8)
            cv2.circle(m, (int(x), int(y)), int(ww * 0.06), 1, -1)
            m = (m > 0) & a
            c255 = np.array(col) * 255
            res[m, :3] = (res[m, :3] * 0.25 + c255 * 0.75 * (0.6 + 0.4 * tl_[m][:, None])).clip(0, 255).astype(np.uint8)
    return res


def _metal(rgba, seed=0):
    """the drawing with a brushed/rusty metal texture worked into it (still reads as itself)."""
    src = rgba[..., :3].astype(np.float32) / 255
    tl_ = _tex_like(src.shape[:2], "metal", seed)
    g = cv2.cvtColor(src, cv2.COLOR_RGB2GRAY)[..., None]
    out = (src * 0.75 + g * 0.25) * (0.62 + 0.38 * tl_[..., None])
    res = rgba.copy()
    res[..., :3] = (np.clip(out, 0, 1) * 255).astype(np.uint8)
    return res


TREAT = {
    None: lambda f, i: f,
    "mono": lambda f, i: _mono(f, seed=i),
    "stone": lambda f, i: _stone(f, 1),
    "stonehand": lambda f, i: _stone(f, 1, tips=hand_tips()),
    "metal": lambda f, i: _metal(f, 2),
    "lineart": lambda f, i: fx.lineart(f, ink=(0.35, 0.35, 0.37), fill=(0.985, 0.985, 0.985)),
    "pencil": lambda f, i: fx.lineart(f, sigma=1.6, ink=(0.30, 0.29, 0.28), width=2),
    "graphite": lambda f, i: fx.lineart(f, sigma=2.2, ink=(0.18, 0.17, 0.16), width=3),
    "thermal": lambda f, i: _thermal(f),
    "thermal2": lambda f, i: _thermal(f, cv2.COLORMAP_HSV, 60),
    "green": lambda f, i: fx.tint(f, rgb("6BE36B"), 0.9),
    "purple": lambda f, i: _thermal(f, cv2.COLORMAP_PLASMA),
    "navy": lambda f, i: _flat(f, rgb("1C2340"), 0.75),
    "mint": lambda f, i: _bright_tint(f, MINT),
    "mint2": lambda f, i: _bright_tint(f, MINT2),
    "cyan": lambda f, i: _bright_tint(f, ECHO_CY),
    "cyan2": lambda f, i: _bright_tint(f, ECHO_CY2),
    "lift": lambda f, i: _lift(f, 0.62),
    "white": lambda f, i: _silhouette(f),
    "dilate": lambda f, i: np.dstack([f[..., :3], cv2.dilate(f[..., 3], np.ones((25, 25), np.uint8))]),
    "olive": lambda f, i: fx.tint(f, rgb("8A8F5A"), 0.55),
    "steel": lambda f, i: _steel(f, i),
}
_imgs = {}


def img(name, i=0, treat=None):
    """skia image of cut `name` frame i with a treatment (cached)."""
    key = (name, i, treat)
    im = _imgs.get(key)
    if im is None:
        c = cut(name)
        f = c.frames[min(i, len(c) - 1)]
        im = _imgs[key] = to_image(TREAT[treat](f, i))
    return im


def put(cv, name, cx, cy, h, i=0, treat=None, anchor=(0.5, 0.5), alpha=1.0, rot=0.0, flip=False, cfilter=None,
        blur=0.0, w=None):
    """draw cut-out `name` with its anchor at (cx, cy); h = height as a fraction of frame height (or w = width)."""
    im = img(name, i, treat)
    s = (w * W / im.width()) if w is not None else (h * H / im.height())
    draw_image(cv, im, cx, cy, s, rot, alpha, anchor, cfilter=cfilter, blur=blur, flip=flip)
    return s


def img_point(name, px, py, cx, cy, h, i=0, treat=None, rot=0.0, flip=False, anchor=(0.5, 0.5), w=None):
    """where pixel (px, py) of cut-out `name` lands when drawn with put(...) using the same arguments."""
    im = img(name, i, treat)
    iw, ih = im.width(), im.height()
    s = (w * W / iw) if w is not None else (h * H / ih)
    x = (px - anchor[0] * iw) * s * (-1 if flip else 1)
    y = (py - anchor[1] * ih) * s
    r = math.radians(rot)
    return cx + x * math.cos(r) - y * math.sin(r), cy + x * math.sin(r) + y * math.cos(r)


def hand_tips():
    """three extremities of the hand cut-out (image px): the bloody chunk, the index fingertip, the knuckles."""
    f = cut("hand").frames[0]
    a = f[..., 3] > 128
    ys, xs = np.where(a)
    hh, ww = a.shape
    up = ys < hh * 0.5
    j = np.argmin(xs[up])
    i = np.argmin(ys)
    rr = xs > ww * 0.55
    k = np.argmin(ys[rr])
    return [(xs[up][j], ys[up][j]), (xs[i], ys[i]), (xs[rr][k], ys[rr][k])]


def nframe(name, lt, fps=12, loop=False):
    return cut(name).at(lt, hold_fps=fps, loop=loop)


# ------------------------------------------------------------------------------------------------ backgrounds

_bg = {}


def paper_bg(dark=False):
    key = ("paper", dark)
    if key not in _bg:
        rng = np.random.default_rng(3)
        base = np.array((208, 206, 203) if dark else (226, 225, 224), np.float32)
        n = rng.standard_normal((H, W)).astype(np.float32)
        fib = cv2.GaussianBlur(n, (0, 0), 0.8) * (4.5 if dark else 2.0)
        streak = cv2.GaussianBlur(rng.standard_normal((H, W)).astype(np.float32), (0, 0), sigmaX=9, sigmaY=1.2) * 3
        im = base[None, None] + (fib + streak)[..., None]
        im[:int(H * 0.015)] += 7
        im[:, :int(W * 0.012)] += 7
        _bg[key] = to_image(np.clip(im, 0, 255).astype(np.uint8))
    return _bg[key]


def relief_bg():
    """embossed white-on-white city relief (from an official PV background plate)."""
    if "relief" not in _bg:
        f = read_frames(f"{SRC}/pv_main_2022/video.mp4", 16.5, 16.55)[0]
        g = cv2.cvtColor(f, cv2.COLOR_RGB2GRAY).astype(np.float32)
        g = cv2.GaussianBlur(g, (0, 0), 1.2)
        k = np.array([[-2, -1, 0], [-1, 0, 1], [0, 1, 2]], np.float32)
        e = cv2.filter2D(g, -1, k)
        e = np.clip(e / (np.percentile(np.abs(e), 98) + 1e-3), -1, 1)
        v = 246 + e * 7
        _bg["relief"] = to_image(np.dstack([v, v, v]).clip(0, 255).astype(np.uint8))
    return _bg["relief"]


def full_bg(cv, im, alpha=1.0):
    draw_image(cv, im, 0, 0, W / im.width(), anchor=(0, 0), alpha=alpha)


def fill(cv, col, a=1.0):
    cv.drawRect(skia.Rect(0, 0, W, H), paint(col, a))


# ------------------------------------------------------------------------------------------------ props

def screw(cv, x, y, d=34.0, rot=0.0):
    """photographic-looking Phillips screw head (grey dome, cross recess, soft highlight)."""
    r = d / 2
    body, shade = rgb("A69E98"), rgb("5E514B")
    hi = (0.93, 0.92, 0.90)
    sh = skia.GradientShader.MakeRadial(skia.Point(x - r * 0.35, y - r * 0.40), r * 1.45,
                                        [cint(hi), cint(body), cint(shade)], [0.0, 0.45, 1.0])
    p = skia.Paint(AntiAlias=True)
    p.setShader(sh)
    cv.drawCircle(x, y, r, p)
    cv.drawCircle(x, y, r, paint(shade, 0.8, stroke=1.2))
    cv.save()
    cv.translate(x, y)
    cv.rotate(rot)
    for a in (0, 90):
        cv.save()
        cv.rotate(a)
        cv.drawLine(-r * 0.55, 0, r * 0.55, 0, paint((0.22, 0.19, 0.17), 0.9, stroke=r * 0.22))
        cv.drawLine(-r * 0.5, -r * 0.08, r * 0.5, -r * 0.08, paint((1, 1, 1), 0.35, stroke=r * 0.07))
        cv.restore()
    cv.restore()


def crayon(cv, path, p1, col, hi, width=13.0, seed=0, p0=0.0, a=1.0):
    """ragged crayon / dry-brush stroke (darker core, lighter speckled rim), written on to fraction p1."""
    if p1 <= p0:
        return
    brush(cv, path, width * 1.25, hi, p0, p1, a=a * 0.55, bristles=7, seed=seed + 7, dry=0.55, taper=0.03, wobble=0.18)
    brush(cv, path, width, col, p0, p1, a=a, bristles=9, seed=seed, dry=0.32, taper=0.03, wobble=0.12)


def red_dots(cv, path, p1, width=13.0, seed=0, a=1.0):
    """the dotted red stroke: a broken chain of irregular blobs."""
    L = path_length(path)
    if p1 <= 0 or L <= 0:
        return
    pts, tans = sample_path(path, 0, p1 * L, step=width * 1.5)
    rng = np.random.default_rng(seed)
    for (x, y), (tx, ty) in zip(pts, tans):
        ln = width * rng.uniform(0.9, 1.6)
        ang = math.degrees(math.atan2(ty, tx))
        cv.save()
        cv.translate(float(x), float(y))
        cv.rotate(ang)
        cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(-ln / 2, -width / 2, ln / 2, width / 2), width / 2, width / 2),
                     paint(RED, a * rng.uniform(0.85, 1.0)))
        cv.drawCircle(float(rng.uniform(-ln / 3, ln / 3)), float(-width * 0.2), width * 0.18, paint(RED_HI, 0.6 * a))
        cv.restore()


def bowling_ball(cv, x, y, d, rot=0.0, a=1.0):
    r = d / 2
    sh = skia.GradientShader.MakeRadial(skia.Point(x - r * 0.35, y - r * 0.35), r * 1.5,
                                        [cint(rgb("5A6CB8"), a), cint(rgb("1B2259"), a), cint(rgb("070A1E"), a)],
                                        [0.0, 0.5, 1.0])
    p = skia.Paint(AntiAlias=True)
    p.setShader(sh)
    cv.drawCircle(x, y, r, p)
    for k in range(3):
        ang = math.radians(rot + [0, 28, 52][k])
        hx, hy = x + math.cos(ang) * r * 0.35, y + math.sin(ang) * r * 0.35 - r * 0.15
        cv.drawCircle(hx, hy, r * 0.09, paint((0.02, 0.02, 0.05), a))
    cv.drawCircle(x - r * 0.4, y - r * 0.42, r * 0.16, paint((1, 1, 1), 0.55 * a, blur=r * 0.08))


def chainsaw_bar(cv, x0, y, x1, thick, a=1.0, phase=0.0):
    """horizontal chainsaw guide bar: dark steel plate with a running tooth chain round its edge."""
    r = thick / 2
    rr = skia.RRect.MakeRectXY(skia.Rect(x0, y - r, x1, y + r), r, r)
    g = skia.GradientShader.MakeLinear([skia.Point(0, y - r), skia.Point(0, y + r)],
                                       [cint((0.42, 0.43, 0.46), a), cint((0.16, 0.16, 0.18), a), cint((0.30, 0.30, 0.33), a)],
                                       [0, 0.55, 1])
    p = skia.Paint(AntiAlias=True)
    p.setShader(g)
    cv.drawRRect(rr, p)
    n = int((x1 - x0) / (thick * 0.55))
    for k in range(n):
        u = (k + phase % 1.0) / n
        x = x0 + r + (x1 - x0 - 2 * r) * u
        tooth = skia.Path()
        tooth.moveTo(x - thick * 0.16, y - r)
        tooth.lineTo(x + thick * 0.12, y - r - thick * 0.32)
        tooth.lineTo(x + thick * 0.18, y - r)
        tooth.close()
        cv.drawPath(tooth, paint((0.12, 0.12, 0.13), a))
        tooth2 = skia.Path()
        tooth2.moveTo(x + thick * 0.16, y + r)
        tooth2.lineTo(x - thick * 0.12, y + r + thick * 0.32)
        tooth2.lineTo(x - thick * 0.18, y + r)
        tooth2.close()
        cv.drawPath(tooth2, paint((0.12, 0.12, 0.13), a))
    cv.drawLine(x0 + r, y - r * 0.35, x1 - r, y - r * 0.35, paint((1, 1, 1), 0.18 * a, stroke=max(1.0, thick * 0.06)))


def sparks(cv, x, y, t, n=14, size=120.0, seed=0, col=rgb("FFD23A")):
    rng = np.random.default_rng(seed + int(t * 12))
    for _ in range(n):
        ang = rng.uniform(0, 2 * math.pi)
        r0 = rng.uniform(0, size * 0.25)
        r1 = r0 + rng.uniform(size * 0.3, size)
        cv.drawLine(x + math.cos(ang) * r0, y + math.sin(ang) * r0, x + math.cos(ang) * r1, y + math.sin(ang) * r1,
                    paint(col, rng.uniform(0.6, 1.0), stroke=rng.uniform(2, 5)))
    cv.drawCircle(x, y, size * 0.12, paint((1, 0.97, 0.75), 0.9, blur=size * 0.08))


def question_marks(cv, n, t, seed=0):
    rng = np.random.default_rng(seed)
    cols = [rgb("4FBDAD"), rgb("89EADE")] + [rgb("C852B5"), rgb("E482E0"), rgb("6BCF5A"), rgb("8A4FD8")]
    for k in range(n):
        dx, dy = rng.uniform(-70, 70), rng.uniform(-60, 40)
        size = 41 * rng.uniform(0.6, 1.5)
        col = cols[k % 2] if k < 4 else cols[int(rng.integers(0, len(cols)))]
        text(cv, "?", 960 + dx * 1.9, 550 + dy * 1.9, size, FONT_LYR, col)


def hey(cv, x, y, t):
    jx, jy = (np.random.default_rng(int(t * 24)).uniform(-4, 4, 2))
    cv.save()
    cv.translate(x + jx, y + jy)
    cv.rotate(15)
    text(cv, "HEY!", 0, 0, H * 0.05 * 1.25, FONT_HEY, NAVY)
    cv.restore()


# ------------------------------------------------------------------------------------------------ post effects

def dir_blur(rgb_, dx, dy):
    """directional motion blur of the whole frame along (dx, dy) pixels (cheap: done at quarter size)."""
    L = math.hypot(dx, dy)
    if L < 2:
        return rgb_
    sm = cv2.resize(rgb_, (W // 4, H // 4), interpolation=cv2.INTER_AREA).astype(np.float32)
    n = max(3, int(L / 4))
    k = np.zeros((n * 2 + 1, n * 2 + 1), np.float32)
    ux, uy = dx / L, dy / L
    for i in range(-n, n + 1):
        k[int(round(n + uy * i)), int(round(n + ux * i))] = 1
    k /= k.sum()
    b = cv2.filter2D(sm, -1, k, borderType=cv2.BORDER_REPLICATE)
    return cv2.resize(b, (W, H), interpolation=cv2.INTER_LINEAR).clip(0, 255).astype(np.uint8)


def mosaic(rgb_, block):
    b = max(1, int(block))
    sm = cv2.resize(rgb_, (max(1, W // b), max(1, H // b)), interpolation=cv2.INTER_AREA)
    return cv2.resize(sm, (W, H), interpolation=cv2.INTER_NEAREST)


def recolor(rgb_, col, amount=1.0):
    g = cv2.cvtColor(rgb_, cv2.COLOR_RGB2GRAY).astype(np.float32)[..., None] / 255
    c = np.array(col, np.float32)[None, None]
    out = np.where(g < 0.5, 2 * g * c, 1 - 2 * (1 - g) * (1 - c))
    return (rgb_ * (1 - amount) + out * 255 * amount).clip(0, 255).astype(np.uint8)


# ================================================================================================= SCENES
# times are edit seconds; reference cadence: motion on twos (12 fps), flashes at full rate.

DUO_H = 0.32          # seated duo height (fraction of H)
DUO_GAP = 0.45        # how much of the bench gap between them to close
DUO_CX, DUO_BOT = 0.485 * W, 0.85 * H
WORDS = [("still", 0.25, 0.50), ("fight", 0.55, 0.80), ("and", 0.85, 1.00), ("i", 1.05, 1.20),
         ("don’t", 1.25, 1.50), ("know", 1.55, 1.80), ("why", 1.85, 2.60)]


def duo_halves():
    """split the seated duo into its two characters (left: Denji, right: Power)."""
    if "duo_halves" not in _bg:
        f = cut("duo").frames[0]
        a = f[..., 3] > 30
        cols = a.sum(0)
        w = f.shape[1]
        mid = int(np.argmin(cols[int(w * 0.3):int(w * 0.7)]) + w * 0.3)
        left, right = f.copy(), f.copy()
        left[:, mid:, 3] = 0
        right[:, :mid, 3] = 0
        _bg["duo_halves"] = (left, right, mid)
    return _bg["duo_halves"]


def draw_duo(cv, treat=None, alpha=1.0, left=True, right=True, dissolve=None):
    f = cut("duo").frames[0]
    s = DUO_H * H / f.shape[0]
    x0 = DUO_CX - f.shape[1] * s / 2
    y0 = DUO_BOT - f.shape[0] * s
    L, R, mid = duo_halves()
    shift = f.shape[1] * s * 0.18 * DUO_GAP           # slide the two halves toward each other
    x0r, x0 = x0 - shift, x0 + shift
    if right:
        draw_image(cv, _cached_img(("duoR", treat), lambda: TREAT[treat](R, 0)), x0r, y0, s, anchor=(0, 0), alpha=alpha)
    if left:
        if dissolve is None:
            draw_image(cv, _cached_img(("duoL", treat), lambda: TREAT[treat](L, 0)), x0, y0, s, anchor=(0, 0), alpha=alpha)
        else:
            draw_image(cv, _cached_img(("duoLd", dissolve), lambda: pixel_dissolve(L, dissolve)), x0, y0, s, anchor=(0, 0))


def _cached_img(key, fn):
    im = _imgs.get(key)
    if im is None:
        im = _imgs[key] = to_image(fn())
    return im


def pixel_dissolve(rgba, k, block=20, seed=4):
    """blocky disintegration: k=0 intact .. 1 gone; dissolving blocks turn mint before vanishing."""
    out = rgba.copy()
    h, w = out.shape[:2]
    rng = np.random.default_rng(seed)
    nb_y, nb_x = h // block + 1, w // block + 1
    order = rng.random((nb_y, nb_x)) + np.linspace(0, 0.6, nb_x)[None, :]   # sweeps across
    order /= order.max()
    for by in range(nb_y):
        for bx in range(nb_x):
            o = order[by, bx]
            ys, xs = slice(by * block, (by + 1) * block), slice(bx * block, (bx + 1) * block)
            if o < k - 0.15:
                out[ys, xs, 3] = 0
            elif o < k:
                a = out[ys, xs, 3]
                if a.size and a.max() > 0:
                    out[ys, xs, :3] = (np.array(BLOCK) * 255).astype(np.uint8)
                    out[ys, xs, 3] = 255 if a.mean() > 40 else 0
    return out


@tl.scene(0.0, 0.25)
def s01_sketch(c):
    cv = c.cv
    full_bg(cv, paper_bg())
    k = clamp01(c.lt / 0.20)
    f = cut("duo").frames[0]
    s = DUO_H * H / f.shape[0]
    # charcoal particles condensing into the sketch
    rng = np.random.default_rng(int(c.lt * 24))
    n = int(900 * (1 - k))
    for _ in range(n):
        x = DUO_CX + rng.normal(0, 260 * (1 - k) + 40)
        y = DUO_BOT - DUO_H * H * 0.5 + rng.normal(0, 200 * (1 - k) + 30)
        cv.drawCircle(float(x), float(y), float(rng.uniform(0.8, 2.6)), paint((0.25, 0.24, 0.23), rng.uniform(0.2, 0.7)))
    layer(cv, alpha=smooth(k))
    draw_duo(cv, treat="pencil")
    cv.restore()


@tl.scene(0.25, 2.65)
def s02_duo(c):
    cv = c.cv
    t = c.t
    if t < 2.25:
        draw_duo(cv)
    else:
        k = [0.5, 0.85, 1.01][min(2, int((t - 2.25) / 0.1))]
        draw_duo(cv, dissolve=round(k, 2))
    for w_, a, b in WORDS:
        if a <= t < b:
            text(cv, w_, 960, 550, 41, FONT_LYR, GREYTXT)
    if t >= 2.15:
        n = 4 if t < 2.35 else 8 if t < 2.45 else 12
        question_marks(cv, n, t, seed=9)


@tl.scene(2.65, 3.45)
def s04_hand_falls(c):
    cv = c.cv
    lt = c.lt
    yk = out_cubic(clamp01(step(lt) / 0.25))
    sway = math.sin(step(lt) * 7) * 6 * (1 - clamp01(lt / 0.8))
    hx = W * 0.44
    wrist_y = mix(-H * 0.5, H * 0.66, yk)
    # bundle of thin coloured wires from the top edge down to the wrist
    rng = np.random.default_rng(2)
    wcols = [rgb("E8893A"), rgb("3C6FD8"), rgb("C83A3A"), rgb("7C4AC9"), rgb("2A9D8F")]
    for k in range(15):
        x0 = hx + rng.uniform(-14, 14)
        x1 = hx + sway + rng.uniform(-12, 12)
        line(cv, polyline([(x0, -10), (mix(x0, x1, 0.5) + rng.uniform(-5, 5), wrist_y * 0.5), (x1, wrist_y + 10)]),
             rng.uniform(2, 4), wcols[k % len(wcols)], 0.95)
    # the stone hand hangs fingers-down from its wrist
    put(cv, "hand", hx + sway, wrist_y, 0.30, treat="stonehand", anchor=(0.80, 0.97), rot=165 + sway * 0.5)


@tl.post(2.65, 3.06)
def p04(rgb_, c):
    lt = c.lt
    if lt < 0.10:
        return dir_blur(rgb_, 0, 180)
    if lt < 0.30:
        return mosaic(rgb_, 38)
    if lt < 0.40:
        return mosaic(rgb_, 14)
    return rgb_


# hand with three strokes to screws (3.45-5.25)
HAND_C = (W * 0.52, H * 0.62)
HAND_H = 0.60
PINS = [(0.23 * W, 0.17 * H), (0.50 * W, 0.05 * H), (0.79 * W, 0.22 * H)]
STROKE_STYLE = [("dots", None, None), ("crayon", CYAN, CYAN_HI), ("crayon", TEAL, TEAL_HI)]


def hand_pose(rot, scale, jitter=(0, 0), cx=None, cy=None):
    cx = (HAND_C[0] if cx is None else cx) + jitter[0]
    cy = (HAND_C[1] if cy is None else cy) + jitter[1]
    return dict(cx=cx, cy=cy, h=HAND_H * scale, rot=rot)


def draw_hand_with_strokes(cv, treat="stonehand", strokes_p=1.0, rot=0.0, scale=1.0, jitter=(0, 0), screws=True, hand=True,
                           pins=None, straight=0.0, cx=None, cy=None):
    pose = hand_pose(rot, scale, jitter, cx, cy)
    pins = pins or PINS
    if hand:
        put(cv, "hand", pose["cx"], pose["cy"], pose["h"], treat=treat, rot=pose["rot"])
    for k, ((px, py), pin_) in enumerate(zip(hand_tips(), pins)):
        x0, y0 = img_point("hand", px, py, pose["cx"], pose["cy"], pose["h"], treat=treat, rot=pose["rot"])
        bend = (1 - straight) * (0.35 if k != 1 else 0.15)
        mx, my = (x0 + pin_[0]) / 2, (y0 + pin_[1]) / 2
        nx, ny = -(pin_[1] - y0), (pin_[0] - x0)
        sgn = -1 if k == 0 else 1
        c1 = (mx + nx * bend * sgn, my + ny * bend * sgn)
        pth = bezier((x0, y0), c1, c1, pin_)
        kind, col, hi = STROKE_STYLE[k]
        if kind == "dots":
            red_dots(cv, pth, strokes_p, 12 * max(scale, 0.5) + 1, seed=3)
        else:
            crayon(cv, pth, strokes_p, col, hi, 13 * max(scale, 0.5) + 1, seed=k)
        if screws and strokes_p > 0.98:
            screw(cv, pin_[0], pin_[1], 34 * max(scale, 0.4), rot=20 * k)


@tl.scene(3.45, 4.30)
def s05_hand_strokes(c):
    lt = step(c.lt)
    rk = out_cubic(clamp01(lt / 0.5))
    draw_hand_with_strokes(c.cv, strokes_p=out_cubic(clamp01((c.lt - 0.10) / 0.30)), rot=35 * rk,
                           scale=0.92 + 0.08 * rk)


@tl.scene(4.30, 4.75)
def s06_recolour(c):
    t = c.t
    treat = "thermal" if t < 4.35 else "green" if t < 4.50 else "purple" if t < 4.60 else "stonehand"
    j = [(0, 0), (8, -5), (-6, 4), (5, 6), (0, 0)][min(4, int(c.lt / 0.1))]
    draw_hand_with_strokes(c.cv, treat=treat, jitter=j, rot=35 + j[0] * 0.5)


@tl.scene(4.75, 5.25)
def s07_strobe(c):
    cv = c.cv
    k = int(round(c.lt * 24))
    mode = ["pencil", "stonehand", "lineart", "stonehand", "pencil", "stonehand", "graphite", "stonehand", "lineart",
            "stonehand", "pencil", None][min(k, 11)]
    if c.t >= 5.20:
        return
    if mode in ("pencil", "graphite"):
        full_bg(cv, paper_bg(dark=mode == "graphite"))
    draw_hand_with_strokes(cv, treat=mode, rot=35 + (10 if k >= 6 else 0))


@tl.scene(5.25, 5.45)
def s08_snap_zoom(c):
    k = in_cubic(clamp01(c.lt / 0.15))
    sc = mix(1.0, 0.06, k)
    cx, cy = mix(HAND_C[0], W * 0.5, k), mix(HAND_C[1], H * 0.55, k)
    draw_hand_with_strokes(c.cv, scale=sc, cx=cx, cy=cy, straight=k, screws=k < 0.5, rot=35,
                           pins=[(mix(px, cx, k * 0.0), mix(py, cy, k * 0.0)) for px, py in PINS])


# puppet (5.45-7.85)
PUP_H = 0.36
PUP_C = (W * 0.50, H * 0.72)
P_PINS = [(0.41 * W, 0.03 * H), (0.27 * W, 0.40 * H), (0.70 * W, 0.44 * H)]


def puppet_anchor_points():
    """head / left hand / right hand of the puppet cut-out, in frame pixels."""
    f = cut("puppet").frames[0]
    s = PUP_H * H / f.shape[0]
    a = f[..., 3] > 100
    ys, xs = np.where(a)
    head_y = ys.min()
    head_x = xs[ys < head_y + 30].mean()
    row = int(f.shape[0] * 0.42)
    band = np.where(a[row - 40:row + 40].any(0))[0]
    lx, rx = band.min(), band.max()
    x0 = PUP_C[0] - f.shape[1] * s / 2
    y0 = PUP_C[1] - f.shape[0] * s / 2
    return [(x0 + head_x * s, y0 + head_y * s), (x0 + lx * s, y0 + row * s), (x0 + rx * s, y0 + row * s)]


@tl.scene(5.45, 6.55)
def s09_puppet(c):
    cv = c.cv
    pts = puppet_anchor_points()
    put(cv, "puppet", PUP_C[0], PUP_C[1], PUP_H, treat="mono")
    for k, (pa, pp) in enumerate(zip(pts, P_PINS)):
        pth = polyline([pa, pp]) if k != 1 else bezier(pa, pa, pp, pp)
        if k == 1:
            red_dots(cv, pth, 1.0, 12, seed=8)
        else:
            crayon(cv, pth, 1.0, CYAN if k == 0 else TEAL, CYAN_HI if k == 0 else TEAL_HI, 13, seed=k + 20)
        screw(cv, pp[0], pp[1], 34, rot=15 * k)


@tl.scene(6.55, 7.85)
def s10_snapped(c):
    cv = c.cv
    lt = step(c.lt)
    # the severed strings hang from their pins and swing (damped pendulum)
    for k, pp in enumerate(P_PINS):
        L = [0.45, 0.30, 0.28][k] * H
        ang = math.radians(15 * math.exp(-lt / 0.35) * math.cos(lt * 14 + k)) + [0.10, -0.35, 0.30][k] * math.exp(-lt / 0.2)
        end = (pp[0] + math.sin(ang) * L, pp[1] + math.cos(ang) * L)
        pth = polyline([pp, end])
        if k == 1:
            red_dots(cv, pth, 1.0, 12, seed=8)
        else:
            crayon(cv, pth, 1.0, CYAN if k == 0 else TEAL, CYAN_HI if k == 0 else TEAL_HI, 13, seed=k + 20)
        screw(cv, pp[0], pp[1], 34, rot=15 * k)
    if c.t < 6.65:
        put(cv, "puppet", PUP_C[0], PUP_C[1] + (c.t - 6.55) * 900, PUP_H, treat="mono")
    else:
        # Denji, dropped onto all fours, still on Makima's leash
        put(cv, "leash", W * 0.5, H * 0.98, 0.25, i=0, treat="mono", anchor=(0.5, 1.0))


@tl.post(7.85, 8.05)
def p11_whip(rgb_, c):
    return dir_blur(rgb_, 0, 420)


@tl.scene(7.85, 8.05)
def s11_whip(c):
    if c.t >= 7.95:
        full_bg(c.cv, relief_bg())
        chainsaw_bar(c.cv, W * 0.085, H * (0.91 - (8.05 - c.t) * 4), W * 0.915, H * 0.03)
    else:
        put(c.cv, "leash", W * 0.5, H * 0.98 - (c.t - 7.85) * 3000, 0.25, i=0, treat="mono", anchor=(0.5, 1.0))


@tl.scene(8.05, 8.65)
def s12_beam(c):
    cv = c.cv
    t = c.t
    plain = any(abs(t - x) < 0.026 for x in (8.10, 8.25, 8.50))
    if not plain:
        full_bg(cv, relief_bg())
    flick = 0.75 + 0.25 * (int(t * 24) % 2)
    chainsaw_bar(cv, W * 0.085, H * 0.91, W * 0.915, H * 0.03, a=flick, phase=t * 6)
    # little Denji (kid) hangs from the bar by a red string, a cyan string hooks the bar
    tw = math.sin(t * 40) * 3
    line(cv, polyline([(W * 0.5, H * 0.895), (W * 0.5 + tw, H * 0.93)]), 3, HERO)
    put(cv, "kid", W * 0.5 + tw, H * 0.93, 0.07, treat="mono", anchor=(0.5, 0.0))
    line(cv, polyline([(W * 0.36, H * 0.895), (W * 0.33, H * 0.80)]), 3, CYAN)
    line(cv, polyline([(W * 0.64, H * 0.895), (W * 0.67, H * 0.82)]), 3, RED)


# collage mask (8.65-11.95)
MASK_H = 0.78
MASK_C = (W * 0.50, H * 0.52)


def draw_mask(cv, y_off=0.0, hands_in=0.0, hands_up=1.0, alpha=1.0):
    put(cv, "head", MASK_C[0], MASK_C[1] + y_off, MASK_H, treat="metal", alpha=alpha)
    # blood-red paint smears on the face
    for k, (x, y, ang) in enumerate([(-0.10, 0.18, 70), (0.12, 0.22, 110)]):
        cx, cy = MASK_C[0] + x * H, MASK_C[1] + y * H + y_off
        for j in range(3):
            p = bezier((cx + j * 14, cy - 60), (cx + j * 14 + 10, cy - 10), (cx + j * 10 - 8, cy + 50), (cx + j * 9, cy + 110))
            ribbon(cv, p, 14, rgb("7E0B08"), 0, 1, a=0.85 * alpha, seed=k * 10 + j, rough=0.35)
    # two stone hands rising from the bottom corners, cupping the face
    up = (1 - hands_up) * H * 0.6
    dx = hands_in * W * 0.06
    for side in (-1, 1):
        put(cv, "hand", MASK_C[0] + side * (W * 0.36 - dx), H * 1.10 + up, 0.58, treat="stonehand",
            anchor=(0.80, 0.98), rot=side * (24 - hands_in * 10), flip=side < 0, alpha=alpha)


@tl.scene(8.65, 8.90)
def s13_mask_drop(c):
    full_bg(c.cv, relief_bg())
    k = out_cubic(clamp01(step(c.lt) / 0.15))
    chainsaw_bar(c.cv, W * 0.085, H * 0.91 + k * H * 0.3, W * 0.915, H * 0.03)
    draw_mask(c.cv, y_off=mix(-H * 1.1, 0, k), hands_up=k)


@tl.post(8.65, 8.74)
def p13(rgb_, c):
    return dir_blur(rgb_, 0, 260 * (1 - c.u * 0.6))


@tl.scene(8.90, 10.65)
def s14_mask_hold(c):
    full_bg(c.cv, relief_bg())
    lt = step(c.lt)
    draw_mask(c.cv, hands_in=smooth(clamp01((c.t - 9.40) / 0.45)))


# HUD: chrome ring, Makima-ring circles round the eye, three clock hands
EYE = (MASK_C[0] - H * 0.02, MASK_C[1] - H * 0.06)


def chrome_ring(cv, cx, cy, R, band, a=1.0):
    p = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=band)
    sh = skia.GradientShader.MakeSweep(cx, cy, [cint((0.95, 0.95, 0.97), a), cint((0.35, 0.36, 0.40), a),
                                                cint((0.85, 0.86, 0.90), a), cint((0.15, 0.15, 0.18), a),
                                                cint((0.92, 0.92, 0.95), a), cint((0.40, 0.40, 0.45), a),
                                                cint((0.95, 0.95, 0.97), a)])
    p.setShader(sh)
    cv.drawCircle(cx, cy, R, p)
    cv.drawCircle(cx, cy, R - band / 2, paint((0.1, 0.1, 0.12), 0.6 * a, stroke=1.5))
    cv.drawCircle(cx, cy, R + band / 2, paint((0.1, 0.1, 0.12), 0.6 * a, stroke=1.5))


def clock_hand(cv, cx, cy, length, ang, col, width):
    x1, y1 = cx + math.cos(math.radians(ang)) * length, cy + math.sin(math.radians(ang)) * length
    cv.drawLine(cx, cy, x1, y1, paint(col, 1.0, stroke=width))
    cap = skia.RRect.MakeRectXY(skia.Rect(-width * 1.6, -width * 0.8 * 1.5, width * 1.6, width * 0.8 * 1.5), width, width)
    cv.save()
    cv.translate(x1, y1)
    cv.rotate(ang)
    cv.drawRRect(cap, paint(col))
    cv.restore()


@tl.scene(10.65, 11.95)
def s15_hud(c):
    cv = c.cv
    full_bg(cv, relief_bg())
    draw_mask(cv, hands_in=1.0)
    t = c.t
    if t < 10.80:
        cv.drawCircle(EYE[0], EYE[1], 46, paint(INK, 0.9, stroke=3))
        brush(cv, bezier((EYE[0] - 60, EYE[1] - 10), (EYE[0] - 20, EYE[1] - 70), (EYE[0] + 40, EYE[1] + 60), (EYE[0] + 70, EYE[1])),
              6, HERO, bristles=3, seed=4)
        return
    k = [0.4, 0.7, 1.0][min(2, int((t - 10.80) / 0.05))]
    amber = rgb("E2A93B")
    rings(cv, EYE[0], EYE[1], [r * k for r in (40, 70, 100, 135, 165)], 3.5, amber, p=1.0)
    rings(cv, EYE[0], EYE[1], [r * k for r in (52, 118)], 2.0, CYAN, p=1.0)
    chrome_ring(cv, W * 0.5, H * 0.5, H * 0.475 * k, H * 0.04)
    ang0 = -90 + 8 * int((t - 10.85) / 0.1)
    clock_hand(cv, EYE[0], EYE[1], 230 * k, ang0, HERO, 6)
    clock_hand(cv, EYE[0], EYE[1], 170 * k, ang0 + 120, NAVY, 5)
    clock_hand(cv, EYE[0], EYE[1], 300 * k, ang0 + 220, TEAL, 4)


# disc -> ball -> Aki bowling (11.95-13.45)
_disc = {}


def disc_image():
    if "disc" not in _disc:
        fr = core.Frame()
        cv = fr.clear()
        full_bg(cv, relief_bg())
        draw_mask(cv, hands_in=1.0)
        a = fr.array()
        cx, cy, R = int(W * 0.5), int(H * 0.48), int(H * 0.40)
        crop = a[cy - R:cy + R, cx - R:cx + R]
        m = np.zeros(crop.shape[:2], np.uint8)
        cv2.circle(m, (R, R), R - 2, 255, -1, cv2.LINE_AA)
        rim = cv2.GaussianBlur((m > 0).astype(np.float32), (0, 0), R * 0.08)
        crop = (crop * (0.55 + 0.45 * rim[..., None])).astype(np.uint8)
        _disc["disc"] = to_image(np.dstack([crop, m]))
    return _disc["disc"]


@tl.scene(11.95, 12.65)
def s16_disc(c):
    t = c.t
    d = 0.71 if t < 12.25 else 0.41 if t < 12.45 else 0.71 if t < 12.55 else 0.22
    cx, cy = W * 0.46, H * 0.46
    if t >= 12.25:
        put(c.cv, "bowl", W * 0.36, H * 0.32, 0.31, treat="olive")
    im = disc_image()
    draw_image(c.cv, im, cx, cy, d * H / im.height())


@tl.scene(12.65, 13.45)
def s17_bowl(c):
    cv = c.cv
    t = c.t
    if t < 13.25:
        put(cv, "bowl", W * 0.36, H * 0.32, 0.31, treat="olive")
        bowling_ball(cv, W * 0.36 + H * 0.12, H * 0.32 + H * 0.06, H * 0.026 * 1.6)
        return
    k = (t - 13.25) / 0.2
    put(cv, "bowl", W * 0.36 - k * 500, H * 0.32 - k * 300, 0.31, treat="olive", alpha=1 - k)
    bowling_ball(cv, W * 0.42 + k * 1400, H * 0.38 + k * 900, H * 0.05)


@tl.post(13.20, 13.25)
def p18_matte(rgb_, c):
    fr = core.Frame()
    cv = fr.clear((0.012, 0.012, 0.012))
    put(cv, "bowl", W * 0.36, H * 0.32, 0.31, treat="white")
    return fr.array()


@tl.post(13.25, 13.45)
def p19_whip(rgb_, c):
    return dir_blur(rgb_, 300, 190)


# flying duo over diagonal rain, chainsaw passes (13.45-17.60)
def rain(cv, t, cols, n=46, seed=3, angle=45, speed=1500, a=1.0, vertical=False):
    rng = np.random.default_rng(seed)
    ang = math.radians(90 if vertical else angle)
    dx, dy = math.cos(ang), math.sin(ang)
    diag = math.hypot(W, H)
    ts = step(t)
    for j in range(n):
        off = rng.uniform(-diag / 2, diag / 2)
        ln = rng.uniform(0.03, 0.10) * W if not vertical else rng.uniform(0.02, 0.20) * H
        base = rng.uniform(0, diag * 2)
        s = ((base + ts * speed * rng.uniform(0.7, 1.3)) % (diag * 2)) - diag
        cx, cy = W / 2 + dx * s - dy * off, H / 2 + dy * s + dx * off
        col = cols[j % len(cols)]
        cv.drawLine(cx, cy, cx - dx * ln, cy - dy * ln, paint(col, a * rng.uniform(0.45, 0.9), stroke=3.0 if not vertical else rng.uniform(3, 6), cap="butt"))


RAIN_COLS = [rgb("273150"), rgb("505D87"), rgb("A7B3ED"), rgb("A6E7F7"), rgb("638CD0"), HERO]
DUO_FLY = (W * 0.65, H * 0.58)


def flying_duo(cv, t, x=None, y=None, a=1.0):
    x = DUO_FLY[0] if x is None else x
    y = DUO_FLY[1] if y is None else y
    j = np.random.default_rng(int(step(t) * 12)).uniform(-5, 5, 2)
    # soft glow trails streaming up-left behind them: cyan, then blue, then red
    for k, col in enumerate([rgb("A6E7F7"), rgb("638CD0"), rgb("E86A5C")]):
        f = tint_filter(col, 1.0, keep_luma=False)
        for name, dx, dy, h, rot in (("puppet", -150, -90, 0.26, -30), ("power_fly", 60, 30, 0.30, 0)):
            put(cv, name, x + dx - (k + 1) * 70 + j[0], y + dy - (k + 1) * 42 + j[1], h, treat="navy", rot=rot,
                alpha=0.26 * a, cfilter=f, blur=12 + k * 8)
    put(cv, "puppet", x - 150 + j[0], y - 90 + j[1], 0.26, treat="navy", rot=-30, alpha=a)
    put(cv, "power_fly", x + 60 + j[0], y + 30 + j[1], 0.30, treat="navy", alpha=a)


def rails(cv, t):
    """two long black diagonal rail lines with a travelling coloured light segment."""
    for k, (off, col) in enumerate(((-260, rgb("55C0C9")), (-200, HERO))):
        p0 = (W * 0.02 + off, -40)
        p1 = (W * 0.02 + off + H * 1.25, H + 40)
        pth = polyline([p0, p1])
        line(cv, pth, 4, INK)
        u = (step(t) * 0.55 + k * 0.4) % 1.2 - 0.1
        line_part(cv, pth, max(0, u), min(1, u + 0.2), 5, col)


@tl.scene(13.45, 17.60)
def s20_flying(c):
    cv = c.cv
    t = c.t
    rain(cv, t, RAIN_COLS, n=90)
    rails(cv, t)
    flying_duo(cv, t)
    # a chainsaw passes bottom -> top-left every two beats (three blurred steps)
    for t0 in (13.80, 15.10, 16.40):
        if t0 <= t < t0 + 0.30:
            k = int((t - t0) / 0.1)
            x, y = [(W * 0.85, H * 1.05), (W * 0.45, H * 0.55), (W * 0.05, H * 0.05)][min(2, k)]
            put(cv, "saw", x, y, 0.42, rot=-30, blur=10, alpha=0.9)
    if t >= 17.55:
        put(cv, "pochita", W * 0.5, H * (1.4 - (t - 17.55) * 8), 0.69)


@tl.scene(17.60, 18.75)
def s21_pochita(c):
    cv = c.cv
    t = c.t
    line(cv, bezier((0, H * 0.05), (W * 0.2, H * 0.1), (W * 0.35, H * 0.25), (W * 0.47, H * 0.36)), 9, INK)
    put(cv, "pochita", W * 0.5, H * 0.66, 0.69)
    if t < 17.75:
        k = (t - 17.60) / 0.15
        cv.drawLine(DUO_FLY[0] * (1 - k) + W * 0.5 * k, DUO_FLY[1] * (1 - k) + H * 0.55 * k, W * 0.5, H * 0.55,
                    paint(rgb("638CD0"), 0.8, stroke=30, blur=6))
    if t >= 17.90:
        # Pochita's engine heats up: red glow + blinking emphasis dashes
        cv.drawCircle(W * 0.5, H * 0.66, H * 0.30, paint(HERO, 0.35, blur=40))
        if int(t * 12) % 2 == 0:
            for k in range(6):
                ang = math.radians(-150 + k * 24)
                r0, r1 = H * 0.42, H * 0.47
                cv.drawLine(W * 0.5 + math.cos(ang) * r0, H * 0.66 + math.sin(ang) * r0,
                            W * 0.5 + math.cos(ang) * r1, H * 0.66 + math.sin(ang) * r1, paint(HERO, 1.0, stroke=7))
    if 18.30 <= t < 18.47:
        hey(cv, W * 0.70, H * 0.30, t)


@tl.scene(18.75, 19.80)
def s22_line_up(c):
    cv = c.cv
    t = c.t
    lt = step(c.lt)
    if t < 18.85:
        # Pochita bursts open: blood petals
        put(cv, "pochita", W * 0.5, H * 0.66 + (t - 18.75) * 2500, 0.69)
        splatter(cv, W * 0.5, H * 0.55, 300, rgb("B5120A"), p=(t - 18.75) / 0.1, seed=12)
    sway = math.sin(lt * 5.5 + 0.6) * 140
    kink = clamp01((t - 19.70) / 0.1)
    top = mix(H * 0.6, -H * 0.1, out_cubic(clamp01(lt / 0.25)))
    pts = [(W * 0.5, H * 1.05), (W * 0.5 - sway, H * 0.72), (W * 0.5 + sway * 0.8, H * 0.38), (W * 0.5 + sway * 0.3 + kink * 90, top)]
    brush(cv, bezier(*pts), 9, HERO, bristles=3, dry=0.0, seed=1, taper=0.08)


@tl.scene(19.80, 20.00)
def s23_cone(c):
    cv = c.cv
    k = clamp01(c.lt / 0.1)
    s = mix(1.0, 2.5, out_cubic(k))
    cx, cy = W * 0.52, H * 0.50
    if c.t >= 19.90:
        put(cv, "arm", W * 0.60, H * 0.55, 1.05, i=0, alpha=1.0)
    # the cord becomes the chainsaw bar, pointing at camera
    path = skia.Path()
    path.moveTo(cx - 60 * s, cy - 30 * s)
    path.lineTo(cx + 260 * s, cy - 120 * s)
    path.lineTo(cx + 300 * s, cy + 40 * s)
    path.lineTo(cx - 40 * s, cy + 60 * s)
    path.close()
    cv.drawPath(path, paint(HERO))
    cv.drawOval(skia.Rect(cx + 240 * s, cy - 125 * s, cx + 320 * s, cy + 45 * s), paint(rgb("19181C")))


CLIMAX = [  # (start, cx, cy, height, rotation, frame, bar angle)  - Chainsaw Man re-framed every 0.1-0.3 s
    (20.00, 0.55, 0.56, 1.20, 0, 0, -18), (20.10, 0.40, 0.62, 1.70, -8, 0, -10), (20.20, 0.62, 0.52, 1.30, 6, 3, -24),
    (20.30, 0.46, 0.66, 1.90, -4, 3, -14), (20.40, 0.58, 0.52, 1.25, 10, 3, -30), (20.60, 0.40, 0.58, 1.20, -6, 5, -6),
    (20.80, 0.60, 0.55, 1.45, 4, 0, -20), (21.10, 0.45, 0.62, 1.95, -6, 3, -12), (21.20, 0.55, 0.52, 1.35, 8, 5, -26),
    (21.40, 0.42, 0.58, 1.80, -12, 0, -8), (21.50, 0.60, 0.54, 1.40, 6, 3, -22), (21.60, 0.50, 0.55, 1.75, 0, 5, -16),
]
HEAD_INSERT = (20.40, 20.60)       # one close-up on the chainsaw head in the middle


def red_bar(cv, x, y, ang, length, thick):
    """the flat blood-red chainsaw bar (the reference's purple tube), with its dark tip."""
    cv.save()
    cv.translate(x, y)
    cv.rotate(ang)
    p = skia.Path()
    p.moveTo(0, -thick * 0.42)
    p.lineTo(length, -thick * 0.55)
    p.lineTo(length, thick * 0.55)
    p.lineTo(0, thick * 0.42)
    p.close()
    cv.drawPath(p, paint(HERO))
    cv.drawOval(skia.Rect(length - thick * 0.25, -thick * 0.55, length + thick * 0.25, thick * 0.55), paint(rgb("19181C")))
    cv.restore()


@tl.scene(20.00, 21.70)
def s24_climax(c):
    cv = c.cv
    t = c.t
    st, cx, cy, h, rot, i, bang = [f for f in CLIMAX if f[0] <= t][-1]
    if HEAD_INSERT[0] <= t < HEAD_INSERT[1]:
        put(cv, "head", W * 0.50, H * 0.58, 1.25)
        red_bar(cv, W * 0.15, H * 0.80, -25, W * 0.9, H * 0.10)
        sparks(cv, W * 0.62, H * 0.52, t, size=220, seed=3)
        return
    s_ = put(cv, "arm", cx * W, cy * H, h, i=min(i, len(cut("arm")) - 1), rot=rot)
    # the bar leaves his hand toward the camera side and runs off frame
    hx, hy = cx * W - 0.18 * h * H, cy * H - 0.05 * h * H
    red_bar(cv, hx, hy, 180 + bang, W * 1.2, H * 0.09 * h)
    sparks(cv, hx, hy, t, size=180 * h, seed=int(t * 10))


@tl.scene(21.70, 22.55)
def s25_stroke(c):
    k = out_cubic(clamp01(step(c.lt) / 0.8))
    y0 = mix(H * 0.88, H * 0.55, k)
    tilt = mix(0.25, 0.02, k)
    pth = bezier((-100, y0 + W * tilt * 0.5), (W * 0.3, y0 + W * tilt * 0.25), (W * 0.7, y0 - W * tilt * 0.1), (W + 100, y0 - W * tilt * 0.5))
    ribbon(c.cv, pth, 66, HERO, a=1.0, seed=5, rough=0.12)


def wrapped_head(cv, x, y):
    hh = 0.70 * H
    ys = [y - hh * 0.43 + k * hh * 0.115 for k in range(5)]
    put(cv, "face", x, y, 0.70)
    layer(cv)
    for k, yy in enumerate(ys):
        if k == 3:
            continue                     # leave the eyes uncovered
        front = bezier((x - hh * 0.45, yy - 10), (x - hh * 0.15, yy + 60), (x + hh * 0.15, yy + 60), (x + hh * 0.45, yy - 25))
        ribbon(cv, front, 92, HERO if k % 2 == 0 else rgb("C8160A"), seed=30 + k, rough=0.16)
    # keep the paint only where the head is (plus a slight overhang)
    im = img("face", 0, "dilate")
    p = skia.Paint()
    p.setBlendMode(skia.BlendMode.kDstIn)
    s_ = 0.70 * H / img("face").height()
    cv.save()
    cv.translate(x, y)
    cv.scale(s_, s_)
    cv.drawImage(im, -im.width() / 2, -im.height() / 2, skia.SamplingOptions(), p)
    cv.restore()
    cv.restore()


@tl.scene(22.55, 24.00)
def s26_wrapped(c):
    cv = c.cv
    k = out_cubic(clamp01(c.lt / 0.2))
    x = mix(W * 1.4, W * 0.55, k)
    ribbon(cv, bezier((-100, H * 0.56), (W * 0.3, H * 0.55), (W * 0.6, H * 0.53), (W + 100, H * 0.55)), 66, HERO, seed=5, rough=0.12)
    wrapped_head(cv, x, H * 0.50)


@tl.post(22.55, 22.72)
def p26(rgb_, c):
    return dir_blur(rgb_, 380, 0)


# echoes and glitch (24.00-26.40)
def echoes(cv, t, kind, n):
    i = nframe("scream", t - 24.0, loop=True)
    sp = W * 0.14
    order = sorted(range(-n // 2, n - n // 2), key=lambda q: -abs(q))
    for q in order:
        if q == 0:
            continue
        jy = np.random.default_rng(q * 7 + int(step(t) * 12)).uniform(-14, 14)
        put(cv, "scream", W * 0.5 + q * sp, H + 4 + jy, 0.70, i=i, treat=kind if q % 2 else kind + "2", anchor=(0.5, 1.0))
    put(cv, "scream", W * 0.5, H + 4, 0.80, i=i, treat="lift", anchor=(0.5, 1.0))


@tl.scene(24.00, 24.70)
def s28_explode(c):
    cv = c.cv
    t = c.t
    n = 2 if t < 24.15 else 4 if t < 24.35 else 8
    echoes(cv, t, "mint", n)
    if t < 24.15:
        k = 0.5 if t < 24.08 else 1.0
        for j in range(6):
            ang = math.radians(j * 60 + 15)
            r = 300 + k * 500
            pth = bezier((W / 2 + math.cos(ang) * r * 0.4, H / 2 + math.sin(ang) * r * 0.4),
                         (W / 2 + math.cos(ang + 0.4) * r * 0.7, H / 2 + math.sin(ang + 0.4) * r * 0.7),
                         (W / 2 + math.cos(ang + 0.2) * r, H / 2 + math.sin(ang + 0.2) * r),
                         (W / 2 + math.cos(ang + 0.5) * r * 1.2, H / 2 + math.sin(ang + 0.5) * r * 1.2))
            ribbon(cv, pth, 50, HERO, seed=j, rough=0.15)


@tl.scene(24.70, 25.50)
def s29_glitch(c):
    echoes(c.cv, c.t, "mint", 8)


@tl.post(24.70, 25.50)
def p29_glitch(rgb_, c):
    k = int((c.t - 24.70) / 0.1)
    out = core.glitch(rgb_, 100 + k, 1.4)
    col = [rgb("1C2340"), HERO, TEAL, (0.05, 0.05, 0.05), None, rgb("1C2340"), None, TEAL][k % 8]
    if col is not None:
        out = recolor(out, col, 0.75)
    return out


@tl.scene(25.50, 26.40)
def s30_echo_cyan(c):
    cv = c.cv
    t = c.t
    echoes(cv, t, "cyan", 10)
    if t >= 26.00:
        k = out_cubic(clamp01((t - 26.00) / 0.35))
        flick = math.sin(clamp01((t - 26.25) / 0.15) * math.pi) * 12
        put(cv, "finger", mix(W * 1.5, W * 0.80, k), H * 0.55, 0.85, rot=-8 + flick)


@tl.scene(26.40, 26.70)
def s31_splash(c):
    cv = c.cv
    t = c.t
    if t < 26.55:
        echoes(cv, t, "cyan", 10)
        put(cv, "finger", W * 0.80, H * 0.55, 0.85, rot=-8)
    if t < 26.45:
        splatter(cv, W * 0.5, H * 0.5, 260, HERO, p=1.0, seed=21)
    elif t < 26.50:
        cv.drawCircle(W * 0.5, H * 0.5, H * 0.40, paint(HERO))
        splatter(cv, W * 0.5, H * 0.5, 560, HERO, p=1.0, seed=22)
    elif t < 26.55:
        fill(cv, HERO)
        splatter(cv, W * 0.5, H * 0.5, 1500, (1, 1, 1), a=0.0, p=1.0, seed=23)
        for k in range(30):
            rng = np.random.default_rng(k)
            x, y = rng.uniform(0, W), rng.choice([rng.uniform(0, 40), rng.uniform(H - 40, H)])
            cv.drawCircle(float(x), float(y), float(rng.uniform(8, 30)), paint(WHITE))
    else:
        fill(cv, HERO)


@tl.scene(26.70, 27.55)
def s32_closeup(c):
    cv = c.cv
    t = c.t
    i = nframe("power_cu", max(0.0, t - 27.40) if t >= 27.40 else 0.0)
    punch = 1.0 if t < 27.45 else 1.06
    put(cv, "power_cu", W * 0.5, H * 0.56, 1.12 * punch, i=i)
    if t < 26.85:
        # the blood fill breaks up with ragged threshold edges, revealing the close-up
        k = (t - 26.70) / 0.15
        rng = np.random.default_rng(5)
        noise = _bg.get("noise")
        if noise is None:
            n = cv2.GaussianBlur(rng.random((H // 4, W // 4)).astype(np.float32), (0, 0), 6)
            n = (n - n.min()) / (n.max() - n.min())
            noise = _bg["noise"] = cv2.resize(n, (W, H))
        m = (noise > k).astype(np.uint8) * 255
        rgba = np.zeros((H, W, 4), np.uint8)
        rgba[..., :3] = (np.array(HERO) * 255).astype(np.uint8)
        rgba[..., 3] = m
        draw_image(cv, to_image(rgba), 0, 0, 1.0, anchor=(0, 0))


_ecu = {}


@tl.scene(27.55, 27.65)
def s34_eyes(c):
    if "eyes" not in _ecu:
        f = full_frames("pv_teaser_2020", 44.25, 44.30, fps=24)[0]
        _ecu["eyes"] = to_image(f)
    im = _ecu["eyes"]
    k = 1.0 if c.t < 27.60 else 1.08
    draw_image(c.cv, im, W / 2, H / 2, k * W / im.width())


# Pochita + starter cord (27.65-28.50), Reze's gerbera (28.50-29.80)
POCH_C = (W * 0.5, H * 0.50)


@tl.scene(27.65, 28.50)
def s35_cord(c):
    cv = c.cv
    t = c.t
    put(cv, "pochita", POCH_C[0], POCH_C[1] + H * 0.06, 0.78)
    lit = clamp01((t - 27.75) / 0.15)
    pull = out_cubic(clamp01((t - 27.75) / 0.15)) if t >= 27.75 else 0.0
    root = (POCH_C[0] - 8, POCH_C[1] - H * 0.27)
    hx, hy = mix(W * 0.62, W * 0.74, pull), mix(H * 0.16, H * 0.04, pull)
    if t < 27.70:
        hx, hy = W * 0.62, H * 0.16
    line(cv, polyline([root, (hx, hy)]), 6, INK)
    cv.drawRect(skia.Rect(hx - 26, hy - 9, hx + 26, hy + 9), paint(INK))
    if t >= 27.70:
        f = cut("hand").frames[0]
        (px, py) = hand_tips()[0]
        k_in = out_cubic(clamp01((t - 27.70) / 0.06))
        put(cv, "hand", hx + (1 - k_in) * 300, hy - (1 - k_in) * 200, 0.62, anchor=(px / f.shape[1], py / f.shape[0]), rot=-25)
    if lit > 0:
        for ex in (-0.21, 0.21):
            cv.drawCircle(POCH_C[0] + ex * H * 0.78 * 0.62, POCH_C[1] + H * 0.06 + H * 0.042, H * 0.06, paint(rgb("01E1FD"), lit * 0.85, blur=8))


@tl.scene(28.50, 29.80)
def s36_flower(c):
    cv = c.cv
    t = c.t
    k = 1.0 if t < 28.80 else 0.67 if t < 29.20 else 0.47
    k = mix(1.0 if t < 28.8 else 0.67, k, out_cubic(clamp01((t - (28.5 if t < 28.8 else 28.8 if t < 29.2 else 29.2)) / 0.3)))
    f = cut("flower").frames[0]
    fx_, fy_ = W * 0.5, H * 0.45
    # black cables radiating, with small blue light pulses
    for j in range(6):
        ang = math.radians(-160 + j * 28)
        r = H * 1.2
        pth = bezier((fx_, fy_), (fx_ + math.cos(ang) * r * 0.3, fy_ + math.sin(ang) * r * 0.2),
                     (fx_ + math.cos(ang) * r * 0.6, fy_ + math.sin(ang) * r * 0.7), (fx_ + math.cos(ang) * r, fy_ + math.sin(ang) * r))
        line(cv, pth, 4 + (j % 2) * 5, INK)
        u = ((t * 1.3 + j * 0.17) % 1.0)
        line_part(cv, pth, u, min(1, u + 0.08), 6 + (j % 2) * 5, rgb("2AB3EF"))
    put(cv, "flower", fx_, fy_ + H * 0.35 * k, 1.25 * k, anchor=(0.5, 0.42))


@tl.scene(29.80, 30.10)
def s37_cables(c):
    cv = c.cv
    off = -(c.t - 29.80) * 6000
    line(cv, polyline([(-50, H * 0.42), (W + 50, H * 0.40)]), H * 0.023, INK)
    line(cv, polyline([(-50, H * 0.55), (W + 50, H * 0.57)]), 4, INK)
    u = (c.t - 29.8) / 0.3
    line_part(cv, polyline([(-50, H * 0.42), (W + 50, H * 0.40)]), u, u + 0.2, H * 0.023, rgb("01E1FD"))


@tl.post(29.85, 29.95)
def p37(rgb_, c):
    return dir_blur(rgb_, 500, 0)


ARM_POSE = dict(cx=W * 0.70, cy=H * 0.30, h=0.36, rot=-28, treat="steel")


def arm_drop(cv, t, y=0.0, treat="steel"):
    put(cv, "sawarm", ARM_POSE["cx"], ARM_POSE["cy"] + y, ARM_POSE["h"], treat=treat, rot=ARM_POSE["rot"])


def saw_tip(y=0.0):
    f = cut("sawarm").frames[0]
    a = f[..., 3] > 128
    ys, xs = np.where(a)
    i = np.argmin(xs)
    return img_point("sawarm", xs[i], ys[i], ARM_POSE["cx"], ARM_POSE["cy"] + y, ARM_POSE["h"], treat="steel",
                     rot=ARM_POSE["rot"])


@tl.scene(30.10, 31.60)
def s38_arm(c):
    cv = c.cv
    t = c.t
    k = out_cubic(clamp01(step(c.lt) / 0.30))
    y = mix(-H * 1.0, 0, k)
    cable = bezier((-50, H * 0.42), (W * 0.3, H * 0.44), (W * 0.62, H * 0.12 + y), (W * 0.80, H * 0.10 + y))
    line(cv, cable, H * 0.023, INK)
    u = clamp01((t - 30.10) / 0.35)
    line_part(cv, cable, u * 0.8, u * 0.8 + 0.2, H * 0.023, rgb("01E1FD"))
    arm_drop(cv, t, y)
    drop = clamp01((t - 30.95) / 0.60)
    if drop > 0:
        tip = saw_tip(y)
        r = 8 + drop * 18
        dp = skia.Path()
        dp.moveTo(tip[0], tip[1])
        dp.cubicTo(tip[0] - r, tip[1] + r * 1.2, tip[0] - r, tip[1] + r * 2.4, tip[0], tip[1] + r * 2.4)
        dp.cubicTo(tip[0] + r, tip[1] + r * 2.4, tip[0] + r, tip[1] + r * 1.2, tip[0], tip[1])
        cv.drawPath(dp, paint(HERO))


@tl.post(30.10, 30.30)
def p38(rgb_, c):
    return dir_blur(rgb_, 0, 260)


@tl.post(31.60, 31.64)
def p39_matte(rgb_, c):
    fr = core.Frame()
    cv = fr.clear((0.012, 0.012, 0.012))
    arm_drop(cv, 31.6, treat="white")
    return fr.array()


@tl.scene(31.65, 32.00)
def s40_drop(c):
    cv = c.cv
    t = c.t
    rain(cv, t, [rgb("95EAF0")], n=24, vertical=True, speed=900, a=0.6, seed=8)
    if t < 31.72:
        arm_drop(cv, t, -(t - 31.65) * 4000)
    tx, ty = saw_tip()
    y = mix(ty, H * 1.3, (t - 31.65) / 0.35)
    cv.drawLine(tx, y - 220, tx, y, paint(HERO, 0.9, stroke=10))


@tl.post(31.70, 31.78)
def p40(rgb_, c):
    return dir_blur(rgb_, 0, 400)


@tl.scene(32.00, 33.00)
def s41_bars(c):
    cv = c.cv
    t = c.t
    rain(cv, t, [rgb("95EAF0")], n=24, vertical=True, speed=900, a=0.6, seed=8)
    cv.drawLine(W * 0.5, 0, W * 0.5, H, paint(rgb("8BEDFA"), 0.9, stroke=3))
    if t >= 32.85:
        return
    idx = min(2, int((t - 32.0) / 0.3))
    col = [rgb("E64839"), rgb("8BEDFA"), rgb("92B6C3")][idx]
    trail = [rgb("EC7265"), rgb("C6F5FC"), rgb("C3D7DE")][idx]
    ph = int(((t - 32.0) - idx * 0.3) / 0.1)
    bw, bh, y = W * 0.62, H * 0.045, H * 0.55
    for side in (-1, 1):
        ang = 0 if ph == 0 else -20 * side
        dy = 0 if ph < 2 else -H * 0.5
        for e in range(4, -1, -1):
            cv.save()
            cv.translate(W * 0.5 + side * bw * 0.25, y + dy + e * 18 * (1 if ph else 0))
            cv.rotate(ang * (1 if ph else 0))
            col_e = col if e == 0 else trail
            cv.drawRect(skia.Rect(-bw * 0.25, -bh / 2, bw * 0.25, bh / 2), paint(col_e, 1.0 if e == 0 else 0.35 / e))
            cv.restore()


# recap totem on a chain (33.00-34.40)
BOX_COLS = [rgb("E5210D"), rgb("0BCBCC"), rgb("0C2F9B"), rgb("9025DC"), (0, 0, 0), rgb("D02DC3")]
THUMBS = ["pochita", "eat", "makima", "power_cu", "head", None]


def totem(cv, t, y_off=0.0, flash=None):
    cx, cy = W * 0.5, H * 0.50 + y_off
    bw, bh = W * 0.07, H * 0.09
    pos = [(0, -2), (-1, -1), (0, -1), (1, -1), (0, 0), (0, 1)]
    chain(cv, polyline([(cx, -40), (cx, cy + bh * 1.6)]), 0, 1, link=22)
    for k, (gx, gy) in enumerate(pos):
        x, y = cx + gx * bw * 1.15, cy + gy * bh * 1.25
        r = skia.Rect(x - bw / 2, y - bh / 2, x + bw / 2, y + bh / 2)
        cv.drawRect(r, paint(WHITE))
        if flash is not None and flash == k:
            cv.drawRect(r, paint(BOX_COLS[k]))
        elif flash is None:
            name = THUMBS[k]
            if name:
                cv.save()
                cv.clipRect(r, True)
                im = img(name, 0)
                s = max(bw / im.width(), bh / im.height()) * 1.15
                draw_image(cv, im, x, y, s)
                cv.restore()
            else:
                text(cv, "chainsaw man", x, y + 4, 12, FONT_MONO, INK)
        cv.drawRect(r, paint(INK, 1.0, stroke=H * 0.003))


@tl.scene(33.00, END)
def s42_totem(c):
    t = c.t
    y = 0.0 if t >= 33.05 else -H * 0.6
    flash = None
    if 33.10 <= t < 33.40:
        flash = min(5, int((t - 33.10) / 0.05))
    totem(c.cv, t, y, flash)


@tl.post(33.00, 33.05)
def p42(rgb_, c):
    return dir_blur(rgb_, 0, 300)


ALL_CUTS = list(CUTS)


def preload():
    for n in ALL_CUTS:
        cut(n)
    relief_bg()
    paper_bg()
    paper_bg(True)
