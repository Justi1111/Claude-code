"""Toggle each bus driver and list every block whose redstone state changes."""
import time
import cell, build
from mc import cmd, setblock
O = (0, 20, 0)
L = cell.chain(3)
PROBE = {"hopper": "hopper[enabled=true]", "dropper": "dropper[triggered=true]",
         "repeater": "repeater[powered=true]", "comparator": "comparator[powered=true]",
         "observer": "observer[powered=true]", "redstone_wall_torch": "redstone_wall_torch[lit=true]",
         "redstone_wire": "redstone_wire[power=0]"}
DRIVERS = {b.net: p for p, b in L.blocks.items() if b.id == "redstone_block"}


def snapshot():
    s = {}
    for p, b in L.blocks.items():
        if b.id in PROBE:
            s[p] = build.state(O, p, PROBE[b.id])
    return s


def driver(net, on):
    x, y, z = DRIVERS[net]
    setblock(O[0] + x, O[1] + y, O[2] + z, "redstone_block" if on else "air")


for net in DRIVERS:
    driver(net, True)
time.sleep(1.5)
base = snapshot()
for net in DRIVERS:
    driver(net, False)
    time.sleep(1.5)
    now = snapshot()
    changed = [p for p in base if base[p] != now[p]]
    by = {}
    for p in changed:
        b = L.blocks[p]
        key = (b.id, b.net or b.note)
        by.setdefault(key, []).append(p)
    print(f"== {net} off: {len(changed)} changes")
    for (bid, n), ps in sorted(by.items(), key=str):
        if bid == "redstone_wire" and n == net:
            continue
        print(f"   {bid:22s} {str(n):20s} {ps[:4]}{'...' if len(ps) > 4 else ''}")
    driver(net, True)
    time.sleep(1.5)
    again = snapshot()
    diff = [p for p in base if base[p] != again[p]]
    if diff:
        print("   !! not restored:", [(p, L.blocks[p].note) for p in diff][:8])
