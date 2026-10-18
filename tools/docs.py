"""Write docs/layers.md: layer-by-layer maps and material counts from the layout."""
import os
from collections import Counter

import cell
import seq
from rs import DIRS

ARROW = {(1, 0, 0): ">", (-1, 0, 0): "<", (0, 0, -1): "^", (0, 0, 1): "v", (0, 1, 0): "u", (0, -1, 0): "d"}
NAMES = {
    "redstone_wire": "редстоун-пыль", "repeater": "повторитель", "comparator": "компаратор",
    "observer": "наблюдатель", "redstone_torch": "редстоун-факел", "redstone_wall_torch": "редстоун-факел",
    "hopper": "воронка", "dropper": "выбрасыватель", "chest": "сундук", "stone": "любой цельный блок (камень)",
    "glass": "стекло (пол)", "lever": "рычаг", "ladder": "лестница",
}


def sym(b):
    f = b.facing()
    if b.id == "stone":
        return "##"
    if b.id == "glass":
        return ".."
    if b.id == "chest":
        return {"INPUT chest": "IN", "OVERFLOW chest": "OV"}.get(b.note, "Ch")
    if b.id == "hopper":
        return "H" + ARROW[f]
    if b.id == "dropper":
        return "D" + ARROW[f]
    if b.id == "observer":
        return "O" + ARROW[f]          # arrow = the side it watches
    if b.id == "repeater":
        return b.props["delay"] + ARROW[tuple(-c for c in f)]   # digit = delay, arrow = output
    if b.id == "comparator":
        return ("s" if b.props["mode"] == "subtract" else "c") + ARROW[tuple(-c for c in f)]
    if b.id == "redstone_wire":
        return "::"
    if b.id == "redstone_torch":
        return "t*"
    if b.id == "redstone_wall_torch":
        return "w" + ARROW[f]
    if b.id == "lever":
        return "Lv"
    if b.id == "ladder":
        return "Ld"
    return "??"


def layer_maps(L, xs, title, skip_floor=True):
    zs = range(min(p[2] for p in L.blocks), max(p[2] for p in L.blocks) + 1)
    ys = sorted({p[1] for p in L.blocks}, reverse=True)
    out = [f"### {title}", ""]
    for y in ys:
        rows = []
        for z in zs:
            row = "".join((sym(L.blocks[(x, y, z)]) if (x, y, z) in L.blocks and not
                           (skip_floor and L.blocks[(x, y, z)].note == "floor") else "  ") + " " for x in xs)
            rows.append(f"{z:4d} |{row}")
        if all(r.split("|")[1].strip() == "" for r in rows):
            continue
        out.append(f"Слой y = {y}" + ("  (уровень сундуков и пола)" if y == 0 else ""))
        out.append("```")
        out.append("   x |" + "".join(f"{x:<3d}" for x in xs))
        out.extend(rows)
        out.append("```")
        out.append("")
    return out


def materials(L, skip_floor=False):
    c = Counter()
    for b in L.blocks.values():
        if skip_floor and b.note == "floor":
            continue
        c[NAMES.get(b.id, b.id)] += 1
    return c


def main():
    root = os.path.join(os.path.dirname(__file__), "..", "docs")
    os.makedirs(root, exist_ok=True)
    one = cell.build_cell()
    west = seq.west_end()
    east = seq.east_end(1)
    lines = ["# Послойные схемы", "",
             "Сгенерировано скриптом `tools/docs.py` из той же раскладки, что и датапак.",
             "Север сверху (z растёт вниз), восток справа. Координаты локальные: сундук-ячейка A = (0, 0, 0).",
             "Склад растёт на восток с шагом 6 блоков; игрок ходит по полу y = 0 с северной стороны.", "",
             "Обозначения (каждая клетка — 2 символа):", "",
             "| знак | блок |", "|---|---|",
             "| `##` | любой цельный непрозрачный блок (опора/проводник) |",
             "| `::` | редстоун-пыль |",
             "| `1>` | повторитель: цифра — задержка (щелчков), стрелка — куда выходит сигнал |",
             "| `c>` / `s>` | компаратор в режиме сравнения / вычитания, стрелка — выход |",
             "| `O^` | наблюдатель, стрелка — сторона, за которой он следит (`d` — вниз) |",
             "| `H>` | воронка, стрелка — куда отдаёт (`d` — вниз) |",
             "| `Du` / `D^` | выбрасыватель, стрелка — куда выбрасывает (`u` — вверх) |",
             "| `w<` | настенный редстоун-факел, стрелка — от стены |",
             "| `t*` | стоячий редстоун-факел |",
             "| `Ch` `IN` `OV` | сундук склада / входной / переполнения |",
             "| `Lv` `Ld` | рычаг паузы / лестница |",
             "", "Стрелки: `>` восток, `<` запад, `^` север, `v` юг, `u` вверх, `d` вниз.", ""]
    lines += layer_maps(one, range(-1, cell.PITCH - 1), "Одна ячейка (x от -1 до 4; повторяется каждые 6 блоков)")
    lines += layer_maps(west, range(-14, -1), "Западный торец: секвенсор, входной сундук, рычаг паузы")
    lines += layer_maps(east, range(5, 9), "Восточный торец (для склада из 1 ячейки): сундук переполнения и лаз")
    lines += ["## Материалы", ""]
    for title, L in (("Одна ячейка", one), ("Западный торец", west), ("Восточный торец", east)):
        lines.append(f"**{title}:** " + ", ".join(f"{k} — {v}" for k, v in sorted(materials(L).items())))
        lines.append("")
    lines.append("Плюс в каждую ячейку: 22 палки, переименованные на наковальне в `sorter` "
                 "(в воронку-щуп T: слоты 2–5 по 6, 6, 5, 5 штук; слот 1 пустой). "
                 "Стеклянный пол сверху — по вкусу (около 18 блоков на каждый метр длины склада).")
    path = os.path.abspath(os.path.join(root, "layers.md"))
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    return path


if __name__ == "__main__":
    print(main())
