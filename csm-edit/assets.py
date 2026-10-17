"""Assets for the Chainsaw Man collage edit: palette, cut-outs (with their mattes and treatments), backgrounds, drawn
props (screws, crayon strokes, chainsaw bar...) and frame-level post effects. The scenes live in edit.py."""
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

def _versioned(v):
    def deco(fn):
        fn.version = v
        return fn
    return deco


def _ramp(h, w, left=0.0, right=0.0, top=0.0, bottom=0.0):
    """alpha ramp that fades given fractions of each edge to zero (hides straight source-crop edges)."""
    x = np.linspace(0, 1, w)[None, :]
    y = np.linspace(0, 1, h)[:, None]
    m = np.ones((h, w), np.float32)
    if left:
        m = m * np.clip(x / left, 0, 1)
    if right:
        m = m * np.clip((1 - x) / right, 0, 1)
    if top:
        m = m * np.clip(y / top, 0, 1)
    if bottom:
        m = m * np.clip((1 - y) / bottom, 0, 1)
    return m


@_versioned(2)
def _pochita_shape(shape):
    """Pochita's orange body only (the handle loop is drawn as a vector instead)."""
    h, w = shape
    m = np.zeros((h, w), np.float32)
    cv2.ellipse(m, (885, 625), (405, 345), 0, 0, 360, 1.0, -1, cv2.LINE_AA)
    return cv2.GaussianBlur(m, (0, 0), 1.2)


@_versioned(2)
def _edge_fade(shape):
    h, w = shape
    return _ramp(h, w, left=0.25, right=0.25, top=0.0, bottom=0.30)


@_versioned(3)
def _arm_shape(shape):
    """drop the other character's leg and shoe at the bottom right of the first drawing."""
    m = np.ones(shape, np.float32)
    m[int(shape[0] * 0.46):, int(shape[1] * 0.76):] = 0
    return m


@_versioned(2)
def _bowl_shape(shape):
    m = np.ones(shape, np.float32)
    m[:, :120] = 0
    return m


@_versioned(2)
def _hand_shape(shape):
    """the teaser hand: fade the wrist where the source frame cut it (bottom and right edges)."""
    h, w = shape
    return _ramp(h, w, right=0.06, bottom=0.14)


@_versioned(4)
def _puppet_shape(shape):
    """Denji from behind, arms out: drop the jacket and coat of the people behind him, fade his legs out."""
    h, w = shape
    m = _ramp(h, w, bottom=0.16)
    m[520:800, 780:900] = 0
    m[700:, 650:750] = 0
    return m


@_versioned(2)
def _sawarm_shape(shape):
    h, w = shape
    return _ramp(h, w, right=0.25)


@_versioned(2)
def _fly_shape(shape):
    h, w = shape
    return _ramp(h, w, bottom=0.12)


@_versioned(4)
def _scream_shape(shape):
    """keep the screaming head, fade out his shoulder and arm on the right."""
    h, w = shape
    return _ramp(h, w, right=0.62, bottom=0.15)


@_versioned(2)
def _saw_shape(shape):
    h, w = shape
    return _ramp(h, w, left=0.12, bottom=0.06)


@_versioned(2)
def _face_shape(shape):
    h, w = shape
    return _ramp(h, w, bottom=0.10)


CUTS = dict(
    duo=dict(vid="nced12_fight_song", t0=2.10, erode=2, min_comp=0.12),
    hand=dict(vid="pv_teaser_2020", t0=38.80, mask_fn=_hand_shape),
    cordhand=dict(vid="pv_main_2022", t0=66.30, t1=66.80),
    puppet=dict(vid="ncop_kickback", t0=81.90, crop=(0, 0, 1180, 1080), mask_fn=_puppet_shape, keep_largest=True),
    leash=dict(vid="ncop_kickback", t0=35.15, t1=35.45),
    kid=dict(vid="pv_teaser_2020", t0=16.50),
    head=dict(vid="pv2_2022", t0=81.90, gc_rect=(560, 0, 1500, 1080), keep_largest=True),
    bowl=dict(vid="ncop_kickback", t0=30.80, crop=(900, 0, 1920, 1080), keep_largest=True, mask_fn=_bowl_shape),
    power_fly=dict(vid="ncop_kickback", t0=56.40, keep_largest=True, mask_fn=_fly_shape),
    saw=dict(vid="pv_main_2022", t0=72.00, keep_largest=True, mask_fn=_saw_shape),
    pochita=dict(vid="cpv_denji", t0=10.90, crop=(0, 0, 1920, 985), gc_rect=(430, 240, 1340, 985), mask_fn=_pochita_shape),
    arm=dict(vid="ncop_kickback", t0=72.20, lo=0.45, hi=0.85, erode=2, keep_largest=True, mask_fn=_arm_shape),
    arm_b=dict(vid="ncop_kickback", t0=72.45, lo=0.45, hi=0.85, erode=2, keep_largest=True),
    arm_c=dict(vid="ncop_kickback", t0=72.62, lo=0.45, hi=0.85, erode=2, keep_largest=True),
    swing=dict(vid="pv_main_2022", t0=91.45),
    face=dict(vid="ncop_kickback", t0=27.90, mask_fn=_face_shape),
    scream=dict(vid="pv_main_2022", t0=53.45, erode=2, keep_largest=True, mask_fn=_scream_shape, holes=True),
    sawarm=dict(vid="ncop_kickback", t0=72.45, crop=(100, 430, 1050, 800), erode=2, mask_fn=_sawarm_shape),
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
    out = c * (0.80 + 0.30 * gn[..., None]) + (1 - c) * 0.25 * gn[..., None]
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


def _duotone(rgba, dark, light):
    g = cv2.cvtColor(rgba[..., :3], cv2.COLOR_RGB2GRAY).astype(np.float32)
    ok = rgba[..., 3] > 128
    lo, hi = np.percentile(g[ok], [3, 97]) if ok.any() else (0, 255)
    gn = np.clip((g - lo) / max(hi - lo, 1), 0, 1)[..., None]
    out = np.array(dark, np.float32) * (1 - gn) + np.array(light, np.float32) * gn
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
        yy, xx = np.mgrid[0:hh, 0:ww].astype(np.float32)
        rng = np.random.default_rng(seed + 9)
        noise = cv2.GaussianBlur(rng.random((hh, ww)).astype(np.float32), (0, 0), ww * 0.012)
        noise = (noise - noise.mean()) / (noise.std() + 1e-6)
        for (x, y), col in zip(tips, [HERO, CYAN, NAVY]):
            r = ww * 0.075
            dist = np.sqrt((xx - x) ** 2 + ((yy - y) * 0.8) ** 2) / r
            m = np.clip((1.0 + 0.30 * noise - dist) / 0.12, 0, 1) * a
            streak = 0.75 + 0.25 * np.sin(xx * 0.35 + noise * 2)
            c255 = np.array(col, np.float32) * 255
            res[..., :3] = (res[..., :3] * (1 - m[..., None] * 0.85) + (c255 * streak[..., None]) * m[..., None] * 0.85).clip(0, 255).astype(np.uint8)
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
    "navy": lambda f, i: _duotone(f, rgb("273150"), rgb("A7B3ED")),
    "mint": lambda f, i: _bright_tint(f, MINT),
    "mint2": lambda f, i: _bright_tint(f, MINT2),
    "cyan": lambda f, i: _bright_tint(f, ECHO_CY),
    "cyan2": lambda f, i: _bright_tint(f, ECHO_CY2),
    "lift": lambda f, i: _lift(f, 0.62),
    "white": lambda f, i: _silhouette(f),
    "red": lambda f, i: _flat(f, HERO, 0.6),
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

def screw(cv, x, y, d=31.0, rot=0.0):
    """photographic-looking Phillips screw head: grey dome lit from the top left, soft cross recess."""
    r = d / 2
    body, shade = rgb("A69E98"), rgb("5E514B")
    hi = (0.95, 0.94, 0.92)
    sh = skia.GradientShader.MakeRadial(skia.Point(x - r * 0.35, y - r * 0.40), r * 1.5,
                                        [cint(hi), cint(body), cint(shade)], [0.0, 0.5, 1.0])
    p = skia.Paint(AntiAlias=True)
    p.setShader(sh)
    cv.drawCircle(x, y, r, p)
    cv.save()
    cv.translate(x, y)
    cv.rotate(rot)
    for a in (0, 90):
        cv.save()
        cv.rotate(a)
        cv.drawLine(-r * 0.52, 0, r * 0.52, 0, paint((0.20, 0.17, 0.15), 0.5, stroke=r * 0.14))
        cv.drawLine(-r * 0.46, -r * 0.07, r * 0.46, -r * 0.07, paint((1, 1, 1), 0.25, stroke=r * 0.05))
        cv.restore()
    cv.restore()
    cv.drawCircle(x - r * 0.38, y - r * 0.42, r * 0.22, paint((1, 1, 1), 0.55, blur=r * 0.12))


def crayon(cv, path, p1, col, hi, width=13.0, seed=0, p0=0.0, a=1.0, core=None):
    """ragged crayon / dry-brush stroke: speckled light rim, varying width, darker core; written on to fraction p1."""
    if p1 <= p0:
        return
    L = path_length(path)
    pts, tans = sample_path(path, p0 * L, p1 * L, step=3.0)
    if len(pts) < 2:
        return
    n = len(pts)
    nrm = np.stack([-tans[:, 1], tans[:, 0]], 1)
    wv = width * (1 + 0.25 * core_noise(n, seed, 30))
    rng = np.random.default_rng(seed)
    core = core or tuple(c * 0.62 for c in col)
    # speckled light rim
    for k in range(5):
        off = rng.uniform(-0.6, 0.6, n) * 0 + (k / 4 - 0.5) * 1.15
        q = pts + nrm * (off * wv)[:, None] + rng.normal(0, 0.8, (n, 2))
        pk = paint(hi, a * 0.55, stroke=max(1.0, width * 0.22))
        pk.setPathEffect(skia.DashPathEffect.Make([float(v) for v in rng.uniform(4, 22, 12)], float(rng.uniform(0, 40))))
        cv.drawPath(polyline(q.tolist()), pk)
    # body, built from bristles across the varying width
    for k in range(9):
        off = (k / 8 - 0.5) * 0.9
        q = pts + nrm * (off * wv)[:, None] + nrm * (core_noise(n, seed * 31 + k, 25) * width * 0.08)[:, None]
        c_ = col if abs(off) > 0.18 else core
        pk = paint(c_, a * rng.uniform(0.75, 1.0), stroke=max(1.0, width * 0.24))
        pk.setPathEffect(skia.DashPathEffect.Make([float(v) for v in np.r_[rng.uniform(40, 160, 6), rng.uniform(1, 7, 6)][[0, 6, 1, 7, 2, 8, 3, 9, 4, 10, 5, 11]]],
                                                  float(rng.uniform(0, 200))))
        cv.drawPath(polyline(q.tolist()), pk)


def core_noise(n, seed, scale):
    return core._noise1(n, seed, scale)


def red_dots(cv, path, p1, width=13.0, seed=0, a=1.0):
    """the dotted red stroke: an irregular, staggered double chain of short dashes and specks with darker cores."""
    L = path_length(path)
    if p1 <= 0 or L <= 0:
        return
    rng = np.random.default_rng(seed)
    d = 0.0
    row = 0
    while d < p1 * L:
        ln = width * rng.uniform(0.6, 1.4)
        pos, tan = skia.PathMeasure(path, False).getPosTan(float(min(d, L)))
        tx, ty = tan.x(), tan.y()
        off = (0.28 if row % 2 else -0.28) * width
        x, y = pos.x() - ty * off, pos.y() + tx * off
        ang = math.degrees(math.atan2(ty, tx))
        cv.save()
        cv.translate(x, y)
        cv.rotate(ang + rng.uniform(-12, 12))
        wd = width * rng.uniform(0.45, 0.75)
        cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(-ln / 2, -wd / 2, ln / 2, wd / 2), wd / 2, wd / 2), paint(RED, a))
        cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(-ln / 3, -wd / 4, ln / 3, wd / 4), wd / 4, wd / 4), paint(rgb("AB594C"), a))
        if rng.random() < 0.5:
            cv.drawCircle(float(rng.uniform(-ln, ln)), float(rng.uniform(-width, width)), float(width * rng.uniform(0.08, 0.18)),
                          paint(RED_HI if rng.random() < 0.5 else RED, a * 0.8))
        cv.restore()
        d += ln * rng.uniform(0.7, 1.25)
        row += 1


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
    # orange engine housing at the left end, rivets on the plate
    hs = skia.RRect.MakeRectXY(skia.Rect(x0 - thick * 2.2, y - thick * 1.3, x0 + thick * 0.4, y + thick * 1.3), thick * 0.4, thick * 0.4)
    cv.drawRRect(hs, paint(rgb("E8761E"), a))
    cv.drawRRect(hs, paint((0.10, 0.08, 0.06), 0.8 * a, stroke=2))
    for k in range(3):
        cv.drawCircle(x0 + (x1 - x0) * (0.2 + 0.3 * k), y, thick * 0.12, paint((0.55, 0.56, 0.58), a))


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
        dx, dy = rng.uniform(-66, 66), rng.uniform(-60, 30)
        size = 41 * rng.uniform(0.6, 1.5)
        col = cols[k % 2] if k < 4 else cols[int(rng.integers(0, len(cols)))]
        text(cv, "?", 960 + dx, 550 + dy, size, FONT_LYR, col)


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


