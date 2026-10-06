#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_E9c_rt.py — 方案 B：良性共模擾動下之誤報（使用 E9b_rt 之分類器）

規格：docs/thesis/planB_realtime_spec.md。舊版 E9c_common_mode.json 保留不動。

擾動與舊版相同（自第 150 秒起，所有 mmWave cell 同乘 g 或 1 + r·(w − 150)），本來即以實際秒定義；
改變者為三種方法之判定（時間參照與監督式分類器依方案 B 定義）與比較集合。

【比較集合】各樣本 w ≥ 150 之 full-consensus 窗：common（三方法共同可評估；主結果）與 own。
【共模下之攻擊】於 g = 1.2 之上，自該樣本 w ≥ 150 之第一個評估窗起，對受測 cell 所有上報窗注入。
【內建檢查】
  1. 三方法於 E9_rt／E9b_rt 之 common 集合（序列後半段）之乾淨誤報與該二輸出逐位相同。
  2. 回歸基準 E9c_rt（人工核對後建立）。
說明：乘法共模擾動下，凍結尺度 s 時空間殘差 z'_j = g · z_j，並未被抵銷。
"""
import os
import sys
import json
import argparse
import collections
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import planB_rt as P
import run_E9_operating_regime as E9
import run_E9b_rt as BR
from run_E9c_common_mode import common_mode, W_ON, CM_STEP, CM_DRIFT, C_G, C_ATTACK

METHODS = ("spatial", "temporal", "supervised")


def flags(method, sm, v, s, model):
    if method == "supervised":
        m, med, thr = model
        return BR.sup_flags(m, sm, v, med, s, thr)
    z = P.z_spatial(sm, v, s) if method == "spatial" else P.z_temporal(sm, v, s)
    return P.flags_from_z(z)


def evalsets(sm, w_from):
    base = [w for w in sm.idx if w >= w_from]
    return {"common": [w for w in base if sm.avail_t[w] and sm.avail_s[w]],
            "own": {"spatial": base, "temporal": [w for w in base if sm.avail_t[w]],
                    "supervised": [w for w in base if sm.avail_s[w]]}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=E9.OUT_DIR)
    ap.add_argument("--set-baseline", action="store_true")
    ap.add_argument("--no-fig", action="store_true")
    args = ap.parse_args()
    seeds, data = P.load_data()
    e9rt = json.load(open(os.path.join(args.out_dir, "E9_operating_regime_rt.json"), encoding="utf-8"))
    e9brt = json.load(open(os.path.join(args.out_dir, "E9b_supervised_baseline_rt.json"), encoding="utf-8"))

    acc = collections.defaultdict(list)
    chk = {m: [] for m in METHODS}
    n_eval = []
    for fi, ts in enumerate(seeds):
        m, med, s, thr, _ = BR.get_fold_model(data, seeds, fi, ts)
        model = (m, med, thr)
        clean = P.samples_of(ts, data[ts])
        pert = {f"step{g}": P.samples_of(ts, common_mode(data[ts], "step", g)) for g in CM_STEP}
        pert.update({f"drift{r}": P.samples_of(ts, common_mode(data[ts], "drift", r)) for r in CM_DRIFT})
        cg = P.samples_of(ts, common_mode(data[ts], "step", C_G))
        for i, sm in enumerate(clean):
            assert all(lst[i].cell == sm.cell and lst[i].idx == sm.idx for lst in list(pert.values()) + [cg]), "擾動後樣本未對齊"
            f0 = {mt: flags(mt, sm, sm.own, s, model) for mt in METHODS}
            for mt in METHODS:
                chk[mt].append((ts, P.rate(f0[mt], P.common_set(sm))))
            ES = evalsets(sm, W_ON)
            if len(ES["common"]) < 5:
                continue
            n_eval.append((ts, len(ES["common"])))
            for mt in METHODS:
                for st, S in (("common", ES["common"]), ("own", ES["own"][mt])):
                    b = P.rate(f0[mt], S)
                    acc[(st, mt, "base")].append((ts, b))
                    for key, lst in pert.items():
                        sp = lst[i]
                        acc[(st, mt, key)].append((ts, P.rate(flags(mt, sp, sp.own, s, model), S)))
            sg = cg[i]
            wa = ES["common"][0]
            Sa = [w for w in ES["common"] if w >= wa]
            for k, a in C_ATTACK:
                inj = (lambda o: P.inject_step(o, wa, a)) if k == "step" else (lambda o, mm: P.inject_drift(o, wa, a, mm))
                va = inj(sg.own) if k == "step" else inj(sg.own, sm.mean)
                vc = inj(sm.own) if k == "step" else inj(sm.own, sm.mean)
                for mt in METHODS:
                    acc[("with_cm", mt, f"{k}{a}")].append((ts, P.rate(flags(mt, sg, va, s, model), Sa)))
                    acc[("without_cm", mt, f"{k}{a}")].append((ts, P.rate(flags(mt, sm, vc, s, model), Sa)))

    ref = {"spatial": e9rt["common"]["spatial"]["clean_fpr"]["mean"],
           "temporal": e9rt["common"]["temporal"]["clean_fpr"]["mean"],
           "supervised": e9brt["thr_cal"]["common"]["clean_fpr"]["mean"]}
    bad = []
    for mt in METHODS:
        got = P.agg_seed([(sd, v) for sd, v in chk[mt] if v is not None])["mean"]
        if got != ref[mt]:
            bad.append((mt, ref[mt], got))
    print("── 檢查 1（common 後半段乾淨誤報 vs E9_rt／E9b_rt）──", "✗ " + str(bad) if bad else "✓")
    if bad:
        raise SystemExit("先查原因，不寫檔。")

    A = lambda key: P.agg_seed([(sd, v) for sd, v in acc[key] if v is not None])
    keys = ["base"] + [f"step{g}" for g in CM_STEP] + [f"drift{r}" for r in CM_DRIFT]
    res = {"spec": "docs/thesis/planB_realtime_spec.md", "W_ON": W_ON, "n_samples": len(n_eval),
           "common_windows_per_sample": n_eval,
           "alarm": {st: {mt: {k: A((st, mt, k)) for k in keys} for mt in METHODS} for st in ("common", "own")},
           "attack_under_common_mode": {"g": C_G, **{w: {mt: {f"{k}{a}": A((w, mt, f"{k}{a}")) for k, a in C_ATTACK}
                                                        for mt in METHODS} for w in ("with_cm", "without_cm")}},
           "note": "z'_j = g·z_j under multiplicative common mode with frozen s; not cancelled"}
    vals = {f"{st}|{mt}|{k}": res["alarm"][st][mt][k]["mean"] for st in ("common", "own") for mt in METHODS for k in keys}
    res["baseline_status"] = P.check_baseline("E9c_rt", vals, args.set_baseline, note="2026-10-06 人工核對")
    print("── 回歸基準 E9c_rt：", res["baseline_status"], "──\n")
    path = os.path.join(args.out_dir, "E9c_common_mode_rt.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, ensure_ascii=False)
    f = lambda a: f"{a['mean']:.2f}（{a['seed_min']:.2f}–{a['seed_max']:.2f}）"
    print(f"樣本 {len(n_eval)}；評估窗 = w ≥ {W_ON} 之 full-consensus 窗中三方法共同可評估者")
    print(f"{'擾動':>10} | " + " | ".join(f"{m:>20}" for m in METHODS))
    for k in keys:
        print(f"{k:>10} | " + " | ".join(f"{f(res['alarm']['common'][m][k]):>20}" for m in METHODS))
    print(f"\n共模 ×{C_G} 之上注入攻擊（有共模／無共模）")
    for k, a in C_ATTACK:
        print(f"{k}{a:>6} | " + " | ".join(
            f"{res['attack_under_common_mode']['with_cm'][m][f'{k}{a}']['mean']:.2f}／"
            f"{res['attack_under_common_mode']['without_cm'][m][f'{k}{a}']['mean']:.2f}" for m in METHODS))
    print(f"\n寫入 {path}")
    if not args.no_fig:
        draw(res, os.path.join(args.out_dir, "fig_E9c_common_mode_rt.png"))


def draw(res, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    C = {"spatial": "#2b8a3e", "temporal": "#c92a2a", "supervised": "#5f3dc4"}
    LS = {"spatial": "-", "temporal": "--", "supervised": "-."}
    R = res["alarm"]["common"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
    for m in METHODS:
        b = R[m]["base"]["mean"]
        a1.plot([1.0] + CM_STEP, [b] + [R[m][f"step{g}"]["mean"] for g in CM_STEP], marker="o", color=C[m], ls=LS[m], label=m)
        a2.plot([0] + [r * 100 for r in CM_DRIFT], [b] + [R[m][f"drift{r}"]["mean"] for r in CM_DRIFT], marker="o", color=C[m], ls=LS[m])
    a1.set_xlabel("benign common-mode step g (all cells)"); a1.set_ylabel("alarm rate (all false alarms), common set")
    a2.set_xlabel("benign common-mode drift (% per second, all cells)")
    for a in (a1, a2):
        a.grid(alpha=0.3)
    a1.legend(fontsize=8)
    fig.suptitle("Plan B: false alarms under synthetic benign common-mode shifts", fontsize=11)
    fig.tight_layout(); fig.savefig(path, dpi=200)
    print(f"圖已存: {path}")


if __name__ == "__main__":
    main()
