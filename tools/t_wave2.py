"""Characterise the observer wave lift: items lifted and empty fires per pulse width."""
import re
import time
from mc import cmd, fill, setblock, put, items, freeze, unfreeze, step

X, Y, Z = 40, 20, 10          # column base (bottom dropper)
N = 4


def build():
    fill(X - 2, Y - 4, Z - 4, X + 2, Y + N + 1, Z + 2, "air")
    for k in range(N):
        setblock(X, Y + k, Z, "dropper[facing=up]")
        setblock(X, Y + k, Z - 1, "observer[facing=north]")
        setblock(X, Y + k, Z - 2, "observer[facing=down]")
    setblock(X, Y + N, Z, "chest")
    setblock(X, Y - 2, Z - 2, "stone")
    setblock(X, Y - 1, Z - 2, "repeater[facing=north]")


def state():
    return [sum(c for _, _, c, _ in items(X, Y + k, Z)) for k in range(N + 1)]


def triggered():
    out = []
    for k in range(N):
        s = cmd(f"execute if block {X} {Y + k} {Z} dropper[triggered=true]")
        out.append("passed" in s.lower())
    return out


def pulse(width, settle=40):
    freeze()
    time.sleep(0.2)
    fires = [0] * N
    prev = triggered()
    setblock(X, Y - 1, Z - 3, "redstone_block")
    for t in range(width + settle):
        if t == width:
            setblock(X, Y - 1, Z - 3, "air")
        step(1)
        cur = triggered()
        for k in range(N):
            if cur[k] and not prev[k]:
                fires[k] += 1
        prev = cur
    unfreeze()
    return fires


build()
for n_items in (1, 2):
    for width in (2, 4, 6, 8):
        for k in range(N + 1):
            cmd(f"data merge block {X} {Y + k} {Z} {{Items:[]}}")
        put(X, Y, Z, 0, "cobblestone", n_items)
        f = pulse(width)
        print(f"items={n_items} width={width}: after={state()} triggers={f}")
