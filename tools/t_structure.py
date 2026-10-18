"""Vanilla install paths: structure pieces via /place template, and a structure block.

    python3 t_structure.py pieces   # west + 3 cells + east at the standard spot
    python3 t_structure.py block    # structure block in LOAD mode, 5-cell file
"""
import sys
import time

import build
import seq
from mc import cmd, put, items


def check_layout(n, c0):
    return build.verify(seq.warehouse(n), c0)


def quick_sort(n, c0, wait=60):
    """Pin cobblestone in cell 0 and dirt in the last cell, feed a few items."""
    w = lambda p: (c0[0] + p[0], c0[1] + p[1], c0[2] + p[2])
    for p in [(0, 0, 0), (-1, 0, 0), (6 * (n - 1), 0, 0), (6 * (n - 1) - 1, 0, 0), (6 * n - 1, -4, 1), (-3, 0, 0)]:
        cmd("data merge block %d %d %d {Items:[]}" % w(p))
    put(*w((0, 0, 0)), 0, "cobblestone", 1)
    put(*w((6 * (n - 1), 0, 0)), 0, "dirt", 1)
    for slot, (it, k) in enumerate([("cobblestone", 3), ("dirt", 2), ("stone", 1)]):
        put(*w((-3, 0, 0)), slot, it, k)
    time.sleep(wait)
    tally = lambda *ps: {i.split(":")[1]: c for p in ps for _, i, c, _ in items(*w(p))}
    return (tally((0, 0, 0), (-1, 0, 0)), tally((6 * (n - 1), 0, 0), (6 * (n - 1) - 1, 0, 0)),
            tally((6 * n - 1, -4, 1)))


def pieces():
    build.clear(-16, 8, -14, 24, 24, 12)
    cmd("place template minecraft:sorter_west -14 10 -10")
    for i in range(3):
        cmd(f"place template minecraft:sorter_cell {6 * i - 1} 10 -10")
    cmd("place template minecraft:sorter_east 17 10 -10")
    time.sleep(2)
    bad = check_layout(3, (0, 20, 0))
    print("pieces: mismatches", len(bad), bad[:3])
    print("pieces: sorted ->", quick_sort(3, (0, 20, 0), 70))


def structure_block():
    sb = (16, 50, -12)
    cmd(f'setblock {sb[0]} {sb[1]} {sb[2]} minecraft:structure_block[mode=load]'
        f'{{mode:"LOAD",name:"minecraft:sorter_5",posX:1,posY:-10,posZ:2,rotation:"NONE",mirror:"NONE",'
        f'integrity:1.0f,showboundingbox:1b}}')
    cmd(f"setblock {sb[0] - 1} {sb[1]} {sb[2]} minecraft:redstone_block")
    time.sleep(3)
    c0 = (sb[0] + 1 + 14, sb[1] - 10 + 10, sb[2] + 2 + 10)
    bad = check_layout(5, c0)
    print("structure block: mismatches", len(bad), bad[:3])
    print("structure block: sorted ->", quick_sort(5, c0, 90))


if __name__ == "__main__":
    {"pieces": pieces, "block": structure_block}[sys.argv[1] if len(sys.argv) > 1 else "pieces"]()
