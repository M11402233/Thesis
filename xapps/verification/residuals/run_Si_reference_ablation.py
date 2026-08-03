#!/usr/bin/env python3
"""
run_Si_reference_ablation.py — 參照機制受控消融實驗(S_i 的核心論證)

設計動機:
  原 S_i vs LSTM 對照存在根本性不可比——LSTM 取 LTE 錨點之「吞吐量」(RxBytes),
  S_i 取 mmWave cell 之「延遲」(delay),二者為不同物理量、不同節點、不同注入攻擊,
  其偵測率不應並列比較。

本實驗改採受控消融(controlled ablation):固定資料、尺度、門檻、攻擊,
  僅變動「參照中心」一個變數,以直接檢驗核心主張——
  「偵測能力之差異來自參照機制,而非模型複雜度」。

  空間共識參照  c_j(t) = median{ delay_k(t) : k ∈ A(t)\{j} }   ← 同窗其他節點
  時間自我參照  c_j(t) = median{ delay_j(t-W..t-1) }            ← 自身近期歷史
  兩者共用: 尺度 s = 1.4826·MAD_global(LOSO, 僅由 training seeds 估計)
            門檻 τ_S = 4;殘差 z_j(t) = |delay_j(t) − c_j(t)| / s

  兩種參照使用相同的統計量與複雜度(中位數),故差異不可歸因於模型能力。

輸入: data/si_lstm_seeds/ues1_t300_seed42*.txt
輸出: data/results/Si_reference_ablation.json, fig_Si_reference_ablation.png
"""
import os, glob, json, collections
import numpy as np

DATA_DIR = os.path.expanduser("~/oran-zt-kpm-verification/data/si_lstm_seeds")
OUT_DIR  = os.path.expanduser("~/oran-zt-kpm-verification/data/results")
os.makedirs(OUT_DIR, exist_ok=True)

TAU_S        = 4.0
MIN_NEIGHBOR = 2      # 僅於 full-consensus 窗評估(peer>=2)
W_HIST       = 10     # 時間自我參照之回看窗數(與 LSTM 輸入視窗一致)
DRIFT_RATES  = [0.001, 0.002, 0.005, 0.01, 0.02, 0.04, 0.08, 0.15]


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
            if c == 1:                       # 排除 LTE 錨點,只做 mmWave 跨節點
                continue
            dly[w][c].append(d)
    return {w: {c: float(np.mean(dly[w][c])) * 1000.0 for c in dly[w]} for w in dly}


def global_scale(train):
    a = [v for s in train for w in s for v in s[w].values()]
    m = np.median(a)
    return 1.4826 * (float(np.median(np.abs(np.array(a) - m))) + 1e-9)


def inject_drift(v, t0, rate, mean):
    o = v.copy()
    for t in range(t0, len(o)):
        o[t] += rate * (t - t0) * mean
    return o


def main():
    files = sorted(glob.glob(os.path.join(DATA_DIR, "ues1_t300_seed*.txt"))) or \
            sorted(glob.glob("ues1_t300_seed*.txt"))
    if len(files) < 2:
        print(f"資料不足(找到 {len(files)} 檔)"); return
    seeds = [os.path.basename(f).split("seed")[-1].replace(".txt", "") for f in files]
    data  = {s: load_cell_delay(f) for s, f in zip(seeds, files)}
    print(f"載入 {len(seeds)} seed: {seeds}\n")

    det = {"spatial": {r: [] for r in DRIFT_RATES},
           "temporal": {r: [] for r in DRIFT_RATES}}
    fpr = {"spatial": [], "temporal": []}

    for ts in seeds:                                   # Leave-One-Seed-Out
        s = global_scale([data[x] for x in seeds if x != ts])
        Wd = data[ts]; wins = sorted(Wd)
        cells = set()
        for w in Wd:
            cells |= set(Wd[w])
        for tc in cells:
            idx = [w for w in wins if tc in Wd[w]
                   and len([c for c in Wd[w] if c != tc]) >= MIN_NEIGHBOR]
            if len(idx) < 40:
                continue
            ser = np.array([Wd[w][tc] for w in idx], dtype=float)
            mean = ser.mean(); t0 = len(idx)//2; atk = slice(t0, len(idx))

            def z_spatial(v):     # 中心 = 同窗其他 cell 的中位數
                return np.array([abs(v[i] - np.median([Wd[w][c] for c in Wd[w] if c != tc])) / s
                                 for i, w in enumerate(idx)])

            def z_temporal(v):    # 中心 = 自身前 W_HIST 窗的中位數
                out = []
                for i in range(len(v)):
                    lo = max(0, i - W_HIST)
                    out.append(abs(v[i] - np.median(v[lo:i])) / s if i > 0 else 0.0)
                return np.array(out)

            fpr["spatial"].append(float((z_spatial(ser)[atk] > TAU_S).mean()))
            fpr["temporal"].append(float((z_temporal(ser)[atk] > TAU_S).mean()))
            for r in DRIFT_RATES:
                dv = inject_drift(ser, t0, r, mean)
                det["spatial"][r].append(float((z_spatial(dv)[atk] > TAU_S).mean()))
                det["temporal"][r].append(float((z_temporal(dv)[atk] > TAU_S).mean()))

    n = len(fpr["spatial"])
    summary = {
        "n_samples_seed_x_cell": n, "tau_S": TAU_S, "W_hist": W_HIST,
        "min_neighbors": MIN_NEIGHBOR, "n_seeds": len(seeds),
        "clean_fpr": {k: float(np.mean(v)) for k, v in fpr.items()},
        "drift_detection": {k: {str(r): float(np.mean(det[k][r])) for r in DRIFT_RATES}
                            for k in det},
        "design_note": "identical data/scale/threshold/attack; only the reference center differs",
    }
    with open(os.path.join(OUT_DIR, "Si_reference_ablation.json"), "w") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)

    print(f"樣本(seed×cell) = {n}   (統計單位為 seed,非 {n})")
    print(f"乾淨 FPR: 空間共識={np.mean(fpr['spatial']):.3f}  時間自我={np.mean(fpr['temporal']):.3f}")
    print(f"\n{'漂移速率':>10} {'空間共識':>10} {'時間自我':>10} {'差值':>8}")
    for r in DRIFT_RATES:
        a = np.mean(det["spatial"][r]); b = np.mean(det["temporal"][r])
        print(f"{r*100:>9.1f}% {a:>10.2f} {b:>10.2f} {a-b:>+8.2f}")
    print(f"\n結果寫入 {os.path.join(OUT_DIR,'Si_reference_ablation.json')}")

    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        rates = [r*100 for r in DRIFT_RATES]
        sp = [np.mean(det["spatial"][r])  for r in DRIFT_RATES]
        tp = [np.mean(det["temporal"][r]) for r in DRIFT_RATES]
        fig, ax = plt.subplots(figsize=(8.5, 5))
        ax.axvspan(0, 2.3, color="#f1f3f5", zorder=0)
        ax.text(1.1, 0.05, "low-and-slow\nevasion region", fontsize=8.5,
                color="#868e96", ha="center")
        ax.plot(rates, sp, "o-", color="#2b8a3e", lw=2.2, ms=7,
                label="spatial consensus reference (S_i)", zorder=3)
        ax.plot(rates, tp, "s--", color="#c92a2a", lw=2.0, ms=6,
                label="temporal self-reference (ablation)", zorder=3)
        ax.set_xlabel("drift rate per window (% of mean delay)")
        ax.set_ylabel("detection rate")
        ax.set_title("Reference-mechanism ablation: identical statistic, scale and threshold",
                     fontsize=11)
        ax.set_ylim(-0.05, 1.05); ax.set_xlim(0, max(rates)+0.5)
        ax.legend(loc="lower right", fontsize=9); ax.grid(alpha=0.3, zorder=0)
        fig.tight_layout()
        fig.savefig(os.path.join(OUT_DIR, "fig_Si_reference_ablation.png"), dpi=150)
        print("圖已存: fig_Si_reference_ablation.png")
    except ImportError:
        print("未安裝 matplotlib,略過畫圖")


if __name__ == "__main__":
    main()
