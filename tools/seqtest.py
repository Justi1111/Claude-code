"""Drive the bus lines of a built chain tick by tick and log item positions."""
import time
import cell
from mc import cmd, setblock, put, items, freeze, unfreeze, step

O = (0, 20, 0)
L = cell.chain(3)
DRIVERS = {b.net: p for p, b in L.blocks.items() if b.id == "redstone_block"}
NAMES = {"F": (-1, -4, 1), "E0": (0, -4, 1), "E1": (0, -3, 1), "E2": (0, -2, 1), "E3": (0, -1, 1),
         "T": (0, -1, 0), "P": (0, -2, 0), "R": (0, -3, 0), "L": (0, -4, 0),
         "M1": (-1, -3, 0), "M2": (-1, -2, 0), "M3": (-1, -1, 0), "A": (0, 0, 0), "B": (-1, 0, 0),
         "t1": (1, -4, 0), "t2": (2, -4, 0), "t3": (3, -4, 0), "t4": (4, -4, 0), "t5": (4, -4, 1),
         "F1": (5, -4, 1)}
_state = {}


def at(name, cell_i=0):
    x, y, z = NAMES[name]
    return O[0] + x + cell.PITCH * cell_i, O[1] + y, O[2] + z


def drive(net, on):
    if _state.get(net) == on:
        return
    x, y, z = DRIVERS[net]
    setblock(O[0] + x, O[1] + y, O[2] + z, "redstone_block" if on else "air")
    _state[net] = on


def counts(names, cell_i=0):
    out = {}
    for n in names:
        its = items(*at(n, cell_i))
        if n == "T":
            out[n] = sum(c for s, _, c, _ in its if s == 0)
        else:
            out[n] = sum(c for _, _, c, _ in its)
    return out


def clear_items(cells=3):
    for i in range(cells):
        for n in NAMES:
            x, y, z = at(n, i)
            if n == "T":
                cmd(f"data remove block {x} {y} {z} Items[{{Slot:0b}}]")
            else:
                cmd(f"data merge block {x} {y} {z} {{Items:[]}}")


def nudge(cells=3):
    """Force comparator re-reads (item edits by command skip some updates)."""
    for i in range(cells):
        for pos in ((1, -1, 1), (1, -1, -1)):          # beside the T comparator
            x, y, z = O[0] + pos[0] + cell.PITCH * i, O[1] + pos[1], O[2] + pos[2]
            setblock(x, y, z, "glass")
            setblock(x, y, z, "air")


def run(schedule, ticks, watch, cell_i=0, log=True):
    """schedule(net, t) -> driver on?  Returns list of (t, counts)."""
    freeze()
    time.sleep(0.3)
    hist = []
    for t in range(ticks):
        for net in DRIVERS:
            drive(net, schedule(net, t))
        step(1)
        c = counts(watch, cell_i)
        hist.append((t, c))
        if log:
            nz = " ".join(f"{k}{v}" for k, v in c.items() if v)
            print(f"t={t:3d} {nz}")
    unfreeze()
    return hist


def windows(spec, period):
    """spec: net -> list of (start, end) during which the driver is OFF
    (for G_L1: ON).  Default driver state: ON for all, OFF for G_L1."""
    def f(net, t):
        tt = t % period
        inside = any(a <= tt < b for a, b in spec.get(net, []))
        default = net != "G_L1"
        return (not default) if inside else default
    return f
