"""Drawn B&W geometric intro v2 (0:15.23-0:20.32 of LOVESICK, CANNIBAL!), denser and audio-reactive.

Every sound drives something: 8th-note hats step the HUD (dial ticks, stepped bars, split micro-snaps,
typing, combo counter), accents fire shockwaves + particles + glitch, the two big hits explode, the kick
roll before the drop becomes a 16th-note strobe, the silence is black, the last approach circle closes
on the drop. Spectrum drives the edge equalizers and an osu!-menu style radial visualizer.

usage: SONG=<audio> python -I geo_anim2.py <out.mp4> [seed] [--frames t1,t2 --stills_dir DIR]   (t = track seconds)
"""
import math
import os
import subprocess
import sys
import warnings

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

warnings.filterwarnings("ignore")
import librosa  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SONG = os.environ["SONG"]  # LOVESICK, CANNIBAL! audio, official 1:57 version (the osu! beatmapset audio works)
FONT_LAT = f"{HERE}/fonts/NotoSerif-Bold.ttf"
FONT_CJK = f"{HERE}/fonts/NotoSerifJP-Bold-sub.ttf"
FONT_MONO = f"{HERE}/fonts/JetBrainsMono-Medium.ttf"
W, H, FPS = 1920, 1080, 60
BEAT = 60 / 189
E8, E16 = BEAT / 2, BEAT / 4
F0, F1 = 914, 1219
N = F1 - F0

args = sys.argv[1:]
OUT = args[0]
SEED = int(args[1]) if len(args) > 1 and not args[1].startswith("--") else 3
STILLS = None
if "--frames" in args:
    STILLS = [float(v) for v in args[args.index("--frames") + 1].split(",")]
    STILLS_DIR = args[args.index("--stills_dir") + 1]
    os.makedirs(STILLS_DIR, exist_ok=True)


def b2t(b):
    return b * BEAT


def c01(x):
    return min(1.0, max(0.0, x))


def smooth(x):
    x = c01(x)
    return x * x * (3 - 2 * x)


def eout(x, p=3.0):
    return 1 - (1 - c01(x)) ** p


def since(t, t0):
    return t - t0 if t >= t0 else 1e9


def decay(t, t0, rate):
    d = t - t0
    return math.exp(-d * rate) if d >= 0 else 0.0


# ------------------------------------------------------------------ musical events (from the 16th-grid analysis)
T_START, T_DROP = F0 / FPS, F1 / FPS
HATS = [b2t(48 + 0.5 * k) for k in range(28)]  # 15.238 .. 19.524
BIG = [b2t(51), b2t(52)]  # 16.190, 16.508
DIP = b2t(50.75)  # 16.111: the gap before the first big hit
ACC = [b2t(50.5), b2t(52.5), b2t(55), b2t(56.5), b2t(58), b2t(58.5), b2t(60), b2t(61)]
T_RISE = b2t(62)  # 19.683: hats stop, kick roll
RISE16 = [b2t(62 + 0.25 * k) for k in range(7)]  # 19.683 .. 20.159
T_GAP = b2t(63.75)  # 20.238 silence
BEATS = [b2t(b) for b in range(48, 64)]


def last_event(t, evs):
    best = None
    for e in evs:
        if e <= t + 1e-9:
            best = e
    return best


def count_events(t, evs):
    return sum(1 for e in evs if e <= t + 1e-9)


# ------------------------------------------------------------------ audio features at 60 fps
_off = 14.5
_y, _sr = librosa.load(SONG, sr=22050, mono=True, offset=_off, duration=6.6)
_hop = 128
_S = np.abs(librosa.stft(_y, n_fft=2048, hop_length=_hop))
_f = librosa.fft_frequencies(sr=_sr, n_fft=2048)


def _band(lo, hi):
    e = _S[(_f >= lo) & (_f < hi)].sum(0)
    e = np.log1p(e)
    lo_, hi_ = np.percentile(e, 10), np.percentile(e, 99.5)
    return np.clip((e - lo_) / (hi_ - lo_ + 1e-9), 0, 1)


_low, _mid, _high = _band(35, 160), _band(160, 2500), _band(5000, 11000)
_rms = librosa.feature.rms(S=_S)[0]
_rms = np.clip((20 * np.log10(_rms + 1e-9) + 30) / 26, 0, 1)
_mel = librosa.power_to_db(librosa.feature.melspectrogram(S=_S ** 2, sr=_sr, n_mels=48, fmin=40, fmax=10000))
_mel = np.clip((_mel - np.percentile(_mel, 20, axis=1, keepdims=True)) /
               (np.percentile(_mel, 99, axis=1, keepdims=True) - np.percentile(_mel, 20, axis=1, keepdims=True) + 1e-6), 0, 1)


def _follow(x, tau_att, tau_rel):
    """Envelope follower over frames."""
    out = np.zeros(N, np.float32)
    v = 0.0
    a_att, a_rel = math.exp(-1 / (FPS * tau_att)), math.exp(-1 / (FPS * tau_rel))
    for i in range(N):
        tt = (F0 + i) / FPS
        k = int((tt - _off) * _sr / _hop)
        s = float(x[max(0, k - 2):k + 3].max())
        v = (a_att * v + (1 - a_att) * s) if s > v else (a_rel * v + (1 - a_rel) * s)
        out[i] = v
    return out


LOW = _follow(_low, 0.01, 0.12)
MID = _follow(_mid, 0.01, 0.10)
HIGH = _follow(_high, 0.005, 0.06)
RMS = _follow(_rms, 0.02, 0.2)


def spectrum(fl):
    tt = (F0 + fl) / FPS
    k = int((tt - _off) * _sr / _hop)
    return _mel[:, max(0, k - 6):k + 1].max(axis=1)


# ------------------------------------------------------------------ drawn background
rng0 = np.random.default_rng(SEED)
BW, BH = 2500, 1500


def _vnoise(w, h, cells, r):
    return cv2.resize(r.random((cells[1], cells[0])).astype(np.float32), (w, h), interpolation=cv2.INTER_CUBIC)


def _fbm(w, h, base, octaves, r, gain=0.55):
    acc = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        acc += _vnoise(w, h, (max(2, int(base * 2 ** o * w / h)), max(2, int(base * 2 ** o))), r) * amp
        tot += amp
        amp *= gain
    acc /= tot
    return (acc - acc.min()) / (acc.max() - acc.min() + 1e-9)


def make_nebula():
    r = np.random.default_rng(SEED + 100)
    a = _fbm(BW, BH, 3, 7, r)
    dx = (_fbm(BW, BH, 2, 5, r) - 0.5) * 300
    dy = (_fbm(BW, BH, 2, 5, r) - 0.5) * 300
    mx, my = np.meshgrid(np.arange(BW, dtype=np.float32), np.arange(BH, dtype=np.float32))
    v = cv2.remap(a, mx + dx, my + dy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    v = np.clip((v - 0.25) / 0.6, 0, 1)
    v = v * v * (3 - 2 * v)
    fil = _fbm(BW, BH, 9, 5, r)  # fine filaments
    v = np.clip(v + (fil - 0.5) * 0.18 * v, 0, 1)
    dust = _fbm(BW, BH, 4, 6, r)
    v = v * (1 - 0.5 * np.clip((dust - 0.55) / 0.25, 0, 1))
    return (0.09 + 0.62 * v).astype(np.float32)


NEB = make_nebula()
# parallax star field (screen space, depth 0..1)
NSTAR = 2600
ST_X = rng0.uniform(-200, W + 200, NSTAR).astype(np.float32)
ST_Y = rng0.uniform(-150, H + 150, NSTAR).astype(np.float32)
ST_D = rng0.random(NSTAR).astype(np.float32)
ST_B = np.clip(rng0.pareto(2.0, NSTAR) / 3.0, 0.06, 1.0).astype(np.float32)
ST_P = rng0.random(NSTAR).astype(np.float32)
# dust specks flying at the camera
ND = 360
DU_A = rng0.uniform(0, 2 * math.pi, ND).astype(np.float32)
DU_R = rng0.uniform(0.02, 1.0, ND).astype(np.float32)
DU_S = rng0.uniform(0.6, 1.6, ND).astype(np.float32)


def make_star(R, long_len, w_long=2.4):
    yy, xx = np.mgrid[-R:R + 1, -R:R + 1].astype(np.float32)
    r = np.hypot(xx, yy) + 1e-3
    s = np.exp(-(r / max(2.0, R * 0.016)) ** 2) * 1.2 + np.exp(-(r / (R * 0.06)) ** 2) * 0.6 + np.exp(-(r / (R * 0.2)) ** 2) * 0.16
    spikes = [(a, long_len, w_long, 1.0) for a in (8, 98, 188, 278)]
    spikes += [(a, long_len * 0.42, w_long * 0.75, 0.6) for a in (53, 143, 233, 323)]
    spikes += [(a, long_len * 0.22, w_long * 0.55, 0.35) for a in (30, 120, 210, 300)]
    for ang, ln, w, a in spikes:
        th = math.radians(ang)
        c, sn = math.cos(th), math.sin(th)
        along = xx * c + yy * sn
        perp = -xx * sn + yy * c
        al = np.clip(along, 0, None)
        s += np.exp(-(perp / (w * (1 + al / ln * 1.2))) ** 2) * np.exp(-al / ln * 2.6) * a * (along > 0)
    win = np.clip(1 - (r / R) ** 2, 0, 1) ** 1.5
    return np.clip(s * win, 0, 1.4).astype(np.float32)


STAR = make_star(460, 440, 4.6)
SPARK = {sz: make_star(sz, sz * 0.95, 1.3) for sz in (16, 24, 36, 52)}
GRAIN = [rng0.normal(0, 4.0, (H, W)).astype(np.float32) for _ in range(6)]
YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)
# stripe and dot patterns for hatched bars / halftone donuts
STRIPES = (((XX + YY) // 9) % 2 == 0)
DOTS = ((np.mod(XX, 14) - 7) ** 2 + (np.mod(YY, 14) - 7) ** 2) < 12

# ------------------------------------------------------------------ star (cursor) path
JUMPS = [
    (T_START, 1130, 455), (BIG[0], 700, 380), (BIG[1], 1250, 640), (b2t(55), 820, 700), (b2t(56.5), 1180, 300),
    (b2t(58), 760, 520), (b2t(58.5), 1010, 400), (b2t(60), 1290, 560), (b2t(61), 870, 470), (T_DROP, 960, 520),
]
SNAP = 0.06


def star_pos(t):
    for i in range(len(JUMPS) - 1):
        ta, xa, ya = JUMPS[i]
        tb, xb, yb = JUMPS[i + 1]
        if ta <= t < tb:
            if i == len(JUMPS) - 2:
                u = smooth((t - T_RISE) / (tb - T_RISE)) if t > T_RISE else 0.0
            else:
                u = eout((t - (tb - SNAP)) / SNAP, 2) if t > tb - SNAP else 0.0
            wob = 5 * math.sin(t * 2.3 + i)
            return xa + (xb - xa) * u + wob, ya + (yb - ya) * u + 0.6 * wob, u
    return JUMPS[-1][1], JUMPS[-1][2], 1.0


HUD_SPRING = {"x": None, "y": None, "vx": 0.0, "vy": 0.0}


# ------------------------------------------------------------------ text
FL = ImageFont.truetype(FONT_LAT, 36)
FC = ImageFont.truetype(FONT_CJK, 38)
FM = ImageFont.truetype(FONT_MONO, 16)
FM_BIG = ImageFont.truetype(FONT_MONO, 22)
CAPS = [(b2t(48), "FlyingTuna", "hat"), (BIG[1], "from #3668 to #1", "16th")]
PREFIX, SEP = "鮪", " : "


def cap_sprite(text):
    pw = FC.getlength(PREFIX)
    full_w = int(pw + FL.getlength(SEP + text)) + 10
    img = Image.new("L", (full_w, 60), 0)
    d = ImageDraw.Draw(img)
    d.text((0, 6), PREFIX, font=FC, fill=255)
    d.text((pw, 8), SEP + text, font=FL, fill=255)
    ends = [int(pw + FL.getlength(SEP)) + 2] + [int(pw + FL.getlength(SEP + text[:k])) + 2 for k in range(1, len(text) + 1)]
    return np.array(img), ends, (W - full_w) // 2, int(H * 0.878)


CAP_SPR = [cap_sprite(c[1]) for c in CAPS]
_txt_cache = {}


def text_sprite(s, font):
    key = (s, id(font))
    if key not in _txt_cache:
        w = int(font.getlength(s)) + 4
        h = int(font.size * 1.4)
        im = Image.new("L", (w, h), 0)
        ImageDraw.Draw(im).text((1, 1), s, font=font, fill=255)
        _txt_cache[key] = np.array(im)
        if len(_txt_cache) > 4000:
            _txt_cache.clear()
    return _txt_cache[key]


def put_text(img, s, x, y, font=None, val=255, anchor="l"):
    spr = text_sprite(s, font or FM)
    h, w = spr.shape
    if anchor == "r":
        x -= w
    elif anchor == "c":
        x -= w // 2
    x, y = int(x), int(y)
    if x >= W or y >= H or x + w <= 0 or y + h <= 0:
        return
    sx0, sy0 = max(0, -x), max(0, -y)
    sx1, sy1 = min(w, W - x), min(h, H - y)
    reg = img[y + sy0:y + sy1, x + sx0:x + sx1]
    m = spr[sy0:sy1, sx0:sx1]
    if val >= 128:
        reg[:] = np.maximum(reg, m)
    else:
        reg[:] = np.minimum(reg, 255 - m)


def draw_caption(img, t):
    idx = None
    for i, c in enumerate(CAPS):
        if t >= c[0]:
            idx = i
    if idx is None:
        return
    t0, text, mode = CAPS[idx]
    mask, ends, x0, y0 = CAP_SPR[idx]
    if mode == "hat":
        n = 2 * count_events(t, [h for h in HATS if h >= t0 - 1e-9])
    else:
        n = int((t - t0) / E16) + 1
    if t >= T_RISE:  # erase two characters per 16th of the kick roll
        n = len(text) - 2 * count_events(t, RISE16)
    if t >= T_GAP:
        return
    cut = ends[max(0, min(n, len(ends) - 1))]
    m = mask[:, :cut]
    h, w = m.shape
    jit = 0
    if since(t, last_event(t, RISE16) or -9) < 0.03 or any(0 <= t - b < 0.05 for b in BIG):
        jit = int(rng0.integers(-14, 15))
    xa = x0 + jit
    reg = img[y0:y0 + h, xa:xa + w]
    reg[:] = np.maximum(reg, (m * 0.97).astype(np.uint8))


# ------------------------------------------------------------------ shots
class Shot:
    pass


def gen_shots():
    r = np.random.default_rng(SEED * 17 + 1)
    bounds = sorted(set([round(b, 5) for b in BEATS + ACC + BIG if b < T_RISE - 1e-6]))
    bounds = [b for b in bounds if b >= T_START - 1e-6] + [T_RISE]
    shots, prev = [], 0.0
    for i, t0 in enumerate(bounds[:-1]):
        sh = Shot()
        sh.t0, sh.t1 = t0, bounds[i + 1]
        sh.phase = 1 if t0 < BIG[0] - 1e-6 else 2
        for _ in range(30):
            ang = r.uniform(-84, 84)
            if abs(ang - prev) > 32:
                break
        prev = ang
        sh.ang, sh.omega, sh.side = ang, r.uniform(-12, 12), int(r.choice([-1, 1]))
        sh.snap = [r.uniform(-7, 7) for _ in range(8)]
        sh.lines = []
        if sh.phase == 2:
            nl = int(r.choice([0, 0, 1, 1, 2]))
            for _ in range(nl):
                sh.lines.append((r.uniform(-560, 560), r.uniform(-300, 300), ang + r.choice([-1, 1]) * r.uniform(28, 75)))
        items = []
        n_items = int(r.integers(1, 3)) if sh.phase == 1 else int(r.integers(3, 7))
        for _ in range(n_items):
            k = r.choice(["bar", "hbar", "line", "ring", "donut", "half", "small"], p=[0.18, 0.1, 0.17, 0.2, 0.12, 0.08, 0.15])
            col = int(r.choice([0, 255]))
            if k in ("bar", "hbar"):
                items.append(dict(k="bar", x=r.uniform(0, W), w=r.uniform(46, 190), c=col, step=r.uniform(-140, 140), hatch=k == "hbar"))
            elif k == "line":
                items.append(dict(k="bar", x=r.uniform(0, W), w=r.uniform(2.0, 4.5), c=col, step=r.uniform(-90, 90), hatch=False))
            else:
                rad, th = {"ring": (r.uniform(70, 330), r.uniform(2.5, 6)), "donut": (r.uniform(55, 180), r.uniform(20, 48)),
                           "half": (r.uniform(80, 170), r.uniform(34, 60)), "small": (r.uniform(14, 36), r.uniform(5, 11))}[k]
                items.append(dict(k="ring", near=bool(r.random() < 0.5), ox=r.normal(0, 260), oy=r.normal(0, 170),
                                  x=r.uniform(80, W - 80), y=r.uniform(80, H - 80), r=rad, th=th, c=col, halftone=k == "half",
                                  g=r.uniform(-0.05, 0.35), vx=r.normal(0, 60), vy=r.normal(0, 35)))
                if k == "ring" and r.random() < 0.35:
                    it = dict(items[-1])
                    it["r"], it["th"] = rad * r.uniform(1.1, 1.3), th * 0.7
                    items.append(it)
                if k == "small" and r.random() < 0.6:
                    for _ in range(int(r.integers(1, 3))):
                        it = dict(items[-1])
                        it["ox"] += r.normal(0, 90)
                        it["oy"] += r.normal(0, 60)
                        it["x"] += r.normal(0, 90)
                        it["y"] += r.normal(0, 60)
                        items.append(it)
        for _ in range(int(r.integers(2, 5)) if sh.phase == 1 else int(r.integers(4, 9))):
            items.append(dict(k="spark", x=r.uniform(40, W - 40), y=r.uniform(40, H * 0.84), sz=int(r.choice([16, 24, 36, 52])),
                              c=int(r.choice([255, 255, 0])), ph=int(r.integers(0, 2))))
        sh.arcs = [(r.uniform(0, 360), r.uniform(25, 120), r.choice([-1, 1]) * r.uniform(40, 160), rr) for rr in (370, 410, 450)]
        sh.items = items
        shots.append(sh)
    return shots


SHOTS = gen_shots()


# ------------------------------------------------------------------ particles
def gen_particles():
    r = np.random.default_rng(SEED * 7 + 3)
    ps = []
    for i, tb in enumerate(BIG):
        x, y, _ = star_pos(tb + 1e-3)
        for _ in range(170):
            a, sp = r.uniform(0, 2 * math.pi), r.uniform(350, 1700)
            ps.append(dict(t0=tb, x=x, y=y, vx=math.cos(a) * sp, vy=math.sin(a) * sp, life=r.uniform(0.45, 1.0),
                           sz=r.uniform(2.5, 9), c=int(r.choice([255, 255, 0])), sq=bool(r.random() < 0.6)))
    for ta in ACC:
        x, y, _ = star_pos(ta + 1e-3)
        for _ in range(48):
            a, sp = r.uniform(0, 2 * math.pi), r.uniform(250, 1000)
            ps.append(dict(t0=ta, x=x, y=y, vx=math.cos(a) * sp, vy=math.sin(a) * sp, life=r.uniform(0.3, 0.7),
                           sz=r.uniform(2, 6), c=int(r.choice([255, 0])), sq=bool(r.random() < 0.6)))
    for tr in RISE16:  # sucked in from the frame edges
        for _ in range(26):
            a = r.uniform(0, 2 * math.pi)
            ps.append(dict(t0=tr, inward=True, a=a, d0=r.uniform(700, 1100), life=E16 * 2.2, sz=r.uniform(2, 6),
                           c=int(r.choice([255, 255, 0])), sq=bool(r.random() < 0.5)))
    return ps


PARTS = gen_particles()


# ------------------------------------------------------------------ drawing helpers
def ring(img, x, y, r, th, c):
    if r > 1 and th > 0.4:
        cv2.circle(img, (int(x * 16), int(y * 16)), int(r * 16), int(c), max(1, int(round(th))), cv2.LINE_AA, shift=4)


def arc(img, x, y, r, a0, a1, th, c):
    if r > 1:
        cv2.ellipse(img, (int(x * 16), int(y * 16)), (int(r * 16), int(r * 16)), 0, a0, a1, int(c), max(1, int(round(th))), cv2.LINE_AA, shift=4)


def line(img, x0, y0, x1, y1, c, th=1):
    cv2.line(img, (int(x0 * 16), int(y0 * 16)), (int(x1 * 16), int(y1 * 16)), int(c), th, cv2.LINE_AA, shift=4)


def bar(img, x, w, c, hatch=False):
    x0, x1 = int(round(x - w / 2)), int(round(x + w / 2))
    if x1 < 0 or x0 >= W:
        return
    x0, x1 = max(0, x0), min(W, max(x0 + 1, x1 + 1))
    if hatch:
        reg = img[:, x0:x1]
        reg[STRIPES[:, x0:x1]] = c
        reg[:, :2] = c
        reg[:, -2:] = c
    else:
        img[:, x0:x1] = c


def halftone_ring(img, x, y, r, th, c):
    r0, r1 = r - th / 2, r + th / 2
    xa, xb = int(max(0, x - r1 - 1)), int(min(W, x + r1 + 2))
    ya, yb = int(max(0, y - r1 - 1)), int(min(H, y + r1 + 2))
    if xa >= xb or ya >= yb:
        return
    d = np.hypot(XX[ya:yb, xa:xb] - x, YY[ya:yb, xa:xb] - y)
    m = (d >= r0) & (d <= r1) & DOTS[ya:yb, xa:xb]
    img[ya:yb, xa:xb][m] = c
    ring(img, x, y, r1, 2, c)
    ring(img, x, y, r0, 2, c)


def blit(imgf, spr, x, y, k, dark=False):
    R = spr.shape[0] // 2
    x, y = int(round(x)), int(round(y))
    x0, y0, x1, y1 = x - R, y - R, x + R + 1, y + R + 1
    sx0, sy0 = max(0, -x0), max(0, -y0)
    sx1, sy1 = spr.shape[1] - max(0, x1 - W), spr.shape[0] - max(0, y1 - H)
    if sx1 <= sx0 or sy1 <= sy0:
        return
    reg = imgf[max(0, y0):min(H, y1), max(0, x0):min(W, x1)]
    if dark:
        reg *= np.clip(1 - spr[sy0:sy1, sx0:sx1] * k, 0, 1)
    else:
        reg += spr[sy0:sy1, sx0:sx1] * k


# ------------------------------------------------------------------ frame
def render(fl):
    t = (F0 + fl) / FPS
    u = fl / (N - 1)
    low, mid, high, rms = float(LOW[fl]), float(MID[fl]), float(HIGH[fl]), float(RMS[fl])
    spec = spectrum(fl)
    lh = last_event(t, HATS)
    hat = decay(t, lh, 22) if (lh is not None and t < T_RISE) else 0.0
    hat_i = count_events(t, HATS)
    beat_k = decay(t, last_event(t, BEATS) or -9, 14)
    acc_k = max(decay(t, a, 9) for a in ACC)
    big_k = max(decay(t, b, 6) for b in BIG)
    r16 = last_event(t, RISE16)
    rise_k = decay(t, r16, 26) if r16 is not None else 0.0
    rise_u = c01((t - T_RISE) / (T_GAP - T_RISE)) if t >= T_RISE else 0.0
    in_gap = t >= T_GAP
    dip = smooth((t - DIP) / 0.03) if DIP <= t < BIG[0] else 0.0

    px, py, jump_u = star_pos(t)
    # HUD follows the star on a spring (lags behind the flick, overshoots)
    hs = HUD_SPRING
    if hs["x"] is None or fl == 0:
        hs.update(x=px, y=py, vx=0.0, vy=0.0)
    for _ in range(2):
        ax = (px - hs["x"]) * 900 - hs["vx"] * 38
        ay = (py - hs["y"]) * 900 - hs["vy"] * 38
        hs["vx"] += ax / (2 * FPS)
        hs["vy"] += ay / (2 * FPS)
        hs["x"] += hs["vx"] / (2 * FPS)
        hs["y"] += hs["vy"] / (2 * FPS)
    hx, hy = hs["x"], hs["y"]

    # ---------------- background: nebula (with shockwave refraction), parallax stars, dust
    zb = 1.0 + 0.06 * smooth(u) + 0.25 * rise_u ** 2
    cx, cy = BW / 2 + 70 * math.sin(u * 2.2) + (px - W / 2) * 0.05, BH / 2 + 35 * math.cos(u * 1.7) + (py - H / 2) * 0.05
    M = np.float32([[zb, 0, W / 2 - zb * cx], [0, zb, H / 2 - zb * cy]])
    waves = [(b, 26.0, 0.55) for b in BIG] + [(a, 10.0, 0.45) for a in ACC]
    mapx = mapy = None
    for tw, amp, dur in waves:
        d = t - tw
        if 0 <= d < dur:
            R = 60 + 1500 * eout(d / dur, 2.0)
            A = amp * (1 - d / dur)
            dxs, dys = XX - px, YY - py
            rr = np.sqrt(dxs * dxs + dys * dys) + 1e-3
            off = A * np.exp(-((rr - R) / 60) ** 2)
            if mapx is None:
                mapx, mapy = XX.copy(), YY.copy()
            mapx -= off * dxs / rr
            mapy -= off * dys / rr
    bg = cv2.warpAffine(NEB, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    if mapx is not None:
        bg = cv2.remap(bg, mapx, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    imgf = bg * 255 * (0.86 + 0.22 * rms)
    # parallax stars
    zs = 1 + (zb - 1) * (0.4 + 1.2 * ST_D)
    sx = (ST_X - W / 2) * zs + W / 2 - (px - W / 2) * 0.02 * ST_D
    sy = (ST_Y - H / 2) * zs + H / 2 - (py - H / 2) * 0.02 * ST_D
    tw_ = 0.55 + 0.45 * np.where((ST_P * 4 + hat_i).astype(int) % 2 == 0, hat, 1 - hat)
    sb = ST_B * tw_ * 255 * (0.8 + 0.5 * high)
    ok = (sx >= 1) & (sx < W - 2) & (sy >= 1) & (sy < H - 2)
    ix, iy, ib = sx[ok].astype(np.int32), sy[ok].astype(np.int32), sb[ok]
    np.add.at(imgf, (iy, ix), ib)
    big_s = ST_B[ok] > 0.5
    np.add.at(imgf, (iy[big_s], ix[big_s] + 1), ib[big_s] * 0.5)
    np.add.at(imgf, (iy[big_s] + 1, ix[big_s]), ib[big_s] * 0.5)
    # dust streaks (speed with the energy)
    spd = 0.18 + 0.9 * rms + 2.5 * big_k + 3.0 * rise_u
    img = np.clip(imgf, 0, 255).astype(np.uint8)
    rr_ = (DU_R + t * 0.12 * DU_S * (1 + spd)) % 1.0
    for a, r0, s in zip(DU_A, rr_, DU_S):
        rad = 60 + (r0 ** 2.2) * 1300
        ln = 2 + spd * 18 * r0
        x0, y0 = W / 2 + math.cos(a) * rad, H / 2 + math.sin(a) * rad * 0.62
        x1, y1 = W / 2 + math.cos(a) * (rad + ln), H / 2 + math.sin(a) * (rad + ln) * 0.62
        line(img, x0, y0, x1, y1, int(140 + 115 * r0), 1)
    imgf = img.astype(np.float32)
    # star glow (+ a little flare ghost line through the centre)
    starA = 255 * (0.85 + 0.35 * rms + 0.8 * big_k + 0.35 * acc_k + 0.25 * hat + 0.6 * rise_k)
    blit(imgf, STAR, px, py, starA)
    for gk, gs in ((0.55, 36), (-0.35, 24), (-0.8, 52)):
        gx, gy = W / 2 + (W / 2 - px) * gk, H / 2 + (H / 2 - py) * gk
        blit(imgf, SPARK[gs], gx, gy, 90 * (0.6 + rms))
    if dip > 0:
        imgf *= 1 - 0.55 * dip
    img = np.clip(imgf, 0, 255).astype(np.uint8)

    shot = next((s for s in SHOTS if s.t0 - 1e-9 <= t < s.t1 - 1e-9), None)
    steps = count_events(t, [h for h in HATS if shot is not None and h >= shot.t0 - 1e-9])
    # ---------------- shot geometry (stepped on the hats, pulsing on the kick)
    pulse = 1 + 0.10 * hat + 0.12 * low + 0.25 * acc_k
    if shot is not None:
        dt = t - shot.t0
        for it in shot.items:
            if it["k"] == "bar":
                bar(img, it["x"] + it["step"] * steps, it["w"] * (1 + 0.25 * low), it["c"], it["hatch"])
        for it in shot.items:
            if it["k"] == "ring":
                if it["near"]:
                    x, y = hx + it["ox"] + it["vx"] * dt, hy + it["oy"] + it["vy"] * dt
                else:
                    x, y = it["x"] + it["vx"] * dt, it["y"] + it["vy"] * dt
                rr = it["r"] * (1 + it["g"] * dt) * pulse
                if it["halftone"]:
                    halftone_ring(img, x, y, rr, it["th"], it["c"])
                else:
                    ring(img, x, y, rr, it["th"] * (1 + 0.6 * low), it["c"])
    # ---------------- edge equalizers
    if BIG[0] <= t < T_GAP:
        grow = eout((t - BIG[0]) / 0.12) * (1 - 0.6 * rise_u)
        nb = 24
        for i in range(nb):
            e = spec[(i * 11) % len(spec)]
            hgt = int((e ** 1.4) * 330 * grow * (1 + 0.3 * hat))
            x = int((i + 0.5) * W / nb)
            if hgt > 3:
                if i % 2 == 0:
                    img[0:hgt, x - 22:x + 22] = 255
                    img[hgt + 6:hgt + 10, x - 22:x + 22] = 255
                else:
                    img[H - hgt:H, x - 22:x + 22] = 0
                    img[H - hgt - 10:H - hgt - 6, x - 22:x + 22] = 0
    # ---------------- HUD around the star (boot-up on the first hats)
    boot = count_events(t, HATS[:6])
    rot = t * 22 + 60 * big_k
    sc = (1 - 0.35 * rise_u) * (1 + 0.06 * beat_k)
    if boot >= 2:  # dial: ticks light up with the combo
        nt = 90
        lit = hat_i % nt
        for i in range(nt):
            a = math.radians(rot + i * 4)
            r0 = 228 * sc
            ln = 16 if i % 5 == 0 else 8
            if i <= lit:
                ln += 6
            line(img, hx + math.cos(a) * r0, hy + math.sin(a) * r0, hx + math.cos(a) * (r0 + ln), hy + math.sin(a) * (r0 + ln), 255, 2 if i % 5 == 0 else 1)
        arc(img, hx, hy, 220 * sc, rot, rot + 4 * lit, 3, 255)
    if boot >= 3:  # dashed ring, spins harder on the kick
        r1 = 300 * sc
        base = -t * 40 - 90 * low * 0 - 200 * big_k
        for k in range(36):
            a0 = base + k * 10
            arc(img, hx, hy, r1, a0, a0 + 5.5, 3, 255 if k % 6 else 0)
    if boot >= 4:  # crosshair with ticks
        g = 200 * sc
        col = 255 if (hat_i % 2 == 0 or t >= T_RISE) else 180
        line(img, 0, hy, hx - g, hy, col)
        line(img, hx + g, hy, W, hy, col)
        line(img, hx, 0, hx, hy - g, col)
        line(img, hx, hy + g, hx, H, col)
        for k in range(1, 18):
            d = g + k * 34
            tl = 10 if k % 4 == 0 else 5
            for sgn in (-1, 1):
                line(img, hx + sgn * d, hy - tl, hx + sgn * d, hy + tl, col)
                line(img, hx - tl, hy + sgn * d, hx + tl, hy + sgn * d, col)
    if boot >= 5:  # radial visualizer (osu! menu style)
        nb = 72
        r0 = 150 * sc
        for i in range(nb):
            e = spec[(i * 5) % len(spec)]
            ln = 8 + (e ** 1.3) * 120 * (1 + 0.5 * big_k + 0.6 * rise_u)
            a = math.radians(rot * 0.5 + i * 5)
            line(img, hx + math.cos(a) * r0, hy + math.sin(a) * r0, hx + math.cos(a) * (r0 + ln), hy + math.sin(a) * (r0 + ln), 255, 4)
        ring(img, hx, hy, r0 - 6, 2, 255)
    if shot is not None and shot.phase == 2:
        for a0, span, w_, rr in shot.arcs:
            a = a0 + w_ * (t - shot.t0)
            arc(img, hx, hy, rr * sc * (1 + 0.05 * hat), a, a + span, 2 if rr != 410 else 7, 255)
    # ---------------- osu! layer: hit circles, approach rings, follow points, judgements
    for i in range(1, len(JUMPS)):
        tj, jx, jy = JUMPS[i]
        span = BEAT * (5.0 if i == len(JUMPS) - 1 else 1.6)
        if tj - span <= t < tj:
            a = (t - (tj - span)) / span
            ring(img, jx, jy, 64, 9, 255)
            ring(img, jx, jy, 46, 2, 255)
            ring(img, jx, jy, 64 * (1 + 2.8 * (1 - a)), 5 if i < len(JUMPS) - 1 else 7, 255)
            if i < len(JUMPS) - 1:
                put_text(img, str(i), jx, jy - 15, FM_BIG, 255, "c")
            _, qx, qy = JUMPS[i - 1]
            dd = math.hypot(jx - qx, jy - qy)
            nd = max(2, int(dd / 44))
            shown = int(nd * min(1.0, a * 1.8))
            for k in range(1, min(shown, nd)):
                f = k / nd
                cv2.circle(img, (int(qx + (jx - qx) * f), int(qy + (jy - qy) * f)), 4, 255, -1, cv2.LINE_AA)
        if i < len(JUMPS) - 1 and 0 <= t - tj < 0.42:
            d = (t - tj) / 0.42
            put_text(img, "300", jx, jy - 110 - 30 * eout(d), FM_BIG, 255, "c")
    # shock rings
    for tw, amp, dur in waves:
        d = t - tw
        if 0 <= d < dur * 0.8:
            q = d / (dur * 0.8)
            ring(img, px, py, 64 + 1300 * eout(q, 2.2), (26 if amp > 20 else 12) * (1 - q) + 2, 255)
            if amp > 20:
                ring(img, px, py, 64 + 900 * eout(q, 1.6), 3, 0)
    # approach circles on the kick roll converging to the star
    if T_RISE <= t < T_GAP:
        for k, tr in enumerate(RISE16):
            d = t - tr
            if 0 <= d < E16 * 3:
                q = d / (E16 * 3)
                ring(img, px, py, 70 + 700 * (1 - q) ** 1.5, 3 + 6 * q, 255 if k % 2 == 0 else 0)
    # particles
    for p in PARTS:
        d = t - p["t0"]
        if 0 <= d < p["life"]:
            q = d / p["life"]
            if p.get("inward"):
                rad = p["d0"] * (1 - eout(q, 1.6)) + 40
                x, y = px + math.cos(p["a"]) * rad, py + math.sin(p["a"]) * rad
            else:
                k = (1 - math.exp(-d * 3.2)) / 3.2
                x, y = p["x"] + p["vx"] * k, p["y"] + p["vy"] * k + 120 * d * d
            s = p["sz"] * (1 - 0.6 * q)
            if p["sq"]:
                cv2.rectangle(img, (int(x - s), int(y - s)), (int(x + s), int(y + s)), p["c"], -1)
            else:
                cv2.circle(img, (int(x * 16), int(y * 16)), int(s * 16), p["c"], -1, cv2.LINE_AA, shift=4)
    # sparkles twinkling on alternating hats
    imgf = img.astype(np.float32)
    if shot is not None:
        for it in shot.items:
            if it["k"] == "spark":
                k = 0.45 + 0.55 * (hat if (it["ph"] + hat_i) % 2 == 0 else 1 - hat)
                blit(imgf, SPARK[it["sz"]], it["x"], it["y"], (255 * k) if it["c"] == 255 else k, dark=it["c"] == 0)
    img = np.clip(imgf, 0, 255).astype(np.uint8)
    # ---------------- micro typography / viewfinder
    m = 46
    for (ax, ay, dx, dy) in ((m, m, 1, 1), (W - m, m, -1, 1), (m, H - m, 1, -1), (W - m, H - m, -1, -1)):
        line(img, ax, ay, ax + 44 * dx, ay, 255, 2)
        line(img, ax, ay, ax, ay + 44 * dy, 255, 2)
    tc = t
    put_text(img, f"TC {int(tc // 60):02d}:{int(tc % 60):02d}:{int((tc % 1) * 60):02d}", m + 6, H - m - 34)
    put_text(img, f"{hat_i:03d}x", m + 6, H - m - 64, FM_BIG)
    put_text(img, "BPM 189 · 4/4", W - m - 6, m + 10, anchor="r")
    put_text(img, f"BEAT {48 + (t - b2t(48)) / BEAT:5.2f}", W - m - 6, m + 32, anchor="r")
    put_text(img, "FT // 2017.05 → 2019.02", m + 6, m + 10)
    if (t % E8) < E8 * 0.55 and t < T_GAP:
        cv2.circle(img, (W - m - 92, H - m - 26), 6, 255, -1, cv2.LINE_AA)
    put_text(img, "REC", W - m - 6, H - m - 36, anchor="r")
    if boot >= 2:
        put_text(img, f"X {int(px):04d}  Y {int(py):04d}", hx + 250 * sc, hy - 250 * sc)
        put_text(img, f"LOW {low:4.2f}  MID {mid:4.2f}", hx + 250 * sc, hy - 228 * sc)
        put_text(img, f"#{max(1, int(3668 * (1 - smooth((t - T_START) / (T_DROP - T_START))) ** 2)):04d}", hx - 250 * sc, hy + 230 * sc, FM_BIG, 255, "r")
    draw_caption(img, t)
    imgf = img.astype(np.float32)

    # ---------------- negative split
    qx, qy = min(W - 120, max(120, px)), min(H - 120, max(120, py))
    if shot is not None:
        snap = shot.snap[min(steps, 7)] if shot.phase == 2 else 0.0
        ang = math.radians(shot.ang + shot.omega * (t - shot.t0) + snap)
        mm = np.clip(0.5 + ((XX - qx) * -math.sin(ang) + (YY - qy) * math.cos(ang)) * shot.side, 0, 1)
        for ox, oy, a2 in shot.lines:
            a2 = math.radians(a2 + shot.omega * (t - shot.t0) - snap)
            m2 = np.clip(0.5 + (XX - qx - ox) * -math.sin(a2) + (YY - qy - oy) * math.cos(a2), 0, 1)
            mm = mm + m2 - 2 * mm * m2
    else:  # kick roll: the line steps a little on every 16th, shards multiply
        k = count_events(t, RISE16)
        ang = math.radians(-30 + 14 * k)
        mm = np.clip(0.5 + (XX - qx) * -math.sin(ang) + (YY - qy) * math.cos(ang), 0, 1)
        for j in range(min(k // 2, 3)):
            a2 = math.radians(40 + 50 * j + 9 * k)
            m2 = np.clip(0.5 + (XX - qx) * -math.sin(a2) + (YY - qy) * math.cos(a2), 0, 1)
            mm = mm + m2 - 2 * mm * m2
    inv = False
    for tb in BIG:
        k = int(round((t - tb) * FPS))
        if 0 <= k < 7 and k % 2 == 1:
            inv = True
    for ta in ACC:
        if int(round((t - ta) * FPS)) == 1:
            inv = True
    if T_RISE <= t < T_GAP and count_events(t, RISE16) % 2 == 0:
        inv = True
    if inv:
        mm = 1 - mm
    imgf = imgf + (255 - 2 * imgf) * mm
    # gray flashes on the big hits
    for tb, nfr in ((BIG[0], 3), (BIG[1], 2)):
        k = int(round((t - tb) * FPS))
        if 0 <= k < nfr:
            imgf = 128 + (imgf - 128) * (0.12 if k < nfr - 1 else 0.45)
    # glitch slices
    gl = 0
    for tb in BIG:
        if 0 <= t - tb < 4 / FPS:
            gl = 10
    for ta in ACC:
        if 0 <= t - ta < 2 / FPS:
            gl = max(gl, 5)
    if T_RISE <= t < T_GAP and since(t, r16) < 2 / FPS:
        gl = max(gl, 7)
    if gl:
        gr = np.random.default_rng(int(t * 1000))
        for _ in range(gl):
            y0 = int(gr.integers(0, H - 20))
            hh = int(gr.integers(6, 90))
            imgf[y0:y0 + hh] = np.roll(imgf[y0:y0 + hh], int(gr.integers(-220, 220)), axis=1)
    # silence before the drop: black, only the closing circle and the star core
    if in_gap:
        imgf[:] = 0
        tmp = np.zeros((H, W), np.uint8)
        ring(tmp, px, py, 64 + 18 * (1 - c01((t - T_GAP) / (T_DROP - T_GAP))), 7, 255)
        ring(tmp, px, py, 46, 2, 255)
        imgf = tmp.astype(np.float32)
        blit(imgf, SPARK[24], px, py, 255)
    imgf += GRAIN[fl % len(GRAIN)]
    out = np.clip(imgf, 0, 255).astype(np.uint8)
    # ---------------- camera: punch + shake + roll (applied to the whole frame)
    if not in_gap:
        zc = 1.03 + 0.015 * beat_k + 0.035 * acc_k + 0.07 * big_k + 0.04 * rise_k - 0.04 * dip
        sh_amp = 2 + 9 * low + 26 * big_k + 8 * acc_k + 10 * rise_k
        gr = np.random.default_rng(fl * 13 + 1)
        sxh, syh = gr.uniform(-1, 1) * sh_amp, gr.uniform(-1, 1) * sh_amp
        rotd = 1.4 * big_k * math.sin(t * 40) + 0.4 * acc_k * math.sin(t * 33)
        Mc = cv2.getRotationMatrix2D((W / 2, H / 2), rotd, zc)
        Mc[0, 2] += sxh
        Mc[1, 2] += syh
        out = cv2.warpAffine(out, Mc, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    return out


if STILLS:
    want = sorted(int(round(ts * FPS)) - F0 for ts in STILLS)
    for fl in range(0, max(want) + 1):  # run sequentially so the HUD spring state is right
        img = render(fl)
        if fl in want:
            cv2.imwrite(f"{STILLS_DIR}/b_{(F0 + fl) / FPS:06.3f}.png", img)
    print("stills", len(want))
    sys.exit(0)

enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                        "-c:v", "libx264", "-preset", "medium", "-crf", "14", "-pix_fmt", "yuv420p", "-movflags", "+faststart", OUT],
                       stdin=subprocess.PIPE)
for fl in range(N):
    enc.stdin.write(render(fl).tobytes())
enc.stdin.close()
enc.wait()
print("done", OUT, N, "frames")
