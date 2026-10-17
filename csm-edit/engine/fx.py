"""Image treatments on cutouts (numpy RGBA, straight alpha): sketch line art, collage texture fill, paper edge,
afterimage echoes, colour-split / tint."""
import cv2
import numpy as np

from . import core


def lineart(rgba, sigma=1.2, k=1.6, tau=0.985, eps=-0.004, phi=180.0, ink=(0.32, 0.32, 0.34), fill=None, width=1.0):
    """XDoG sketch lines of a cutout: grey pencil lines on transparent (or on `fill` inside the silhouette)."""
    rgb = rgba[..., :3].astype(np.float32) / 255.0
    g = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    g1 = cv2.GaussianBlur(g, (0, 0), sigma)
    g2 = cv2.GaussianBlur(g, (0, 0), sigma * k)
    d = g1 - tau * g2
    e = np.where(d >= eps, 1.0, 1.0 + np.tanh(phi * (d - eps)))
    lines = np.clip(1 - e, 0, 1)
    if width > 1.0:
        lines = cv2.dilate(lines, np.ones((int(width), int(width)), np.uint8))
    a = rgba[..., 3].astype(np.float32) / 255.0 if rgba.shape[2] == 4 else np.ones(g.shape, np.float32)
    edge = cv2.morphologyEx((a > 0.5).astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)).astype(np.float32)
    lines = np.maximum(lines * a, edge * 0.9)
    out = np.zeros(rgba.shape[:2] + (4,), np.uint8)
    if fill is None:
        out[..., :3] = (np.array(ink) * 255).astype(np.uint8)
        out[..., 3] = (lines * 255).astype(np.uint8)
    else:
        col = np.array(fill, np.float32)[None, None] * (1 - lines[..., None]) + np.array(ink, np.float32)[None, None] * lines[..., None]
        out[..., :3] = (col * 255).astype(np.uint8)
        out[..., 3] = (np.maximum(a, lines) * 255).astype(np.uint8)
    return out


def paper_edge(rgba, px=7, rgb=(0.985, 0.985, 0.975)):
    """add a white cut-paper border around the silhouette (like a sticker / hand-cut collage piece)."""
    a = rgba[..., 3]
    pad = px * 2
    big = np.pad(rgba, ((pad, pad), (pad, pad), (0, 0)))
    ab = big[..., 3]
    rng = np.random.default_rng(int(a.sum()) % 9973)
    dil = cv2.dilate((ab > 100).astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (px * 2 + 1, px * 2 + 1)))
    # rough the paper edge a little
    noise = cv2.GaussianBlur(rng.random(dil.shape).astype(np.float32), (0, 0), px * 0.8)
    dil = (cv2.GaussianBlur(dil.astype(np.float32), (0, 0), px * 0.5) + (noise - 0.5) * 0.6 > 0.5).astype(np.float32)
    dil = cv2.GaussianBlur(dil, (0, 0), 0.8)
    out = np.zeros_like(big)
    paper = np.array(rgb, np.float32) * 255
    fa = ab.astype(np.float32) / 255
    out[..., :3] = (big[..., :3] * fa[..., None] + paper * (1 - fa[..., None])).astype(np.uint8)
    out[..., 3] = (np.maximum(dil, fa) * 255).astype(np.uint8)
    return out, pad


def collage(rgba, textures, k=6, seed=0, keep=0.35, lines=True):
    """fill the colour regions of a cutout with photo textures (keeps shading and dark lines): a mixed-media look."""
    rng = np.random.default_rng(seed)
    h, w = rgba.shape[:2]
    a = rgba[..., 3] > 100
    rgb = rgba[..., :3].astype(np.float32) / 255.0
    pix = rgb[a].reshape(-1, 3)
    if len(pix) < k * 10:
        return rgba
    sample = pix[rng.choice(len(pix), min(len(pix), 20000), replace=False)]
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1e-3)
    _, _, centers = cv2.kmeans(sample.astype(np.float32), k, None, crit, 2, cv2.KMEANS_PP_CENTERS)
    d = ((rgb[..., None, :] - centers[None, None]) ** 2).sum(-1)
    lab = d.argmin(-1)
    lab = cv2.medianBlur(lab.astype(np.uint8), 5)
    lum = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    out = rgb.copy()
    order = np.argsort(centers.sum(1))
    for j in range(k):
        m = (lab == j) & a
        if not m.any():
            continue
        luma_c = centers[j].mean()
        if j == order[0] and luma_c < 0.25:
            continue        # keep the darkest region (hair / lines) as drawn
        tex = textures[int(rng.integers(len(textures)))]
        th, tw = tex.shape[:2]
        sc = max(h / th, w / tw) * rng.uniform(1.0, 1.6)
        t2 = cv2.resize(tex, (int(tw * sc) + 1, int(th * sc) + 1))
        y0 = int(rng.integers(0, max(1, t2.shape[0] - h)))
        x0 = int(rng.integers(0, max(1, t2.shape[1] - w)))
        crop = t2[y0:y0 + h, x0:x0 + w, :3].astype(np.float32) / 255.0
        tl = crop.mean(axis=2, keepdims=True)
        shaded = crop / (tl.mean() + 1e-3) * lum[..., None]
        mixed = shaded * (1 - keep) + rgb * keep
        out[m] = np.clip(mixed[m], 0, 1)
    if lines:
        g = cv2.GaussianBlur(lum, (0, 0), 1.0)
        dark = np.clip((0.22 - g) / 0.12, 0, 1)[..., None]
        out = out * (1 - dark) + rgb * dark
    res = rgba.copy()
    res[..., :3] = (np.clip(out, 0, 1) * 255).astype(np.uint8)
    return res


def tint(rgba, rgb, amount=1.0):
    """recolour a cutout toward rgb, keeping its luminance (like the reference's green afterimages)."""
    src = rgba[..., :3].astype(np.float32) / 255.0
    lum = cv2.cvtColor(src, cv2.COLOR_RGB2GRAY)[..., None]
    col = np.array(rgb, np.float32)[None, None]
    tinted = np.where(lum < 0.5, 2 * lum * col, 1 - 2 * (1 - lum) * (1 - col))
    out = rgba.copy()
    out[..., :3] = (np.clip(src * (1 - amount) + tinted * amount, 0, 1) * 255).astype(np.uint8)
    return out


def crop_alpha(rgba, pad=4):
    """crop to the alpha bounding box; returns (cropped, (x0, y0))."""
    ys, xs = np.where(rgba[..., 3] > 8)
    if len(xs) == 0:
        return rgba, (0, 0)
    x0, x1 = max(0, xs.min() - pad), min(rgba.shape[1], xs.max() + pad + 1)
    y0, y1 = max(0, ys.min() - pad), min(rgba.shape[0], ys.max() + pad + 1)
    return rgba[y0:y1, x0:x1].copy(), (x0, y0)


def load_textures(paths, size=1024):
    out = []
    for p in paths:
        im = cv2.imread(p, cv2.IMREAD_COLOR)
        if im is None:
            continue
        h, w = im.shape[:2]
        s = size / max(h, w)
        out.append(cv2.resize(im, (int(w * s), int(h * s)))[..., ::-1].copy())
    return out


def echo(cv, img, x, y, scale, offsets, rgb, alphas, cfilter_amount=0.85):
    """afterimages: copies of img at offsets, tinted, behind the original (draw the original after this)."""
    filt = core.tint_filter(rgb, cfilter_amount, keep_luma=False)
    for (dx, dy), a in zip(offsets, alphas):
        core.draw_image(cv, img, x + dx, y + dy, scale=scale, alpha=a, cfilter=filt)
