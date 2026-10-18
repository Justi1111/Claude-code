"""A completely full storage chest must not block the rest of the warehouse."""
from mc import cmd, put, items
from t_live import setup, wait, INPUT
from seqtest import at

setup([[], [("dirt", 1)], [("sand", 1)]], [])
for half in ("A", "B"):
    x, y, z = at(half, 0)
    stacks = ",".join(f'{{Slot:{i}b,id:"minecraft:cobblestone",count:64}}' for i in range(27))
    cmd(f"data merge block {x} {y} {z} {{Items:[{stacks}]}}")
for slot, (it, n) in enumerate([("cobblestone", 4), ("dirt", 3), ("sand", 3), ("stone", 1)]):
    put(*INPUT, slot, it, n)
s, dt = wait(150)
lift = sum(k for n in ("M1", "M2", "M3") for _, _, k, _ in items(*at(n, 0)))
print(round(dt), "s", s)
print("cobblestone waiting in cell 0 match lift:", lift)
ok = s["cell0"] == {"cobblestone": 54 * 64} and lift == 4 and s["cell1"] == {"dirt": 4} \
    and s["cell2"] == {"sand": 4} and s["overflow"] == {"stone": 1}
print("PASS full chest" if ok else "FAIL full chest")
