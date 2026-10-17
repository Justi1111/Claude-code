"""Anime character cut-outs: isnetis (skytnt/anime-seg) mattes over source video frames, cached as RGBA PNGs.

A Cut is a list of RGBA frames (straight alpha, cropped to the subject) sampled from a source time range, with an
optional crop box applied to the source first (to isolate one character or avoid burned-in text).
"""
import hashlib
import json
import os
import subprocess

import cv2
import numpy as np

SCRATCH = os.environ.get("CSM_SCRATCH",
                         "/tmp/claude-0/-home-user-Claude-code/a61365b4-59b2-5d5f-8537-7f9c9b765619/scratchpad/csm")
MODEL = f"{SCRATCH}/models/isnetis.onnx"
CACHE = f"{SCRATCH}/cache/cut"
SRC = f"{SCRATCH}/src"

_sess = None


def _session():
    global _sess
    if _sess is None:
        import onnxruntime as ort
        so = ort.SessionOptions()
        so.intra_op_num_threads = int(os.environ.get("CSM_SEG_THREADS", "4"))
        _sess = ort.InferenceSession(MODEL, so, providers=["CPUExecutionProvider"])
    return _sess


def segment(rgb, size=1024):
    """alpha (float32 0..1, HxW) of the anime subject(s) in an RGB uint8 image."""
    h, w = rgb.shape[:2]
    s = size / max(h, w)
    nh, nw = int(round(h * s)), int(round(w * s))
    img = cv2.resize(rgb, (nw, nh), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    pad = np.zeros((size, size, 3), np.float32)
    y0, x0 = (size - nh) // 2, (size - nw) // 2
    pad[y0:y0 + nh, x0:x0 + nw] = img
    out = _session().run(None, {"img": pad.transpose(2, 0, 1)[None]})[0][0, 0]
    m = out[y0:y0 + nh, x0:x0 + nw]
    return cv2.resize(m, (w, h), interpolation=cv2.INTER_LINEAR).clip(0, 1)


def grabcut(rgb, rect, init=None, iters=6):
    """GrabCut matte (0..1) inside rect=(x0,y0,x1,y1); init = optional prior alpha to seed fg/bg."""
    h, w = rgb.shape[:2]
    mask = np.full((h, w), cv2.GC_BGD, np.uint8)
    x0, y0, x1, y1 = rect
    mask[y0:y1, x0:x1] = cv2.GC_PR_FGD
    if init is not None:
        mask[(init > 0.85)] = cv2.GC_FGD
        mask[(init < 0.05) & (mask == cv2.GC_PR_FGD)] = cv2.GC_PR_BGD
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    bgr = np.ascontiguousarray(rgb[..., ::-1])
    cv2.grabCut(bgr, mask, None, bgd, fgd, iters, cv2.GC_INIT_WITH_MASK)
    a = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 1.0, 0.0).astype(np.float32)
    return cv2.GaussianBlur(a, (0, 0), 1.0)


def refine(alpha, rgb=None, erode=1, feather=0.8, lo=0.25, hi=0.75, min_comp=0.02, keep_largest=False):
    """tighten a soft matte: contrast-stretch, small erode, light feather, drop specks / stray islands."""
    a = np.clip((alpha - lo) / (hi - lo), 0, 1)
    if erode > 0:
        a = cv2.erode(a, np.ones((2 * erode + 1, 2 * erode + 1), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats((a > 0.5).astype(np.uint8), 8)
    if n > 2:
        keep = np.zeros(n, bool)
        areas = stats[1:, cv2.CC_STAT_AREA]
        big = areas.max()
        if keep_largest:
            keep[1 + int(np.argmax(areas))] = True
        else:
            keep[1:] = areas >= max(400, big * min_comp)
        # soft edge pixels belong to their nearest kept island
        m = keep[lab].astype(np.float32)
        m = cv2.dilate(m, np.ones((5, 5), np.uint8))
        a = a * m
    if feather > 0:
        a = cv2.GaussianBlur(a, (0, 0), feather)
    return a


def read_frames(path, t0, t1, fps=None):
    """decode [t0, t1) from a video as RGB uint8 frames (native fps unless given)."""
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                            "-of", "csv=p=0", path], capture_output=True, text=True).stdout.strip().split(",")
    w, h = int(probe[0]), int(probe[1])
    vf = [f"fps={fps}"] if fps else []
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{t0:.3f}", "-i", path, "-t", f"{t1 - t0:.3f}"]
    if vf:
        cmd += ["-vf", ",".join(vf)]
    cmd += ["-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    n = len(raw) // (w * h * 3)
    return [np.frombuffer(raw, np.uint8, w * h * 3, i * w * h * 3).reshape(h, w, 3) for i in range(n)]


class Cut:
    """frames of a cut-out. cut.frames[i] = RGBA uint8 (cropped), cut.offsets[i] = (x, y) of the crop in the source."""

    def __init__(self, vid, t0, t1=None, fps=12, crop=None, erode=1, feather=0.8, lo=0.25, hi=0.75, mask_fn=None,
                 name=None, gc_rect=None, gc_seed=False, min_comp=0.02, keep_largest=False):
        self.vid, self.t0, self.t1 = vid, t0, (t1 if t1 is not None else t0 + 0.5 / fps)
        self.fps = fps
        key = json.dumps([vid, round(t0, 3), round(self.t1, 3), fps, crop, erode, feather, lo, hi, name, gc_rect, gc_seed,
                          min_comp, keep_largest, getattr(mask_fn, "version", None)], sort_keys=True)
        self.min_comp, self.keep_largest = min_comp, keep_largest
        self.gc_rect, self.gc_seed = gc_rect, gc_seed
        self.key = (name + "_" if name else "") + hashlib.md5(key.encode()).hexdigest()[:10]
        self.dir = f"{CACHE}/{self.key}"
        meta = f"{self.dir}/meta.json"
        if not os.path.exists(meta):
            self._build(crop, erode, feather, lo, hi, mask_fn)
        m = json.load(open(meta))
        self.offsets = [tuple(o) for o in m["offsets"]]
        self.src_size = tuple(m["src_size"])
        self.frames = [cv2.imread(f"{self.dir}/{i:03d}.png", cv2.IMREAD_UNCHANGED)[..., [2, 1, 0, 3]]
                       for i in range(m["n"])]

    def _build(self, crop, erode, feather, lo, hi, mask_fn):
        os.makedirs(self.dir, exist_ok=True)
        frames = read_frames(f"{SRC}/{self.vid}/video.mp4", self.t0, self.t1, fps=self.fps)
        if not frames:
            raise RuntimeError(f"no frames for {self.vid} {self.t0}-{self.t1}")
        H, W = frames[0].shape[:2]
        x0, y0, x1, y1 = crop if crop else (0, 0, W, H)
        alphas = []
        for f in frames:
            sub = np.ascontiguousarray(f[y0:y1, x0:x1])
            if self.gc_rect:
                prior = segment(sub) if self.gc_seed else None
                alphas.append(grabcut(sub, self.gc_rect, prior))
            else:
                alphas.append(segment(sub))
        # temporal smoothing of the raw mattes (anime holds frames, so neighbours mostly agree)
        sm = []
        for i in range(len(alphas)):
            win = alphas[max(0, i - 1):i + 2]
            sm.append(np.median(np.stack(win), 0) if len(win) == 3 else alphas[i])
        offsets = []
        for i, (f, a) in enumerate(zip(frames, sm)):
            sub = f[y0:y1, x0:x1]
            a = refine(a, sub, erode, feather, lo, hi, self.min_comp, self.keep_largest)
            if mask_fn is not None:
                a = a * mask_fn(sub.shape[:2])
            ys, xs = np.where(a > 0.03)
            if len(xs) == 0:
                bx0, by0, bx1, by1 = 0, 0, sub.shape[1], sub.shape[0]
            else:
                bx0, by0 = max(0, xs.min() - 3), max(0, ys.min() - 3)
                bx1, by1 = min(sub.shape[1], xs.max() + 4), min(sub.shape[0], ys.max() + 4)
            rgba = np.dstack([sub[by0:by1, bx0:bx1], (a[by0:by1, bx0:bx1] * 255).astype(np.uint8)])
            cv2.imwrite(f"{self.dir}/{i:03d}.png", rgba[..., [2, 1, 0, 3]])
            offsets.append((int(x0 + bx0), int(y0 + by0)))
        json.dump(dict(n=len(frames), offsets=offsets, src_size=(int(W), int(H)), vid=self.vid, t0=self.t0, t1=self.t1,
                       fps=self.fps), open(f"{self.dir}/meta.json", "w"))

    def __len__(self):
        return len(self.frames)

    def at(self, lt, hold_fps=None, loop=False):
        """frame index for local time lt (seconds since the cut started playing)."""
        f = hold_fps or self.fps
        i = int(np.floor(lt * f + 1e-6) * (self.fps / f))
        n = len(self.frames)
        return i % n if loop else min(max(i, 0), n - 1)

    def frame(self, lt=0.0, **kw):
        return self.frames[self.at(lt, **kw)]


def full_frames(vid, t0, t1, fps=12, crop=None):
    """plain (uncut) RGB frames, for full-frame inserts like extreme close-ups."""
    fr = read_frames(f"{SRC}/{vid}/video.mp4", t0, t1, fps=fps)
    if crop:
        x0, y0, x1, y1 = crop
        fr = [f[y0:y1, x0:x1] for f in fr]
    return fr
