# -*- coding: utf-8 -*-
"""比對 venv 之關鍵套件版本與舊機器相同；不符即停（結果可重現性之前提）。"""
import sys
import importlib.metadata as md
NEED = {"torch": "2.5.1+cpu", "numpy": "2.2.6", "scipy": "1.15.3", "gymnasium": "1.1.1",
        "stable_baselines3": "2.6.0", "sb3_contrib": "2.6.0", "nashpy": "0.0.43", "cloudpickle": "3.1.2"}
bad = {p: (md.version(p) if p in {d.metadata["Name"].replace("-", "_").lower() for d in md.distributions()} else None, v)
       for p, v in NEED.items()}
bad = {p: (got, v) for p, (got, v) in bad.items() if got != v}
print("Python", sys.version.split()[0], "（舊機器 3.10.12）")
if bad:
    print("✗ 版本不符：", bad); sys.exit(2)
print("✓ 套件版本與舊機器相同：", NEED)
