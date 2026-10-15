"""Main part of the FlyingTuna edit: beat-synced gameplay cuts 0:20.32-1:00.95 + the old calm 1:00.95-1:11.11.

Milestone captions are drawn by ../captions/captions.py (Archivo Expanded Black label, gold JetBrains Mono date)
and laid over their shots. The calm here is only a placeholder now: the finished edit takes segments 0-77 from
this render and continues with build_ending.py (see build_full.py).

usage: python -I build_main.py <workdir> [captions=1]
Track: femtanyl - LOVESICK, CANNIBAL! (official 1:57 version), 189 BPM, grid from 0.000 s.
"""
import csv
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


def spread(items, n):
    """n items spread over the period: split the date-sorted list into n buckets, take the best-scored of each."""
    items = sorted(items, key=lambda r: (r["date"], r["path"], float(r["start"])))
    if len(items) <= n:
        return items
    out = []
    for k in range(n):
        a, b = round(k * len(items) / n), round((k + 1) * len(items) / n)
        out.append(max(items[a:b], key=lambda r: float(r["score"])))
    return out


A1 = spread(pool(["2", "2b", "3", "8", "8b", "9", "10", "10b", "12", "14", "12b", "14b", "9b"]), 10)
A2 = spread(pool([16, 19, 20, 23, 25, 26, 31, 33, 35, 37, 38, 39, 41, 42, 43]), 9)
A3 = spread(pool([50, 51, 53, 54, 56, 58, 59, 60, 64, 65, 66, 67, 68, 69, 70, 72, 74, 75, 76, 77, 79, 80, 81, 86]), 19)
B1 = spread(pool([88, 89, 90, 92, 93, 94, 95, 97, 98, 99, 101, 103, 104, 105, 107, 109, 110, 111, 113, 115, 117, 118,
                  125, 127, 129, 130, 133, 135, 136, 141, 142]), 10)
B2 = spread(pool([143, 144, 150, 153, 162, 165, 167, 175, 179, 180]), 9)
B3 = spread(pool([181, 187, 193, 194, 195, 196, 197, 198, 199, 201]), 9)
B4 = spread(pool([203, 210, 212, 213, 214, 219, 220, 225, 226, 228, 234, 235, 237, 239, 240, 241, 248, 255, 259]), 5)

MS = {
    "730": dict(path=f"{MAIN}/20180223_BillowingFlaccidRhinocerosChefFrank.mp4", start=50.2, cap="730PP", date="23.02.2018"),
    "726": dict(path=f"{MAIN}/20180513_CourageousChillyNigiriPeanutButterJellyTime.mp4", start=35.3, cap="726PP", date="13.05.2018"),
    "tab": dict(path=f"{LIB}/01_2018_mouse_to_tablet/2018-07-20_almost_adapted_tablet.mp4", start=16.0, cap="TABLET", date="2018", zoom=(1727, 967, 2.6)),
    "800": dict(path=f"{LIB}/02_road_to_1/2018-11-25_first_800pp_play.mp4", start=36.9, cap="FIRST 800PP", date="25.11.2018"),
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
phrase(80, 4, A2, "730")
phrase(96, 4, A3[:9], "726")
phrase(112, 4, A3[9:])
m = MS["tab"]
slots.append((128, 4, m, m["cap"], m["date"], m["zoom"]))
phrase(132, 4, B1)
phrase(148, 4, B2, "800")
phrase(164, 4, B3, "10")
m4, m2 = MS["4"], MS["2"]
slots.append((180, 2, m4, m4["cap"], m4["date"], None))
it = iter(B4)
for b, n in [(182, 2), (184, 2), (186, 2), (188, 1), (189, 1)]:
    slots.append((b, n, next(it), None, None, None))
slots.append((190, 2, m2, m2["cap"], m2["date"], None))
# calm: the #1 result, then his reaction
TOP1 = dict(path=f"{LIB}/03_number_one_2019-02-11/2019-02-11_top1_moment_60s.mp4", start=29.5)
PAR = dict(path=f"{LIB}/03_number_one_2019-02-11/2019-02-11_i_will_go_to_say_to_my_parents.mp4", start=15.7)
slots.append((192, 11, TOP1, None, None, None))
slots.append((203, 21, PAR, None, None, None))
END_BEAT = 224

# sanity: contiguous grid
for (b, n, *_), (b2, *__) in zip(slots, slots[1:]):
    assert b + n == b2, (b, n, b2)
assert slots[-1][0] + slots[-1][1] == END_BEAT


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
                    f"{float(item['start']):.2f}", cap or ""))

with open(f"{WORK}/concat.txt", "w") as f:
    for s in segs:
        f.write(f"file '{s}'\n")
with open(f"{WORK}/cutlist.tsv", "w", encoding="utf-8") as f:
    f.write("n\ttrack_start\ttrack_end\tbeats\tclip_date\tclip_title\tsource_file\tsource_in\tcaption\n")
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
