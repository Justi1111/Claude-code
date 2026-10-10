"""Build CLIPS.md (curated, by chapter) and clips_index.tsv (everything) from clip metadata + transcripts.

usage: python -I build_catalog.py <scratchpad> <library_dir> <out_md> <out_tsv>
"""
import glob
import json
import os
import re
import sys

SP, LIB, OUT_MD, OUT_TSV = sys.argv[1:5]

CHAPTERS = [
    ("00_2017_start_and_ban", "2017 — начало, бан и «I'm Not a Hacker»", "20160101", "20171231"),
    ("01_2018_mouse_to_tablet", "2018 — мышь, пол, переход на планшет, OWC 2018", "20180101", "20181124"),
    ("02_road_to_1", "Конец 2018 – начало 2019 — путь к #1", "20181125", "20190210"),
    ("03_number_one_2019-02-11", "11.02.2019 и дальше — #1 в мире", "20190211", "20191130"),
    ("04_owc2019", "Декабрь 2019 — OWC 2019 (серебро, 0:7)", "20191201", "20200110"),
    ("05_2020_2021_tech_and_1kpp", "2020–2021 — техника, 1000pp, трофеи", "20200111", "20211031"),
    ("06_owc2021_and_army", "Ноябрь 2021 – 2022 — OWC 2021, уход в армию", "20211101", "20230520"),
    ("07_return_2023", "Май–октябрь 2023 — возвращение", "20230521", "20231031"),
    ("08_owc2023", "Ноябрь–декабрь 2023 — OWC 2023 (6:7)", "20231101", "20231231"),
    ("09_owc2024", "2024 — год трофеев и чемпионство", "20240101", "20241231"),
    ("10_2025_2026", "2025–2026 — «дядя osu!»", "20250101", "20271231"),
]
HALLU = re.compile(r"thank(s)? (you )?for watching|subtitles by|ご視聴|字幕|MBC 뉴스|시청해주셔서|구독과 좋아요|amara\.org|請不吝|點贊|订阅", re.I)


def load_jsonl(p):
    return [json.loads(l) for l in open(p)] if os.path.exists(p) else []


ft = load_jsonl(os.path.join(SP, "lists/ft_all.jsonl"))
for r in ft:
    r["channel"] = "flyingtuna"
os_ = load_jsonl(os.path.join(SP, "lists/osulive_sel.jsonl"))
for r in os_:
    r["channel"] = "osulive"
rows, seen = [], set()
for r in ft + os_:
    if r["id"] in seen:
        continue
    seen.add(r["id"])
    rows.append(r)

# picks: id -> (chapter, slug)
picks = {}
for p in glob.glob(os.path.join(SP, "lists/picks*.tsv")):
    for line in open(p):
        if line.strip() and not line.startswith("#"):
            c, i, s = line.rstrip("\n").split("\t")[:3]
            picks[i] = (c, s)
# library files: match by date+slug
libfiles = {}
for f in glob.glob(os.path.join(LIB, "*", "*.mp4")):
    libfiles[os.path.relpath(f, LIB)] = f


def libname(r):
    if r["id"] not in picks:
        return ""
    c, s = picks[r["id"]]
    d = r["upload_date"]
    name = f"{c}/{d[:4]}-{d[4:6]}-{d[6:]}_{re.sub(r'[^a-z0-9]+', '_', s.lower()).strip('_')}.mp4"
    return name if name in libfiles else ""


def transcript(cid):
    for d, kind in ((os.path.join(SP, "tr_md"), "md"), (os.path.join(SP, "tr_ft"), "sm"), (os.path.join(SP, "tr_os"), "sm")):
        p = os.path.join(d, cid + ".json")
        if os.path.exists(p):
            t = json.load(open(p))
            out = []
            for s in t.get("segments", []):
                if s.get("nsp", 0) > 0.6 or s.get("lp", 0) < -1.1:
                    continue
                txt = s["t"].strip()
                if not txt or HALLU.search(txt):
                    continue
                txt = re.sub(r"\b(\S+)( \1\b){3,}", lambda m: f"{m.group(1)} ×{len(m.group(0).split())}", txt)
                txt = re.sub(r"(.)\1{6,}", lambda m: m.group(1) * 4 + "…", txt)
                if len(txt) > 160:
                    txt = txt[:157] + "…"
                out.append(f"[{s['s']:.0f}s] {txt}")
            return t.get("lang") or "", kind, out
    return "", "", None


tsv = open(OUT_TSV, "w")
tsv.write("date\tviews\tduration_s\tchannel\ttitle\turl\tlang\tmodel\tlibrary_file\ttranscript\n")
by_ch = {c[0]: [] for c in CHAPTERS}
for r in sorted(rows, key=lambda r: r.get("timestamp") or 0):
    lang, kind, tr = transcript(r["id"])
    lf = libname(r)
    tsv.write("\t".join([r["upload_date"], str(r.get("view_count") or 0), str(int(r.get("duration") or 0)), r["channel"],
                         (r.get("title") or "").replace("\t", " "), r.get("url") or "", lang, kind, lf,
                         " | ".join(tr or []).replace("\t", " ")]) + "\n")
    ch = picks[r["id"]][0] if r["id"] in picks else None
    if ch is None or ch == "11_osulive_broadcast":
        if r["channel"] == "osulive" and r["id"] not in picks:
            continue
        if ch is None:
            for c in CHAPTERS:
                if c[2] <= r["upload_date"] <= c[3]:
                    ch = c[0]
                    break
    by_ch.setdefault(ch, []).append((r, lang, kind, tr, lf))
tsv.close()

md = ["# Каталог клипов FlyingTuna\n",
      "★ — клип скачан в исходном качестве и лежит в библиотеке; путь указан относительно `osu-edit/clips/ft_library/`.",
      "Расшифровка автоматическая (Whisper): «md» — модель medium, точнее; «sm» — small, черновая. Корейский в «sm» часто с ошибками.",
      "Всё, включая клипы без пометок, есть в `clips_index.tsv`: 1020 клипов с канала + выборка клипов трансляции osu!.\n"]
vod_tsv = os.path.join(os.path.dirname(OUT_MD), "library", "library.tsv")
if os.path.exists(vod_tsv):
    md.append("\n## Куски из сохранившихся записей стримов (VOD)\n")
    md.append("Этого нет среди клипов: вырезано из полных записей, которые ещё лежат у него на Twitch.\n")
    for line in open(vod_tsv):
        f = line.rstrip("\n").split("\t")
        if len(f) >= 6 and f[3] and not line.startswith("#"):
            md.append(f"- ★ `{f[0]}/{f[1]}` — {f[5]} · [{f[2]}]({f[2]}) · {f[3]}–{f[4]}")
titles = {c[0]: c[1] for c in CHAPTERS}
titles["11_osulive_broadcast"] = "Трансляция osu! (osulive) — комментаторы"
for ch in [c[0] for c in CHAPTERS] + ["11_osulive_broadcast"]:
    items = by_ch.get(ch, [])
    if not items:
        continue
    picked = [x for x in items if x[0]["id"] in picks]
    rest = [x for x in items if x[0]["id"] not in picks]
    speechy = [x for x in rest if x[3] and sum(len(s) for s in x[3]) > 60]
    notable = sorted(rest, key=lambda x: -(x[0].get("view_count") or 0))[:12]
    extra = []
    for x in notable + sorted(speechy, key=lambda x: -(x[0].get("view_count") or 0))[:10]:
        if x not in extra:
            extra.append(x)
    md.append(f"\n## {titles.get(ch, ch)}\n")
    md.append(f"Всего клипов в периоде: {len(items)}. Ниже: ★ отобранные, затем самые просматриваемые и разговорные.\n")
    for (r, lang, kind, tr, lf) in sorted(picked, key=lambda x: x[0].get("timestamp") or 0) + sorted(extra, key=lambda x: x[0].get("timestamp") or 0):
        d = r["upload_date"]
        star = "★ " if r["id"] in picks else ""
        views = f"{r.get('view_count') or 0:,}".replace(",", " ")
        head = (f"- {star}**{d[:4]}-{d[4:6]}-{d[6:]}** · {views} просм. · {int(r.get('duration') or 0)} с · "
                f"«{(r.get('title') or '').strip()}» · [ссылка]({r.get('url')})")
        md.append(head)
        if lf:
            md.append(f"  - файл: `{lf}`")
        if tr:
            md.append(f"  - {lang}/{kind}: " + " ".join(tr)[:600])
open(OUT_MD, "w").write("\n".join(md) + "\n")
print("chapters:", {k: len(v) for k, v in by_ch.items()})
