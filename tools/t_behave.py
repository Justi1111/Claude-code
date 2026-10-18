"""Behaviour tests on the live machine (redstone sequencer running in real time)."""
import time
from mc import cmd, put
from t_live import setup, summary, wait, INPUT, OVF
from seqtest import at


def feed(stacks):
    cmd(f"data merge block {INPUT[0]} {INPUT[1]} {INPUT[2]} {{Items:[]}}")
    for slot, (it, n) in enumerate(stacks):
        put(*INPUT, slot, it, n)


def check(label, cond):
    print(("PASS " if cond else "FAIL ") + label)
    return cond


ok = True
# 1. five pinned types in one chest, two-type chest pinned through the left half (B)
setup([[("cobblestone", 1), ("dirt", 1), ("sand", 1), ("gravel", 1), ("oak_planks", 1)],
       [], [("ender_pearl", 1)]], [])
put(*at("B", 1), 0, "andesite", 2)                       # pin via chest half B
feed([("cobblestone", 3), ("dirt", 3), ("sand", 3), ("gravel", 3), ("oak_planks", 3),
      ("andesite", 4), ("ender_pearl", 5), ("stone", 2), ("diamond_sword", 1),
      ('diamond[custom_name="shiny"]', 1), ("diamond", 1)])
s, dt = wait(300)
print(round(dt), "s", s)
c0, c1, c2 = s["cell0"], s["cell1"], s["cell2"]
ok &= check("5 types sorted into one chest", all(c0.get(k) == 4 for k in ("cobblestone", "dirt", "sand", "gravel", "oak_planks")) and len(c0) == 5)
ok &= check("pin through the left chest half", c1 == {"andesite": 6})
ok &= check("16-stack item sorted", c2 == {"ender_pearl": 6})
ok &= check("unpinned / unstackable items to overflow", s["overflow"] == {"stone": 2, "diamond_sword": 1, "diamond": 2})
ok &= check("nothing left inside the machine", not s["busy"])

# 2. pin release: take every sand out of cell 0, then sand goes to overflow
cmd(f"data merge block {at('A')[0]} {at('A')[1]} {at('A')[2]} {{Items:[]}}")
cmd(f"data merge block {at('B')[0]} {at('B')[1]} {at('B')[2]} {{Items:[]}}")
for slot, it in enumerate(("cobblestone", "dirt", "gravel", "oak_planks")):
    put(*at("A"), slot, it, 4)
cmd(f"data merge block {OVF[0]} {OVF[1]} {OVF[2]} {{Items:[]}}")
feed([("sand", 2), ("dirt", 1)])
s, dt = wait(200)
print(round(dt), "s", s)
ok &= check("released type no longer goes to its old chest", "sand" not in s["cell0"] and s["overflow"] == {"sand": 2})
ok &= check("other pins of that chest still work", s["cell0"].get("dirt") == 5)

# 3. new pin made by hand while the machine runs
put(*at("A", 2), 5, "sand", 1)
cmd(f"data merge block {OVF[0]} {OVF[1]} {OVF[2]} {{Items:[]}}")
feed([("sand", 3)])
s, dt = wait(200)
print(round(dt), "s", s)
ok &= check("hand-placed item pins a new type", s["cell2"].get("sand") == 4 and not s["overflow"])
print("ALL PASS" if ok else "SOME FAILED")
