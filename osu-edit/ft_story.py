"""FlyingTuna story edit: "0-7. 6-7. 7-4." Timeline for story.py.

Music: TK from Ling tosite sigure - unravel (audio from the osu! beatmapset used as the OWC 2024 Grand Final's
championship-point map). Its tempo drifts, so every cut sits on downbeats taken from the beatmap's own timing
points. Voice lines are FlyingTuna's (and the casters') own words from Twitch clips; Korean lines are captioned
in English with the original underneath. On-screen quotes come from his interviews (osu! news, Full Circle,
OWC interview).
"""
import os

import cv2
import numpy as np

import gfx
import layers as L
import typo
from btmc_story import E, S, big, count_text, ev_tag, fit, label
from gfx import clamp01, ease_out_back, ease_out_cubic, ease_out_expo

HERE = os.path.dirname(os.path.abspath(__file__))
CL = "clips/ft/"
TRACK = CL + "music/unravel.mp3"
BEATS = np.load(os.path.join(HERE, CL, "music/unravel_beats.npy"))

KR_RED, KR_BLUE, US_NAVY, US_RED = (205, 46, 58), (40, 110, 220), (40, 60, 120), (190, 30, 45)
GOLD, PINK, WHITE, MUTED, ICE = (255, 196, 77), (255, 79, 160), (255, 255, 255), (150, 150, 170), (150, 200, 255)

SOURCES = {
    "cat23": {"file": CL + "tw_owc23_goodbye_karcher.mp4"},
    "heart23": {"file": CL + "tw_owc23_heartbreak.mp4"},
    "gf23": {"file": CL + "tw_os_owc23_gf_reset.mp4"},
    "n1": {"file": CL + "tw_n1_humble_2019.mp4", "cam": [884, 850, 330, 212]},
    "n1yes": {"file": CL + "tw_n1_really_2019.mp4"},
    "cast19": {"file": CL + "tw_os_owc19_reverse_victory.mp4"},
    "kr19": {"file": CL + "tw_owc19_kr_win_reaction.mp4"},
    "y2021": {"file": CL + "tw_a_2021.mp4", "cam": [1345, 711, 537, 307]},
    "ret23": {"file": CL + "tw_ret_casual_2023.mp4"},
    "win24": {"file": CL + "tw_owc24_the_win.mp4"},
    "ggsk24": {"file": CL + "tw_owc24_ggsk.mp4"},
    "champ24": {"file": CL + "tw_owc24_goat.mp4"},
    "jumps18": {"file": CL + "tw_jumps_2018.mp4"},
}


def words(src, s0, s1, fix=None, ext="md.words.json"):
    import json
    base = os.path.join(HERE, SOURCES[src]["file"]).rsplit(".", 1)[0]
    path = base + "." + ext
    if not os.path.exists(path):
        path = base + ".words.json"
    out = []
    for seg in json.load(open(path)):
        for w in seg.get("words", []):
            if s0 - 0.05 <= w["s"] and w["e"] <= s1 + 0.15:
                out.append([w["w"].strip(), w["s"], w["e"]])
    if fix:
        for i, txt in fix.items():
            out[i][0] = txt
    return [tuple(w) for w in out if w[0]]


def V(src, sin, sout, at, hl=(), fix=None, **kw):
    v = {"src": src, "sin": sin, "sout": sout, "at": at, "words": words(src, sin, sout, fix), "hl": list(hl),
         "db": -12.5}
    v.update(kw)
    return v


def KV(src, sin, sout, at, en, ko, hl=(), **kw):
    """A Korean line: English translation spread over the spoken span, original underneath."""
    ws = en.split()
    span0, span1 = sin + 0.04, sout - 0.12
    weights = np.array([len(w) + 2 for w in ws], float)
    edges = span0 + (span1 - span0) * np.concatenate([[0], np.cumsum(weights) / weights.sum()])
    v = {"src": src, "sin": sin, "sout": sout, "at": at, "hl": list(hl), "sub": ko, "db": -12.0,
         "words": [(w, float(edges[i]), float(edges[i + 1])) for i, w in enumerate(ws)]}
    v.update(kw)
    return v


# ------------------------------------------------------------------ music plan (track downbeats -> output)
class Piece:
    def __init__(self, t0, t1, at):
        self.t0, self.t1, self.at = t0, t1, at

    def out(self, track_t):
        return self.at + (track_t - self.t0)

    @property
    def end(self):
        return self.at + (self.t1 - self.t0)


T_A = 3.05
PA = Piece(1.055, 4.647, T_A)                  # intro: "oshiete, oshiete yo..."
PB = Piece(26.141, 40.816, PA.end)              # band in -> first explosion (31.479)
GAP = 0.62                                      # silence after 0-7
PC = Piece(45.675, 52.804, PB.end + GAP)        # verse
PD = Piece(209.255, 216.378, PC.end)            # breakdown
PE = Piece(59.920, 77.686, PD.end)              # pre-chorus -> chorus (62.580)
PF = Piece(77.686, 81.242, PE.end)              # chorus tail, fades out
END = PF.end + 2.3

b = PB.out
c = PC.out
e = PE.out

MUSIC = [
    {"file": TRACK, "from": PA.t0, "to": PA.t1, "at": PA.at, "fade_in": 0.01, "fade_out": 0.02},
    {"file": TRACK, "from": PB.t0, "to": PB.t1, "at": PB.at, "fade_in": 0.01, "fade_out": 0.03},
    {"file": TRACK, "from": PC.t0, "to": PC.t1, "at": PC.at, "fade_in": 0.02, "fade_out": 0.02},
    {"file": TRACK, "from": PD.t0, "to": PD.t1, "at": PD.at, "fade_in": 0.02, "fade_out": 0.02, "gain": 1.15},
    {"file": TRACK, "from": PE.t0, "to": 74.135, "at": PE.at, "fade_in": 0.01, "fade_out": 0.01},
    # 7-4: the band goes underwater while he screams, then everything comes back for the title
    {"file": TRACK, "from": 74.135, "to": PE.t1, "at": e(74.135), "fade_in": 0.01, "fade_out": 0.01, "lp": 380,
     "gain": 1.1},
    {"file": TRACK, "from": PF.t0, "to": PF.t1 + 2.0, "at": PF.at, "fade_in": 0.01, "fade_out": 2.2},
]


def beat_times():
    out = []
    for p in (PA, PB, PC, PD, PE, PF):
        bs = BEATS[(BEATS >= p.t0 - 1e-3) & (BEATS < p.t1 - 1e-3)]
        out.extend(p.out(x) for x in bs)
    return np.array(sorted(out))


# ------------------------------------------------------------------ voices
VOICES = [
    V("cat23", 51.25, 53.60, 0.35, hl=["CLOSE"], hl_color=ICE, tag="DEC 2023 · MINUTES AFTER THE GRAND FINAL"),
    V("n1yes", 10.25, 10.72, b(26.141) + 0.55, hl=["YES!"], hl_color=GOLD),
    V("n1", 20.18, 22.26, b(28.814) - 0.10, hl=["PARENTS."], hl_color=GOLD),
    V("cast19", 1.05, 2.22, b(31.479) + 0.12, hl=["TUNA", "FLYING"], tag="OWC 2019 · CASTERS"),
    V("cast19", 22.45, 26.58, b(32.792), hl=["KOREA", "TUNA!"]),
    KV("kr19", 4.70, 6.52, b(36.805) + 0.10, "WE WON! WE WON! WE WON! LET'S GOOO!", "이겼다 이겼다 이겼다 가즈아!",
       hl=["WON!", "GOOO!"], hl_color=GOLD),
    V("ret23", 4.98, 7.52, c(49.239) + 0.25, hl=["GIGA", "EMBARRASSED"], tag="MAY 2023 · FIRST STREAM BACK"),
    KV("heart23", 15.30, 16.98, PD.at + 0.95, "AH... SO CLOSE...", "아.. 아깝다..", hl=["CLOSE..."], hl_color=ICE),
    KV("heart23", 22.38, 24.76, PD.at + 2.85, "IT'S OKAY. YOU ALL DID GREAT.", "괜찮아 다들 잘했어", hl=["GREAT."],
       hl_color=ICE),
    V("cat23", 35.12, 37.32, PD.at + 5.30, hl=["GIVE", "UP"], hl_color=GOLD, hold=0.2, db=-10.5),
    KV("ggsk24", 43.22, 43.72, e(74.135) + 0.10, "WE WON!", "이겼어!", hl=["WON!"], hl_color=GOLD, hold=0.1,
       db=-8.0),
    KV("ggsk24", 45.44, 46.26, e(74.135) + 0.70, "WE WON!", "이겼어!", hl=["WON!"], hl_color=GOLD, hold=0.15,
       db=-8.0),
    KV("ggsk24", 51.84, 52.86, e(74.135) + 1.75, "GUYS, LET'S GO!", "얘들아 가자!", hl=["GO!"], hl_color=GOLD,
       db=-9.5),
    V("champ24", 17.62, 20.12, PF.at + 0.15, hl=["2019,"], hl_color=GOLD, tag="A FRIEND ON CALL, DEC 2024"),
    V("champ24", 25.20, 26.80, PF.at + 2.75, hl=["FINALLY", "HAPPENED."], hl_color=GOLD, hold=0.6),
]
# "I will go to say to my parents": whisper put the "I" six seconds earlier; show it with "will"
VOICES[2]["words"] = [("I", 20.18, 20.27)] + list(VOICES[2]["words"])

# ------------------------------------------------------------------ shots
COLD = {"type": "tint", "tint": (0.8, 0.9, 1.15), "sat": 0.35, "contrast": 1.1}
CAT_BOX = [48, 110, 1520, 822]          # the cam box inside his stream layout (no overlays)
CAT = {"type": "tint", "tint": (0.95, 1.05, 1.3), "sat": 0.45, "contrast": 1.05, "lift": 0.07, "gamma": 0.75}
RED_G = {"type": "duo", "dark": (14, 2, 6), "mid": (150, 20, 35), "light": (255, 205, 205), "contrast": 1.2}
BW = {"type": "bw"}

SHOTS = [
    # cold open: the cat cam right after losing 2023
    S(0.0, T_A - 0.12, "cat23", 41.0, "full", grade=CAT, crop=CAT_BOX, focus=(0.37, 0.6), zoom=1.08,
      pulse=False, drift=0.025),
    # title over 2018 jump plays
    S(T_A, PA.end, "jumps18", 2.0, "full", grade={"type": "tint", "tint": (0.6, 0.65, 1.0), "sat": 0.5},
      focus=(0.45, 0.42), zoom=1.6, pulse=True),
    # Feb 11 2019: #1
    S(PA.end, b(28.814), "n1yes", 10.25 - 0.55 - (PA.end - b(26.141)) * 0, "window", crop=[0, 0, 1920, 1080],
      win={"cy": 760}, accent=GOLD),
    S(b(28.814), b(31.479), "n1", 20.18 + 0.10, "split", crop=[0, 0, 1920, 1080], win={"cy": 740},
      face={"cx": 700, "cy": 1080, "w": 440}, accent=GOLD),
    # OWC 2019: casters, then his stream
    S(b(31.479), b(36.805), "cast19", 1.05 - 0.12, "window", crop=[0, 70, 1920, 940], win={"cy": 760, "w": 1010},
      accent=KR_BLUE),
    S(b(36.805), PB.end, "kr19", 4.70 - 0.10, "window", crop=[0, 0, 1920, 1080], win={"cy": 760}, accent=GOLD),
    # 2021
    S(c(45.675), c(47.462), "y2021", 18.0, "split", crop=[0, 0, 1920, 1080], win={"cy": 740},
      face={"cx": 700, "cy": 1080, "w": 440}, accent=KR_BLUE),
    # May 2023 return
    S(c(49.239), PC.end, "ret23", 4.98 - 0.25, "window", crop=[0, 0, 1920, 1080], win={"cy": 760}, accent=PINK),
    # OWC 2023: broadcast -> results -> cat
    S(PD.at, PD.at + 0.9, "gf23", 18.0, "window", crop=[0, 0, 1920, 1080], win={"cy": 760}, accent=ICE,
      grade=COLD),
    S(PD.at + 0.9, PD.at + 5.25, "heart23", 15.30 - 0.95, "window", crop=[0, 0, 1920, 1080], win={"cy": 760},
      accent=ICE, grade=COLD),
    S(PD.at + 5.25, PD.end, "cat23", 35.72, "full", grade=CAT, crop=CAT_BOX, focus=(0.37, 0.6), zoom=1.12,
      pulse=False, in_dur=0.0),
    # 2024: the trophy run over his unravel gameplay, then the comeback
    S(PE.at, e(62.580), "win24", 2.0, "full", grade=BW, focus=(0.42, 0.5), zoom=1.3, pulse=True),
    S(e(62.580), e(70.579), "win24", 6.0, "window", crop=[0, 0, 1920, 1080], win={"cy": 790}, accent=GOLD),
    S(e(70.579), e(74.135), "win24", 40.5, "window", crop=[0, 0, 1920, 1080], win={"cy": 790}, accent=GOLD),
    S(e(74.135), e(75.912), "ggsk24", 43.0, "window", crop=[0, 0, 1920, 1080], win={"cy": 760}, accent=GOLD),
    S(e(75.912), PE.end, "champ24", 5.0, "window", crop=[140, 160, 1720, 820], win={"cy": 760}, accent=GOLD),
    S(PE.end, END, "champ24", 9.0, "window", crop=[140, 160, 1720, 820], win={"cy": 700, "w": 960},
      accent=GOLD, pulse=False),
]


# ------------------------------------------------------------------ events
def team_pill(ctx, canvas, name, x, y, colors, a, scale=1.0):
    k = ctx.k
    w, h = 150 * scale, 64 * scale
    x0, y0 = int((x - w / 2) * k), int((y - h / 2) * k)
    x1, y1 = int((x + w / 2) * k), int((y + h / 2) * k)
    if a <= 0.01:
        return
    ov = canvas.copy()
    cv2.rectangle(ov, (x0, y0), (x1, (y0 + y1) // 2), colors[0][::-1], -1)
    cv2.rectangle(ov, (x0, (y0 + y1) // 2), (x1, y1), colors[1][::-1], -1)
    cv2.addWeighted(ov, a, canvas, 1 - a, 0, canvas)
    spr = gfx.text_sprite(name, int(42 * scale * k), "anton", WHITE, int(3 * k), (0, 0, 0))
    gfx.blit(canvas, spr, x * k, y * k, 1.0, 0, a)


TEAMS = {"USA": (US_NAVY, US_RED), "KOR": (KR_RED, KR_BLUE)}


def ev_score(ctx, canvas, ev, t):
    """Scoreboard: left/right team pills, rolling digits, flash on every point."""
    u = t - ev["t0"]
    k = ctx.k
    keys = ev["keys"]                      # [(t_rel, left, right)]
    y, sc = ev.get("y", 1250), ev.get("scale", 1.0)
    a = clamp01(u / 0.15) * (1 - clamp01((u - (ev["t1"] - ev["t0"]) + 0.15) / 0.15))
    idx = max(0, int(np.searchsorted([kk[0] for kk in keys], u, "right")) - 1)
    last, lv, rv = keys[idx]
    prev = keys[idx - 1] if idx > 0 else keys[idx]
    p = ease_out_expo(clamp01((u - last) / 0.35))
    l_show = prev[1] + (lv - prev[1]) * p
    r_show = prev[2] + (rv - prev[2]) * p
    pop = 1 + 0.18 * (1 - ease_out_back(clamp01((u - last) / 0.3), 2.0)) if u - last < 0.3 and last > 0 else 1.0
    lcol = ev.get("lcol", WHITE)
    rcol = ev.get("rcol", WHITE)
    size = int(150 * sc * k)
    team_pill(ctx, canvas, ev["left"], 540 - 330 * sc, y, TEAMS[ev["left"]], a, sc)
    team_pill(ctx, canvas, ev["right"], 540 + 330 * sc, y, TEAMS[ev["right"]], a, sc)
    typo.counter(canvas, l_show, (540 - 120 * sc) * k, y * k, size, "anton", lcol, digits=1, lead_zeros=False,
                 alpha=a, scale=pop, glow=int(10 * k), glow_color=lcol)
    typo.counter(canvas, r_show, (540 + 120 * sc) * k, y * k, size, "anton", rcol, digits=1, lead_zeros=False,
                 alpha=a, scale=pop, glow=int(10 * k), glow_color=rcol)
    colon = gfx.text_sprite(":", size, "anton", MUTED)
    gfx.blit(canvas, colon, 540 * k, (y - 8 * sc) * k, 1.0, 0, a)
    if ev.get("label"):
        label(ctx, canvas, ev["label"], 540, y - 110 * sc, u, 26, ev.get("label_color", MUTED), "mono", "center",
              a, pill=True)
    for note_t, note, col in ev.get("notes", []):
        nu = u - note_t
        if 0 <= nu < ev.get("note_dur", 1.6):
            label(ctx, canvas, note, 540, y + 118 * sc, nu, 26, col, "mono", "center",
                  1 - clamp01((nu - ev.get("note_dur", 1.6) + 0.2) / 0.2), pill=True)


def ev_title(ctx, canvas, ev, t):
    u = t - ev["t0"]
    k = ctx.k
    canvas[:] = L.dim(canvas, 0.45)
    cy = 860
    sz = fit(ctx, "FLYINGTUNA", "unb", 150, 960)
    L.shockwave(canvas, (540 * k, cy * k), u - 0.05, k, ICE, 1.6, 0.6)
    big(ctx, canvas, "FLYINGTUNA", 540, cy, u - 0.05, sz, WHITE, "unb", "rise", glow=18, glow_color=KR_BLUE,
        stagger=0.045, dur=0.36, seed=5)
    if u > 0.55:
        spr = gfx.text_sprite("플라잉튜나", int(46 * k), "kr", ICE)
        gfx.blit(canvas, spr, 540 * k, (cy + 130) * k, 1.0, 0, clamp01((u - 0.55) / 0.3))
    label(ctx, canvas, "ONCE “ARGUABLY THE BEST MOUSE PLAYER IN THE WORLD”", 540, cy + 230, u - 1.2, 23,
          MUTED, "mono", "center", 1.0)
    label(ctx, canvas, "— OWC 2024 INTERVIEW", 540, cy + 270, u - 1.4, 20, (110, 110, 125), "mono", "center", 1.0)


def ev_n1(ctx, canvas, ev, t):
    """Feb 11 2019: rank #1 at 16."""
    u = t - ev["t0"]
    k = ctx.k
    label(ctx, canvas, "FEB 11, 2019", 540, 1150, u, 30, GOLD, "mono", "center", dot=GOLD, pill=True)
    big(ctx, canvas, "#1 IN THE WORLD", 540, 1250, u - 0.12, fit(ctx, "#1 IN THE WORLD", "unb", 92, 960), GOLD,
        "unb", "slam", glow=16, glow_color=GOLD, stagger=0.03, dur=0.2, seed=11)
    if u > 0.5:
        count_text(ctx, canvas, u - 0.5, 15032, "PP", 330, 1360, 64, WHITE, dur=0.6)
        big(ctx, canvas, "AGE 16", 760, 1360, u - 0.7, 64, WHITE, "anton", "slam", stagger=0.04, dur=0.18, seed=12)


def ev_stamp_seq(ctx, canvas, ev, t):
    """One big stamp per beat (trophies, milestones)."""
    u = t - ev["t0"]
    items = ev["items"]
    for i, (at, title, sub, col) in enumerate(items):
        ui = u - at
        nxt = items[i + 1][0] - at if i + 1 < len(items) else ev["t1"] - ev["t0"] - at
        if ui < 0 or ui > nxt:
            continue
        y = ev.get("y", 1250)
        sz = fit(ctx, title, "unb", ev.get("size", 70), 960)
        big(ctx, canvas, title, 540, y, ui, sz, col, "unb", "slam", glow=10, glow_color=col, stagger=0.02, dur=0.16,
            seed=70 + i)
        if sub:
            label(ctx, canvas, sub, 540, y + sz * 0.85, ui - 0.08, 25, MUTED, "mono", "center", pill=True)


def ev_military(ctx, canvas, ev, t):
    u = t - ev["t0"]
    k = ctx.k
    canvas[:] = L.dim(canvas, 0.85 * clamp01(u / 0.15))
    big(ctx, canvas, "MILITARY", 540, 820, u, 110, WHITE, "unb", "rise", stagger=0.03, dur=0.3, seed=80)
    big(ctx, canvas, "SERVICE", 540, 950, u - 0.1, 110, WHITE, "unb", "rise", stagger=0.03, dur=0.3, seed=81)
    # a slow progress bar: a year and a half away
    p = clamp01((u - 0.3) / max(0.1, ev["t1"] - ev["t0"] - 0.45))
    x0, x1, y = 190, 890, 1090
    cv2.rectangle(canvas, (int(x0 * k), int((y - 10) * k)), (int(x1 * k), int((y + 10) * k)), (60, 60, 70), -1)
    cv2.rectangle(canvas, (int(x0 * k), int((y - 10) * k)), (int((x0 + (x1 - x0) * p) * k), int((y + 10) * k)),
                  ICE[::-1], -1)
    label(ctx, canvas, "1.5 YEARS AWAY FROM OSU!", 540, 1150, u - 0.25, 28, MUTED, "mono", "center")


def ev_quote_card(ctx, canvas, ev, t):
    """An interview line on screen (his words, credited)."""
    u = t - ev["t0"]
    k = ctx.k
    y = ev.get("y", 1250)
    if ev.get("band"):
        n = len(ev["lines"])
        hh = n * ev.get("size", 64) * 1.2 + 90
        y0, y1 = int((y - ev.get("size", 64)) * k), int((y - ev.get("size", 64) + hh) * k)
        a = 0.7 * clamp01(u / 0.15)
        roi = canvas[max(0, y0):y1]
        canvas[max(0, y0):y1] = cv2.addWeighted(roi, 1 - a, np.zeros_like(roi), a, 0)
    for j, line in enumerate(ev["lines"]):
        sz = fit(ctx, line, "unb", ev.get("size", 64), 950)
        big(ctx, canvas, line, 540, y + j * sz * 1.2, u - j * 0.1, sz, ev.get("color", WHITE), "unb", "rise",
            glow=ev.get("glow", 0), glow_color=ev.get("color", WHITE), stagger=0.014, dur=0.28, seed=90 + j)
    if ev.get("credit"):
        label(ctx, canvas, ev["credit"], 540, y + len(ev["lines"]) * ev.get("size", 64) * 1.2 + 10, u - 0.3, 22,
              MUTED, "mono", "center")


def ev_champions(ctx, canvas, ev, t):
    u = t - ev["t0"]
    k = ctx.k
    L.shockwave(canvas, (540 * k, 760 * k), u, k, GOLD, 2.4, 0.7)
    L.sparks(canvas, (540 * k, 760 * k), u, 21, k, n=70, color=(255, 215, 120), speed=2300, life=1.0)
    sz = fit(ctx, "CHAMPIONS", "unb", 120, 960)
    big(ctx, canvas, "WORLD", 540, 1180, u, sz, GOLD, "unb", "slam", glow=18, glow_color=GOLD, stagger=0.04,
        dur=0.18, seed=101)
    big(ctx, canvas, "CHAMPIONS", 540, 1300, u - 0.15, sz, GOLD, "unb", "slam", glow=18, glow_color=GOLD,
        stagger=0.04, dur=0.18, seed=102)
    label(ctx, canvas, "SOUTH KOREA · OSU! WORLD CUP 2024 · CAPTAIN: FLYINGTUNA", 540, 1395, u - 0.45, 22, WHITE,
          "mono", "center", pill=True)


def ev_end(ctx, canvas, ev, t):
    u = t - ev["t0"]
    k = ctx.k
    canvas[:] = L.dim(canvas, 0.88 * clamp01(u / 0.3))
    sz = fit(ctx, "FLYINGTUNA", "unb", 150, 940)
    L.glow_dot(canvas, (540 * k, 760 * k), 380 * k, KR_BLUE, 0.25 * clamp01(u / 0.4))
    big(ctx, canvas, "FLYINGTUNA", 540, 760, u, sz, WHITE, "unb", "slam", glow=22, glow_color=KR_BLUE, stagger=0.04,
        dur=0.2, seed=111)
    spr = gfx.text_sprite("플라잉튜나", int(40 * k), "kr", ICE)
    gfx.blit(canvas, spr, 540 * k, 880 * k, 1.0, 0, clamp01((u - 0.3) / 0.3))
    # the three finals, side by side
    for i, (yr, l_, r_, ln, rn, col) in enumerate([("2019", 7, 0, "USA", "KOR", (220, 80, 90)),
                                                   ("2023", 7, 6, "USA", "KOR", ICE),
                                                   ("2024", 7, 4, "KOR", "USA", GOLD)]):
        ui = u - 0.6 - i * 0.25
        if ui < 0:
            continue
        x = 540 + (i - 1) * 300
        a = clamp01(ui / 0.2)
        label(ctx, canvas, yr, x, 1010, ui, 26, MUTED, "mono", "center", a)
        spr = gfx.text_sprite(f"{l_}-{r_}", int(96 * k), "anton", col, glow=int(10 * k), glow_color=col)
        gfx.blit(canvas, spr, x * k, 1090 * k, 1 + 0.25 * (1 - ease_out_back(clamp01(ui / 0.25), 2.0)), 0, a)
        label(ctx, canvas, f"{ln} : {rn}", x, 1165, ui, 22, (170, 170, 185), "mono", "center", a)
    label(ctx, canvas, "EX-#1 IN THE WORLD  ·  OSU! CHAMPION 2024", 540, 1260, u - 1.5, 24, WHITE, "mono", "center",
          pill=True)
    label(ctx, canvas, "“ONE OF THE GREATEST THINGS IN MY LIFE AND I WILL CHERISH IT ALWAYS”", 540, 1320,
          u - 1.8, 18, MUTED, "mono", "center")


EVENTS = [
    E(0.0, T_A - 0.12, ev_score, left="USA", right="KOR", keys=[(0.0, 7, 6)], y=1240, scale=0.7,
      label="OSU! WORLD CUP 2023 · GRAND FINAL", rcol=ICE),
    E(T_A, PA.end, ev_title, top=False),
    E(PA.end, b(28.814), ev_n1),
    E(b(31.479) + 0.1, b(36.805), ev_tag, text="OWC 2019 · KOREA vs UNITED KINGDOM · TIEBREAKER", color=KR_BLUE,
      y=1215),
    E(b(39.471), PB.end + GAP, ev_score, left="USA", right="KOR", keys=[(0.0, 0, 0), (0.87, 7, 0)], y=1300,
      scale=0.95, label="OWC 2019 · GRAND FINAL", lcol=WHITE, rcol=(255, 90, 100)),
    E(c(45.675), c(47.462), ev_stamp_seq, items=[(0.0, "THE PERENNIAL 2021", "1ST", KR_BLUE),
                                                 (0.6, "CORSACE CLOSED 2021", "1ST · 7-6 vs UTAMI", KR_BLUE),
                                                 (1.2, "OSU! WORLD CUP 2021", "3RD", WHITE)], y=1330, size=60),
    E(c(47.462), c(49.239), ev_military, top=False),
    E(c(51.003) + 0.9, PD.at + 0.85, ev_quote_card, lines=["“THIS YEAR OR NEVER.”"], size=70,
      color=GOLD, glow=12, credit="SEP 2023 · BEFORE OWC 2023", y=1290, top=True),
    E(PD.at + 0.9, PD.at + 5.25, ev_score, left="USA", right="KOR", keys=[(0.0, 6, 6), (0.3, 7, 6)], y=1300,
      scale=0.8, label="OWC 2023 · GRAND FINAL · BRACKET RESET · TIEBREAKER", rcol=ICE),
    E(PE.at, e(62.580), ev_stamp_seq, items=[(0.0, "SSOT 24", "1ST", GOLD),
                                             (e(61.253) - PE.at, "LAZER GRAND ARENA", "1ST · OFFICIAL OSU! LAZER 1V1", GOLD),
                                             (e(61.659) - PE.at, "THE PERENNIAL 2024", "1ST", GOLD),
                                             (e(62.580) - PE.at - 0.45, "CORSACE OPEN 2024", "1ST · 7-0", GOLD)],
      y=1290, size=66),
    E(e(62.580), PF.at - 0.05, ev_score, left="KOR", right="USA",
      keys=[(0.0, 1, 4), (e(63.468) - e(62.580), 2, 4), (e(65.246) - e(62.580), 3, 4),
            (e(67.024) - e(62.580), 4, 4), (e(68.801) - e(62.580), 5, 4), (e(70.579) - e(62.580), 6, 4),
            (e(74.135) - e(62.580), 7, 4)],
      y=1290, scale=0.9, label="OWC 2024 · GRAND FINAL", lcol=GOLD, rcol=WHITE,
      notes=[(e(62.580) - e(62.580) + 0.15, "DOWN 1-4", (255, 120, 120)),
             (e(67.024) - e(62.580), "FLYINGTUNA · 731K ON DT4", GOLD),
             (e(72.357) - e(62.580), "CHAMPIONSHIP POINT · “UNRAVEL”", GOLD)]),
    E(e(63.468) + 0.2, e(67.024) - 0.1, ev_quote_card, lines=["“WE ARE USED TO", "REVERSE SWEEPING.”"],
      size=60, color=WHITE, credit="FLYINGTUNA · OSU! NEWS, DEC 2024", y=730, band=True),
    E(PF.at, PF.at + 3.05, ev_champions, top=True),
    E(PF.at + 3.1, END, ev_end, top=True),
]

# ------------------------------------------------------------------ chapters + tracks
CHAPTERS = [
    {"t0": 0.0, "t1": T_A - 0.12, "title": "SO CLOSE", "color": ICE},
    {"t0": PA.end, "t1": b(31.479), "title": "16 YEARS OLD", "color": GOLD},
    {"t0": b(31.479), "t1": PB.end, "title": "THE FIRST FINAL", "color": KR_RED},
    {"t0": c(45.675), "t1": c(47.462), "title": "TROPHIES", "color": KR_BLUE},
    {"t0": c(47.462), "t1": c(49.239), "title": "AWAY", "color": MUTED},
    {"t0": c(49.239), "t1": PC.end, "title": "THE RETURN", "color": PINK},
    {"t0": PD.at, "t1": PD.end, "title": "THE CAPTAIN", "color": ICE},
    {"t0": PE.at, "t1": e(62.580), "title": "THE YEAR", "color": GOLD},
    {"t0": e(62.580), "t1": PE.end, "title": "REVERSE SWEEP", "color": GOLD},
]

YEAR_KEYS = [(0.0, 2023.0), (T_A - 0.12, 2023.0), (T_A, 2016.0, "out"), (PA.end - 0.4, 2016.0),
             (PA.end, 2019.0, "out"), (PB.end + GAP, 2019.0), (c(45.675), 2021.0, "out"),
             (c(47.462), 2021.0), (c(47.462) + 0.35, 2022.0, "out"), (c(49.239), 2022.0),
             (c(49.239) + 0.35, 2023.0, "out"), (PE.at, 2023.0), (PE.at + 0.35, 2024.0, "out"), (END, 2024.0)]


def spikes(times, peak, dur=0.25, ease="in"):
    keys = [(0.0, 0.0)]
    for x in times:
        keys += [(x - 0.06, 0.0), (x, peak, ease), (x + dur, 0.0)]
    return keys


DOWNS_E = [e(x) for x in (63.468, 65.246, 67.024, 68.801, 70.579, 72.357)]
TRACKS = {
    "year": YEAR_KEYS,
    "year_alpha": [(0.0, 1.0), (T_A - 0.13, 1.0), (T_A - 0.12, 0.0, "step"), (PA.end - 0.01, 0.0),
                   (PA.end, 1.0, "step"), (PF.at - 0.01, 1.0), (PF.at, 0.0, "step")],
    "rail_alpha": [(0.0, 1.0), (T_A - 0.13, 1.0), (T_A - 0.12, 0.0, "step"), (PA.end - 0.01, 0.0),
                   (PA.end, 1.0, "step"), (PF.at + 3.0, 1.0), (PF.at + 3.3, 0.0)],
    "accent": [(0.0, ICE), (PA.end, GOLD, "step"), (b(31.479) - 0.01, GOLD), (b(31.479), KR_RED, "step"),
               (c(45.675) - 0.01, KR_RED), (c(45.675), KR_BLUE, "step"), (c(49.239) - 0.01, KR_BLUE),
               (c(49.239), PINK, "step"), (PD.at - 0.01, PINK), (PD.at, ICE, "step"), (PE.at - 0.01, ICE),
               (PE.at, GOLD, "step")],
    "flash": [(0.0, 0.0), (T_A, 0.6, "step"), (T_A + 0.2, 0.0), (b(31.479), 0.9, "step"), (b(31.479) + 0.25, 0.0),
              (b(40.340), 0.7, "step"), (b(40.340) + 0.2, 0.0), (e(62.580), 1.0, "step"), (e(62.580) + 0.3, 0.0),
              (e(74.135), 0.7, "step"), (e(74.135) + 0.3, 0.0), (PF.at, 0.9, "step"),
              (PF.at + 0.35, 0.0)] + [kk for x in DOWNS_E for kk in ((x, 0.35, "step"), (x + 0.15, 0.0))],
    "zoom_blur": spikes([T_A, PA.end, b(31.479), c(45.675), c(49.239), PD.at, PE.at, e(62.580), e(74.135)], 0.22),
    "whip": spikes([b(28.814), b(36.805), PD.at + 0.9, PD.at + 5.25, e(70.579), e(75.912)], 70.0, 0.09),
    "rgb": [(0.0, 0.0), (b(40.340), 8.0, "step"), (b(40.340) + 0.3, 0.0)],
    "glitch": [(0.0, 0.0), (b(40.340), 0.8, "step"), (b(40.340) + 0.25, 0.0)],
    "bloom": [(0.0, 0.3), (e(74.135), 0.8, "step"), (e(74.135) + 1.5, 0.45), (PF.at, 0.85, "step"),
              (PF.at + 1.5, 0.45)],
    "dark": [(0.0, 0.0), (END - 0.9, 0.0), (END, 1.0)],
}

SFX = [
    {"name": "impact", "at": T_A, "gain": 0.4},
    {"name": "stamp", "at": PA.end + 0.12, "gain": 0.45},
    {"name": "impact", "at": b(31.479), "gain": 0.6},
    {"name": "impact", "at": b(40.340), "gain": 0.9},
    {"name": "glitch", "at": b(40.340), "gain": 0.6},
    {"name": "tick", "at": c(45.675), "gain": 0.3}, {"name": "tick", "at": c(45.675) + 0.6, "gain": 0.3},
    {"name": "tick", "at": c(45.675) + 1.2, "gain": 0.3},
    {"name": "whoosh", "at": c(47.462) - 0.1, "gain": 0.3},
    {"name": "whoosh", "at": PD.at - 0.1, "gain": 0.3},
    {"name": "stamp", "at": PD.at + 0.45, "gain": 0.5},
    {"name": "riser", "at": e(62.580) - 1.4, "dur": 1.4, "gain": 0.3},
    {"name": "impact", "at": e(62.580), "gain": 0.7},
] + [{"name": "stamp", "at": x, "gain": 0.35} for x in DOWNS_E] + [
    {"name": "impact", "at": e(74.135), "gain": 0.9},
    {"name": "impact", "at": PF.at, "gain": 0.8},
    {"name": "impact", "at": PF.at + 3.1, "gain": 0.4},
]

TIMELINE = {
    "size": (1080, 1920), "fps": 60, "duration": END, "output": "out/flyingtuna_story.mp4",
    "beat_times": beat_times(), "cap_y": 1520, "duck_db": -14.0, "grain": 0.85,
    "duck_carve": {"lo": 450, "hi": 4200, "db": -10},
    "sources": SOURCES, "shots": SHOTS, "voices": VOICES, "events": EVENTS, "chapters": CHAPTERS,
    "tracks": TRACKS, "music": MUSIC, "sfx": SFX,
    "rail": {"years": (2016, 2026), "x0": 110, "x1": 970, "y": 196, "year_x": 100, "year_y": 300,
             "playhead": "fish"},
}
