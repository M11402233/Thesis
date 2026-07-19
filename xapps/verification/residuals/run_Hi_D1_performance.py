#!/usr/bin/env python3
"""
run_Hi_D1_performance.py — H_i D1(成員消失)偵測效能實驗(補 review 指出缺的 FPR/TPR/delay)

與 run_Hi_experiments.py 的差別:
  - run_Hi_experiments.py: 注入指定 z 值、看『分級分佈』(驗證三級分級機制有作用)
  - 本腳本: 量『真實偵測效能』—— clean FPR / injection TPR / F1 / detection delay,
            並 edge/resident UE 分開報、以 seed 為統計單位報 95% CI。

方法(對齊 4.7 定義 v2):
  - per-UE Hampel robust z = (d − median_x)/(1.4826·MAD_x);z > τ_z^reject(=3) 判 violated
  - 經驗 p 值 p_emp = P(乾淨停留 ≥ d);p_emp < α(=0.01) 判 violated(兩者取聯集或交集,可選)
  - clean FPR: 對乾淨資料的每個 dwell 事件,量被誤判 violated 的比例
  - injection TPR: 注入『超時消失』(UE 掛 LTE-only 超過正常後不歸隊),量被判 violated 比例
  - detection delay: 從注入開始到第一次觸發 violated 的窗數
  - 統計單位: seed(留一交叉驗證建 per-UE 基線),跨 seed 報 mean ± 95% CI

輸出:
  data/results/Hi_D1_performance.json
  data/results/fig_Hi_D1_roc.png            (τ_z 掃描的 FPR-TPR)
  data/results/fig_Hi_D1_edge_vs_resident.png

跑法:
  cd ~/oran-zt-kpm-verification
  python3 xapps/verification/residuals/run_Hi_D1_performance.py

依賴: numpy, matplotlib
"""
import os
import glob
import json
import collections
import numpy as np

DATA_DIR = os.path.expanduser("~/oran-zt-kpm-verification/data/si_lstm_seeds")
OUT_DIR  = os.path.expanduser("~/oran-zt-kpm-verification/data/results")
os.makedirs(OUT_DIR, exist_ok=True)

# ---- 參數(對齊 4.7 定義)----
TAU_Z_REJECT = 3.0      # robust z 判 violated 門檻(≈3σ)
ALPHA_EMP    = 0.01     # 經驗 p 值顯著水準
EDGE_SPLIT   = 0.55     # LTE 佔比 >= 0.55 視為 edge UE
DECISION_RULE = "z_only"  # "z_only" | "p_only" | "z_or_p" | "z_and_p"
TAU_Z_SWEEP  = [2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0]  # ROC 用


# ---------------------------------------------------------------
# 載入 + 狀態序列
# ---------------------------------------------------------------
def load(path):
    rec = collections.defaultdict(dict)  # imsi -> {window: set(cells)}
    with open(path) as fh:
        fh.readline()
        for line in fh:
            p = line.split("\t")
            if len(p) < 4:
                continue
            try:
                w = int(float(p[0])); cell = int(p[2]); imsi = int(p[3])
            except ValueError:
                continue
            rec[imsi].setdefault(w, set()).add(cell)
    return rec


def state_seq(wm, all_w):
    s = []
    for w in all_w:
        cells = wm.get(w, set())
        if any(c != 1 for c in cells):
            s.append("mmw")
        elif 1 in cells:
            s.append("lte")
        else:
            s.append("absent")
    return s


def dwell_events(seq):
    """回傳 [(start_index, length), ...] 每段連續 lte-only 停留"""
    ev = []
    i = 0
    while i < len(seq):
        if seq[i] == "mmw":
            j = i + 1
            run = 0
            while j < len(seq) and seq[j] == "lte":
                run += 1
                j += 1
            if run > 0:
                ev.append((i + 1, run))
            i = j
        else:
            i += 1
    return ev


def ue_lte_fraction(seq):
    na = sum(1 for s in seq if s != "absent")
    return (sum(1 for s in seq if s == "lte") / na) if na else 0.5


# ---------------------------------------------------------------
# per-UE Hampel 基線 + 經驗分布(由訓練 seed 建,永不線上更新)
# ---------------------------------------------------------------
def build_baseline(train_files):
    dwell = collections.defaultdict(list)
    grp_dwell = {"edge": [], "resident": []}
    for f in train_files:
        rec = load(f)
        all_w = sorted(set(w for im, wm in rec.items() for w in wm))
        for imsi, wm in rec.items():
            seq = state_seq(wm, all_w)
            ds = [d for _, d in dwell_events(seq)]
            dwell[imsi] += ds
            grp = "edge" if ue_lte_fraction(seq) >= EDGE_SPLIT else "resident"
            grp_dwell[grp] += ds
    hampel = {}
    emp = {}
    for imsi, d in dwell.items():
        if len(d) >= 8:
            med = np.median(d)
            mad = np.median(np.abs(np.array(d) - med))
            hampel[imsi] = (med, 1.4826 * mad if mad > 0 else 1.0)
            emp[imsi] = sorted(d)
    grp_emp = {k: sorted(v) for k, v in grp_dwell.items()}
    grp_hampel = {}
    for k, v in grp_dwell.items():
        if v:
            med = np.median(v); mad = np.median(np.abs(np.array(v) - med))
            grp_hampel[k] = (med, 1.4826 * mad if mad > 0 else 1.0)
    return hampel, emp, grp_hampel, grp_emp


def get_params(imsi, grp, hampel, emp, grp_hampel, grp_emp):
    if imsi in hampel:
        return hampel[imsi][0], hampel[imsi][1], emp[imsi]
    med, sig = grp_hampel.get(grp, (2.0, 1.0))
    return med, sig, grp_emp.get(grp, [2])


def is_violated(d, med, sig, clean_sorted):
    z = abs(d - med) / sig if sig > 0 else 0.0
    p = (sum(1 for x in clean_sorted if x >= d) / len(clean_sorted)) if clean_sorted else 1.0
    if DECISION_RULE == "z_only":
        return z > TAU_Z_REJECT, z, p
    if DECISION_RULE == "p_only":
        return p < ALPHA_EMP, z, p
    if DECISION_RULE == "z_or_p":
        return (z > TAU_Z_REJECT or p < ALPHA_EMP), z, p
    return (z > TAU_Z_REJECT and p < ALPHA_EMP), z, p


# ---------------------------------------------------------------
# 攻擊注入:超時消失(UE 掛 LTE-only 超過正常後不歸隊)
# ---------------------------------------------------------------
def inject_disappearance(seq, start, extra_len):
    """在乾淨的 mmw 位置注入一段長 extra_len 的 lte-only(模擬被移除卻偽裝回落)"""
    s = list(seq)
    # 找一個 start 之後為 mmw 的乾淨注入點(避免黏到既有 lte 段)
    inj = start
    while inj < len(s) - extra_len and s[inj] != "mmw":
        inj += 1
    for t in range(inj, min(inj + extra_len, len(s))):
        s[t] = "lte"
    return s, inj


# ---------------------------------------------------------------
# 主實驗:留一交叉驗證
# ---------------------------------------------------------------
def run_once(tau_z=TAU_Z_REJECT):
    global TAU_Z_REJECT
    TAU_Z_REJECT = tau_z

    files = sorted(glob.glob(os.path.join(DATA_DIR, "ues1_t300_seed*.txt"))) or \
            sorted(glob.glob("ues1_t300_seed*.txt"))
    seeds = [os.path.basename(f).split("seed")[-1].replace(".txt", "") for f in files]

    per_seed = []  # 每個 held-out seed 一組指標
    for ts, tf in zip(seeds, files):
        train = [f for f in files if f != tf]
        hampel, emp, grp_hampel, grp_emp = build_baseline(train)

        rec = load(tf)
        all_w = sorted(set(w for im, wm in rec.items() for w in wm))

        # ---- clean FPR: 對乾淨 dwell 事件,量誤判 ----
        fp = {"edge": [0, 0], "resident": [0, 0]}   # [false_pos, total]
        for imsi, wm in rec.items():
            seq = state_seq(wm, all_w)
            grp = "edge" if ue_lte_fraction(seq) >= EDGE_SPLIT else "resident"
            med, sig, clean = get_params(imsi, grp, hampel, emp, grp_hampel, grp_emp)
            for _, d in dwell_events(seq):
                v, _, _ = is_violated(d, med, sig, clean)
                fp[grp][1] += 1
                if v:
                    fp[grp][0] += 1

        # ---- injection TPR + detection delay ----
        tp = {"edge": [0, 0], "resident": [0, 0]}
        delays = []
        for imsi, wm in rec.items():
            seq = state_seq(wm, all_w)
            grp = "edge" if ue_lte_fraction(seq) >= EDGE_SPLIT else "resident"
            med, sig, clean = get_params(imsi, grp, hampel, emp, grp_hampel, grp_emp)
            # 注入強度: 正常上界的 1.5x 到 3x(超時消失)
            base_hi = med + TAU_Z_REJECT * sig
            for mult in (1.5, 2.0, 3.0):
                extra = max(2, int(round(base_hi * mult)))
                s2, inj = inject_disappearance(seq, len(all_w) // 3, extra)
                # 從 inj 起算,逐窗累積停留,第一次 violated 的 delay
                detected = False
                run = 0
                for t in range(inj, len(s2)):
                    if s2[t] == "lte":
                        run += 1
                        v, _, _ = is_violated(run, med, sig, clean)
                        if v:
                            delays.append(t - inj + 1)
                            detected = True
                            break
                    else:
                        break
                tp[grp][1] += 1
                if detected:
                    tp[grp][0] += 1

        def rate(pair):
            return pair[0] / pair[1] if pair[1] else float("nan")

        all_fp = [fp["edge"][0] + fp["resident"][0], fp["edge"][1] + fp["resident"][1]]
        all_tp = [tp["edge"][0] + tp["resident"][0], tp["edge"][1] + tp["resident"][1]]
        per_seed.append({
            "seed": ts,
            "fpr_all": rate(all_fp), "tpr_all": rate(all_tp),
            "fpr_edge": rate(fp["edge"]), "fpr_resident": rate(fp["resident"]),
            "tpr_edge": rate(tp["edge"]), "tpr_resident": rate(tp["resident"]),
            "mean_detection_delay": float(np.mean(delays)) if delays else float("nan"),
        })
    return per_seed


def ci95(vals):
    v = [x for x in vals if x == x]  # drop nan
    if len(v) < 2:
        return (float(np.mean(v)) if v else float("nan"), float("nan"))
    m = np.mean(v); se = np.std(v, ddof=1) / np.sqrt(len(v))
    return float(m), float(1.96 * se)


def main():
    print("=== H_i D1 偵測效能(留一交叉驗證,seed 為統計單位)===")
    print(f"決策規則={DECISION_RULE}, τ_z={TAU_Z_REJECT}, α={ALPHA_EMP}, edge_split={EDGE_SPLIT}\n")

    per_seed = run_once(TAU_Z_REJECT)
    for r in per_seed:
        print(f"  seed {r['seed']}: FPR={r['fpr_all']:.3f} TPR={r['tpr_all']:.3f} "
              f"delay={r['mean_detection_delay']:.1f}窗 | "
              f"edge(FPR={r['fpr_edge']:.2f},TPR={r['tpr_edge']:.2f}) "
              f"resident(FPR={r['fpr_resident']:.2f},TPR={r['tpr_resident']:.2f})")

    fpr_m, fpr_ci = ci95([r["fpr_all"] for r in per_seed])
    tpr_m, tpr_ci = ci95([r["tpr_all"] for r in per_seed])
    dly_m, dly_ci = ci95([r["mean_detection_delay"] for r in per_seed])
    f1 = 2 * tpr_m * (1 - fpr_m) / (tpr_m + (1 - fpr_m)) if (tpr_m + (1 - fpr_m)) > 0 else float("nan")

    print(f"\n跨 seed 彙總(mean ± 95% CI):")
    print(f"  clean FPR         = {fpr_m:.3f} ± {fpr_ci:.3f}")
    print(f"  injection TPR     = {tpr_m:.3f} ± {tpr_ci:.3f}")
    print(f"  detection delay   = {dly_m:.1f} ± {dly_ci:.1f} 窗")
    print(f"  F1(近似)          = {f1:.3f}")

    # ---- ROC: 掃 τ_z ----
    roc = []
    for tz in TAU_Z_SWEEP:
        ps = run_once(tz)
        fm, _ = ci95([r["fpr_all"] for r in ps])
        tm, _ = ci95([r["tpr_all"] for r in ps])
        roc.append({"tau_z": tz, "fpr": fm, "tpr": tm})
        print(f"  [ROC] τ_z={tz}: FPR={fm:.3f} TPR={tm:.3f}")

    result = {
        "params": {"tau_z_reject": TAU_Z_REJECT, "alpha_emp": ALPHA_EMP,
                   "edge_split": EDGE_SPLIT, "decision_rule": DECISION_RULE},
        "per_seed": per_seed,
        "summary": {"fpr": [fpr_m, fpr_ci], "tpr": [tpr_m, tpr_ci],
                    "detection_delay": [dly_m, dly_ci], "f1_approx": f1},
        "roc": roc,
    }
    with open(os.path.join(OUT_DIR, "Hi_D1_performance.json"), "w") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)
    print(f"\n結果寫入 {os.path.join(OUT_DIR, 'Hi_D1_performance.json')}")

    # ---- 圖 ----
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        # ROC
        fig, ax = plt.subplots(figsize=(6.5, 5))
        fprs = [r["fpr"] for r in roc]; tprs = [r["tpr"] for r in roc]
        ax.plot(fprs, tprs, "o-", color="#1971c2")
        for r in roc:
            ax.annotate(f"τ={r['tau_z']}", (r["fpr"], r["tpr"]),
                        textcoords="offset points", xytext=(5, -8), fontsize=8)
        ax.plot([0, 1], [0, 1], "--", color="#adb5bd", alpha=0.6)
        ax.set_xlabel("false positive rate (clean dwell events)")
        ax.set_ylabel("true positive rate (injected disappearance)")
        ax.set_title("H_i D1 detection: FPR-TPR under τ_z sweep (seed-level)")
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(os.path.join(OUT_DIR, "fig_Hi_D1_roc.png"), dpi=150)

        # edge vs resident
        fig2, ax2 = plt.subplots(figsize=(7, 4.5))
        groups = ["resident", "edge"]
        fpr_g = [ci95([r[f"fpr_{g}"] for r in per_seed])[0] for g in groups]
        tpr_g = [ci95([r[f"tpr_{g}"] for r in per_seed])[0] for g in groups]
        x = np.arange(len(groups)); w = 0.35
        ax2.bar(x - w/2, fpr_g, w, label="clean FPR", color="#e8590c")
        ax2.bar(x + w/2, tpr_g, w, label="injection TPR", color="#2b8a3e")
        ax2.set_xticks(x); ax2.set_xticklabels(groups)
        ax2.set_ylabel("rate"); ax2.set_ylim(0, 1.05)
        ax2.set_title("H_i D1: edge vs resident UE (per-UE baseline)")
        ax2.legend()
        fig2.tight_layout()
        fig2.savefig(os.path.join(OUT_DIR, "fig_Hi_D1_edge_vs_resident.png"), dpi=150)
        print("圖已存: fig_Hi_D1_roc.png, fig_Hi_D1_edge_vs_resident.png")
    except ImportError:
        print("未安裝 matplotlib,略過畫圖(JSON 仍完整)")


if __name__ == "__main__":
    main()
