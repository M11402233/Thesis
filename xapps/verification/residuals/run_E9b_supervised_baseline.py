#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_E9b_supervised_baseline.py — E9b：監督式時序分類器於階躍訓練、漂移測試（第四章 4.7.5 延伸）

【要回答的問題】
既有工作（Alimohammadi et al., arXiv 2512.01596）之偵測器為**監督式時序分類**：
以帶標籤之注入資料（AF = 1.2–1.5 階躍）訓練 LSTM/GRU/1D-CNN/Transformer，序列長度 10。
本研究之 lstm_baseline_anchor.py 為凍結之預測式模型（自我參照），依 CLAUDE.md 之界定，
其盲點**不得外推至監督式模型**。E9b 補上此缺口：
  在本研究資料上，以階躍標籤訓練一個監督式 LSTM 分類器，測試其於
  (a) 訓練分布內之階躍、(b) 訓練分布外之漸進漂移 之偵測率與偵測前偏差。
結果照實報告：若監督式模型能抓到漂移，論文之差異化主張須改寫。

【設計】
  資料      D-SH，與 E9 相同之 seed×cell full-consensus 序列；LOSO（3 seed 訓練、1 seed 測試）
  輸入      僅受測 cell 自身之 delay 序列（長度 SEQ = 10，與既有工作相同）；不含 peer 資訊
            level    ： x = (delay − median_train) / s
            relative ： level 再減去該長度 10 序列之中位數（只看形狀，不看絕對水準）
  標籤      逐窗：注入起點後 = 1
  訓練資料  每條訓練序列：1 份乾淨 + 每個 AF × K_ONSET 個隨機起點之階躍注入；類別以 pos_weight 平衡
  模型      LSTM(1→64, 2 層) + Linear；Adam 1e-3；EPOCHS 輪；CPU、固定種子、確定性演算法
  門檻      thr0.5（機率 0.5）與 thr_cal（以**訓練資料**乾淨窗校準，使其 FPR = E9 空間參照之乾淨 FPR，
            以便與空間參照於相同誤報水準下比較；不使用測試資料）
  測試      與 E9 相同：t0 = len//2，評估序列後半段；攻擊族 = E9 之 STEP_AFS 與 DRIFT_RATES
  另報      Q2 準則 2c 之首次偵測窗數與偵測時偏移（與 run_slow_poisoning_suite 同定義）

【內建檢查（訓練擬合，非測試表現）】
  訓練資料之 balanced accuracy（thr0.5）須 ≥ 0.80，否則代表分類器未學會訓練分布。
  此門檻於執行前訂定，不得事後調整。**逐變體判定**：任一 fold 未過之變體，其測試結果
  不寫入、不採計，僅於 JSON 記錄其擬合數字與狀態；全部變體皆未過時停止、不寫檔。
  （2026-10-05 修訂紀錄：首次執行時 relative 變體 3/4 fold 未過（0.680–0.805），原版
   「任一失敗即全體停止」改為逐變體判定；門檻值與 level 變體之設計均未變動。）
  另：同設定重跑須逐位相同（確定性；以 --check-determinism 驗證）。

【誠實聲明（寫進論文）】
  - 此為「同類方法於本研究觀測維度上之實作」，非既有工作之重現：既有工作之輸入為 per-UE 多項 KPM，
    本實作僅有 per-cell delay；模型規模、訓練資料量均不同。
  - 結論限於：「以階躍標籤訓練、僅以自身時序為輸入之監督式分類器」於本資料上之行為。

【輸出】
  <out>/E9b_supervised_baseline.json
  <out>/fig_E9b_supervised_baseline.png
"""
import os
import sys
import json
import hashlib
import argparse
import collections
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_E9_operating_regime as E9
from run_E9_operating_regime import load_cell_delay, global_scale, inject_drift, inject_step
from run_slow_poisoning_suite import find_files, build_samples, first_detection, agg_seed

import torch
import torch.nn as nn

SEQ = 10
HIDDEN = 64
LAYERS = 2
EPOCHS = 25
BATCH = 256
LR = 1e-3
K_ONSET = 5
BASE_SEED = 20261005
FIT_GATE = 0.80
VARIANTS = ("level", "relative")
THREADS = 2          # 保留核心給背景 ns-3


def set_det(seed):
    torch.manual_seed(seed)
    np.random.seed(seed % (2**32))
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(THREADS)


class Clf(nn.Module):
    def __init__(self):
        super().__init__()
        self.lstm = nn.LSTM(1, HIDDEN, num_layers=LAYERS, batch_first=True)
        self.head = nn.Linear(HIDDEN, 1)

    def forward(self, x):
        h, _ = self.lstm(x)
        return self.head(h[:, -1, :]).squeeze(-1)


def windows_of(x, variant):
    """回傳 (n−SEQ+1, SEQ) 之序列矩陣；第 i 列對應結尾窗 t = i + SEQ − 1"""
    W = np.lib.stride_tricks.sliding_window_view(x, SEQ).astype(np.float32)
    if variant == "relative":
        W = W - np.median(W, axis=1, keepdims=True)
    return W


def build_train(series_list, med, s, variant, rng):
    Xs, ys, clean_mask = [], [], []
    for ser in series_list:
        n = len(ser)
        copies = [(ser, None)]
        for af in E9.STEP_AFS:
            for _ in range(K_ONSET):
                t0 = int(rng.integers(SEQ, n - SEQ))
                copies.append((inject_step(ser, t0, af), t0))
        for v, t0 in copies:
            W = windows_of((v - med) / s, variant)
            t_end = np.arange(SEQ - 1, n)
            y = np.zeros(len(t_end), np.float32) if t0 is None else (t_end >= t0).astype(np.float32)
            Xs.append(W); ys.append(y)
            # 校準用：乾淨複本之後半段（與測試評估區間同位置）
            cm = np.zeros(len(t_end), bool)
            if t0 is None:
                cm[t_end >= n // 2] = True
            clean_mask.append(cm)
    return np.concatenate(Xs), np.concatenate(ys), np.concatenate(clean_mask)


def train_model(X, y, seed):
    set_det(seed)
    m = Clf()
    opt = torch.optim.Adam(m.parameters(), lr=LR)
    pos = float(y.sum()); neg = float(len(y) - pos)
    lossf = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(neg / max(pos, 1.0)))
    Xt = torch.from_numpy(X).unsqueeze(-1); yt = torch.from_numpy(y)
    g = torch.Generator().manual_seed(seed)
    for _ in range(EPOCHS):
        perm = torch.randperm(len(yt), generator=g)
        m.train()
        for i in range(0, len(perm), BATCH):
            b = perm[i:i + BATCH]
            opt.zero_grad()
            loss = lossf(m(Xt[b]), yt[b])
            loss.backward()
            opt.step()
    m.eval()
    return m


def predict(m, X):
    with torch.no_grad():
        return torch.sigmoid(m(torch.from_numpy(X).unsqueeze(-1))).numpy()


def flags_for(m, v, med, s, variant, thr):
    p = predict(m, windows_of((v - med) / s, variant))
    f = np.zeros(len(v), bool)
    f[SEQ - 1:] = p > thr
    return f


def run(data, seeds, target_fpr):
    out = {}
    for variant in VARIANTS:
        rec = {th: {"fpr": [], "step": collections.defaultdict(list),
                    "onset": collections.defaultdict(list),
                    "drift": collections.defaultdict(list),
                    "q2": collections.defaultdict(list)} for th in ("thr0.5", "thr_cal")}
        fit, thr_cal_by_fold = {}, {}
        for fi, ts in enumerate(seeds):
            train_seeds = [x for x in seeds if x != ts]
            s = global_scale([data[x] for x in train_seeds])
            train_series = [ser for x in train_seeds for _, _, ser, _ in build_samples(data[x])]
            med = float(np.median(np.concatenate(train_series)))
            fold_seed = BASE_SEED + 1000 * fi + VARIANTS.index(variant)
            rng = np.random.default_rng(fold_seed)
            X, y, cm = build_train(train_series, med, s, variant, rng)
            m = train_model(X, y, fold_seed)
            p = predict(m, X)
            tpr = float((p[y == 1] > 0.5).mean()); tnr = float((p[y == 0] <= 0.5).mean())
            fit[ts] = {"balanced_acc": (tpr + tnr) / 2, "tpr": tpr, "tnr": tnr,
                       "n_train_windows": int(len(y)), "pos_frac": float(y.mean())}
            thr_cal = float(np.quantile(p[cm], 1 - target_fpr))
            thr_cal_by_fold[ts] = thr_cal
            thr = {"thr0.5": 0.5, "thr_cal": thr_cal}

            for tc, idx, ser, pm in build_samples(data[ts]):
                mean = ser.mean(); t0 = len(ser) // 2
                for th, tv in thr.items():
                    R = rec[th]
                    R["fpr"].append((ts, float(flags_for(m, ser, med, s, variant, tv)[t0:].mean())))
                    for af in E9.STEP_AFS:
                        f = flags_for(m, inject_step(ser, t0, af), med, s, variant, tv)
                        R["step"][af].append((ts, float(f[t0:].mean())))
                        R["onset"][af].append((ts, float(f[t0:t0 + E9.ONSET_K].any())))
                    for rate in E9.DRIFT_RATES:
                        f = flags_for(m, inject_drift(ser, t0, rate, mean), med, s, variant, tv)
                        R["drift"][rate].append((ts, float(f[t0:].mean())))
                        k = first_detection(f, t0, "2c")
                        n = (len(ser) - t0 - 1) if k is None else (k - t0)
                        R["q2"][rate].append({"seed": ts, "detected": k is not None,
                                              "windows": n, "offset_pct": rate * n * 100})
        res_v = {"train_fit": fit, "thr_cal_by_fold": thr_cal_by_fold}
        for th, R in rec.items():
            q2 = {}
            for rate, rows in R["q2"].items():
                det = [x for x in rows if x["detected"]]
                q2[str(rate)] = {
                    "undetected_frac": agg_seed([(x["seed"], float(not x["detected"])) for x in rows]),
                    "detected_median_windows": float(np.median([x["windows"] for x in det])) if det else None,
                    "detected_median_offset_pct": float(np.median([x["offset_pct"] for x in det])) if det else None,
                    "all_median_offset_pct_censored": float(np.median([x["offset_pct"] for x in rows]))}
            res_v[th] = {"clean_fpr": agg_seed(R["fpr"]),
                         "step": {str(k): agg_seed(v) for k, v in R["step"].items()},
                         "step_onset_hit": {str(k): agg_seed(v) for k, v in R["onset"].items()},
                         "drift": {str(k): agg_seed(v) for k, v in R["drift"].items()},
                         "Q2_2c": q2}
        out[variant] = res_v
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=None)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--no-fig", action="store_true")
    ap.add_argument("--check-determinism", action="store_true", help="整體重跑一次並比對")
    args = ap.parse_args()
    out_dir = args.out_dir or E9.OUT_DIR
    os.makedirs(out_dir, exist_ok=True)
    files = find_files(args.data_dir)
    if len(files) < 2:
        print("資料不足，用 --data-dir 指定。"); return
    seeds = [os.path.basename(f).split("seed")[-1].replace(".txt", "") for f in files]
    data = {s: load_cell_delay(f) for s, f in zip(seeds, files)}
    e9 = json.load(open(os.path.join(out_dir, "E9_operating_regime.json"), encoding="utf-8"))
    target_fpr = e9["clean_fpr"]["spatial"]["mean"]
    print(f"載入 {len(seeds)} seed；thr_cal 對齊 E9 空間參照乾淨 FPR = {target_fpr:.4f}\n")

    res = run(data, seeds, target_fpr)

    if args.check_determinism:
        res2 = run(data, seeds, target_fpr)
        h1 = hashlib.sha256(json.dumps(res, sort_keys=True).encode()).hexdigest()
        h2 = hashlib.sha256(json.dumps(res2, sort_keys=True).encode()).hexdigest()
        print(f"── 確定性檢查 ── {'✓ 兩次逐位相同' if h1 == h2 else '✗ 不同'}（{h1[:12]}）")
        if h1 != h2:
            raise SystemExit("非確定性，停止，不寫檔。")

    print("── 訓練擬合檢查（balanced accuracy ≥ 0.80，thr0.5）──")
    bad = []
    for v in VARIANTS:
        for sd, f in res[v]["train_fit"].items():
            ok = f["balanced_acc"] >= FIT_GATE
            print(f"  {v:>8} fold {sd}: {f['balanced_acc']:.3f}（TPR {f['tpr']:.3f} / TNR {f['tnr']:.3f}）"
                  f"{'' if ok else '  ✗'}")
            if not ok:
                bad.append((v, sd))
    failed = sorted({v for v, _ in bad})
    passed = [v for v in VARIANTS if v not in failed]
    if not passed:
        raise SystemExit("所有變體皆未學會訓練分布，E9b 測試結果不可用，停止，不寫檔。")
    for v in failed:
        print(f"  ✗ {v}：未通過擬合檢查，測試結果不採計、不寫入")
        res[v] = {"status": "excluded_fit_gate", "train_fit": res[v]["train_fit"]}
    for v in passed:
        res[v]["status"] = "ok"
    print(f"  採計變體：{passed}\n")

    full = {"variants_passed": passed, "variants_excluded": failed, "fit_gate": FIT_GATE,
            "seq_len": SEQ, "hidden": HIDDEN, "layers": LAYERS, "epochs": EPOCHS,
            "k_onset": K_ONSET, "train_afs": E9.STEP_AFS, "target_fpr_from_E9_spatial": target_fpr,
            "results": res,
            "reference_E9": {"spatial": {"clean_fpr": e9["clean_fpr"]["spatial"]["mean"],
                                         "drift": {k: v["mean"] for k, v in e9["drift"]["spatial"].items()},
                                         "step": {k: v["mean"] for k, v in e9["step"]["spatial"].items()}},
                             "temporal": {"clean_fpr": e9["clean_fpr"]["temporal"]["mean"],
                                          "drift": {k: v["mean"] for k, v in e9["drift"]["temporal"].items()},
                                          "step": {k: v["mean"] for k, v in e9["step"]["temporal"].items()}}},
            "note": ("supervised LSTM classifier trained on step labels, own-cell delay only; "
                     "an implementation of the method class on this work's observation dimension, "
                     "not a reproduction of the prior work")}
    path = os.path.join(out_dir, "E9b_supervised_baseline.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(full, fh, indent=2, ensure_ascii=False)

    ref = full["reference_E9"]
    for v in passed:
        for th in ("thr0.5", "thr_cal"):
            R = res[v][th]
            print(f"══ 監督式 [{v}, {th}]  乾淨 FPR {R['clean_fpr']['mean']:.3f}"
                  f"（空間 {ref['spatial']['clean_fpr']:.3f}）══")
            print("   階躍 AF :" + "".join(f"  ×{a}: {R['step'][str(a)]['mean']:.2f}"
                                       f"(onset {R['step_onset_hit'][str(a)]['mean']:.2f})"
                                       for a in E9.STEP_AFS))
            print(f"   {'漂移':>6} {'監督':>6} {'空間':>6} {'時間':>6} | 2c 未偵測  偵測時偏移%")
            for rate in E9.DRIFT_RATES:
                q = R["Q2_2c"][str(rate)]
                off = q["detected_median_offset_pct"]
                print(f"   {rate*100:>5.1f}% {R['drift'][str(rate)]['mean']:>6.2f} "
                      f"{ref['spatial']['drift'][str(rate)]:>6.2f} {ref['temporal']['drift'][str(rate)]:>6.2f} | "
                      f"{q['undetected_frac']['mean']:>8.2f}  {off if off is None else round(off, 1)}")
            print()
    print(f"寫入 {path}")
    if not args.no_fig:
        draw(full, out_dir)


def draw(full, out_dir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rates = E9.DRIFT_RATES; x = [r * 100 for r in rates]
    ref = full["reference_E9"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.6), sharey=True,
                                 gridspec_kw={"width_ratios": [1.6, 1]})
    a1.plot(x, [ref["spatial"]["drift"][str(r)] for r in rates], "o-", color="#2b8a3e", lw=2,
            label="spatial consensus (E9)")
    a1.plot(x, [ref["temporal"]["drift"][str(r)] for r in rates], "s--", color="#c92a2a", lw=2,
            label="temporal self-reference (E9)")
    sty = {"level": ("#5f3dc4", "-"), "relative": ("#e67700", "-.")}
    for v in full["variants_passed"]:
        R = full["results"][v]["thr_cal"]
        a1.plot(x, [R["drift"][str(r)]["mean"] for r in rates], marker="^", color=sty[v][0],
                ls=sty[v][1], lw=1.6, label=f"supervised LSTM [{v}] (threshold calibrated on training clean data; "
                      f"test clean FPR {R['clean_fpr']['mean']:.3f} vs spatial {ref['spatial']['clean_fpr']:.3f})")
        a2.plot(range(len(E9.STEP_AFS)), [R["step"][str(a)]["mean"] for a in E9.STEP_AFS],
                marker="^", color=sty[v][0], ls=sty[v][1], lw=1.6)
    a2.plot(range(len(E9.STEP_AFS)), [ref["spatial"]["step"][str(a)] for a in E9.STEP_AFS],
            "o-", color="#2b8a3e", lw=2)
    a2.plot(range(len(E9.STEP_AFS)), [ref["temporal"]["step"][str(a)] for a in E9.STEP_AFS],
            "s--", color="#c92a2a", lw=2)
    a1.set_xscale("log"); a1.set_xticks(x); a1.set_xticklabels([f"{v:g}" for v in x])
    a1.set_xlabel("gradual drift (%/window, log) — out of training distribution")
    a1.set_ylabel("detection rate (injection interval)"); a1.grid(alpha=0.3)
    a2.set_xticks(range(len(E9.STEP_AFS))); a2.set_xticklabels([f"×{a}" for a in E9.STEP_AFS])
    a2.set_xlabel("step AF — training distribution"); a2.grid(alpha=0.3)
    fig.legend(*a1.get_legend_handles_labels(), loc="lower center", ncol=2, fontsize=8.5, frameon=False)
    fig.suptitle("E9b supervised classifier trained on steps, tested on drift", fontsize=11)
    fig.subplots_adjust(left=0.07, right=0.98, top=0.88, bottom=0.27, wspace=0.06)
    fig.savefig(os.path.join(out_dir, "fig_E9b_supervised_baseline.png"), dpi=200)
    print(f"圖已存: {out_dir}/fig_E9b_supervised_baseline.png")


if __name__ == "__main__":
    main()
