"""Cut a time range from a Twitch VOD by fetching only the needed HLS segments.

usage: python -I vod_cut.py <vod_id> <start> <end> <out.mp4> [format]
start/end as seconds or h:mm:ss. Uses yt-dlp to resolve the playlist, curl for segments.
"""
import os
import re
import subprocess
import sys
import tempfile
import urllib.parse


def secs(x):
    if ":" in x:
        p = [float(v) for v in x.split(":")]
        while len(p) < 3:
            p.insert(0, 0.0)
        return p[0] * 3600 + p[1] * 60 + p[2]
    return float(x)


vod, s0, s1, out = sys.argv[1], secs(sys.argv[2]), secs(sys.argv[3]), sys.argv[4]
fmt = sys.argv[5] if len(sys.argv) > 5 else "1080p60/720p60/best"
m3u8 = subprocess.run(["yt-dlp", "-g", "-f", fmt, f"https://www.twitch.tv/videos/{vod}"],
                      capture_output=True, text=True).stdout.strip().splitlines()[-1]
pl = subprocess.run(["curl", "-sS", m3u8], capture_output=True, text=True).stdout
base = m3u8.rsplit("/", 1)[0] + "/"
t = 0.0
segs = []
dur = None
for line in pl.splitlines():
    if line.startswith("#EXTINF:"):
        dur = float(line[8:].split(",")[0])
    elif line and not line.startswith("#") and dur is not None:
        if t + dur > s0 and t < s1:
            segs.append((t, urllib.parse.urljoin(base, line)))
        t += dur
        dur = None
if not segs:
    sys.exit("no segments in range")
tmp = tempfile.mkdtemp(prefix="vodcut_")
files = []
for i, (st, url) in enumerate(segs):
    f = os.path.join(tmp, f"{i:05d}.ts")
    subprocess.run(["curl", "-sS", "--retry", "3", "-o", f, url], check=True)
    files.append(f)
lst = os.path.join(tmp, "list.txt")
open(lst, "w").write("".join(f"file '{f}'\n" for f in files))
joined = os.path.join(tmp, "joined.ts")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined], check=True)
off = s0 - segs[0][0]
subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{off:.3f}", "-i", joined, "-t", f"{s1 - s0:.3f}",
                "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart", out], check=True)
for f in files + [lst, joined]:
    os.remove(f)
os.rmdir(tmp)
print("wrote", out, f"{s1 - s0:.1f}s from {len(segs)} segments")
