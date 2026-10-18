"""One sorter cell (local coordinates, origin = storage chest half A).

x grows east, y up, z south.  The player walks on a floor at y = 0 north of
the chests (z < 0).  Cells repeat toward +x every PITCH blocks; a cell owns
x in [-1, PITCH - 2].

Item path
  F (feeder)  -> E0..E3 (entry lift) -> T (probe hopper under the chest)
  T -> P (extractor) -> R (router)
  R ejects west    -> M1..M3 (match lift) -> storage chest
  L steals from R  -> transit             -> next cell's F

Global phase lines (run along x, one repeater per cell):
  south: G_inj (F lock, also opens the E-gate window), G_pulls (P lock)
  north: G_probe (T lock), G_R (R lock), G_L1 (L lock), G_mw (M-gate window)
"""
from rs import Layout

PITCH = 6
NORTH_BUS_Z = -9          # G_probe y=-1, G_R y=-3, G_L1 y=-5
MW_BUS_Z = NORTH_BUS_Z     # G_mw y=-7 (stacked under the other north lines)
SOUTH_BUS_Z = 6           # G_pulls y=-2, G_inj y=-5
BUS_REP_X = 3             # every bus line gets its repeater here (facing west)

BLOCKER = 'stick[custom_name="§8sorter"]'


def core(L):
    p = L.put
    p((0, 0, 0), "chest[facing=north,type=right]", note="storage A")
    p((-1, 0, 0), "chest[facing=north,type=left]", note="storage B")
    p((0, -1, 0), "hopper[facing=east]", expect={"tau1", "G_probe", "Ewave", "Mwave"}, note="T probe")
    p((0, -2, 0), "hopper[facing=east]", expect={"tau1", "G_pulls", "Ewave", "Mwave"}, note="P extractor")
    p((0, -3, 0), "hopper[facing=west]", expect={"G_R", "Ewave", "Mwave"}, note="R router")
    p((0, -4, 0), "hopper[facing=east]", expect={"Llock", "Ewave"}, note="L no-match exit")
    for k, y in enumerate((-3, -2, -1)):
        p((-1, y, 0), "dropper[facing=up]", expect={"Mwave"}, note=f"M{k + 1}")
    for k, y in enumerate((-4, -3, -2)):
        p((0, y, 1), "dropper[facing=up]", expect={"Ewave"}, note=f"E{k}")
    p((0, -1, 1), "dropper[facing=north]", expect={"Ewave"}, note="E3 -> T")
    p((-1, -4, 1), "hopper[facing=east]", expect={"G_inj", "Ewave"}, note="F feeder")
    L.comp((1, -1, 0), "west", "Tcomp", rear=set(), side=set(), note="T comparator")
    p((1, -2, 0), "stone", note="PE: P lock block / T-comp support")
    for x in range(1, PITCH - 2):
        p((x, -4, 0), "hopper[facing=east]", expect=set(), note="transit")
    p((PITCH - 2, -4, 0), "hopper[facing=south]", expect=set(), note="transit")
    p((PITCH - 2, -4, 1), "hopper[facing=east]", expect=set(), note="transit -> next F")


def entry_side(L):
    """South: entry-lift wave, E-gate, F lock, P lock branch."""
    for y in (-4, -3, -2, -1):
        L.obs((0, y, 2), "south", "Ewave", "E wave O2")
    for y in range(-5, 0):
        L.obs((0, y, 3), "down", "Ewave", "E wave O1")
    L.rep((0, -6, 3), "south", "Etrig", src="Egate", note="E wave trigger")
    # E-gate: E0 content minus the inject window; E0 itself is strongly powered
    # while the wave fires it (after the window, so harmless).
    L.comp((1, -4, 1), "west", "Egate", mode="subtract", rear={"Ewave"}, side={"W_E"}, note="E-gate")
    L.rep((2, -4, 1), "west", "Egate", note="E-gate amp")
    for pos in ((3, -4, 1), (3, -4, 2), (3, -5, 3), (3, -6, 4), (2, -6, 4), (1, -6, 4), (0, -6, 4)):
        L.dust(pos, "Egate", "E route")
    L.solid((0, -5, 4), "insulator: E route vs G_inj branch")
    # F lock
    L.put((-1, -5, 1), "stone", note="FL: F lock block")
    L.rep((-1, -5, 2), "south", "G_inj", note="F lock")
    for z in range(3, SOUTH_BUS_Z):
        L.dust((-1, -5, z), "G_inj", "G_inj branch")
    # E-gate window = G_inj delayed
    L.rep((1, -4, 2), "south", "W_E", note="E-gate side")
    L.rep((1, -4, 3), "south", "W_E", delay=2, src="G_inj", note="E window delay")
    L.dust((1, -4, 4), "G_inj", "W_E branch")
    L.dust((1, -5, 5), "G_inj", "W_E branch")
    # P lock: G_pulls -> PE
    L.rep((1, -2, 1), "south", "G_pulls", note="P lock")
    for z in range(2, SOUTH_BUS_Z):
        L.dust((1, -2, z), "G_pulls", "G_pulls branch")


def control_side(L):
    """North: lock interfaces, presence signal pr, match-lift wave and M-gate."""
    p = L.put
    # match-lift wave (bottom of O1 column observes the trigger)
    for y in (-3, -2, -1):
        L.obs((-1, y, -1), "north", "Mwave", "M wave O2")
    for y in range(-5, 0):
        L.obs((-1, y, -2), "down", "Mwave", "M wave O1")
    L.rep((-1, -6, -2), "north", "Mtrig", src="Mgate", note="M wave trigger")
    # T lock
    p((0, -1, -1), "stone", note="B_T")
    L.rep((0, -1, -2), "north", "G_probe", note="T lock")
    # P lock torch tau1 = NOT pr
    p((0, -2, -1), "redstone_wall_torch[facing=west]", net="tau1", expect={"pr"}, note="tau1")
    p((1, -2, -1), "stone", note="A_tau (tau1 attach)")
    # R lock
    L.rep((0, -3, -1), "north", "G_R", note="R lock")
    # L lock: LB under L, fed by pr OR G_L1
    p((0, -5, 0), "stone", note="LB: L lock block")
    L.rep((0, -5, -1), "north", "Llock", src=None, note="L lock")
    L.blocks[(0, -5, -1)].expect = {"prL", "G_L1"}
    L.dust((0, -5, -2), "Ljct", "L junction")
    L.blocks[(0, -5, -2)].expect = {"prL", "G_L1"}
    # branches toward the north bus
    for z in range(-3, NORTH_BUS_Z, -1):
        L.dust((0, -1, z), "G_probe", "G_probe branch")
        L.dust((0, -3, z), "G_R", "G_R branch")
        if z < -3:
            L.dust((0, -5, z), "G_L1", "G_L1 branch")
    L.rep((0, -5, -3), "north", "G_L1", note="G_L1 one-way into L junction")
    L.dust((0, -3, -2), "G_R", "G_R branch")
    # pr: T-comp -> S_T -> two dust (threshold >= 2) -> repeaters
    p((2, -1, 0), "stone", note="S_T")
    L.dust((3, -1, 0), "Tcomp", "pr threshold")
    L.dust((3, -2, -1), "Tcomp", "pr threshold")
    L.rep((2, -2, -1), "east", "pr", src="Tcomp", note="pr -> A_tau")
    L.rep((3, -2, -2), "south", "pr2", src="Tcomp", note="pr copy")
    L.dust((3, -2, -3), "pr2", "pr copy")
    L.dust((2, -3, -3), "pr2", "pr copy")
    L.dust((2, -4, -2), "pr2", "pr copy")
    L.rep((1, -5, -2), "east", "prL", src="pr2", note="pr -> L junction")
    L.rep((2, -5, -3), "south", "prM", src="pr2", note="pr -> M-gate")
    L.dust((2, -5, -4), "prM", "pr to M-gate")
    L.dust((2, -6, -5), "prM", "pr to M-gate")
    # M-gate: pr AND (G_mw low).  The window is exactly the 8 gt in which a
    # match still holds pr, so the output pulse is 8 gt: two lift waves.
    L.comp((1, -7, -5), "east", "Mgate", mode="subtract", rear={"prM"}, side={"G_mw"}, note="M-gate")
    L.rep((1, -7, -6), "north", "G_mw", note="G_mw full strength into M-gate side")
    for z in range(-7, MW_BUS_Z, -1):
        L.dust((1, -7, z), "G_mw", "G_mw branch")
    L.rep((0, -7, -5), "east", "Mgate", note="M route delay (keeps lift pulses off R's push ticks)")
    for pos in ((-1, -7, -5), (-1, -7, -4), (-1, -6, -3)):
        L.dust(pos, "Mgate", "M route")


def buses(L, x0=-1, x1=PITCH - 2):
    """Bus segment of one cell: x in [x0, x1]; repeater at BUS_REP_X."""
    lines = [((-1, NORTH_BUS_Z), "G_probe"), ((-3, NORTH_BUS_Z), "G_R"), ((-5, NORTH_BUS_Z), "G_L1"),
             ((-7, MW_BUS_Z), "G_mw"), ((-2, SOUTH_BUS_Z), "G_pulls"), ((-5, SOUTH_BUS_Z), "G_inj")]
    for (y, z), net in lines:
        for x in range(x0, x1 + 1):
            if x == BUS_REP_X:
                L.rep((x, y, z), "west", net, note=f"{net} bus")
            else:
                L.dust((x, y, z), net, f"{net} bus")


def build_cell():
    L = Layout()
    core(L)
    entry_side(L)
    control_side(L)
    buses(L)
    return L


if __name__ == "__main__":
    from rs import Checker
    L = build_cell()
    print(len(L.blocks), "blocks")
    for e in Checker(L).run():
        print(e)


def chain(n):
    """n cells side by side, with redstone-block stand-ins driving the buses."""
    L = Layout()
    for i in range(n):
        L.merge(build_cell().shifted(i * PITCH))
    for (y, z), net in [((-1, NORTH_BUS_Z), "G_probe"), ((-3, NORTH_BUS_Z), "G_R"), ((-5, NORTH_BUS_Z), "G_L1"),
                        ((-7, MW_BUS_Z), "G_mw"), ((-2, SOUTH_BUS_Z), "G_pulls"), ((-5, SOUTH_BUS_Z), "G_inj")]:
        L.put((-2, y, z), "redstone_block", net=net, note=f"{net} driver")
    return L
