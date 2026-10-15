"""Main part of the FlyingTuna edit: beat-synced gameplay cuts 0:20.32-1:00.95 + the old calm 1:00.95-1:11.11.

Milestone captions are drawn by ../captions/captions.py (Archivo Expanded Black label, gold JetBrains Mono date)
and laid over their shots. The calm here is only a placeholder now: the finished edit takes the segments before
1:00.95 from this render and continues with build_ending.py (see build_full.py).

Order is by the real Twitch clip time (KST), and every pool is cut at the milestones' own times, so nothing shot
after a milestone plays before it. Everything before the TABLET shot is on mouse (the 31.03.2018 tablet try and
the 19.07.2018 tablet clip are left out).

usage: python -I build_main.py <workdir> [captions=1]
Track: femtanyl - LOVESICK, CANNIBAL! (official 1:57 version), 189 BPM, grid from 0.000 s.
"""
import csv
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "captions"))
import captions  # noqa: E402

S = "/tmp/claude-0/-home-user-Claude-code/a61365b4-59b2-5d5f-8537-7f9c9b765619/scratchpad"
LIB = "/home/user/Claude-code/osu-edit/clips/ft_library"
MAIN = "/home/user/Claude-code/osu-edit/clips/ft_main"
SONG = f"{S}/tracks_x/2143023/audio.mp3"
WORK = sys.argv[1]
CAPS = (sys.argv[2] if len(sys.argv) > 2 else "1") == "1"
os.makedirs(WORK, exist_ok=True)

BEAT = 60 / 189
FPS = 60
T = lambda b: b * BEAT
F = lambda b: round(T(b) * FPS)
B0 = 64  # 0:20.317, the drop

# ---------- clip pool ----------
best = {r["id"]: r for r in csv.DictReader(open(f"{S}/rev/best.tsv", encoding="utf-8"), delimiter="\t")}
for line in open(f"{S}/rev2/jobs.txt", encoding="utf-8"):
    i, path, st, d = line.strip().split("|")
    base = best[i[:-1]]
    best[i] = dict(base, id=i, path=path, start=st)


def pool(ids):
    return [best[str(i)] for i in ids]


def _clip_index():
    """Twitch clip slug and creation time for a local file: ft_main files carry the slug in their name, library files
    are mapped through the download manifest."""
    slug_t = {}
    for line in open(f"{S}/lists/ft_all.jsonl", encoding="utf-8"):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        slug_t[d["url"].rsplit("/", 1)[-1]] = d["timestamp"]
    lib = {}
    for line in open(f"{S}/lists/main_manifest.tsv", encoding="utf-8"):
        p = line.rstrip("\n").split("\t")
        if len(p) >= 6 and "twitch.tv" in p[4]:
            lib[os.path.basename(p[5])] = p[4].rsplit("/", 1)[-1]

    def slug(path):
        name = os.path.basename(path)
        return lib.get(name) or name.split("_", 1)[-1][:-4]
    return slug, lambda path: slug_t[slug(path)]


clip_slug, clip_time = _clip_index()


def item_time(it):
    """when a shot happened: its own ts if it has one (footage from outside the Twitch catalog), else its clip's time."""
    return it.get("ts") or clip_time(it["path"])


def spread(items, n):
    """n items spread over the period: split the time-sorted list into n buckets, take the best-scored of each."""
    items = sorted(items, key=lambda r: (clip_time(r["path"]), float(r["start"])))
    if len(items) <= n:
        return items
    out = []
    for k in range(n):
        a, b = round(k * len(items) / n), round((k + 1) * len(items) / n)
        out.append(max(items[a:b], key=lambda r: float(r["score"])))
    return out


A1 = spread(pool(["2", "2b", "3", "8", "8b", "9", "10", "10b", "12", "14", "12b", "14b", "9b"]), 10)
A2 = spread(pool([16, 19, 20, 23, 25, 26, 33, 35, 37, 38, 39, 41, 42, 43]), 10)
A3 = spread(pool([50, 51, 53, 54, 56, 58, 59, 60, 64, 65, 66, 67, 68, 69, 70, 72, 74, 75, 76, 77, 79, 80, 81]), 19)
B1 = spread(pool([88, 89, 90, 92, 93, 94, 95, 97, 98, 99, 101, 103, 104, 105, 107, 109, 110, 111, 113, 115, 117, 118,
                  125, 127, 129, 130, 133, 135, 136, 141, 142]), 9) + pool([143])  # ends on the 800pp map itself


def at(i, start):
    """a pool clip at another in-point (where the scored one lands on a black frame or a result screen)."""
    return dict(best[str(i)], start=f"{start:.2f}")


# pools cut at the milestones' own times (KST): 800PP 25.11 20:00, TOP 10 16.12 20:32, #4 27.12 01:11, #2 11.02 05:19
B2 = spread(pool([144, 150, 153, 162, 165, 167, 175]) + [at(154, 15.0), at(170, 1.5)], 9)
B3 = spread(pool([180, 181, 179, 187, 193]) + [at(178, 28.0), at(188, 44.0)], 7)
B4 = spread(pool([194, 195, 196, 197, 198, 199, 201, 203, 210, 212, 213, 214, 219, 220, 225, 226, 228, 234, 235, 237,
                  239, 240, 241, 248, 255]) + [at(258, 10.0)], 5)
# between #2 (05:19) and #1 (22:57) on 11.02.2019: the rest of that night's stream, in order
POST2 = [at(257, 1.2), at(259, 2.2), at(259, 9.2), at(253, 0.2)]

MS = {
    "726": dict(path=f"{MAIN}/20180513_CourageousChillyNigiriPeanutButterJellyTime.mp4", start=35.3, cap="726PP", date="13.05.2018"),
    "tab": dict(path=f"{LIB}/01_2018_mouse_to_tablet/2018-07-20_almost_adapted_tablet.mp4", start=16.0, cap="TABLET", date="2018", zoom=(1727, 967, 2.6)),
    # the Twitch clip of the 800pp play stops at the end of the map; the result screen comes from the stream recording
    # on YouTube (Circle People, ObzZQBtWkFE, 2:16), played 25.11.2018 20:00:37 KST
    "800": dict(path=f"{LIB}/02_road_to_1/2018-11-25_first_800pp_result_youtube.mp4", start=0.0, cap="FIRST 800PP",
                date="25.11.2018", ts=clip_time(f"{LIB}/02_road_to_1/2018-11-25_first_800pp_play.mp4") + 2,
                url="https://www.youtube.com/watch?v=ObzZQBtWkFE"),
    "10": dict(path=f"{LIB}/02_road_to_1/2018-12-16_top10_global.mp4", start=27.2, cap="TOP 10", date="16.12.2018"),
    "4": dict(path=f"{LIB}/02_road_to_1/2018-12-26_14k_pp.mp4", start=45.2, cap="#4 · 14,000PP", date="26.12.2018"),
    "2": dict(path=f"{LIB}/02_road_to_1/2019-02-10_number2_lets_go.mp4", start=17.6, cap="#2", date="11.02.2019"),
}

# ---------- slots ----------
slots = []  # (beat, n_beats, item, caption, date, zoom)


def phrase(b0, nbars, items, first=None):
    pattern = []
    for bar in range(nbars):
        bb = b0 + 4 * bar
        if bar < nbars - 1:
            pattern += [(bb, 2), (bb + 2, 2)]
        else:
            pattern += [(bb, 1), (bb + 1, 1), (bb + 2, 1), (bb + 3, 1)]
    it = iter(items)
    for k, (b, n) in enumerate(pattern):
        if k == 0 and first:
            m = MS[first]
            slots.append((b, n, m, m["cap"], m["date"], m.get("zoom")))
        else:
            slots.append((b, n, next(it), None, None, None))
    rest = list(it)
    assert not rest, (b0, len(rest))


phrase(64, 4, A1)
phrase(80, 4, A2)  # no caption here: the 730pp on 23.02.2018 was "if ranked" on an unranked map
phrase(96, 4, A3[:9], "726")
phrase(112, 4, A3[9:])
m = MS["tab"]
slots.append((128, 4, m, m["cap"], m["date"], m["zoom"]))
phrase(132, 4, B1)
phrase(148, 4, B2, "800")
# TOP 10, #4 and #2 keep their old spacing but sit a bar earlier, so a few clips play after #2 before the calm
m10, m4, m2 = MS["10"], MS["4"], MS["2"]
slots.append((164, 2, m10, m10["cap"], m10["date"], None))
for (b, n), item in zip([(166, 2), (168, 2), (170, 2), (172, 1), (173, 1), (174, 1), (175, 1)], B3):
    slots.append((b, n, item, None, None, None))
slots.append((176, 2, m4, m4["cap"], m4["date"], None))
for (b, n), item in zip([(178, 2), (180, 2), (182, 2), (184, 1), (185, 1)], B4):
    slots.append((b, n, item, None, None, None))
slots.append((186, 2, m2, m2["cap"], m2["date"], None))
for (b, n), item in zip([(188, 1), (189, 1), (190, 1), (191, 1)], POST2):
    slots.append((b, n, item, None, None, None))
# calm: the #1 result, then his reaction
TOP1 = dict(path=f"{LIB}/03_number_one_2019-02-11/2019-02-11_top1_moment_60s.mp4", start=29.5)
PAR = dict(path=f"{LIB}/03_number_one_2019-02-11/2019-02-11_i_will_go_to_say_to_my_parents.mp4", start=15.7)
slots.append((192, 11, TOP1, None, None, None))
slots.append((203, 21, PAR, None, None, None))
END_BEAT = 224

# sanity: contiguous grid, pools fully used, real clip times never go backwards before the calm
assert (len(B3), len(B4), len(POST2)) == (7, 5, 4), (len(B3), len(B4), len(POST2))
for (b, n, *_), (b2, *__) in zip(slots, slots[1:]):
    assert b + n == b2, (b, n, b2)
assert slots[-1][0] + slots[-1][1] == END_BEAT
order = [(item_time(it), float(it["start"])) for b, n, it, *_ in slots if b < 192]
bad = [k + 1 for k in range(1, len(order)) if order[k] < order[k - 1]]
assert not bad, f"clip time goes backwards at slots {bad}"
if os.environ.get("FT_PLAN_ONLY"):
    import datetime
    kst = datetime.timezone(datetime.timedelta(hours=9))
    for k, (b, n, it, cap, *_) in enumerate(slots):
        t = datetime.datetime.fromtimestamp(item_time(it), kst).strftime("%d.%m.%Y %H:%M")
        print(f"{k + 1:3d} {T(b):7.3f} {n:2d}b {t} {float(it['start']):6.2f} {cap or '':14s} {it.get('title', '')[:40]}")
    sys.exit(0)


segs, cutlist = [], []
for k, (b, n, item, cap, date, zoom) in enumerate(slots):
    f0, f1 = F(b) - F(B0), F(b + n) - F(B0)
    nfr = f1 - f0
    out = f"{WORK}/seg_{k:03d}.mp4"
    vf = "fps=60,scale=1920:1080:flags=lanczos,setsar=1"
    if zoom:
        cx, cy, zmax = zoom
        p = f"(on/{nfr - 1})"
        ease = f"({p}*{p}*(3-2*{p}))"
        z = f"(1+{zmax - 1}*{ease})"
        vf = (f"fps=60,scale=3840:2160:flags=lanczos,zoompan=z='{z}':x='max(0,min(iw-iw/zoom,{cx * 2}-iw/zoom/2))'"
              f":y='max(0,min(ih-ih/zoom,{cy * 2}-ih/zoom/2))':d=1:s=1920x1080:fps=60,setsar=1")
    if cap and CAPS:
        captions.render(["-ss", f"{float(item['start']):.3f}", "-i", item["path"]], vf,
                        captions.milestone_frames(cap, date, nfr), nfr, out)
    else:
        cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{float(item['start']):.3f}", "-i", item["path"],
               "-frames:v", str(nfr), "-vf", vf, "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "14",
               "-pix_fmt", "yuv420p", "-r", "60", out]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print("FAIL", k, r.stderr[-400:])
            sys.exit(1)
    segs.append(out)
    src = os.path.basename(item["path"])
    cutlist.append((k + 1, f"{T(b):.3f}", f"{T(b + n):.3f}", n, item.get("date", ""), item.get("title", cap or ""), src,
                    f"{float(item['start']):.2f}", cap or "", item.get("url") or f"https://www.twitch.tv/flyingtuna/clip/{clip_slug(item['path'])}"))

with open(f"{WORK}/concat.txt", "w") as f:
    for s in segs:
        f.write(f"file '{s}'\n")
with open(f"{WORK}/cutlist.tsv", "w", encoding="utf-8") as f:
    f.write("n\ttrack_start\ttrack_end\tbeats\tclip_date\tclip_title\tsource_file\tsource_in\tcaption\turl\n")
    for row in cutlist:
        f.write("\t".join(map(str, row)) + "\n")

# ---------- assemble with audio ----------
t_start = F(B0) / FPS
dur = (F(END_BEAT) - F(B0)) / FPS
calm0 = T(192) - t_start
par0 = T(203) - t_start
video = f"{WORK}/video.mp4"
subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", f"{WORK}/concat.txt", "-c", "copy", video], check=True)
fc = (f"[1:a]atrim={t_start:.4f}:{t_start + dur:.4f},asetpts=PTS-STARTPTS,"
      f"volume='if(gte(t,{calm0:.3f}),0.72,1)':eval=frame[song];"
      f"[2:a]atrim=29.5:{29.5 + T(11):.4f},asetpts=PTS-STARTPTS,volume=0.55,afade=t=in:d=0.3,adelay=delays={int(calm0 * 1000)}:all=1[c1];"
      f"[3:a]atrim=15.7:{15.7 + T(21):.4f},asetpts=PTS-STARTPTS,acompressor=threshold=0.125:ratio=6:attack=5:release=120:makeup=2,"
      f"volume=1.1,afade=t=in:d=0.15,adelay=delays={int(par0 * 1000)}:all=1[c2];"
      f"[song][c1][c2]amix=inputs=3:normalize=0:duration=first,alimiter=limit=0.89:level=false[a]")
final = f"{WORK}/main_part.mp4"
subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", video, "-i", SONG, "-i", TOP1["path"], "-i", PAR["path"],
                "-filter_complex", fc, "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k",
                "-shortest", "-movflags", "+faststart", final], check=True)
print("segments", len(segs), "duration", round(dur, 3), "->", final)
