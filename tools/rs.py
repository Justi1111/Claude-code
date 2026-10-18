"""Block layout container plus a static redstone checker.

The checker reimplements the vanilla 26.3 rules that decide who powers whom
(dust connections and level flow, diodes, observers, torches, strong/weak
power through conductors, dropper quasi-connectivity).  Every emitter carries
a net name; every receiver declares which nets may reach it.  `check()`
reports any receiver that sees a different set, which catches cross-talk
before anything is built.
"""
import re

N, S, E, W, U, D = (0, 0, -1), (0, 0, 1), (1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0)
DIRS = {"north": N, "south": S, "east": E, "west": W, "up": U, "down": D}
HORIZ = (N, S, E, W)
ALL6 = (N, S, E, W, U, D)
CONDUCTORS = {"stone", "dropper", "dispenser", "cobblestone", "smooth_stone",
              "stone_bricks", "polished_andesite", "target"}
FULL_TOP = CONDUCTORS | {"glass", "observer", "redstone_block", "white_stained_glass"}
SIGNAL_SOURCES = {"repeater", "comparator", "observer", "redstone_torch",
                  "redstone_wall_torch", "redstone_block", "lever"}


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def neg(d):
    return (-d[0], -d[1], -d[2])


def parse(block):
    m = re.match(r"(?:minecraft:)?([a-z_]+)(?:\[(.*)\])?", block)
    props = {}
    if m.group(2):
        for kv in m.group(2).split(","):
            k, v = kv.split("=")
            props[k.strip()] = v.strip()
    return m.group(1), props


class Block:
    def __init__(self, block, net=None, expect=None, side=None, note=""):
        self.block = block
        self.id, self.props = parse(block)
        self.net = net            # net carried by this emitter (or dust)
        self.expect = expect      # nets allowed to power this receiver (main input)
        self.side = side          # nets allowed on a comparator side / repeater lock
        self.note = note

    def facing(self):
        return DIRS[self.props["facing"]] if "facing" in self.props else None


class Layout:
    def __init__(self):
        self.blocks = {}
        self.taps = {}

    # -- placement -------------------------------------------------------
    def put(self, pos, block, net=None, expect=None, side=None, note=""):
        if pos in self.blocks:
            old = self.blocks[pos]
            if old.block != block or old.net != net:
                raise ValueError(f"overlap at {pos}: {old.block}/{old.net} ({old.note}) vs {block}/{net} ({note})")
            return
        self.blocks[pos] = Block(block, net, expect, side, note)

    def solid(self, pos, note="support", block="stone"):
        if pos not in self.blocks:
            self.put(pos, block, note=note)

    def dust(self, pos, net, note="", support="stone"):
        self.put(pos, "redstone_wire", net=net, note=note)
        self.solid(add(pos, D), block=support)

    def rep(self, pos, facing, net, delay=1, src=None, note="", support="stone"):
        """Repeater whose INPUT is on the `facing` side; carries `net`."""
        self.put(pos, f"repeater[facing={facing},delay={delay}]", net=net,
                 expect={src or net}, side=set(), note=note)
        self.solid(add(pos, D), block=support)

    def comp(self, pos, facing, net, mode="compare", rear=None, side=None, note="", support="stone"):
        self.put(pos, f"comparator[facing={facing},mode={mode}]", net=net,
                 expect=rear if rear is not None else set(), side=side if side is not None else set(),
                 note=note)
        self.solid(add(pos, D), block=support)

    def obs(self, pos, facing, net, note=""):
        self.put(pos, f"observer[facing={facing}]", net=net, note=note)

    def get(self, pos):
        return self.blocks.get(pos)

    def id_at(self, pos):
        b = self.blocks.get(pos)
        return b.id if b else "air"

    def shifted(self, dx, dy=0, dz=0):
        out = Layout()
        for p, b in self.blocks.items():
            out.blocks[(p[0] + dx, p[1] + dy, p[2] + dz)] = b
        out.taps = {k: (v[0] + dx, v[1] + dy, v[2] + dz) for k, v in self.taps.items()}
        return out

    def merge(self, other):
        for p, b in other.blocks.items():
            if p in self.blocks and (self.blocks[p].block != b.block or self.blocks[p].net != b.net):
                raise ValueError(f"merge overlap at {p}: {self.blocks[p].block} vs {b.block}")
            self.blocks[p] = b
        self.taps.update(other.taps)


# -- checker ---------------------------------------------------------------
def _conductor(L, p):
    return L.id_at(p) in CONDUCTORS


def _wire(L, p):
    return L.id_at(p) == "redstone_wire"


def _survive_on(L, p):
    return L.id_at(p) in FULL_TOP or L.id_at(p) == "hopper"


def _should_connect(L, p, d):
    b = L.get(p)
    if b is None:
        return False
    if b.id == "redstone_wire":
        return True
    if d is None:
        return False
    if b.id == "repeater":
        f = b.facing()
        return f == d or f == neg(d)
    if b.id == "observer":
        return b.facing() == d
    return b.id in SIGNAL_SOURCES


def dust_connections(L, p):
    up_ok = not _conductor(L, add(p, U))
    conn = {}
    for d in HORIZ:
        rel = add(p, d)
        if up_ok and _survive_on(L, rel) and _wire(L, add(rel, U)):
            conn[d] = "up"
        elif _should_connect(L, rel, d) or (not _conductor(L, rel) and _wire(L, add(rel, D))):
            conn[d] = "side"
    ns = N in conn or S in conn
    ew = E in conn or W in conn
    if not conn:
        return conn  # a dot (setblock default) – flagged by the checker
    if not ns:
        conn.setdefault(E, "side")
        conn.setdefault(W, "side")
    if not ew:
        conn.setdefault(N, "side")
        conn.setdefault(S, "side")
    return conn


def wire_reads(L, p):
    """Dust positions whose level flows into dust p (vanilla evaluator)."""
    out = []
    above_cond = _conductor(L, add(p, U))
    for d in HORIZ:
        n = add(p, d)
        if _wire(L, n):
            out.append(n)
        if _conductor(L, n) and not above_cond:
            if _wire(L, add(n, U)):
                out.append(add(n, U))
        elif not _conductor(L, n):
            if _wire(L, add(n, D)):
                out.append(add(n, D))
    return out


class Checker:
    def __init__(self, L):
        self.L = L
        self.conn = {p: dust_connections(L, p) for p, b in L.blocks.items() if b.id == "redstone_wire"}
        self.dust_nets = self._dust_nets()

    # signal emitted by the block at q toward a neighbour located at q - d,
    # i.e. getSignal(q, d) where d points from the asking block to q.
    def _nets_signal(self, q, d, strong_only=False):
        L = self.L
        b = L.get(q)
        if b is None:
            return set()
        if b.id == "redstone_wire":
            if d == D:
                return set()
            if d == U or neg(d) in self.conn.get(q, {}):
                return set(self.dust_nets.get(q, set()))
            return set()
        if b.id in ("repeater", "comparator", "observer"):
            return {b.net} if b.facing() == d else set()
        if b.id == "redstone_torch":
            if strong_only:
                return {b.net} if d == D else set()
            return {b.net} if d != U else set()
        if b.id == "redstone_wall_torch":
            if strong_only:
                return {b.net} if d == D else set()
            return {b.net} if d != b.facing() else set()
        if b.id == "redstone_block":
            return set() if strong_only else {b.net or "tap"}
        if b.id == "lever":
            face = b.props.get("face", "wall")
            att = add(q, D if face == "floor" else U if face == "ceiling" else neg(b.facing()))
            if strong_only:
                return {b.net} if att == add(q, neg(d)) else set()
            return {b.net}
        if b.id in CONDUCTORS and not strong_only:
            return self._conductor_power(q)
        return set()

    def _conductor_power(self, c, for_dust=False):
        """getDirectSignalTo(c): nets strongly (or, unless for_dust, dust-) powering c."""
        out = set()
        for e in ALL6:
            n = add(c, e)
            b = self.L.get(n)
            if b is None:
                continue
            if b.id == "redstone_wire":
                if for_dust:
                    continue
                out |= self._nets_signal(n, e)
            else:
                out |= self._nets_signal(n, e, strong_only=True)
        return out

    def _dust_nets(self):
        L = self.L
        nets = {p: set() for p in self.conn}
        # direct (non-dust) sources: getBestNeighborSignal with dust muted
        for p in nets:
            for d in ALL6:
                q = add(p, d)
                b = L.get(q)
                if b is None or b.id == "redstone_wire":
                    continue
                if b.id in CONDUCTORS:
                    nets[p] |= self._conductor_power(q, for_dust=True)
                else:
                    nets[p] |= self._nets_signal(q, d, strong_only=False) if b.id != "redstone_block" else {b.net or "tap"}
        changed = True
        reads = {p: wire_reads(L, p) for p in nets}
        while changed:
            changed = False
            for p in nets:
                for q in reads[p]:
                    if not nets[q] <= nets[p]:
                        nets[p] |= nets[q]
                        changed = True
        return nets

    def strengths(self, weak=()):
        """Dust power assuming every source emits 15 (nets in `weak` are skipped)."""
        L = self.L
        power = {}
        for p in self.conn:
            best = 0
            for d in ALL6:
                q = add(p, d)
                b = L.get(q)
                if b is None or b.id == "redstone_wire":
                    continue
                nets = (self._conductor_power(q, for_dust=True) if b.id in CONDUCTORS
                        else self._nets_signal(q, d) if b.id != "redstone_block" else {"tap"})
                if nets - set(weak):
                    best = 15
            power[p] = best
        reads = {p: wire_reads(L, p) for p in self.conn}
        changed = True
        while changed:
            changed = False
            for p in power:
                for q in reads[p]:
                    if power[q] - 1 > power[p]:
                        power[p] = power[q] - 1
                        changed = True
        return power

    def mech_nets(self, m):
        """hasNeighborSignal(m)."""
        out = set()
        for d in ALL6:
            q = add(m, d)
            out |= self._nets_signal(q, d)
        return out

    def input_nets(self, b, pos):
        """Main input of a diode: getSignal(rear, facing) + dust level."""
        f = b.facing()
        rear = add(pos, f)
        out = self._nets_signal(rear, f)
        if _wire(self.L, rear):
            out |= self.dust_nets.get(rear, set())
        return out

    def side_nets(self, b, pos, diodes_only):
        f = b.facing()
        sides = [d for d in HORIZ if d != f and d != neg(f)]
        out = set()
        for d in sides:
            q = add(pos, d)
            sb = self.L.get(q)
            if sb is None:
                continue
            if sb.id == "redstone_block" and not diodes_only:
                out.add(sb.net or "tap")
            elif sb.id == "redstone_wire" and not diodes_only:
                out |= self.dust_nets.get(q, set())
            elif sb.id in ("repeater", "comparator") or (sb.id == "observer" and not diodes_only):
                out |= self._nets_signal(q, d, strong_only=True)
        return out

    def run(self):
        L = self.L
        errors = []
        for p, c in self.conn.items():
            if not c:
                errors.append(f"dust dot (no connections) at {p} [{L.blocks[p].note}]")
        for p, b in sorted(L.blocks.items()):
            got = None
            exp = b.expect
            if b.id == "redstone_wire":
                got, exp = self.dust_nets[p], ({b.net} if b.expect is None else b.expect)
            elif b.id in ("hopper", "dropper"):
                got = self.mech_nets(p)
                if b.id == "dropper":
                    got |= self.mech_nets(add(p, U))
                exp = b.expect if b.expect is not None else set()
            elif b.id in ("repeater", "comparator"):
                got = self.input_nets(b, p)
                side = self.side_nets(b, p, diodes_only=(b.id == "repeater"))
                if side != (b.side or set()):
                    errors.append(f"{b.id} side at {p} [{b.note}]: got {sorted(side)} expected {sorted(b.side or set())}")
            elif b.id in ("redstone_wall_torch", "redstone_torch"):
                att = add(p, neg(b.facing())) if b.id == "redstone_wall_torch" else add(p, D)
                got = self._nets_signal(att, neg(b.facing()) if b.id == "redstone_wall_torch" else D)
                exp = b.expect if b.expect is not None else set()
            if got is not None and exp is not None and got != exp:
                errors.append(f"{b.id} at {p} [{b.note}]: got {sorted(got)} expected {sorted(exp)}")
        return errors
