"""Build a 2-cell warehouse facing south through the datapack and sort a few items."""
import time
import seq, build, export
from mc import cmd, put, items
K, DIR, N = 1, "south", 2
C0 = (40, 20, 0)                                     # world position of cell 0's chest A


def w(p):
    x, y, z = export.rot_pos(p, K)
    return C0[0] + x, C0[1] + y, C0[2] + z


player = tuple(c - o for c, o in zip(C0, export.rot_pos(tuple(-a for a in export.PLAYER), K)))
print("player at", player)
print(cmd(f'execute positioned {player[0]} {player[1]} {player[2]} run function sorter:build {{cells:{N},dir:"{DIR}"}}'))
time.sleep(2)
L = seq.warehouse(N)
bad = []
for p, b in L.blocks.items():
    if "passed" not in cmd(f"execute if block {w(p)[0]} {w(p)[1]} {w(p)[2]} minecraft:{b.id}").lower():
        bad.append((p, b.block))
print("mismatches", len(bad), bad[:4])
put(*w((0, 0, 0)), 0, "cobblestone", 1)
put(*w((5, 0, 0)), 0, "dirt", 1)                     # cell 1, left half
for slot, (it, n) in enumerate([("cobblestone", 4), ("dirt", 3), ("stone", 2)]):
    put(*w((-3, 0, 0)), slot, it, n)
time.sleep(45)


def tally(*ps):
    c = {}
    for p in ps:
        for _, it, k, _ in items(*w(p)):
            c[it.split(":")[1]] = c.get(it.split(":")[1], 0) + k
    return c


print("cell0", tally((0, 0, 0), (-1, 0, 0)), "cell1", tally((6, 0, 0), (5, 0, 0)),
      "overflow", tally((N * 6 - 1, -4, 1)), "input", tally((-3, 0, 0)))
