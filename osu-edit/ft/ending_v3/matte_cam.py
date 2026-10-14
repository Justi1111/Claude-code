"""Person matte for the face-cam window (Robust Video Matting, ONNX) over a time range of a clip.

usage: python -I matte_cam.py <clip> <t0> <t1> <out.npy> [x0,y0,x1,y1]
Saves uint8 alpha frames at 2x the window size, 60 fps, starting at t0.
"""
import os
import subprocess
import sys

import numpy as np
import onnxruntime as ort

clip, t0, t1, out = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
x0, y0, x1, y1 = [int(v) for v in (sys.argv[5] if len(sys.argv) > 5 else "885,850,1275,1065").split(",")]
w, h = (x1 - x0) * 2, (y1 - y0) * 2
raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t0:.3f}", "-to", f"{t1:.3f}", "-i", clip,
                      "-vf", f"fps=60,crop={x1 - x0}:{y1 - y0}:{x0}:{y0},scale={w}:{h}:flags=lanczos",
                      "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
n = len(raw) // (w * h * 3)
fr = np.frombuffer(raw[:n * w * h * 3], np.uint8).reshape(n, h, w, 3)
sess = ort.InferenceSession(os.environ.get("RVM_ONNX", "rvm_mobilenetv3_fp32.onnx"),
                            providers=["CPUExecutionProvider"])
rec = [np.zeros((1, 1, 1, 1), np.float32)] * 4
dr = np.array([0.5], np.float32)
alphas = np.zeros((n, h, w), np.uint8)
for i in range(n):
    src = (fr[i].astype(np.float32) / 255.0).transpose(2, 0, 1)[None]
    fgr, pha, *rec = sess.run(None, {"src": src, "r1i": rec[0], "r2i": rec[1], "r3i": rec[2], "r4i": rec[3], "downsample_ratio": dr})
    alphas[i] = np.clip(pha[0, 0] * 255, 0, 255).astype(np.uint8)
np.save(out, alphas)
print("frames", n, "size", w, h, "mean alpha", round(float(alphas.mean()) / 255, 3))
