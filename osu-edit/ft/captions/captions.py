"""Caption overlays for the FlyingTuna edit: RGBA frames drawn with PIL + numpy, laid over the picture by ffmpeg.

Milestones (the pounding part): the label in Archivo Expanded Black, white falling off to a pale lavender, with a
soft shadow instead of an outline. It lands on the beat a touch large with a short colour split and settles in
7 frames. The date sits under it in JetBrains Mono, tracked out, gold, between two hairlines.

The #1 plate (the calm ending): "세계 1위" in Noto Serif KR Black, a gold hairline with "#1 IN THE WORLD" and the
date under it, lower left over a soft dark vignette (the ranking table and his webcam stay clear). The letters come
in one by one out of a blur, the line draws itself, and everything leaves slowly.

Frames are straight-alpha RGBA, 1920x1080.
"""
import os
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
W, H = 1920, 1080
GOLD = (255, 214, 102)


def font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name), size, layout_engine=ImageFont.Layout.RAQM)


def pen(text, f, tracking=0.0):
    """pen x of every character (pair kerning kept) and the width of the line."""
    xs = [f.getlength(text[:i + 1]) - f.getlength(text[i]) + i * tracking for i in range(len(text))]
    return xs, f.getlength(text) + (len(text) - 1) * tracking


def ease(p):
    p = min(1.0, max(0.0, p))
    return 1 - (1 - p) ** 3


def smooth(p):
    p = min(1.0, max(0.0, p))
    return p * p * (3 - 2 * p)


class Canvas:
    """premultiplied RGBA accumulator over a box of the frame."""

    def __init__(self, box):
        self.x0, self.y0, self.x1, self.y1 = box
        h, w = self.y1 - self.y0, self.x1 - self.x0
        self.c = np.zeros((h, w, 3), np.float32)
        self.a = np.zeros((h, w), np.float32)

    def size(self):
        return self.x1 - self.x0, self.y1 - self.y0

    def mask(self):
        return Image.new("L", self.size(), 0)

    def text(self, m, text, f, x, y, tracking=0.0):
        """draw text (baseline at y, frame coordinates) into the L image m."""
        d = ImageDraw.Draw(m)
        xs, _ = pen(text, f, tracking)
        for ch, cx in zip(text, xs):
            if ch != " ":
                d.text((x + cx - self.x0, y - self.y0), ch, font=f, fill=255, anchor="ls")
        return m

    def over(self, color, m, opacity=1.0, chans=None):
        """composite a colour (RGB tuple or HxWx3 array 0..255) through mask m; chans = per-channel masks."""
        a = np.asarray(m, np.float32) * (opacity / 255.0)
        col = np.asarray(color, np.float32) / 255.0
        if chans is None:
            self.c = col * a[..., None] + self.c * (1 - a[..., None])
        else:  # colour split: each channel through its own mask, coverage = the widest of them
            per = np.dstack([np.asarray(k, np.float32) * (opacity / 255.0) for k in chans])
            a = per.max(axis=2)
            self.c = col * per + self.c * (1 - a[..., None])
        self.a = a + self.a * (1 - a)

    def rgba(self, frame=None, base_alpha=None):
        """straight-alpha uint8 frame; base_alpha is a full-frame black layer under the canvas."""
        out = np.zeros((H, W, 4), np.uint8) if frame is None else frame
        if base_alpha is not None:
            out[..., :3] = 0
            out[..., 3] = (base_alpha * 255 + 0.5).astype(np.uint8)
            ba = base_alpha[self.y0:self.y1, self.x0:self.x1]
        else:
            ba = np.zeros_like(self.a)
        a = self.a + ba * (1 - self.a)
        c = self.c / np.maximum(a, 1e-6)[..., None]
        out[self.y0:self.y1, self.x0:self.x1, :3] = (np.clip(c, 0, 1) * 255 + 0.5).astype(np.uint8)
        out[self.y0:self.y1, self.x0:self.x1, 3] = (np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)
        return out


def shift(m, dx=0, dy=0):
    return m.transform(m.size, Image.AFFINE, (1, 0, -dx, 0, 1, -dy), Image.BILINEAR)


def blur(m, r):
    return m.filter(ImageFilter.GaussianBlur(r)) if r > 0.2 else m


# ---------------------------------------------------------------- milestones
M_FONT, M_SIZE, M_MAXW = "ArchivoExpanded-Black.ttf", 156, 1520
D_FONT, D_SIZE = "JetBrainsMono-Medium.ttf", 34
M_CY = 0.20 * H          # vertical centre of the label's caps
M_BOX = (0, 0, W, 470)


def _vgrad(h, w, y_top, y_bot, top=(255, 255, 255), bot=(232, 222, 255)):
    t = np.clip((np.arange(h, dtype=np.float32) - y_top) / max(1.0, y_bot - y_top), 0, 1)[:, None, None]
    return np.broadcast_to(np.asarray(top, np.float32) * (1 - t) + np.asarray(bot, np.float32) * t, (h, w, 3))


def milestone_frame(label, date, f):
    """frame f (0 = the beat) of a milestone caption."""
    cv = Canvas(M_BOX)
    e = ease(f / 7)
    scale = 1.10 - 0.10 * e
    size = M_SIZE
    fnt = font(M_FONT, size)
    while pen(label, fnt, -0.01 * size)[1] > M_MAXW:
        size = int(size * 0.95)
        fnt = font(M_FONT, size)
    cap_h0 = -fnt.getbbox("H", anchor="ls")[1]
    fs = font(M_FONT, max(8, round(size * scale)))
    tr = -0.01 * fs.size
    _, wd = pen(label, fs, tr)
    cap_h = -fs.getbbox("H", anchor="ls")[1]
    base = M_CY + cap_h / 2
    m = cv.text(cv.mask(), label, fs, (W - wd) / 2, base, tr)
    # soft shadows, no outline
    cv.over((0, 0, 0), blur(m, 38), 0.55)
    cv.over((0, 0, 0), blur(shift(m, 0, 7), 7), 0.75)
    glow = 0.45 * (1 - e)
    if glow > 0.01:
        cv.over((255, 255, 255), blur(m, 18), glow)
    w_, h_ = cv.size()
    fill = _vgrad(h_, w_, base - cap_h - cv.y0, base - cv.y0)
    dx = 10 * (1 - e)
    if dx > 0.5:
        cv.over(fill, m, 1.0, chans=(shift(m, dx), m, shift(m, -dx)))
    else:
        cv.over(fill, m, 1.0)
    # date line, a beat behind: letters close in, hairlines grow
    q = ease((f - 2) / 8)
    if q > 0:
        fd = font(D_FONT, D_SIZE)
        dtr = D_SIZE * (0.55 - 0.23 * q)
        _, dw = pen(date, fd, dtr)
        base_d = M_CY + cap_h0 / 2 + 76
        dm = cv.text(cv.mask(), date, fd, (W - dw) / 2, base_d, dtr)
        hl = cv.mask()
        gap, ll, yl = 26, 70 * q, base_d - 13
        dr = ImageDraw.Draw(hl)
        dr.rectangle(((W - dw) / 2 - gap - ll - cv.x0, yl - cv.y0, (W - dw) / 2 - gap - cv.x0, yl + 1 - cv.y0), fill=255)
        dr.rectangle(((W + dw) / 2 + gap - cv.x0, yl - cv.y0, (W + dw) / 2 + gap + ll - cv.x0, yl + 1 - cv.y0), fill=255)
        cv.over((0, 0, 0), blur(dm, 10), 0.8 * q)
        cv.over(GOLD, dm, q)
        cv.over(GOLD, hl, 0.85 * q)
    return cv.rgba()


def milestone_frames(label, date, n):
    last = None
    for f in range(n):
        if f <= 10:
            last = milestone_frame(label, date, f)
        yield last


# ---------------------------------------------------------------- the #1 plate
P_BOX = (0, 560, 1240, H)
P_X = 92
P_HEAD = ("NotoSerifKR-Black-subset.ttf", 128, 820)    # font, size, baseline
P_SUB = ("Montserrat-Medium.ttf", 30, 868)
P_DATE = ("JetBrainsMono-Medium.ttf", 26, 912)
P_RULE = (P_X + 2, 856, 108)                           # x, y, length
P_SUB_X = P_X + 132
P_OUT = 1.3                                             # seconds to leave


def _backdrop():
    """soft dark pool under the plate; it dies out before the webcam (x >= 880) so his face stays untouched."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = ((xx - 300) / 720) ** 2 + ((yy - 860) / 300) ** 2
    right = 1 - np.clip((xx - 600) / 260, 0, 1) ** 2 * (3 - 2 * np.clip((xx - 600) / 260, 0, 1))
    return np.exp(-d * 1.4) * 0.78 * right


class Plate:
    def __init__(self, head="세계 1위", sub="#1 IN THE WORLD", date="11.02.2019"):
        self.bd = _backdrop()
        self.head, self.sub, self.date = head, sub, date
        hf = font(P_HEAD[0], P_HEAD[1])
        self.hf = hf
        xs, _ = pen(head, hf, 0.04 * hf.size)
        self.glyphs = []  # (char, x) without spaces
        for ch, cx in zip(head, xs):
            if ch != " ":
                self.glyphs.append((ch, P_X - 6 + cx))
        self.cache = {}

    def frame(self, t, t_out):
        """t: seconds since the ranking panel came up; t_out: when the plate starts to leave."""
        leave = smooth((t - t_out) / P_OUT) if t >= t_out else 0.0
        static = 2.7 <= t < t_out
        if static and "hold" in self.cache:
            return self.cache["hold"]
        cv = Canvas(P_BOX)
        vis = 1 - leave
        lift = -10 * leave
        soft = 6 * leave
        # headline: glyph by glyph out of a blur
        head = cv.mask()
        for i, (ch, x) in enumerate(self.glyphs):
            p = ease((t - 0.20 - 0.16 * i) / 1.1)
            if p <= 0:
                continue
            g = Image.new("L", head.size, 0)
            ImageDraw.Draw(g).text((x - cv.x0, P_HEAD[2] + 18 * (1 - p) + lift - cv.y0), ch, font=self.hf, fill=255, anchor="ls")
            g = blur(g, 14 * (1 - p) + soft)
            head = Image.fromarray(np.maximum(np.asarray(head), (np.asarray(g, np.float32) * p * vis).astype(np.uint8)))
        cv.over((0, 0, 0), blur(head, 22), 0.6)
        cv.over((255, 255, 255), blur(head, 26), 0.22)
        cv.over((255, 255, 255), head, 1.0)
        # gold hairline draws itself
        r = smooth((t - 0.95) / 0.9)
        if r > 0:
            rx, ry, rl = P_RULE
            hl = cv.mask()
            ImageDraw.Draw(hl).rectangle((rx - cv.x0, ry + lift - cv.y0, rx + rl * r - cv.x0, ry + 1 + lift - cv.y0), fill=255)
            cv.over(GOLD, hl, 0.95 * vis)
        # "#1 IN THE WORLD": letters close in
        s = ease((t - 1.10) / 1.2)
        if s > 0:
            sf = font(P_SUB[0], P_SUB[1])
            sm = cv.text(cv.mask(), self.sub, sf, P_SUB_X, P_SUB[2] + lift, P_SUB[1] * (0.48 - 0.18 * s))
            sm = blur(sm, soft)
            cv.over((0, 0, 0), blur(sm, 6), 0.7 * s * vis)
            cv.over((246, 244, 252), sm, s * vis)
        dd = ease((t - 1.45) / 1.1)
        if dd > 0:
            df = font(P_DATE[0], P_DATE[1])
            dm = cv.text(cv.mask(), self.date, df, P_SUB_X, P_DATE[2] + lift, P_DATE[1] * 0.36)
            dm = blur(dm, soft)
            cv.over((0, 0, 0), blur(dm, 5), 0.7 * dd * vis)
            cv.over(GOLD, dm, dd * vis)
        base = self.bd * smooth(t / 1.6) * vis
        out = cv.rgba(base_alpha=base)
        if static:
            self.cache["hold"] = out
        return out


def plate_frames(n, t_out, fps=60):
    p = Plate()
    for k in range(n):
        yield p.frame(k / fps, t_out)


# ---------------------------------------------------------------- ffmpeg
def render(inputs, vf, frames, n, out, offset=0, post="", fps=60, crf=14, preset="fast"):
    """picture = inputs (ffmpeg args) through vf, overlay frames (from frame `offset`), then post filters."""
    fc = (f"[0:v]{vf}[b];[1:v]setpts=PTS+{offset}/({fps}*TB)[o];"
          f"[b][o]overlay=eof_action=pass:format=auto{',' + post if post else ''},format=yuv420p[v]")
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y", *inputs,
           "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(fps), "-i", "pipe:0",
           "-filter_complex", fc, "-map", "[v]", "-frames:v", str(n), "-an",
           "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p", "-r", str(fps), out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for fr in frames:
            p.stdin.write(fr.tobytes())
    except BrokenPipeError:
        pass
    p.stdin.close()
    if p.wait() != 0:
        raise RuntimeError(f"ffmpeg failed for {out}")
