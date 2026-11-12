#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_E24pre_logdomain.py — 規格 docs/thesis/E24pre_log_domain_precheck_spec.md v1。
E23 事後觀察之拆解：域（線性／log）× 參照（同窗 peer／凍結全域常數）。只讀乾淨 D-30；固定階躍。

跑法：ZT_DATASET=d30 ZT_FUSION_ORDER=severity python3 xapps/verification/residuals/run_E24pre_logdomain.py
"""
import os
import sys
import json
import math
import time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run_E23_reference as E23                                       # noqa: E402
from run_E23_reference import X, S0, stop                             # noqa: E402

OUT_DIR = os.path.join(S0.SEV_DIR, "E24pre")
E23_S0 = os.path.join(S0.SEV_DIR, "E23", "E23_s0.json")
AS = [0.892, 0.822, 0.8, 0.6]
STATS = ["A", "B", "C", "D", "E"]


def node_values(base):
    """{(w, j): (tgt, lm, ref_raw, ref_lm)}；僅 peer ≥ MIN_PEER 之 (節點, 窗)"""
    out = {}
    for w, cells in base:
        mm = [c for c in sorted(cells) if c != X.LTE_CELL]
        t = {c: float(np.mean(list(cells[c].values()))) for c in mm}
        lm = {c: float(np.mean([math.log(v) for v in cells[c].values()])) for c in mm}
        for j in mm:
            peers = [c for c in mm if c != j]
            if len(peers) < X.MIN_PEER:
                continue
            out[(w, j)] = (t[j], lm[j], float(np.median([t[c] for c in peers])), float(np.median([lm[c] for c in peers])))
    return out


def main():
    t_start = time.time()
    seeds = E23.load_all(with_replay=True)
    for s in seeds:
        s["nv"] = node_values(s["base"])
        nvio = sum(abs(t - r) / s["anchor"].scale > X.TAU_S for t, _, r, _ in s["nv"].values())
        ref = sum(a["S_i"] == "violated" for a in s["ann"])
        if nvio != ref or len(s["nv"]) != len(s["ann"]):
            stop(f"E24P-1 seed {s['seed']}：S_i 違反 {nvio} vs 註記 {ref}；筆數 {len(s['nv'])} vs {len(s['ann'])}")
    print("  E24P-1 ✓")
    if math.log(1.0) != 0.0 or (1.0 - 1.0) != 0.0:
        stop("E24P-2")

    def vals(s, st, train):
        """回傳 [(key, v, tgt)]"""
        if st == "C":
            const = float(np.median([t for x in train for t, *_ in x["nv"].values()]))
        if st == "D":
            alpha = E23.fit(train, True)[0]
        o = []
        for k, (t, lm, r, rlm) in s["nv"].items():
            v = {"A": lambda: t - r, "B": lambda: lm - rlm, "C": lambda: t - const,
                 "D": lambda: lm - alpha, "E": lambda: math.log(t) - math.log(r)}[st]()
            o.append((k, v, t))
        return o

    def shift(st, a, t):
        return (a - 1.0) * t if st in ("A", "C") else math.log(a)

    res = {}
    for st in STATS:
        n = fa = 0
        det = {a: 0 for a in AS}
        per, ths = {}, []
        for s in seeds:
            train = [x for x in seeds if x is not s]
            th = float(np.quantile(np.abs([v for x in train for _, v, _ in vals(x, st, train)]), 0.95))
            ths.append(th)
            V = vals(s, st, train)
            n += len(V)
            fa += sum(abs(v) >= th for _, v, _ in V)
            for a in AS:
                det[a] += sum(abs(v + shift(st, a, t)) >= th for _, v, t in V)
            by = {}
            for (w, j), v, _ in V:
                by.setdefault(j, []).append(v)
            for j, vv in by.items():
                vv = np.array(vv)
                per[f"{s['seed']}|{j}"] = {"FA": float((np.abs(vv) >= th).mean()), "mean": float(vv.mean()),
                                           "lag1": float(np.corrcoef(vv[:-1], vv[1:])[0, 1]) if len(vv) > 2 and vv.std() > 0 else None}
        lag = [p["lag1"] for p in per.values() if p["lag1"] is not None]
        res[st] = {"n": n, "FA": fa / n, "DET": {str(a): det[a] / n for a in AS}, "theta": ths,
                   "n_series_FA_gt_0.20": sum(p["FA"] > 0.20 for p in per.values()), "n_series": len(per),
                   "lag1_median": float(np.median(lag)), "per_series": per}
        r = res[st]
        print(f"  {st}  n {n}  θ [{min(ths):.3f}, {max(ths):.3f}]  FA {r['FA']:.3f}  "
              + "  ".join(f"DET(×{a}) {r['DET'][str(a)]:.3f}" for a in AS)
              + f"  FA>0.20 之序列 {r['n_series_FA_gt_0.20']}／{len(per)}  lag-1 中位數 {r['lag1_median']:.3f}")

    ref0 = json.load(open(E23_S0, encoding="utf-8"))["results"]["Ref-0"]
    d = res["D"]
    if abs(d["FA"] - ref0["FA"]) > 1e-12 or any(abs(d["DET"][str(a)] - ref0["DET"][str(a)]) > 1e-12 for a in AS):
        stop(f"E24P-0 D 未重現 E23 Ref-0：{d['FA']} {d['DET']} vs {ref0['FA']} {ref0['DET']}")
    print("  E24P-0 ✓（D 重現 E23 之 Ref-0）")

    # S_i 原判定
    n = sum(len(s["nv"]) for s in seeds)
    si = {"FA": sum(abs(t - r) / s["anchor"].scale > X.TAU_S for s in seeds for t, _, r, _ in s["nv"].values()) / n,
          "DET": {str(a): sum(abs(a * t - r) / s["anchor"].scale > X.TAU_S
                              for s in seeds for t, _, r, _ in s["nv"].values()) / n for a in AS}}
    print(f"  S_i(τ=4)  FA {si['FA']:.3f}  " + "  ".join(f"DET(×{a}) {si['DET'][str(a)]:.3f}" for a in AS))

    b = res["B"]
    verdict = ("增益來自 log 域（peer 參照可保留）" if b["FA"] <= 0.10 and b["DET"]["0.8"] >= 0.70
               else "增益來自全域參照" if b["DET"]["0.8"] < 0.30 else "不確定")
    print(f"  判定：{verdict}")
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, "E24pre_logdomain.json")
    json.dump({"spec": "docs/thesis/E24pre_log_domain_precheck_spec.md v1", "stats": res, "S_i_tau4": si,
               "verdict": verdict}, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"寫入 {out}（{time.time() - t_start:.0f} s）")


if __name__ == "__main__":
    main()
