"""BTMC story edit: "100%". Timeline for story.py.

Everything is placed on the music grid of Camellia - Purge My Existence Out Of This World (feat. BTMC),
175 BPM, first downbeat 2.040 s. Voice lines are BTMC's own words from his Twitch clips (word timings from
faster-whisper), quotes on screen come from his osu! news interviews.
"""
import json
import math
import os

import cv2
import numpy as np

import gfx
import layers as L
import typo
from gfx import clamp01, ease_in_cubic, ease_out_back, ease_out_cubic, ease_out_expo

HERE = os.path.dirname(os.path.abspath(__file__))
CL = "clips/btmc/"

BPM = 175.0
BEAT = 60.0 / BPM
BAR = 4 * BEAT
TRACK = CL + "music/purge_full.mp3"


def tbar(b):
    """Track time of bar b."""
    return 2.040 + b * BAR


PINK, GOLD, RED, BLUE, WHITE = (255, 79, 160), (255, 196, 77), (255, 52, 72), (90, 190, 255), (255, 255, 255)
MUTED = (150, 150, 170)

# ------------------------------------------------------------------ sources (cam = webcam rect, 1920x1080 px)
SOURCES = {
    "yeah": {"file": CL + "tw_yeah_2025.mp4", "cam": [1440, 270, 480, 270]},
    "omg": {"file": CL + "tw_omg_2025.mp4", "cam": [1500, 270, 400, 210]},
    "ss2019": {"file": CL + "tw_new_top_play_2019.mp4", "cam": [1368, 762, 372, 232]},
    "passion": {"file": CL + "tw_not_just_a_game.mp4", "cam": [1400, 758, 344, 250]},
    "pp975": {"file": CL + "tw_pp900_2021.mp4", "cam": [1388, 762, 522, 296]},
    "owc": {"file": CL + "tw_owc2020_usa_won.mp4", "cam": [1526, 506, 290, 216]},
    "rplace": {"file": CL + "tw_rplace_goated_defense.mp4", "cam": [1512, 514, 290, 216]},
    "nutshell": {"file": CL + "tw_rplace_nutshell.mp4", "cam": [1512, 528, 300, 206]},
    "invasion": {"file": CL + "tw_rplace_xqc_invasion.mp4"},
    "rtvod": {"file": CL + "tw_rt1_vod_stuff.mp4"},
    "rtres": {"file": CL + "tw_rt1_mrekk_emotion.mp4"},
    "rtbr": {"file": CL + "tw_rt1_mrekk_utami_fc.mp4"},
    "k1": {"file": CL + "tw_k1_day_a.mp4", "cam": [1580, 812, 340, 268]},
    "goat": {"file": CL + "tw_best_ever_2025.mp4"},
    "lan26": {"file": CL + "tw_mcsr_lan_2026.mp4"},
}
BIGBLACK = CL + "bigblack_2015.mp4"
HAVE_BIGBLACK = os.path.exists(os.path.join(HERE, BIGBLACK))
if HAVE_BIGBLACK:
    SOURCES["bigblack"] = {"file": BIGBLACK}


def words(src, s0, s1, fix=None):
    """Whisper words of a source between s0..s1 as [(text, start, end)] (source time)."""
    base = os.path.join(HERE, SOURCES[src]["file"]).rsplit(".", 1)[0] + ".words.json"
    out = []
    for seg in json.load(open(base)):
        for w in seg["words"]:
            if s0 - 0.05 <= w["s"] and w["e"] <= s1 + 0.12:
                out.append([w["w"].strip(), w["s"], w["e"]])
    if fix:
        for i, txt in fix.items():
            out[i][0] = txt
    return [tuple(w) for w in out if w[0]]


def V(src, sin, sout, at, hl=(), fix=None, **kw):
    v = {"src": src, "sin": sin, "sout": sout, "at": at, "words": words(src, sin, sout, fix), "hl": list(hl)}
    v.update(kw)
    return v


# ------------------------------------------------------------------ time plan
T_REW = 5.52          # rewind starts
M1 = 6.20             # music in (track bar 11)
P2 = M1 + 7 * BAR     # 15.80 drop (track bar 18)
P3 = P2 + 14 * BAR    # 35.00 the fall (track bar 117)
P4 = P3 + 3 * BAR     # 39.11 finale (track bar 216)
HIT = P4 + 4 * BAR    # 44.60 final hit (track bar 220)
END = HIT + 2.9


def b1(k):
    return M1 + k * BAR


def b2(k):
    return P2 + k * BAR


# ------------------------------------------------------------------ voices
VOICES = [
    V("yeah", 35.45, 37.55, 0.35, hl=["PP"]),
    V("yeah", 41.12, 43.92, 2.75, hl=["PERSON"], fix={0: "I"}),
    V("ss2019", 19.60, 22.12, b1(3) + 0.24, hl=["SS", "FIRST", "TRY?"], fix={4: "SS", 5: ""}),
    V("ss2019", 45.07, 47.36, b1(5) + 0.15, hl=["HISTORY", "WRITTEN."]),
    V("passion", 30.60, 32.90, b2(2) + 0.10, hl=["PASSIONATE"], hl_color=GOLD),
    V("passion", 33.98, 35.50, b2(2) + 2.50, hl=["GAME."], hl_color=GOLD),
    V("rplace", 22.50, 24.42, b2(5) + 0.14, hl=["PLACE", "NOW."]),
    V("nutshell", 2.40, 5.92, b2(6) + 0.80, hl=["HISTORY", "TOGETHER."]),
    V("rtvod", 14.48, 17.30, b2(9) + 0.25, hl=["ROUNDTABLE", "SUSTAINABLE"]),
    V("k1", 13.58, 16.05, b2(12) + 0.16, hl=["1K?", "1K"], hl_color=GOLD),
    V("yeah", 35.45, 37.55, P3 + 0.08, hl=["PP."], echo=0.19, lp=1800, db=-19, caption=False),
    V("omg", 13.66, 14.90, P3 + 2.05, hl=["HUNDRED", "PERCENT", "RIGHT"], hl_color=GOLD),
    V("omg", 18.78, 19.56, P3 + 3.35, hl=["SORRY"], until=P4 - 0.03),
]

# ------------------------------------------------------------------ shots
COLD = {"type": "tint", "tint": (0.85, 0.92, 1.1), "sat": 0.35, "contrast": 1.15}
REDG = {"type": "duo", "dark": (16, 2, 6), "mid": (170, 20, 40), "light": (255, 210, 210), "contrast": 1.25}


def S(t0, t1, src, sin, layout="window", **kw):
    s = {"t0": t0, "t1": t1, "src": src, "sin": sin, "layout": layout}
    s.update(kw)
    return s


SHOTS = [
    # cold open: flash-forward to Feb 2025
    S(0.0, T_REW, "yeah", 35.10, "face", cam=[1478, 270, 252, 206], face={"w": 760, "cy": 880, "delay": 0.0},
      face_grade=COLD, bg=False, pulse=False, drift=0.01),
    # 2019: "did I seriously just SS that first try?" / "history has just been written"
    S(b1(3), b1(5) + 0.05, "ss2019", 19.60 - 0.24, "split", win={"cy": 740}, face={"cx": 700, "cy": 1080, "w": 460}),
    S(b1(5) + 0.05, P2, "ss2019", 45.07 - 0.10, "split", win={"cy": 740}, face={"cx": 700, "cy": 1080, "w": 460, "delay": 0.0},
      in_dur=0.0),
    # 2020 world cup: winner card, then his reaction
    S(P2, b2(1), "owc", 0.25, "window", crop=[380, 200, 800, 700], rate=0.6, win={"cy": 790, "w": 740},
      accent=GOLD),
    S(b2(1), b2(2), "owc", 24.2, "face", face={"w": 700, "cy": 820, "delay": 0.0},
      accent=GOLD),
    # 2021 passion
    S(b2(2), b2(2) + 2.50, "passion", 30.60 - 0.10, "face", face={"w": 860, "cy": 840}, accent=GOLD),
    S(b2(2) + 2.50, b2(5), "passion", 33.98, "face", face={"w": 960, "cy": 840, "delay": 0.0}, accent=GOLD,
      in_dur=0.0),
    # 2022 r/place
    S(b2(5), b2(6) + 0.75, "rplace", 22.50 - 0.14, "split", crop=[0, 140, 1500, 900], win={"cy": 740},
      face={"cx": 700, "cy": 1080, "w": 460}, accent=PINK),
    S(b2(6) + 0.75, b2(9), "nutshell", 2.40 - 0.05, "face", face={"w": 820, "cy": 860}, accent=PINK,
      bg_from=["rplace", 30.0]),
    # 2022 the roundtable
    S(b2(9), b2(11) + 0.6, "rtvod", 14.48 - 0.25, "full", focus=(0.33, 0.5), zoom=1.0, accent=BLUE),
    S(b2(11) + 0.6, b2(12), "rtres", 20.0, "window", crop=[0, 0, 1920, 1080], win={"cy": 760}, accent=BLUE),
    # 2024 1k
    S(b2(12), P3, "k1", 13.58 - 0.16, "split", crop=[0, 0, 1920, 1080], win={"cy": 740},
      face={"cx": 700, "cy": 1080, "w": 460}, accent=GOLD),
    # 2025 the fall
    S(P3, P3 + 2.0, "yeah", 37.0, "window", crop=[0, 120, 1920, 900], grade=REDG, win={"cy": 760, "tilt": -1.5},
      accent=RED, bg_grade=REDG),
    S(P3 + 2.0, P3 + 3.30, "omg", 13.66 - 0.05, "face", face={"w": 860, "cy": 860, "delay": 0.0},
      face_grade={"type": "tint", "tint": (1.05, 0.85, 0.85), "sat": 0.45}, accent=RED, in_dur=0.0),
    S(P3 + 3.30, P4, "omg", 18.78 - 0.05, "face", face={"w": 900, "cy": 860, "delay": 0.0},
      face_grade={"type": "tint", "tint": (1.05, 0.9, 0.9), "sat": 0.5}, accent=RED, in_dur=0.0),
    # finale backdrop (dimmed, behind the quote)
    S(P4, P4 + BAR, "goat", 2.0, "full", grade={"type": "bw"}, focus=(0.42, 0.55), zoom=1.45, pulse=False),
    S(P4 + BAR, P4 + 2 * BAR, "rtbr", 6.0, "full", grade={"type": "bw"}, focus=(0.45, 0.4), zoom=1.2, pulse=False),
    S(P4 + 2 * BAR, P4 + 3 * BAR, "rtvod", 33.0, "full", grade={"type": "bw"}, focus=(0.33, 0.5), pulse=False),
]

if HAVE_BIGBLACK:
    SHOTS.append(S(b1(2), b1(3), "bigblack", 0.0, "window", win={"cy": 800}, accent=RED))


# ------------------------------------------------------------------ event helpers
def K(ctx, v):
    return v * ctx.k


def fit(ctx, text, fname, size, max_w):
    """Largest size <= size at which text fits max_w (1080-space px)."""
    w = gfx.text_layout(text, 100, fname)[1] / 100
    return min(size, max_w / max(w, 1e-3))


def label(ctx, canvas, text, x, y, u, size=30, color=MUTED, fname="mono", align="left", alpha=1.0, dot=None,
          pill=False):
    if u < 0:
        return
    k = ctx.k
    spr = gfx.text_sprite(text, int(size * k), fname, color)
    w = spr.shape[1]
    a = clamp01(u / 0.15) * alpha
    dx = (1 - ease_out_expo(clamp01(u / 0.35))) * 40
    cx = x * k + w / 2 if align == "left" else (x * k - w / 2 if align == "right" else x * k)
    cx -= dx * k
    if pill and a > 0.01:
        ext = (w / 2 + (44 if dot else 22) * k, size * 0.95 * k)
        x0, x1 = int(cx - ext[0] - (12 * k if dot else 0)), int(cx + w / 2 + 22 * k)
        y0, y1 = int(y * k - ext[1]), int(y * k + ext[1])
        roi = canvas[max(0, y0):y1, max(0, x0):x1]
        if roi.size:
            canvas[max(0, y0):y1, max(0, x0):x1] = cv2.addWeighted(roi, 1 - 0.72 * a, np.zeros_like(roi), 0.72 * a, 0)
    gfx.blit(canvas, spr, cx, y * k, 1.0, 0, a)
    if dot:
        cv2.circle(canvas, (int(cx - w / 2 - 22 * k), int(y * k)), max(2, int(9 * k)), dot[::-1], -1, cv2.LINE_AA)


def big(ctx, canvas, text, cx, cy, u, size, color=WHITE, fname="unb", style="slam", glow=0, glow_color=None,
        stagger=0.03, dur=0.3, exit_u=None, exit_style="fall", tracking=0, stroke=0, alpha=1.0, seed=0):
    k = ctx.k
    typo.letters(canvas, text, u, cx * k, cy * k, int(size * k), fname, color, style=style, stagger=stagger, dur=dur,
                 glow=int(glow * k), glow_color=glow_color, exit_u=exit_u, exit_style=exit_style,
                 tracking=int(tracking * k), stroke=int(stroke * k), alpha=alpha, seed=seed)


def ev_rewind(ctx, canvas, ev, t):
    """VHS rewind: frames from 2025 back to 2013 flicker past with tracking distortion."""
    k, W, H = ctx.k, ctx.W, ctx.H
    u = t - ev["t0"]
    seq = ev["seq"]
    dur = ev["t1"] - ev["t0"]
    i = min(len(seq) - 1, int(u / dur * len(seq)))
    name, st = seq[i]
    src = ctx.srcs[name]
    st = st - (u - i * dur / len(seq)) * 4.0            # playing backwards, fast
    img = cv2.resize(src.frame(max(0.0, st)), (W, int(W * 9 / 16)))
    img = cv2.cvtColor(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
    img = cv2.addWeighted(img, 0.8, np.full_like(img, (60, 30, 90)), 0.2, 0)
    full = np.zeros_like(canvas)
    y0 = (H - img.shape[0]) // 2
    full[y0:y0 + img.shape[0]] = img
    rs = np.random.default_rng(int(t * 60))
    n = 14
    offs = (rs.standard_normal(n) * 28 * k).astype(int)
    band = int((u * 3.3 % 1.0) * H)
    full = ctx.post.slices(full, n, offs)
    cv2.rectangle(full, (0, band), (W, band + int(26 * k)), (230, 230, 230), -1)
    noise = (rs.random((H // 4, W // 4)) * 70).astype(np.uint8)
    noise = cv2.resize(noise, (W, H), interpolation=cv2.INTER_NEAREST)
    full = cv2.add(full, cv2.cvtColor(noise, cv2.COLOR_GRAY2BGR))
    canvas[:] = full
    blink = (int(t * 8) % 2) == 0
    if blink:
        spr = gfx.text_sprite("<< REWIND", int(44 * k), "mono", WHITE)
        gfx.blit(canvas, spr, 100 * k + spr.shape[1] / 2, 470 * k, 1.0, 0, 0.9)


def ev_title(ctx, canvas, ev, t):
    u = t - ev["t0"]
    k = ctx.k
    cy = 880
    L.shockwave(canvas, (540 * k, cy * k), u, k, PINK, 1.8, 0.6)
    L.sparks(canvas, (540 * k, cy * k), u, 7, k, n=34, color=(255, 170, 210), speed=1700, life=0.6)
    big(ctx, canvas, "BTMC", 540, cy, u, fit(ctx, "BTMC", "unb", 230, 900), WHITE, "unb", "slam", glow=26,
        glow_color=PINK, stagger=0.05, dur=0.22,
        exit_u=ev["t1"] - ev["t0"] - 0.22, exit_style="scatter", seed=3)
    if u > 0.32:
        typo.scramble(canvas, "EDWARD LING", u - 0.32, 540 * k, (cy + 210) * k, int(46 * k), "mono", MUTED, dur=0.4,
                      exit_u=ev["t1"] - ev["t0"] - 0.6, seed=11, tracking=int(10 * k))
    a = clamp01((u - 0.5) / 0.3) * (1 - clamp01((u - 1.15) / 0.2))
    label(ctx, canvas, "A STORY IN HIS OWN WORDS", 540, cy - 230, u - 0.5, 28, PINK, "mono", "center", a)


PIX = [(110, 170, 60), (90, 140, 50), (120, 85, 50), (100, 70, 40), (140, 140, 140)]


def ev_2013(ctx, canvas, ev, t):
    """A Minecraft PvP kid clicks his first circle."""
    u = t - ev["t0"]
    k = ctx.k
    cx, cy = 540, 860
    # pixel blocks assemble, then collapse into a hit circle on beat 3
    hit_t = 2 * BEAT
    rs = np.random.default_rng(5)
    n = 64
    for i in range(n):
        gx, gy = i % 8, i // 8
        tx, ty = cx - 4 * 52 + gx * 52 + 26, cy - 4 * 52 + gy * 52 + 26
        d = rs.uniform(0, 0.25)
        p = ease_out_cubic(clamp01((u - d) / 0.3))
        sx, sy = tx + rs.uniform(-500, 500) * (1 - p), ty + rs.uniform(-700, 700) * (1 - p)
        q = clamp01((u - hit_t + 0.25) / 0.25)                 # suck into the circle
        ang = math.atan2(ty - cy, tx - cx)
        r = math.hypot(tx - cx, ty - cy) * (1 - ease_in_cubic(q))
        sx, sy = sx * (1 - q) + (cx + math.cos(ang) * r) * q, sy * (1 - q) + (cy + math.sin(ang) * r) * q
        if q >= 1:
            continue
        col = PIX[(gx * 7 + gy * 3) % len(PIX)]
        s = 48 * (1 - 0.6 * q)
        cv2.rectangle(canvas, (int((sx - s / 2) * k), int((sy - s / 2) * k)), (int((sx + s / 2) * k), int((sy + s / 2) * k)),
                      col[::-1], -1)
    if u > hit_t - 0.3:
        ap = clamp01((hit_t - u) / 0.3)
        hu = u - hit_t
        sc = 1 + 0.25 * clamp01(hu / 0.1) * (1 - clamp01((hu - 0.1) / 0.3)) if hu > 0 else 1
        L.hit_circle(canvas, (cx * k, cy * k), 150 * k * sc, ap, PINK, 1.0, "1", k)
        if hu > 0:
            L.shockwave(canvas, (cx * k, cy * k), hu, k, PINK, 1.4, 0.5)
            L.glow_dot(canvas, (cx * k, cy * k), 140 * k, PINK, 0.6 * (1 - clamp01(hu / 0.4)))
    big(ctx, canvas, "A MINECRAFT PVP KID", 540, 1260, u, 58, WHITE, "unb", "rise", stagger=0.015, dur=0.3,
        exit_u=hit_t - 0.28, exit_style="up", seed=21)
    big(ctx, canvas, "FINDS OSU!", 540, 1260, u - hit_t - 0.02, 84, PINK, "unb", "slam", glow=14, glow_color=PINK,
        stagger=0.03, dur=0.2, seed=22)


def ev_2015(ctx, canvas, ev, t):
    u = t - ev["t0"]
    k = ctx.k
    top = 640 if not HAVE_BIGBLACK else 1220
    if not HAVE_BIGBLACK:
        label(ctx, canvas, "HIS MOST VIEWED VIDEO EVER", 540, top - 120, u, 30, RED, "mono", "center", 1.0, dot=RED)
        for j, line in enumerate(["“AND SOME SAY", "HE NEVER PLAYED", "OSU! AGAIN”"]):
            big(ctx, canvas, line, 540, top + j * 112, u - 0.08 - j * 0.12, 86, WHITE, "unb", "rise", stagger=0.012,
                dur=0.28, seed=30 + j)
        if u > 0.3:
            count_text(ctx, canvas, u - 0.3, 4931132, " VIEWS", 540, top + 3 * 112 + 60, 78, RED, dur=0.85)
        label(ctx, canvas, "FAILED THE BIG BLACK IN THE FINAL SECONDS", 540, top + 3 * 112 + 150, u - 0.5, 26, MUTED,
              "mono", "center")
    else:
        label(ctx, canvas, "“AND SOME SAY HE NEVER PLAYED OSU! AGAIN”", 540, top, u, 30, WHITE, "mono",
              "center", 1.0, dot=RED)


def ev_ticker(ctx, canvas, ev, t):
    """Milestones on the way up, one per bar, bottom-left."""
    u = t - ev["t0"]
    items = ev["items"]
    k = ctx.k
    for i, (at, year, text, col) in enumerate(items):
        ui = u - at
        if ui < 0:
            continue
        nxt = items[i + 1][0] - at if i + 1 < len(items) else 99
        out = clamp01((ui - nxt) / 0.2)
        if out >= 1:
            continue
        y = ev.get("y", 1290) - ease_out_expo(out) * 60
        a = (1 - out) * clamp01(ui / 0.12)
        spr_y = gfx.text_sprite(year, int(40 * k), "anton", col)
        spr_t = gfx.text_sprite(text, int(34 * k), "unb_bold", WHITE)
        x = 100
        dx = (1 - ease_out_expo(clamp01(ui / 0.3))) * -60
        pill_w = spr_y.shape[1] / k + spr_t.shape[1] / k + 60
        ov = canvas.copy()
        cv2.rectangle(ov, (int((x - 16 + dx) * k), int((y - 34) * k)), (int((x + pill_w + dx) * k), int((y + 34) * k)),
                      (14, 10, 20), -1)
        cv2.addWeighted(ov, 0.75 * a, canvas, 1 - 0.75 * a, 0, canvas)
        cv2.rectangle(canvas, (int((x - 16 + dx) * k), int((y - 34) * k)), (int((x - 10 + dx) * k), int((y + 34) * k)),
                      col[::-1], -1)
        gfx.blit(canvas, spr_y, (x + dx) * k + spr_y.shape[1] / 2, y * k, 1.0, 0, a)
        gfx.blit(canvas, spr_t, (x + 22 + dx) * k + spr_y.shape[1] + spr_t.shape[1] / 2, y * k, 1.0, 0, a)


def ev_champion(ctx, canvas, ev, t):
    u = t - ev["t0"]
    k = ctx.k
    L.shockwave(canvas, (540 * k, 760 * k), u, k, GOLD, 2.2, 0.6)
    L.sparks(canvas, (540 * k, 760 * k), u, 13, k, n=60, color=(255, 215, 120), speed=2100, life=0.9)
    label(ctx, canvas, "OSU! WORLD CUP 2020  ·  GRAND FINAL", 540, 1175, u - 0.05, 28, MUTED, "mono", "center",
          pill=True)
    big(ctx, canvas, "USA 7-6 GERMANY", 540, 1250, u - 0.15, 64, WHITE, "anton", "rise", stagger=0.02, seed=40)
    cs = fit(ctx, "CHAMPION", "unb", 118, 960)
    big(ctx, canvas, "WORLD", 540, 1370, u - 0.32, cs, GOLD, "unb", "slam", glow=18, glow_color=GOLD, stagger=0.04,
        dur=0.2, seed=41)
    big(ctx, canvas, "CHAMPION", 540, 1490, u - 0.5, cs, GOLD, "unb", "slam", glow=18, glow_color=GOLD,
        stagger=0.04, dur=0.2, seed=42)
    if u > 0.9:
        typo.shine_text(canvas, "CHAMPION", int(cs * k), "unb", 540 * k, 1490 * k, clamp01((u - 0.9) / 0.6))


def count_text(ctx, canvas, u, value, suffix, x, y, size, col, dur=0.7, align="center", glow=10):
    """Count-up number with thousands separators; motion-blurred while it spins."""
    if u < 0:
        return
    k = ctx.k
    v, vel = typo.count_value(u, 0.0, dur, 0, value)
    text = f"{int(round(v)):,}{suffix}"
    spr = gfx.text_sprite(text, int(size * k), "anton", col, glow=int(glow * k), glow_color=col)
    blur = min(40.0, abs(vel) / max(value, 1) * 30 * k)
    if blur >= 2:
        spr = gfx.vblur(spr, blur)
    sc = 1 + 0.22 * (1 - ease_out_back(clamp01(u / 0.25), 2.0))
    w = spr.shape[1]
    cx = x * k if align == "center" else (x * k - w / 2 if align == "right" else x * k + w / 2)
    gfx.blit(canvas, spr, cx, y * k, sc, 0, clamp01(u / 0.08))


def ev_counter(ctx, canvas, ev, t):
    u = t - ev["t0"]
    col = ev.get("color", GOLD)
    x, y, size = ev.get("x", 985), ev.get("y", 300), ev.get("size", 104)
    count_text(ctx, canvas, u, ev["value"], ev.get("suffix", ""), x, y, size, col, ev.get("dur", 0.7), "right")
    if ev.get("label"):
        label(ctx, canvas, ev["label"], x, y + size * 0.62, u - 0.15, 25, col, "mono", "right")


def ev_tag(ctx, canvas, ev, t):
    u = t - ev["t0"]
    col = ev.get("color", PINK)
    label(ctx, canvas, ev["text"], ev.get("x", 540), ev.get("y", 1290), u, ev.get("size", 30), col, "mono",
          ev.get("align", "center"), dot=col if ev.get("dot", True) else None, pill=True)


def ev_headline(ctx, canvas, ev, t):
    u = t - ev["t0"]
    k = ctx.k
    for j, line in enumerate(ev["lines"]):
        big(ctx, canvas, line, 540, ev.get("y", 1270) + j * 108, u - j * 0.14, ev.get("size", 92), ev.get("color", RED),
            "unb", "slam", glow=10, glow_color=ev.get("color", RED), stagger=0.025, dur=0.18,
            exit_u=ev.get("exit"), exit_style="glitch", seed=50 + j)


def ev_quote(ctx, canvas, ev, t):
    """Finale: his own sentence (osu! news interview, 2024), one phrase per bar."""
    u = t - ev["t0"]
    k = ctx.k
    ov = L.dim(canvas, 0.55)
    canvas[:] = ov
    lines = [("IF I WAS ABLE TO", 0.0, WHITE, 70), ("SET A SCORE BEFORE,", 0.12, WHITE, 70),
             ("I KNOW WITHOUT", BAR, WHITE, 70), ("A DOUBT", BAR + 0.12, WHITE, 70),
             ("I CAN DO IT", 2 * BAR, GOLD, 108), ("AGAIN.", 2 * BAR + 0.14, GOLD, 140)]
    y = 640
    for j, (text, at, col, size) in enumerate(lines):
        size = fit(ctx, text, "unb", size, 940)
        big(ctx, canvas, text, 540, y, u - at, size, col, "unb", "rise" if col == WHITE else "slam",
            glow=16 if col == GOLD else 0, glow_color=col, stagger=0.016, dur=0.3, seed=60 + j)
        y += size * 1.18 + (30 if j % 2 else 0)
    label(ctx, canvas, "BTMC  ·  OSU! NEWS INTERVIEW, 2024", 540, 1500, u - 2 * BAR - 0.4, 26, MUTED, "mono",
          "center")


def ev_montage(ctx, canvas, ev, t):
    u = t - ev["t0"]
    seq = ev["seq"]
    step = (ev["t1"] - ev["t0"]) / len(seq)
    i = min(len(seq) - 1, int(u / step))
    name, st, focus = seq[i]
    src = ctx.srcs[name]
    img = cv2.resize(src.frame(st + (u - i * step)), (ctx.W, int(ctx.W * 9 / 16)))
    zoom = 1.0 + 0.06 * ((u - i * step) / step)
    full = __import__("story").cover(src.frame(st + (u - i * step)), ctx.W, ctx.H, *focus, zoom=zoom)
    canvas[:] = cv2.addWeighted(full, 0.75, np.zeros_like(full), 0.25, 0)
    del img
    f = 1 - clamp01((u - i * step) / 0.08)
    if f > 0:
        canvas[:] = L.flash(canvas, 0.6 * f)


def ev_end(ctx, canvas, ev, t):
    u = t - ev["t0"]
    k = ctx.k
    cy = 880
    L.shockwave(canvas, (540 * k, cy * k), u, k, PINK, 2.6, 0.7)
    L.sparks(canvas, (540 * k, cy * k), u, 99, k, n=70, color=(255, 170, 210), speed=2300, life=1.0)
    L.glow_dot(canvas, (540 * k, cy * k), 420 * k, PINK, 0.22 * clamp01(u / 0.3))
    sc = 1.0 + 0.04 * u
    typo.letters(canvas, "BTMC", u, 540 * k, cy * k, int(fit(ctx, "BTMC", "unb", 230, 880) * k * sc), "unb", WHITE,
                 style="slam", stagger=0.05,
                 dur=0.2, glow=int(28 * k), glow_color=PINK, seed=7)
    if u > 0.45:
        typo.letters(canvas, "THE FACE OF OSU!", u - 0.45, 540 * k, (cy + 200) * k, int(54 * k), "unb", PINK,
                     style="rise", stagger=0.02, dur=0.3, tracking=int(6 * k), seed=8)
    label(ctx, canvas, "2013 — 2026", 540, cy - 210, u - 0.7, 34, MUTED, "mono", "center")
    a = clamp01((u - 1.1) / 0.4)
    label(ctx, canvas, "VOICE: BTMC STREAMS  ·  MUSIC: CAMELLIA — PURGE MY EXISTENCE (FEAT. BTMC)", 540,
          1460, u - 1.1, 19, (120, 120, 140), "mono", "center", a)


def ev_vignette_red(ctx, canvas, ev, t):
    u = t - ev["t0"]
    a = 0.35 * clamp01(u / 0.2)
    red = np.zeros_like(canvas)
    red[:] = (30, 10, 120)
    canvas[:] = cv2.addWeighted(canvas, 1 - a * 0.4, red, a * 0.4, 0)


def E(t0, t1, fn, **kw):
    e = {"t0": t0, "t1": t1, "fn": fn}
    e.update(kw)
    return e


EVENTS = [
    E(T_REW, M1, ev_rewind, top=True, seq=[("omg", 14), ("k1", 16), ("rtvod", 18), ("rplace", 26), ("owc", 2),
                                           ("passion", 32), ("ss2019", 44), ("ss2019", 24)]),
    E(M1, b1(1), ev_title, top=True),
    E(b1(1), b1(2), ev_2013),
    E(b1(2), b1(3), ev_2015),
    E(b1(3), P2, ev_ticker, items=[(0.0, "2017", "FIRST 500PP PLAY  ·  533PP", PINK),
                                   (BAR, "2018", "TOP 100 IN THE WORLD", PINK),
                                   (2 * BAR, "2019", "RAISE MY SWORD +HR  ·  875PP", GOLD)], y=1335),
    E(P2, b2(2), ev_champion),
    E(b2(5) + 0.3, b2(9), ev_counter, value=26973, label="WATCHING · CHANNEL RECORD", color=PINK, dur=0.9),
    E(b2(9) + 0.1, b2(11) + 0.6, ev_tag, text="THE ROUNDTABLE  ·  LOS ANGELES 2022", color=BLUE, y=1220),
    E(b2(11) + 0.6, b2(12), ev_headline, lines=["HE PAID FOR IT", "HIMSELF"], color=BLUE, y=1220, size=78),
    E(b2(12) + 1.2, P3, ev_counter, value=1116, suffix="PP", label="SEP 2024 · FIRST 1K PLAY", color=GOLD, dur=0.6),
    E(P3, P4, ev_vignette_red, under=False),
    E(P3 + 0.05, P3 + 1.95, ev_headline, lines=["THE COMMUNITY", "TURNED ON HIM"], color=RED, y=1240, size=84,
      exit=1.7),
    E(P4, HIT - BAR, ev_quote),
    E(HIT - BAR, HIT, ev_montage, top=True, seq=[("ss2019", 41.0, (0.5, 0.45)), ("rtbr", 20.0, (0.45, 0.4)),
                                                 ("rplace", 30.0, (0.4, 0.5)), ("rtres", 22.0, (0.5, 0.5)),
                                                 ("pp975", 4.0, (0.45, 0.5)), ("k1", 18.0, (0.5, 0.5)),
                                                 ("goat", 50.0, (0.5, 0.5)), ("rtvod", 16.0, (0.33, 0.5))]),
    E(HIT, END, ev_end, top=True),
]

# ------------------------------------------------------------------ chapters (title under the year)
CHAPTERS = [
    {"t0": 0.0, "t1": T_REW, "title": "FLASH-FORWARD", "color": RED},
    {"t0": b1(1), "t1": b1(2), "title": "THE BEGINNING", "color": PINK},
    {"t0": b1(2), "t1": b1(3), "title": "THE FAIL", "color": RED},
    {"t0": b1(3), "t1": P2, "title": "THE CLIMB", "color": PINK},
    {"t0": P2, "t1": b2(2), "title": "THE PEAK", "color": GOLD},
    {"t0": b2(2), "t1": b2(5), "title": "NOT JUST A GAME", "color": GOLD},
    {"t0": b2(5), "t1": b2(9), "title": "THE WAR", "color": PINK},
    {"t0": b2(9), "t1": b2(12), "title": "THE TABLE", "color": BLUE},
    {"t0": b2(12), "t1": P3, "title": "1000PP", "color": GOLD},
    {"t0": P3, "t1": P4, "title": "THE FALL", "color": RED},
]


YEAR_KEYS = [(0.0, 2025.0), (T_REW, 2025.0), (M1, 2013.0, "out"), (b1(2), 2013.0), (b1(2) + 0.35, 2015.0, "out"),
             (b1(3), 2015.0), (b1(3) + 0.35, 2017.0, "out"), (b1(4), 2017.0), (b1(4) + 0.35, 2018.0, "out"),
             (b1(5), 2018.0), (b1(5) + 0.35, 2019.0, "out"), (P2, 2019.0), (P2 + 0.35, 2020.0, "out"),
             (b2(2), 2020.0), (b2(2) + 0.35, 2021.0, "out"), (b2(5), 2021.0), (b2(5) + 0.35, 2022.0, "out"),
             (b2(12), 2022.0), (b2(12) + 0.35, 2024.0, "out"), (P3, 2024.0), (P3 + 0.35, 2025.0, "out"),
             (HIT - BAR, 2025.0), (HIT, 2026.0, "out")]

TRACKS = {
    "year": YEAR_KEYS,
    "year_alpha": [(0.0, 1.0), (M1 - 0.01, 1.0), (M1, 0.0, "step"), (b1(1) - 0.01, 0.0), (b1(1), 1.0, "step"),
                   (P4 - 0.01, 1.0), (P4 + 0.2, 0.0), (HIT - BAR, 0.0)],
    "rail_alpha": [(0.0, 1.0), (M1 - 0.01, 1.0), (M1, 0.0, "step"), (b1(1) - 0.01, 0.0), (b1(1), 1.0, "step"),
                   (HIT - 0.01, 1.0), (HIT, 1.0)],
    "accent": [(0.0, RED), (M1, PINK, "step"), (P2 - 0.01, PINK), (P2, GOLD, "step"), (b2(5) - 0.01, GOLD),
               (b2(5), PINK, "step"), (b2(9) - 0.01, PINK), (b2(9), BLUE, "step"), (b2(12) - 0.01, BLUE),
               (b2(12), GOLD, "step"), (P3 - 0.01, GOLD), (P3, RED, "step"), (P4 - 0.01, RED), (P4, GOLD, "step"),
               (HIT - 0.01, GOLD), (HIT, PINK, "step")],
    "flash": [(0, 0), (M1, 0.9, "step"), (M1 + 0.22, 0.0), (P2, 1.0, "step"), (P2 + 0.3, 0.0),
              (b2(5), 0.5, "step"), (b2(5) + 0.18, 0.0), (b2(9), 0.5, "step"), (b2(9) + 0.18, 0.0),
              (b2(12), 0.5, "step"), (b2(12) + 0.18, 0.0), (P4, 0.6, "step"), (P4 + 0.25, 0.0),
              (HIT, 1.0, "step"), (HIT + 0.35, 0.0)],
    "zoom_blur": [(0, 0), (M1 - 0.12, 0.0), (M1, 0.25, "in"), (M1 + 0.2, 0.0), (P2 - 0.1, 0.0), (P2, 0.3, "in"),
                  (P2 + 0.25, 0.0), (b2(2) - 0.08, 0.0), (b2(2), 0.18, "in"), (b2(2) + 0.18, 0.0),
                  (b2(5) - 0.08, 0.0), (b2(5), 0.2, "in"), (b2(5) + 0.18, 0.0), (b2(9) - 0.08, 0.0),
                  (b2(9), 0.2, "in"), (b2(9) + 0.18, 0.0), (b2(12) - 0.08, 0.0), (b2(12), 0.2, "in"),
                  (b2(12) + 0.18, 0.0), (HIT - 0.1, 0.0), (HIT, 0.3, "in"), (HIT + 0.3, 0.0)],
    "rgb": [(0, 0), (T_REW, 6.0, "step"), (M1, 0.0, "step"), (P3, 9.0, "step"), (P3 + 0.5, 1.5), (P4, 0.0, "step")],
    "glitch": [(0, 0), (P3, 0.9, "step"), (P3 + 0.35, 0.1), (P3 + 1.9, 0.0), (P3 + 1.95, 0.6, "step"),
               (P3 + 2.1, 0.0)],
    "whip": sum([[(x - 0.06, 0.0), (x, 70.0, "in"), (x + 0.09, 0.0)] for x in
                 (b1(5) + 0.05, b2(1), b2(2) + 2.50, b2(6) + 0.75, b2(11) + 0.6, P3 + 2.0, P3 + 3.30)], [(0, 0.0)]),
    "bloom": [(0, 0.3), (P2, 0.7, "step"), (P2 + 1.0, 0.4), (HIT, 0.8, "step"), (HIT + 1.2, 0.45)],
    "dark": [(0, 0.0), (END - 0.8, 0.0), (END, 1.0)],
}

MUSIC = [
    {"file": TRACK, "from": tbar(11), "to": tbar(18), "at": M1, "fade_in": 0.02},
    {"file": TRACK, "from": tbar(18), "to": tbar(32), "at": P2, "fade_out": 0.03},
    {"file": TRACK, "from": tbar(117), "to": tbar(120), "at": P3, "lp": 900, "gain": 1.25, "fade_in": 0.01,
     "fade_out": 0.05},
    {"file": TRACK, "from": tbar(216), "to": tbar(220) + 3.4, "at": P4, "fade_in": 0.01, "fade_out": 1.2},
]

SFX = [
    {"name": "rev_cymbal", "at": T_REW - 0.05, "dur": 0.7, "gain": 0.5},
    {"name": "glitch", "at": T_REW, "gain": 0.6},
    {"name": "scramble", "at": T_REW + 0.2, "gain": 0.4},
    {"name": "impact", "at": M1, "gain": 0.7},
    {"name": "whoosh", "at": b1(1) - 0.1, "gain": 0.35},
    {"name": "hit", "at": b1(1) + 2 * BEAT, "gain": 0.5},
    {"name": "stamp", "at": b1(2), "gain": 0.4},
    {"name": "tick", "at": b1(3), "gain": 0.3}, {"name": "tick", "at": b1(4), "gain": 0.3},
    {"name": "tick", "at": b1(5), "gain": 0.3},
    {"name": "riser", "at": P2 - 1.6, "dur": 1.6, "gain": 0.35},
    {"name": "impact", "at": P2, "gain": 0.9},
    {"name": "whoosh", "at": b2(2) - 0.12, "gain": 0.3},
    {"name": "whoosh", "at": b2(5) - 0.12, "gain": 0.3},
    {"name": "whoosh", "at": b2(9) - 0.12, "gain": 0.3},
    {"name": "whoosh", "at": b2(12) - 0.12, "gain": 0.3},
    {"name": "stamp", "at": b2(12) + 1.3, "gain": 0.45},
    {"name": "glitch", "at": P3, "gain": 0.8},
    {"name": "impact", "at": P3, "gain": 0.5},
    {"name": "whoosh", "at": P4 - 0.15, "gain": 0.3},
    {"name": "impact", "at": HIT, "gain": 0.6},
]

TIMELINE = {
    "size": (1080, 1920), "fps": 60, "duration": END, "output": "out/btmc_story.mp4",
    "beat": BEAT, "beat0": M1, "cap_y": 1500, "duck_db": -10.0, "grain": 0.9,
    "sources": SOURCES, "shots": SHOTS, "voices": VOICES, "events": EVENTS, "chapters": CHAPTERS,
    "tracks": TRACKS, "music": MUSIC, "sfx": SFX,
    "rail": {"years": (2013, 2026), "x0": 100, "x1": 980, "y": 196, "year_x": 100, "year_y": 300},
}
