"""Chainsaw Man collage edit: the 43 scenes, timed to the reference sound (0-34.4 s).

Structure, timings, scales and cadence follow the reference breakdown (white collage edit). The subjects are swapped for
Chainsaw Man: puppet strings that snap and leave Denji on a chain leash, a chainsaw bar for the beam, a collage Chainsaw
Man head with a Makima-ring HUD, Aki bowling, Pochita as the machine, the starter cord turning into the chainsaw's red
slash, a blood splash, Makima's ringed eyes, Pochita's starter cord pulled, Reze's gerbera, a chainsaw arm dripping
blood, and a recap totem on a chain. Assets (cut-outs, treatments, props) are in assets.py.
"""
import math

import cv2
import numpy as np
import skia

import assets as AS
from assets import *  # noqa: F401,F403
from assets import (W, H, core, tl, draw_image, to_image, paint, brush, ribbon, line, polyline, bezier, chain, rings,  # noqa: E402
                    splatter, text, mix, clamp01, smooth, out_cubic, in_cubic, tint_filter, layer, line_part)


def cimg(key, fn):
    """cached skia image built by fn() -> RGBA array."""
    im = AS._imgs.get(key)
    if im is None:
        im = AS._imgs[key] = to_image(fn())
    return im


def extreme(name, how, i=0):
    """an extreme alpha pixel of a cut-out (image px): 'left', 'right', 'top', 'topleft', 'botright'."""
    f = cut(name).frames[i]
    ys, xs = np.where(f[..., 3] > 128)
    k = {"left": np.argmin(xs), "right": np.argmax(xs), "top": np.argmin(ys), "topleft": np.argmin(xs + ys),
         "botright": np.argmax(xs + ys)}[how]
    return float(xs[k]), float(ys[k])


# ================================================================================================= 0 - 2.65 duo + words

DUO_H = 0.32
DUO_CX, DUO_BOT = 0.485 * W, 0.85 * H
DUO_GAP = 0.45
WORDS = [("still", 0.25, 0.50), ("fight", 0.55, 0.80), ("and", 0.85, 1.00), ("i", 1.05, 1.20),
         ("don’t", 1.25, 1.50), ("know", 1.55, 1.80), ("why", 1.85, 2.60)]


def duo_halves():
    if "duo_halves" not in AS._bg:
        f = cut("duo").frames[0]
        a = f[..., 3] > 30
        cols = a.sum(0)
        w = f.shape[1]
        mid = int(np.argmin(cols[int(w * 0.3):int(w * 0.7)]) + w * 0.3)
        left, right = f.copy(), f.copy()
        left[:, mid:, 3] = 0
        right[:, :mid, 3] = 0
        AS._bg["duo_halves"] = (left, right, mid)
    return AS._bg["duo_halves"]


def duo_geom():
    f = cut("duo").frames[0]
    s = DUO_H * H / f.shape[0]
    x0 = DUO_CX - f.shape[1] * s / 2
    y0 = DUO_BOT - f.shape[0] * s
    shift = f.shape[1] * s * 0.18 * DUO_GAP
    return s, x0 + shift, x0 - shift, y0


def pixel_dissolve(rgba, k, block=20, seed=4):
    out = rgba.copy()
    h, w = out.shape[:2]
    rng = np.random.default_rng(seed)
    nb_y, nb_x = h // block + 1, w // block + 1
    order = rng.random((nb_y, nb_x)) + np.linspace(0, 0.6, nb_x)[None, :]
    order /= order.max()
    for by in range(nb_y):
        for bx in range(nb_x):
            o = order[by, bx]
            ys, xs = slice(by * block, (by + 1) * block), slice(bx * block, (bx + 1) * block)
            a = out[ys, xs, 3]
            if a.size == 0:
                continue
            if o < k - 0.15:
                out[ys, xs, 3] = 0
            elif o < k and a.max() > 0:
                out[ys, xs, :3] = (np.array(BLOCK) * 255).astype(np.uint8)
                out[ys, xs, 3] = 255 if a.mean() > 40 else 0
    return out


def draw_duo(cv, treat=None, alpha=1.0, left=True, right=True, dissolve=None):
    s, xl, xr, y0 = duo_geom()
    L, R, mid = duo_halves()
    if right:
        draw_image(cv, cimg(("duoR", treat), lambda: TREAT[treat](R, 0)), xr, y0, s, anchor=(0, 0), alpha=alpha)
    if left:
        if dissolve is None:
            draw_image(cv, cimg(("duoL", treat), lambda: TREAT[treat](L, 0)), xl, y0, s, anchor=(0, 0), alpha=alpha)
        else:
            draw_image(cv, cimg(("duoLd", dissolve), lambda: pixel_dissolve(L, dissolve)), xl, y0, s, anchor=(0, 0))


def duo_points(n=30, seed=1):
    """random points inside the duo silhouettes (frame px), for the charcoal to condense onto."""
    if "duo_pts" not in AS._bg:
        s, xl, xr, y0 = duo_geom()
        L, R, mid = duo_halves()
        pts = []
        for img_, x0 in ((L, xl), (R, xr)):
            ys, xs = np.where(img_[..., 3] > 128)
            rng = np.random.default_rng(seed)
            idx = rng.choice(len(xs), n // 2, replace=False)
            pts += [(x0 + xs[k] * s, y0 + ys[k] * s) for k in idx]
        AS._bg["duo_pts"] = pts
    return AS._bg["duo_pts"]


@tl.scene(0.0, 0.25)
def s01_sketch(c):
    cv = c.cv
    full_bg(cv, paper_bg())
    ts = step(c.lt)
    k = clamp01(ts / 0.20)
    rng = np.random.default_rng(5)
    # heavy charcoal clumps condensing onto the two figures
    for j, (tx, ty) in enumerate(duo_points()):
        sx, sy = tx + rng.normal(0, 300), ty + rng.normal(0, 200)
        x, y = mix(sx, tx, out_cubic(k)), mix(sy, ty, out_cubic(k))
        r = mix(rng.uniform(14, 48), rng.uniform(4, 10), k)
        cv.drawCircle(float(x), float(y), float(r), paint((0.20, 0.19, 0.18), rng.uniform(0.45, 0.8) * (1 - 0.6 * k), blur=r * 0.25))
        for _ in range(6):
            cv.drawCircle(float(x + rng.normal(0, r)), float(y + rng.normal(0, r)), float(rng.uniform(1, 3.5)),
                          paint((0.15, 0.14, 0.13), rng.uniform(0.3, 0.8)))
    layer(cv, alpha=smooth(clamp01((k - 0.25) / 0.75)))
    draw_duo(cv, treat="pencil")
    cv.restore()


@tl.scene(0.25, 2.70)
def s02_duo(c):
    cv = c.cv
    t = c.t
    if t < 2.25:
        draw_duo(cv)
    elif t < 2.65:
        k = [0.5, 0.85, 1.01, 1.01][min(3, int((t - 2.25) / 0.1))]
        draw_duo(cv, dissolve=round(k, 2))
    else:
        # bass entry: everything drops with a whip as the hand enters
        draw_duo(cv, left=False)
    for w_, a, b in WORDS:
        if a <= t < b:
            text(cv, w_, 960, 550, 41, FONT_LYR, GREYTXT)
    if 2.15 <= t < 2.65:
        n = 4 if t < 2.35 else 8 if t < 2.45 else 12
        question_marks(cv, n, t, seed=9)


# ================================================================================================= 2.65 - 5.45 the hand

PINS = [(0.27 * W, 0.41 * H), (0.42 * W, 0.06 * H), (0.72 * W, 0.46 * H)]
STROKES = [("dots", None, None), ("crayon", CYAN, CYAN_HI), ("crayon", TEAL, TEAL_HI)]
HAND_C = (W * 0.48, H * 0.50)
HAND_H = 0.50
WRIST = (0.86, 0.93)          # where the wires attach (fraction of the hand image)
WIRE_COLS = [rgb("E8893A"), rgb("3C6FD8"), rgb("C83A3A"), rgb("7C4AC9"), rgb("2A9D8F")]


def wires(cv, x, y, sway=0.0, top_x=None):
    """the bundle of ~15 thin coloured wires from the top edge down to (x, y)."""
    top_x = x if top_x is None else top_x
    rng = np.random.default_rng(2)
    for k in range(15):
        x0 = top_x + rng.uniform(-14, 14)
        x1 = x + rng.uniform(-10, 10)
        mx = mix(x0, x1, 0.5) + rng.uniform(-6, 6) + sway * 0.5
        line(cv, polyline([(x0, -10), (mx, y * 0.5), (x1, y)]), rng.uniform(2, 3.5), WIRE_COLS[k % 5], 0.95)


@tl.scene(2.65, 3.45)
def s04_hand_falls(c):
    cv = c.cv
    lt = step(c.lt)
    yk = mix(0.4, 1.0, out_cubic(clamp01(lt / 0.22)))
    # damped pendulum about the wire attachment
    ang = 15 * math.exp(-lt / 0.4) * math.cos(lt * 13)
    hx = W * 0.44
    wrist_y = mix(-H * 0.5, H * 0.62, yk)
    wires(cv, hx, wrist_y + 6)
    put(cv, "hand", hx, wrist_y, 0.30, treat="stonehand", anchor=WRIST, rot=165 + ang)


@tl.post(2.65, 3.06)
def p04(rgb_, c):
    lt = c.lt
    if lt < 0.09:
        return dir_blur(rgb_, 0, 200)
    if lt < 0.20:
        return mosaic(rgb_, 38)
    if lt < 0.30:
        return mosaic(rgb_, 18)
    return rgb_


def hand_pose(rot=35.0, scale=1.0, jitter=(0, 0), cx=None, cy=None):
    cx = (HAND_C[0] if cx is None else cx) + jitter[0]
    cy = (HAND_C[1] if cy is None else cy) + jitter[1]
    return dict(cx=cx, cy=cy, h=HAND_H * scale, rot=rot)


def draw_hand_with_strokes(cv, treat="stonehand", strokes_p=1.0, rot=35.0, scale=1.0, jitter=(0, 0), screws=True,
                           cx=None, cy=None, straight=0.0, lt=0.0, wire=True):
    pose = hand_pose(rot, scale, jitter, cx, cy)
    f = cut("hand").frames[0]
    wx, wy = img_point("hand", WRIST[0] * f.shape[1], WRIST[1] * f.shape[0], pose["cx"], pose["cy"], pose["h"],
                       treat=treat, rot=pose["rot"])
    if wire:
        sway = math.sin(step(lt) * 5) * 10
        wires(cv, wx + sway * 0.3, wy, sway, top_x=mix(W * 0.44, wx, 0.6))
    put(cv, "hand", pose["cx"], pose["cy"], pose["h"], treat=treat, rot=pose["rot"])
    for k, ((px, py), pin_) in enumerate(zip(hand_tips(), PINS)):
        x0, y0 = img_point("hand", px, py, pose["cx"], pose["cy"], pose["h"], treat=treat, rot=pose["rot"])
        pin2 = (mix(pin_[0], pose["cx"], 1 - scale), mix(pin_[1], pose["cy"], 1 - scale)) if scale < 1 else pin_
        # wide arcs that sweep round the hand into a cage
        bend = (1 - straight) * 0.95
        mx, my = (x0 + pin2[0]) / 2, (y0 + pin2[1]) / 2
        nx, ny = -(pin2[1] - y0), (pin2[0] - x0)
        sgn = [1, -1, -1][k]
        c1 = (mx + nx * bend * sgn * 0.55, my + ny * bend * sgn * 0.55)
        c2 = (mx + nx * bend * sgn * 0.45 + (pin2[0] - x0) * 0.2, my + ny * bend * sgn * 0.45 + (pin2[1] - y0) * 0.2)
        pth = bezier((x0, y0), c1, c2, pin2)
        kind, col, hi = STROKES[k]
        wdt = 13 * max(scale, 0.4) + 1
        if kind == "dots":
            red_dots(cv, pth, strokes_p, wdt, seed=3)
        else:
            crayon(cv, pth, strokes_p, col, hi, wdt, seed=k, core=rgb("1F959A") if k == 1 else rgb("064A4C"))
        if screws and strokes_p > 0.98:
            screw(cv, pin2[0], pin2[1], 31 * max(scale, 0.4), rot=20 * k)


@tl.scene(3.45, 4.30)
def s05_hand_strokes(c):
    lt = step(c.lt)
    rk = out_cubic(clamp01(lt / 0.5))
    draw_hand_with_strokes(c.cv, strokes_p=out_cubic(clamp01((c.lt - 0.10) / 0.30)), rot=35 * rk - 10,
                           scale=0.92 + 0.08 * rk, lt=c.lt)


@tl.scene(4.30, 4.75)
def s06_recolour(c):
    t = c.t
    treat = "thermal" if t < 4.35 else "green" if t < 4.50 else "purple" if t < 4.60 else "stonehand"
    j = [(0, 0), (8, -5), (-6, 4), (5, 6), (0, 0)][min(4, int(c.lt / 0.1))]
    draw_hand_with_strokes(c.cv, treat=treat, jitter=j, rot=25 + j[0] * 0.5, lt=c.lt)


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
    draw_hand_with_strokes(cv, treat=mode, rot=25 + (10 if k >= 6 else 0), lt=c.lt)


@tl.scene(5.25, 5.45)
def s08_snap_zoom(c):
    k = in_cubic(clamp01(c.lt / 0.15))
    sc = mix(1.0, 0.06, k)
    cx, cy = mix(HAND_C[0], W * 0.5, k), mix(HAND_C[1], H * 0.55, k)
    draw_hand_with_strokes(c.cv, scale=sc, cx=cx, cy=cy, straight=k, screws=k < 0.5, rot=25, lt=c.lt, wire=k < 0.4)


# ================================================================================================= 5.45 - 7.85 the puppet

PUP_H = 0.36
PUP_C = (W * 0.50, H * 0.72)
P_PINS = [(0.41 * W, 0.03 * H), (0.27 * W, 0.40 * H), (0.70 * W, 0.44 * H)]


def puppet_anchor_points():
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


def draw_string(cv, k, a_pt, pin_pt):
    pth = polyline([a_pt, pin_pt]) if k != 1 else bezier(a_pt, a_pt, pin_pt, pin_pt)
    if k == 1:
        red_dots(cv, pth, 1.0, 12, seed=8)
    else:
        crayon(cv, pth, 1.0, CYAN if k == 0 else TEAL, CYAN_HI if k == 0 else TEAL_HI, 13, seed=k + 20,
               core=rgb("1F959A") if k == 0 else rgb("064A4C"))
    screw(cv, pin_pt[0], pin_pt[1], 31, rot=15 * k)


@tl.scene(5.45, 6.55)
def s09_puppet(c):
    cv = c.cv
    put(cv, "puppet", PUP_C[0], PUP_C[1], PUP_H, treat="mono")
    for k, (pa, pp) in enumerate(zip(puppet_anchor_points(), P_PINS)):
        draw_string(cv, k, pa, pp)


LEASH_C = (W * 0.5, H * 0.98)


@tl.scene(6.55, 7.85)
def s10_snapped(c):
    cv = c.cv
    lt = step(c.lt)
    for k, pp in enumerate(P_PINS):
        L = [0.45, 0.30, 0.28][k] * H
        ang = math.radians(15 * math.exp(-lt / 0.35) * math.cos(lt * 14 + k)) + [0.10, -0.35, 0.30][k] * math.exp(-lt / 0.2)
        draw_string(cv, k, (pp[0] + math.sin(ang) * L, pp[1] + math.cos(ang) * L), pp)
    if c.t < 6.65:
        put(cv, "puppet", PUP_C[0], PUP_C[1] + (c.t - 6.55) * 900, PUP_H, treat="mono")
        return
    # the strings are cut, but Denji drops onto all fours on a chain leash that runs off frame (to Makima)
    f = cut("leash").frames[0]
    nx, ny = img_point("leash", f.shape[1] * 0.20, f.shape[0] * 0.30, LEASH_C[0], LEASH_C[1], 0.25, treat="mono",
                       anchor=(0.5, 1.0))
    taut = smooth(clamp01((c.t - 6.75) / 0.25))
    end = (-60, mix(H * 0.55, H * 0.25, taut))
    chain(cv, polyline(catenary((nx, ny), end, mix(90, 12, taut), 40)), 0, 1, link=20, rgb=(0.55, 0.56, 0.60))
    put(cv, "leash", LEASH_C[0], LEASH_C[1], 0.25, i=0, treat="mono", anchor=(0.5, 1.0))


@tl.scene(7.85, 8.05)
def s11_whip(c):
    cv = c.cv
    if c.t >= 7.95:
        full_bg(cv, relief_bg())
        rng = np.random.default_rng(int(c.t * 24))
        for k in range(6):
            x = W * rng.uniform(0.3, 0.7)
            cv.drawLine(x, 0, x, H, paint([CYAN, RED, TEAL][k % 3], 0.8, stroke=2))
    else:
        put(cv, "leash", LEASH_C[0], LEASH_C[1] - (c.t - 7.85) * 3000, 0.25, i=0, treat="mono", anchor=(0.5, 1.0))
        chain(cv, polyline([(-60, H * 0.25 - (c.t - 7.85) * 3000), (W * 0.4, H * 0.8 - (c.t - 7.85) * 3000)]), 0, 1, link=20)


@tl.post(7.85, 8.05)
def p11_whip(rgb_, c):
    return dir_blur(rgb_, 0, 380)


BAR_Y, BAR_T = 0.83 * H, 0.045 * H


@tl.scene(8.05, 8.65)
def s12_beam(c):
    cv = c.cv
    t = c.t
    plain = any(abs(t - x) < 0.026 for x in (8.10, 8.25, 8.50))
    if not plain:
        full_bg(cv, relief_bg())
    flick = 0.80 + 0.20 * (int(t * 24) % 2)
    chainsaw_bar(cv, W * 0.13, BAR_Y, W * 0.90, BAR_T, a=flick, phase=t * 6)
    # little Denji hangs under the bar on a red string; a cyan crayon line climbs from him, a red one from the bar
    tw = math.sin(t * 40) * 3
    line(cv, polyline([(W * 0.5, BAR_Y + BAR_T * 0.5), (W * 0.5 + tw, BAR_Y + H * 0.05)]), 3, HERO)
    put(cv, "kid", W * 0.5 + tw, BAR_Y + H * 0.05, 0.13, treat="mono", anchor=(0.5, 0.0))
    up = out_cubic(clamp01((t - 8.10) / 0.3))
    crayon(cv, polyline([(W * 0.5 + 18, BAR_Y - BAR_T), (W * 0.5 + 30, BAR_Y - H * 0.53)]), up, CYAN, CYAN_HI, 11, seed=4)
    crayon(cv, polyline([(W * 0.27, BAR_Y - BAR_T * 0.5), (W * 0.29, BAR_Y - H * 0.25)]), up, RED, RED_HI, 11, seed=5)


# ================================================================================================= 8.65 - 11.95 collage mask

MASK_H = 0.80
MASK_C = (W * 0.52, H * 0.95)          # anchored at the bottom: the head's crop edge stays off frame


def draw_mask(cv, y_off=0.0, hands_in=0.0, hands_up=1.0, sway=0.0):
    put(cv, "saw", MASK_C[0], MASK_C[1] + y_off, MASK_H, treat="metal", anchor=(0.5, 1.0))
    # two stone hands rise at the sides and frame the head without covering it
    up = (1 - hands_up) * H * 0.7
    for side in (-1, 1):
        dx = W * (0.41 - 0.03 * hands_in)
        put(cv, "hand", W * 0.5 + side * dx, H * 1.08 + up + sway * side, 0.58, treat="stonehand",
            anchor=(0.80, 0.98), rot=side * (20 - hands_in * 8), flip=side < 0)


@tl.scene(8.65, 8.90)
def s13_mask_drop(c):
    full_bg(c.cv, relief_bg())
    k = out_cubic(clamp01((step(c.lt) + 0.08) / 0.15))
    draw_mask(c.cv, y_off=mix(-H * 0.9, 0, k), hands_up=0.0)


@tl.post(8.65, 8.74)
def p13(rgb_, c):
    return dir_blur(rgb_, 0, 220 * (1 - c.u * 0.6))


@tl.scene(8.90, 10.65)
def s14_mask_hold(c):
    full_bg(c.cv, relief_bg())
    t = c.t
    up = [0.33, 0.66, 1.0][min(2, int((t - 8.90) / 0.17))] if t < 9.40 else 1.0
    cin = smooth(clamp01((step(t) - 9.40) / 0.50))
    sway = 0.0 if 9.95 <= t < 10.45 else math.sin(step(t) * 9) * H * 0.012
    draw_mask(c.cv, hands_in=cin, hands_up=up, sway=sway)


def eye_point():
    f = cut("saw").frames[0]
    return img_point("saw", 0.66 * f.shape[1], 0.30 * f.shape[0], MASK_C[0], MASK_C[1], MASK_H, treat="metal",
                     anchor=(0.5, 1.0))


def chrome_ring(cv, cx, cy, R, band, rot=0.0):
    p = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=band)
    m = skia.Matrix()
    m.setRotate(rot, cx, cy)
    sh = skia.GradientShader.MakeSweep(cx, cy, [cint((0.10, 0.10, 0.12)), cint((0.95, 0.96, 0.98)), cint((0.18, 0.18, 0.21)),
                                                cint((0.05, 0.05, 0.06)), cint((0.80, 0.82, 0.86)), cint((0.12, 0.12, 0.14)),
                                                cint((0.10, 0.10, 0.12))], None, skia.TileMode.kClamp, 0, 360, 0, m)
    p.setShader(sh)
    cv.drawCircle(cx, cy, R, p)


def clock_hand(cv, cx, cy, length, ang, col, width):
    x1, y1 = cx + math.cos(math.radians(ang)) * length, cy + math.sin(math.radians(ang)) * length
    cv.drawLine(cx, cy, x1, y1, paint(col, 1.0, stroke=width))
    cap = skia.RRect.MakeRectXY(skia.Rect(-width * 1.6, -width * 1.2, width * 1.6, width * 1.2), width, width)
    cv.save()
    cv.translate(x1, y1)
    cv.rotate(ang)
    cv.drawRRect(cap, paint(col))
    cv.restore()


@tl.scene(10.65, 11.95)
def s15_hud(c):
    cv = c.cv
    t = c.t
    flicker = 11.40 <= t < 11.60 and int(t * 24) % 2 == 0
    if not flicker:
        full_bg(cv, relief_bg())
    draw_mask(cv, hands_in=1.0, sway=math.sin(step(t) * 9) * H * 0.010)
    ex, ey = eye_point()
    if t < 10.80:
        cv.drawCircle(ex, ey, 46, paint(INK, 0.9, stroke=3))
        brush(cv, bezier((ex - 60, ey - 10), (ex - 20, ey - 70), (ex + 40, ey + 60), (ex + 70, ey)), 6, HERO, bristles=3, seed=4)
        return
    k = [0.4, 0.7, 1.0][min(2, int((t - 10.80) / 0.05))]
    amber = rgb("E2A93B")
    rings(cv, ex, ey, [r * k for r in (40, 70, 100, 135, 165)], 4.0, amber, p=1.0)       # Makima's ringed eye
    rings(cv, ex, ey, [r * k for r in (52, 118, 210)], 2.0, CYAN, p=1.0)
    chrome_ring(cv, W * 0.5, H * 0.5, H * 0.50 * k, H * 0.045, rot=8 * int((t - 10.85) / 0.1))
    ang0 = -90 + 8 * int((t - 10.85) / 0.1)
    clock_hand(cv, ex, ey, 260 * k, ang0, HERO, 7)
    clock_hand(cv, ex, ey, 190 * k, ang0 + 120, NAVY, 6)
    clock_hand(cv, ex, ey, 330 * k, ang0 + 220, TEAL, 5)


# ================================================================================================= 11.95 - 13.45 disc, Aki bowling

def disc_image():
    if "disc" not in AS._bg:
        fr = core.Frame()
        cv = fr.clear()
        full_bg(cv, relief_bg())
        draw_mask(cv, hands_in=1.0)
        a = fr.array()
        ex, ey = eye_point()
        cx, cy, R = int(W * 0.5), int(H * 0.50), int(H * 0.42)
        crop = a[cy - R:cy + R, cx - R:cx + R]
        m = np.zeros(crop.shape[:2], np.uint8)
        cv2.circle(m, (R, R), R - 2, 255, -1, cv2.LINE_AA)
        rim = cv2.GaussianBlur((m > 0).astype(np.float32), (0, 0), R * 0.08)
        crop = (crop * (0.55 + 0.45 * rim[..., None])).astype(np.uint8)
        AS._bg["disc"] = to_image(np.dstack([crop, m]))
    return AS._bg["disc"]


BOWL = dict(cx=W * 0.36, cy=H * 0.32, h=0.31)


def ball_in_hand():
    hx, hy = extreme("bowl", "right")
    return img_point("bowl", hx, hy, BOWL["cx"], BOWL["cy"], BOWL["h"], treat="olive")


@tl.scene(11.95, 12.65)
def s16_disc(c):
    t = c.t
    d = 0.71 if t < 12.25 else 0.41 if t < 12.45 else 0.71 if t < 12.55 else 0.22
    if t >= 12.25:
        put(c.cv, "bowl", BOWL["cx"], BOWL["cy"], BOWL["h"], treat="olive")
    im = disc_image()
    draw_image(c.cv, im, W * 0.46, H * 0.46, d * H / im.height())


@tl.scene(12.65, 13.45)
def s17_bowl(c):
    cv = c.cv
    t = c.t
    bx, by = ball_in_hand()
    if t < 13.30:
        put(cv, "bowl", BOWL["cx"], BOWL["cy"], BOWL["h"], treat="olive")
        if t < 13.25:
            bowling_ball(cv, bx, by + 6, H * 0.04)
            return
    k = clamp01((t - 13.25) / 0.2)
    if t >= 13.30:
        put(cv, "bowl", BOWL["cx"] - k * 500, BOWL["cy"] - k * 300, BOWL["h"], treat="olive", blur=12)
    layer(cv, blur=10)
    bowling_ball(cv, bx + k * 1300, by + k * 820, H * 0.06)
    cv.restore()


@tl.post(13.20, 13.25)
def p18_matte(rgb_, c):
    fr = core.Frame()
    cv = fr.clear((0.012, 0.012, 0.012))
    put(cv, "bowl", BOWL["cx"], BOWL["cy"], BOWL["h"], treat="white")
    return fr.array()


@tl.post(13.33, 13.45)
def p19_whip(rgb_, c):
    return dir_blur(rgb_, 300, 190)


# ================================================================================================= 13.45 - 17.60 flying duo

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
        cv.drawLine(cx, cy, cx - dx * ln, cy - dy * ln, paint(cols[j % len(cols)], a * rng.uniform(0.45, 0.9),
                                                             stroke=3.0 if not vertical else rng.uniform(3, 6), cap="butt"))


RAIN_COLS = [rgb("273150"), rgb("505D87"), rgb("A7B3ED"), rgb("A6E7F7"), rgb("638CD0"), HERO]
LEAD = (W * 0.58, H * 0.45)
SECOND = (W * 0.70, H * 0.64)


def flying_duo(cv, t, sc=1.0, to=None, k_to=0.0):
    j = np.random.default_rng(int(step(t) * 12)).uniform(-5, 5, 2)
    figs = [("puppet", LEAD, 0.27, -30), ("power_fly", SECOND, 0.29, 0)]
    for name, (x, y), h, rot in figs:
        if to is not None:
            x, y = mix(x, to[0], k_to), mix(y, to[1], k_to)
        h *= sc
        # continuous light smear up-left behind each figure: red farthest, then blue, then cyan nearest
        for k in range(9, 0, -1):
            col = [rgb("A6E7F7"), rgb("638CD0"), rgb("E86A5C")][min(2, (k - 1) // 3)]
            put(cv, name, x - k * 26 * sc + j[0], y - k * 16 * sc + j[1], h, treat="navy", rot=rot, alpha=0.16,
                cfilter=tint_filter(col, 1.0, keep_luma=False), blur=10 + k * 2)
        put(cv, name, x + j[0], y + j[1], h, treat="navy", rot=rot)


def rails(cv, t):
    for k, (off, col) in enumerate(((-300, rgb("55C0C9")), (-240, HERO))):
        pth = polyline([(W * 0.02 + off, -40), (W * 0.02 + off + H * 1.25, H + 40)])
        line(cv, pth, 4, INK)
        u = (step(t) * 0.55 + k * 0.4) % 1.2 - 0.1
        line_part(cv, pth, max(0, u), min(1, u + 0.2), 5, col)


@tl.scene(13.45, 17.60)
def s20_flying(c):
    cv = c.cv
    t = c.t
    rain(cv, t, RAIN_COLS, n=90)
    rails(cv, t)
    # a chainsaw head passes through the left of frame every two beats, behind the duo
    for t0 in (13.85, 15.25, 16.50):
        if t0 <= t < t0 + 0.30:
            k = int((t - t0) / 0.1)
            x, y = [(W * 0.30, H * 1.05), (W * 0.20, H * 0.55), (W * 0.08, H * 0.05)][min(2, k)]
            put(cv, "saw", x, y, 0.40, rot=-30, blur=12, alpha=0.9)
    if t < 17.55:
        flying_duo(cv, t)
    else:
        put(cv, "pochita", W * 0.5, H * (1.4 - (t - 17.55) * 8), 0.48)


# ================================================================================================= 17.60 - 20.00 Pochita, the cord

POCH = dict(cx=W * 0.5, cy=H * 0.95, h=0.48)


def pochita(cv, y_off=0.0, treat=None, h=None, cx=None, cy=None):
    h = POCH["h"] if h is None else h
    cx = POCH["cx"] if cx is None else cx
    cy = (POCH["cy"] if cy is None else cy) + y_off
    im = img("pochita", 0, treat)
    s = h * H / im.height()
    # the chainsaw handle loop on his head, drawn as a vector
    top = cy - im.height() * s
    hw, hh = im.width() * s * 0.22, im.height() * s * 0.20
    arch = skia.Path()
    arch.moveTo(cx - hw, top + hh * 0.5)
    arch.lineTo(cx - hw, top - hh * 0.35)
    arch.quadTo(cx - hw, top - hh, cx - hw * 0.5, top - hh)
    arch.lineTo(cx + hw * 0.5, top - hh)
    arch.quadTo(cx + hw, top - hh, cx + hw, top - hh * 0.35)
    arch.lineTo(cx + hw, top + hh * 0.5)
    cv.drawPath(arch, paint(rgb("2E3B3E"), 1.0, stroke=hh * 0.22, cap="round"))
    put(cv, "pochita", cx, cy, h, treat=treat, anchor=(0.5, 1.0))
    return cx, top


@tl.scene(17.60, 18.75)
def s21_pochita(c):
    cv = c.cv
    t = c.t
    line(cv, bezier((0, H * 0.05), (W * 0.2, H * 0.1), (W * 0.35, H * 0.30), (W * 0.47, H * 0.48)), 9, INK)
    if t < 17.80:
        k = (t - 17.60) / 0.20
        flying_duo(cv, t, sc=mix(1.0, 0.2, k), to=(W * 0.5, H * 0.55), k_to=k)
        cv.drawLine(LEAD[0] * (1 - k) + W * 0.5 * k, LEAD[1] * (1 - k) + H * 0.55 * k, W * 0.5, H * 0.55,
                    paint(rgb("638CD0"), 0.7, stroke=26, blur=5))
    hit = any(abs(t - x) < 0.045 for x in (17.90, 18.31))
    pochita(cv, treat="red" if hit else None)
    if t >= 17.90 and int(t * 12) % 2 == 0:
        for k in range(6):
            ang = math.radians(-150 + k * 24)
            r0, r1 = H * 0.32, H * 0.37
            cx, cy = W * 0.5, H * 0.72
            cv.drawLine(cx + math.cos(ang) * r0, cy + math.sin(ang) * r0, cx + math.cos(ang) * r1, cy + math.sin(ang) * r1,
                        paint(HERO, 1.0, stroke=7))
    if 18.30 <= t < 18.47:
        hey(cv, W * 0.63, H * 0.45, t)


LINE_X = W * 0.40


def line_shape(t):
    """the thin red line (the starter cord) wobbling up: returns (path, tip)."""
    lt = step(t - 18.75)
    sway = math.sin(lt * 6.5 + 0.6) * 40
    tail = H * 1.05 + lt * 120                 # the tail drifts down as the camera tilts up after the line
    tip_y = mix(H * 0.75, H * 0.40, out_cubic(clamp01(lt / 0.25)))
    kink = clamp01((t - 19.70) / 0.08)
    tip = (LINE_X + sway * 0.6 + kink * 70, tip_y - kink * 30)
    pth = bezier((LINE_X - sway * 0.5, tail), (LINE_X - sway, mix(tail, tip_y, 0.35)), (LINE_X + sway, mix(tail, tip_y, 0.7)), tip)
    return pth, tip


@tl.scene(18.75, 19.80)
def s22_line_up(c):
    cv = c.cv
    t = c.t
    if t < 18.85:
        pochita(cv, y_off=(t - 18.75) * 2500)
        splatter(cv, W * 0.5, H * 0.62, 300, rgb("B5120A"), p=(t - 18.75) / 0.1, seed=12)
    pth, tip = line_shape(t)
    brush(cv, pth, 8, HERO, bristles=3, dry=0.0, seed=1, taper=0.25)


def cone(cv, tip, s, ang=-20.0):
    """flat blood-red cone growing from the cord's tip, its wide end (dark cap) toward camera."""
    cv.save()
    cv.translate(*tip)
    cv.rotate(ang)
    ln, r = 0.30 * W * s, 0.16 * H * s
    p = skia.Path()
    p.moveTo(0, -4)
    p.lineTo(ln, -r)
    p.lineTo(ln, r)
    p.lineTo(0, 4)
    p.close()
    cv.drawPath(p, paint(HERO))
    cv.drawOval(skia.Rect(ln - r * 0.35, -r, ln + r * 0.35, r), paint(rgb("19181C")))
    cv.restore()


@tl.scene(19.80, 20.00)
def s23_cone(c):
    cv = c.cv
    _, tip = line_shape(19.799)
    s = mix(0.6, 1.5, out_cubic(clamp01(c.lt / 0.1)))
    if c.t >= 19.90:
        put(cv, "arm", W * 0.62, H * 0.56, 1.05)
    brush(cv, line_shape(19.799)[0], 8, HERO, bristles=3, dry=0.0, seed=1, taper=0.25)
    cone(cv, tip, s)


# ================================================================================================= 20.00 - 21.70 climax

CLIMAX = [  # (start, cut-out, cx, cy, height, rotation)  - Chainsaw Man re-framed every 0.1-0.3 s
    (20.00, "arm", 0.56, 0.56, 1.20, 0), (20.10, "arm_b", 0.42, 0.60, 1.45, -8), (20.20, "saw", 0.55, 0.62, 1.05, -12),
    (20.30, "arm_c", 0.50, 0.50, 1.10, 4), (20.40, "arm", 0.60, 0.52, 1.50, 10), (20.60, "arm_b", 0.55, 0.58, 1.20, -6),
    (20.80, "saw", 0.45, 0.60, 1.35, 10), (21.10, "arm_c", 0.55, 0.52, 1.30, -8), (21.20, "arm", 0.44, 0.62, 1.45, -10),
    (21.40, "arm_b", 0.60, 0.55, 1.55, 6), (21.50, "arm_c", 0.48, 0.48, 1.45, 10), (21.60, "saw", 0.52, 0.62, 1.55, -4),
]
BLADE = {"arm": "topleft", "arm_b": "right", "arm_c": "botright", "saw": "topleft"}


def red_bar(cv, x, y, ang, length, thick):
    cv.save()
    cv.translate(x, y)
    cv.rotate(ang)
    p = skia.Path()
    p.moveTo(0, -thick * 0.30)
    p.lineTo(length, -thick * 0.55)
    p.lineTo(length, thick * 0.55)
    p.lineTo(0, thick * 0.30)
    p.close()
    cv.drawPath(p, paint(HERO))
    cv.drawOval(skia.Rect(length - thick * 0.22, -thick * 0.55, length + thick * 0.22, thick * 0.55), paint(rgb("19181C")))
    cv.restore()


@tl.scene(20.00, 21.70)
def s24_climax(c):
    cv = c.cv
    t = c.t
    _, name, cx, cy, h, rot = [f for f in CLIMAX if f[0] <= t][-1]
    px, py = extreme(name, BLADE[name])
    bx, by = img_point(name, px, py, cx * W, cy * H, h, rot=rot)
    # the red slash leaves the chainsaw blade and sweeps across the frame, widening toward camera
    to_c = math.degrees(math.atan2(H * 0.55 - by, W * 0.5 - bx))
    red_bar(cv, bx, by, to_c + 12, W * 1.4, H * 0.16 * h)
    put(cv, name, cx * W, cy * H, h, rot=rot)


@tl.scene(21.70, 22.55)
def s25_stroke(c):
    k = out_cubic(clamp01(step(c.lt) / 0.8))
    y0 = mix(H * 0.88, H * 0.55, k)
    tilt = mix(0.25, 0.02, k)
    pth = bezier((-100, y0 + W * tilt * 0.5), (W * 0.3, y0 + W * tilt * 0.25), (W * 0.7, y0 - W * tilt * 0.1),
                 (W + 100, y0 - W * tilt * 0.5))
    ribbon(c.cv, pth, 66, HERO, a=1.0, seed=5, rough=0.12)


# ================================================================================================= 22.55 - 24.00 wrapped head

FACE_H = 0.84


def wrapped_head(cv, x):
    """Denji's head wrapped in sagging red brush bandages, both eyes left clear; the shirt edge stays off frame."""
    put(cv, "face", x, H + 4, FACE_H, anchor=(0.5, 1.0))
    top = H + 4 - FACE_H * H
    eye_y = top + 0.47 * FACE_H * H
    hw = 0.62 * FACE_H * H
    ys = [top + 0.06 * H, top + 0.15 * H, top + 0.24 * H, eye_y + 0.085 * H, eye_y + 0.175 * H, eye_y + 0.265 * H]
    layer(cv)
    for k, yy in enumerate(ys):
        tilt = (4 if k % 2 else -5)
        dy = math.tan(math.radians(tilt)) * hw
        front = bezier((x - hw, yy - dy), (x - hw * 0.3, yy + 0.06 * H), (x + hw * 0.3, yy + 0.06 * H), (x + hw, yy + dy))
        ribbon(cv, front, 70, HERO if k % 2 == 0 else rgb("C8160A"), seed=30 + k, rough=0.16)
    im = img("face", 0, "dilate")
    p = skia.Paint()
    p.setBlendMode(skia.BlendMode.kDstIn)
    s_ = FACE_H * H / img("face").height()
    cv.save()
    cv.translate(x, H + 4)
    cv.scale(s_, s_)
    cv.drawImage(im, -im.width() / 2, -im.height(), skia.SamplingOptions(), p)
    cv.restore()
    cv.restore()


@tl.scene(22.55, 24.00)
def s26_wrapped(c):
    cv = c.cv
    k = out_cubic(clamp01(c.lt / 0.2))
    ribbon(cv, bezier((-100, H * 0.56), (W * 0.3, H * 0.55), (W * 0.6, H * 0.53), (W + 100, H * 0.55)), 66, HERO, seed=5, rough=0.12)
    wrapped_head(cv, mix(W * 1.4, W * 0.55, k))


@tl.post(22.55, 22.72)
def p26(rgb_, c):
    return dir_blur(rgb_, 380, 0)


# ================================================================================================= 24.00 - 26.40 echoes, glitch

def echoes(cv, t, kind, n):
    """flat-tinted copies of the screaming head fanned out at 14% W, full-colour head on top."""
    sp = W * 0.14
    order = sorted(range(-n // 2, n - n // 2), key=lambda q: -abs(q))
    for q in order:
        if q == 0:
            continue
        jy = np.random.default_rng(q * 7 + int(step(t) * 12)).uniform(-18, 18)
        put(cv, "scream", W * 0.47 + q * sp, H * 0.92 + jy, 0.58, treat=kind if q % 2 else kind + "2", anchor=(0.42, 1.0))
    put(cv, "scream", W * 0.47, H * 1.03, 0.72, treat="lift", anchor=(0.42, 1.0))


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
    k = int((c.t - 24.70) * 12)
    out = core.glitch(rgb_, 100 + k, 1.3)
    out[..., 0] = np.roll(out[..., 0], 9, axis=1)
    out[..., 2] = np.roll(out[..., 2], -9, axis=1)
    col = {2: rgb("1C2340"), 6: HERO}.get(k % 8)
    if col is not None:
        out = recolor(out, col, 0.40)
    return out


@tl.scene(25.50, 26.40)
def s30_echo_cyan(c):
    cv = c.cv
    t = c.t
    echoes(cv, t, "cyan", 10)
    if t >= 26.00:
        # a hand swings in from the right and flicks blood at him
        k = out_cubic(clamp01((t - 26.00) / 0.30))
        flick = math.sin(clamp01((t - 26.25) / 0.15) * math.pi) * 18
        put(cv, "hand", mix(W * 1.4, W * 0.82, k), H * 0.62, 0.70, rot=-30 - flick)


# ================================================================================================= 26.40 - 27.65 splash, close-ups

@tl.scene(26.40, 26.79)
def s31_splash(c):
    cv = c.cv
    t = c.t
    if t < 26.50:
        echoes(cv, t, "cyan", 10)
        put(cv, "hand", W * 0.82, H * 0.62, 0.70, rot=-30)
    if t < 26.45:
        splatter(cv, W * 0.5, H * 0.52, 240, HERO, p=1.0, seed=21)
    elif t < 26.50:
        splatter(cv, W * 0.5, H * 0.50, 560, HERO, p=1.0, seed=22)
    elif t < 26.625:
        fill(cv, HERO)
        # white crown of splash at the rim
        layer(cv)
        splatter(cv, W * 0.5, H * 0.5, 1300, (1, 1, 1), p=1.0, seed=24)
        cv.drawCircle(W * 0.5, H * 0.5, W * 0.52, paint(HERO, 1.0))
        cv.restore()
    else:
        k = (t - 26.625) / 0.165
        reveal_hole(cv, k)


def reveal_hole(cv, k):
    """the red fill opens from the centre with one big ragged hole."""
    noise = AS._bg.get("hole")
    if noise is None:
        rng = np.random.default_rng(5)
        n = cv2.GaussianBlur(rng.random((H // 4, W // 4)).astype(np.float32), (0, 0), 25)
        n = (n - n.min()) / (n.max() - n.min())
        yy, xx = np.mgrid[0:H // 4, 0:W // 4].astype(np.float32)
        r = np.sqrt(((xx - W / 8) / (W / 8)) ** 2 + ((yy - H / 8) / (H / 8)) ** 2) / 1.42
        noise = AS._bg["hole"] = cv2.resize(r * 0.75 + n * 0.25, (W, H))
    m = (noise > k * 1.05).astype(np.uint8) * 255
    rgba = np.zeros((H, W, 4), np.uint8)
    rgba[..., :3] = (np.array(HERO) * 255).astype(np.uint8)
    rgba[..., 3] = m
    draw_image(cv, to_image(rgba), 0, 0, 1.0, anchor=(0, 0))


CLOSEUPS = [(26.625, "power_cu", 0, 1.12), (27.02, "face", 0, 1.05), (27.27, "power_cu", 3, 1.12)]


@tl.scene(26.625, 27.55)
def s32_closeups(c):
    cv = c.cv
    t = c.t
    st, name, i, h = [x for x in CLOSEUPS if x[0] <= t][-1]
    punch = 1.08 if t - st >= 2 / 24 else 1.0
    if name == "power_cu":
        put(cv, name, W * 0.5, H + 4, h * punch, i=min(len(cut(name)) - 1, i + int((t - st) * 12)), anchor=(0.5, 1.0))
    else:
        put(cv, name, W * 0.5, H + 4, h * punch, anchor=(0.5, 1.0))
    if t < 26.79:
        reveal_hole(cv, (t - 26.625) / 0.165)


@tl.scene(27.55, 27.65)
def s34_eyes(c):
    if "eyes" not in AS._bg:
        f = full_frames("pv_teaser_2020", 44.25, 44.30, fps=24)[0]
        AS._bg["eyes"] = to_image(f)
    im = AS._bg["eyes"]
    k = 1.0 if c.t < 27.60 else 1.08
    draw_image(c.cv, im, W / 2, H / 2, k * W / im.width())


# ================================================================================================= 27.65 - 29.80 starter cord, gerbera

BIG_POCH = dict(cx=W * 0.50, cy=H * 1.12, h=1.05)


def pupils():
    """centres of Pochita's two dark pupils (image px), found as the two biggest dark blobs in his upper half."""
    if "pupils" not in AS._bg:
        f = cut("pochita").frames[0]
        g = cv2.cvtColor(f[..., :3], cv2.COLOR_RGB2GRAY)
        m = ((g < 70) & (f[..., 3] > 200)).astype(np.uint8)
        m[int(m.shape[0] * 0.6):] = 0
        n, lab, st, cen = cv2.connectedComponentsWithStats(m, 8)
        order = np.argsort(-st[1:, cv2.CC_STAT_AREA])[:2] + 1
        AS._bg["pupils"] = sorted([tuple(cen[k]) for k in order])
    return AS._bg["pupils"]


@tl.scene(27.65, 28.50)
def s35_cord(c):
    cv = c.cv
    t = c.t
    pull = clamp01((t - 27.75) / 0.15)
    punch = 1.06 if 27.75 <= t < 27.84 else 1.0
    h = BIG_POCH["h"] * punch
    hx_, top = pochita(cv, h=h, cx=BIG_POCH["cx"], cy=BIG_POCH["cy"])
    # the starter cord runs from his head to a hand that pinches its grip and yanks it
    hx, hy = mix(W * 0.74, W * 0.84, pull), mix(H * 0.20, H * 0.06, pull)
    if t < 27.70:
        hx, hy = W * 1.3, -H * 0.2
    elif t < 27.75:
        k_in = (t - 27.70) / 0.05
        hx, hy = mix(W * 1.3, W * 0.74, k_in), mix(-H * 0.2, H * 0.20, k_in)
    line(cv, bezier((hx_, top + 20), (hx_ + 40, top - 140), (hx - 260, hy + 40), (hx, hy)), 7, INK)
    cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(hx - 34, hy - 12, hx + 34, hy + 12), 10, 10), paint(INK))
    f = cut("hand").frames[0]
    px, py = hand_tips()[0]
    put(cv, "hand", hx, hy, 0.62, anchor=(px / f.shape[1], py / f.shape[0]), rot=-30)
    lit = clamp01((t - 27.78) / 0.12)
    if lit > 0:
        for px, py in pupils():
            x, y = img_point("pochita", px, py, BIG_POCH["cx"], BIG_POCH["cy"], h, anchor=(0.5, 1.0))
            cv.drawCircle(x, y, 0.045 * h * H, paint(rgb("01E1FD"), lit))


@tl.scene(28.50, 29.80)
def s36_flower(c):
    cv = c.cv
    t = c.t
    seg = 0 if t < 28.80 else 1 if t < 29.20 else 2
    k = [1.0, 0.67, 0.47][seg]
    prev = [1.0, 1.0, 0.67][seg]
    k = mix(prev, k, out_cubic(clamp01((t - [28.5, 28.8, 29.2][seg]) / 0.25)))
    fx_, fy_ = W * 0.5, H * 0.45
    rot = [0, 3, -2, 2, -3][int(step(t) * 4) % 5]
    for j in range(6):
        ang = math.radians(-160 + j * 28 + math.sin(t * 3 + j) * 1.5)
        r = H * 1.2
        pth = bezier((fx_, fy_), (fx_ + math.cos(ang) * r * 0.3, fy_ + math.sin(ang) * r * 0.2),
                     (fx_ + math.cos(ang) * r * 0.6, fy_ + math.sin(ang) * r * 0.7), (fx_ + math.cos(ang) * r, fy_ + math.sin(ang) * r))
        line(cv, pth, 4 + (j % 2) * 5, INK)
        u = ((t * 1.3 + j * 0.17) % 1.0)
        line_part(cv, pth, u, min(1, u + 0.08), 6 + (j % 2) * 5, rgb("2AB3EF"))
    put(cv, "flower", fx_, fy_ + H * 0.35 * k, 1.25 * k, anchor=(0.5, 0.42), rot=rot)


# ================================================================================================= 29.80 - 32.00 cables, chainsaw arm

@tl.scene(29.80, 30.10)
def s37_cables(c):
    cv = c.cv
    u = (c.t - 29.8) / 0.3
    line(cv, polyline([(-50, H * 0.42), (W + 50, H * 0.40)]), H * 0.023, INK)
    line(cv, polyline([(-50, H * 0.55), (W + 50, H * 0.57)]), 4, INK)
    line_part(cv, polyline([(-50, H * 0.42), (W + 50, H * 0.40)]), u, u + 0.2, H * 0.023, rgb("01E1FD"))


@tl.post(29.85, 29.95)
def p37(rgb_, c):
    return dir_blur(rgb_, 500, 0)


ARM_POSE = dict(cx=W * 0.70, cy=H * 0.28, h=0.36, rot=-28)


def arm_y(t):
    return mix(-H * 0.9, 0, out_cubic(clamp01(step(t - 30.10) / 0.25)))


def draw_arm(cv, t, treat=None, blur=0.0):
    sway = math.sin(step(t) * 6) * 3
    y = arm_y(t)
    put(cv, "sawarm", ARM_POSE["cx"], ARM_POSE["cy"] + y, ARM_POSE["h"], treat=treat, rot=ARM_POSE["rot"] + sway, blur=blur)
    return y, sway


def arm_point(name_px, y, sway):
    return img_point("sawarm", name_px[0], name_px[1], ARM_POSE["cx"], ARM_POSE["cy"] + y, ARM_POSE["h"],
                     rot=ARM_POSE["rot"] + sway)


@tl.scene(30.10, 31.60)
def s38_arm(c):
    cv = c.cv
    t = c.t
    y = arm_y(t)
    sway = math.sin(step(t) * 6) * 3
    f = cut("sawarm").frames[0]
    plug = arm_point((f.shape[1] * 0.70, f.shape[0] * 0.45), y, sway)
    cable = bezier((-50, H * 0.42), (W * 0.3, H * 0.44), (plug[0] - 300, plug[1] + 80), plug)
    line(cv, cable, H * 0.023, INK)
    u = ((t - 30.10) / 0.4) % 1.0
    line_part(cv, cable, u * 0.8, u * 0.8 + 0.2, H * 0.023, rgb("01E1FD"))
    draw_arm(cv, t, blur=8 if t < 30.30 else 0)
    tip = arm_point(extreme("sawarm", "left"), y, sway)
    if t >= 30.6:
        # blood runs along the underside of the blade toward its tip
        base = arm_point((f.shape[1] * 0.55, f.shape[0] * 0.62), y, sway)
        k = clamp01((t - 30.6) / 0.4)
        line(cv, polyline([base, (mix(base[0], tip[0], k), mix(base[1], tip[1], k) + 6)]), 7, HERO)
    drop = clamp01((t - 30.95) / 0.60)
    if drop > 0:
        r = 10 + drop * 10
        dp = skia.Path()
        x0, y0 = tip
        dp.moveTo(x0, y0)
        dp.cubicTo(x0 - r, y0 + r * 1.2, x0 - r, y0 + r * 2.4, x0, y0 + r * 2.4)
        dp.cubicTo(x0 + r, y0 + r * 2.4, x0 + r, y0 + r * 1.2, x0, y0)
        cv.drawPath(dp, paint(HERO))


@tl.post(31.60, 31.64)
def p39_matte(rgb_, c):
    fr = core.Frame()
    cv = fr.clear((0.012, 0.012, 0.012))
    draw_arm(cv, 31.6, treat="white")
    return fr.array()


@tl.scene(31.65, 32.00)
def s40_drop(c):
    cv = c.cv
    t = c.t
    rain(cv, t, [rgb("95EAF0")], n=24, vertical=True, speed=900, a=0.6, seed=8)
    y_arm = -(t - 31.65) * 4000
    if t < 31.72:
        draw_arm(cv, 31.6)
    tip = arm_point(extreme("sawarm", "left"), 0.0, math.sin(step(31.6) * 6) * 3)
    y = mix(tip[1], H * 1.3, (t - 31.65) / 0.35)
    cv.drawLine(tip[0], y - 240, tip[0], y, paint(HERO, 0.9, stroke=12))


@tl.post(31.70, 31.78)
def p40(rgb_, c):
    return dir_blur(rgb_, 0, 400)


# ================================================================================================= 32.00 - 34.40 bars, totem

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
    ph = min(2, int(((t - 32.0) - idx * 0.3) / 0.1))
    bw, bh, y, gap = W * 0.42, H * 0.045, H * 0.55, W * 0.025
    for side in (-1, 1):
        ang = [0, -20 * side, -28 * side][ph]
        dy = [0, 0, -H * 0.5][ph]
        layer(cv, blur=0 if ph == 0 else 0)
        # motion smear: stacked fading copies, then blurred
        for e in range(6, 0, -1):
            if ph == 0:
                break
            cv.save()
            cv.translate(W * 0.5 + side * (gap + bw / 2), y + dy + e * 14)
            cv.rotate(ang)
            cv.drawRect(skia.Rect(-bw / 2, -bh / 2, bw / 2, bh / 2), paint(col, 0.10, blur=10))
            cv.restore()
        cv.save()
        cv.translate(W * 0.5 + side * (gap + bw / 2), y + dy)
        cv.rotate(ang)
        cv.drawRect(skia.Rect(-bw / 2, -bh / 2, bw / 2, bh / 2), paint(col))
        cv.restore()
        cv.restore()


BOX_COLS = [rgb("E5210D"), rgb("0BCBCC"), rgb("0C2F9B"), rgb("9025DC"), (0, 0, 0), rgb("D02DC3")]
THUMBS = ["pochita", "saw", "makima", "kid", "hand", None]


def totem(cv, y_off=0.0, flash=None):
    cx, cy = W * 0.5, H * 0.46 + y_off
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
                im = img(name, 0)
                s = min(bw * 0.70 / im.width(), bh * 0.70 / im.height())
                draw_image(cv, im, x, y, s)
            else:
                text(cv, "chainsaw", x, y - 2, 12, FONT_MONO, INK)
                text(cv, "man", x, y + 13, 12, FONT_MONO, INK)
        cv.drawRect(r, paint(INK, 1.0, stroke=H * 0.003))


@tl.scene(33.00, END)
def s42_totem(c):
    t = c.t
    y = 0.0 if t >= 33.05 else -H * 0.6
    flash = min(5, int((t - 33.10) / 0.05)) if 33.10 <= t < 33.40 else None
    totem(c.cv, y, flash)


@tl.post(33.00, 33.05)
def p42(rgb_, c):
    return dir_blur(rgb_, 0, 300)


def preload():
    for n in CUTS:
        cut(n)
    relief_bg()
    paper_bg()
    paper_bg(True)
