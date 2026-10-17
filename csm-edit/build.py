"""Render the Chainsaw Man collage edit.

usage: python3 -I build.py render <out.mp4> [workers]        full edit with the reference sound
       python3 -I build.py sheet <out.png> t1,t2,...           contact sheet of single frames
       python3 -I build.py stills <outdir> t1,t2,...           full-size PNGs
       python3 -I build.py part <out.mp4> t0 t1 [workers]      a time range (with sound)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import edit  # noqa: E402
from engine import timeline as tl  # noqa: E402


def main():
    cmd = sys.argv[1]
    edit.preload()
    if cmd == "render":
        workers = int(sys.argv[3]) if len(sys.argv) > 3 else 4
        tl.render("edit", sys.argv[2], edit.END, audio=edit.AUDIO, workers=workers)
    elif cmd == "part":
        t0, t1 = float(sys.argv[3]), float(sys.argv[4])
        workers = int(sys.argv[5]) if len(sys.argv) > 5 else 4
        tl.render("edit", sys.argv[2], edit.END, audio=edit.AUDIO, workers=workers,
                  k_start=int(round(t0 * 24)), k_end=int(round(t1 * 24)))
    elif cmd == "sheet":
        times = [float(x) for x in sys.argv[3].split(",")]
        tl.sheet(times, sys.argv[2])
    elif cmd == "stills":
        times = [float(x) for x in sys.argv[3].split(",")]
        tl.stills(times, sys.argv[2])
    print("done", cmd)


if __name__ == "__main__":
    main()
