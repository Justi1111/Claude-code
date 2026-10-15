"""Polish pass over the finished FlyingTuna edit (build_full.py output).

A look on every frame: a gentle S-curve and a little more colour, bloom on the highlights (hit circles, cursor, the
#1 plate), a soft vignette and fine grain. In the pounding part (0:20.32-1:00.95) everything follows the beat grid:
  - every cut punches in a few percent with a short exposure kick and a thin colour split,
  - the other beats pulse very lightly (the kick is on every beat),
  - phrase downbeats and milestones hit harder: bigger punch, white flash, wider colour split, a short shake,
  - the drop hits hardest; the TABLET bar, where the beat drops out, gets only a soft flash,
  - the cut right before each downbeat glitches for three frames (slices shifted sideways, channels apart).
The calm opens on a soft white flash; from there only the look, so the #1 clip stays as it is.

usage: FT_MAIN_WORK=<build_main.py workdir> python -I polish.py <in.mp4> <out.mp4> [workers]
       ... polish.py <in.mp4> --stills <frame,frame,...> <outdir>     before/after PNGs of single frames
"""
import csv
import os
import subprocess
import sys
from multiprocessing import Pool

import cv2
import numpy as np

W, H, FPS = 1920, 1080, 60
BEAT = 60 / 189
F0 = 914                      # track frame of the edit's first frame (0:15.233)
MAINW = os.environ.get("FT_MAIN_WORK", "/home/user/Claude-code/osu-edit/out/ft_main_v7/work")
ACCENTS = {80, 96, 112, 132, 148, 164, 176, 186}   # phrase downbeats and milestones
DROP, TABLET, CALM = 64, 128, 192


def F(b):
    return round(b * BEAT * FPS)


def timeline(n):
    """per-frame effect amounts for an edit of n frames."""
    rows = list(csv.DictReader(open(f"{MAINW}/cutlist.tsv", encoding="utf-8"), delimiter="\t"))
    cuts = sorted({round(float(r["track_start"]) / BEAT) for r in rows if float(r["track_start"]) < CALM * BEAT - 1e-3})
    cut_set = set(cuts)
    glitch_beats = {cuts[i] for i in range(len(cuts) - 1) if cuts[i + 1] in ACCENTS | {TABLET}} | {cuts[-1]}
    events = []  # (frame, kind)
    for b in cuts:
        kind = "drop" if b == DROP else "soft" if b == TABLET else "accent" if b in ACCENTS else "cut"
        events.append((F(b) - F0, kind))
        if b in glitch_beats:
            events.append((F(b) - F0, "glitch"))
    for b in range(DROP, CALM):
        if b not in cut_set and not (TABLET <= b < TABLET + 4):
            events.append((F(b) - F0, "pulse"))
    events.append((F(CALM) - F0, "calm"))

    p = {k: np.zeros(n, np.float32) for k in ("punch", "expo", "flash", "chroma", "shake", "bloom")}
    glitch = np.zeros(n, np.int32)
    d = np.arange(n, dtype=np.float32)
    env = {  # kind: {param: (amount, decay in frames)}
        "cut": dict(punch=(0.035, 3.5), expo=(0.05, 2.5), chroma=(1.5, 2.5), bloom=(0.10, 4)),
        "pulse": dict(punch=(0.012, 3.0), expo=(0.02, 2.5)),
        "accent": dict(punch=(0.07, 4), expo=(0.10, 3), flash=(0.32, 2.2), chroma=(7, 3), shake=(7, 4), bloom=(0.30, 5)),
        "drop": dict(punch=(0.11, 5), expo=(0.15, 3), flash=(0.65, 3), chroma=(12, 4), shake=(10, 5), bloom=(0.40, 6)),
        "soft": dict(expo=(0.05, 4), flash=(0.15, 4)),
        "calm": dict(expo=(0.05, 6), flash=(0.35, 7)),
    }
    for f0, kind in events:
        if kind == "glitch":
            for j in range(3):
                if f0 + j < n:
                    glitch[f0 + j] = f0 * 3 + j + 1
            continue
        for name, (amt, tau) in env[kind].items():
            t = d[f0:] - f0
            p[name][f0:] = np.maximum(p[name][f0:], amt * np.exp(-t / tau))
    pound = np.zeros(n, np.float32)
    pound[F(DROP) - F0:F(CALM) - F0] = 1
    p["bloom"] += 0.32 + 0.12 * pound
    p["glitch"] = glitch
    return p


class Look:
    def __init__(self):
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) / np.sqrt(2)
        self.vig = (1 - 0.16 * r ** 2.4)[..., None].astype(np.float32)
        rng = np.random.default_rng(7)
        self.grain = [rng.standard_normal((H, W)).astype(np.float32) for _ in range(12)]
        x = np.linspace(0, 1, 256, dtype=np.float32)
        s = x * x * (3 - 2 * x)
        self.lut = np.clip((x + 0.28 * (s - x)) * 255 + 0.5, 0, 255).astype(np.uint8)   # gentle S

    def __call__(self, frame, k, p):
        img = cv2.LUT(frame, self.lut).astype(np.float32) / 255.0
        punch, sh, ca = float(p["punch"][k]), float(p["shake"][k]), float(p["chroma"][k])
        if punch > 1e-4 or sh > 0.3 or ca > 0.3:
            rng = np.random.default_rng(k)
            dx, dy = (rng.uniform(-1, 1, 2) * sh) if sh > 0.3 else (0.0, 0.0)
            s = 1 + punch
            if ca > 0.3:
                chans = []
                for c, extra in ((0, ca / (W / 2)), (1, 0.0), (2, -ca / (W / 2))):
                    sc = s * (1 + extra) + 2 * ca / W
                    m = np.float32([[sc, 0, (1 - sc) * W / 2 + dx], [0, sc, (1 - sc) * H / 2 + dy]])
                    chans.append(cv2.warpAffine(img[..., c], m, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT))
                img = np.dstack(chans)
            else:
                s += 2 * sh / W
                m = np.float32([[s, 0, (1 - s) * W / 2 + dx], [0, s, (1 - s) * H / 2 + dy]])
                img = cv2.warpAffine(img, m, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        g = int(p["glitch"][k])
        if g:
            rng = np.random.default_rng(g)
            for _ in range(rng.integers(4, 8)):
                y0 = int(rng.integers(0, H - 20))
                h = int(rng.integers(8, 90))
                sx = int(rng.choice([-1, 1]) * rng.integers(15, 70))
                band = img[y0:y0 + h]
                band = np.roll(band, sx, axis=1)
                band[..., 0] = np.roll(band[..., 0], 9, axis=1)
                band[..., 2] = np.roll(band[..., 2], -9, axis=1)
                img[y0:y0 + h] = band
        # grade (the S-curve went in through the LUT): a little more colour, cooler deep shadows
        luma = img @ np.float32([0.2126, 0.7152, 0.0722])
        img = luma[..., None] + (img - luma[..., None]) * 1.12
        shade = ((1 - luma) ** 3)[..., None]
        img += shade * np.float32([-0.002, 0.0, 0.008])
        # bloom (screen) from the highlights
        small = cv2.resize(img, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
        sl = small @ np.float32([0.2126, 0.7152, 0.0722])
        mask = np.clip((sl - 0.55) / 0.45, 0, 1) ** 1.3
        hi = small * mask[..., None]
        bl = 0.55 * cv2.GaussianBlur(hi, (0, 0), 4) + 0.45 * cv2.GaussianBlur(hi, (0, 0), 16)
        bl = cv2.resize(bl, (W, H), interpolation=cv2.INTER_LINEAR)
        kb = float(p["bloom"][k])
        img = 1 - (1 - np.clip(img, 0, 1)) * (1 - np.clip(kb * bl, 0, 1))
        img *= 1 + float(p["expo"][k])
        fl = float(p["flash"][k])
        if fl > 1e-3:
            img = img + fl * (1 - img)
        img *= self.vig
        img += 0.010 * self.grain[k % 12][..., None]
        return (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)


def count_frames(src):
    return int(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries",
                               "stream=nb_read_frames", "-of", "csv=p=0", src], capture_output=True, text=True).stdout)


def decode(src, k0, n):
    ss = [] if k0 == 0 else ["-ss", f"{(k0 - 0.5) / FPS:.6f}"]
    return subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", *ss, "-i", src, "-frames:v", str(n), "-f", "rawvideo",
                             "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)


def work(args):
    src, out, k0, n, total = args
    p = timeline(total)
    look = Look()
    dec = decode(src, k0, n)
    enc = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "fast", "-crf", "15", "-pix_fmt", "yuv420p",
                            out], stdin=subprocess.PIPE)
    done = 0
    while done < n:
        buf = dec.stdout.read(W * H * 3)
        if len(buf) < W * H * 3:
            break
        frame = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
        enc.stdin.write(look(frame, k0 + done, p).tobytes())
        done += 1
    enc.stdin.close()
    enc.wait()
    dec.wait()
    return out, done


def main():
    src = sys.argv[1]
    if sys.argv[2] == "--stills":
        frames = [int(x) for x in sys.argv[3].split(",")]
        outdir = sys.argv[4]
        os.makedirs(outdir, exist_ok=True)
        total = count_frames(src)
        p, look = timeline(total), Look()
        for k in frames:
            dec = decode(src, k, 1)
            frame = np.frombuffer(dec.stdout.read(W * H * 3), np.uint8).reshape(H, W, 3)
            dec.wait()
            cv2.imwrite(f"{outdir}/f{k:05d}_a.png", frame[..., ::-1])
            cv2.imwrite(f"{outdir}/f{k:05d}_b.png", look(frame, k, p)[..., ::-1])
        return
    out = sys.argv[2]
    workers = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    total = count_frames(src)
    tmp = os.path.abspath(out) + ".parts"   # absolute: the concat list resolves paths from its own folder
    os.makedirs(tmp, exist_ok=True)
    bounds = [round(i * total / workers) for i in range(workers + 1)]
    jobs = [(src, f"{tmp}/part{i}.mp4", bounds[i], bounds[i + 1] - bounds[i], total) for i in range(workers)]
    with Pool(workers) as pool:
        res = pool.map(work, jobs)
    assert sum(n for _, n in res) == total, (res, total)
    with open(f"{tmp}/list.txt", "w") as f:
        for path, _ in res:
            f.write(f"file '{path}'\n")
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", f"{tmp}/list.txt", "-i", src,
                    "-map", "0:v", "-map", "1:a", "-c", "copy", "-movflags", "+faststart", out], check=True)
    print("polished", total, "frames ->", out)


if __name__ == "__main__":
    main()
