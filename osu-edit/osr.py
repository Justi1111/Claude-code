"""Minimal .osr (osu! replay) parser."""
import lzma
import struct
import sys

MODS = ["NF", "EZ", "TD", "HD", "HR", "SD", "DT", "RX", "HT", "NC", "FL", "AU", "SO", "AP", "PF"]


class Reader:
    def __init__(self, data):
        self.d, self.p = data, 0

    def byte(self):
        v = self.d[self.p]
        self.p += 1
        return v

    def short(self):
        v = struct.unpack_from("<H", self.d, self.p)[0]
        self.p += 2
        return v

    def int(self):
        v = struct.unpack_from("<i", self.d, self.p)[0]
        self.p += 4
        return v

    def long(self):
        v = struct.unpack_from("<q", self.d, self.p)[0]
        self.p += 8
        return v

    def uleb(self):
        res, shift = 0, 0
        while True:
            b = self.byte()
            res |= (b & 0x7F) << shift
            if not b & 0x80:
                return res
            shift += 7

    def string(self):
        if self.byte() == 0x0B:
            n = self.uleb()
            s = self.d[self.p:self.p + n].decode("utf-8", "replace")
            self.p += n
            return s
        return ""


def mods_str(m):
    out = [MODS[i] for i in range(len(MODS)) if m >> i & 1]
    if "NC" in out and "DT" in out:
        out.remove("DT")
    if "PF" in out and "SD" in out:
        out.remove("SD")
    return "".join(out) or "NM"


def parse(path):
    r = Reader(open(path, "rb").read())
    o = {}
    o["mode"] = r.byte()
    o["version"] = r.int()
    o["beatmap_md5"] = r.string()
    o["player"] = r.string()
    o["replay_md5"] = r.string()
    o["n300"], o["n100"], o["n50"], o["ngeki"], o["nkatu"], o["nmiss"] = (r.short() for _ in range(6))
    o["score"] = r.int()
    o["max_combo"] = r.short()
    o["perfect"] = r.byte()
    o["mods"] = r.int()
    o["life"] = r.string()
    o["timestamp"] = r.long()
    n = r.int()
    raw = lzma.decompress(r.d[r.p:r.p + n])
    r.p += n
    o["score_id"] = r.long() if r.p + 8 <= len(r.d) else None
    frames, t = [], 0
    for fr in raw.decode().split(","):
        if not fr:
            continue
        w, x, y, z = fr.split("|")
        w = int(w)
        if w == -12345:  # RNG seed frame
            continue
        t += w
        frames.append((t, float(x), float(y), int(z)))
    o["frames"] = frames
    tot = o["n300"] + o["n100"] + o["n50"] + o["nmiss"]
    o["acc"] = 100 * (300 * o["n300"] + 100 * o["n100"] + 50 * o["n50"]) / (300 * tot) if tot else 0
    return o


if __name__ == "__main__":
    import datetime
    for p in sys.argv[1:]:
        o = parse(p)
        ts = datetime.datetime(1, 1, 1) + datetime.timedelta(microseconds=o["timestamp"] / 10)
        print(p.split("/")[-1])
        print(f"  player {o['player']}  mods {mods_str(o['mods'])}  acc {o['acc']:.2f}%  combo {o['max_combo']}x"
              f"  300/100/50/miss {o['n300']}/{o['n100']}/{o['n50']}/{o['nmiss']}  score {o['score']}")
        print(f"  map md5 {o['beatmap_md5']}  date {ts:%Y-%m-%d}  frames {len(o['frames'])}"
              f"  length {o['frames'][-1][0] / 1000:.1f}s  score_id {o['score_id']}")
