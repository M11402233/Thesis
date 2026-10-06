#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_E9c_common_mode.py — E9c：良性共模擾動下之誤報（第四章 4.7.5.2；補 4.7.5.1 之【待填】）

【要回答的問題】
E9b 顯示以絕對水準為輸入之監督式分類器亦能偵測漸進漂移。本研究主張空間共識參照之一項
設計性質為：**全場域共同之變化（例如負載上升使所有 cell 之 delay 同時上升）會被同窗共識抵銷**，
而以絕對水準或自身歷史為參照者不具此性質。本實驗以合成之良性共模擾動檢驗此性質：
  (a) 良性共模階躍：t ≥ W_ON 時，所有 mmWave cell 之 delay 同乘 g
  (b) 良性共模漂移：t ≥ W_ON 時，所有 mmWave cell 之 delay 同乘 (1 + r·(t − W_ON))
  (c) 共模擾動下之攻擊：共模階躍 g = 1.2 之上，再對受測 cell 注入 E9 之攻擊（階躍或漂移）
  (a)(b) 中任何告警皆為誤報；(c) 檢驗共模擾動是否掩蓋或混淆真攻擊。

【設計】
  資料      D-SH，與 E9／E9b 相同之 seed × cell full-consensus 序列；LOSO
  參照      空間共識（E9）、時間自我參照（E9）、監督式分類器 level 變體（E9b，同一訓練流程與種子）
  擾動時點  W_ON = 150（模擬時間秒；以絕對窗號定義，使所有 cell 同時受影響）
  評估區間  各樣本中 w ≥ W_ON 之 full-consensus 窗；另以同一子集之乾淨資料計算基線，報告差值
  (c) 之攻擊起點：該樣本 w ≥ W_ON 之第一個 full-consensus 窗

【內建一致性檢查】
  1. 空間／時間參照於 E9 評估區間（t0 = len//2）之乾淨誤報率須與 E9_operating_regime.json 逐位相同。
  2. 重新訓練之監督式分類器於 E9 評估區間之乾淨誤報率（thr_cal）須與 E9b_supervised_baseline.json
     逐位相同（同一種子、確定性訓練）。
  任一失敗即停止、不寫檔。

【誠實聲明（寫進論文）】
  - 共模擾動為合成之理想情境：所有 cell 以同一倍率變化。實際之全場域負載變化僅部分相關，
    本實驗之結果為「完全共模」下之行為，不代表真實負載變化下之誤報率。
  - 對空間參照而言，乘法共模擾動仍使殘差 |delay_j − c_j| 同乘 g，故 g 越大其誤報亦略升，非完全抵銷。
  - 監督式分類器之結論限於 E9b 之 level 變體（自身時序之絕對水準為輸入）。

【輸出】
  <out>/E9c_common_mode.json
  <out>/fig_E9c_common_mode.png
"""
import os
import sys
import json
import argparse
import collections
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_E9_operating_regime as E9
from run_E9_operating_regime import load_cell_delay, global_scale, inject_drift, inject_step, TAU_S
from run_slow_poisoning_suite import find_files, build_samples, zfun, agg_seed
import run_E9b_supervised_baseline as B

W_ON = 150
CM_STEP = [1.1, 1.2, 1.3, 1.5]
CM_DRIFT = [0.005, 0.01, 0.02]
C_G = 1.2
C_ATTACK = [("step", 1.3), ("step", 1.5), ("drift", 0.01), ("drift", 0.02)]
METHODS = ("spatial", "temporal", "supervised")
VARIANT = "level"


def common_mode(Wd, kind, mag):
    """對所有 mmWave cell 施加同一乘法擾動（w ≥ W_ON）"""
    out = {}
    for w, row in Wd.items():
        if w >= W_ON:
            f = mag if kind == "step" else (1 + mag * (w - W_ON))
            out[w] = {c: v * f for c, v in row.items()}
        else:
            out[w] = dict(row)
    return out


def train_fold(data, seeds, fi, ts, target_fpr):
    """與 run_E9b_supervised_baseline.run 完全相同之訓練流程（level 變體）"""
    train_seeds = [x for x in seeds if x != ts]
    s = global_scale([data[x] for x in train_seeds])
    train_series = [ser for x in train_seeds for _, _, ser, _ in build_samples(data[x])]
    med = float(np.median(np.concatenate(train_series)))
    fold_seed = B.BASE_SEED + 1000 * fi + B.VARIANTS.index(VARIANT)
    rng = np.random.default_rng(fold_seed)
    X, y, cm = B.build_train(train_series, med, s, VARIANT, rng)
    m = B.train_model(X, y, fold_seed)
    p = B.predict(m, X)
    thr = float(np.quantile(p[cm], 1 - target_fpr))
    return m, s, med, thr


def flags(method, v, pm, s, model):
    if method == "supervised":
        m, med, thr = model
        return B.flags_for(m, v, med, s, VARIANT, thr)
    return zfun(method, v, pm, s) > TAU_S


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=None)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--no-fig", action="store_true")
    args = ap.parse_args()
    out_dir = args.out_dir or E9.OUT_DIR
    files = find_files(args.data_dir)
    if len(files) < 2:
        print("資料不足，用 --data-dir 指定。"); return
    seeds = [os.path.basename(f).split("seed")[-1].replace(".txt", "") for f in files]
    data = {s: load_cell_delay(f) for s, f in zip(seeds, files)}
    e9 = json.load(open(os.path.join(out_dir, "E9_operating_regime.json"), encoding="utf-8"))
    e9b = json.load(open(os.path.join(out_dir, "E9b_supervised_baseline.json"), encoding="utf-8"))
    target_fpr = e9b["target_fpr_from_E9_spatial"]
    print(f"載入 {len(seeds)} seed；W_ON = {W_ON}\n")

    chk = {m: [] for m in METHODS}
    base = {m: [] for m in METHODS}
    cmA = {m: {f"step{g}": [] for g in CM_STEP} | {f"drift{r}": [] for r in CM_DRIFT} for m in METHODS}
    cmA_ex = {m: {k: [] for k in cmA[m]} for m in METHODS}
    cmC = {m: {f"{k}{a}": [] for k, a in C_ATTACK} for m in METHODS}
    cmC_clean = {m: {f"{k}{a}": [] for k, a in C_ATTACK} for m in METHODS}   # 無共模下之同一攻擊
    n_eval = []

    for fi, ts in enumerate(seeds):
        m, s, med, thr = train_fold(data, seeds, fi, ts, target_fpr)
        model = (m, med, thr)
        Wd = data[ts]
        clean = {tc: (idx, ser, pm) for tc, idx, ser, pm in build_samples(Wd)}
        pert = {}
        for g in CM_STEP:
            pert[f"step{g}"] = {tc: (ser, pm) for tc, idx, ser, pm in build_samples(common_mode(Wd, "step", g))}
        for r in CM_DRIFT:
            pert[f"drift{r}"] = {tc: (ser, pm) for tc, idx, ser, pm in build_samples(common_mode(Wd, "drift", r))}
        cg = {tc: (ser, pm) for tc, idx, ser, pm in build_samples(common_mode(Wd, "step", C_G))}

        for tc, (idx, ser, pm) in clean.items():
            t0 = len(ser) // 2
            f0s = {meth: flags(meth, ser, pm, s, model) for meth in METHODS}
            for meth in METHODS:                            # 一致性檢查：涵蓋全部樣本
                chk[meth].append((ts, float(f0s[meth][t0:].mean())))
            post = np.array([w >= W_ON for w in idx])
            if post.sum() < 5:
                continue
            n_eval.append((ts, int(post.sum())))
            ta = int(np.argmax(post))                       # (c) 之攻擊起點
            mean = ser.mean()
            for meth in METHODS:
                f0 = f0s[meth]
                b = float(f0[post].mean())
                base[meth].append((ts, b))
                for key, d in pert.items():
                    v, p2 = d[tc]
                    r_ = float(flags(meth, v, p2, s, model)[post].mean())
                    cmA[meth][key].append((ts, r_))
                    cmA_ex[meth][key].append((ts, r_ - b))
                vg, pg = cg[tc]
                for k, a in C_ATTACK:
                    inj = (lambda x: inject_step(x, ta, a)) if k == "step" else \
                          (lambda x, mm: inject_drift(x, ta, a, mm))
                    va = inj(vg) if k == "step" else inj(vg, vg.mean())
                    vc = inj(ser) if k == "step" else inj(ser, mean)
                    cmC[meth][f"{k}{a}"].append((ts, float(flags(meth, va, pg, s, model)[ta:].mean())))
                    cmC_clean[meth][f"{k}{a}"].append((ts, float(flags(meth, vc, pm, s, model)[ta:].mean())))

    # ---- 一致性檢查 ----
    bad = []
    for meth, ref in (("spatial", e9["clean_fpr"]["spatial"]["mean"]),
                      ("temporal", e9["clean_fpr"]["temporal"]["mean"]),
                      ("supervised", e9b["results"][VARIANT]["thr_cal"]["clean_fpr"]["mean"])):
        got = float(np.mean([v for _, v in chk[meth]]))
        if abs(got - ref) > 1e-12:
            bad.append((meth, ref, got))
    print("── 一致性檢查（E9 評估區間之乾淨誤報率 vs E9／E9b 輸出）──")
    if bad:
        for b_ in bad:
            print("  ✗", b_)
        raise SystemExit("不一致，停止，不寫檔。")
    print("  ✓ 空間、時間、監督式三者逐位相同\n")

    res = {"W_ON": W_ON, "variant": VARIANT, "tau_S": TAU_S,
           "n_samples": len(n_eval), "post_windows_per_sample": n_eval,
           "baseline_post_alarm": {m: agg_seed(base[m]) for m in METHODS},
           "common_mode_alarm": {m: {k: agg_seed(v) for k, v in cmA[m].items()} for m in METHODS},
           "common_mode_excess_alarm": {m: {k: agg_seed(v) for k, v in cmA_ex[m].items()} for m in METHODS},
           "attack_under_common_mode": {"g": C_G,
                                        "with_cm": {m: {k: agg_seed(v) for k, v in cmC[m].items()} for m in METHODS},
                                        "without_cm": {m: {k: agg_seed(v) for k, v in cmC_clean[m].items()} for m in METHODS}},
           "consistency": "ok",
           "note": ("synthetic ideal common-mode (all mmWave cells scaled identically from W_ON); "
                    "any alarm under (a)(b) is a false alarm")}
    path = os.path.join(out_dir, "E9c_common_mode.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, ensure_ascii=False)

    f = lambda a: f"{a['mean']:.2f}（{a['seed_min']:.2f}–{a['seed_max']:.2f}）"
    print(f"樣本 {len(n_eval)}；評估區間 = 各樣本 w ≥ {W_ON} 之 full-consensus 窗")
    print("\n══ 良性共模擾動下之告警率（皆為誤報）══")
    print(f"{'擾動':>10} | " + " | ".join(f"{m:>22}" for m in METHODS))
    print(f"{'無（基線）':>10} | " + " | ".join(f"{f(res['baseline_post_alarm'][m]):>22}" for m in METHODS))
    for k in cmA["spatial"]:
        print(f"{k:>10} | " + " | ".join(f"{f(res['common_mode_alarm'][m][k]):>22}" for m in METHODS))
    print(f"\n══ 共模階躍 g = {C_G} 之上注入攻擊：偵測率（有共模／無共模）══")
    for k in cmC["spatial"]:
        print(f"{k:>10} | " + " | ".join(
            f"{res['attack_under_common_mode']['with_cm'][m][k]['mean']:.2f}／"
            f"{res['attack_under_common_mode']['without_cm'][m][k]['mean']:.2f}" for m in METHODS))
    print(f"\n寫入 {path}")
    if not args.no_fig:
        draw(res, out_dir)


def draw(res, out_dir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    C = {"spatial": "#2b8a3e", "temporal": "#c92a2a", "supervised": "#5f3dc4"}
    LS = {"spatial": "-", "temporal": "--", "supervised": "-."}
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
    for m in METHODS:
        b = res["baseline_post_alarm"][m]["mean"]
        a1.plot([1.0] + CM_STEP, [b] + [res["common_mode_alarm"][m][f"step{g}"]["mean"] for g in CM_STEP],
                marker="o", color=C[m], ls=LS[m], label=m)
        a2.plot([0] + [r * 100 for r in CM_DRIFT],
                [b] + [res["common_mode_alarm"][m][f"drift{r}"]["mean"] for r in CM_DRIFT],
                marker="o", color=C[m], ls=LS[m])
    a1.set_xlabel("benign common-mode step g (all cells)"); a1.set_ylabel("alarm rate (all false alarms)")
    a2.set_xlabel("benign common-mode drift (%/window, all cells)")
    for a in (a1, a2):
        a.grid(alpha=0.3)
    a1.legend(fontsize=8)
    fig.suptitle("E9c false alarms under synthetic benign common-mode shifts", fontsize=11)
    fig.tight_layout(); fig.savefig(os.path.join(out_dir, "fig_E9c_common_mode.png"), dpi=200)
    print(f"圖已存: {out_dir}/fig_E9c_common_mode.png")


if __name__ == "__main__":
    main()
