"""Scenes on a timeline, post effects, and the (multi-process) render loop.

A scene is a function f(ctx) drawn while t0 <= t < t1. Scenes may overlap (later ones draw on top). Post effects are
functions g(rgb, ctx) -> rgb applied to the finished frame inside their window. ctx carries:
  t (edit time), lt (time since scene start), u (0..1 through the scene), dur, k (frame index), cv (skia canvas).
"""
import os
import subprocess
import sys
from multiprocessing import Pool

import numpy as np

from . import core

SCENES = []
POSTS = []
BEATS = []          # filled by the edit (beat times in seconds)


class Ctx:
    pass


def scene(t0, t1, name=None, z=0):
    def deco(fn):
        SCENES.append(dict(t0=t0, t1=t1, fn=fn, name=name or fn.__name__, z=z))
        return fn
    return deco


def post(t0, t1, name=None):
    def deco(fn):
        POSTS.append(dict(t0=t0, t1=t1, fn=fn, name=name or fn.__name__))
        return fn
    return deco


def beat(i):
    """time of beat i (fractional i interpolates; beyond the list it extrapolates with the mean period)."""
    if not BEATS:
        raise RuntimeError("BEATS not set")
    period = (BEATS[-1] - BEATS[0]) / (len(BEATS) - 1)
    if i < 0:
        return BEATS[0] + i * period
    j = int(np.floor(i))
    f = i - j
    if j + 1 < len(BEATS):
        return BEATS[j] + (BEATS[j + 1] - BEATS[j]) * f
    return BEATS[-1] + (i - (len(BEATS) - 1)) * period


def render_frame(k, frame=None):
    t = k / core.FPS
    frame = frame or core.Frame()
    cv = frame.clear()
    ctx = Ctx()
    ctx.t, ctx.k, ctx.cv, ctx.frame = t, k, cv, frame
    for s in sorted((s for s in SCENES if s["t0"] <= t < s["t1"]), key=lambda s: s["z"]):
        ctx.lt = t - s["t0"]
        ctx.dur = s["t1"] - s["t0"]
        ctx.u = ctx.lt / ctx.dur if ctx.dur > 0 else 1.0
        cv.save()
        s["fn"](ctx)
        cv.restore()
    rgb = frame.array()
    for p in POSTS:
        if p["t0"] <= t < p["t1"]:
            ctx.lt = t - p["t0"]
            ctx.dur = p["t1"] - p["t0"]
            ctx.u = ctx.lt / ctx.dur if ctx.dur > 0 else 1.0
            rgb = p["fn"](rgb, ctx)
    return rgb


def _work(args):
    module, k0, k1, out = args
    __import__(module)
    w = core.Writer(out, crf=14)
    frame = core.Frame()
    for k in range(k0, k1):
        w.write(render_frame(k, frame))
    w.close()
    return out


def render(module, out, t_end, audio=None, audio_ss=0.0, workers=4, k_start=0, k_end=None):
    """render frames [k_start, k_end) of the edit defined in `module` to out (with audio if given)."""
    n = int(round(t_end * core.FPS))
    k_end = n if k_end is None else k_end
    tmp = os.path.abspath(out) + ".parts"
    os.makedirs(tmp, exist_ok=True)
    total = k_end - k_start
    bounds = [k_start + round(i * total / workers) for i in range(workers + 1)]
    jobs = [(module, bounds[i], bounds[i + 1], f"{tmp}/part{i:02d}.mp4") for i in range(workers) if bounds[i + 1] > bounds[i]]
    with Pool(len(jobs)) as pool:
        parts = pool.map(_work, jobs)
    with open(f"{tmp}/list.txt", "w") as f:
        for p in parts:
            f.write(f"file '{p}'\n")
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", f"{tmp}/list.txt"]
    if audio:
        a0 = audio_ss + k_start / core.FPS
        cmd += ["-ss", f"{a0:.3f}", "-t", f"{total / core.FPS:.3f}", "-i", audio, "-map", "0:v", "-map", "1:a",
                "-c:a", "aac", "-b:a", "256k"]
    cmd += ["-c:v", "copy", "-movflags", "+faststart", out]
    subprocess.run(cmd, check=True)
    return out


def stills(times, outdir, prefix="f"):
    import cv2
    os.makedirs(outdir, exist_ok=True)
    frame = core.Frame()
    paths = []
    for t in times:
        k = int(round(t * core.FPS))
        p = f"{outdir}/{prefix}{k:05d}.png"
        cv2.imwrite(p, render_frame(k, frame)[..., ::-1])
        paths.append(p)
    return paths


def sheet(times, out, cols=6, tile=(480, 270)):
    """contact sheet of rendered frames at the given times, labelled."""
    import cv2
    frame = core.Frame()
    rows = (len(times) + cols - 1) // cols
    canvas = np.full((rows * tile[1], cols * tile[0], 3), 40, np.uint8)
    for i, t in enumerate(times):
        k = int(round(t * core.FPS))
        im = cv2.resize(render_frame(k, frame), tile, interpolation=cv2.INTER_AREA)
        cv2.putText(im, f"{t:.2f}", (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(im, f"{t:.2f}", (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 230, 0), 1, cv2.LINE_AA)
        r, c = divmod(i, cols)
        canvas[r * tile[1]:(r + 1) * tile[1], c * tile[0]:(c + 1) * tile[0]] = im
    cv2.imwrite(out, canvas[..., ::-1])
    return out


if __name__ == "__main__":
    sys.exit("import this module")
