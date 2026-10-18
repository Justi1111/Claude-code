"""Throughput: two full stacks plus mixed items through three cells, no loss."""
import time
from mc import put
from t_live import setup, wait, INPUT
setup([[("cobblestone", 1)], [("dirt", 1)], [("sand", 1)]],
      [("cobblestone", 64), ("dirt", 40), ("sand", 24), ("stone", 16)])
s, dt = wait(900)
total = sum(s["cell0"].values()) + sum(s["cell1"].values()) + sum(s["cell2"].values()) + sum(s["overflow"].values())
print(round(dt), "s", s)
print("items in:", 144 + 3, "items found:", total, "rate", round(144 / dt, 2), "items/s")
