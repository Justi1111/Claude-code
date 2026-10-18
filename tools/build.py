"""Place a Layout on the test server and read back block states."""
from mc import cmd, fill, put, freeze, unfreeze, step

ORDER = {"stone": 0, "glass": 0, "chest": 0, "hopper": 1, "dropper": 1,
         "observer": 2, "repeater": 2, "comparator": 2, "redstone_wall_torch": 2,
         "redstone_torch": 2, "redstone_block": 2, "redstone_wire": 3}


def clear(x0, y0, z0, x1, y1, z1, block="air"):
    for y in range(y0, y1 + 1):
        out = fill(x0, y, z0, x1, y, z1, block + " strict")   # strict: nothing pops off
        if "Successfully" not in out and "No blocks" not in out:
            raise RuntimeError(out)


def place(L, origin, skip=()):
    ox, oy, oz = origin
    items = sorted(L.blocks.items(), key=lambda kv: ORDER.get(kv[1].id, 0))
    for (x, y, z), b in items:
        if b.id in skip:
            continue
        out = cmd(f"setblock {ox + x} {oy + y} {oz + z} {b.block}")
        if "Changed the block" not in out and "Could not set" not in out:
            raise RuntimeError(f"{(x, y, z)} {b.block}: {out}")


def verify(L, origin):
    ox, oy, oz = origin
    bad = []
    for (x, y, z), b in L.blocks.items():
        out = cmd(f"execute if block {ox + x} {oy + y} {oz + z} {b.id}")
        if "passed" not in out.lower():
            bad.append(((x, y, z), b.block, b.note))
    return bad


def state(origin, pos, prop_test):
    """True if the block at origin+pos matches e.g. 'hopper[enabled=false]'."""
    ox, oy, oz = origin
    x, y, z = pos
    out = cmd(f"execute if block {ox + x} {oy + y} {oz + z} {prop_test}")
    return "passed" in out.lower()


BLOCKERS = [(1, 6), (2, 6), (3, 5), (4, 5)]


def load_blockers(origin, t_pos=(0, -1, 0), item='stick[custom_name="sorter"]'):
    ox, oy, oz = origin
    x, y, z = t_pos
    for slot, n in BLOCKERS:
        put(ox + x, oy + y, oz + z, slot, item, n)
