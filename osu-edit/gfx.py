"""2D/2.5D graphics helpers: fonts, text sprites, alpha + perspective blits, easing."""
import math
import os
from functools import lru_cache

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
INTER = "/usr/share/fonts/opentype/inter/"
FONTS = {
    # display
    "anton": (os.path.join(HERE, "fonts/Anton-Regular.ttf"), None),
    "unb": (os.path.join(HERE, "fonts/Unbounded[wght].ttf"), b"Black"),
    "unb_bold": (os.path.join(HERE, "fonts/Unbounded[wght].ttf"), b"Bold"),
    "archivo": (os.path.join(HERE, "fonts/ArchivoBlack-Regular.ttf"), None),
    "bebas": (os.path.join(HERE, "fonts/BebasNeue-Regular.ttf"), None),
    "mono": (os.path.join(HERE, "fonts/SpaceMono-Bold.ttf"), None),
    "kr": (os.path.join(HERE, "fonts/NotoSansKR[wght].ttf"), b"Black"),
    "kr_bold": (os.path.join(HERE, "fonts/NotoSansKR[wght].ttf"), b"Bold"),
    # inter (system)
    "black": (INTER + "InterDisplay-Black.otf", None),
    "black_i": (INTER + "InterDisplay-BlackItalic.otf", None),
    "bold": (INTER + "InterDisplay-Bold.otf", None),
    "bold_i": (INTER + "InterDisplay-BoldItalic.otf", None),
    "semi": (INTER + "Inter-SemiBold.otf", None),
    "regular": (INTER + "Inter-Regular.otf", None),
}


@lru_cache(maxsize=128)
def font(name, size):
    path, var = FONTS.get(name, (name, None))
    f = ImageFont.truetype(path, max(1, int(size)))
    if var:
        f.set_variation_by_name(var)
    return f


def _masks(text, f, stroke, pad, tracking):
    """Return (fill_mask, stroke_mask) as L images for the text."""
    asc, desc = f.getmetrics()
    if tracking:
        adv = [f.getlength(c) + tracking for c in text]
        w = int(sum(adv) - tracking) + pad * 2
    else:
        adv = None
        w = int(math.ceil(f.getlength(text))) + pad * 2
    h = asc + desc + pad * 2
    fill = Image.new("L", (max(w, 1), h), 0)
    strk = Image.new("L", (max(w, 1), h), 0)
    df, ds = ImageDraw.Draw(fill), ImageDraw.Draw(strk)
    if adv:
        x = pad
        for c, a in zip(text, adv):
            df.text((x, pad), c, font=f, fill=255)
            if stroke:
                ds.text((x, pad), c, font=f, fill=255, stroke_width=stroke, stroke_fill=255)
            x += a
    else:
        df.text((pad, pad), text, font=f, fill=255)
        if stroke:
            ds.text((pad, pad), text, font=f, fill=255, stroke_width=stroke, stroke_fill=255)
    return fill, strk


@lru_cache(maxsize=2048)
def text_sprite(text, size, fname="black_i", color=(255, 255, 255), stroke=0,
                stroke_color=(0, 0, 0), glow=0, glow_color=None, tracking=0, outline_only=False):
    """Render text to a BGRA uint8 array. Colors are RGB.
    outline_only=True draws just the stroke (hollow letters)."""
    f = font(fname, size)
    pad = stroke + glow * 3 + 6
    fill, strk = _masks(text, f, stroke, pad, tracking)
    F = np.array(fill, np.float32) / 255
    Sm = np.array(strk, np.float32) / 255 if stroke else np.zeros_like(F)
    rgb = np.zeros(F.shape + (3,), np.float32)
    if outline_only:
        a = np.clip(Sm - F, 0, 1) if stroke else F
        rgb[:] = color
    else:
        a = np.maximum(F, Sm)
        rgb[:] = stroke_color
        rgb = rgb * (1 - F[..., None]) + np.array(color, np.float32) * F[..., None]
    if glow:
        g = Image.fromarray((np.maximum(F, Sm) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(glow))
        G = np.array(g, np.float32) / 255
        gc = np.array(glow_color or color, np.float32)
        ga = G * 0.9 * (1 - a)
        tot = a + ga
        rgb = (rgb * a[..., None] + gc * ga[..., None]) / np.maximum(tot, 1e-6)[..., None]
        a = np.clip(tot, 0, 1)
    out = np.dstack([rgb[..., 2], rgb[..., 1], rgb[..., 0], a * 255])
    return np.ascontiguousarray(np.clip(out, 0, 255).astype(np.uint8))


@lru_cache(maxsize=512)
def text_layout(text, size, fname, tracking=0):
    """Per-character x offsets (left edges, relative to the string's left) and total width."""
    f = font(fname, size)
    xs, x = [], 0.0
    for c in text:
        xs.append(x)
        x += f.getlength(c) + tracking
    return xs, x - tracking


def text_mask(text, size, fname, tracking=0, stroke=0):
    """Float32 alpha mask (0..1) of filled text."""
    f = font(fname, size)
    fill, strk = _masks(text, f, stroke, stroke + 6, tracking)
    m = np.maximum(np.array(fill), np.array(strk)) if stroke else np.array(fill)
    return m.astype(np.float32) / 255


# ---------------------------------------------------------------- compositing
def _composite(roi, src_bgr, a, add=False):
    """roi (uint8) <- src over roi with alpha a (float32 HxWx1)."""
    if add:
        out = roi.astype(np.float32) + src_bgr.astype(np.float32) * a
    else:
        out = roi.astype(np.float32) * (1 - a) + src_bgr.astype(np.float32) * a
    roi[:] = np.clip(out, 0, 255).astype(np.uint8)


def blit(frame, spr, cx, cy, scale=1.0, angle=0.0, alpha=1.0, add=False):
    """Composite BGRA sprite onto BGR frame, centred at (cx, cy) with rotation/scale."""
    if alpha <= 0.003 or scale <= 0.01:
        return
    H, W = frame.shape[:2]
    h, w = spr.shape[:2]
    if angle == 0 and abs(scale - 1) < 1e-3:
        x0, y0 = int(round(cx - w / 2)), int(round(cy - h / 2))
        xs, ys = max(0, -x0), max(0, -y0)
        x0c, y0c, x1c, y1c = max(0, x0), max(0, y0), min(W, x0 + w), min(H, y0 + h)
        if x1c <= x0c or y1c <= y0c:
            return
        part = spr[ys:ys + y1c - y0c, xs:xs + x1c - x0c]
        _composite(frame[y0c:y1c, x0c:x1c], part[:, :, :3], part[:, :, 3:4].astype(np.float32) * (alpha / 255), add)
        return
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, scale)
    M[0, 2] += cx - w / 2
    M[1, 2] += cy - h / 2
    corners = np.array([[0, 0, 1], [w, 0, 1], [0, h, 1], [w, h, 1]], np.float64) @ M.T
    x0, y0 = np.floor(corners.min(0)).astype(int)
    x1, y1 = np.ceil(corners.max(0)).astype(int)
    x0c, y0c, x1c, y1c = max(x0, 0), max(y0, 0), min(x1, W), min(y1, H)
    if x1c <= x0c or y1c <= y0c:
        return
    M2 = M.copy()
    M2[0, 2] -= x0c
    M2[1, 2] -= y0c
    warped = cv2.warpAffine(spr, M2, (x1c - x0c, y1c - y0c), flags=cv2.INTER_LINEAR,
                            borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    _composite(frame[y0c:y1c, x0c:x1c], warped[:, :, :3], warped[:, :, 3:4].astype(np.float32) * (alpha / 255), add)


def blit_clip(frame, spr, cx, cy, clip, alpha=1.0, add=False):
    """Unrotated blit restricted to clip=(x0, y0, x1, y1) — for mask reveals."""
    H, W = frame.shape[:2]
    h, w = spr.shape[:2]
    x0, y0 = int(round(cx - w / 2)), int(round(cy - h / 2))
    cx0, cy0 = max(0, int(clip[0])), max(0, int(clip[1]))
    cx1, cy1 = min(W, int(clip[2])), min(H, int(clip[3]))
    X0, Y0 = max(x0, cx0), max(y0, cy0)
    X1, Y1 = min(x0 + w, cx1), min(y0 + h, cy1)
    if X1 <= X0 or Y1 <= Y0 or alpha <= 0.003:
        return
    part = spr[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0]
    _composite(frame[Y0:Y1, X0:X1], part[:, :, :3], part[:, :, 3:4].astype(np.float32) * (alpha / 255), add)


def rot3d(rx, ry, rz):
    rx, ry, rz = map(math.radians, (rx, ry, rz))
    Rx = np.array([[1, 0, 0], [0, math.cos(rx), -math.sin(rx)], [0, math.sin(rx), math.cos(rx)]])
    Ry = np.array([[math.cos(ry), 0, math.sin(ry)], [0, 1, 0], [-math.sin(ry), 0, math.cos(ry)]])
    Rz = np.array([[math.cos(rz), -math.sin(rz), 0], [math.sin(rz), math.cos(rz), 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


def project_rect(w, h, cx, cy, scale=1.0, rx=0.0, ry=0.0, rz=0.0, f=1800.0):
    """Corners (TL, TR, BR, BL) of a w x h rectangle rotated in 3D and projected."""
    pts = np.array([[-w / 2, -h / 2, 0], [w / 2, -h / 2, 0], [w / 2, h / 2, 0], [-w / 2, h / 2, 0]]) * scale
    p = pts @ rot3d(rx, ry, rz).T
    z = np.maximum(p[:, 2] + f, 1.0)
    xy = p[:, :2] * (f / z)[:, None] + np.array([cx, cy])
    return xy.astype(np.float32)


def warp_sprite(frame, spr, dst, alpha=1.0, add=False):
    """Perspective-warp a BGRA sprite onto the quad dst (TL, TR, BR, BL)."""
    if alpha <= 0.003:
        return
    H, W = frame.shape[:2]
    h, w = spr.shape[:2]
    x0, y0 = np.floor(dst.min(0)).astype(int)
    x1, y1 = np.ceil(dst.max(0)).astype(int)
    x0c, y0c, x1c, y1c = max(x0, 0), max(y0, 0), min(x1, W), min(y1, H)
    if x1c <= x0c or y1c <= y0c:
        return
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    M = cv2.getPerspectiveTransform(src, (dst - np.float32([x0c, y0c])).astype(np.float32))
    warped = cv2.warpPerspective(spr, M, (x1c - x0c, y1c - y0c), flags=cv2.INTER_LINEAR,
                                 borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    _composite(frame[y0c:y1c, x0c:x1c], warped[:, :, :3], warped[:, :, 3:4].astype(np.float32) * (alpha / 255), add)


def warp_image(canvas, img, src_pts, dst, alpha=1.0):
    """Perspective-warp the src_pts quad of a BGR image onto the canvas quad dst,
    with an anti-aliased edge. Returns the homography (src -> canvas)."""
    H, W = canvas.shape[:2]
    M_full = cv2.getPerspectiveTransform(np.float32(src_pts), np.float32(dst))
    x0, y0 = np.floor(dst.min(0)).astype(int)
    x1, y1 = np.ceil(dst.max(0)).astype(int)
    x0c, y0c, x1c, y1c = max(x0, 0), max(y0, 0), min(x1, W), min(y1, H)
    if x1c <= x0c or y1c <= y0c or alpha <= 0.003:
        return M_full
    T = np.array([[1, 0, -x0c], [0, 1, -y0c], [0, 0, 1]], np.float64)
    warped = cv2.warpPerspective(img, T @ M_full, (x1c - x0c, y1c - y0c), flags=cv2.INTER_LINEAR,
                                 borderMode=cv2.BORDER_REPLICATE)
    mask = np.zeros((y1c - y0c, x1c - x0c), np.uint8)
    poly = np.round((dst - np.float32([x0c, y0c])) * 16).astype(np.int32)
    cv2.fillConvexPoly(mask, poly, 255, cv2.LINE_AA, 4)
    roi = canvas[y0c:y1c, x0c:x1c]
    if alpha >= 0.999:
        m = mask[..., None].astype(np.float32) / 255
    else:
        m = mask[..., None].astype(np.float32) * (alpha / 255)
    _composite(roi, warped, m)
    return M_full


def rounded_rect(w, h, r, color_rgba):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle((0, 0, w - 1, h - 1), r, fill=tuple(color_rgba))
    return img


def pil_to_bgra(img):
    a = np.array(img.convert("RGBA"))
    return np.ascontiguousarray(a[:, :, [2, 1, 0, 3]])


def hblur(spr, k):
    k = int(k)
    return spr if k < 2 else cv2.blur(spr, (k, 1))


def vblur(spr, k):
    k = int(k)
    return spr if k < 2 else cv2.blur(spr, (1, k))


# ---------------------------------------------------------------- easing
def clamp01(x):
    return max(0.0, min(1.0, x))


def lerp(a, b, t):
    return a + (b - a) * t


def ease_out_cubic(x):
    x = clamp01(x)
    return 1 - (1 - x) ** 3


def ease_in_cubic(x):
    x = clamp01(x)
    return x ** 3


def ease_in_out(x):
    x = clamp01(x)
    return 3 * x * x - 2 * x * x * x


def ease_in_out_cubic(x):
    x = clamp01(x)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def ease_out_back(x, s=1.9):
    x = clamp01(x) - 1
    return x * x * ((s + 1) * x + s) + 1


def ease_out_expo(x):
    x = clamp01(x)
    return 1.0 if x >= 1 else 1 - 2 ** (-10 * x)


def ease_in_expo(x):
    x = clamp01(x)
    return 0 if x == 0 else 2 ** (10 * x - 10)


def ease_in_out_expo(x):
    x = clamp01(x)
    if x in (0, 1):
        return x
    return 2 ** (20 * x - 10) / 2 if x < 0.5 else (2 - 2 ** (-20 * x + 10)) / 2


def ease_out_quint(x):
    x = clamp01(x)
    return 1 - (1 - x) ** 5


def spring(x, freq=3.0, damp=7.0):
    """0 -> 1 with a damped overshoot (x in seconds-ish units)."""
    if x <= 0:
        return 0.0
    return 1 - math.exp(-damp * x) * math.cos(2 * math.pi * freq * x)
