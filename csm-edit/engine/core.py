"""Drawing core for the collage edit: a skia canvas on off-white and the primitives the scenes are built from.

Everything is drawn in output pixels (1920x1080). Times are in seconds. Colours are (r, g, b) floats 0..1.
"""
import math
import subprocess

import numpy as np
import skia

W, H = 1920, 1080
FPS = 24
BG = (0.969, 0.969, 0.965)
INK = (0.07, 0.07, 0.08)
BLOOD = (0.62, 0.04, 0.05)
SAMPLING = skia.SamplingOptions(skia.FilterMode.kLinear, skia.MipmapMode.kLinear)


# ---------------------------------------------------------------- easing / timing

def clamp01(x):
    return 0.0 if x < 0 else 1.0 if x > 1 else float(x)


def mix(a, b, k):
    return a + (b - a) * k


def smooth(x):
    x = clamp01(x)
    return x * x * (3 - 2 * x)


def out_cubic(x):
    x = clamp01(x)
    return 1 - (1 - x) ** 3


def in_cubic(x):
    x = clamp01(x)
    return x ** 3


def in_out_cubic(x):
    x = clamp01(x)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def out_expo(x):
    x = clamp01(x)
    return 1.0 if x >= 1 else 1 - 2 ** (-10 * x)


def in_expo(x):
    x = clamp01(x)
    return 0.0 if x <= 0 else 2 ** (10 * x - 10)


def out_back(x, s=1.7):
    x = clamp01(x) - 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def prog(t, t0, t1, ease=smooth):
    """eased 0..1 progress of t through [t0, t1]."""
    if t1 <= t0:
        return 1.0 if t >= t1 else 0.0
    return ease((t - t0) / (t1 - t0))


def hold_frames(t, fps):
    """quantise time to a lower frame rate (animation 'on twos')."""
    return math.floor(t * fps + 1e-6) / fps


# ---------------------------------------------------------------- colour helpers

def c4(rgb, a=1.0):
    return skia.Color4f(float(rgb[0]), float(rgb[1]), float(rgb[2]), float(a))


def cint(rgb, a=1.0):
    return skia.Color4f(float(rgb[0]), float(rgb[1]), float(rgb[2]), float(a)).toColor()


def paint(rgb=INK, a=1.0, stroke=None, cap="round", blur=0.0, blend=None):
    p = skia.Paint(AntiAlias=True)
    p.setColor4f(c4(rgb, a))
    if stroke is not None:
        p.setStyle(skia.Paint.kStroke_Style)
        p.setStrokeWidth(float(stroke))
        p.setStrokeCap({"round": skia.Paint.kRound_Cap, "butt": skia.Paint.kButt_Cap, "square": skia.Paint.kSquare_Cap}[cap])
        p.setStrokeJoin(skia.Paint.kRound_Join)
    if blur > 0:
        p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, float(blur)))
    if blend is not None:
        p.setBlendMode(blend)
    return p


def tint_filter(rgb, amount=1.0, keep_luma=True):
    """colour filter that pushes an image toward rgb (multiplied by its luminance when keep_luma)."""
    r, g, b = rgb
    k = float(amount)
    if keep_luma:
        lr, lg, lb = 0.2126, 0.7152, 0.0722
        m = [mix(1, r * lr * 1.6, k), mix(0, r * lg * 1.6, k), mix(0, r * lb * 1.6, k), 0, 0,
             mix(0, g * lr * 1.6, k), mix(1, g * lg * 1.6, k), mix(0, g * lb * 1.6, k), 0, 0,
             mix(0, b * lr * 1.6, k), mix(0, b * lg * 1.6, k), mix(1, b * lb * 1.6, k), 0, 0,
             0, 0, 0, 1, 0]
    else:
        m = [1 - k, 0, 0, 0, r * k, 0, 1 - k, 0, 0, g * k, 0, 0, 1 - k, 0, b * k, 0, 0, 0, 1, 0]
    return skia.ColorFilters.Matrix(m)


def mono_filter(amount=1.0, contrast=1.0):
    lr, lg, lb = 0.2126 * contrast, 0.7152 * contrast, 0.0722 * contrast
    k = float(amount)
    off = (1 - contrast) * 0.5
    rows = []
    for i in range(3):
        row = [0.0] * 5
        row[0], row[1], row[2] = mix(1 if i == 0 else 0, lr, k), mix(1 if i == 1 else 0, lg, k), mix(1 if i == 2 else 0, lb, k)
        row[4] = off * k
        rows += row
    return skia.ColorFilters.Matrix(rows + [0, 0, 0, 1, 0])


def invert_filter():
    return skia.ColorFilters.Matrix([-1, 0, 0, 0, 1, 0, -1, 0, 0, 1, 0, 0, -1, 0, 1, 0, 0, 0, 1, 0])


# ---------------------------------------------------------------- images

def to_image(rgba):
    """numpy HxWx4 uint8 (straight alpha) or HxWx3 -> skia.Image."""
    a = np.ascontiguousarray(rgba)
    if a.shape[2] == 3:
        a = np.ascontiguousarray(np.dstack([a, np.full(a.shape[:2], 255, np.uint8)]))
    return skia.Image.fromarray(a, colorType=skia.kRGBA_8888_ColorType, alphaType=skia.kUnpremul_AlphaType)


def draw_image(cv, img, x, y, scale=1.0, rot=0.0, alpha=1.0, anchor=(0.5, 0.5), shadow=None, cfilter=None,
               blur=0.0, src=None, blend=None, flip=False):
    """draw img with its anchor point at (x, y). shadow = dict(dx, dy, sigma, a, rgb)."""
    if alpha <= 0.002:
        return
    iw, ih = img.width(), img.height()
    sr = skia.Rect(0, 0, iw, ih) if src is None else skia.Rect(*src)
    sw, sh = sr.width(), sr.height()
    p = skia.Paint(AntiAlias=True)
    p.setAlphaf(clamp01(alpha))
    filt = None
    if blur > 0.05:
        filt = skia.ImageFilters.Blur(float(blur), float(blur))
    if shadow:
        sc = cint(shadow.get("rgb", (0, 0, 0)), shadow.get("a", 0.25))
        filt = skia.ImageFilters.DropShadow(float(shadow.get("dx", 0)), float(shadow.get("dy", 10)), float(shadow.get("sigma", 14)),
                                            float(shadow.get("sigma", 14)), sc, filt)
    if filt is not None:
        p.setImageFilter(filt)
    if cfilter is not None:
        p.setColorFilter(cfilter)
    if blend is not None:
        p.setBlendMode(blend)
    cv.save()
    cv.translate(float(x), float(y))
    if rot:
        cv.rotate(float(rot))
    cv.scale(float(scale) * (-1 if flip else 1), float(scale))
    dst = skia.Rect(-anchor[0] * sw, -anchor[1] * sh, (1 - anchor[0]) * sw, (1 - anchor[1]) * sh)
    cv.drawImageRect(img, sr, dst, SAMPLING, p)
    cv.restore()


# ---------------------------------------------------------------- paths

def polyline(pts, closed=False):
    path = skia.Path()
    path.moveTo(*pts[0])
    for q in pts[1:]:
        path.lineTo(*q)
    if closed:
        path.close()
    return path


def bezier(p0, c0, c1, p1):
    path = skia.Path()
    path.moveTo(*p0)
    path.cubicTo(*c0, *c1, *p1)
    return path


def catenary(p0, p1, sag, n=48):
    """points of a hanging curve from p0 to p1 sagging by `sag` pixels at the middle (negative = arch)."""
    out = []
    for i in range(n + 1):
        u = i / n
        x = mix(p0[0], p1[0], u)
        y = mix(p0[1], p1[1], u) + sag * 4 * u * (1 - u)
        out.append((x, y))
    return out


def sample_path(path, d0, d1, step=4.0):
    """(points, tangents) along a skia path between arc lengths d0 and d1."""
    pm = skia.PathMeasure(path, False)
    L = pm.getLength()
    d0, d1 = max(0.0, d0), min(L, d1)
    if d1 <= d0:
        return np.zeros((0, 2)), np.zeros((0, 2))
    n = max(2, int((d1 - d0) / step) + 1)
    ps, ts = [], []
    for d in np.linspace(d0, d1, n):
        pos, tan = pm.getPosTan(float(d))
        ps.append((pos.x(), pos.y()))
        ts.append((tan.x(), tan.y()))
    return np.array(ps), np.array(ts)


def path_length(path):
    return skia.PathMeasure(path, False).getLength()


def _noise1(n, seed, scale):
    """smooth 1-d noise in -1..1 of length n."""
    rng = np.random.default_rng(seed)
    k = max(2, int(n / max(scale, 1)) + 2)
    knots = rng.uniform(-1, 1, k)
    x = np.linspace(0, k - 1, n)
    i = np.floor(x).astype(int).clip(0, k - 2)
    f = x - i
    f = f * f * (3 - 2 * f)
    return knots[i] * (1 - f) + knots[i + 1] * f


# ---------------------------------------------------------------- strokes

def brush(cv, path, width, rgb, p0=0.0, p1=1.0, a=1.0, bristles=14, seed=0, dry=0.35, taper=0.12, wobble=0.12,
          tex_rgb=None):
    """textured paint stroke along path, drawn between fractions p0..p1 of its length.

    A bundle of thin bristle strokes offset along the normal, each with its own opacity, small wobble and dry-brush
    breakups, so it reads as a painted streak rather than a vector line.
    """
    L = path_length(path)
    if L <= 0 or p1 <= p0 or a <= 0:
        return
    pts, tans = sample_path(path, p0 * L, p1 * L, step=3.0)
    if len(pts) < 2:
        return
    n = len(pts)
    nrm = np.stack([-tans[:, 1], tans[:, 0]], 1)
    u = np.linspace(p0, p1, n)
    prof = np.ones(n)
    if taper > 0:
        prof = np.minimum(1, np.minimum(u / taper, (1 - u) / taper).clip(0, 1) * 0.75 + 0.25)
    rng = np.random.default_rng(seed)
    bw = max(1.0, width / bristles * 2.1)
    for k in range(bristles):
        off = (k / max(1, bristles - 1) - 0.5) * width * 0.92
        wob = _noise1(n, seed * 131 + k, 40) * width * wobble
        q = pts + nrm * ((off + wob) * prof)[:, None]
        rgbk = rgb if tex_rgb is None or rng.random() > 0.3 else tex_rgb
        shade = rng.uniform(0.80, 1.08)
        col = tuple(min(1.0, c * shade) for c in rgbk)
        pk = paint(col, a * rng.uniform(0.55, 1.0), stroke=bw * rng.uniform(0.7, 1.3))
        if dry > 0:
            on = rng.uniform(30, 140, 8) * (1.1 - dry)
            off_ = rng.uniform(2, 26, 8) * dry
            iv = [float(v) for pair in zip(on, off_) for v in pair]
            pk.setPathEffect(skia.DashPathEffect.Make(iv, float(rng.uniform(0, 200))))
        cv.drawPath(polyline(q.tolist()), pk)


def line(cv, pts, width, rgb=INK, a=1.0, dash=None, cap="round"):
    p = paint(rgb, a, stroke=width, cap=cap)
    if dash:
        p.setPathEffect(skia.DashPathEffect.Make([float(v) for v in dash], 0.0))
    cv.drawPath(polyline(pts) if not isinstance(pts, skia.Path) else pts, p)


def line_part(cv, path, p0, p1, width, rgb=INK, a=1.0, dash=None):
    L = path_length(path)
    if p1 <= p0 or L <= 0:
        return
    seg = skia.Path()
    skia.PathMeasure(path, False).getSegment(p0 * L, p1 * L, seg, True)
    line(cv, seg, width, rgb, a, dash)


def dotted(cv, path, p0, p1, r, gap, rgb, a=1.0, seed=0, jitter=0.25):
    """a chain of small irregular dots (the reference's red dotted line)."""
    L = path_length(path)
    pts, _ = sample_path(path, p0 * L, p1 * L, step=gap)
    rng = np.random.default_rng(seed)
    for (x, y) in pts:
        rr = r * rng.uniform(1 - jitter, 1 + jitter)
        cv.drawCircle(float(x + rng.normal(0, r * 0.3)), float(y + rng.normal(0, r * 0.3)), float(rr),
                      paint(rgb, a * rng.uniform(0.6, 1.0)))


def pin(cv, x, y, r=11.0, rgb=(0.55, 0.56, 0.58), a=1.0):
    """a small metal map-pin head with a soft shadow."""
    cv.drawCircle(float(x + r * 0.25), float(y + r * 0.45), float(r * 1.05), paint((0, 0, 0), 0.22 * a, blur=r * 0.45))
    hi = tuple(min(1, c * 1.7 + 0.15) for c in rgb)
    lo = tuple(c * 0.35 for c in rgb)
    sh = skia.GradientShader.MakeRadial(skia.Point(float(x - r * 0.35), float(y - r * 0.4)), float(r * 1.5),
                                        [cint(hi, a), cint(rgb, a), cint(lo, a)], [0.0, 0.45, 1.0])
    p = skia.Paint(AntiAlias=True)
    p.setShader(sh)
    cv.drawCircle(float(x), float(y), float(r), p)
    cv.drawCircle(float(x - r * 0.35), float(y - r * 0.38), float(r * 0.22), paint((1, 1, 1), 0.85 * a))


def _stadium(w, h):
    return skia.RRect.MakeRectXY(skia.Rect(-w / 2, -h / 2, w / 2, h / 2), h / 2, h / 2)


def chain(cv, path, p0, p1, link=40.0, rgb=(0.60, 0.61, 0.64), a=1.0, phase=0.0, shadow=True, outline=(0.12, 0.12, 0.14)):
    """a steel chain along path: alternating face-on rings (with their hole) and edge-on links, shaded and outlined."""
    L = path_length(path)
    if L <= 0 or p1 <= p0 or a <= 0:
        return
    pm = skia.PathMeasure(path, False)
    step = link * 0.74
    d = p0 * L + (phase % 1.0) * step
    i = int(math.floor(phase))
    hi = tuple(min(1, c * 1.6 + 0.18) for c in rgb)
    lo = tuple(c * 0.30 for c in rgb)
    links = []
    while d < p1 * L - step * 0.2:
        pos, tan = pm.getPosTan(float(d))
        links.append((pos.x(), pos.y(), math.degrees(math.atan2(tan.y(), tan.x())), i % 2))
        d += step
        i += 1
    lw, lh = link, link * 0.58
    t = link * 0.17
    if shadow:
        sp = paint((0, 0, 0), 0.20 * a, blur=link * 0.14)
        for x, y, ang, odd in links:
            cv.save()
            cv.translate(x + link * 0.10, y + link * 0.28)
            cv.rotate(ang)
            cv.drawRRect(_stadium(lw, lh if not odd else t * 1.4), sp)
            cv.restore()
    for x, y, ang, odd in links:
        cv.save()
        cv.translate(x, y)
        cv.rotate(ang)
        if not odd:
            ring = skia.Path()
            ring.addRRect(_stadium(lw, lh))
            ring.addRRect(_stadium(lw - 2 * t, lh - 2 * t))
            ring.setFillType(skia.PathFillType.kEvenOdd)
            g = skia.GradientShader.MakeLinear([skia.Point(0, -lh / 2), skia.Point(0, lh / 2)],
                                               [cint(hi, a), cint(rgb, a), cint(lo, a), cint(rgb, a), cint(hi, a * 0.9)],
                                               [0.0, 0.3, 0.55, 0.8, 1.0])
            p = paint(rgb, a)
            p.setShader(g)
            cv.drawPath(ring, p)
            cv.drawPath(ring, paint(outline, 0.55 * a, stroke=1.3))
            cv.drawArc(skia.Rect(-lw / 2 + t * 0.5, -lh / 2 + t * 0.35, lw / 2 - t * 0.5, lh / 2 - t * 0.35), 200, 60, False,
                       paint((1, 1, 1), 0.7 * a, stroke=t * 0.28))
        else:
            r = _stadium(lw * 1.02, t * 1.25)
            g = skia.GradientShader.MakeLinear([skia.Point(0, -t * 0.62), skia.Point(0, t * 0.62)],
                                               [cint(hi, a), cint(rgb, a), cint(lo, a)], [0.0, 0.45, 1.0])
            p = paint(rgb, a)
            p.setShader(g)
            cv.drawRRect(r, p)
            cv.drawRRect(r, paint(outline, 0.6 * a, stroke=1.3))
            cv.drawLine(-lw * 0.38, -t * 0.22, lw * 0.38, -t * 0.22, paint((1, 1, 1), 0.65 * a, stroke=t * 0.18))
        cv.restore()


def rings(cv, cx, cy, radii, width, rgb, a=1.0, p=1.0, rot=0.0, ticks=0, start=-90.0):
    """concentric (partly drawn) circles, e.g. Makima's ringed eyes or a HUD target."""
    for k, rr in enumerate(radii):
        sweep = 360.0 * clamp01(p * (1 + 0.15 * k) - 0.15 * k)
        if sweep <= 0:
            continue
        pr = paint(rgb, a, stroke=width * (1.0 if k % 2 == 0 else 0.55), cap="butt")
        cv.drawArc(skia.Rect(cx - rr, cy - rr, cx + rr, cy + rr), start + rot * (1 if k % 2 else -1), sweep, False, pr)
    if ticks and radii:
        R = radii[-1]
        for j in range(ticks):
            ang = math.radians(rot + j * 360 / ticks)
            if j / ticks > p:
                break
            x0, y0 = cx + math.cos(ang) * R * 1.04, cy + math.sin(ang) * R * 1.04
            x1, y1 = cx + math.cos(ang) * R * 1.10, cy + math.sin(ang) * R * 1.10
            cv.drawLine(x0, y0, x1, y1, paint(rgb, a, stroke=width * 0.6, cap="butt"))


_splat_cache = {}


def splat_image(size, seed=0, rgb=BLOOD, direction=None):
    """an organic blood/ink splash as a skia.Image (metaballs: random blobs, tapered streaks, droplets -> blur -> threshold)."""
    key = (int(size), seed, tuple(rgb), direction)
    if key in _splat_cache:
        return _splat_cache[key]
    import cv2
    rng = np.random.default_rng(seed)
    S = int(size * 2.8)
    c = S / 2
    m = np.zeros((S, S), np.float32)
    for _ in range(9):
        r = size * rng.uniform(0.10, 0.22)
        cv2.circle(m, (int(c + rng.normal(0, size * 0.10)), int(c + rng.normal(0, size * 0.10))), int(r), 1.0, -1, cv2.LINE_AA)
    for _ in range(int(rng.integers(10, 18))):
        ang = rng.uniform(0, 2 * np.pi) if direction is None else direction + rng.normal(0, 0.7)
        length = size * rng.uniform(0.45, 1.25)
        r0 = size * rng.uniform(0.03, 0.075)
        n = int(length / max(2, r0 * 0.5))
        for j in range(n):
            u = j / max(1, n - 1)
            rr = r0 * (1 - 0.82 * u)
            x, y = c + np.cos(ang) * length * u, c + np.sin(ang) * length * u
            cv2.circle(m, (int(x), int(y)), max(1, int(rr)), 1.0, -1, cv2.LINE_AA)
        x, y = c + np.cos(ang) * length * 1.08, c + np.sin(ang) * length * 1.08
        cv2.circle(m, (int(x), int(y)), max(1, int(r0 * rng.uniform(0.4, 0.9))), 1.0, -1, cv2.LINE_AA)
    for _ in range(int(rng.integers(14, 26))):
        ang = rng.uniform(0, 2 * np.pi)
        dist = size * rng.uniform(0.5, 1.3)
        x, y = c + np.cos(ang) * dist, c + np.sin(ang) * dist
        if 4 < x < S - 4 and 4 < y < S - 4:
            cv2.circle(m, (int(x), int(y)), max(1, int(size * rng.uniform(0.006, 0.03))), 1.0, -1, cv2.LINE_AA)
    m = cv2.GaussianBlur(m, (0, 0), max(1.0, size * 0.018))
    a = np.clip((m - 0.42) / 0.16, 0, 1)
    shade = 0.85 + 0.15 * cv2.GaussianBlur(rng.random((S, S)).astype(np.float32), (0, 0), size * 0.05)
    img = np.zeros((S, S, 4), np.uint8)
    for k in range(3):
        img[..., k] = np.clip(rgb[k] * 255 * shade, 0, 255).astype(np.uint8)
    img[..., 3] = (a * 255).astype(np.uint8)
    im = to_image(img)
    _splat_cache[key] = im
    return im


def splatter(cv, cx, cy, size, rgb=BLOOD, a=1.0, p=1.0, seed=0, direction=None, rot=0.0):
    """blood/ink splash growing out from (cx, cy) as p goes 0 -> 1."""
    k = out_expo(p)
    if k <= 0 or a <= 0:
        return
    im = splat_image(size, seed, rgb, direction)
    cv.save()
    R = im.width() * 0.5 * min(1.0, k * 1.15)
    clip = skia.Path()
    clip.addCircle(float(cx), float(cy), float(R))
    cv.clipPath(clip, skia.ClipOp.kIntersect, True)
    draw_image(cv, im, cx, cy, scale=0.82 + 0.18 * k, rot=rot, alpha=a)
    cv.restore()


def ribbon(cv, path, width, rgb, p0=0.0, p1=1.0, a=1.0, seed=0, streaks=True, rough=0.10):
    """a solid painted band (ragged edges, streaky texture on top), e.g. a paint stroke wrapping something."""
    L = path_length(path)
    if L <= 0 or p1 <= p0 or a <= 0:
        return
    pts, tans = sample_path(path, p0 * L, p1 * L, step=4.0)
    if len(pts) < 2:
        return
    n = len(pts)
    nrm = np.stack([-tans[:, 1], tans[:, 0]], 1)
    u = np.linspace(0, 1, n)
    prof = np.clip(np.minimum(u, 1 - u) / 0.04, 0, 1) ** 0.5 * 0.6 + 0.4
    e1 = width / 2 * prof * (1 + rough * _noise1(n, seed, 12))
    e2 = width / 2 * prof * (1 + rough * _noise1(n, seed + 1, 12))
    top = pts + nrm * e1[:, None]
    bot = pts - nrm * e2[:, None]
    poly = np.concatenate([top, bot[::-1]])
    cv.drawPath(polyline(poly.tolist(), closed=True), paint(rgb, a))
    if streaks:
        rng = np.random.default_rng(seed)
        for k in range(int(width / 3)):
            off = rng.uniform(-0.45, 0.45) * width
            q = pts + nrm * (off * prof)[:, None]
            lt = rng.uniform(-0.25, 0.22)
            col = tuple(np.clip(np.array(rgb) * (1 + lt) + (0.08 if lt > 0 else 0), 0, 1))
            pk = paint(col, a * rng.uniform(0.25, 0.6), stroke=rng.uniform(1.0, 3.0))
            on = rng.uniform(40, 260, 6)
            off_ = rng.uniform(10, 120, 6)
            pk.setPathEffect(skia.DashPathEffect.Make([float(v) for pr in zip(on, off_) for v in pr], float(rng.uniform(0, 300))))
            cv.drawPath(polyline(q.tolist()), pk)


def speed_lines(cv, t, angle_deg, n=60, seed=0, colors=((0.1, 0.1, 0.12), (0.55, 0.85, 0.95), BLOOD), a=1.0,
                speed=2600.0, length=(120, 520), width=(1.0, 3.5), area=None):
    """diagonal streaks moving along angle_deg."""
    rng = np.random.default_rng(seed)
    ang = math.radians(angle_deg)
    dx, dy = math.cos(ang), math.sin(ang)
    diag = math.hypot(W, H)
    for j in range(n):
        off = rng.uniform(-diag / 2, diag / 2)
        l = rng.uniform(*length)
        base = rng.uniform(0, diag * 2)
        s = ((base + t * speed * rng.uniform(0.6, 1.4)) % (diag * 2)) - diag
        cx, cy = W / 2 + dx * s - dy * off, H / 2 + dy * s + dx * off
        col = colors[j % len(colors)] if rng.random() < 0.5 else colors[0]
        cv.drawLine(cx, cy, cx - dx * l, cy - dy * l, paint(col, a * rng.uniform(0.3, 1.0), stroke=rng.uniform(*width)))


# ---------------------------------------------------------------- text

_fonts = {}


def font(path, size):
    tf = _fonts.get(path)
    if tf is None:
        tf = _fonts[path] = skia.Typeface.MakeFromFile(path)
    f = skia.Font(tf, float(size))
    f.setEdging(skia.Font.Edging.kAntiAlias)
    f.setSubpixel(True)
    return f


def text(cv, s, x, y, size, font_path, rgb=INK, a=1.0, align="center", tracking=0.0):
    f = font(font_path, size)
    p = paint(rgb, a)
    if tracking == 0:
        w = f.measureText(s)
        x0 = x - (w / 2 if align == "center" else w if align == "right" else 0)
        cv.drawString(s, float(x0), float(y), f, p)
        return w
    widths = [f.measureText(ch) for ch in s]
    total = sum(widths) + tracking * size * (len(s) - 1)
    x0 = x - (total / 2 if align == "center" else total if align == "right" else 0)
    for ch, w in zip(s, widths):
        cv.drawString(ch, float(x0), float(y), f, p)
        x0 += w + tracking * size
    return total


# ---------------------------------------------------------------- frame + post

class Frame:
    def __init__(self):
        self.surface = skia.Surface(W, H)
        self.cv = self.surface.getCanvas()

    def clear(self, rgb=BG):
        self.cv.clear(c4(rgb))
        return self.cv

    def array(self):
        """HxWx3 uint8 RGB."""
        return self.surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)[..., :3].copy()

    def image(self):
        return self.surface.makeImageSnapshot()


def layer(cv, alpha=1.0, cfilter=None, blur=0.0, blend=None):
    """start an offscreen group (end with cv.restore())."""
    p = skia.Paint()
    p.setAlphaf(clamp01(alpha))
    if cfilter is not None:
        p.setColorFilter(cfilter)
    if blur > 0.05:
        p.setImageFilter(skia.ImageFilters.Blur(float(blur), float(blur)))
    if blend is not None:
        p.setBlendMode(blend)
    cv.saveLayer(None, p)


def glitch(arr, seed, amount=1.0):
    """horizontal slice shifts, channel split and a few corrupted blocks (numpy, in place on a copy)."""
    out = arr.copy()
    rng = np.random.default_rng(seed)
    h, w = out.shape[:2]
    for _ in range(int(rng.integers(5, 10) * amount)):
        y0 = int(rng.integers(0, h - 10))
        hh = int(rng.integers(6, int(h * 0.09)))
        sx = int(rng.choice([-1, 1]) * rng.integers(12, int(80 * amount) + 13))
        band = np.roll(out[y0:y0 + hh], sx, axis=1)
        band[..., 0] = np.roll(band[..., 0], int(9 * amount), axis=1)
        band[..., 2] = np.roll(band[..., 2], -int(9 * amount), axis=1)
        out[y0:y0 + hh] = band
    for _ in range(int(rng.integers(2, 6) * amount)):
        bw, bh = int(rng.integers(40, 260)), int(rng.integers(10, 70))
        x0, y0 = int(rng.integers(0, w - bw)), int(rng.integers(0, h - bh))
        sx0, sy0 = int(np.clip(x0 + rng.integers(-200, 200), 0, w - bw)), int(np.clip(y0 + rng.integers(-60, 60), 0, h - bh))
        out[y0:y0 + bh, x0:x0 + bw] = out[sy0:sy0 + bh, sx0:sx0 + bw]
    return out


def grain(arr, k, amount=0.018, seed=7):
    rng = np.random.default_rng(seed * 1000 + k % 24)
    n = rng.standard_normal(arr.shape[:2]).astype(np.float32) * (amount * 255)
    return np.clip(arr.astype(np.float32) + n[..., None], 0, 255).astype(np.uint8)


class Writer:
    """raw RGB frames -> H.264 file."""

    def __init__(self, path, fps=FPS, crf=16, audio=None, audio_ss=0.0, audio_t=None):
        cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
               "-r", str(fps), "-i", "-"]
        if audio:
            cmd += ["-ss", f"{audio_ss:.3f}"] + (["-t", f"{audio_t:.3f}"] if audio_t else []) + ["-i", audio,
                                                                                               "-map", "0:v", "-map", "1:a",
                                                                                               "-c:a", "aac", "-b:a", "256k",
                                                                                               "-shortest"]
        cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                path]
        self.p = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    def write(self, rgb):
        self.p.stdin.write(np.ascontiguousarray(rgb, np.uint8).tobytes())

    def close(self):
        self.p.stdin.close()
        self.p.wait()
