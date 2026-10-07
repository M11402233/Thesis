#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_fig_Ci_unified.py — Fig 4-1 ～ 4-4（C_i）之統一版：讀 run_Ci_unified.py 之輸出作圖，不另行判定。

與 make_fig_Ci_final.py 之差異：
  - 注入起點 = 序列中點（不再寫死第 30 窗，適用 60 s 與 300 s 資料）
  - E6（圖 3）、E8（圖 4）之數值直接取自 Ci_unified_<tag>.json
  - 圖 1／2 之軌跡以 run_Ci_unified 之注入函式與 xApp 之 verify_ci 計算
  - 輸出檔名加 _<tag>，不覆寫既有之 fig_Ci_*.png
【內建檢查】圖 1／2 之第一個 seed 之乾淨軌跡須每窗 = N_known（與 JSON 之 E0 一致）。
用法：ZT_DATASET=d28 python3 make_fig_Ci_unified.py --tag unified
"""
import os
import sys
import json
import argparse
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import datasets as DS
import run_Ci_unified as U
X = U.X

C_BASE, C_FAB, C_COL, C_DEP = "#2b8a3e", "#c92a2a", "#e8590c", "#1971c2"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="unified")
    ap.add_argument("--data", default=None, help="預設依 ZT_DATASET")
    ap.add_argument("--out-dir", default=DS.results_dir())
    args = ap.parse_args()
    R = json.load(open(os.path.join(args.out_dir, f"Ci_unified_{args.tag}.json"), encoding="utf-8"))
    meta = R["meta"]
    n_known, attacker = meta["N_known"], meta["attacker_cell"]
    X.N_KNOWN = n_known
    import glob
    files = DS.files() if args.data is None else sorted(glob.glob(os.path.expanduser(args.data)))
    first = [f for f in files if os.path.basename(f) == meta["files"][0]]
    if not first:
        raise SystemExit(f"找不到 JSON 所記錄之第一個檔案 {meta['files'][0]}")
    seed = DS.seed_of(first[0])
    data = U.load(first[0])
    T = len(data); ATK = T // 2

    def traj(mode):
        out = []
        for i, (_, c) in enumerate(data):
            if i >= ATK:
                if mode == "fab":
                    c = U.fab(c, 3, attacker)
                elif mode == "col":
                    c = U.replace(c, 2, 2, attacker)[0]
                elif mode == "dep":
                    c = U.drop_global(c, 2)[0]
            out.append(c)
        return out

    seqs = {m: traj(m) for m in ("base", "fab", "col", "dep")}
    ntot = {m: [len(U.union(c)) for c in s] for m, s in seqs.items()}
    cons = {m: [0 if v else 1 for v, _ in U.judge(s)] for m, s in seqs.items()}
    if set(ntot["base"]) != {n_known}:
        raise SystemExit(f"✗ 檢查：seed {seed} 乾淨軌跡非每窗 = {n_known}")
    print(f"── 檢查：seed {seed} 乾淨軌跡每窗 = {n_known} ✓")
    sfx = f"_{args.tag}"

    def save(fig, name):
        fig.tight_layout()
        p = os.path.join(args.out_dir, f"{name}{sfx}.png")
        fig.savefig(p, dpi=150, bbox_inches="tight"); plt.close(fig); print("  寫入", p)

    # 圖 1：N_total 軌跡
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.axvspan(ATK, T - 1, color="#f1f3f5", zorder=0)
    ax.axhline(n_known, ls="--", color=C_BASE, lw=1.1, zorder=1)
    for m, col, ls, lab in (("base", C_BASE, "-", "baseline"), ("fab", C_FAB, "-", "fabrication (+3 fake)"),
                            ("col", C_COL, "--", "collusion (+2 fake / −2 real)"), ("dep", C_DEP, "-", "depletion (−2 real)")):
        ax.plot(ntot[m], ls, color=col, lw=1.8, label=lab)
    ax.set_xlabel("window (1 s)"); ax.set_ylabel("N_total(t)")
    ax.set_ylim(n_known - 3.5, n_known + 4.5); ax.set_xlim(0, T - 1)
    ax.set_title(f"Field-wide cardinality under four scenarios (seed {seed}, N_known = {n_known}; "
                 f"injection from window {ATK})", fontsize=10.5)
    ax.grid(alpha=0.3); ax.legend(fontsize=9, loc="upper left", ncol=2)
    save(fig, "fig_Ci_1_trajectories")

    # 圖 2：布林判定（經 xApp verify_ci）
    fig, ax = plt.subplots(figsize=(9, 3.9))
    ax.axvspan(ATK, T - 1, color="#f1f3f5", zorder=0)
    for m, col, lw, ls in (("base", C_BASE, 1.8, "-"), ("fab", C_FAB, 2.4, "-"),
                           ("col", C_COL, 1.6, (0, (4, 2))), ("dep", C_DEP, 1.6, (0, (1, 1.5)))):
        ax.step(range(T), cons[m], where="mid", color=col, lw=lw, ls=ls,
                label={"base": "baseline", "fab": "fabrication", "col": "collusion", "dep": "depletion"}[m])
    ax.set_yticks([0, 1]); ax.set_yticklabels(["0  (violated)", "1  (conserved)"], fontsize=9.5)
    ax.set_ylim(-0.28, 1.32); ax.set_xlim(0, T - 1)
    ax.set_xlabel("window (1 s)"); ax.set_ylabel("C_i(t)")
    ax.set_title("C_i boolean assertion — conservation-preserving collusion is invisible", fontsize=11)
    ax.grid(alpha=0.3); ax.legend(fontsize=8.5, loc="center left", ncol=2)
    save(fig, "fig_Ci_2_boolean")

    # 圖 3：E6
    e6 = R["E6"]
    durs = sorted(e6, key=int)
    esc = [100 * e6[d]["escape_rate"] for d in durs]
    fig, ax = plt.subplots(figsize=(7, 4.6))
    ax.bar([str(d) for d in durs], esc, color=[C_FAB if int(d) < meta["L_C"] else C_BASE for d in durs], width=0.55)
    for i, (v, d) in enumerate(zip(esc, durs)):
        ax.text(i, v + 3, f"{v:.0f}%\n({e6[d]['escaped']}/{e6[d]['trials']})", ha="center", fontsize=9.5)
    ax.set_xlabel(f"attack injection duration D (windows),  policy L_C = {meta['L_C']};  unit = {e6[durs[0]]['unit']}")
    ax.set_ylabel("escape rate from hard veto (%)")
    ax.set_title("E6: pulse attacks shorter than L_C evade rejection", fontsize=11)
    ax.set_ylim(0, 125); ax.grid(alpha=0.3, axis="y")
    save(fig, "fig_Ci_3_persistence")

    # 圖 4：E8
    pc = R["E8"]["per_cell"]
    cells = sorted(pc, key=int)
    means = [pc[c]["mean"] for c in cells]; idle = [100 * pc[c]["idle_ratio"] for c in cells]
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    ax.bar([f"cell {c}" for c in cells], means, color=C_DEP, width=0.55)
    for i, (m, idl) in enumerate(zip(means, idle)):
        ax.text(i, m + 0.03 * max(means), f"{m:.2f}", ha="center", fontsize=9.5)
        ax.text(i, -0.10 * max(means), f"idle {idl:.0f}%", ha="center", fontsize=8, color="#868e96")
    ax.set_xlabel("compromised O-DU  (idle % = windows with no attachable UE)")
    ax.set_ylabel("erasable UEs per window (mean)")
    ax.set_title("E8: single-O-DU depletion surface is structurally bounded", fontsize=11)
    ax.set_ylim(-0.145 * max(means), max(means) * 1.30); ax.grid(alpha=0.3, axis="y")
    save(fig, "fig_Ci_4_attack_surface")


if __name__ == "__main__":
    main()
