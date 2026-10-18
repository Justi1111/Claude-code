"""Pause lever stops intake; `sorter:here` picks the direction from the player's facing."""
import time
from mc import cmd, put, items, setblock
from t_live import setup, wait, INPUT, O
setup([[("cobblestone", 1)], [], []], [])
setblock(O[0] - 4, O[1], O[2], "lever[face=floor,facing=north,powered=true]")
# a command-placed lever does not update blocks next to its support (a player's
# click does), so poke the input hopper once
setblock(O[0] - 3, O[1] - 1, O[2] - 1, "glass"); setblock(O[0] - 3, O[1] - 1, O[2] - 1, "air")
put(*INPUT, 0, "cobblestone", 3)
time.sleep(15)
held = sum(k for _, _, k, _ in items(*INPUT))
print("PASS pause holds the input" if held == 3 else f"FAIL pause: input has {held}")
setblock(O[0] - 4, O[1], O[2], "lever[face=floor,facing=north,powered=false]")
setblock(O[0] - 3, O[1] - 1, O[2] - 1, "glass"); setblock(O[0] - 3, O[1] - 1, O[2] - 1, "air")
s, dt = wait(120)
print("PASS resume" if s["cell0"].get("cobblestone") == 4 else f"FAIL resume {s}")
# direction dispatch: an armor stand looking south builds a south-facing row
cmd("summon minecraft:armor_stand 41 21 -3 {Tags:[\"dirtest\"],Rotation:[0f,0f],NoGravity:1b}")
cmd("execute positioned 40 20 0 run fill ~-8 ~-11 ~-15 ~11 ~1 ~14 minecraft:air")
print(cmd("execute as @e[tag=dirtest,limit=1] at @s run function sorter:here {cells:1}"))
time.sleep(1)
ok = "passed" in cmd("execute if block 40 20 0 minecraft:chest").lower() and \
     "passed" in cmd("execute if block 40 20 -1 minecraft:chest").lower()
print("PASS here(south)" if ok else "FAIL here(south)")
cmd("kill @e[tag=dirtest]")
