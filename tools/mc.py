"""Helpers for building and inspecting redstone on a test server via RCON."""
import re

from rcon import Rcon

_r = None


def r():
    global _r
    if _r is None:
        _r = Rcon()
        _r.sock.settimeout(60)
    return _r


def cmd(c):
    out = r().cmd(c)
    return out


def setblock(x, y, z, block):
    out = cmd(f"setblock {x} {y} {z} {block}")
    if "Changed the block" not in out and "Could not set" not in out:
        raise RuntimeError(f"setblock {x} {y} {z} {block}: {out}")
    return out


def fill(x1, y1, z1, x2, y2, z2, block):
    return cmd(f"fill {x1} {y1} {z1} {x2} {y2} {z2} {block}")


def put(x, y, z, slot, item, count=1):
    out = cmd(f"item replace block {x} {y} {z} container.{slot} with {item} {count}")
    if "Replaced" not in out:
        raise RuntimeError(f"put {x} {y} {z} {slot} {item}: {out}")


def items(x, y, z):
    """Return list of (slot, id, count, extra) for a container."""
    out = cmd(f"data get block {x} {y} {z} Items")
    res = []
    for m in re.finditer(r"\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}", out.split(":", 1)[-1] if ":" in out else out):
        body = m.group(1)
        slot = re.search(r"Slot: (\d+)b", body)
        iid = re.search(r'id: "([^"]+)"', body)
        cnt = re.search(r"count: (\d+)", body)
        if iid:
            res.append((int(slot.group(1)) if slot else -1, iid.group(1),
                        int(cnt.group(1)) if cnt else 1, "components" in body))
    return res


def count(x, y, z, item_id=None):
    return sum(c for _, i, c, _ in items(x, y, z) if item_id is None or i == item_id)


def signal(x, y, z):
    out = cmd(f"data get block {x} {y} {z} OutputSignal")
    m = re.search(r"(-?\d+)$", out.strip())
    return int(m.group(1)) if m else None


def freeze():
    cmd("tick freeze")


def unfreeze():
    cmd("tick unfreeze")


def step(n=1):
    cmd(f"tick step {n}")
    import time
    time.sleep(n / 20 + 0.15)
