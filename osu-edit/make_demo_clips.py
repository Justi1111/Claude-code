"""Generate placeholder osu!-style gameplay clips (video + music) for testing the edit.

Each clip is a fake 1920x1080@60 lazer-style gameplay recording with its own
synthesized song, so the edit pipeline can be tested before real clips arrive.

    python3 make_demo_clips.py            # writes clips/demo1.mp4 .. demo4.mp4
"""
import math
import os
import subprocess
import sys

import cv2
import numpy as np
import soundfile as sf

import gfx
import synth as S

W, H, FPS = 1920, 1080, 60
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "clips")

SONGS = [
    dict(name="demo1", title="Crimson Overture", bpm=200, root=45, genre="metal", dur=11.0,
         combo=[(60, 60, 255), (90, 140, 255), (255, 255, 255), (40, 40, 200)],
         bg=[(20, 10, 60), (40, 20, 140), (10, 5, 25)]),
    dict(name="demo2", title="Violet Horizon", bpm=175, root=41, genre="dnb", dur=11.0,
         combo=[(255, 90, 200), (80, 160, 255), (255, 140, 120), (220, 220, 255)],
         bg=[(60, 20, 70), (40, 90, 160), (25, 10, 30)]),
    dict(name="demo3", title="Azure Overdrive", bpm=222, root=47, genre="jcore", dur=11.0,
         combo=[(255, 220, 80), (255, 140, 40), (255, 255, 255), (200, 120, 255)],
         bg=[(80, 50, 10), (160, 110, 20), (30, 20, 5)]),
    dict(name="demo4", title="Golden Requiem", bpm=185, root=43, genre="epic", dur=11.0,
         combo=[(60, 200, 255), (120, 230, 255), (255, 255, 255), (40, 140, 230)],
         bg=[(10, 60, 90), (30, 110, 170), (5, 20, 30)]),
]
OFFSET = 0.31  # first beat time in every song (lets the beat tracker prove itself)

PROGRESSION = [(0, (0, 3, 7)), (-4, (0, 4, 7)), (3, (0, 4, 7)), (-2, (0, 4, 7))]
MINOR = [0, 2, 3, 5, 7, 8, 10]


# =============================================================== music
DRUMS = {
    #          kick steps                     snare steps     hats
    "metal": ([0, 2, 4, 6, 8, 10, 12, 13, 14, 15], [4, 12], [0, 4, 8, 12]),
    "dnb": ([0, 10], [4, 12], list(range(0, 16, 2))),
    "jcore": ([0, 4, 8, 12], [4, 12], [2, 6, 10, 14]),
    "epic": ([0, 3, 8, 11], [4, 12], list(range(0, 16, 2))),
}


def make_song(spec):
    bpm, root, genre = spec["bpm"], spec["root"], spec["genre"]
    beat = 60 / bpm
    step = beat / 4
    n = S.n_samples(spec["dur"] + 2)
    drums = np.zeros((n, 2))
    music = np.zeros((n, 2))
    side = np.ones(n)  # sidechain envelope
    kick_s, snare_s, crash_s = S.kick(), S.snare(), S.crash()
    hat_c, hat_o = S.hat(), S.hat(True)
    n_bars = int((spec["dur"] - OFFSET) / (beat * 4)) + 1
    rs = np.random.default_rng(sum(map(ord, spec["name"])))
    lead_notes = [rs.choice(MINOR) + 12 * rs.integers(1, 3) for _ in range(16)]

    for bar in range(n_bars):
        bt = OFFSET + bar * beat * 4
        intro = bar < 2
        chord_root, triad = PROGRESSION[bar % 4]
        kicks, snares, hats = DRUMS[genre]
        if intro:
            kicks, hats = [0, 8], [0, 4, 8, 12]
            snares = [12] if bar == 0 else [4, 12, 13, 14, 15]
        for s in range(16):
            at = S.n_samples(bt + s * step)
            if s in kicks:
                S.place(drums, kick_s * (0.6 if intro else 1), at)
                d = S.n_samples(beat * 0.5)
                end = min(n, at + d)
                side[at:end] = np.minimum(side[at:end], 0.35 + 0.65 * np.linspace(0, 1, end - at) ** 0.7)
            if s in snares:
                S.place(drums, snare_s * (0.5 + 0.1 * s if intro and s > 12 else 1), at)
            if s in hats:
                S.place(drums, hat_o if genre == "jcore" else hat_c, at)
        if bar == 2:
            S.place(drums, crash_s * 1.3, S.n_samples(bt))
        elif not intro and bar % 2 == 0:
            S.place(drums, crash_s * 0.6, S.n_samples(bt))

        # harmony
        f_root = S.midi_hz(root + chord_root)
        bar_len = beat * 4
        pad = sum(S.supersaw(f_root * 2 ** ((12 + iv) / 12), bar_len) for iv in triad) / 3
        pad = S.lowpass(pad, 900 if intro else 5000)
        S.place(music, pad * (0.18 if genre != "metal" else 0.1), S.n_samples(bt))

        for s in range(0, 16, 2 if genre != "metal" else 1):
            at = S.n_samples(bt + s * step)
            if genre == "jcore" and s % 4 == 0:
                continue  # offbeat bass
            if genre == "dnb" and s % 8:
                continue
            dur = step * (8 if genre == "dnb" else 1.8)
            b = S.bass_note(f_root / 2, dur, cutoff=1200 if genre == "dnb" else 700)
            S.place(music, b * (0.0 if intro else 0.32), at)
            if genre == "metal" and not intro and s % 2 == 0:
                S.place(music, S.power_chord(f_root, step * 1.9) * 0.22, at)

        if not intro:
            for s in range(0, 16, 1 if genre in ("jcore", "epic") else 2):
                at = S.n_samples(bt + s * step)
                if genre in ("jcore", "epic"):
                    m = root + 24 + chord_root + triad[s % 3] + (12 if s % 8 >= 4 else 0)
                else:
                    m = root + 24 + chord_root + lead_notes[(s // 2 + bar * 3) % 16]
                p = S.pluck(S.midi_hz(m), step * 1.5, decay=0.09, square=genre == "jcore")
                S.place(music, p * 0.12, at)

    music *= side[:, None]
    S.place(music, S.riser(beat * 4) * 0.5, S.n_samples(OFFSET + beat * 4))
    mix = drums * 0.9 + S.reverb(music, 1.1, 0.25)[:n]
    return mix[: S.n_samples(spec["dur"])], beat


# =============================================================== beatmap
def gen_beatmap(spec, beat):
    """Return list of hit objects in osu! pixels. Patterns: jumps, streams, sliders."""
    rs = np.random.default_rng(sum(map(ord, spec["title"])))
    objs = []
    t = OFFSET + beat * 2  # objects start on beat 3 of intro
    end = spec["dur"] - 0.4
    combo_i, num = 0, 0
    prev = np.array([256.0, 192.0])
    last_type = None

    def add(kind, time, pos, **kw):
        nonlocal num, combo_i
        num += 1
        objs.append(dict(kind=kind, t=time, pos=np.array(pos, float), combo=combo_i, num=num, **kw))

    def new_combo():
        nonlocal num, combo_i
        combo_i += 1
        num = 0

    while t < end:
        drop = t >= OFFSET + beat * 8
        pat = rs.choice(["jump", "stream", "slider", "star"] if drop else ["jump", "slider"],
                        p=[0.35, 0.3, 0.2, 0.15] if drop else [0.6, 0.4])
        if pat == last_type and pat == "stream":
            pat = "jump"
        last_type = pat
        new_combo()
        if pat == "jump":
            spacing = rs.uniform(170, 260) if drop else 120
            ang = rs.uniform(0, 2 * np.pi)
            interval = beat / 2 if spec["bpm"] < 210 else beat
            for i in range(8):
                ang += np.pi * rs.uniform(0.55, 0.9) * (1 if i % 2 else -1)
                p = prev + spacing * np.array([np.cos(ang), np.sin(ang)])
                p = np.clip(p, [30, 30], [482, 354])
                add("circle", t, p)
                prev = p
                t += interval
        elif pat == "star":
            c = np.array([256 + rs.uniform(-60, 60), 192 + rs.uniform(-40, 40)])
            rad = rs.uniform(130, 170)
            a0 = rs.uniform(0, 2 * np.pi)
            for i in range(10):
                a = a0 + (i * 2 % 5) * 2 * np.pi / 5
                p = np.clip(c + rad * np.array([np.cos(a), np.sin(a)]), [30, 30], [482, 354])
                add("circle", t, p)
                prev = p
                t += beat / 2
        elif pat == "stream":
            count = int(rs.choice([12, 16]))
            c = np.clip(prev + rs.uniform(-80, 80, 2), [140, 120], [372, 264])
            rad = rs.uniform(80, 120)
            a0 = rs.uniform(0, 2 * np.pi)
            sweep = rs.choice([-1, 1]) * rs.uniform(1.4, 2.2) * np.pi
            for i in range(count):
                a = a0 + sweep * i / count
                p = c + rad * np.array([np.cos(a), np.sin(a) * 0.8])
                add("circle", t, p)
                prev = p
                t += beat / 4
            t += beat / 4
        else:  # sliders
            for i in range(4):
                ang = rs.uniform(0, 2 * np.pi)
                p0 = np.clip(prev + 150 * np.array([np.cos(ang), np.sin(ang)]), [40, 40], [472, 344])
                d = rs.uniform(90, 150)
                a2 = rs.uniform(0, 2 * np.pi)
                p2 = np.clip(p0 + d * np.array([np.cos(a2), np.sin(a2)]), [30, 30], [482, 354])
                mid = (p0 + p2) / 2 + rs.uniform(-50, 50, 2)
                curve = [(1 - u) ** 2 * p0 + 2 * (1 - u) * u * mid + u ** 2 * p2 for u in np.linspace(0, 1, 24)]
                dur = beat if i % 2 == 0 else beat / 2
                add("slider", t, p0, path=np.array(curve), end=t + dur)
                prev = p2
                t += dur + beat / 2
    return [o for o in objs if o["t"] < end]


# =============================================================== render
PF_SCALE = 1080 * 0.8 / 384
PF_X = (W - 512 * PF_SCALE) / 2
PF_Y = (H - 384 * PF_SCALE) / 2 + 8 * PF_SCALE
RAD = (54.4 - 4.48 * 4) * PF_SCALE
PREEMPT, FADEIN = 0.45, 0.3


def to_screen(p):
    return np.array([PF_X + p[0] * PF_SCALE, PF_Y + p[1] * PF_SCALE])


def make_bg(spec):
    rs = np.random.default_rng(len(spec["title"]))
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    c0, c1, c2 = [np.array(c, np.float32) for c in spec["bg"]]
    g = (yy / H)[..., None]
    img = c0 * (1 - g) + c2 * g
    for _ in range(14):
        cx, cy, r = rs.uniform(0, W), rs.uniform(0, H), rs.uniform(80, 420)
        m = np.exp(-(((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * r * r)))[..., None]
        img = img + m * c1 * rs.uniform(0.3, 1.0)
    # dark silhouettes (fake "art")
    sil = np.zeros((H, W), np.uint8)
    for _ in range(6):
        pts = np.array([[rs.uniform(0, W), rs.uniform(H * 0.3, H)] for _ in range(7)], np.int32)
        cv2.fillPoly(sil, [cv2.convexHull(pts)], 255)
    sil = cv2.GaussianBlur(sil, (0, 0), 6).astype(np.float32)[..., None] / 255
    img = img * (1 - 0.75 * sil)
    img = np.clip(img * 0.3, 0, 255).astype(np.uint8)
    return img


def blend_roi(frame, x0, y0, x1, y1, draw_fn, alpha):
    x0, y0 = max(0, int(x0)), max(0, int(y0))
    x1, y1 = min(W, int(x1)), min(H, int(y1))
    if x1 <= x0 or y1 <= y0 or alpha <= 0:
        return
    roi = frame[y0:y1, x0:x1]
    layer = roi.copy()
    draw_fn(layer, -x0, -y0)
    cv2.addWeighted(layer, alpha, roi, 1 - alpha, 0, dst=roi)


def cpt(p, ox, oy):
    return (int(round((p[0] + ox) * 16)), int(round((p[1] + oy) * 16)))


def draw_circle_obj(frame, o, now, color, approach=True):
    c = to_screen(o["pos"])
    dt = o["t"] - now
    if dt > 0:
        alpha = gfx.clamp01((PREEMPT - dt) / FADEIN)
        scale = 1.0
    else:  # hit animation
        k = -dt / 0.24
        alpha = 1 - k
        scale = 1 + 0.45 * gfx.ease_out_cubic(k)
    r = RAD * scale

    def draw(layer, ox, oy):
        sh = 4
        cv2.circle(layer, cpt(c, ox, oy), int(r * 16), tuple(int(v * 0.55) for v in color), -1, cv2.LINE_AA, sh)
        cv2.circle(layer, cpt(c, ox, oy), int(r * 0.8 * 16), tuple(int(v * 0.8) for v in color), -1, cv2.LINE_AA, sh)
        cv2.circle(layer, cpt(c, ox, oy), int((r - 4) * 16), (255, 255, 255), 8, cv2.LINE_AA, sh)
    pad = r + 10
    blend_roi(frame, c[0] - pad, c[1] - pad, c[0] + pad, c[1] + pad, draw, alpha)
    if dt > 0:
        spr = gfx.text_sprite(str(o["num"]), 64, "bold", (255, 255, 255))
        gfx.blit(frame, spr, c[0], c[1] + 4, 1.0, 0, alpha)
        if approach:
            ar = RAD * (1 + 2.6 * gfx.clamp01(dt / PREEMPT))

            def draw_a(layer, ox, oy):
                cv2.circle(layer, cpt(c, ox, oy), int(ar * 16), color, 5, cv2.LINE_AA, 4)
            pad = ar + 8
            blend_roi(frame, c[0] - pad, c[1] - pad, c[0] + pad, c[1] + pad, draw_a, alpha * 0.9)


def draw_slider(frame, o, now, color):
    pts = np.array([to_screen(p) for p in o["path"]])
    dur = o["end"] - o["t"]
    if now > o["end"]:
        alpha = 1 - (now - o["end"]) / 0.2
    else:
        alpha = gfx.clamp01((PREEMPT - (o["t"] - now)) / FADEIN)
    if alpha <= 0:
        return
    x0, y0 = pts.min(0) - RAD - 12
    x1, y1 = pts.max(0) + RAD + 12

    def draw(layer, ox, oy):
        pl = [np.array([cpt(p, ox, oy) for p in pts], np.int32)]
        cv2.polylines(layer, pl, False, (255, 255, 255), int(RAD * 2), cv2.LINE_AA, 4)
        cv2.polylines(layer, pl, False, tuple(int(v * 0.25) for v in color), int(RAD * 2 - 16), cv2.LINE_AA, 4)
        cv2.polylines(layer, pl, False, tuple(int(v * 0.4) for v in color), int(RAD * 1.2), cv2.LINE_AA, 4)
    blend_roi(frame, x0, y0, x1, y1, draw, alpha * 0.85)
    # end circle
    if now < o["end"]:
        def draw_e(layer, ox, oy):
            e = to_screen(o["path"][-1])
            cv2.circle(layer, cpt(e, ox, oy), int((RAD - 4) * 16), (255, 255, 255), 8, cv2.LINE_AA, 4)
        e = to_screen(o["path"][-1])
        blend_roi(frame, e[0] - RAD - 8, e[1] - RAD - 8, e[0] + RAD + 8, e[1] + RAD + 8, draw_e, alpha)
    if o["t"] <= now <= o["end"]:
        u = (now - o["t"]) / dur
        b = slider_pos(o, u)

        def draw_b(layer, ox, oy):
            cv2.circle(layer, cpt(b, ox, oy), int(RAD * 0.85 * 16), color, -1, cv2.LINE_AA, 4)
            cv2.circle(layer, cpt(b, ox, oy), int(RAD * 0.85 * 16), (255, 255, 255), 6, cv2.LINE_AA, 4)
            cv2.circle(layer, cpt(b, ox, oy), int(RAD * 2.2 * 16), (255, 255, 255), 5, cv2.LINE_AA, 4)
        pad = RAD * 2.4
        blend_roi(frame, b[0] - pad, b[1] - pad, b[0] + pad, b[1] + pad, draw_b, 0.95)
    head = dict(o, kind="circle")
    if now < o["t"] + 0.24:
        draw_circle_obj(frame, head, now, color)


def slider_pos(o, u):
    pts = np.array([to_screen(p) for p in o["path"]])
    f = u * (len(pts) - 1)
    i = min(int(f), len(pts) - 2)
    return pts[i] + (pts[i + 1] - pts[i]) * (f - i)


def cursor_at(objs, now):
    """Human-ish cursor: snaps to each object, follows sliders."""
    prev_t, prev_p = 0.0, to_screen((256, 300))
    for o in objs:
        if o["kind"] == "slider" and o["t"] <= now <= o["end"]:
            return slider_pos(o, (now - o["t"]) / (o["end"] - o["t"]))
        if now < o["t"]:
            target = to_screen(o["pos"])
            span = max(o["t"] - prev_t, 1e-3)
            u = gfx.clamp01((now - prev_t) / span)
            u = gfx.ease_in_out(min(1, u * 1.15))
            wob = np.array([math.sin(now * 37), math.cos(now * 29)]) * 3
            return prev_p + (target - prev_p) * u + wob
        prev_t = o["end"] if o["kind"] == "slider" else o["t"]
        prev_p = slider_pos(o, 1.0) if o["kind"] == "slider" else to_screen(o["pos"])
    return prev_p


def render_clip(spec):
    os.makedirs(OUT, exist_ok=True)
    audio, beat = make_song(spec)
    objs = gen_beatmap(spec, beat)
    for o in objs:
        S.place(audio, S.hitsound(clap=o["num"] % 4 == 0) * 0.45, S.n_samples(o["t"]))
    audio = S.master(audio, 1.3, 0.9)
    wav = os.path.join(OUT, spec["name"] + ".wav")
    sf.write(wav, audio, S.SR)

    bg = make_bg(spec)
    mp4 = os.path.join(OUT, spec["name"] + ".mp4")
    ff = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "veryfast", "-crf", "15",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", "-shortest", mp4],
        stdin=subprocess.PIPE)
    n_frames = int(spec["dur"] * FPS)
    trail = []
    score, combo, hits, k1, k2 = 0, 0, 0, 0, 0
    hit_err = []
    hit_ptr = 0
    rs = np.random.default_rng(3)
    for fi in range(n_frames):
        now = fi / FPS
        frame = bg.copy()
        # kiai pulse on beats during drop
        bt = (now - OFFSET) / beat
        if bt >= 8:
            pulse = math.exp(-((bt % 1) * 6))
            frame = cv2.convertScaleAbs(frame, alpha=1 + 0.25 * pulse)
        # judge hits
        while hit_ptr < len(objs) and objs[hit_ptr]["t"] <= now:
            o = objs[hit_ptr]
            combo += 1
            hits += 1
            score += 300 * (1 + combo // 25)
            hit_err.append((o["t"], rs.normal(0, 9)))
            if hit_ptr % 2:
                k2 += 1
            else:
                k1 += 1
            hit_ptr += 1
        # objects (later ones underneath)
        vis = [o for o in objs if o["t"] - PREEMPT <= now <= (o.get("end", o["t"]) + 0.26)]
        for o in reversed(vis):
            col = spec["combo"][o["combo"] % len(spec["combo"])]
            if o["kind"] == "slider":
                draw_slider(frame, o, now, col)
            else:
                draw_circle_obj(frame, o, now, col)
        # cursor + trail
        cp = cursor_at(objs, now)
        trail.append(cp)
        trail = trail[-14:]
        for i, p in enumerate(trail[:-1]):
            a = (i + 1) / len(trail)
            cv2.circle(frame, (int(p[0]), int(p[1])), int(6 + 10 * a), (int(200 * a), int(230 * a), int(255 * a)), -1, cv2.LINE_AA)
        cv2.circle(frame, (int(cp[0]), int(cp[1])), 24, (180, 240, 255), -1, cv2.LINE_AA)
        cv2.circle(frame, (int(cp[0]), int(cp[1])), 24, (255, 255, 255), 4, cv2.LINE_AA)
        # HUD
        acc = 100 - 1.07 * (1 - math.exp(-hits / 40)) - 0.02 * math.sin(hits)
        s_spr = gfx.text_sprite(f"{score:08d}", 70, "bold", (255, 255, 255))
        gfx.blit(frame, s_spr, W - s_spr.shape[1] / 2 - 20, 60)
        a_spr = gfx.text_sprite(f"{acc:.2f}%", 40, "bold", (255, 255, 255))
        gfx.blit(frame, a_spr, W - a_spr.shape[1] / 2 - 20, 125)
        bump = 1 + 0.25 * math.exp(-max(0, now - (objs[hit_ptr - 1]["t"] if hit_ptr else -9)) * 18)
        c_spr = gfx.text_sprite(f"{combo}x", 84, "bold", (255, 255, 255))
        gfx.blit(frame, c_spr, 30 + c_spr.shape[1] / 2 * bump, H - 70, bump)
        cv2.rectangle(frame, (20, 20), (620, 34), (40, 40, 40), -1)
        cv2.rectangle(frame, (20, 20), (int(20 + 600 * (0.82 + 0.18 * math.sin(now))), 34), (255, 210, 120), -1)
        cv2.rectangle(frame, (W // 2 - 160, H - 30), (W // 2 + 160, H - 26), (90, 200, 90), -1)
        cv2.rectangle(frame, (W // 2 - 60, H - 30), (W // 2 + 60, H - 26), (255, 200, 80), -1)
        for t0, e in hit_err[-25:]:
            a = gfx.clamp01(1 - (now - t0) / 3)
            x = int(W // 2 + e * 4)
            cv2.line(frame, (x, H - 44), (x, H - 14), (int(255 * a), int(255 * a), int(255 * a)), 2)
        for i, (k, cnt) in enumerate([("K1", k1), ("K2", k2)]):
            y = H // 2 - 40 + i * 80
            lit = hit_ptr and (hit_ptr - 1) % 2 == i and now - objs[hit_ptr - 1]["t"] < 0.08
            cv2.rectangle(frame, (W - 90, y), (W - 20, y + 66), (255, 220, 120) if lit else (60, 60, 60), -1 if lit else 3)
            kspr = gfx.text_sprite(str(cnt), 26, "bold", (255, 255, 255))
            gfx.blit(frame, kspr, W - 55, y + 33)
        ff.stdin.write(frame.tobytes())
        if fi % 120 == 0:
            print(f"  {spec['name']}: {fi}/{n_frames}", flush=True)
    ff.stdin.close()
    ff.wait()
    os.remove(wav)
    print("wrote", mp4)


if __name__ == "__main__":
    which = sys.argv[1:] or [s["name"] for s in SONGS]
    for spec in SONGS:
        if spec["name"] in which:
            render_clip(spec)
