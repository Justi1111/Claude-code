"""Generate the `sorter` datapack (mcfunction builder) from the layout.

    /function sorter:build {cells:8, dir:"east"}

Run it standing on the spot that becomes the walkway in front of the input
chest.  The row of storage chests grows in direction `dir` (east, south, west,
north); the chests are on your right-hand side.  Every part clears its own
volume first.
"""
import json
import os
import shutil

import cell
import nbt
import seq
from rs import Layout

DIRS = ["east", "south", "west", "north"]          # clockwise quarter turns from east
CW = {"north": "east", "east": "south", "south": "west", "west": "north"}
PLAYER = (-3, 1, -1)                               # player's feet, cell-0 frame
BLOCKER = {"id": "minecraft:stick", "name": "sorter"}
PACK_FORMAT = 121                                  # Minecraft Java 26.3


def rot_pos(p, k):
    x, y, z = p
    for _ in range(k):
        x, z = -z, x
    return x, y, z


def rot_block(block, k):
    if "[" not in block:
        return block
    head, props = block[:-1].split("[", 1)
    out = []
    for kv in props.split(","):
        key, val = kv.split("=")
        if key == "facing" and val in CW:
            for _ in range(k):
                val = CW[val]
        out.append(f"{key}={val}")
    return f"{head}[{','.join(out)}]"


def blocker_nbt():
    parts = []
    for slot, n in ((1, 6), (2, 6), (3, 5), (4, 5)):
        parts.append(f'{{Slot:{slot}b,id:"{BLOCKER["id"]}",count:{n},'
                     f'components:{{"minecraft:custom_name":"{BLOCKER["name"]}"}}}}')
    return "{Items:[" + ",".join(parts) + "]}"


ORDER = {"stone": 0, "glass": 0, "chest": 0, "ladder": 0, "hopper": 1, "dropper": 1,
         "comparator": 2, "repeater": 2, "redstone_wall_torch": 2, "redstone_torch": 2,
         "lever": 2, "observer": 3, "redstone_wire": 4}


def obs_key(item):
    (x, y, z), b = item
    # observers: the vertical (facing down) chains bottom-up first, then the side
    # observers, so placing one never changes the block another one watches
    if b.id == "observer":
        return (ORDER["observer"], 0 if "facing=down" in b.block else 1, y)
    return (ORDER.get(b.id, 0), 0, 0)


def setblocks(L, k, origin=(0, 0, 0)):
    """setblock commands for layout L, relative to `origin` (same frame), rotated k."""
    lines = []
    for p, b in sorted(L.blocks.items(), key=obs_key):
        rel = tuple(a - o for a, o in zip(p, origin))
        x, y, z = rot_pos(rel, k)
        block = rot_block(b.block, k)
        if b.note == "T probe":
            block += blocker_nbt()
        lines.append(f"setblock ~{x} ~{y} ~{z} minecraft:{block}")
    return lines


def clear_box(L, k, origin=(0, 0, 0)):
    pts = [rot_pos(tuple(a - o for a, o in zip(p, origin)), k) for p in L.blocks]
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    # strict: no shape updates while clearing, so old redstone does not drop as items
    return f"fill ~{lo[0]} ~{lo[1]} ~{lo[2]} ~{hi[0]} ~{hi[1]} ~{hi[2]} minecraft:air strict"


def cell_part():
    """One cell plus its strip of floor (x in [-1, PITCH-2])."""
    L = cell.build_cell()
    full = seq.warehouse(2)
    for p, b in full.blocks.items():
        if b.note == "floor" and -1 <= p[0] <= cell.PITCH - 2:
            L.blocks.setdefault(p, b)
    return L


def west_part():
    L = seq.west_end()
    full = seq.warehouse(2)
    for p, b in full.blocks.items():
        if b.note == "floor" and p[0] < -1:
            L.blocks.setdefault(p, b)
    return L


def east_part():
    """Overflow end, in the frame of the (virtual) cell after the last one."""
    n = 1
    L = seq.east_end(n)
    full = seq.warehouse(n)
    for p, b in full.blocks.items():
        if b.note == "floor" and p[0] >= n * cell.PITCH - 1:
            L.blocks.setdefault(p, b)
    out = Layout()
    out.blocks = {(p[0] - n * cell.PITCH, p[1], p[2]): b for p, b in L.blocks.items()}
    return out


DATA_VERSION = 5023                                # world_version of Minecraft Java 26.3
BOX_Y = (-10, 0)                                   # every structure piece shares this y/z box
BOX_Z = (-10, 7)


def _state(block, layout, pos):
    from rs import parse, dust_connections, DIRS as RDIRS
    bid, props = parse(block)
    props = dict(props)
    defaults = {"repeater": {"locked": "false", "powered": "false"},
                "comparator": {"powered": "false"}, "observer": {"powered": "false"},
                "hopper": {"enabled": "true"}, "dropper": {"triggered": "false"},
                "chest": {"type": "single", "waterlogged": "false"}, "ladder": {"waterlogged": "false"},
                "redstone_torch": {"lit": "true"}, "redstone_wall_torch": {"lit": "true"},
                "lever": {"powered": "false"}}
    for k, v in defaults.get(bid, {}).items():
        props.setdefault(k, v)
    if bid == "redstone_wire":
        conn = dust_connections(layout, pos)
        names = {(0, 0, -1): "north", (0, 0, 1): "south", (1, 0, 0): "east", (-1, 0, 0): "west"}
        for d, n in names.items():
            props[n] = conn.get(d, "none")
        props["power"] = "0"
    # 26.3 palette entries use lower-case keys (older files are upgraded by the data fixer)
    return {"id": "minecraft:" + bid, "properties": props} if props else {"id": "minecraft:" + bid}


def structure(L, x0, x1, context=None):
    """Structure template of L's blocks with x in [x0, x1] and the common y/z box.

    Empty positions become air so loading clears whatever was there.
    `context` (a bigger layout) is used for dust shapes at the piece edges."""
    ctx = context or L
    palette, index, blocks = [], {}, []
    for x in range(x0, x1 + 1):
        for y in range(BOX_Y[0], BOX_Y[1] + 1):
            for z in range(BOX_Z[0], BOX_Z[1] + 1):
                b = L.blocks.get((x, y, z))
                st = _state(b.block, ctx, (x, y, z)) if b else {"id": "minecraft:air"}
                key = repr(st)
                if key not in index:
                    index[key] = len(palette)
                    palette.append(st)
                entry = {"pos": [x - x0, y - BOX_Y[0], z - BOX_Z[0]], "state": index[key]}
                if b is not None and b.note == "T probe":
                    entry["nbt"] = {"id": "minecraft:hopper", "Items": [
                        {"Slot": nbt.Byte(slot), "id": BLOCKER["id"], "count": n,
                         "components": {"minecraft:custom_name": BLOCKER["name"]}}
                        for slot, n in ((1, 6), (2, 6), (3, 5), (4, 5))]}
                blocks.append(entry)
    return {"DataVersion": DATA_VERSION,
            "size": [x1 - x0 + 1, BOX_Y[1] - BOX_Y[0] + 1, BOX_Z[1] - BOX_Z[0] + 1],
            "palette": palette, "blocks": blocks, "entities": []}


def write_structures(root):
    """sorter_1..sorter_5 (complete warehouses) and sorter_west / _cell / _east pieces."""
    os.makedirs(root, exist_ok=True)
    out = []
    for n in range(1, 6):
        L = seq.warehouse(n)
        x1 = max(p[0] for p in L.blocks)
        assert x1 + 15 <= 48, n
        path = os.path.join(root, f"sorter_{n}.nbt")
        nbt.write(path, structure(L, -14, x1))
        out.append(path)
    big = seq.warehouse(3)
    pieces = {"sorter_west": (west_part(), -14, -2, big),
              "sorter_cell": (cell_part(), -1, cell.PITCH - 2, big.shifted(-cell.PITCH)),
              "sorter_east": (east_part(), -1, 2, big.shifted(-3 * cell.PITCH))}
    for name, (L, x0, x1, ctx) in pieces.items():
        path = os.path.join(root, name + ".nbt")
        nbt.write(path, structure(L, x0, x1, ctx))
        out.append(path)
    return out


def write_pack(root):
    if os.path.exists(root):
        shutil.rmtree(root)
    fn = os.path.join(root, "data", "sorter", "function")
    os.makedirs(fn)
    with open(os.path.join(root, "pack.mcmeta"), "w") as f:
        json.dump({"pack": {"description": "Auto-sorting warehouse with pinned chests (vanilla redstone)",
                            "min_format": PACK_FORMAT, "max_format": PACK_FORMAT}}, f, indent=2)

    def put(name, lines):
        path = os.path.join(fn, name + ".mcfunction")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write("\n".join(lines) + "\n")

    put("build", ["# /function sorter:build {cells:8, dir:\"east\"}",
                  "$function sorter:$(dir)/build {cells:$(cells)}"])
    put("here", ["# /function sorter:here {cells:8}  -- direction = where you look",
                 "$execute if entity @s[y_rotation=-135..-45] run function sorter:east/build {cells:$(cells)}",
                 "$execute if entity @s[y_rotation=-45..45] run function sorter:south/build {cells:$(cells)}",
                 "$execute if entity @s[y_rotation=45..135] run function sorter:west/build {cells:$(cells)}",
                 "$execute unless entity @s[y_rotation=-135..135] run function sorter:north/build {cells:$(cells)}"])
    wpart, cpart, epart = west_part(), cell_part(), east_part()
    for k, d in enumerate(DIRS):
        c0 = rot_pos(tuple(-a for a in PLAYER), k)          # cell-0 origin seen from the player
        step = rot_pos((cell.PITCH, 0, 0), k)
        at_c0 = f"~{c0[0]} ~{c0[1]} ~{c0[2]}"
        nxt = f"~{step[0]} ~{step[1]} ~{step[2]}"
        put(f"{d}/build", [
            "scoreboard objectives add sorter_build dummy",
            "$scoreboard players set #left sorter_build $(cells)",
            f"execute positioned {at_c0} run function sorter:{d}/west_end",
            f"execute positioned {at_c0} run function sorter:{d}/cells",
            'tellraw @s {"text":"Склад построен. Кладите предметы во входной сундук; тип закрепляется, если положить его в любой сундук склада.","color":"green"}',
        ])
        put(f"{d}/cells", [
            f"function sorter:{d}/cell",
            "scoreboard players remove #left sorter_build 1",
            # the end piece is decided before recursing: calls run depth-first, so a
            # test placed after the recursive call would see the final count
            f"execute if score #left sorter_build matches ..0 positioned {nxt} run function sorter:{d}/east_end",
            f"execute if score #left sorter_build matches 1.. positioned {nxt} run function sorter:{d}/cells",
        ])
        put(f"{d}/cell", [clear_box(cpart, k)] + setblocks(cpart, k))
        put(f"{d}/west_end", [clear_box(wpart, k)] + setblocks(wpart, k))
        put(f"{d}/east_end", [clear_box(epart, k)] + setblocks(epart, k))
    return root


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "datapack", "sorter")
    print(write_pack(os.path.abspath(out)))
    here = os.path.dirname(os.path.abspath(__file__))
    for p in write_structures(os.path.join(here, "..", "structures")):
        print(os.path.abspath(p))
