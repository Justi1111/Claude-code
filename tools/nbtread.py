"""Tiny NBT reader (debugging structure files)."""
import gzip
import struct


def _read(b, i, t):
    if t == 1:
        return struct.unpack('>b', b[i:i + 1])[0], i + 1
    if t == 2:
        return struct.unpack('>h', b[i:i + 2])[0], i + 2
    if t == 3:
        return struct.unpack('>i', b[i:i + 4])[0], i + 4
    if t == 4:
        return struct.unpack('>q', b[i:i + 8])[0], i + 8
    if t == 5:
        return struct.unpack('>f', b[i:i + 4])[0], i + 4
    if t == 6:
        return struct.unpack('>d', b[i:i + 8])[0], i + 8
    if t == 8:
        n = struct.unpack('>H', b[i:i + 2])[0]
        return b[i + 2:i + 2 + n].decode(), i + 2 + n
    if t == 9:
        et, n = struct.unpack('>bi', b[i:i + 5])
        i += 5
        out = []
        for _ in range(n):
            v, i = _read(b, i, et)
            out.append(v)
        return out, i
    if t == 10:
        out = {}
        while True:
            tt = b[i]
            i += 1
            if tt == 0:
                return out, i
            n = struct.unpack('>H', b[i:i + 2])[0]
            k = b[i + 2:i + 2 + n].decode()
            i += 2 + n
            out[k], i = _read(b, i, tt)
    if t == 11:
        n = struct.unpack('>i', b[i:i + 4])[0]
        return list(struct.unpack('>%di' % n, b[i + 4:i + 4 + 4 * n])), i + 4 + 4 * n
    raise ValueError(t)


def load(path):
    b = gzip.open(path).read()
    assert b[0] == 10
    n = struct.unpack('>H', b[1:3])[0]
    return _read(b, 3 + n, 10)[0]
