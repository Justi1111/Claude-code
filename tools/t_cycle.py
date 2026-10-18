import sys
from seqtest import *
import build
SPEC = {"G_inj": [(0, 4)], "G_probe": [(32, 36)], "G_pulls": [(38, 48)], "G_R": [(46, 66)],
        "G_L1": [(50, 66)], "G_mw": [(42, 50)]}


def case(label, sample, chest):
    clear_items()
    for i in range(3):
        build.load_blockers((O[0] + 6 * i, O[1], O[2]))
    for slot, (it, n) in enumerate(chest):
        put(*at("A"), slot, it, n)
    put(*at("F"), 0, sample, 1)
    print("=====", label)
    h = run(windows(SPEC, 1000), int(sys.argv[1]) if len(sys.argv) > 1 else 110,
            ["F", "E0", "E3", "T", "P", "R", "L", "M1", "M2", "M3", "A", "B", "t1", "t2"], log=False)
    prev = None
    for t, c in h:
        s = " ".join(f"{k}{v}" for k, v in c.items() if v)
        if s != prev:
            print(f"t={t:3d} {s}")
            prev = s
    tt = items(*at("T"))
    print("T contents:", tt)


case("MATCH", "cobblestone", [("dirt", 5), ("cobblestone", 10)])
case("NOMATCH", "stone", [("dirt", 5), ("cobblestone", 10)])
