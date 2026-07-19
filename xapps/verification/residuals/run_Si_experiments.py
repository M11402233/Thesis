#!/usr/bin/env python3
"""
run_Si_experiments.py — S_i 跨節點空間一致性殘差:定義與驗證(對 attack type B)
版本 v2:改為「真空間」設計 — 中心取自同窗其他 cell,回應 review 對「是否 spatial」的質疑。

S_i 定義(v2 定案):
  對受測 cell j 於窗 t:
     中心  c_j(t) = median{ delay_k(t) : k 為同窗其他活躍 mmWave cell }   ← 真空間(同一時刻跨節點)
     尺度  s      = 1.4826 · MAD_global(乾淨訓練資料全 cell 全窗的 delay)  ← 全域穩定尺度
     殘差  z_j(t) = | delay_j(t) − c_j(t) | / s
     S_i violated ⟺ z_j(t) > θ    (θ=4;每個窗獨立判定,不累積)

  為何中心用同窗跨 cell、尺度用全域:
    中心必須是「此刻其他節點」才算 spatial consistency(回應 review A/第二份 review)。
    但同窗活躍 cell 數少(N≤7),即時 MAD 有小樣本高變異問題,推升 FPR(0.14–0.20);
    故尺度改由全域乾淨資料估計(大樣本、穩定),此為 pooled/shrinkage scale 的標準作法。
    1.4826 使 MAD 成為常態下標準差的漸近一致估計量。

  為何以延遲為偵測維度(empirical observability,非攻擊知識):
    探勘顯示 delay 場域 CV≈0.12(緊約束)、per-UE 吞吐 CV≈0.62(過鬆)。固定/空間參照
    對 delay 有意義、對吞吐則過寬。此專門化由「哪個量在物理上可觀測地穩定」決定,
    而非因為預先知道攻擊落在 delay。純吞吐竄改(type B2)在 RLC-only(無 PRB/CQI)資料上
    無可用不變量,列為限制與未來工作(MAC-layer SM 取 PRB)。

輸入:data/si_lstm_seeds/ues1_t300_seed42*.txt
輸出:data/results/Si_experiment_results.json, fig_Si_vs_lstm_delay.png
"""
import os, glob, json, collections
import numpy as np

DATA_DIR = os.path.expanduser("~/oran-zt-kpm-verification/data/si_lstm_seeds")
OUT_DIR = os.path.expanduser("~/oran-zt-kpm-verification/data/results")
os.makedirs(OUT_DIR, exist_ok=True)

DRIFT_RATES = [0.005, 0.01, 0.02, 0.04, 0.08, 0.15]
THRESHOLD = 4.0
MIN_NEIGHBORS = 2
STEP_FRAC = 0.5
LSTM_REF = {0.005: 0.07, 0.01: 0.17, 0.02: 0.44, 0.04: 0.67, 0.08: 0.84, 0.15: 0.91}
LSTM_FPR = 0.02


def load_cell_delay_per_window(path):
    dly = collections.defaultdict(lambda: collections.defaultdict(list))
    with open(path) as fh:
        fh.readline()
        for line in fh:
            p = line.split("\t")
            if len(p) < 11:
                continue
            try:
                w = int(float(p[0])); cell = int(p[2]); d = float(p[10])
            except ValueError:
                continue
            if cell == 1:
                continue
            dly[w][cell].append(d)
    out = {}
    for w in dly:
        out[w] = {c: float(np.mean(dly[w][c])) * 1000.0 for c in dly[w]}
    return out


def inject_step(v, t0, frac, mean):
    o = v.copy(); o[t0:] += frac * mean; return o


def inject_drift(v, t0, rate, mean):
    o = v.copy()
    for t in range(t0, len(o)):
        o[t] += rate * (t - t0) * mean
    return o


def global_scale(train_data):
    allv = []
    for s in train_data:
        for w in train_data[s]:
            for c in train_data[s][w]:
                allv.append(train_data[s][w][c])
    med = np.median(allv)
    return 1.4826 * (float(np.median(np.abs(np.array(allv) - med))) + 1e-9)


def main():
    files = sorted(glob.glob(os.path.join(DATA_DIR, "ues1_t300_seed*.txt")))
    if not files:
        files = sorted(glob.glob("ues1_t300_seed*.txt"))
    if len(files) < 2:
        print(f"資料不足(找到 {len(files)} 檔),至少需 2 個 seed。"); return
    seeds = [os.path.basename(f).split("seed")[-1].replace(".txt", "") for f in files]
    data = {s: load_cell_delay_per_window(f) for s, f in zip(seeds, files)}
    print(f"載入 {len(seeds)} 個 seed:{seeds}")

    det = {r: [] for r in DRIFT_RATES}; fpr, step = [], []
    for ts in seeds:                                   # Leave-One-Seed-Out
        scale = global_scale({s: data[s] for s in seeds if s != ts})
        W = data[ts]; wins = sorted(W)
        cells = set()
        for w in W:
            cells |= set(W[w])
        for tc in cells:
            idx = [w for w in wins if tc in W[w]
                   and len([c for c in W[w] if c != tc]) >= MIN_NEIGHBORS]
            if len(idx) < 40:
                continue
            series = np.array([W[w][tc] for w in idx], dtype=float)
            mean = series.mean(); t0 = len(idx) // 2; atk = slice(t0, len(idx))

            def zseq(vals):
                return np.array([abs(vals[i] - np.median([W[w][c] for c in W[w] if c != tc])) / scale
                                 for i, w in enumerate(idx)])
            fpr.append(float((zseq(series)[atk] > THRESHOLD).mean()))
            step.append(float((zseq(inject_step(series, t0, STEP_FRAC, mean))[atk] > THRESHOLD).mean()))
            for r in DRIFT_RATES:
                det[r].append(float((zseq(inject_drift(series, t0, r, mean))[atk] > THRESHOLD).mean()))

    summary = {
        "n_samples": len(fpr), "threshold": THRESHOLD, "min_neighbors": MIN_NEIGHBORS,
        "design": "center = same-window cross-cell median (spatial); scale = global clean MAD",
        "Si_fpr": float(np.mean(fpr)), "Si_step_detection": float(np.mean(step)),
        "Si_drift_detection": {str(r): float(np.mean(det[r])) for r in DRIFT_RATES},
        "lstm_ref_drift_detection": {str(r): LSTM_REF[r] for r in DRIFT_RATES},
        "lstm_ref_fpr": LSTM_FPR,
        "scope_note": "Advantage on DELAY tampering (B1). Throughput tampering (B2) has no "
                      "usable invariant on RLC-only data (no PRB/CQI) — see 4.6.5.",
    }
    with open(os.path.join(OUT_DIR, "Si_experiment_results.json"), "w") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)

    print(f"\n  樣本(seed×cell)={summary['n_samples']}  S_i FPR={summary['Si_fpr']:.3f} (LSTM {LSTM_FPR})  階梯={summary['Si_step_detection']:.2f}")
    for r in DRIFT_RATES:
        s = summary["Si_drift_detection"][str(r)]
        print(f"  漂移 {r*100:>4.1f}% : S_i={s:.2f}  vs  LSTM={LSTM_REF[r]:.2f}  (絕對增益 +{s-LSTM_REF[r]:.2f})")

    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        rates = [r * 100 for r in DRIFT_RATES]
        si = [summary["Si_drift_detection"][str(r)] for r in DRIFT_RATES]
        lstm = [LSTM_REF[r] for r in DRIFT_RATES]
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.axvspan(0, 2.3, color="#eeeeee", zorder=0)
        ax.plot(rates, si, "o-", color="#2b8a3e", lw=2.2, ms=7, label="S_i spatial residual (delay)", zorder=3)
        ax.plot(rates, lstm, "s--", color="#c92a2a", lw=2, ms=6, label="LSTM single-node temporal", zorder=3)
        ax.set_xlabel("drift rate per window (% of mean)")
        ax.set_ylabel("detection rate")
        ax.set_title("Detection performance against gradual delay drift")
        ax.set_ylim(-0.05, 1.05); ax.set_xlim(0, max(rates) + 0.5)
        ax.legend(loc="center right"); ax.grid(alpha=0.3, zorder=0)
        fig.tight_layout(); fig.savefig(os.path.join(OUT_DIR, "fig_Si_vs_lstm_delay.png"), dpi=150)
        print("圖已存:fig_Si_vs_lstm_delay.png")
    except ImportError:
        print("未安裝 matplotlib,略過畫圖")


if __name__ == "__main__":
    main()
