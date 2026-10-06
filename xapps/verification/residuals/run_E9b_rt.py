#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_E9b_rt.py — 方案 B：監督式時序分類器（level、雙通道）於實際秒數下之重訓與評估

規格：docs/thesis/planB_realtime_spec.md 第二、四節。舊版 E9b_supervised_baseline.json 保留不動。

【模型】LSTM(2 → 64, 2 層) + Linear；輸入 w−9 … w 共 10 秒（通道一：(delay − 訓練中位數)/s，
  缺窗 = 0；通道二：遮罩）。其餘超參數、種子規則、AF 集合、每條序列 5 個隨機起點與舊版相同。
  **輸入改為雙通道為處理不規則觀測之模型修改。**
【訓練】每 fold 以 3 個訓練 seed 之 full-consensus 窗中可評估者為訓練窗；階躍注入於受測 cell
  所有上報窗；標籤 = (w ≥ 注入起點)。
【門檻】thr_cal：校準目標 FPR 0.0369（凍結，取自舊 E9 空間參照之乾淨 FPR 原值）；以訓練 fold
  乾淨複本後半段之可評估窗，合併後取分位數。另報 thr 0.5。
【評估】own（監督式自身可評估集合）與 common（三方法共同集合；主結果）。
【模型存檔】data/results/planB_models/E9b_rt_fold<seed>.pt（E9c_rt／E9d_rt 沿用同一模型）。

【內建檢查】
  1. 擬合檢查：訓練 balanced accuracy ≥ 0.80（逐 fold；未過則停止）。
  2. 回歸基準 E9b_rt（人工核對後以 --set-baseline 建立）。
"""
import os
import sys
import json
import hashlib
import argparse
import collections
import numpy as np
import torch
import torch.nn as nn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import planB_rt as P
import run_E9_operating_regime as E9
import run_E9b_supervised_baseline as B     # 沿用超參數常數

OUT_DIR = E9.OUT_DIR
MODEL_DIR = os.path.join(OUT_DIR, "planB_models")
TARGET_FPR = 0.036918565416925425        # 舊 E9 空間參照乾淨 FPR 原值（凍結）；main() 內與舊 JSON 核對
CONFIG = dict(seq=P.SEQ, hidden=B.HIDDEN, layers=B.LAYERS, epochs=B.EPOCHS, batch=B.BATCH, lr=B.LR,
              k_onset=B.K_ONSET, base_seed=B.BASE_SEED, afs=E9.STEP_AFS, min_obs=P.MIN_OBS,
              target_fpr=TARGET_FPR, channels=2)


class Clf2(nn.Module):
    def __init__(self):
        super().__init__()
        self.lstm = nn.LSTM(2, B.HIDDEN, num_layers=B.LAYERS, batch_first=True)
        self.head = nn.Linear(B.HIDDEN, 1)

    def forward(self, x):
        h, _ = self.lstm(x)
        return self.head(h[:, -1, :]).squeeze(-1)


def build_train(train_samples, med, s, rng):
    Xs, ys, cms = [], [], []
    for sm in train_samples:
        n = len(sm.idx)
        copies = [(sm.own, None)]
        for af in E9.STEP_AFS:
            for _ in range(B.K_ONSET):
                w0 = sm.idx[int(rng.integers(P.SEQ, n - P.SEQ))]
                copies.append((P.inject_step(sm.own, w0, af), w0))
        for v, w0 in copies:
            ws, X = P.seq_features(sm, v, med, s, sm.idx)
            if not ws:
                continue
            ws = np.array(ws)
            y = np.zeros(len(ws), np.float32) if w0 is None else (ws >= w0).astype(np.float32)
            cm = (ws >= sm.w_on) if w0 is None else np.zeros(len(ws), bool)
            Xs.append(X); ys.append(y); cms.append(cm)
    return np.concatenate(Xs), np.concatenate(ys), np.concatenate(cms)


def train(X, y, seed):
    B.set_det(seed)
    m = Clf2()
    opt = torch.optim.Adam(m.parameters(), lr=B.LR)
    pos = float(y.sum()); neg = float(len(y) - pos)
    lossf = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(neg / max(pos, 1.0)))
    Xt, yt = torch.from_numpy(X), torch.from_numpy(y)
    g = torch.Generator().manual_seed(seed)
    for _ in range(B.EPOCHS):
        perm = torch.randperm(len(yt), generator=g)
        m.train()
        for i in range(0, len(perm), B.BATCH):
            b = perm[i:i + B.BATCH]
            opt.zero_grad(); lossf(m(Xt[b]), yt[b]).backward(); opt.step()
    m.eval()
    return m


def predict(m, X):
    if len(X) == 0:
        return np.zeros(0)
    with torch.no_grad():
        return torch.sigmoid(m(torch.from_numpy(X))).numpy()


def config_hash():
    return hashlib.sha256(json.dumps(CONFIG, sort_keys=True).encode()).hexdigest()[:16]


def get_fold_model(data, seeds, fi, ts, retrain=False):
    """回傳 (model, med, s, thr_cal, fit)；已存檔且組態相同者直接載入"""
    os.makedirs(MODEL_DIR, exist_ok=True)
    path = os.path.join(MODEL_DIR, f"E9b_rt_fold{ts}.pt")
    s = P.fold_scale(data, seeds, ts)
    train_samples = [sm for x in seeds if x != ts for sm in P.samples_of(x, data[x])]
    med = float(np.median(np.concatenate([[sm.own[w] for w in sm.idx] for sm in train_samples])))
    if os.path.exists(path) and not retrain:
        ck = torch.load(path, weights_only=False)
        if ck["config_hash"] == config_hash():
            B.set_det(0)
            m = Clf2(); m.load_state_dict(ck["state"]); m.eval()
            return m, ck["med"], ck["s"], ck["thr_cal"], ck["fit"]
    seed = B.BASE_SEED + 1000 * fi            # 與舊版 level 變體相同之種子規則
    rng = np.random.default_rng(seed)
    X, y, cm = build_train(train_samples, med, s, rng)
    m = train(X, y, seed)
    p = predict(m, X)
    tpr = float((p[y == 1] > 0.5).mean()); tnr = float((p[y == 0] <= 0.5).mean())
    fit = {"balanced_acc": (tpr + tnr) / 2, "tpr": tpr, "tnr": tnr, "n_train_windows": int(len(y)),
           "pos_frac": float(y.mean()), "n_calib_windows": int(cm.sum())}
    thr = float(np.quantile(p[cm], 1 - TARGET_FPR))
    torch.save({"state": m.state_dict(), "med": med, "s": s, "thr_cal": thr, "fit": fit,
                "config": CONFIG, "config_hash": config_hash()}, path)
    return m, med, s, thr, fit


def sup_flags(m, sm, v, med, s, thr):
    ws, X = P.seq_features(sm, v, med, s, sm.idx)
    p = predict(m, X)
    out = {w: None for w in sm.idx}
    out.update({w: bool(pi > thr) for w, pi in zip(ws, p)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=OUT_DIR)
    ap.add_argument("--retrain", action="store_true")
    ap.add_argument("--set-baseline", action="store_true")
    ap.add_argument("--no-fig", action="store_true")
    args = ap.parse_args()
    old = json.load(open(os.path.join(args.out_dir, "E9_operating_regime.json"), encoding="utf-8"))
    if old["clean_fpr"]["spatial"]["mean"] != TARGET_FPR:
        raise SystemExit("凍結之校準目標與舊 E9 原值不符")
    seeds, data = P.load_data()

    acc = collections.defaultdict(list)
    fits, thrs = {}, {}
    for fi, ts in enumerate(seeds):
        m, med, s, thr, fit = get_fold_model(data, seeds, fi, ts, args.retrain)
        fits[ts], thrs[ts] = fit, thr
        print(f"fold {ts}: balanced acc {fit['balanced_acc']:.3f}（TPR {fit['tpr']:.3f}／TNR {fit['tnr']:.3f}）；"
              f"thr_cal {thr:.4f}；校準窗 {fit['n_calib_windows']}")
        for sm in P.samples_of(ts, data[ts]):
            sets = {"own": P.own_set(sm, "supervised"), "common": P.common_set(sm)}
            for thn, tv in (("thr_cal", thr), ("thr0.5", 0.5)):
                f0 = sup_flags(m, sm, sm.own, med, s, tv)
                for st, S in sets.items():
                    acc[(thn, st, "clean")].append((ts, P.rate(f0, S)))
                    fd = P.first_detection(f0, S, sm.w_on, "2c")
                    acc[(thn, st, "clean_2c_any")].append((ts, float(fd is not None)))
                for af in E9.STEP_AFS:
                    f = sup_flags(m, sm, P.inject_step(sm.own, sm.w_on, af), med, s, tv)
                    for st, S in sets.items():
                        acc[(thn, st, "step", af)].append((ts, P.rate(f, S)))
                        acc[(thn, st, "onset", af)].append((ts, P.onset_hit(f, S, sm.w_on)))
                for r in E9.DRIFT_RATES:
                    f = sup_flags(m, sm, P.inject_drift(sm.own, sm.w_on, r, sm.mean), med, s, tv)
                    for st, S in sets.items():
                        acc[(thn, st, "drift", r)].append((ts, P.rate(f, S)))
                        fd = P.first_detection(f, S, sm.w_on, "2c")
                        acc[(thn, st, "q2_undet", r)].append((ts, float(fd is None)))
                        if fd is not None:
                            acc[(thn, st, "q2_sec", r)].append((ts, fd - sm.w_on))

    bad = [ts for ts, f in fits.items() if f["balanced_acc"] < B.FIT_GATE]
    print("── 擬合檢查（≥ 0.80）──", "✗ " + str(bad) if bad else "✓")
    if bad:
        raise SystemExit("擬合檢查未通過，停止，不寫檔。")

    A = lambda k: P.agg_seed([(sd, v) for sd, v in acc[k] if v is not None])
    res = {"spec": "docs/thesis/planB_realtime_spec.md", "config": CONFIG, "train_fit": fits,
           "thr_cal_by_fold": thrs, "calibration_target_fpr": TARGET_FPR}
    for thn in ("thr_cal", "thr0.5"):
        res[thn] = {}
        for st in ("own", "common"):
            q2 = {}
            for r in E9.DRIFT_RATES:
                secs = [v for _, v in acc[(thn, st, "q2_sec", r)]]
                q2[str(r)] = {"undetected_frac": A((thn, st, "q2_undet", r)),
                              "detected_median_seconds": float(np.median(secs)) if secs else None,
                              "detected_median_offset_pct": float(np.median(secs)) * r * 100 if secs else None}
            res[thn][st] = {"clean_fpr": A((thn, st, "clean")),
                            "clean_2c_floor": A((thn, st, "clean_2c_any")),
                            "step": {str(k): A((thn, st, "step", k)) for k in E9.STEP_AFS},
                            "step_onset_hit": {str(k): A((thn, st, "onset", k)) for k in E9.STEP_AFS},
                            "drift": {str(k): A((thn, st, "drift", k)) for k in E9.DRIFT_RATES},
                            "Q2_2c": q2}
    rt = json.load(open(os.path.join(args.out_dir, "E9_operating_regime_rt.json"), encoding="utf-8"))
    res["reference_E9_rt_common"] = {r: {"clean_fpr": rt["common"][r]["clean_fpr"]["mean"],
                                         "drift": {k: v["mean"] for k, v in rt["common"][r]["drift"].items()},
                                         "step": {k: v["mean"] for k, v in rt["common"][r]["step"].items()}}
                                     for r in ("spatial", "temporal")}

    vals = {f"{thn}|{st}|{fam}|{k}": res[thn][st][fam][k]["mean"] for thn in ("thr_cal", "thr0.5")
            for st in ("own", "common") for fam in ("drift", "step", "step_onset_hit") for k in res[thn][st][fam]}
    vals.update({f"{thn}|{st}|clean": res[thn][st]["clean_fpr"]["mean"] for thn in ("thr_cal", "thr0.5") for st in ("own", "common")})
    vals.update({f"fit|{k}": v["balanced_acc"] for k, v in fits.items()})
    res["baseline_status"] = P.check_baseline("E9b_rt", vals, args.set_baseline,
                                              note="2026-10-06 首次重訓後人工核對")
    print("── 回歸基準 E9b_rt：", res["baseline_status"], "──\n")

    path = os.path.join(args.out_dir, "E9b_supervised_baseline_rt.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, ensure_ascii=False)
    ref = res["reference_E9_rt_common"]
    R = res["thr_cal"]["common"]
    print(f"══ common 集合，thr_cal（校準目標 0.0369）：實際測試乾淨 FPR {R['clean_fpr']['mean']:.3f}"
          f"（空間 {ref['spatial']['clean_fpr']:.3f}、時間 {ref['temporal']['clean_fpr']:.3f}）══")
    print(f"{'漂移%/秒':>8} {'監督':>6} {'空間':>6} {'時間':>6} | 2c 未偵測 偵測秒數中位")
    for k in E9.DRIFT_RATES:
        q = R["Q2_2c"][str(k)]
        print(f"{k*100:>8.1f} {R['drift'][str(k)]['mean']:>6.2f} {ref['spatial']['drift'][str(k)]:>6.2f} "
              f"{ref['temporal']['drift'][str(k)]:>6.2f} | {q['undetected_frac']['mean']:>8.2f} {q['detected_median_seconds']}")
    print("階躍：" + "  ".join(f"×{k} {R['step'][str(k)]['mean']:.2f}(onset {R['step_onset_hit'][str(k)]['mean']:.2f})" for k in E9.STEP_AFS))
    print(f"乾淨 2c 底線（注入區間內任一連續兩秒誤報）：{R['clean_2c_floor']['mean']:.2f}")
    print(f"\n寫入 {path}")
    if not args.no_fig:
        draw(res, os.path.join(args.out_dir, "fig_E9b_supervised_baseline_rt.png"))


def draw(res, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ref = res["reference_E9_rt_common"]; R = res["thr_cal"]["common"]
    x = [r * 100 for r in E9.DRIFT_RATES]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.8), sharey=True, gridspec_kw={"width_ratios": [1.6, 1]})
    a1.plot(x, [ref["spatial"]["drift"][str(r)] for r in E9.DRIFT_RATES], "o-", color="#2b8a3e", lw=2, label="spatial consensus")
    a1.plot(x, [ref["temporal"]["drift"][str(r)] for r in E9.DRIFT_RATES], "s--", color="#c92a2a", lw=2, label="temporal self-reference")
    a1.plot(x, [R["drift"][str(r)]["mean"] for r in E9.DRIFT_RATES], "^-", color="#5f3dc4", lw=1.6,
            label=f"supervised LSTM [level, 2-channel] (calibration target FPR 0.0369; "
                  f"test clean FPR {R['clean_fpr']['mean']:.3f} vs spatial {ref['spatial']['clean_fpr']:.3f})")
    xs = range(len(E9.STEP_AFS))
    a2.plot(xs, [ref["spatial"]["step"][str(k)] for k in E9.STEP_AFS], "o-", color="#2b8a3e", lw=2)
    a2.plot(xs, [ref["temporal"]["step"][str(k)] for k in E9.STEP_AFS], "s--", color="#c92a2a", lw=2)
    a2.plot(xs, [R["step"][str(k)]["mean"] for k in E9.STEP_AFS], "^-", color="#5f3dc4", lw=1.6)
    a1.set_xscale("log"); a1.set_xticks(x); a1.set_xticklabels([f"{v:g}" for v in x])
    a1.set_xlabel("gradual drift (% per second, log) — out of training distribution")
    a1.set_ylabel("alarm rate in injection interval (common set)"); a1.grid(alpha=0.3)
    a2.set_xticks(xs); a2.set_xticklabels([f"×{k}" for k in E9.STEP_AFS])
    a2.set_xlabel("step AF — training distribution"); a2.grid(alpha=0.3)
    fig.legend(*a1.get_legend_handles_labels(), loc="lower center", ncol=1, fontsize=8.5, frameon=False)
    fig.suptitle("Plan B: supervised classifier trained on steps, tested on drift (real-time seconds)", fontsize=11)
    fig.subplots_adjust(left=0.07, right=0.98, top=0.9, bottom=0.3, wspace=0.06)
    fig.savefig(path, dpi=200)
    print(f"圖已存: {path}")


if __name__ == "__main__":
    main()
