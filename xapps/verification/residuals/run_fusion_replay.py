#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_fusion_replay.py — 4.11 階層式融合之規則回放（單窗，決策一致性）

對代表性攻擊各取一個真實量測窗（seed 4200，第一個 index ≥ 10 且 ≥ 3 個活躍 mmWave
cell 之窗），注入後經 zt_kpm_xapp 之 P1 判定函式、P2 融合（fuse）與 P3 政策執行
（enforce, admission=strict）產出決策、觸發規則、准入動作與准入結果。

  - C_i／S_i／H_i-D2 由 xApp 之判定函式於真實資料上計算；S_i 尺度取自凍結之
    TrustAnchor（LOSO：不含 seed 4200）。
  - H_i-D1 證據位與其歸屬節點為情境設定值（stipulated）：單窗回放無法累積 D1 所需之
    多窗停留歷史。歸屬節點以 uebound 語意給定（d1_ev.cells = [歸屬節點]）。
  - 「灌水 +1」於連續 L_C 窗注入，以檢驗持續後之 R1_CI_VETO。
  - 另取一個無活躍 mmWave 節點之窗：不產生節點註記，status = n/a。

【內建一致性檢查】預期值取自第四章 4.11.2 之表與 4.11.3（依 4.4.0 推導）。
任一不符即印出 ✗ 並以 exit 2 結束、不寫檔；不得調參數使其通過。

跑法：
  python3 run_fusion_replay.py
  python3 run_fusion_replay.py --data-dir ./seeds/si_lstm_seeds --out-dir ./results
"""
import os
import sys
import glob
import json
import argparse
import collections
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zt_kpm_xapp as X

X.FUSION_MODE = "bound"

DATA_DIR = os.path.expanduser("~/oran-zt-kpm-verification/data/si_lstm_seeds")
OUT_DIR = os.path.expanduser("~/oran-zt-kpm-verification/data/results")

# 4.11.2 之預期:(decision, rule_id, action)
EXPECTED = {
    "baseline":       ("trusted",   "R0_CLEAN",     "allow"),
    "A_inflate_+1":   ("rejected",  "R1_CI_VETO",   "exclude"),
    "delay_drift":    ("low-trust", "R2_SI_ALONE",  "restrict"),
    "teleport":       ("rejected",  "R1_D2_VETO",   "exclude"),
    "conserving_swap": ("low-trust", "R2_D1_STRONG", "restrict"),
}


def cell_map(cells):
    m = collections.defaultdict(set)
    for c, ues in cells.items():
        for i in ues:
            m[i].add(c)
    return m


def copy_cells(cells):
    return {c: dict(u) for c, u in cells.items()}


def replay(name, cells, prev_cells, target, anchor, w, ci_prev_cells=None,
           d1=("normal", None), cur_map=None, prev_map=None):
    """單窗之 P1(C_i/S_i/D2 實算,D1 情境設定)→ P2 → P3。回傳一列結果"""
    ci_run0 = 0
    if ci_prev_cells is not None:                     # 前一窗亦注入:累積 C_i 持續窗
        _, ci_run0, _ = X.verify_ci(ci_prev_cells, 0)
    ci, ci_run, ci_ev = X.verify_ci(cells, ci_run0)
    d2, d2_ev = X.verify_hi_d2(prev_map if prev_map is not None else cell_map(prev_cells),
                               cur_map if cur_map is not None else cell_map(cells))
    d1_level, d1_ev = d1
    if not any(c != X.LTE_CELL for c in cells):       # 無判定對象
        _, rec = X.enforce([], cells, w, "strict")
        return {"scenario": name, "window": w, "status": rec["status"],
                "reason": rec.get("reason"), "out_of_scope": rec["out_of_scope"],
                "annotation": None}
    si, z, peer = X.verify_si(cells, target, anchor.scale)
    dec, rid = X.fuse(ci, ci_run, si, d2, d1_level, d1_ev, target)
    ann = {"window": w, "node": target, "decision": dec, "rule_id": rid}
    _, rec = X.enforce([ann], cells, w, "strict")
    return {"scenario": name, "window": w, "status": rec["status"], "node": target,
            "C_i": ci, "ci_run": ci_run, "S_i": si, "z_S": z, "peer": peer, "H_i_D2": d2,
            "H_i_D1": d1_level,
            "d1_attributed_node": (d1_ev or {}).get("cells", [None])[0] if d1_ev else None,
            "decision": dec, "rule_id": rid, "action": ann["action"],
            "admitted": ann["admitted"], "out_of_scope": rec["out_of_scope"],
            "evidence": {k: v for k, v in (("C_i", ci_ev), ("D2", d2_ev), ("D1", d1_ev)) if v}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=None)
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()
    out_dir = args.out_dir or OUT_DIR

    search = [args.data_dir] if args.data_dir else [
        DATA_DIR, os.path.join("seeds", "si_lstm_seeds"), "."]
    files = []
    for d in search:
        files = sorted(glob.glob(os.path.join(d, "ues1_t300_seed*.txt")))
        if len(files) >= 2:
            break
    if len(files) < 2:
        print("資料不足，用 --data-dir 指定。"); return

    test = files[0]
    anchor = X.TrustAnchor(files[1:])                 # LOSO:凍結基線不含受測 seed
    wins = list(X.TraceReplaySource(test).windows())
    W = dict(wins)
    # 偽造成員所用之「正常 delay」:training seeds 之 mmWave delay 全域中位數
    med_g = float(np.median([d for f in files[1:] for _, cells in X.TraceReplaySource(f).windows()
                             for c, u in cells.items() if c != X.LTE_CELL for d in u.values()]))

    tw = next(w for w, cells in wins[10:] if len([c for c in cells if c != X.LTE_CELL]) >= 3)
    prev_w = tw - 1 if tw - 1 in W else tw
    target = [c for c in W[tw] if c != X.LTE_CELL][0]
    n_mmw = len([c for c in W[tw] if c != X.LTE_CELL])
    seed = os.path.basename(test).split("seed")[-1][:4]
    print(f"規則回放(seed {seed}, window {tw}, {n_mmw} 個 mmWave cell, 受測節點 {target})")

    rows = []
    # baseline
    rows.append(replay("baseline", W[tw], W[prev_w], target, anchor, tw))

    # A. 灌水 +1:prev_w 與 tw 連續注入未登記 IMSI(持續 L_C=2 窗)
    def inflate(cells):
        c2 = copy_cells(cells)
        c2.setdefault(target, {})[9999] = med_g
        return c2
    rows.append(replay("A_inflate_+1", inflate(W[tw]), inflate(W[prev_w]), target, anchor, tw,
                       ci_prev_cells=inflate(W[prev_w])))

    # delay drift:受測節點 delay 拉到 med_g + 6s
    dr = copy_cells(W[tw])
    dr[target] = {i: med_g + 6 * anchor.scale for i in dr[target]}
    rows.append(replay("delay_drift", dr, W[prev_w], target, anchor, tw))

    # teleport:prev 掛 mmWave A 之 UE,本窗直接出現於另一 mmWave B 且無 LTE 過渡
    prev_m, cur_m = cell_map(W[prev_w]), cell_map(W[tw])
    tele = dict(cur_m)
    some = [i for i in prev_m if any(c != X.LTE_CELL for c in prev_m[i])]
    if some:
        ii = some[0]
        other = [c for c in W[tw] if c != X.LTE_CELL and c not in prev_m[ii]]
        if other:
            tele[ii] = {other[0]}
    rows.append(replay("teleport", W[tw], W[prev_w], target, anchor, tw,
                       cur_map=tele, prev_map=prev_m))

    # 守恆式替換:-1 真成員 +1 偽成員(基數不變,delay 正常);D1 strong 歸屬於受測節點
    sw = copy_cells(W[tw])
    real = sorted(sw[target])
    swapped = real[0] if real else None
    if real:
        del sw[target][real[0]]
        sw[target][8888] = med_g
    rows.append(replay("conserving_swap", sw, W[prev_w], target, anchor, tw,
                       d1=("strong", {"imsi": swapped, "cells": [target],
                                      "bound_by": "stipulated"})))

    # 無活躍 mmWave 節點之窗 → status = n/a
    na = None
    for f in files:
        for w, cells in X.TraceReplaySource(f).windows():
            if not any(c != X.LTE_CELL for c in cells):
                na = (os.path.basename(f), w, cells); break
        if na:
            break
    if na:
        r = replay("no_active_mmwave_node", na[2], na[2], None, anchor, na[1])
        r["seed_file"] = na[0]
        rows.append(r)

    # ---- 印表 ----
    print("=" * 112)
    print(f"{'情境':<22}{'C_i':<11}{'S_i':<16}{'H-D2':<10}{'H-D1†':<8}{'D1 歸屬':<9}"
          f"{'決策':<11}{'規則':<15}{'動作':<10}{'准入'}")
    print("-" * 112)
    for r in rows:
        if r["status"] == "n/a":
            print(f"{r['scenario']:<22}status=n/a  reason={r['reason']}  "
                  f"({r.get('seed_file')}, window {r['window']};不產生節點註記)")
            continue
        s_i = f"{r['S_i']}" + (f"(z={r['z_S']})" if r["z_S"] is not None else "")
        print(f"{r['scenario']:<22}{r['C_i']:<11}{s_i:<16}{r['H_i_D2']:<10}{r['H_i_D1']:<8}"
              f"{str(r['d1_attributed_node'] or '—'):<9}{r['decision']:<11}{r['rule_id']:<15}"
              f"{r['action']:<10}{'✓' if r['admitted'] else '✗'}")
    print("† H_i-D1 證據位與歸屬節點為情境設定值,非偵測器輸出。准入政策 = strict。")

    # ---- 決策一致性檢查(預期值取自 4.11.2/4.11.3)----
    by = {r["scenario"]: r for r in rows}
    checks = []
    for name, (dec, rid, act) in EXPECTED.items():
        r = by[name]
        checks.append((f"{name} → {rid} → {dec} → {act}",
                       r["decision"] == dec and r["rule_id"] == rid and r["action"] == act
                       and r["admitted"] == (act == "allow")))
    checks.append(("conserving_swap:C_i conserved 但非 trusted",
                   by["conserving_swap"]["C_i"] == "conserved"
                   and by["conserving_swap"]["decision"] != "trusted"))
    if na:
        checks.append(("無節點窗 → status=n/a,無節點註記",
                       by["no_active_mmwave_node"]["status"] == "n/a"
                       and by["no_active_mmwave_node"]["annotation"] is None))
    checks.append(("LTE 錨點為 out_of_scope,任何情境皆未准入",
                   all(r["out_of_scope"] == [X.LTE_CELL] for r in rows)))
    print("\n決策一致性檢查:")
    for name, ok in checks:
        print(f"  {'✓' if ok else '✗'} {name}")
    if not all(ok for _, ok in checks):
        print("\n✗ 有不符。停止:不寫入任何輸出。請回報,勿調參數。")
        sys.exit(2)
    print("\n全部一致")

    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "fusion_replay.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"seed": seed, "window": tw, "target": target, "n_mmw": n_mmw,
                   "fusion_mode": X.FUSION_MODE, "admission": "strict",
                   "d1_stipulated": True, "rows": rows,
                   "checks": {n: ok for n, ok in checks}},
                  fh, indent=2, ensure_ascii=False, default=str)
    print(f"寫入 {out}")


if __name__ == "__main__":
    main()
