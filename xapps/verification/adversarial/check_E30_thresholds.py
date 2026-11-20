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
    # C-3（E30 §4）：腳本攻擊之行為特徵 = 定義值，且與偵測端無關（開環）
    from psro import behaviour
    c3 = {}
    for atk, exp in ((G.A0[0], {"m": -0.4, "p": 1.0}), (G.A0[1], {"m": -0.2, "p": 1.0})):
        feats = {}
        for mode, act, det in (("F", None, E.FloorDetector()), ("T", 4, Const("T", 4)), ("TL", 12, Const("TL", 12))):
            tot = {}
            for f in ds.files:
                sd = ds.get(f)
                for cell in sd.cells_all:
                    ep = G.run_episode(E.new_episode(sd, cell), det, atk)
                    for k, v in ep.stats.items():
                        tot[k] = tot.get(k, 0) + v
            feats[mode] = behaviour(tot)
        for mode, b in feats.items():
            if b is None or any(abs(b[k] - v) > 1e-9 for k, v in exp.items()) or b != feats["F"]:
                print("✗ C-3", atk.name, mode, b, "期望", exp); sys.exit(2)
        c3[atk.name] = feats["F"]
    print("C-3 ✓ 腳本攻擊特徵 = 定義值（step×0.6：m = −0.4、p = 1；step×0.8：m = −0.2、p = 1），F／T／TL 下相同", c3)
    # C-5／C-6（E30 §2a、§7）：F（規則版）、無攻擊
    from psro import decision_report
    tot = {}
    for f in ds.files:
        sd = ds.get(f)
        for cell in sd.cells_all:
            ep = G.run_episode(E.new_episode(sd, cell), E.FloorDetector(), None)
            for k, v in ep.stats.items():
                tot[k] = tot.get(k, 0) + v
    rep = decision_report(tot)
    nall = tot["det_n_all"]
    cnt = sum(tot.get(f"dc_{g}_{d}", 0) for g in ("clean", "tam") for d in ("trusted", "low-trust", "rejected", "abstain"))
    if cnt != nall or tot["clean_n"] != rep["clean"]["n"] or tot.get("tam_n", 0) != rep["tampered"]["n"]:
        print("✗ C-6 決策計數不等於全部 (節點, 秒)", cnt, nall); sys.exit(2)
    # C-5：全部 − 學習者步 = 規則直接決定之 (節點, 秒) 之 reward（無攻擊：rejected −β、abstain −μ）
    diff = tot["det_R_all"] - tot["det_R"]
    exp = -G.BETA * tot.get("dc_clean_rejected", 0) - G.MU * tot.get("dc_clean_abstain", 0)
    if abs(diff - exp) > 1e-9 or tot["det_n_all"] - tot["det_n"] != tot.get("dc_clean_rejected", 0) + tot.get("dc_clean_abstain", 0):
        print("✗ C-5 分母差異不能由規則決定之步解釋", diff, exp, tot["det_n_all"] - tot["det_n"]); sys.exit(2)
    print(f"C-5／C-6 ✓ 分母 {nall:,}（學習者步 {tot['det_n']:,}，規則決定 {nall - tot['det_n']:,}）；"
          f"abstain {rep['abstain_share_all']:.4f}、乾淨被擋 {rep['clean']['not_admitted']:.4f}")
    if moved:
        print("✗ 「不動」策略卻有門檻變更", moved); sys.exit(2)
    print(f"C-1 ✓ T／TL 恆選凍結門檻 = F：{n:,} 筆（{len(ds.files)} seed × 全部 cell × 4 情境 × 2 模式）")
    if a.json:
        json.dump({"C-1": {"records": n, "pass": True}, "C-3": c3, "C-5_C-6": rep}, open(a.json, "w"), indent=1)


if __name__ == "__main__":
    main()
