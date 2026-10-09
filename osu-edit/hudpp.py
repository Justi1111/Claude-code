"""Read danser's live pp counter (top-left HUD) from a render, frame by frame.

Digit templates are learned from a few crops whose values are known, then every
frame's counter is segmented and matched. Results are cached in cache/<clip>.pp.json.
"""
import json
import os
import subprocess

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")
CROP = (0, 175, 330, 110)  # x, y, w, h of the pp counter in a 1920x1080 danser render
SIZE = (24, 36)

# (clip file, time in s, value shown) used to learn the digit shapes
KNOWN = [
    ("clips/danser_1256809.mp4", 3.8, "1281"), ("clips/danser_1256809.mp4", 5.48, "1284"),
    ("clips/danser_1256809.mp4", 9.27, "1300"), ("clips/danser_1475722.mp4", 9.92, "1601"),
    ("clips/danser_1475722.mp4", 13.47, "1734"), ("clips/danser_5774158.mp4", 3.97, "908"),
    ("clips/danser_5774158.mp4", 6.5, "986"), ("clips/danser_5774158.mp4", 9.19, "1028"),
    ("clips/danser_5589237.mp4", 3.58, "1109"), ("clips/danser_5589237.mp4", 8.2, "1255"),
    ("clips/danser_5589237.mp4", 12.88, "1155"),
]


def _grab(path, t):
    x, y, w, h = CROP
    out = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", path, "-frames:v", "1", "-vf",
                          f"crop={w}:{h}:{x}:{y}", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                         capture_output=True).stdout
    return np.frombuffer(out, np.uint8).reshape(h, w)


def _glyphs(gray):
    """Digit glyph images left to right (the trailing 'pp' is dropped)."""
    g = gray.astype(np.float32)
    m = (g > max(60.0, g.max() * 0.55)).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    comps = [st[i] for i in range(1, n) if st[i, cv2.CC_STAT_AREA] > 40 and st[i, cv2.CC_STAT_HEIGHT] > 25]
    comps.sort(key=lambda s: s[0])
    if not comps:
        return []
    # digits share the cap line; 'p' glyphs hang below it
    top = min(s[1] for s in comps)
    digits = [s for s in comps if s[1] <= top + 4]
    out = []
    for x, y, w, h, _ in digits:
        out.append(cv2.resize(m[y:y + h, x:x + w].astype(np.float32), SIZE, interpolation=cv2.INTER_AREA))
    return out


def learn():
    acc = {str(d): [] for d in range(10)}
    for path, t, val in KNOWN:
        gl = _glyphs(_grab(os.path.join(HERE, path), t))
        if len(gl) != len(val):
            continue
        for ch, img in zip(val, gl):
            acc[ch].append(img)
    return {d: np.mean(v, 0) for d, v in acc.items() if v}


def read_value(gray, templates):
    gl = _glyphs(gray)
    if not gl:
        return None
    s = ""
    for img in gl:
        best = min(templates, key=lambda d: np.abs(templates[d] - img).mean())
        s += best
    return int(s) if s else None


def pp_track(path, fps=10):
    """Live pp per 1/fps second for the whole clip (cached)."""
    os.makedirs(CACHE, exist_ok=True)
    cp = os.path.join(CACHE, os.path.basename(path) + ".pp.json")
    if os.path.exists(cp) and os.path.getmtime(cp) > os.path.getmtime(path):
        return json.load(open(cp))
    tm = learn()
    x, y, w, h = CROP
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", path, "-vf", f"fps={fps},crop={w}:{h}:{x}:{y}", "-f",
                          "rawvideo", "-pix_fmt", "gray", "-"], stdout=subprocess.PIPE)
    vals = []
    while True:
        buf = p.stdout.read(w * h)
        if len(buf) < w * h:
            break
        vals.append(read_value(np.frombuffer(buf, np.uint8).reshape(h, w), tm))
    p.wait()
    # reject misreads (implausible values, isolated spikes), then fill gaps
    arr = np.array([v if v is not None else np.nan for v in vals], float)
    arr[(arr < 50) | (arr > 4000)] = np.nan
    med = np.array([np.nanmedian(arr[max(0, i - 3):i + 4]) if np.any(~np.isnan(arr[max(0, i - 3):i + 4])) else np.nan
                    for i in range(len(arr))])
    arr[np.abs(arr - med) > 60] = np.nan
    idx = np.where(~np.isnan(arr))[0]
    if len(idx):
        arr = np.interp(np.arange(len(arr)), idx, arr[idx])
    res = {"fps": fps, "pp": [float(v) for v in arr]}
    json.dump(res, open(cp, "w"))
    return res


if __name__ == "__main__":
    import sys
    for f in sys.argv[1:]:
        r = pp_track(os.path.join(HERE, f))
        pp = np.array(r["pp"])
        print(f, "frames", len(pp), "range", pp.min(), pp.max())
        print("  every 1s:", [int(v) for v in pp[::r["fps"]]])
