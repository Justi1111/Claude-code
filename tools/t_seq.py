"""Sample the six phase lines at the bus start for two periods; compare with targets."""
import time
import build
from mc import freeze, unfreeze, step
O = (0, 20, 0)
POS = {"G_inj": (-1, -5, 6), "G_probe": (-1, -1, -9), "G_pulls": (-1, -2, 6),
       "G_R": (-1, -3, -9), "G_L1": (-1, -5, -9), "G_mw": (-1, -7, -9)}
TARGET = {"G_inj": lambda c: not (0 <= c < 4), "G_probe": lambda c: not (32 <= c < 36),
          "G_pulls": lambda c: not (c >= 38 or c < 8), "G_R": lambda c: c >= 26 or c < 6,
          "G_L1": lambda c: 10 <= c < 26, "G_mw": lambda c: not (2 <= c < 10)}
freeze(); time.sleep(0.3)
rows = {k: "" for k in POS}
N = 100
for t in range(N):
    step(1)
    for k, p in POS.items():
        rows[k] += "#" if not build.state(O, p, "redstone_wire[power=0]") else "."
unfreeze()
for k in POS:
    print(f"{k:8s} {rows[k]}")
# find a phase that matches every line
for ph in range(40):
    ok = all(rows[k][t] == ("#" if TARGET[k]((t + ph) % 40) else ".") for k in POS for t in range(10, N))
    if ok:
        print("all lines match with phase", ph)
best = []
for ph in range(40):
    bad = {k: sum(rows[k][t] != ("#" if TARGET[k]((t + ph) % 40) else ".") for t in range(10, N)) for k in POS}
    best.append((sum(bad.values()), ph, bad))
print(sorted(best)[:3])
