"""Ending of the FlyingTuna edit, v3: track 0:56.18 -> ~1:12.17, rendered alone.

Look (from the user's three references): fire-filled condensed shout words placed behind him (person matte),
elegant serif subtitles + typewriter context lines in a cinema letterbox, cold duotone for the calm that turns
warm on the #1 reveal, bloom / anamorphic streaks / film-burn light leaks / flashes / grain.
Chronology of the calm (one clip, in order): "oh... shit" -> "YES!" -> "YES!" -> "oh my f*cking god" ->
result screen (hands on head) = #1 -> "I will go to say to my parents", the word "parents" on the drum return.

usage: python -I ending_v3.py <out_video.mp4> [--frames t1,t2,... --stills DIR]   (t = track seconds)
"""
import math
import os
import subprocess
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

S = os.environ.get("FT_WORK", "/tmp/claude-0/-home-user-Claude-code/a61365b4-59b2-5d5f-8537-7f9c9b765619/scratchpad")  # mattes, fonts2, tracks_x, models
LIB = "/home/user/Claude-code/osu-edit/clips/ft_library/03_number_one_2019-02-11"
CLEAN = "/home/user/Claude-code/osu-edit/out/ft_main/work_clean"
REAL = f"{LIB}/2019-02-12_when_tuna_really_gets_1.mp4"
PAR = f"{LIB}/2019-02-11_i_will_go_to_say_to_my_parents.mp4"
FD = f"{S}/fonts2"
F_DISPLAY = f"{FD}/Anton-Regular.ttf"
F_SERIF = f"{FD}/InstrumentSerifItalic.ttf"
F_MONO = f"{FD}/CourierPrime.ttf"
F_KR = "/home/user/Claude-code/osu-edit/fonts/NotoSansKR[wght].ttf"

W, H, FPS = 1920, 1080, 60
BEAT = 60 / 189


def F(b):
    return round(b * BEAT * FPS)


def TB(b):  # exact track time of a beat
    return b * BEAT


FR0 = F(177)          # first rendered track frame (56.183 s)
FR_END = F(224) + 63  # ~72.17 s
NFR = FR_END - FR0
LB = 138              # letterbox bar height (2.39:1)


def c01(x):
    return min(1.0, max(0.0, x))


def smooth(x):
    x = c01(x)
    return x * x * (3 - 2 * x)


def eout(x, p=3.0):
    return 1 - (1 - c01(x)) ** p


def ein(x, p=2.0):
    return c01(x) ** p


def env(t, t0, att=0.0, dec=0.3):
    """0 before t0, ramps up over att, then decays exponentially with time constant dec."""
    d = t - t0
    if d < 0:
        return 0.0
    a = 1.0 if att <= 0 else c01(d / att)
    return a * math.exp(-max(0.0, d - att) / dec)


# ------------------------------------------------------------------ shots
FC = (885, 850, 1275, 1065)  # face-cam window in the 1920x1080 stream frame
KC = (1305, 730, 1900, 1065)  # hand-cam window


def cam_lin(a, b, ease=smooth):
    return lambda u: tuple(a[i] + (b[i] - a[i]) * ease(u) for i in range(len(a)))


SHOTS = []
for k, b0 in enumerate([177, 178, 179, 180, 182, 184, 186, 188, 189, 190]):
    b1 = [178, 179, 180, 182, 184, 186, 188, 189, 190, 192][k]
    SHOTS.append(dict(name=f"cut{k}", f0=F(b0), f1=F(b1), path=f"{CLEAN}/seg_{68 + k:03d}.mp4", sin=0.0, look="raw",
                      cam=cam_lin((960, 540, 1.0, 0), (960, 540, 1.0, 0))))
SHOTS += [
    dict(name="A", f0=F(192), f1=F(198), path=REAL, sin=0.00, look="cold",
         cam=cam_lin((960, 540, 1.0, 0), (1030, 760, 1.30, 0))),
    dict(name="B", f0=F(198), f1=F(201), path=REAL, sin=9.43, look="cold", matte=("really_8_16", 8.0),
         cam=cam_lin((1080, 948, 4.95, 0), (1080, 944, 5.15, 0))),
    dict(name="C1", f0=F(201), f1=F(203), path=REAL, sin=12.27, look="cold", matte=("really_8_16", 8.0),
         cam=cam_lin((1080, 950, 5.2, -2.5), (1080, 950, 5.35, -3.0))),
    dict(name="C2", f0=F(203), f1=F(210), path=REAL, sin=13.55, look="cold", matte=("really_8_16", 8.0),
         cam=cam_lin((1010, 770, 1.55, 0), (1080, 948, 4.95, 0), lambda u: ein(u, 2.2))),
    dict(name="D", f0=F(210), f1=F(218), path=REAL, sin=17.00, look="warm", matte=("really_16_19", 16.2), box_front=True,
         cam=cam_lin((960, 540, 1.0, 0), (1010, 650, 1.22, 0))),
    dict(name="E", f0=F(218), f1=F(224), path=PAR, sin=19.80, look="soft", matte=("parents_19_22", 19.0),
         cam=cam_lin((1080, 955, 4.6, 0), (1078, 950, 5.0, 0))),
    dict(name="END", f0=F(224), f1=FR_END, path=None, look="black"),
]
MATTES = {}


def matte(name):
    if name not in MATTES:
        MATTES[name] = np.load(f"{S}/matte/{name}.npy")
    return MATTES[name]


class Reader:
    def __init__(self, path, sin, n):
        self.p = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{sin:.3f}", "-i", path, "-frames:v", str(n + 1),
                                   "-vf", "fps=60,scale=1920:1080", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                  stdout=subprocess.PIPE, stdin=subprocess.DEVNULL)
        self.last = np.zeros((H, W, 3), np.uint8)

    def next(self):
        buf = self.p.stdout.read(W * H * 3)
        if len(buf) == W * H * 3:
            self.last = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
        return self.last


# ------------------------------------------------------------------ precomputed textures
rng = np.random.default_rng(11)
YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)
VIGN = np.clip(1 - 0.55 * (((XX - W / 2) / (W * 0.62)) ** 2 + ((YY - H / 2) / (H * 0.62)) ** 2), 0, 1).astype(np.float32)[..., None]
GRAIN = [rng.normal(0, 1, (H // 2, W // 2)).astype(np.float32) for _ in range(8)]


def fbm(w, h, base, octaves, seed, gain=0.55):
    r = np.random.default_rng(seed)
    acc = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        n = r.random((max(2, int(base * 2 ** o * h / w)), max(2, int(base * 2 ** o)))).astype(np.float32)
        acc += cv2.resize(n, (w, h), interpolation=cv2.INTER_CUBIC) * amp
        tot += amp
        amp *= gain
    acc /= tot
    return (acc - acc.min()) / (acc.max() - acc.min() + 1e-9)


NZ_A = fbm(1024, 1024, 4, 6, 3)
NZ_B = fbm(1024, 1024, 9, 4, 5)


def lut(stops):
    xs = np.array([s[0] for s in stops], np.float32)
    out = np.zeros((256, 3), np.float32)
    for c in range(3):
        out[:, c] = np.interp(np.linspace(0, 1, 256), xs, [s[1][c] for s in stops])
    return out


FIRE = lut([(0.0, (0.35, 0.02, 0.0)), (0.30, (0.78, 0.10, 0.0)), (0.55, (1.0, 0.36, 0.02)), (0.78, (1.0, 0.68, 0.14)), (1.0, (1.0, 0.96, 0.80))])
COLD = lut([(0.0, (0.008, 0.012, 0.03)), (0.45, (0.20, 0.30, 0.40)), (0.8, (0.70, 0.84, 0.92)), (1.0, (0.97, 0.99, 1.0))])
WARM = lut([(0.0, (0.02, 0.008, 0.0)), (0.45, (0.42, 0.26, 0.12)), (0.8, (0.93, 0.78, 0.55)), (1.0, (1.0, 0.97, 0.90))])
SOFT = lut([(0.0, (0.015, 0.012, 0.012)), (0.45, (0.33, 0.30, 0.29)), (0.8, (0.86, 0.82, 0.78)), (1.0, (0.99, 0.98, 0.96))])


def fire_fill(h, w, t, seed=0):
    oy = (int(t * 260) + seed * 97) % 1024
    ox = (seed * 211) % 1024
    a = np.roll(np.roll(NZ_A, -oy, axis=0), -ox, axis=1)[::2, ::2]
    b = np.roll(np.roll(NZ_B, -((int(t * 460) + seed * 31) % 1024), axis=0), -ox, axis=1)[::2, ::2]
    a = cv2.resize(a, (w, h), interpolation=cv2.INTER_CUBIC)
    b = cv2.resize(b, (w, h), interpolation=cv2.INTER_CUBIC)
    y = np.linspace(0, 1, h, dtype=np.float32)[:, None]  # 0 top .. 1 bottom
    base = 0.30 + 0.62 * y ** 0.8                          # hotter towards the bottom
    f = base + (a - 0.5) * 0.30 + np.clip(b - 0.62, 0, 1) * 0.9 * y
    return FIRE[(np.clip(f, 0, 1) * 255).astype(np.uint8)]


# ------------------------------------------------------------------ text
_fonts, _spr = {}, {}


def font(path, size):
    k = (path, size)
    if k not in _fonts:
        _fonts[k] = ImageFont.truetype(path, size)
    return _fonts[k]


def text_mask(s, path, size, tracking=0):
    """uint8 alpha of a string, tight box with padding; returns (mask, ascent_offset)."""
    k = (s, path, size, tracking)
    if k in _spr:
        return _spr[k]
    f = font(path, size)
    widths = [f.getlength(ch) for ch in s]
    tw = int(sum(widths) + tracking * max(0, len(s) - 1)) + 4
    asc, desc = f.getmetrics()
    pad = int(size * 0.25)
    im = Image.new("L", (tw + 2 * pad, asc + desc + 2 * pad), 0)
    d = ImageDraw.Draw(im)
    if tracking == 0:
        d.text((pad, pad), s, font=f, fill=255)
    else:
        x = pad
        for ch, wd in zip(s, widths):
            d.text((x, pad), ch, font=f, fill=255)
            x += wd + tracking
    m = np.array(im)
    ys, xs = np.nonzero(m > 8)
    if len(ys):
        m = m[max(0, ys.min() - pad):ys.max() + pad + 1, max(0, xs.min() - pad):xs.max() + pad + 1]
    _spr[k] = m
    return m


def place(mask, cx, cy, scale=1.0, rot=0.0, height=None):
    """Warp a mask into a full-frame float alpha, centered at (cx, cy)."""
    h, w = mask.shape
    s = scale * (height / h if height else 1.0)
    M = cv2.getRotationMatrix2D((w / 2, h / 2), rot, s)
    M[0, 2] += cx - w / 2
    M[1, 2] += cy - h / 2
    return cv2.warpAffine(mask, M, (W, H), flags=cv2.INTER_LINEAR).astype(np.float32) / 255.0


def blur(a, s):
    return cv2.GaussianBlur(a, (0, 0), s)


def glow_of(alpha, color, s1=14, s2=46, k1=0.95, k2=0.65):
    small = cv2.resize(alpha, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
    g = blur(small, s1 / 4) * k1 + blur(small, s2 / 4) * k2
    g = cv2.resize(g, (W, H), interpolation=cv2.INTER_LINEAR)
    return g[..., None] * np.array(color, np.float32)


def fire_layer(alpha, t, seed, hot=0.0):
    ys, xs = np.nonzero(alpha > 0.01)
    rgb = np.zeros((H, W, 3), np.float32)
    if len(ys) == 0:
        return rgb
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    fill = fire_fill(y1 - y0, x1 - x0, t, seed)
    if hot > 0:
        fill = fill * (1 - hot) + np.array([1.0, 0.97, 0.9], np.float32) * hot
    rgb[y0:y1, x0:x1] = fill
    return rgb


# ------------------------------------------------------------------ effects
def bloom(img, th=0.62, s=(5, 16, 42), k=(0.35, 0.3, 0.25), amount=0.5):
    small = cv2.resize(img, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
    hi = np.clip((small - th) / (1 - th), 0, 1)
    acc = np.zeros_like(small)
    for si, ki in zip(s, k):
        acc += blur(hi, si / 4) * ki
    return img + cv2.resize(acc, (W, H), interpolation=cv2.INTER_LINEAR) * amount


def streak(img, x, y, k, color=(0.62, 0.80, 1.0), length=0.55, thick=5.0):
    """Anamorphic horizontal flare through (x, y)."""
    if k <= 0.003:
        return img
    sw, sh = W // 4, H // 4
    xs = np.arange(sw, dtype=np.float32)[None, :] * 4
    ys = np.arange(sh, dtype=np.float32)[:, None] * 4
    dx = np.abs(xs - x) / (W * length)
    dy = np.abs(ys - y) / thick
    band = np.exp(-dy) * np.exp(-dx * 2.2)
    core = np.exp(-((xs - x) ** 2 + (ys - y) ** 2) / (2 * 90.0 ** 2))
    f = cv2.resize((band * 0.85 + core * 0.9).astype(np.float32), (W, H), interpolation=cv2.INTER_LINEAR)
    return img + f[..., None] * np.array(color, np.float32) * k


def light_leak(img, t, t0, dur, color=(1.0, 0.42, 0.12), direction=-1, strength=0.85):
    u = (t - t0) / dur
    if u < 0 or u > 1:
        return img
    e = math.sin(math.pi * u) ** 1.4 * strength
    sw, sh = W // 8, H // 8
    xs = np.arange(sw, dtype=np.float32)[None, :] * 8
    ys = np.arange(sh, dtype=np.float32)[:, None] * 8
    cx = W * (1.15 - 1.3 * u) if direction < 0 else W * (-0.15 + 1.3 * u)
    blob = np.exp(-(((xs - cx) / (W * 0.22)) ** 2 + ((ys - H * 0.45) / (H * 0.55)) ** 2))
    blob2 = np.exp(-(((xs - cx - direction * W * 0.12) / (W * 0.1)) ** 2 + ((ys - H * 0.3) / (H * 0.3)) ** 2))
    f = cv2.resize((blob * 0.8 + blob2 * 0.6).astype(np.float32), (W, H), interpolation=cv2.INTER_LINEAR)
    leak = f[..., None] * np.array(color, np.float32) * e
    return 1 - (1 - np.clip(img, 0, 1)) * (1 - np.clip(leak, 0, 1))


def chroma(img, px):
    if px < 0.4:
        return img
    out = img.copy()
    e = px / (W / 2)
    for c, sgn in ((0, 1), (2, -1)):
        M = cv2.getRotationMatrix2D((W / 2, H / 2), 0, 1 + sgn * e)
        out[..., c] = cv2.warpAffine(img[..., c], M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    return out


def grade(img, look):
    if look == "raw":
        x = np.clip(img, 0, 1)
        x = x * x * (3 - 2 * x) * 0.35 + x * 0.65  # gentle contrast
        y = x.mean(axis=2, keepdims=True)
        return np.clip(y + (x - y) * 1.12, 0, 1)
    table = {"cold": COLD, "warm": WARM, "soft": SOFT}[look]
    yl = img[..., 0] * 0.299 + img[..., 1] * 0.587 + img[..., 2] * 0.114
    yl = np.clip((yl - 0.04) / 0.9, 0, 1)
    yl = yl * yl * (3 - 2 * yl) * 0.6 + yl * 0.4
    return table[(yl * 255).astype(np.uint8)]


# ------------------------------------------------------------------ type events
def shout(t, t0, text, height, cx, cy, rot=0.0, seed=0, echoes=0, exit_t=None, grow=0.0):
    """Fire-filled shout word: returns (alpha, rgb, glow) or None."""
    if t < t0 or (exit_t is not None and t >= exit_t + 0.07):
        return None
    d = t - t0
    pop = 1.0 + 0.32 * (1 - eout(d / 0.09, 2.5))
    sc = pop * (1 + grow * d)
    alpha_k = c01(d / 0.035)
    if exit_t is not None and t >= exit_t:
        q = (t - exit_t) / 0.07
        sc *= 1 + 0.25 * q
        alpha_k *= 1 - q
    m = text_mask(text, F_DISPLAY, 300)
    a = place(m, cx, cy, sc, rot, height) * alpha_k
    for e in range(echoes):
        k = 1.0 + 0.07 * (e + 1) * (1 + 2 * d)
        edge = place(m, cx, cy, sc * k, rot, height)
        edge = np.clip(edge - blur(edge, 2.0) * 1.0, 0, 1) * 3.0
        a = np.maximum(a, np.clip(edge, 0, 1) * alpha_k * (0.55 - 0.15 * e))
    rgb = fire_layer(a, t, seed, hot=0.35 * (1 - c01(d / 0.12)))
    g = glow_of(a, (1.0, 0.24, 0.04), k1=0.9, k2=0.7)
    return a, rgb, g


def mono_line(s, size, tracking, cx, cy, alpha=1.0, typed=None):
    if typed is not None:
        s = s[:max(0, int(typed))]
    if not s:
        return None
    m = text_mask(s, F_MONO, size, tracking)
    return place(m, cx, cy) * alpha


# subtitles: (track time per word)
SUB_A = [("oh…", TB(192)), ("shit.", TB(192) + 1.28)]
SUB_E = [("i", TB(218) + 0.08), ("will", TB(218) + 0.54), ("go", TB(218) + 0.76), ("to", TB(218) + 0.96), ("say", TB(218) + 1.20),
         ("to", TB(218) + 1.40), ("my", TB(218) + 1.60), ("parents", TB(218) + 1.94)]


def subtitle(words, t, cy, size=58, fade_out=None):
    f = font(F_SERIF, size)
    space = f.getlength(" ")
    ws = [f.getlength(w) for w, _ in words]
    total = sum(ws) + space * (len(words) - 1)
    x = W / 2 - total / 2
    acc = np.zeros((H, W), np.float32)
    for (w, tw), wd in zip(words, ws):
        if t >= tw:
            d = t - tw
            k = eout(d / 0.16, 2)
            m = text_mask(w, F_SERIF, size)
            a = place(m, x + wd / 2, cy + 10 * (1 - k)) * k
            if d < 0.16:
                a = a * 0.6 + blur(a, 3.0 * (1 - k) + 0.01) * 0.4
            acc = np.maximum(acc, a)
        x += wd + space
    if fade_out is not None:
        acc *= 1 - c01((t - fade_out[0]) / fade_out[1])
    return acc


# ------------------------------------------------------------------ main frame
def shot_at(fr):
    for s in SHOTS:
        if s["f0"] <= fr < s["f1"]:
            return s
    return SHOTS[-1]


readers = {}


def cam_matrix(cx, cy, z, rot, shake=(0.0, 0.0)):
    M = cv2.getRotationMatrix2D((cx, cy), rot, z)
    M[0, 2] += W / 2 - cx + shake[0]
    M[1, 2] += H / 2 - cy + shake[1]
    return M


def render(fr):
    t = fr / FPS
    s = shot_at(fr)
    k = fr - s["f0"]
    n = s["f1"] - s["f0"]
    u = k / max(1, n - 1)
    look = s["look"]
    calm = look in ("cold", "warm", "soft", "black")

    # ---- shake / punch from events
    shake_amp = 0.0
    punch = 1.0
    for tw, amp in ((62.907, 26), (63.860, 34), (64.554, 18), (66.534, 30), (TB(210), 22), (TB(224), 30)):
        shake_amp += amp * env(t, tw, 0, 0.16)
    if not calm:
        for b in (177, 178, 179, 180, 182, 184, 186, 188, 189, 190):
            punch += (0.075 if b >= 188 else 0.05) * env(t, F(b) / FPS, 0, 0.09)
    if look in ("cold",) and s["name"] == "A":
        punch += 0.07 * env(t, TB(192), 0, 0.18)
    gr = np.random.default_rng(fr * 7 + 3)
    shake = (gr.uniform(-1, 1) * shake_amp, gr.uniform(-1, 1) * shake_amp)

    # ---- base image
    if s["path"] is None:
        base = np.zeros((H, W, 3), np.float32)
        M = None
    else:
        key = s["name"]
        if key not in readers:
            readers[key] = Reader(s["path"], s["sin"], n)
        src = readers[key].next().astype(np.float32) / 255.0
        cx, cy, z, rot = s["cam"](u)
        z *= punch
        M = cam_matrix(cx, cy, z, rot, shake)
        interp = cv2.INTER_CUBIC if z > 1.6 else cv2.INTER_LINEAR
        base = cv2.warpAffine(src, M, (W, H), flags=interp, borderMode=cv2.BORDER_REPLICATE)
        if z > 2.5:  # restore some crispness on the big face-cam blow-ups
            base = np.clip(base * 1.7 - blur(base, 2.2) * 0.7, 0, 1)
    img = grade(base, look) if look != "black" else base
    if look == "warm":  # the reveal: start from the cold look and bloom into warm over 0.35 s
        mix = smooth((t - TB(210)) / 0.35)
        img = grade(base, "cold") * (1 - mix) + img * mix

    # ---- person matte in output coordinates
    pm = None
    if s.get("matte") and M is not None:
        name, mt0 = s["matte"]
        arr = matte(name)
        idx = int(round((s["sin"] + k / FPS - mt0) * FPS))
        idx = min(max(idx, 0), len(arr) - 1)
        x0, y0, x1, y1 = FC
        Mm = M.copy()
        Mm[:, :2] = M[:, :2] / 2.0
        Mm[:, 2] = M[:, 2] + M[:, :2] @ np.array([x0, y0], np.float32)
        pm = cv2.warpAffine(arr[idx], Mm, (W, H), flags=cv2.INTER_LINEAR).astype(np.float32) / 255.0
        pm = np.clip((pm - 0.08) / 0.84, 0, 1)
    boxm = None
    if s.get("box_front") and M is not None:
        bm = np.zeros((H, W), np.float32)
        corners = np.array([[FC[0], FC[1]], [FC[2], FC[1]], [FC[2], FC[3]], [FC[0], FC[3]]], np.float32)
        pts = (corners @ M[:, :2].T + M[:, 2]).astype(np.int32)
        cv2.fillConvexPoly(bm, pts, 1.0, cv2.LINE_AA)
        boxm = bm

    # ---- typography layers (behind him)
    layers = []  # (alpha, rgb, glow)
    flare_pts = []
    if s["name"] == "cut3":  # #4 at 57.143
        layers.append(milestone(t, F(180) / FPS, "#4", "14,000PP  ·  26.12.2018", seed=4))
    if s["name"] == "cut9":  # #2 at 60.317
        layers.append(milestone(t, F(190) / FPS, "#2", "11.02.2019", seed=2))
    if s["name"] == "B":
        layers.append(shout(t, 62.907, "YES", 600, 1360, 470, seed=1))
        flare_pts.append((1360, 470, env(t, 62.907, 0, 0.3)))
    if s["name"] == "C1":
        layers.append(shout(t, 63.860, "YES!", 620, 1370, 470, rot=-3, seed=2, echoes=3))
        flare_pts.append((1370, 470, 1.2 * env(t, 63.860, 0, 0.32)))
    if s["name"] == "C2":
        layers.append(shout(t, 64.554, "OH", 640, 520, 460, seed=3, exit_t=65.954, grow=0.06))
        layers.append(shout(t, 65.954, "MY", 210, 1380, 300, seed=4, exit_t=66.154))
        layers.append(shout(t, 66.154, "F*CKING", 300, 1240, 420, seed=5, exit_t=66.534))
        layers.append(shout(t, 66.534, "GOD", 600, 1370, 480, seed=6, echoes=2))
        for tw, x, y in ((64.554, 520, 460), (66.534, 1370, 480)):
            flare_pts.append((x, y, env(t, tw, 0, 0.3)))
    if s["name"] == "D":
        layers.append(number_one(t))
        flare_pts.append((600, 500, 1.6 * env(t, TB(210), 0, 0.5) + 0.5 * env(t, TB(212), 0.05, 0.35) + 0.4 * env(t, TB(216), 0.05, 0.35)))
    if s["name"] == "END":
        layers.append(end_card(t))
        flare_pts.append((960, 520, 1.4 * env(t, TB(224), 0, 0.45)))
    layers = [l for l in layers if l is not None]
    spot = None
    if s["name"] in ("cut3", "cut9"):
        spot = (960, 520, 760, 430, 0.55)
    elif s["name"] == "D":
        spot = (600, 500, 560, 470, 0.5)
    if layers and spot is not None:
        sx, sy, rx, ry, kd = spot
        sm = np.exp(-(((XX - sx) / rx) ** 2 + ((YY - sy) / ry) ** 2))[..., None]
        img = img * (1 - kd * sm)
    if layers:
        comp = img.copy()
        for a, rgb, g in layers:
            comp = comp * (1 - a[..., None]) + rgb * a[..., None]
            comp = comp + g * (1 - a[..., None])
        front = None
        if pm is not None:
            front = pm
        if boxm is not None:
            front = boxm if front is None else np.maximum(front, boxm)
        if front is not None:
            f3 = front[..., None]
            comp = comp * (1 - f3) + img * f3
        img = comp

    # ---- light
    if calm:
        img = bloom(img, th=0.55, amount=0.75 if look != "black" else 0.9)
    else:
        img = bloom(img, th=0.7, amount=0.35)
    for x, y, kf in flare_pts:
        img = streak(img, x, y, kf * 0.9, color=(1.0, 0.62, 0.32) if look in ("warm", "black") else (0.62, 0.8, 1.0))
    img = light_leak(img, t, TB(210) - 0.05, 1.1, color=(1.0, 0.45, 0.12), direction=-1, strength=0.9)
    img = light_leak(img, t, TB(224) - 0.02, 0.9, color=(1.0, 0.35, 0.10), direction=1, strength=0.7)
    if look == "cold":
        img = light_leak(img, t, TB(201) - 0.1, 1.6, color=(0.35, 0.65, 1.0), direction=1, strength=0.35)
    # flashes
    fl = 0.0
    for tf, kf, dec in ((TB(192), 1.0, 0.05), (62.907, 0.35, 0.05), (63.860, 0.5, 0.05), (66.534, 0.3, 0.04), (TB(210), 1.0, 0.06), (TB(224), 1.0, 0.07)):
        fl = max(fl, kf * env(t, tf, 0, dec))
    if not calm:
        for b in (177, 178, 179, 180, 182, 184, 186, 188, 189, 190):
            fl = max(fl, 0.16 * env(t, F(b) / FPS, 0, 0.03))
    img = img + (1 - np.clip(img, 0, 1)) * fl
    # chromatic aberration
    ca = 2.0 if calm else 1.0
    ca += 10 * max(env(t, 62.907, 0, 0.12), env(t, 63.860, 0, 0.14), env(t, TB(210), 0, 0.15), env(t, TB(224), 0, 0.15))
    if not calm:
        ca += 6 * max(env(t, F(b) / FPS, 0, 0.07) for b in (180, 188, 189, 190))
    img = chroma(np.clip(img, 0, 1.5), ca)
    img = img * (VIGN * (0.55 if calm else 0.25) + (1 - (0.55 if calm else 0.25)))
    # grain
    g = cv2.resize(GRAIN[fr % len(GRAIN)], (W, H), interpolation=cv2.INTER_LINEAR)[..., None]
    img = img + g * (0.045 if calm else 0.022) * (0.35 + 0.65 * np.clip(img, 0, 1))
    # letterbox (animated in on the calm hit)
    if calm:
        lb = int(LB * eout((t - TB(192)) / 0.11, 3))
        if lb > 0:
            img[:lb] = 0
            img[H - lb:] = 0
    img = np.clip(img, 0, 1)
    # ---- subtitles and context lines (on top, in the bars)
    over = np.zeros((H, W), np.float32)
    tint = None
    if s["name"] == "A":
        over = np.maximum(over, subtitle(SUB_A, t, H - 82))
        ml = mono_line("2019.02.11   23:15 KST", 24, 5, W / 2, H - 34, alpha=0.8, typed=(t - TB(192) - 0.25) * 40)
        if ml is not None:
            over = np.maximum(over, ml)
    if s["name"] in ("E", "END"):
        over = np.maximum(over, subtitle(SUB_E, t, H - 82, fade_out=(FR_END / FPS - 0.35, 0.3)))
        a_kr = c01((t - TB(218) - 0.3) / 0.3) * (1 - c01((t - (FR_END / FPS - 0.35)) / 0.3))
        if a_kr > 0:
            m = text_mask("부모님께 말하러 갈게요", F_KR, 24, 3)
            over = np.maximum(over, place(m, W / 2, H - 34) * 0.75 * a_kr)
    if over.max() > 0:
        glow = blur(over, 6.0) * 0.5
        img = img * (1 - over[..., None]) + over[..., None] * np.array([0.98, 0.98, 0.97], np.float32)
        img = np.clip(img + glow[..., None] * 0.35, 0, 1)
    # end fade
    img *= 1 - c01((t - (FR_END / FPS - 0.32)) / 0.3)
    return (img * 255).astype(np.uint8)


def milestone(t, t0, big, small, seed=0):
    d = t - t0
    if d < 0:
        return None
    pop = 1.0 + 0.35 * (1 - eout(d / 0.08, 2.5))
    m = text_mask(big, F_DISPLAY, 300)
    a = place(m, 960, 460, pop, 0, 560)
    rgb = fire_layer(a, t, seed, hot=0.4 * (1 - c01(d / 0.1)))
    gl = glow_of(a, (1.0, 0.22, 0.04), k1=0.9, k2=0.6)
    ms = text_mask(small, F_MONO, 40, 9)
    a2 = place(ms, 960, 820) * c01((d - 0.03) / 0.06)
    rgb = rgb * (1 - a2[..., None]) + np.array([1.0, 1.0, 1.0], np.float32) * a2[..., None]
    a = np.maximum(a, a2)
    return a, rgb, gl


def number_one(t):
    t0 = TB(210)
    d = t - t0
    if d < 0:
        return None
    sc = (1.0 + 0.3 * (1 - eout(d / 0.1, 2.5))) * (1 + 0.025 * d)
    m = text_mask("#1", F_DISPLAY, 300)
    a = place(m, 600, 500, sc, 0, 600)
    hot = 0.55 + 0.45 * (1 - c01(d / 0.25))
    rgb = fire_layer(a, t, 9, hot=hot)
    # light sweep across the numerals on b212 and b216
    for ts in (TB(212), TB(216)):
        q = (t - ts) / 0.45
        if 0 <= q <= 1:
            xs = 220 + 800 * q
            band = np.exp(-(((XX - xs) + (YY - 500) * 0.35) / 60.0) ** 2)
            rgb = rgb + band[..., None] * a[..., None] * 0.9
    gl = glow_of(a, (1.0, 0.55, 0.18), k1=1.0, k2=0.8)
    lines = []
    ma = mono_line("IN THE WORLD", 34, 16, 600, 862, alpha=c01((d - 0.12) / 0.15))
    if ma is not None:
        lines.append(ma)
    mb = mono_line("11.02.2019", 28, 12, 600, 178, alpha=c01((d - 0.2) / 0.15))
    if mb is not None:
        lines.append(mb)
    for la in lines:
        rgb = rgb * (1 - la[..., None]) + np.array([1.0, 0.96, 0.9], np.float32) * la[..., None]
        a = np.maximum(a, la)
    return a, rgb, gl


def end_card(t):
    t0 = TB(224)
    d = t - t0
    if d < 0:
        return None
    sc = 1.0 + 0.28 * (1 - eout(d / 0.1, 2.5)) + 0.03 * d
    m = text_mask("NEVER FORGET.", F_DISPLAY, 300)
    a = place(m, 960, 520, sc, 0, 250)
    rgb = fire_layer(a, t, 12, hot=0.7 + 0.3 * (1 - c01(d / 0.3)))
    gl = glow_of(a, (1.0, 0.45, 0.12), k1=1.0, k2=0.75)
    ms = mono_line("2019.02.11   TOP #1.", 34, 14, 960, 335, alpha=c01((d - 0.06) / 0.1))
    if ms is not None:
        rgb = rgb * (1 - ms[..., None]) + np.array([0.55, 0.72, 1.0], np.float32) * ms[..., None]
        a = np.maximum(a, ms)
    return a, rgb, gl


# ------------------------------------------------------------------ run
if "--frames" in sys.argv:
    want = sorted(set(int(round(float(v) * FPS)) for v in sys.argv[sys.argv.index("--frames") + 1].split(",")))
    out_dir = sys.argv[sys.argv.index("--stills") + 1]
    os.makedirs(out_dir, exist_ok=True)
    for fr in range(FR0, max(want) + 1):  # readers are sequential
        if fr in want:
            img = render(fr)
            cv2.imwrite(f"{out_dir}/e_{fr / FPS:07.3f}.png", cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
        else:
            s = shot_at(fr)
            if s["path"] is not None:
                key = s["name"]
                if key not in readers:
                    readers[key] = Reader(s["path"], s["sin"], s["f1"] - s["f0"])
                readers[key].next()
    print("stills", len(want))
    sys.exit(0)

out = sys.argv[1]
enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                        "-c:v", "libx264", "-preset", "medium", "-crf", "15", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out],
                       stdin=subprocess.PIPE)
for fr in range(FR0, FR_END):
    enc.stdin.write(render(fr).tobytes())
    if (fr - FR0) % 120 == 0:
        print("frame", fr - FR0, "/", NFR, flush=True)
enc.stdin.close()
enc.wait()
print("done", out, NFR, "frames from", FR0 / FPS)
