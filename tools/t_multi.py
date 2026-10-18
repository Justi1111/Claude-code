"""Three cells, period-30 schedule, mixed input; check where every item ends up."""
import sys, time
from seqtest import *
import build
from mc import setblock
PERIOD = 40
SCHED = {"G_inj": [(0, 4)], "G_probe": [(32, 36)], "G_pulls": [(38, 40), (0, 8)], "G_R": [(6, 26)],
         "G_L1": [(10, 26)], "G_mw": [(2, 10)]}
OVF = (O[0] + 17, O[1] - 4, O[2] + 1)  # part of the built east end


def setup(chests, feed):
    clear_items()
    cmd(f"data merge block {OVF[0]} {OVF[1]} {OVF[2]} {{Items:[]}}")
    for i in range(3):
        build.load_blockers((O[0] + 6 * i, O[1], O[2]))
        for slot, (it, n) in enumerate(chests[i]):
            put(*at("A", i), slot, it, n)
    for slot, (it, n) in enumerate(feed):
        put(*at("F"), slot, it, n)
    nudge()


def summary():
    out = {}
    for i in range(3):
        c = {}
        for n in ("A", "B"):
            for _, it, k, _ in items(*at(n, i)):
                c[it.split(":")[1]] = c.get(it.split(":")[1], 0) + k
        out[f"cell{i}"] = c
    c = {}
    for _, it, k, _ in items(*OVF):
        c[it.split(":")[1]] = c.get(it.split(":")[1], 0) + k
    out["overflow"] = c
    stray = {}
    for i in range(3):
        for n in NAMES:
            if n in ("A", "B"):
                continue
            for s, it, k, _ in items(*at(n, i)):
                if n == "T" and s > 0:
                    continue
                stray[f"{n}{i}"] = stray.get(f"{n}{i}", 0) + k
    out["in_machine"] = stray
    return out


if __name__ == "__main__":
    setup([[("cobblestone", 1)], [("dirt", 1)], [("sand", 1)]],
          [("cobblestone", 3), ("dirt", 2), ("sand", 2), ("stone", 2), ("oak_log", 1)])
    ticks = int(sys.argv[1]) if len(sys.argv) > 1 else 600
    t0 = time.time()
    run(windows(SCHED, PERIOD), ticks, [], log=False)
    print("ran", ticks, "ticks in", round(time.time() - t0), "s")
    print(summary())
