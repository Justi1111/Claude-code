"""Small 2D graphics helpers: text sprites, alpha blits, easing."""
from functools import lru_cache

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT_DIR = "/usr/share/fonts/opentype/inter/"
FONTS = {
    "black": "InterDisplay-Black.otf",
    "black_i": "InterDisplay-BlackItalic.otf",
    "bold": "InterDisplay-Bold.otf",
    "bold_i": "InterDisplay-BoldItalic.otf",
    "semi": "Inter-SemiBold.otf",
    "regular": "Inter-Regular.otf",
    "mono": "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
}


@lru_cache(maxsize=64)
def font(name, size):
    path = FONTS.get(name, name)
    if not path.startswith("/"):
        path = FONT_DIR + path
    return ImageFont.truetype(path, size)


@lru_cache(maxsize=512)
def text_sprite(text, size, fname="black_i", color=(255, 255, 255), stroke=0,
                stroke_color=(0, 0, 0), glow=0, glow_color=None, tracking=0):
    """Render text to a premultiplied-free BGRA uint8 array. Colors are RGB."""
    f = font(fname, size)
    pad = stroke + glow * 3 + 8
    if tracking:
        widths = [f.getlength(c) + tracking for c in text]
        w = int(sum(widths)) + pad * 2
    else:
        w = int(f.getlength(text)) + pad * 2
    asc, desc = f.getmetrics()
    h = asc + desc + pad * 2
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def draw(dr, fill, sw=0, sf=None):
        if tracking:
            x = pad
            for c, cw in zip(text, widths):
                dr.text((x, pad), c, font=f, fill=fill, stroke_width=sw, stroke_fill=sf)
                x += cw
        else:
            dr.text((pad, pad), text, font=f, fill=fill, stroke_width=sw, stroke_fill=sf)

    if glow:
        g = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw(ImageDraw.Draw(g), tuple(glow_color or color) + (255,), stroke + 2, tuple(glow_color or color) + (255,))
        g = g.filter(ImageFilter.GaussianBlur(glow))
        img = Image.alpha_composite(img, g)
        d = ImageDraw.Draw(img)
    draw(d, tuple(color) + (255,), stroke, tuple(stroke_color) + (255,) if stroke else None)
    a = np.array(img)
    return np.ascontiguousarray(a[:, :, [2, 1, 0, 3]])


def blit(frame, spr, cx, cy, scale=1.0, angle=0.0, alpha=1.0, add=False):
    """Composite BGRA sprite onto BGR frame, centered at (cx, cy)."""
    if alpha <= 0.003 or scale <= 0.01:
        return
    H, W = frame.shape[:2]
    h, w = spr.shape[:2]
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
    roi = frame[y0c:y1c, x0c:x1c]
    a = warped[:, :, 3:4].astype(np.float32) * (alpha / 255.0)
    src = warped[:, :, :3].astype(np.float32)
    if add:
        out = roi.astype(np.float32) + src * a
    else:
        out = roi.astype(np.float32) * (1 - a) + src * a
    roi[:] = np.clip(out, 0, 255).astype(np.uint8)


def rounded_rect(w, h, r, color_rgba):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle((0, 0, w - 1, h - 1), r, fill=tuple(color_rgba))
    return img


def pil_to_bgra(img):
    a = np.array(img.convert("RGBA"))
    return np.ascontiguousarray(a[:, :, [2, 1, 0, 3]])


# ---------------------------------------------------------------- easing
def clamp01(x):
    return max(0.0, min(1.0, x))


def ease_out_cubic(x):
    x = clamp01(x)
    return 1 - (1 - x) ** 3


def ease_in_cubic(x):
    x = clamp01(x)
    return x ** 3


def ease_in_out(x):
    x = clamp01(x)
    return 3 * x * x - 2 * x * x * x


def ease_out_back(x, s=1.9):
    x = clamp01(x) - 1
    return x * x * ((s + 1) * x + s) + 1


def ease_in_expo(x):
    x = clamp01(x)
    return 0 if x == 0 else 2 ** (10 * x - 10)
