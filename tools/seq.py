"""West end of the warehouse: phase sequencer, input chest and feed.

Clock: a redstone-torch ring oscillator, half period 20 gt (torch 2 gt plus an
18 gt repeater loop), so X is a square wave with period 40 gt.  X runs to two
torch towers (north at z=-9, south at z=6); every tower level gives X inverted
once more and 2 gt later.  Each phase line has a module next to its bus end:
two repeater rows (A, B) whose delays select two copies of X, merged by dust
(OR) or by a subtract comparator, then one output repeater into the bus.

All times are game ticks (gt).  A line value is "driver on" (powered).
"""
from rs import Layout
import cell

PERIOD = 40
HALF = 20
PHI = 10                       # free global phase, chosen so every row delay fits

# M(t) = 1 for t mod 40 in [0, 20).  Line = OR(M@d1, M@d2) | M@d | M@d1 - M@d2
LINES = {
    #  name       y   zA  zB   tower stage delay s, op, (d1, d2)
    "G_probe": (-1, -9, -10, 8, "or", (12, 36)),
    "G_R":     (-3, -9, None, 26, "one", (26,)),
    "G_L1":    (-5, -9, -10, 4, "sub", (10, 26)),
    "G_mw":    (-7, -9, -10, 22, "or", (22, 10)),
    "G_pulls": (-2, 6, 7, 8, "or", (18, 8)),
    "G_inj":   (-5, 6, 7, 4, "or", (20, 4)),
}
SLOTS = (-8, -7, -6, -5, -4)
TOWER_X = -10


def row_delays(total_gt):
    """Repeater ticks for the five row slots (0 = solid block), summing to total_gt."""
    ticks = total_gt // 2
    assert total_gt % 2 == 0 and 5 <= ticks <= 20 or ticks in (4,), total_gt
    if ticks >= 5:
        base, extra = divmod(ticks, 5)
        out = [base] * 5
        for i in range(extra):
            out[i] += 1
        assert max(out) <= 4
        return out
    return [1, 0, 1, 1, 1]       # 4 ticks: rep, block, rep, rep, rep


def module_delays(name):
    y, za, zb, s, op, ds = LINES[name]
    if op == "or":
        return [(d + PHI - s - 2) % PERIOD or PERIOD for d in ds]
    if op == "one":
        return [(ds[0] + PHI - s - 2) % PERIOD or PERIOD]
    return [(d + PHI - s - 4) % PERIOD or PERIOD for d in ds]


def tower(L, z, top_y):
    """Torch tower at (TOWER_X, *, z): base block y=-9, torches at even y."""
    L.put((TOWER_X, -9, z), "stone", note="tower base")
    y = -8
    k = 1
    while y <= top_y:
        L.put((TOWER_X, y, z), "redstone_torch", net=f"tower{z}_{k}", note=f"tower torch stage {k}")
        L.blocks[(TOWER_X, y, z)].expect = {f"tower{z}_{k - 1}"} if k > 1 else {"Xn" if z < 0 else "Xs"}
        if y + 1 <= top_y:
            L.put((TOWER_X, y + 1, z), "stone", note="tower block")
        y += 2
        k += 1


def module(L, name):
    y, za, zb, s, op, ds = LINES[name]
    stage = {-7: 1, -5: 2, -3: 3, -1: 4, -2: 4}[y]
    src = f"tower{za}_{stage}"
    delays = module_delays(name)
    rows = [(za, delays[0], "A")] + ([(zb, delays[1], "B")] if zb is not None else [])
    for z, total, tag in rows:
        L.dust((-9, y, z), src, f"{name} S")
        prev = src
        for x, d in zip(SLOTS, row_delays(total)):
            net = f"{name}{tag}{x}"
            if d:
                L.rep((x, y, z), "west", net, delay=d, src=prev, note=f"{name} row {tag}")
                prev = net
            else:
                L.put((x, y, z), "stone", note=f"{name} row {tag} relay")
    out_net = name
    if op == "or":
        L.dust((-3, y, za), name + "m", f"{name} OR")
        L.dust((-3, y, zb), name + "m", f"{name} OR")
        for p in ((-3, y, za), (-3, y, zb)):
            L.blocks[p].expect = {f"{name}A-4", f"{name}B-4"}
        L.rep((-2, y, za), "west", out_net, src=name + "m", note=f"{name} out")
        L.blocks[(-2, y, za)].expect = {f"{name}A-4", f"{name}B-4"}
    elif op == "sub":
        L.dust((-3, y, zb), name + "B-4", f"{name} side")
        L.comp((-3, y, za), "west", name + "w", mode="subtract", rear={f"{name}A-4"}, side={f"{name}B-4"},
               note=f"{name} window")
        L.rep((-2, y, za), "west", out_net, src=name + "w", note=f"{name} out")
    else:
        L.dust((-3, y, za), name + "A-4", f"{name} pass")
        L.rep((-2, y, za), "west", out_net, src=name + "A-4", note=f"{name} out")
    # the S dust of the tower level also feeds row B through the dust pair
    if zb is not None:
        for z in (za, zb):
            L.blocks[(-9, y, z)].expect = {src}


def oscillator(L):
    """Torch ring at y=-9 around z=0; X leaves on the dust junction (-9,-9,0)."""
    L.put((-14, -9, 0), "stone", note="B0 oscillator torch block")
    L.put((-13, -9, 0), "redstone_wall_torch[facing=east]", net="X0", expect={"osc4"}, note="T0")
    L.rep((-12, -9, 0), "west", "osc1", delay=4, src="X0", note="osc")
    L.rep((-11, -9, 0), "west", "X", delay=3, src="osc1", note="osc")
    L.dust((-10, -9, 0), "X", "X junction")
    L.dust((-10, -9, -1), "X", "osc return")
    L.rep((-11, -9, -1), "east", "osc3", src="X", note="osc")
    L.dust((-12, -9, -1), "osc3", "osc return")
    L.dust((-12, -9, -2), "osc3", "osc return")
    L.dust((-13, -9, -2), "osc3", "osc return")
    L.dust((-14, -9, -2), "osc3", "osc return")
    L.rep((-14, -9, -1), "north", "osc4", src="osc3", note="osc -> B0")
    # X to both tower bases along x=-9; equal 2 gt repeaters into each base
    L.dust((-9, -9, 0), "X", "X line")
    for z in range(-1, -8, -1):
        L.dust((-9, -9, z), "X", "X line north")
    L.dust((-10, -9, -7), "X", "X line north")
    L.rep((-10, -9, -8), "south", "Xn", src="X", note="X -> north tower base")
    for z in range(1, 5):
        L.dust((-9, -9, z), "X", "X line south")
    L.dust((-10, -9, 4), "X", "X line south")
    L.rep((-10, -9, 5), "north", "Xs", src="X", note="X -> south tower base")


def feed(L):
    """Input chest at the west end of the chest row, hopper chain to cell 0's F."""
    L.put((-3, 0, 0), "chest[facing=north]", note="INPUT chest")
    L.put((-4, -1, 0), "stone", note="pause lever block")
    L.put((-4, 0, 0), "lever[face=floor,facing=north,powered=false]", net="PAUSE", note="PAUSE lever")
    L.put((-3, -1, 0), "hopper[facing=down]", expect={"PAUSE"}, note="input feed (pause lever locks it)")
    for y in (-2, -3):
        L.put((-3, y, 0), "hopper[facing=down]", expect=set(), note="input feed")
    L.put((-3, -4, 0), "hopper[facing=east]", expect=set(), note="input feed")
    L.put((-2, -4, 0), "hopper[facing=south]", expect=set(), note="input feed")
    L.put((-2, -4, 1), "hopper[facing=east]", expect=set(), note="input feed -> F")


def west_end():
    L = Layout()
    oscillator(L)
    tower(L, -9, -1)
    tower(L, 6, -2)
    for name in LINES:
        module(L, name)
    feed(L)
    return L


def east_end(n):
    """Overflow chest fed by the last cell's transit, reached by a ladder shaft."""
    L = Layout()
    x = n * cell.PITCH - 1
    L.put((x, -4, 1), "chest[facing=east]", note="OVERFLOW chest")
    for y in range(-3, 1):
        L.put((x + 2, y, 1), "stone", note="ladder wall")
        if y < 0:
            L.put((x + 1, y, 1), "ladder[facing=west]", note="ladder to overflow")
    L.taps["shaft"] = [(x, 0, 1), (x + 1, 0, 1)]
    return L


def floor(L, block="glass"):
    """Walkable floor at y = 0 over the whole machine, leaving the shaft open."""
    xs = [p[0] for p in L.blocks]
    zs = [p[2] for p in L.blocks]
    keep_open = set(L.taps.get("shaft", []))
    for x in range(min(xs), max(xs) + 1):
        for z in range(min(zs), max(zs) + 1):
            if (x, 0, z) not in L.blocks and (x, 0, z) not in keep_open:
                L.put((x, 0, z), block, note="floor")


def warehouse(n, with_floor=True):
    L = Layout()
    for i in range(n):
        L.merge(cell.build_cell().shifted(i * cell.PITCH))
    L.merge(west_end())
    L.merge(east_end(n))
    if with_floor:
        floor(L)
    return L


if __name__ == "__main__":
    for n in LINES:
        print(n, module_delays(n), [row_delays(d) for d in module_delays(n)])
