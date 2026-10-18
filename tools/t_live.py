"""Real-time test: items go into the INPUT chest, the redstone sequencer does the rest."""
import sys, time
import build
from mc import cmd, put, items
from seqtest import O, at, clear_items, nudge, NAMES
import cell

N = 3
INPUT = (O[0] - 3, O[1], O[2])
OVF = (O[0] + N * cell.PITCH - 1, O[1] - 4, O[2] + 1)


def tally(pos, acc):
    for s, it, k, _ in items(*pos):
        acc[it.split(":")[1]] = acc.get(it.split(":")[1], 0) + k
    return acc


def summary():
    out = {}
    for i in range(N):
        c = {}
        tally(at("A", i), c); tally(at("B", i), c)
        out[f"cell{i}"] = c
    out["overflow"] = tally(OVF, {})
    out["input"] = tally(INPUT, {})
    busy = {}
    for i in range(N):
        for n in NAMES:
            if n in ("A", "B", "F1"):
                continue
            for s, it, k, _ in items(*at(n, i)):
                if n == "T" and s > 0:
                    continue
                busy[f"{n}@{i}"] = busy.get(f"{n}@{i}", 0) + k
    for p in [(O[0] - 3, O[1] + y, O[2]) for y in (-1, -2, -3, -4)] + [(O[0] - 2, O[1] - 4, O[2]), (O[0] - 2, O[1] - 4, O[2] + 1)]:
        for s, it, k, _ in items(*p):
            busy["feed"] = busy.get("feed", 0) + k
    out["busy"] = busy
    return out


def setup(chests, inp):
    clear_items(N)
    cmd(f"data merge block {OVF[0]} {OVF[1]} {OVF[2]} {{Items:[]}}")
    cmd(f"data merge block {INPUT[0]} {INPUT[1]} {INPUT[2]} {{Items:[]}}")
    for i in range(N):
        build.load_blockers((O[0] + 6 * i, O[1], O[2]))
        for slot, (it, n) in enumerate(chests[i]):
            put(*at("A", i), slot, it, n)
    nudge(N)
    for slot, (it, n) in enumerate(inp):
        put(*INPUT, slot, it, n)


def wait(limit):
    t0 = time.time()
    while time.time() - t0 < limit:
        time.sleep(5)
        s = summary()
        if not s["busy"] and not s["input"]:
            return s, time.time() - t0
    return summary(), time.time() - t0


if __name__ == "__main__":
    setup([[("cobblestone", 1)], [("dirt", 1), ("sand", 1)], [("oak_log", 3)]],
          [("cobblestone", 5), ("dirt", 4), ("sand", 3), ("oak_log", 2), ("stone", 2), ("glass", 1)])
    s, dt = wait(float(sys.argv[1]) if len(sys.argv) > 1 else 180)
    print(round(dt), "s", s)
