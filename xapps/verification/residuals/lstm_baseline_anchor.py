#!/usr/bin/env python3
"""
lstm_baseline_anchor.py — 單節點時序 LSTM 基準(重現 Alimohammadi 風格),跑在 LTE 錨點序列上

角色定位:這是論文的「被規避的對照組」。它的任務不是抓到所有攻擊,而是要展示
        「單節點時序方法對緩慢漂移天生無力」——LSTM 會逐步把漂移學成正常,
        使漂移偏移留在重建/預測誤差門檻之內而不被觸發。這正是三殘差(S_i/C_i)
        相對時序方法的核心增量論證。

為什麼跑在 cell 1(LTE 錨點)而不是 mmWave cell:
        已驗證你的 mmWave cell 序列又薄又斷續(1 UE/cell、常常整段空窗),
        訓練不出有意義的 LSTM。cell 1 每個 seed 都有 299–300 個連續窗、
        CV≈0.65–0.70,是唯一夠密夠連續的單節點序列。這也符合 Alimohammadi
        單節點時序偵測的原始設定。

本版新增(回應 review):step attack 拆兩口徑,避免『0.07 被誤解為連階梯都抓不到』——
    - step_full : 整段攻擊窗偵測率(原數字);因階梯偏移進入輸入視窗後被吸收為新基準而偏低
    - step_onset(k): 注入後前 k 窗內是否『至少觸發一次』;若 onset≫full,證明起始點其實被抓到
    LSTM 為離線一次訓練、測試時凍結(no online update);其對緩慢漂移失效源於滑動輸入視窗
    吸收漂移,而非線上 re-baseline。

輸入:data/si_lstm_seeds/ues1_t300_seed42*.txt(你已收集的 4 個 300s seed)
輸出:
    data/results/lstm_baseline_results.json
    data/results/fig_lstm_drift_evasion.png   ← 核心圖:偵測率 vs 漂移速率

依賴:numpy, torch, matplotlib
    pip install torch numpy matplotlib --break-system-packages
    (torch 只需 CPU 版即可,序列很短,不需要 GPU)

跑法:
    cd ~/oran-zt-kpm-verification
    python3 xapps/verification/residuals/lstm_baseline_anchor.py
"""
import os
import sys
import glob
import json
import collections
import numpy as np

DATA_DIR = os.path.expanduser("~/oran-zt-kpm-verification/data/si_lstm_seeds")
OUT_DIR = os.path.expanduser("~/oran-zt-kpm-verification/data/results")
os.makedirs(OUT_DIR, exist_ok=True)

WINDOW = 10          # LSTM 看前 10 個窗預測下一窗
EPOCHS = 60
HIDDEN = 32
SEED = 0
ONSET_K = [1, 2, 3, 5]   # onset 判定:注入後前 k 個可預測窗內是否『至少觸發一次』

np.random.seed(SEED)


# ----------------------------------------------------------------------
# 1. 資料:抽 cell 1(LTE 錨點)每窗聚合 DL 吞吐量序列(Mbit/window)
# ----------------------------------------------------------------------
def load_anchor_series(path: str) -> np.ndarray:
    win_rx = collections.defaultdict(float)
    with open(path) as fh:
        fh.readline()  # 跳過 % 表頭
        for line in fh:
            p = line.split("\t")
            if len(p) < 11:
                continue
            try:
                start = int(float(p[0])); cell = int(p[2]); rx = float(p[9])
            except ValueError:
                continue
            if cell != 1:            # 只取 LTE 錨點
                continue
            win_rx[start] += rx
    wins = sorted(win_rx)
    return np.array([win_rx[w] * 8 / 1e6 for w in wins], dtype=float)


def load_all():
    files = sorted(glob.glob(os.path.join(DATA_DIR, "ues1_t300_seed*.txt")))
    if not files:
        # 後備:也接受放在 uploads 或當前目錄的檔案
        files = sorted(glob.glob("ues1_t300_seed*.txt"))
    series = {}
    for f in files:
        seed = os.path.basename(f).split("seed")[-1].replace(".txt", "")
        s = load_anchor_series(f)
        if len(s) >= 100:
            series[seed] = s
    return series


# ----------------------------------------------------------------------
# 2. 攻擊注入(attack type B:竄改吞吐量數值)
# ----------------------------------------------------------------------
def inject_step(series, t0, frac):
    """突發階梯:t0 起整段 +frac*mean(一次到位的大偏移,LSTM 應該抓得到)"""
    out = series.copy()
    out[t0:] += frac * series.mean()
    return out


def inject_drift(series, t0, rate):
    """緩慢漂移:t0 起每窗遞增 rate*mean(漂移速率越小,LSTM 越可能學成正常)"""
    out = series.copy()
    for t in range(t0, len(out)):
        out[t] += rate * (t - t0) * series.mean()
    return out


# ----------------------------------------------------------------------
# 3. LSTM 預測器(torch)
# ----------------------------------------------------------------------
def build_and_train(train_series_list):
    import torch
    import torch.nn as nn

    torch.manual_seed(SEED)

    class LSTMPredictor(nn.Module):
        def __init__(self, hidden=HIDDEN):
            super().__init__()
            self.lstm = nn.LSTM(1, hidden, batch_first=True)
            self.fc = nn.Linear(hidden, 1)

        def forward(self, x):
            out, _ = self.lstm(x)
            return self.fc(out[:, -1, :]).squeeze(-1)

    # 用所有訓練序列的均值/標準差做標準化(存起來,測試時共用)
    concat = np.concatenate(train_series_list)
    mu, sd = concat.mean(), concat.std() + 1e-9

    def to_windows(series):
        s = (series - mu) / sd
        X = np.array([s[i:i + WINDOW] for i in range(len(s) - WINDOW)])
        y = np.array([s[i + WINDOW] for i in range(len(s) - WINDOW)])
        return X[..., None], y

    Xs, ys = [], []
    for s in train_series_list:
        X, y = to_windows(s)
        Xs.append(X); ys.append(y)
    X = torch.tensor(np.concatenate(Xs), dtype=torch.float32)
    y = torch.tensor(np.concatenate(ys), dtype=torch.float32)

    model = LSTMPredictor()
    opt = torch.optim.Adam(model.parameters(), lr=1e-2)
    lossf = nn.MSELoss()
    for ep in range(EPOCHS):
        model.train()
        opt.zero_grad()
        pred = model(X)
        loss = lossf(pred, y)
        loss.backward()
        opt.step()
    model.eval()

    # 用訓練殘差定門檻:mean + 3*std(標準的無監督異常門檻)
    with torch.no_grad():
        resid = (model(X).numpy() - y.numpy())
    thr = np.abs(resid).mean() + 3 * np.abs(resid).std()
    return model, (mu, sd), thr


def anomaly_flags(model, norm, thr, series):
    """回傳每個可預測窗是否被判為異常(True=偵測到)"""
    import torch
    mu, sd = norm
    s = (series - mu) / sd
    X = np.array([s[i:i + WINDOW] for i in range(len(s) - WINDOW)])
    y = np.array([s[i + WINDOW] for i in range(len(s) - WINDOW)])
    with torch.no_grad():
        pred = model(torch.tensor(X[..., None], dtype=torch.float32)).numpy()
    resid = np.abs(pred - y)
    return resid > thr    # 布林陣列,長度 = len(series)-WINDOW


def onset_and_full(flags, t0):
    """把偵測拆成兩個口徑,回應 review『0.07 被誤解』:
       - full : 整段攻擊窗的偵測率 (= flags[atk_region].mean(),原本報的數字)
       - onset: 注入後前 k 個可預測窗內『至少觸發一次』(命中=1/未命中=0)
       座標對齊:flags 的 index i 對應原序列第 (i+WINDOW) 窗,
                 故注入起點 t0 在 flags 中的位置為 fi = t0 - WINDOW。
    """
    fi = max(0, t0 - WINDOW)
    atk = flags[fi:]
    full = float(atk.mean()) if len(atk) else float("nan")
    onset = {k: (1.0 if flags[fi:fi + k].any() else 0.0) for k in ONSET_K}
    return full, onset


# ----------------------------------------------------------------------
# 4. 主實驗:漂移速率掃描,量 LSTM 何時失效
# ----------------------------------------------------------------------
def main():
    series = load_all()
    if len(series) < 2:
        print(f"資料不足(找到 {len(series)} 個 seed),至少需要 2 個。"
              f"確認 {DATA_DIR} 下有 ues1_t300_seed*.txt")
        return
    seeds = sorted(series)
    print(f"載入 {len(seeds)} 個 seed:{seeds}")

    try:
        import torch  # noqa
    except ImportError:
        print("\n未安裝 torch。請先執行:")
        print("  pip install torch numpy matplotlib --break-system-packages")
        return

    # leave-one-seed-out:一個 seed 當測試,其餘訓練,輪流,報跨 seed 平均
    drift_rates = [0.005, 0.01, 0.02, 0.04, 0.08, 0.15]  # 每窗漂移佔均值比例
    step_frac = 0.5     # 突發階梯對照(半個均值的一次偏移)
    t0_frac = 0.5       # 攻擊從序列中點開始注入

    results = {"seeds": seeds, "window": WINDOW,
               "drift_rates": drift_rates, "per_fold": [], "summary": {}}

    det_by_rate = {r: [] for r in drift_rates}
    det_step = []          # 階梯:整段攻擊窗偵測率(原口徑)
    onset_step = {k: [] for k in ONSET_K}   # 階梯:onset 命中(前 k 窗)
    fpr_list = []

    for test_seed in seeds:
        train_list = [series[s] for s in seeds if s != test_seed]
        test = series[test_seed]
        model, norm, thr = build_and_train(train_list)

        # (a) 乾淨測試序列的誤報率(false positive rate)
        clean_flags = anomaly_flags(model, norm, thr, test)
        fpr = float(clean_flags.mean())
        fpr_list.append(fpr)

        t0 = int(len(test) * t0_frac)

        # (b) 突發階梯:拆 onset(起始點抓到否) 與 full(整段偵測率)
        step_series = inject_step(test, t0, step_frac)
        sf = anomaly_flags(model, norm, thr, step_series)
        step_full, step_onset = onset_and_full(sf, t0)
        det_step.append(step_full)
        for k in ONSET_K:
            onset_step[k].append(step_onset[k])

        # (c) 漂移掃描:速率越小,偵測率應該越低(LSTM 學成正常)
        fold = {"test_seed": test_seed, "fpr": fpr,
                "step_det_full": step_full,
                "step_det_onset": step_onset, "drift_det": {}}
        for r in drift_rates:
            dseries = inject_drift(test, t0, r)
            df = anomaly_flags(model, norm, thr, dseries)
            det = float(df[max(0, t0 - WINDOW):].mean())
            det_by_rate[r].append(det)
            fold["drift_det"][str(r)] = det
        results["per_fold"].append(fold)
        drift_str = ", ".join(f"{r}:{fold['drift_det'][str(r)]:.2f}" for r in drift_rates)
        onset_str = ", ".join(f"k{k}:{step_onset[k]:.0f}" for k in ONSET_K)
        print(f"  [test={test_seed}] FPR={fpr:.2f}  "
              f"step_full={step_full:.2f} step_onset({onset_str})  "
              f"drift_det={{{drift_str}}}")

    # 匯總
    results["summary"] = {
        "mean_fpr": float(np.mean(fpr_list)),
        "mean_step_detection_full": float(np.mean(det_step)),
        "mean_step_detection_onset": {str(k): float(np.mean(onset_step[k])) for k in ONSET_K},
        "mean_drift_detection_by_rate": {str(r): float(np.mean(det_by_rate[r])) for r in drift_rates},
    }
    out_json = os.path.join(OUT_DIR, "lstm_baseline_results.json")
    with open(out_json, "w") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)
    print(f"\n結果寫入 {out_json}")
    print("關鍵數字(跨 seed 平均):")
    print(f"  乾淨序列誤報率 FPR        = {results['summary']['mean_fpr']:.2f}")
    print(f"  突發階梯 full-window 偵測率 = {results['summary']['mean_step_detection_full']:.2f}  (整段攻擊窗)")
    for k in ONSET_K:
        print(f"  突發階梯 onset 命中率(k={k})  = {results['summary']['mean_step_detection_onset'][str(k)]:.2f}  (注入後前 {k} 窗內至少觸發一次)")
    print("  → onset 遠高於 full 即證明:LSTM 抓得到『起始點』,但階梯偏移進入輸入視窗後被吸收為新基準,故整段偵測率被拉低")
    for r in drift_rates:
        print(f"  漂移速率 {r:<5} 偵測率 = {results['summary']['mean_drift_detection_by_rate'][str(r)]:.2f}")

    # 核心圖:偵測率 vs 漂移速率(預期:速率越小偵測率越低 → LSTM 失效區)
    try:
        import matplotlib.pyplot as plt
        rates = drift_rates
        dets = [results["summary"]["mean_drift_detection_by_rate"][str(r)] for r in rates]
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot([r * 100 for r in rates], dets, "o-", color="#c92a2a",
                label="LSTM detection rate (slow drift)")
        _sf = results["summary"]["mean_step_detection_full"]
        _so = results["summary"]["mean_step_detection_onset"][str(ONSET_K[0])]
        ax.axhline(_sf, ls="--", color="#495057",
                   label=f"step attack full-window (det={_sf:.2f})")
        ax.axhline(_so, ls=":", color="#495057",
                   label=f"step attack onset k={ONSET_K[0]} (hit={_so:.2f})")
        ax.set_xlabel("drift rate per window (% of mean throughput)")
        ax.set_ylabel("detection rate")
        ax.set_title("Single-node LSTM misses slow drift (baseline weakness)")
        ax.set_ylim(-0.05, 1.05)
        ax.legend(); ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(os.path.join(OUT_DIR, "fig_lstm_drift_evasion.png"), dpi=150)
        print("圖已存:fig_lstm_drift_evasion.png")
    except ImportError:
        print("未安裝 matplotlib,略過畫圖")


if __name__ == "__main__":
    main()
