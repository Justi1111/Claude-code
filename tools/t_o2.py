"""Exact strong-power windows of the lift droppers (= their O2 observer pulses)."""
from seqtest import *
import build, time
SPEC = {"G_inj": [(0, 4)], "G_probe": [(32, 36)], "G_pulls": [(38, 48)], "G_R": [(47, 68)],
        "G_L1": [(51, 66)], "G_mw": [(43, 51)]}
clear_items()
build.load_blockers(O)
put(*at("A"), 0, "cobblestone", 10)
put(*at("F"), 0, "cobblestone", 1)
O2 = {"E0": (0, -4, 2), "E1": (0, -3, 2), "E2": (0, -2, 2), "E3": (0, -1, 2),
      "M1": (-1, -3, -1), "M2": (-1, -2, -1), "M3": (-1, -1, -1)}
on = {k: [] for k in O2}
sched = windows(SPEC, 1000)
freeze(); time.sleep(0.3)
for t in range(90):
    for net in DRIVERS:
        drive(net, sched(net, t))
    step(1)
    for k, p in O2.items():
        if build.state(O, p, "observer[powered=true]"):
            on[k].append(t)
unfreeze()
for k, v in on.items():
    print(k, v)
