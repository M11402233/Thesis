#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_fig_Hi_H1_H4.py — 重繪 Fig 4-9～4-12（H_i 乾淨基線四圖；第四章 4.8.1、4.8.2、4.8.4、4.8.6）

【為何重繪】
舊版四圖已上傳 HackMD，但 repo 中既無圖檔亦無產生腳本，無法重現（圖表狀態清單 ❓）。
本腳本以 D-SH（必要時 D-C）唯讀重算，所有數字輸出至 JSON，並與正文已發表之數字對帳。

【四圖】
  fig_Hi_H1_dwell_dist   LTE-only 停留窗數分布（全體／resident／edge），標示 12 窗
  fig_Hi_H2_edge_ue      28 個 UE-run 之 LTE-only 佔比排序圖，標示分群門檻 0.55、中位數與最大間隙
  fig_Hi_H3_geom_reject  幾何分布適合度：觀測 vs 幾何（MLE）期望次數，三群之 χ² 與 α = 0.01 臨界值
  fig_Hi_H4_teleport     D2 完整性檢查：逐 seed 乾淨跨 mmWave cell 轉移數（D-SH、D-C）與注入瞬移之偵測數

【定義（沿用 run_Hi_experiments.py，不另定義）】
  狀態序列、停留事件、D2 偵測、瞬移注入均直接 import run_Hi_experiments 之函式。
  LTE-only 佔比 = LTE-only 窗數 / 有出現之窗數（與 run_Hi_D1_performance.ue_lte_fraction 相同）。
  分群：佔比 ≥ 0.55 為 edge。
  幾何分布適合度：p̂ = 1 / 平均停留；分箱 {1, 2, 3, 4, 5, ≥ 6}；df = 6 − 1 − 1 = 4；
  臨界值取 α = 0.01（χ²_{0.99}(4) = 13.277）。

【內建檢查：須重現正文已發表之數字，否則停止、不產圖】
  4.8.1  停留 ≤ 12 窗之比例四捨五入為 97%
  4.8.2  χ²：resident 38.5、edge 58.1、全體 191.4
  4.8.4  D-SH 乾淨跨 mmWave cell 轉移 = 0；注入瞬移 28 例、偵測 28 例；D-C 乾淨轉移 = 0
  4.8.6  分群 14／14
  （中位數與最大間隙另行輸出；正文之 0.5535 與「最大間隙 0.333–0.397」與本腳本之重算不同，
   以腳本輸出為準，見輸出 JSON 之 corrections。）

【輸出】
  <out>/fig_Hi_H1_dwell_dist.png、fig_Hi_H2_edge_ue.png、fig_Hi_H3_geom_reject.png、fig_Hi_H4_teleport.png
  <out>/Hi_baseline_figs.json
"""
import os
import sys
import glob
import json
import argparse
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_Hi_experiments import (load, state_seq, dwell_events, mmw_cell_seq,
                                detect_D2, inject_teleport)

ROOT = os.path.expanduser("~/oran-zt-kpm-verification/data")
DSH = os.path.join(ROOT, "si_lstm_seeds")
DC = os.path.join(ROOT, "batchFinal_seeds")
OUT_DIR = os.path.join(ROOT, "results")
EDGE_SPLIT = 0.55
K_BIN = 5
CHI2_CRIT_001_DF4 = 13.277
PUBLISHED = {"le12_pct": 97, "chi2": {"resident": 38.5, "edge": 58.1, "all": 191.4},
             "d2_clean_dsh": 0, "d2_inject": 28, "d2_detect": 28, "d2_clean_dc": 0,
             "split": (14, 14)}


def per_run(files):
    runs = []
    for f in files:
        sd = os.path.basename(f).split("seed")[-1].replace(".txt", "")
        rec = load(f)
        aw = sorted(set(w for im, wm in rec.items() for w in wm))
        for im, wm in sorted(rec.items()):
            s = state_seq(wm, aw)
            na = sum(1 for x in s if x != "absent")
            fr = sum(1 for x in s if x == "lte") / na if na else 0.5
            runs.append({"seed": sd, "imsi": im, "lte_frac": fr, "dwell": dwell_events(s),
                         "d2_clean": detect_D2(mmw_cell_seq(wm, aw), s),
                         "_ms": mmw_cell_seq(wm, aw), "_st": s, "_n": len(aw)})
    return runs


def geom_chi2(ev):
    ev = np.array(ev); n = len(ev); p = 1 / ev.mean()
    ks = np.arange(1, K_BIN + 1)
    obs = np.array([(ev == k).sum() for k in ks] + [(ev > K_BIN).sum()], float)
    exp = np.array(list(n * p * (1 - p) ** (ks - 1)) + [n * (1 - p) ** K_BIN])
    return float(((obs - exp) ** 2 / exp).sum()), obs.tolist(), exp.tolist(), float(p), n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=OUT_DIR)
    args = ap.parse_args()
    fs = sorted(glob.glob(os.path.join(DSH, "ues1_t300_seed*.txt")))
    fc = sorted(glob.glob(os.path.join(DC, "seed*.txt")))
    if len(fs) != 4:
        raise SystemExit(f"D-SH 應為 4 檔，找到 {len(fs)}")
    runs = per_run(fs)
    runs_dc = per_run(fc) if fc else []

    allev = [d for r in runs for d in r["dwell"]]
    grp = {"resident": [d for r in runs if r["lte_frac"] < EDGE_SPLIT for d in r["dwell"]],
           "edge": [d for r in runs if r["lte_frac"] >= EDGE_SPLIT for d in r["dwell"]],
           "all": allev}
    le12 = float(np.mean(np.array(allev) <= 12))
    fr = np.sort([r["lte_frac"] for r in runs])
    gaps = np.diff(fr); gmax = float(gaps.max())
    tied = [(float(fr[i]), float(fr[i + 1])) for i in range(len(gaps)) if abs(gaps[i] - gmax) < 1e-9]
    split = (int((fr < EDGE_SPLIT).sum()), int((fr >= EDGE_SPLIT).sum()))
    chi = {g: geom_chi2(v) for g, v in grp.items()}

    # D2：乾淨與注入（與 run_Hi_experiments.main 相同之注入點與判定）
    clean_dsh = sum(r["d2_clean"] for r in runs)
    per_seed = {}
    nin = det = 0
    for r in runs:
        ps = per_seed.setdefault(r["seed"], {"clean": 0, "inject": 0, "detect": 0})
        ps["clean"] += r["d2_clean"]
        ms2, pos = inject_teleport(r["_ms"], r["_st"], r["_n"] // 2)
        if pos:
            st2 = list(r["_st"]); st2[pos] = "mmw"
            nin += 1; ps["inject"] += 1
            if detect_D2(ms2, st2) > r["d2_clean"]:
                det += 1; ps["detect"] += 1
    clean_dc = sum(r["d2_clean"] for r in runs_dc)
    dc_per_seed = {}
    for r in runs_dc:
        dc_per_seed[r["seed"]] = dc_per_seed.get(r["seed"], 0) + r["d2_clean"]

    # ---- 對帳 ----
    bad = []
    if round(le12 * 100) != PUBLISHED["le12_pct"]:
        bad.append(("≤12 窗比例", PUBLISHED["le12_pct"], le12))
    for g, v in PUBLISHED["chi2"].items():
        if round(chi[g][0], 1) != v:
            bad.append((f"χ² {g}", v, round(chi[g][0], 1)))
    if clean_dsh != PUBLISHED["d2_clean_dsh"] or nin != PUBLISHED["d2_inject"] or det != PUBLISHED["d2_detect"]:
        bad.append(("D2 D-SH", (0, 28, 28), (clean_dsh, nin, det)))
    if runs_dc and clean_dc != PUBLISHED["d2_clean_dc"]:
        bad.append(("D2 D-C 乾淨", 0, clean_dc))
    if split != PUBLISHED["split"]:
        bad.append(("分群", PUBLISHED["split"], split))
    print("── 對帳（正文已發表之數字）──")
    if bad:
        for b in bad:
            print("  ✗", b)
        raise SystemExit("與正文不一致，停止，不產圖。")
    print(f"  ✓ ≤12 窗 {le12:.4f}；χ² {[round(chi[g][0], 1) for g in ('resident', 'edge', 'all')]}；"
          f"D2 D-SH 乾淨 {clean_dsh}、注入 {nin}／偵測 {det}；D-C 乾淨 {clean_dc}（{len(dc_per_seed)} seed）；分群 {split}")
    print(f"  另：LTE-only 佔比中位數 {float(np.median(fr)):.4f}；最大間隙 {gmax:.4f}，並列於 {tied}\n")

    os.makedirs(args.out_dir, exist_ok=True)
    res = {"n_dwell_events": len(allev), "le12_frac": le12, "dwell_max": int(max(allev)),
           "lte_frac_sorted": fr.tolist(), "lte_frac_median": float(np.median(fr)),
           "max_gap": gmax, "max_gap_tied_at": tied, "split_resident_edge": split,
           "chi2": {g: {"chi2": c[0], "obs": c[1], "exp": c[2], "p_hat": c[3], "n": c[4],
                        "df": K_BIN + 1 - 2} for g, c in chi.items()},
           "chi2_crit_alpha001_df4": CHI2_CRIT_001_DF4,
           "d2": {"dsh_clean": clean_dsh, "dsh_inject": nin, "dsh_detect": det, "dsh_per_seed": per_seed,
                  "dc_clean": clean_dc, "dc_per_seed": dc_per_seed},
           "corrections": {"median_text_0.5535": float(np.median(fr)),
                           "max_gap_text_0.333-0.397": tied,
                           "critical_value_text_approx13": "chi2_0.99(df=4) = 13.277 (alpha = 0.01)"}}
    with open(os.path.join(args.out_dir, "Hi_baseline_figs.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, ensure_ascii=False)
    draw(res, grp, args.out_dir)


def draw(res, grp, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    C = {"resident": "#1971c2", "edge": "#e67700", "all": "#495057"}

    # H1
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4))
    mx = res["dwell_max"]
    bins = np.arange(0.5, mx + 1.5, 1)
    for g in ("resident", "edge"):
        a1.hist(grp[g], bins=bins, alpha=0.6, color=C[g], label=f"{g} (n={len(grp[g])})")
    a1.set_yscale("log"); a1.set_xlabel("LTE-only dwell (windows)"); a1.set_ylabel("events (log)")
    a1.axvline(12.5, color="k", ls=":", lw=1); a1.legend(fontsize=8); a1.grid(alpha=0.3)
    for g in ("resident", "edge", "all"):
        v = np.sort(grp[g]); a2.step(v, np.arange(1, len(v) + 1) / len(v), where="post", color=C[g], label=g)
    a2.axvline(12, color="k", ls=":", lw=1)
    a2.text(13, 0.5, f"{res['le12_frac']*100:.1f}% ≤ 12", fontsize=9)
    a2.set_xscale("log"); a2.set_xlabel("LTE-only dwell (windows, log)"); a2.set_ylabel("CDF")
    a2.legend(fontsize=8); a2.grid(alpha=0.3)
    fig.suptitle(f"H_i clean baseline: LTE-only dwell distribution (D-SH, {res['n_dwell_events']} events)", fontsize=11)
    fig.tight_layout(); fig.savefig(os.path.join(out, "fig_Hi_H1_dwell_dist.png"), dpi=200); plt.close(fig)

    # H2
    fig, ax = plt.subplots(figsize=(8, 4))
    fr = res["lte_frac_sorted"]
    ax.bar(range(len(fr)), fr, color=[C["edge"] if x >= EDGE_SPLIT else C["resident"] for x in fr])
    ax.axhline(EDGE_SPLIT, color="k", ls="--", lw=1, label=f"split = {EDGE_SPLIT}")
    ax.axhline(res["lte_frac_median"], color="#868e96", ls=":", lw=1, label=f"median = {res['lte_frac_median']:.4f}")
    for lo, hi in res["max_gap_tied_at"]:
        ax.axhspan(lo, hi, color="#ffe066", alpha=0.35, lw=0)
    ax.set_xlabel("UE-run (sorted)"); ax.set_ylabel("LTE-only fraction")
    ax.set_title(f"Edge/resident split {res['split_resident_edge'][1]}/{res['split_resident_edge'][0]} "
                 f"(shaded = tied largest gaps {res['max_gap']:.4f}); exploratory", fontsize=10)
    ax.legend(fontsize=8); ax.grid(alpha=0.3, axis="y")
    fig.tight_layout(); fig.savefig(os.path.join(out, "fig_Hi_H2_edge_ue.png"), dpi=200); plt.close(fig)

    # H3
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.8))
    labels = ["1", "2", "3", "4", "5", "≥6"]
    for ax, g in zip(axes, ("resident", "edge", "all")):
        c = res["chi2"][g]; x = np.arange(len(labels))
        ax.bar(x - 0.2, c["obs"], 0.4, color=C[g], label="observed")
        ax.bar(x + 0.2, c["exp"], 0.4, color="#adb5bd", label="geometric (MLE)")
        ax.set_xticks(x); ax.set_xticklabels(labels); ax.set_xlabel("dwell (windows)")
        ax.set_title(f"{g} (n={c['n']}, p̂={c['p_hat']:.3f}): χ² = {c['chi2']:.1f}\n"
                     f"df={c['df']}, critical value at α=0.01: {res['chi2_crit_alpha001_df4']:.2f}", fontsize=9.5)
        ax.grid(alpha=0.3, axis="y")
    axes[0].set_ylabel("events"); axes[0].legend(fontsize=8)
    fig.suptitle("Geometric goodness-of-fit is rejected in all groups → non-parametric D1", fontsize=11)
    fig.tight_layout(); fig.savefig(os.path.join(out, "fig_Hi_H3_geom_reject.png"), dpi=200); plt.close(fig)

    # H4
    d2 = res["d2"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 3.8), gridspec_kw={"width_ratios": [1, 1.4]})
    sd = sorted(d2["dsh_per_seed"]); x = np.arange(len(sd))
    a1.bar(x - 0.25, [d2["dsh_per_seed"][s]["clean"] for s in sd], 0.25, color="#495057", label="clean transitions")
    a1.bar(x, [d2["dsh_per_seed"][s]["inject"] for s in sd], 0.25, color="#adb5bd", label="injected teleports")
    a1.bar(x + 0.25, [d2["dsh_per_seed"][s]["detect"] for s in sd], 0.25, color="#c92a2a", label="detected")
    for i, s_ in enumerate(sd):
        a1.text(i - 0.25, 0.1, str(d2["dsh_per_seed"][s_]["clean"]), ha="center", fontsize=9, fontweight="bold")
    a1.set_xticks(x); a1.set_xticklabels(sd); a1.set_title("D-SH (300 s)", fontsize=10)
    a1.set_ylabel("count"); a1.legend(fontsize=8); a1.grid(alpha=0.3, axis="y")
    sc = sorted(d2["dc_per_seed"]); xc = np.arange(len(sc))
    a2.bar(xc, [d2["dc_per_seed"][s] for s in sc], 0.5, color="#495057")
    a2.set_xticks(xc); a2.set_xticklabels(sc, rotation=45, fontsize=8)
    for i, s_ in enumerate(sc):
        a2.text(i, 0.05, str(d2["dc_per_seed"][s_]), ha="center", fontsize=10, fontweight="bold")
    a2.set_ylim(0, 1); a2.set_yticks([0, 1]); a2.set_ylabel("count")
    a2.set_title(f"D-C (60 s): clean cross-mmWave transitions = {d2['dc_clean']} in all seeds", fontsize=10)
    a2.grid(alpha=0.3, axis="y")
    fig.suptitle("D2 integrity check — clean baseline is 0 because no legitimate handover occurs (vacuous); "
                 "injected detection is by construction", fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(out, "fig_Hi_H4_teleport.png"), dpi=200); plt.close(fig)
    print(f"圖已存: {out}/fig_Hi_H1_dwell_dist.png, fig_Hi_H2_edge_ue.png, fig_Hi_H3_geom_reject.png, fig_Hi_H4_teleport.png")


if __name__ == "__main__":
    main()
