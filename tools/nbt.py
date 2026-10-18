"""Minimal NBT writer (big-endian, gzip) for structure template files."""
import gzip
import struct

END, BYTE, INT, STRING, LIST, COMPOUND = 0, 1, 3, 8, 9, 10


class Byte(int):
    pass


def _tag_type(v):
    if isinstance(v, Byte):
        return BYTE
    if isinstance(v, int):
        return INT
    if isinstance(v, str):
        return STRING
    if isinstance(v, list):
        return LIST
    if isinstance(v, dict):
        return COMPOUND
    raise TypeError(type(v))


def _payload(v):
    t = _tag_type(v)
    if t == BYTE:
        return struct.pack(">b", v)
    if t == INT:
        return struct.pack(">i", v)
    if t == STRING:
        b = v.encode("utf-8")
        return struct.pack(">H", len(b)) + b
    if t == LIST:
        et = _tag_type(v[0]) if v else END
        return struct.pack(">bi", et, len(v)) + b"".join(_payload(x) for x in v)
    out = b""
    for k, x in v.items():
        kb = k.encode("utf-8")
        out += struct.pack(">bH", _tag_type(x), len(kb)) + kb + _payload(x)
    return out + struct.pack(">b", END)


def write(path, root):
    data = struct.pack(">bH", COMPOUND, 0) + _payload(root)
    with gzip.open(path, "wb") as f:
        f.write(data)
