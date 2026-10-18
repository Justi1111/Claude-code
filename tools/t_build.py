import time
import seq, build
from mc import cmd, setblock, freeze, unfreeze
O = (0, 20, 0)


def rebuild(n=3):
    L = seq.warehouse(n)
    freeze()
    build.clear(-16, 8, -14, 6 * n + 6, 24, 12)
    build.place(L, O)
    unfreeze()
    time.sleep(1.0)
    for p, b in L.blocks.items():   # clear stale 'triggered' flags left by the build
        if b.id == "dropper":
            setblock(O[0] + p[0], O[1] + p[1], O[2] + p[2], b.block.replace("]", ",triggered=false]"))
    bad = build.verify(L, O)
    assert not bad, bad
    return L


if __name__ == "__main__":
    print(len(rebuild().blocks), "blocks placed")
