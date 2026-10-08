"""Compositing layers: gameplay shots (playfield-aware crops in 2D/3D windows),
colour grades, backgrounds, rings, sparks, frames and post effects."""
import collections
import math
from functools import lru_cache

import cv2
import numpy as np

import gfx

# osu! playfield inside a 16:9 recording (fractions of width/height)
PF = dict(x=0.2, y=0.1167, w=0.6, h=0.8)


# ======================================================================= shots
class View:
    """What part of the source to show.
    zoom 1.0 = the whole playfield width; follow 0..1 = how much to track the action."""

    def __init__(self, zoom=1.0, follow=0.3, ox=0.0, oy=0.0, rot=0.0, flip=False):
        self.zoom, self.follow, self.ox, self.oy, self.rot, self.flip = zoom, follow, ox, oy, rot, flip


def view_quad(clip, st, view, aspect):
    sw, sh = clip.w, clip.h
    px, py, pw, ph = sw * PF["x"], sh * PF["y"], sw * PF["w"], sh * PF["h"]
    cw = pw / view.zoom
    ch = cw / aspect
    pfc = np.array([px + pw / 2, py + ph / 2])
    c = pfc * (1 - view.follow) + clip.centre(st) * view.follow + np.array([view.ox, view.oy]) * pw
    if cw < sw:
        c[0] = np.clip(c[0], cw / 2, sw - cw / 2)
    if ch < sh:
        c[1] = np.clip(c[1], ch / 2, sh - ch / 2)
    else:
        c[1] = sh / 2
    r = math.radians(view.rot)
    R = np.array([[math.cos(r), -math.sin(r)], [math.sin(r), math.cos(r)]])
    pts = np.array([[-cw / 2, -ch / 2], [cw / 2, -ch / 2], [cw / 2, ch / 2], [-cw / 2, ch / 2]]) @ R.T + c
    if view.flip:
        pts = pts[[1, 0, 3, 2]]
    return pts.astype(np.float32)


def rect_quad(x0, y0, x1, y1):
    return np.float32([[x0, y0], [x1, y0], [x1, y1], [x0, y1]])


def quad_size(q):
    return float(np.linalg.norm(q[1] - q[0])), float(np.linalg.norm(q[3] - q[0]))


def put_shot(canvas, frame, clip, st, view, dst, grade=None, alpha=1.0):
    """Draw the view of `frame` into the canvas quad `dst`. Returns homography src->canvas."""
    w, h = quad_size(dst)
    src = view_quad(clip, st, view, max(w, 1) / max(h, 1))
    if grade is None:
        return gfx.warp_image(canvas, frame, src, dst, alpha)
    # grade only the pixels we show
    H, W = canvas.shape[:2]
    x0, y0 = np.floor(dst.min(0)).astype(int)
    x1, y1 = np.ceil(dst.max(0)).astype(int)
    x0c, y0c, x1c, y1c = max(x0, 0), max(y0, 0), min(x1, W), min(y1, H)
    M = cv2.getPerspectiveTransform(np.float32(src), np.float32(dst))
    if x1c <= x0c or y1c <= y0c:
        return M
    T = np.array([[1, 0, -x0c], [0, 1, -y0c], [0, 0, 1]], np.float64)
    warped = cv2.warpPerspective(frame, T @ M, (x1c - x0c, y1c - y0c), flags=cv2.INTER_LINEAR,
                                 borderMode=cv2.BORDER_REPLICATE)
    warped = grade(warped)
    mask = np.zeros((y1c - y0c, x1c - x0c), np.uint8)
    cv2.fillConvexPoly(mask, np.round((dst - np.float32([x0c, y0c])) * 16).astype(np.int32), 255, cv2.LINE_AA, 4)
    m = mask[..., None].astype(np.float32) * (alpha / 255)
    roi = canvas[y0c:y1c, x0c:x1c]
    roi[:] = (roi.astype(np.float32) * (1 - m) + warped.astype(np.float32) * m).astype(np.uint8)
    return M


def map_point(M, p):
    v = M @ np.array([p[0], p[1], 1.0])
    return v[:2] / v[2]


# ======================================================================= grades
def _hex(c):
    return np.array(c, np.float32)


@lru_cache(maxsize=64)
def _duo_lut(dark, mid, light, contrast, gamma):
    x = np.arange(256) / 255.0
    l = np.clip((x ** gamma - 0.5) * contrast + 0.5, 0, 1)
    d, m, li = _hex(dark), _hex(mid), _hex(light)
    lo = np.clip(l * 2, 0, 1)[:, None]
    hi = np.clip(l * 2 - 1, 0, 1)[:, None]
    col = np.where(l[:, None] < 0.5, d * (1 - lo) + m * lo, m * (1 - hi) + li * hi)
    return np.clip(col[:, ::-1], 0, 255).astype(np.uint8).reshape(256, 1, 3)


@lru_cache(maxsize=64)
def _tint_lut(tint, contrast, lift, gamma):
    x = np.arange(256) / 255.0
    chans = []
    for c in (2, 1, 0):
        y = np.clip((x ** gamma - 0.5) * contrast + 0.5 + lift, 0, 1) * tint[c]
        chans.append(np.clip(y * 255, 0, 255).astype(np.uint8))
    return np.stack(chans, 1).reshape(256, 1, 3)


def make_grade(spec):
    """spec: {"type": "duo", "dark": rgb, "mid": rgb, "light": rgb} | {"type": "tint", "tint": rgb-mult,
    "sat": 1.3} | {"type": "bw"} | {"type": "neg"}; plus contrast / gamma / lift."""
    if spec is None:
        return None
    t = spec.get("type", "tint")
    con, gam = spec.get("contrast", 1.2), spec.get("gamma", 1.0)
    if t == "duo":
        lut = _duo_lut(tuple(spec["dark"]), tuple(spec["mid"]), tuple(spec["light"]), con, gam)

        def f(img):
            g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            return cv2.LUT(cv2.merge([g, g, g]), lut)
        return f
    if t == "bw":
        lut = _tint_lut(tuple(spec.get("tint", (1, 1, 1))), con, spec.get("lift", 0.0), gam)

        def f(img):
            g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            return cv2.LUT(cv2.merge([g, g, g]), lut)
        return f
    lut = _tint_lut(tuple(spec.get("tint", (1, 1, 1))), con, spec.get("lift", 0.0), gam)
    sat = spec.get("sat", 1.0)
    neg = t == "neg"

    def f(img):
        if neg:
            img = cv2.bitwise_not(img)
        if sat != 1.0:
            g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            img = cv2.addWeighted(img, sat, cv2.merge([g, g, g]), 1 - sat, 0)
        return cv2.LUT(img, lut)
    return f


# ======================================================================= backgrounds
def bg_blur(frame, W, H, grade=None, dim=0.4):
    sh, sw = frame.shape[:2]
    small = cv2.resize(frame, (96, 54), interpolation=cv2.INTER_AREA)
    cw = max(4, int(54 * W / H))
    small = small[:, (96 - cw) // 2:(96 - cw) // 2 + cw]
    small = cv2.GaussianBlur(small, (0, 0), 2.2)
    if grade:
        small = grade(small)
    bg = cv2.resize(small, (W, H), interpolation=cv2.INTER_LINEAR)
    return cv2.convertScaleAbs(bg, alpha=dim)


@lru_cache(maxsize=16)
def _gradient(W, H, top, bottom):
    g = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    img = _hex(top)[::-1] * (1 - g) + _hex(bottom)[::-1] * g
    return np.repeat(img, W, axis=1).astype(np.uint8)


def bg_gradient(W, H, top, bottom):
    return _gradient(W, H, tuple(top), tuple(bottom)).copy()


# ======================================================================= shapes
def ring(canvas, c, r, thick, color, alpha=1.0):
    if alpha <= 0.01 or r <= 1:
        return
    H, W = canvas.shape[:2]
    pad = r + thick + 2
    x0, y0 = int(max(0, c[0] - pad)), int(max(0, c[1] - pad))
    x1, y1 = int(min(W, c[0] + pad)), int(min(H, c[1] + pad))
    if x1 <= x0 or y1 <= y0:
        return
    roi = canvas[y0:y1, x0:x1]
    layer = roi.copy()
    cv2.circle(layer, (int((c[0] - x0) * 16), int((c[1] - y0) * 16)), int(r * 16), color[::-1], max(1, int(thick)),
               cv2.LINE_AA, 4)
    cv2.addWeighted(layer, alpha, roi, 1 - alpha, 0, dst=roi)


def shockwave(canvas, c, u, k=1.0, color=(255, 255, 255), size=1.0, dur=0.45):
    """Expanding approach-circle style ring burst."""
    if u < 0 or u > dur:
        return
    p = u / dur
    e = gfx.ease_out_expo(p)
    ring(canvas, c, (60 + 620 * e) * k * size, (26 * (1 - p) + 2) * k, color, (1 - p) ** 1.5)
    ring(canvas, c, (30 + 380 * e) * k * size, (10 * (1 - p) + 1) * k, color, 0.6 * (1 - p) ** 2)


def sparks(canvas, c, u, seed, k=1.0, n=26, color=(255, 230, 180), speed=1500, life=0.5):
    if u < 0 or u > life:
        return
    rs = np.random.default_rng(seed)
    ang = rs.uniform(0, 2 * np.pi, n)
    sp = rs.uniform(0.35, 1.0, n) * speed * k
    p = u / life
    for i in range(n):
        d = sp[i] * (u - 0.9 * u * u / life)
        tail = sp[i] * 0.022 * (1 - p)
        x, y = c[0] + math.cos(ang[i]) * d, c[1] + math.sin(ang[i]) * d + 300 * k * u * u
        x2, y2 = x - math.cos(ang[i]) * tail, y - math.sin(ang[i]) * tail
        a = (1 - p)
        col = tuple(int(v * a) for v in color[::-1])
        cv2.line(canvas, (int(x), int(y)), (int(x2), int(y2)), col, max(1, int(3 * k * (1 - p) + 1)), cv2.LINE_AA)


def quad_outline(canvas, q, color=(255, 255, 255), thick=3):
    cv2.polylines(canvas, [np.round(q * 16).astype(np.int32)], True, color[::-1], max(1, int(thick)), cv2.LINE_AA, 4)


def brackets(canvas, q, length, gap, color=(255, 255, 255), thick=4):
    """Corner brackets just outside a quad (TL, TR, BR, BL)."""
    c = q.mean(0)
    for i in range(4):
        p = q[i]
        out = (p - c) / (np.linalg.norm(p - c) + 1e-6) * gap
        a = q[(i + 1) % 4] - p
        b = q[(i - 1) % 4] - p
        a = a / (np.linalg.norm(a) + 1e-6) * length
        b = b / (np.linalg.norm(b) + 1e-6) * length
        p0 = p + out
        for d in (a, b):
            cv2.line(canvas, tuple(np.round(p0 * 16).astype(int)), tuple(np.round((p0 + d) * 16).astype(int)),
                     color[::-1], max(1, int(thick)), cv2.LINE_AA, 4)


def hit_circle(canvas, c, r, approach, color=(255, 60, 90), alpha=1.0, num="1", k=1.0):
    """osu! hit circle with approach circle (approach: 1 = far, 0 = on beat)."""
    if alpha <= 0.01:
        return
    H, W = canvas.shape[:2]
    pad = r * (1 + 3 * approach) + 12
    x0, y0 = int(max(0, c[0] - pad)), int(max(0, c[1] - pad))
    x1, y1 = int(min(W, c[0] + pad)), int(min(H, c[1] + pad))
    roi = canvas[y0:y1, x0:x1]
    layer = roi.copy()
    cc = (int((c[0] - x0) * 16), int((c[1] - y0) * 16))
    cv2.circle(layer, cc, int(r * 16), tuple(int(v * 0.6) for v in color[::-1]), -1, cv2.LINE_AA, 4)
    cv2.circle(layer, cc, int(r * 0.82 * 16), color[::-1], -1, cv2.LINE_AA, 4)
    cv2.circle(layer, cc, int(r * 16), (255, 255, 255), max(2, int(9 * k)), cv2.LINE_AA, 4)
    ar = r * (1 + 2.8 * approach)
    cv2.circle(layer, cc, int(ar * 16), color[::-1], max(2, int(6 * k)), cv2.LINE_AA, 4)
    cv2.addWeighted(layer, alpha, roi, 1 - alpha, 0, dst=roi)
    spr = gfx.text_sprite(num, int(r * 1.1), "unb", (255, 255, 255))
    gfx.blit(canvas, spr, c[0], c[1] + r * 0.05, 1.0, 0, alpha)


# ======================================================================= post
class Post:
    def __init__(self, W, H):
        self.W, self.H = W, H
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
        v = np.clip(1 - 0.6 * np.clip(r - 0.5, 0, None) ** 1.6, 0, 1)
        self.vig = cv2.merge([(v * 255).astype(np.uint8)] * 3)
        rs = np.random.default_rng(1)
        self.grain = []
        for _ in range(4):
            g = rs.normal(0, 1, (H // 2, W // 2)).astype(np.float32)
            g = cv2.resize(g, (W, H), interpolation=cv2.INTER_NEAREST)
            pos = np.clip(g * 6, 0, 255).astype(np.uint8)
            neg = np.clip(-g * 6, 0, 255).astype(np.uint8)
            self.grain.append((cv2.merge([pos] * 3), cv2.merge([neg] * 3)))
        lines = (np.arange(H) % 4 < 2).astype(np.float32)
        self.scan = cv2.merge([((1 - 0.22 * lines[:, None]) * 255 * np.ones((1, W))).astype(np.uint8)] * 3)
        self.echo = collections.deque(maxlen=10)
        self.xx = np.tile(np.arange(W, dtype=np.float32), (H, 1))
        self.yy = np.tile(np.arange(H, dtype=np.float32)[:, None], (1, W))

    def bloom(self, img, amount, thresh=120):
        if amount <= 0:
            return img
        small = cv2.resize(img, (self.W // 6, self.H // 6), interpolation=cv2.INTER_AREA)
        small = cv2.subtract(small, (thresh, thresh, thresh, 0))
        small = cv2.GaussianBlur(small, (0, 0), 7)
        big = cv2.resize(small, (self.W, self.H), interpolation=cv2.INTER_LINEAR)
        return cv2.addWeighted(img, 1.0, big, amount, 0)

    def rgb_split(self, img, amount):
        if amount < 0.6:
            return img
        b, g, r = cv2.split(img)
        c = (self.W / 2, self.H / 2)
        k = amount / (self.W / 2)
        r = cv2.warpAffine(r, cv2.getRotationMatrix2D(c, 0, 1 + k), (self.W, self.H), borderMode=cv2.BORDER_REFLECT)
        b = cv2.warpAffine(b, cv2.getRotationMatrix2D(c, 0, 1 - k), (self.W, self.H), borderMode=cv2.BORDER_REFLECT)
        return cv2.merge([b, g, r])

    def zoom_blur(self, img, amount, center=None):
        if amount < 0.004:
            return img
        c = center if center is not None else (self.W / 2, self.H / 2)
        acc = img.astype(np.float32)
        for i in range(1, 5):
            M = cv2.getRotationMatrix2D((float(c[0]), float(c[1])), 0, 1 + amount * i)
            acc += cv2.warpAffine(img, M, (self.W, self.H), borderMode=cv2.BORDER_REFLECT)
        return (acc / 5).astype(np.uint8)

    def dir_blur(self, img, length, vertical=True):
        L = int(length)
        if L < 3:
            return img
        return cv2.blur(img, (1, L) if vertical else (L, 1))

    def glitch(self, img, amount, seed):
        if amount <= 0:
            return img
        rs = np.random.default_rng(seed)
        out = img.copy()
        for _ in range(int(4 + 10 * amount)):
            y = int(rs.integers(0, self.H - 40))
            h = int(rs.integers(8, int(30 + 160 * amount)))
            dx = int(rs.choice([-1, 1]) * rs.integers(15, int(40 + 200 * amount)))
            out[y:y + h] = np.roll(out[y:y + h], dx, axis=1)
            ch = int(rs.integers(0, 3))
            out[y:y + h, :, ch] = np.roll(out[y:y + h, :, ch], dx // 2, axis=1)
        return out

    def slices(self, img, n, offsets):
        """Shift n horizontal slices by per-slice pixel offsets (black fill)."""
        out = np.zeros_like(img)
        hs = self.H / n
        for i in range(n):
            y0, y1 = int(i * hs), int((i + 1) * hs)
            dx = int(offsets[i])
            if abs(dx) >= self.W:
                continue
            if dx >= 0:
                out[y0:y1, dx:] = img[y0:y1, :self.W - dx]
            else:
                out[y0:y1, :self.W + dx] = img[y0:y1, -dx:]
        return out

    def wobble(self, img, amp, t, freq=0.045):
        if amp < 0.5:
            return img
        mx = self.xx + amp * np.sin(self.yy * freq + t * 25).astype(np.float32)
        return cv2.remap(img, mx, self.yy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

    def scanlines(self, img):
        return cv2.multiply(img, self.scan, scale=1 / 255)

    def finish(self, img, fi, grain=1.0, vignette=True):
        if vignette:
            img = cv2.multiply(img, self.vig, scale=1 / 255)
        if grain > 0:
            pos, neg = self.grain[fi % 4]
            if grain != 1.0:
                pos = cv2.convertScaleAbs(pos, alpha=grain)
                neg = cv2.convertScaleAbs(neg, alpha=grain)
            img = cv2.subtract(cv2.add(img, pos), neg)
        return img


def flash(img, amount, color=(255, 255, 255)):
    if amount <= 0.01:
        return img
    layer = np.empty_like(img)
    layer[:] = color[::-1]
    return cv2.addWeighted(img, 1 - min(1.0, amount), layer, min(1.0, amount), 0)


def dim(img, amount):
    return img if amount <= 0 else cv2.convertScaleAbs(img, alpha=max(0.0, 1 - amount))


def speed_lines(canvas, c, amount, seed, k=1.0, n=56, color=(255, 255, 255)):
    """Radial speed streaks around point c (hyperspace / impact lines)."""
    if amount <= 0.02:
        return
    rs = np.random.default_rng(seed)
    H, W = canvas.shape[:2]
    R = math.hypot(W, H)
    col = tuple(int(v * min(1.0, amount)) for v in color[::-1])
    for _ in range(n):
        a = rs.uniform(0, 2 * np.pi)
        r0 = rs.uniform(0.12, 0.55) * R * (1 - 0.4 * amount)
        ln = rs.uniform(0.08, 0.32) * R * amount
        d = np.array([math.cos(a), math.sin(a)])
        p0 = np.array(c) + d * r0
        p1 = np.array(c) + d * (r0 + ln)
        cv2.line(canvas, tuple(int(v) for v in p0), tuple(int(v) for v in p1), col,
                 max(1, int(rs.uniform(1, 4) * k)), cv2.LINE_AA)


def screen(a, b):
    """Screen blend of two uint8 images."""
    return cv2.subtract(255, cv2.multiply(cv2.subtract(255, a), cv2.subtract(255, b), scale=1 / 255))
