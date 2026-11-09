# -*- coding: utf-8 -*-
"""check_speedup.py — 加速之等價檢查（失敗即停）。

  S1 同窗批次推論 = 逐節點推論：學過之偵測端（短訓練）× 學過之攻擊者，判定與攻擊者紀錄逐位相同
  S2 注入起點前之快取（T0Cache）：AttackerEnv 有／無快取，同一 reset seed 與同一動作序列下，
     觀測、reward、判定逐位相同（含同一環境之第二次取用，驗證深複製不互相污染）

用法：ZT_DATASET=d30 ZT_FUSION_ORDER=severity python check_speedup.py
"""
import sys
import torch
import numpy as np

torch.set_num_threads(1)
import game_core as G          # noqa: E402
import env_kpm_game as E       # noqa: E402
from sb3_contrib import MaskablePPO          # noqa: E402
from stable_baselines3 import PPO            # noqa: E402


def fail(m):
    print("  ✗", m); print("停止，請回報。"); sys.exit(2)


class PerNode:
    """隱藏 batch，強制逐節點決定"""
    def __init__(self, d):
        self.d, self.name = d, d.name

    def __call__(self, ep, j):
        return self.d(ep, j)


def main():
    ds = G.DataStore(); f = ds.files; test, train = f[0], f[1:]
    de = E.DetectorEnv(ds, train, test, G.A0, [1 / 3] * 3, seed=1)
    md = MaskablePPO("MlpPolicy", de, n_steps=1024, batch_size=256, seed=0, verbose=0, device="cpu")
    md.learn(4096)
    det = E.LearnedDetector(md, "D_chk")
    ae = E.AttackerEnv(ds, train, test, [det], [1.0], "O-full", seed=1)
    ma = PPO("MlpPolicy", ae, n_steps=512, batch_size=128, seed=0, verbose=0, device="cpu")
    ma.learn(1024)
    atk = E.LearnedAttacker(ma, "O-full", "A_chk")

    sd = ds.get(test)
    n = 0
    for cell in sd.cells_all:
        a = G.run_episode(E.new_episode(sd, cell), det, atk)
        b = G.run_episode(E.new_episode(sd, cell), PerNode(det), atk)
        if a.final != b.final or a.atk_log != b.atk_log:
            fail(f"S1 cell {cell}：批次與逐節點不同")
        n += len(a.final)
    esc = sum(1 for v in a.final.values() if v[2] == "drl")
    print(f"S1 ✓ 批次推論 = 逐節點推論（{n:,} 筆；最後一個 episode 中 DRL 升級 {esc} 筆，檢查有鑑別力）")

    def roll(env, s):
        out = []
        o, info = env.reset(seed=s); out.append((o.tobytes(), str(info)))
        rng = np.random.default_rng(s); done = False
        while not done:
            o, r, done, _, inf = env.step(rng.uniform(-1, 1, 1).astype(np.float32))
            out.append((o.tobytes(), r, str(inf)))
        return out, sorted(env.ep.final.items())
    plain = E.AttackerEnv(ds, train, test, [det], [1.0], "O-outcome", seed=1)
    fast = E.AttackerEnv(ds, train, test, [det], [1.0], "O-outcome", seed=1)
    fast.t0_cache = G.T0Cache()
    for s in (3, 4, 3, 5, 4):                      # 重複之 seed 測試快取重用
        if roll(plain, s) != roll(fast, s):
            fail(f"S2 reset seed {s}：有／無快取不同")
    print(f"S2 ✓ T0Cache 有／無逐位相同（5 個 episode，含 2 次快取重用；快取 {len(fast.t0_cache._c)} 筆）")


if __name__ == "__main__":
    main()
