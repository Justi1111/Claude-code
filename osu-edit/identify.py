"""Identify which .osr replay a danser render shows, and where it starts.

Finds the cursor in every frame (bright cyan blob), then matches the path against
every replay in replays/ to recover the map time at video t=0.

    python3 identify.py clips/danser2.mp4 [more.mp4 ...]
"""
import glob
import json
import os
import subprocess
import sys

import cv2
import numpy as np

import osr

HERE = os.path.dirname(os.path.abspath(__file__))


def cursor_track(path, fps=30, W=960, H=540):
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", path, "-vf", f"fps={fps},scale={W}:{H}", "-f", "rawvideo",
                          "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
    out, i = [], 0
    src_w = int(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width",
                                "-of", "csv=p=0", path], capture_output=True, text=True).stdout.strip())
    k = src_w / W
    while True:
        buf = p.stdout.read(W * H * 3)
        if len(buf) < W * H * 3:
            break
        f = np.frombuffer(buf, np.uint8).reshape(H, W, 3).astype(np.int16)
        b, g, r = f[..., 0], f[..., 1], f[..., 2]
        m = ((b > 200) & (g > 200) & (r < 170) & (g - r > 60)).astype(np.uint8)
        n, lab, st, cen = cv2.connectedComponentsWithStats(m)
        if n > 1:
            j = 1 + np.argmax(st[1:, cv2.CC_STAT_AREA])
            out.append((i / fps, cen[j][0] * k, cen[j][1] * k, st[j, cv2.CC_STAT_AREA]))
        else:
            out.append((i / fps, np.nan, np.nan, 0))
        i += 1
    p.wait()
    return np.array(out), src_w


def match(track, src_w, replays):
    ok = (~np.isnan(track[:, 1])) & (track[:, 3] > 40)
    vt, vx, vy = track[ok, 0], track[ok, 1], track[ok, 2]
    H = src_w * 9 / 16
    s = 0.8 * H / 384
    ox, oy = (src_w - 512 * s) / 2, (H - 384 * s) / 2
    sub = np.arange(0, len(vt), 3)
    results = []
    for rp in replays:
        o = osr.parse(rp)
        fr = np.array(o["frames"], float)
        mods = osr.mods_str(o["mods"])
        rate = 1.5 if ("DT" in mods or "NC" in mods) else 1.0
        if "HT" in mods:
            rate = 0.75
        t, x, y = fr[:, 0], fr[:, 1], fr[:, 2]
        if "HR" in mods:
            y = 384 - y

        def err(T0, idx):
            mt = T0 + vt[idx] * 1000 * rate
            return np.median(np.hypot(ox + np.interp(mt, t, x) * s - vx[idx], oy + np.interp(mt, t, y) * s - vy[idx]))
        span = (vt[-1] - vt[0]) * 1000 * rate
        best = min((err(T0, sub), T0) for T0 in np.arange(-2000, t[-1] - span, 50))
        T0 = best[1]
        best = min((err(T, np.arange(len(vt))), T) for T in np.arange(T0 - 80, T0 + 80, 1))
        results.append(dict(replay=os.path.relpath(rp, HERE), err=float(best[0]), offset=float(best[1] / 1000),
                            rate=rate, mods=mods, acc=o["acc"], combo=o["max_combo"]))
    results.sort(key=lambda r: r["err"])
    return results


if __name__ == "__main__":
    reps = sorted(glob.glob(os.path.join(HERE, "replays", "*.osr")))
    for path in sys.argv[1:]:
        tr, w = cursor_track(path)
        res = match(tr, w, reps)
        b = res[0]
        print(f"{path}: {b['replay']}  {b['mods']}  offset {b['offset']:.3f}s  err {b['err']:.1f}px"
              f"  (next best {res[1]['err']:.0f}px)")
        print("   " + json.dumps({"file": b["replay"], "offset": round(b["offset"], 3), "rate": b["rate"]}))
