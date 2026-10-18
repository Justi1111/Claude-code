"""Minimal RCON client for driving a local Minecraft server in tests."""
import socket
import struct
import time


class Rcon:
    def __init__(self, host="127.0.0.1", port=25575, password="test", timeout=30):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.req = 0
        if self._send(3, password)[0] == -1:
            raise RuntimeError("RCON auth failed")

    def _packet(self, rid, ptype, body):
        data = struct.pack("<ii", rid, ptype) + body.encode("utf-8") + b"\x00\x00"
        return struct.pack("<i", len(data)) + data

    def _recv(self):
        raw = b""
        while len(raw) < 4:
            chunk = self.sock.recv(4 - len(raw))
            if not chunk:
                raise ConnectionError("RCON connection closed")
            raw += chunk
        (length,) = struct.unpack("<i", raw)
        data = b""
        while len(data) < length:
            chunk = self.sock.recv(length - len(data))
            if not chunk:
                raise ConnectionError("RCON connection closed")
            data += chunk
        rid, ptype = struct.unpack("<ii", data[:8])
        return rid, ptype, data[8:-2].decode("utf-8", "replace")

    def _send(self, ptype, body):
        self.req += 1
        rid = self.req
        self.sock.sendall(self._packet(rid, ptype, body))
        if ptype == 3:
            r = self._recv()
            return r[0], r[2]
        # The server reads one packet per socket read, so never pipeline.
        # Replies longer than 4096 bytes arrive in several packets; an empty
        # follow-up command (sent only after the first part) marks the end.
        r_id, _, text = self._recv()
        out = [text]
        if len(text.encode("utf-8")) >= 4096:
            self.req += 1
            marker = self.req
            self.sock.sendall(self._packet(marker, 2, ""))
            while True:
                r_id, _, text = self._recv()
                if r_id == marker:
                    break
                out.append(text)
        return rid, "".join(out)

    def cmd(self, command):
        return self._send(2, command)[1]


def wait_for_server(timeout=300, **kw):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            return Rcon(**kw)
        except OSError:
            time.sleep(2)
    raise TimeoutError("server did not start")
