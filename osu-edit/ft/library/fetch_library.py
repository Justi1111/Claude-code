"""Rebuild the FlyingTuna clip library from library.tsv (Twitch clips + VOD cuts).

usage: python fetch_library.py [out_dir]   (default: ../../clips/ft_library)
Needs yt-dlp, ffmpeg and curl. Twitch clips download in source quality; VOD rows with
start/end are cut by vod_cut.py, which fetches only the needed HLS segments.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
out_root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "..", "clips", "ft_library")
for line in open(os.path.join(HERE, "library.tsv")):
    if not line.strip() or line.startswith("#"):
        continue
    chapter, name, src, start, end, title = (line.rstrip("\n").split("\t") + [""] * 6)[:6]
    out_dir = os.path.join(out_root, chapter)
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, name)
    if os.path.exists(out):
        continue
    if start:
        vod = src.rstrip("/").rsplit("/", 1)[-1]
        subprocess.run([sys.executable, os.path.join(HERE, "vod_cut.py"), vod, start, end, out])
    else:
        subprocess.run(["yt-dlp", "-q", "--no-warnings", "-f", "best[ext=mp4]/best", "-o", out, src])
    print(("ok   " if os.path.exists(out) else "FAIL ") + os.path.join(chapter, name), flush=True)
