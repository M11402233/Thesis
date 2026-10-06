#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_E13_rt.py — 方案 B：τ_S 敏感度（殘差層改以實際秒數；融合層與十等分表不受影響）

規格：docs/thesis/planB_realtime_spec.md。舊版 E13_tauS_sensitivity.json 保留不動。

【殘差層】τ_S ∈ {3, 3.5, 4, 4.5, 5}；空間與時間參照（時間參照依方案 B 定義）；
  乾淨誤報與漂移 0.5／1／2 %/秒、階躍 ×1.3；own 與 common 集合。
【不受方案 B 影響、須逐位重現者】
  1. 融合層（uebound, L_H = 1）於 τ_S = 4 之 1,803／575／766／6（n = 3,150），
     且五個 τ_S 之計數與舊 E13 輸出相同（xApp 未改動）。
  2. 4.7.7 十等分表（空間參照乾淨 z，與時間單位無關）。
  3. 空間參照於原始評估集合之乾淨誤報與 ×1.3 階躍（各 τ_S）與舊 E13 相同。
【回歸基準】E13_rt（人工核對後建立）。
"""
import os
import sys
import json
import argparse
import collections
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import planB_rt as P
import run_E13_tauS_sensitivity as E13
import run_E9_operating_regime as E9

TAUS = E13.TAUS
RATES = [0.005, 0.01, 0.02]
REFS = ("spatial", "temporal")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=E9.OUT_DIR)
    ap.add_argument("--set-baseline", action="store_true")
    args = ap.parse_args()
    seeds, data = P.load_data()
    old = json.load(open(os.path.join(args.out_dir, "E13_tauS_sensitivity.json"), encoding="utf-8"))

    acc = collections.defaultdict(list)
    for ts in seeds:
        s = P.fold_scale(data, seeds, ts)
        for sm in P.samples_of(ts, data[ts]):
            sets = {"own": {r: P.own_set(sm, r) for r in REFS}, "common": {r: P.common_set(sm) for r in REFS}}
            for r in REFS:
                zf = (lambda v: P.z_spatial(sm, v, s)) if r == "spatial" else (lambda v: P.z_temporal(sm, v, s))
                zc = zf(sm.own)
                zd = {k: zf(P.inject_drift(sm.own, sm.w_on, k, sm.mean)) for k in RATES}
                zs = zf(P.inject_step(sm.own, sm.w_on, 1.3))
                for tau in TAUS:
                    for st in ("own", "common"):
                        S = sets[st][r]
                        acc[(tau, st, r, "clean")].append((ts, P.rate(P.flags_from_z(zc, tau), S)))
                        acc[(tau, st, r, "step1.3")].append((ts, P.rate(P.flags_from_z(zs, tau), S)))
                        for k in RATES:
                            acc[(tau, st, r, k)].append((ts, P.rate(P.flags_from_z(zd[k], tau), S)))

    A = lambda key: P.agg_seed([(sd, v) for sd, v in acc[key] if v is not None])
    resid = {str(tau): {st: {r: {"clean_fpr": A((tau, st, r, "clean")), "step1.3": A((tau, st, r, "step1.3")),
                                  "drift": {str(k): A((tau, st, r, k)) for k in RATES}}
                             for r in REFS} for st in ("own", "common")} for tau in TAUS}

    # ---- 不受方案 B 影響之檢查 ----
    bad = []
    for tau in TAUS:
        a = resid[str(tau)]["own"]["spatial"]; o = old["residual"][str(tau)]["spatial"]
        if a["clean_fpr"]["mean"] != o["clean_fpr"]["mean"]:
            bad.append(("空間乾淨", tau))
        if a["step1.3"]["mean"] != o["step"]["1.3"]["mean"]:
            bad.append(("空間階躍×1.3", tau))
    fus = E13.fusion_level(P.find_files(None))
    for tau in TAUS:
        if {k: fus[str(tau)]["counts"].get(k, 0) for k in E13.EXPECTED_P3} != \
           {k: old["fusion_uebound_L1"][str(tau)]["counts"].get(k, 0) for k in E13.EXPECTED_P3}:
            bad.append(("融合層", tau))
    if {k: fus["4.0"]["counts"].get(k, 0) for k in E13.EXPECTED_P3} != E13.EXPECTED_P3:
        bad.append(("融合層 τ=4 vs 1803/575/766/6",))
    dec = E13.decile_table(data, seeds)
    for r, (f, z, p) in zip(dec["rows"], E13.PUBLISHED_477):
        if (round(r["fpr"], 3), round(r["mean_z"], 2), round(r["mean_peer"], 2)) != (f, z, p):
            bad.append(("十等分", r["decile"]))
    print("── 不受方案 B 影響之檢查 ──")
    if bad:
        print("  ✗", bad); raise SystemExit("不一致，先查原因，不寫檔。")
    print("  ✓ 空間乾淨／×1.3（原始評估集合，五個 τ_S）、融合層五個 τ_S、十等分表皆與舊值相同\n")

    res = {"spec": "docs/thesis/planB_realtime_spec.md", "taus": TAUS, "residual_rt": resid,
           "fusion_uebound_L1": fus, "decile_spatial_tau4": dec}
    vals = {f"{tau}|{st}|{r}|{k}": resid[str(tau)][st][r]["drift"][k]["mean"]
            for tau in TAUS for st in ("own", "common") for r in REFS for k in resid[str(tau)][st][r]["drift"]}
    vals.update({f"{tau}|{st}|{r}|clean": resid[str(tau)][st][r]["clean_fpr"]["mean"]
                 for tau in TAUS for st in ("own", "common") for r in REFS})
    res["baseline_status"] = P.check_baseline("E13_rt", vals, args.set_baseline, note="2026-10-06 人工核對")
    print("── 回歸基準 E13_rt：", res["baseline_status"], "──\n")
    path = os.path.join(args.out_dir, "E13_tauS_sensitivity_rt.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, ensure_ascii=False)

    print("══ common 集合：乾淨誤報與漂移偵測（空間 | 時間）；差距 = 1 %/秒 空間 − 時間（seed 範圍）══")
    for tau in TAUS:
        a = resid[str(tau)]["common"]["spatial"]; b = resid[str(tau)]["common"]["temporal"]
        d = {sd: a["drift"]["0.01"]["per_seed"][sd] - b["drift"]["0.01"]["per_seed"][sd] for sd in a["drift"]["0.01"]["per_seed"]}
        print(f"τ={tau:<3} | {a['clean_fpr']['mean']:.3f} " + " ".join(f"{a['drift'][str(k)]['mean']:.2f}" for k in RATES)
              + f" | {b['clean_fpr']['mean']:.3f} " + " ".join(f"{b['drift'][str(k)]['mean']:.2f}" for k in RATES)
              + f" | {a['drift']['0.01']['mean'] - b['drift']['0.01']['mean']:+.2f}（{min(d.values()):+.2f} 至 {max(d.values()):+.2f}）")
    print(f"\n寫入 {path}")


if __name__ == "__main__":
    main()
