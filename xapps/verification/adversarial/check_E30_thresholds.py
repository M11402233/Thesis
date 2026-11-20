# -*- coding: utf-8 -*-
"""check_E30_thresholds.py — E30 §7 C-1（docs/thesis/E30_coevolution_spec.md）：
T 偵測端恆選「不動」（MOVES 索引 4）、TL 恆選「不動＋依下限」時，與 F（規則版 D0）逐筆相同。
另核對：凍結 τ_H 之 D1 = E19（SeedData.ev_h 內建 assert）；mask 內含「不動」；非凍結格點之下限只用既有函式。
全部 seed × 全部 cell × A0（無攻擊 ＋ 3 個腳本攻擊）。任一不符即停（exit 2），不寫結果。
用法（~/venvs/drl）：ZT_DATASET=d30p ZT_DELAY_SOURCE=percell ZT_FUSION_ORDER=severity python check_E30_thresholds.py [--json out]
"""
import sys
import json
import argparse
import game_core as G
import env_kpm_game as E


class Const:
    def __init__(self, mode, a):
        self.det_mode, self.a, self.name = mode, a, f"const_{mode}_{a}"

    def __call__(self, ep, j):
        assert ep.mask_th(j)[self.a], ("「不動」不在 mask 內", j)
        return self.a


def decs(ep):
    return {k: v[:2] for k, v in ep.final.items()}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--json"); a = ap.parse_args()
    ds = G.DataStore(); n = 0; moved = 0
    for f in ds.files:
        sd = ds.get(f)
        _ = sd.ev_h                                       # 觸發凍結格點之 D1 核對
        for cell in sd.cells_all:
            for atk in [None] + G.A0:
                ref = G.run_episode(E.new_episode(sd, cell), E.FloorDetector(), atk)
                for mode, act in (("T", 4), ("TL", 4 * 3 + 0)):
                    ep = G.run_episode(E.new_episode(sd, cell), Const(mode, act), atk)
                    if decs(ep) != decs(ref):
                        bad = [(k, decs(ref)[k], decs(ep).get(k)) for k in decs(ref) if decs(ref)[k] != decs(ep).get(k)][:3]
                        print("✗ C-1", sd.seed, cell, getattr(atk, "name", None), mode, bad); sys.exit(2)
                    keep = {k: v for k, v in ep.stats.items() if not k.startswith("th_") and k not in ("det_R", "det_n")}
                    kref = {k: v for k, v in ref.stats.items() if k not in ("det_R", "det_n")}
                    if keep != kref:
                        print("✗ C-1 stats", sd.seed, cell, mode, keep, kref); sys.exit(2)
                    moved += ep.stats["th_changes"]; n += len(ep.final)
    if moved:
        print("✗ 「不動」策略卻有門檻變更", moved); sys.exit(2)
    print(f"C-1 ✓ T／TL 恆選凍結門檻 = F：{n:,} 筆（{len(ds.files)} seed × 全部 cell × 4 情境 × 2 模式）")
    if a.json:
        json.dump({"C-1": {"records": n, "pass": True}}, open(a.json, "w"), indent=1)


if __name__ == "__main__":
    main()
