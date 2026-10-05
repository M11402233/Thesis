#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_E9_operating_regime.py — E9：既有工作之攻擊模型下的操作區對照（第四章 4.7.5）

【要回答的問題】
既有 KPM 中毒偵測（Alimohammadi et al., FNWF 2024 / arXiv 2512.01596）之評估採放大因子
AF = 1.2 / 1.3 / 1.4 / 1.5 的「階躍」注入。4.7.4 已顯示時間自我參照之失效集中在低速漂移。
本實驗檢驗：既有工作之評估是否恰好落在「兩種參照皆有效」的高幅度區間。

【設計：完全沿用 4.7.4，只擴充攻擊族】
  資料      D-SH（ues1_t300_seed42*.txt），LOSO
  尺度      s = 1.4826·MAD_global（僅由 training seeds 估計）
  門檻      τ_S = 4
  評估範圍  僅 full-consensus 窗（peer ≥ 2）
  評估區間  序列後半段（注入區間）
  參照      空間：同窗其他 cell 中位數　vs　時間：自身前 W=10 窗中位數
  攻擊族    (a) 階躍放大：t ≥ t0 時 delay × AF，AF ∈ {1.2,1.3,1.4,1.5}
            (b) 漸進漂移：同 4.7.4，r ∈ {0.1,…,15}%/窗

【內建一致性檢查】
漂移族之結果必須逐位重現 4.7.4 之表格（0.04/0.09/0.26/0.54/0.74/0.86/0.93/0.96 等）。
若不一致，代表實作與 4.7.4 有差異，E9 之結果不可與 4.7.4 並列——腳本會印出警告。

【誠實聲明（寫進論文）】
既有工作放大的是目標 UE 之多項 KPM 分布的平均與共變異數；本實驗僅放大受測 cell 之 delay，
屬「同型攻擊於本研究觀測維度上之對應」，而非其實驗之重現。本實驗比較兩種參照機制，
不比較本研究與既有工作之偵測器效能。

【輸出】
  <out>/E9_operating_regime.json      全部數字（含 per-seed，供 CI／誤差棒）
  <out>/fig_E9_operating_regime.png   Fig 4-6：左區漂移、右區階躍，共用 y 軸

跑法：
  python3 run_E9_operating_regime.py
  python3 run_E9_operating_regime.py --data-dir ./seeds/si_lstm_seeds --out-dir ./results
"""
import os
import glob
import json
import argparse
import collections
import numpy as np

DATA_DIR = os.path.expanduser("~/oran-zt-kpm-verification/data/si_lstm_seeds")
OUT_DIR = os.path.expanduser("~/oran-zt-kpm-verification/data/results")

# ---- 與 run_Si_reference_ablation.py 完全相同之參數 ----
TAU_S = 4.0
MIN_NEIGHBOR = 2
W_HIST = 10
MIN_LEN = 40
DRIFT_RATES = [0.001, 0.002, 0.005, 0.01, 0.02, 0.04, 0.08, 0.15]
# ---- E9 新增 ----
STEP_AFS = [1.2, 1.3, 1.4, 1.5]
ONSET_K = 5          # onset 命中：注入後前 5 窗內至少觸發一次

# 4.7.4 已發表之數字（兩位小數），用於一致性檢查
PUBLISHED_474 = {
    "spatial":  {0.001: 0.04, 0.002: 0.09, 0.005: 0.26, 0.01: 0.54,
                 0.02: 0.74, 0.04: 0.86, 0.08: 0.93, 0.15: 0.96},
    "temporal": {0.001: 0.01, 0.002: 0.01, 0.005: 0.01, 0.01: 0.01,
                 0.02: 0.01, 0.04: 0.14, 0.08: 0.92, 0.15: 0.95},
}


# ==========================================================================
# 資料載入與尺度（逐字沿用 run_Si_reference_ablation.py）
# ==========================================================================
def load_cell_delay(path):
    dly = collections.defaultdict(lambda: collections.defaultdict(list))
    with open(path) as fh:
        fh.readline()
        for line in fh:
            p = line.split("\t")
            if len(p) < 11:
                continue
            try:
                w = int(float(p[0])); c = int(p[2]); d = float(p[10])
            except ValueError:
                continue
            if c == 1:
                continue
            dly[w][c].append(d)
    return {w: {c: float(np.mean(dly[w][c])) * 1000.0 for c in dly[w]} for w in dly}


def global_scale(train):
    a = [v for s in train for w in s for v in s[w].values()]
    m = np.median(a)
    return 1.4826 * (float(np.median(np.abs(np.array(a) - m))) + 1e-9)


# ==========================================================================
# 攻擊注入
# ==========================================================================
def inject_drift(v, t0, rate, mean):
    """與 4.7.4 相同：偏移每窗遞增 rate × mean"""
    o = v.copy()
    for t in range(t0, len(o)):
        o[t] += rate * (t - t0) * mean
    return o


def inject_step(v, t0, af):
    """既有工作之攻擊模型於 delay 維度之對應：注入起點後乘以放大因子"""
    o = v.copy()
    o[t0:] = o[t0:] * af
    return o


# ==========================================================================
# 兩種參照（邏輯與 4.7.4 相同）
# ==========================================================================
def make_refs(Wd, idx, tc, s):
    peer_med = np.array([np.median([Wd[w][c] for c in Wd[w] if c != tc]) for w in idx])

    def z_spatial(v):
        return np.abs(v - peer_med) / s

    def z_temporal(v):
        out = np.zeros(len(v))
        for i in range(1, len(v)):
            lo = max(0, i - W_HIST)
            out[i] = abs(v[i] - np.median(v[lo:i])) / s
        return out

    return z_spatial, z_temporal


# ==========================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=None)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--no-fig", action="store_true")
    args = ap.parse_args()

    out_dir = args.out_dir or OUT_DIR
    os.makedirs(out_dir, exist_ok=True)

    search = [args.data_dir] if args.data_dir else [
        DATA_DIR, os.path.join("seeds", "si_lstm_seeds"), "."]
    files = []
    for d in search:
        files = sorted(glob.glob(os.path.join(d, "ues1_t300_seed*.txt")))
        if len(files) >= 2:
            break
    if len(files) < 2:
        print(f"資料不足(找到 {len(files)} 檔)。用 --data-dir 指定。")
        return
    seeds = [os.path.basename(f).split("seed")[-1].replace(".txt", "") for f in files]
    data = {s: load_cell_delay(f) for s, f in zip(seeds, files)}
    print(f"載入 {len(seeds)} seed: {seeds}\n")

    refs = ("spatial", "temporal")
    # det[ref][family][param] = list of (seed, value)
    det = {r: {"drift": collections.defaultdict(list),
               "step": collections.defaultdict(list)} for r in refs}
    onset = {r: collections.defaultdict(list) for r in refs}
    fpr = {r: [] for r in refs}
    n_samples = 0

    for ts in seeds:                                          # LOSO
        s = global_scale([data[x] for x in seeds if x != ts])
        Wd = data[ts]; wins = sorted(Wd)
        cells = set()
        for w in Wd:
            cells |= set(Wd[w])
        for tc in cells:
            idx = [w for w in wins if tc in Wd[w]
                   and len([c for c in Wd[w] if c != tc]) >= MIN_NEIGHBOR]
            if len(idx) < MIN_LEN:
                continue
            n_samples += 1
            ser = np.array([Wd[w][tc] for w in idx], dtype=float)
            mean = ser.mean(); t0 = len(idx) // 2; atk = slice(t0, len(idx))
            zs, zt = make_refs(Wd, idx, tc, s)
            zfun = {"spatial": zs, "temporal": zt}

            for r in refs:
                fpr[r].append((ts, float((zfun[r](ser)[atk] > TAU_S).mean())))
                for rate in DRIFT_RATES:
                    z = zfun[r](inject_drift(ser, t0, rate, mean))
                    det[r]["drift"][rate].append((ts, float((z[atk] > TAU_S).mean())))
                for af in STEP_AFS:
                    z = zfun[r](inject_step(ser, t0, af))
                    det[r]["step"][af].append((ts, float((z[atk] > TAU_S).mean())))
                    onset[r][af].append(
                        (ts, float((z[t0:t0 + ONSET_K] > TAU_S).any())))

    # ---------------- 彙整：macro 平均 + per-seed 範圍 ----------------
    def agg(pairs):
        vals = [v for _, v in pairs]
        by_seed = collections.defaultdict(list)
        for sd, v in pairs:
            by_seed[sd].append(v)
        seed_means = [float(np.mean(v)) for v in by_seed.values()]
        return {"mean": float(np.mean(vals)),
                "seed_min": float(min(seed_means)), "seed_max": float(max(seed_means)),
                "per_seed": {sd: float(np.mean(v)) for sd, v in by_seed.items()}}

    res = {
        "n_samples_seed_x_cell": n_samples, "n_seeds": len(seeds),
        "tau_S": TAU_S, "W_hist": W_HIST, "min_neighbors": MIN_NEIGHBOR,
        "onset_k": ONSET_K,
        "clean_fpr": {r: agg(fpr[r]) for r in refs},
        "drift": {r: {str(k): agg(v) for k, v in det[r]["drift"].items()} for r in refs},
        "step": {r: {str(k): agg(v) for k, v in det[r]["step"].items()} for r in refs},
        "step_onset_hit": {r: {str(k): agg(v) for k, v in onset[r].items()} for r in refs},
        "note": ("delay-dimension analogue of the prior-work step attack; "
                 "compares reference mechanisms, not detectors"),
    }

    # ---------------- 一致性檢查：漂移族須重現 4.7.4 ----------------
    mismatch = []
    for r in refs:
        for rate, pub in PUBLISHED_474[r].items():
            got = round(res["drift"][r][str(rate)]["mean"], 2)
            if abs(got - pub) > 0.005:
                mismatch.append((r, rate, pub, got))
    res["consistency_with_4_7_4"] = "ok" if not mismatch else mismatch

    with open(os.path.join(out_dir, "E9_operating_regime.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, ensure_ascii=False)

    # ---------------- 輸出 ----------------
    print(f"樣本 (seed×cell) = {n_samples}（統計單位為 seed）")
    print(f"乾淨 FPR（注入區間）: 空間 {res['clean_fpr']['spatial']['mean']:.3f}  "
          f"時間 {res['clean_fpr']['temporal']['mean']:.3f}\n")

    print("── 一致性檢查（漂移族 vs 4.7.4 已發表數字）──")
    if not mismatch:
        print("  ✓ 全部吻合，E9 與 4.7.4 為同一實作，可並列呈現\n")
    else:
        print("  ✗ 不一致，請先排查再使用 E9 結果：")
        for m in mismatch:
            print(f"    {m[0]} rate={m[1]}: 已發表 {m[2]} / 本次 {m[3]}")
        print()

    print("── 階躍放大族（4.7.5 結果表）──")
    print(f"{'AF':>5} {'空間':>7} {'時間':>7} {'差值':>7} {'時間 onset':>11}  seed 範圍(空間 / 時間)")
    for af in STEP_AFS:
        a = res["step"]["spatial"][str(af)]; b = res["step"]["temporal"][str(af)]
        o = res["step_onset_hit"]["temporal"][str(af)]
        print(f"{af:>5.1f} {a['mean']:>7.2f} {b['mean']:>7.2f} {a['mean']-b['mean']:>+7.2f} "
              f"{o['mean']:>11.2f}  [{a['seed_min']:.2f}–{a['seed_max']:.2f}] / "
              f"[{b['seed_min']:.2f}–{b['seed_max']:.2f}]")

    print("\n── 漸進漂移族（應與 4.7.4 相同）──")
    print(f"{'速率':>7} {'空間':>7} {'時間':>7} {'差值':>7}")
    for rate in DRIFT_RATES:
        a = res["drift"]["spatial"][str(rate)]["mean"]
        b = res["drift"]["temporal"][str(rate)]["mean"]
        print(f"{rate*100:>6.1f}% {a:>7.2f} {b:>7.2f} {a-b:>+7.2f}")
    print(f"\n寫入 {os.path.join(out_dir, 'E9_operating_regime.json')}")

    if args.no_fig:
        return
    draw(res, os.path.join(out_dir, "fig_E9_operating_regime.png"))


def draw(res, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    C_SP, C_TP = "#2b8a3e", "#c92a2a"
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.8), sharey=True,
                                   gridspec_kw={"width_ratios": [1.6, 1], "wspace": 0.06})

    # 左區：漸進漂移
    x = [r * 100 for r in DRIFT_RATES]
    for ref, col, mk, ls, lab in (("spatial", C_SP, "o", "-", "spatial consensus reference"),
                                  ("temporal", C_TP, "s", "--", "temporal self-reference")):
        m = [res["drift"][ref][str(r)]["mean"] for r in DRIFT_RATES]
        lo = [res["drift"][ref][str(r)]["seed_min"] for r in DRIFT_RATES]
        hi = [res["drift"][ref][str(r)]["seed_max"] for r in DRIFT_RATES]
        ax1.plot(x, m, marker=mk, ls=ls, color=col, lw=2, ms=6, label=lab, zorder=3)
        ax1.fill_between(x, lo, hi, color=col, alpha=0.12, zorder=1)
    ax1.set_xscale("log")
    ax1.set_xticks(x)
    ax1.set_xticklabels([f"{v:g}" for v in x])
    ax1.axvspan(min(x) * 0.8, 2.3, color="#f1f3f5", zorder=0)
    ax1.text(0.35, 0.03, "low-and-slow region", fontsize=8.5, color="#868e96")
    ax1.set_xlabel("gradual drift: rate per window (% of mean delay, log)")
    ax1.set_ylabel("detection rate (injection interval)")
    ax1.set_ylim(-0.04, 1.04)
    ax1.grid(alpha=0.3, zorder=0)
    ax1.set_title("this work's attack family", fontsize=10.5)

    # 右區：階躍放大
    xs = list(range(len(STEP_AFS)))
    for ref, col, mk, ls in (("spatial", C_SP, "o", "-"), ("temporal", C_TP, "s", "--")):
        m = [res["step"][ref][str(a)]["mean"] for a in STEP_AFS]
        lo = [res["step"][ref][str(a)]["seed_min"] for a in STEP_AFS]
        hi = [res["step"][ref][str(a)]["seed_max"] for a in STEP_AFS]
        ax2.plot(xs, m, marker=mk, ls=ls, color=col, lw=2, ms=6, zorder=3)
        ax2.fill_between(xs, lo, hi, color=col, alpha=0.12, zorder=1)
    om = [res["step_onset_hit"]["temporal"][str(a)]["mean"] for a in STEP_AFS]
    ax2.plot(xs, om, marker="^", ls=":", color=C_TP, lw=1.4, ms=6, alpha=0.8,
             label="temporal: onset hit (first 5 windows)", zorder=3)
    ax2.set_xticks(xs)
    ax2.set_xticklabels([f"×{a}" for a in STEP_AFS])
    ax2.set_xlabel("step amplification factor (prior-work attack model)")
    ax2.grid(alpha=0.3, zorder=0)
    ax2.set_title("prior-work attack family (delay analogue)", fontsize=10.5)

    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    fig.legend(h1 + h2, l1 + l2, loc="lower center", ncol=3, fontsize=9,
               bbox_to_anchor=(0.5, 0.0), frameon=False)
    fig.suptitle("Two reference mechanisms under gradual drift and step amplification "
                 "(identical data, scale, threshold; shaded = seed range)", fontsize=11)
    fig.subplots_adjust(left=0.07, right=0.98, top=0.86, bottom=0.22, wspace=0.06)
    fig.savefig(path, dpi=200)
    print(f"圖已存: {path}")


if __name__ == "__main__":
    main()
