#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_E11b_pulses.py — E11b：重複單窗脈衝 × L_C（RQ2 之 2c；規則行為驗證）

規格：docs/thesis/E11_E12_B4_spec.md（v2）之 E11b 段。

注入：C_i 灌水單窗脈衝（受測 cell 加報未登記 IMSI 9001），脈衝間隔 g ∈ {1, 2, 3, 5} 秒
      （脈衝之間至少 g 個完整、C_i 正常之秒窗），共 10 個脈衝；L_C ∈ {1, 2, 3}。
      受測 cell 於脈衝窗無上報者，該脈衝無法注入，記為「未注入」而不計入分母。
量測：在造成 C_i 違反之脈衝窗中，受測節點由 R1_CI_VETO 判為 rejected 之比例；
      其他規則造成之 rejected 另列；並報同窗其他節點之連帶判定。
預先聲明：脈衝間有間隔時，L_C ≥ 2 依構造為 0、L_C = 1 依構造為 1——規則行為驗證，非實證發現。

【內建檢查】
  1. 乾淨回放不受 L_C 影響（D-SH 乾淨資料無 C_i 違反）：三個 L_C 下乾淨回放皆 = 1,803／575／766／6
  2. 可追溯性：所有註記以 run_E11_transitions.trace（獨立實作）重算，P1→P2 須相同
  3. 間隔窗之 C_i 須為正常（連續計數歸零）
"""
import os
import sys
import copy
import json
import argparse
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_E11_transitions as E
P, E10, X = E.P, E.E10, E.X

GAPS = [1, 2, 3, 5]
N_PULSE = 10
L_CS = [1, 2, 3]
OUT_DIR = E.OUT_DIR


def inject_pulses(windows, target, k0, g):
    out = copy.deepcopy(windows)
    pulses, missed = [], []
    for i in range(N_PULSE):
        k = k0 + i * (g + 1)
        if k >= len(out):
            break
        c = out[k][1]
        if target in c and c[target]:
            c[target][E.FAKE_IMSI] = sum(c[target].values()) / len(c[target])
            pulses.append(k)
        else:
            missed.append(k)
    return out, pulses, missed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=OUT_DIR)
    args = ap.parse_args()
    files = P.find_files(None)
    seeds = [os.path.basename(f).split("seed")[-1].replace(".txt", "") for f in files]
    orig_LC = X.L_C
    res = collections.defaultdict(collections.Counter)
    n_traced = 0
    try:
        for L in L_CS:
            X.L_C = L
            clean_total = collections.Counter()
            for sd, f in zip(seeds, files):
                anchor = X.TrustAnchor([h for h in files if h != f])
                wins = E10.load_windows(f)
                nk = len({i for _, c in wins for u in c.values() for i in u})
                clean, _ = E10.run_policy(wins, anchor, "uebound", 1)
                clean_total.update(a["decision"] for a in clean)
                E.check_trace(clean, E.trace(wins, anchor, nk), f"L_C={L} seed {sd} 乾淨"); n_traced += len(clean)
                for sm in P.samples_of(sd, P.load_cell_delay(f)):
                    for g in GAPS:
                        att, pulses, missed = inject_pulses(wins, sm.cell, sm.w_on, g)
                        ann, _ = E10.run_policy(att, anchor, "uebound", 1)
                        tr = E.trace(att, anchor, nk)
                        E.check_trace(ann, tr, f"L_C={L} seed {sd} cell {sm.cell} g={g}"); n_traced += len(ann)
                        key = f"L_C={L}|g={g}"
                        res[key]["脈衝_已注入"] += len(pulses)
                        res[key]["脈衝_未注入（受測節點無上報）"] += len(missed)
                        pset = set(pulses)
                        for k in range(min(pulses, default=0), (max(pulses) + 1) if pulses else 0):
                            if k not in pset:
                                anyj = next((r for (kk, j), r in tr.items() if kk == k), None)
                                if anyj is not None and anyj["ev"]["C_i"]:
                                    raise SystemExit(f"✗ 檢查 3：{key} seed {sd} 間隔窗 {k} 之 C_i 非正常")
                        for k in pulses:
                            r = tr.get((k, sm.cell))
                            if r is None or not r["ev"]["C_i"]:
                                res[key]["脈衝_未造成C_i違反"] += 1; continue
                            res[key]["分母_造成C_i違反之脈衝窗"] += 1
                            if r["rule_id"] == "R1_CI_VETO":
                                res[key]["受測_R1_CI_VETO"] += 1
                            elif r["decision"] == "rejected":
                                res[key][f"受測_其他規則rejected|{r['rule_id']}"] += 1
                            else:
                                res[key][f"受測_{r['decision']}|{r['rule_id']}"] += 1
                            for (kk, j), o in tr.items():
                                if kk == k and j != sm.cell:
                                    res[key][f"同窗其他節點|{o['decision']}|{o['rule_id']}"] += 1
            got = {k: clean_total.get(k, 0) for k in E.EXPECTED_P3}
            if got != E.EXPECTED_P3:
                raise SystemExit(f"✗ 檢查 1：L_C={L} 乾淨回放 {got}")
    finally:
        X.L_C = orig_LC

    print("── 檢查 1：三個 L_C 下乾淨回放皆 = 1,803／575／766／6 ✓")
    print(f"── 檢查 2：可追溯性 ✓（獨立重算 {n_traced} 筆）")
    print("── 檢查 3：所有間隔窗之 C_i 皆正常 ✓\n")
    out = {}
    print(f"{'設定':<12} {'分母':>5} {'R1_CI_VETO':>11} {'比例':>6}  其他")
    for key in sorted(res, key=lambda s: (int(s.split('|')[0][4:]), int(s.split('=')[2]))):
        v = res[key]
        den = v["分母_造成C_i違反之脈衝窗"]
        veto = v["受測_R1_CI_VETO"]
        out[key] = {"denominator": den, "veto": veto, "ratio": veto / den if den else None, "counts": dict(v)}
        other = {k: c for k, c in v.items() if k.startswith("受測_") and k != "受測_R1_CI_VETO"}
        print(f"{key:<12} {den:>5} {veto:>11} {(veto / den if den else float('nan')):>6.2f}  {other}"
              f"  未注入 {v['脈衝_未注入（受測節點無上報）']}")
    path = os.path.join(args.out_dir, "E11b_pulses.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"spec": "docs/thesis/E11_E12_B4_spec.md v2 (E11b)", "gaps": GAPS, "n_pulse": N_PULSE,
                   "L_C": L_CS, "n_records_traced": n_traced, "results": out,
                   "note": "rule-behaviour verification: with gaps, L_C>=2 gives 0 and L_C=1 gives 1 by construction"},
                  fh, indent=1, ensure_ascii=False)
    print(f"\n寫入 {path}")


if __name__ == "__main__":
    main()
