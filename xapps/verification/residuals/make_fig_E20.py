# -*- coding: utf-8 -*-
"""make_fig_E20.py — E20 圖 F1–F4（讀 E20_error_rates.json）。
用法：python3 make_fig_E20.py [E20_error_rates.json]"""
import os
import sys
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

C1, C2, C3, C4 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#dddcd7"
plt.rcParams.update({"font.size": 9, "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2,
                     "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True})
POL = ["strict", "restrict_annotated"]
ATK = [("A0_step_0.6", "step ×0.6"), ("A0_step_0.8", "step ×0.8"), ("A0_drift_0.01", "drift 1 %/s")]


def _lab(ax, x, y, s):
    ax.text(x, y, s, ha="center", va="bottom", fontsize=7.5, color=INK)


def f1(d, path):
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.8), gridspec_kw={"width_ratios": [1, 1, 1.3]})
    drl = d["DRL_method1"]
    for ax, pol in zip(axes[:2], POL):
        m1 = d["FB1"][pol]
        vals = [m1["FB"], d["FB2"]["2a_marginal"][pol], d["FB2"]["2b_per_UE"][pol]]
        dr = [r["FB1"][pol] for r in drl.values()]
        xs = np.arange(4)
        ax.bar(xs[:3], vals, 0.6, color=[C1, C2, C3])
        ax.errorbar([0], [m1["FB"]], yerr=[[m1["FB"] - m1["seed_min"]], [m1["seed_max"] - m1["FB"]]],
                    fmt="none", ecolor=INK, capsize=4, lw=1)
        ax.bar([3], [np.mean(dr)], 0.6, color=C4)
        ax.errorbar([3], [np.mean(dr)], yerr=[[np.mean(dr) - min(dr)], [max(dr) - np.mean(dr)]],
                    fmt="none", ecolor=INK, capsize=4, lw=1)
        for x, v in zip(xs, vals + [np.mean(dr)]):
            _lab(ax, x, v * 1.02, f"{v:.3f}" if v >= 0.1 else f"{v:.4f}")
        ax.set_xticks(xs, ["M1: D0\n(bar = pooled,\nwhisker = seed\nmin–max)", "M2a:\nmarginal\nrates", "M2b:\nper-UE\nrates", "M1: DRL\n(6 runs,\nmin–max)"])
        ax.set_ylabel("FB: clean (node, window) blocked")
        ax.set_title(f"admission = {pol}", fontsize=10)
        ax.set_ylim(0, max(vals + dr + [m1["seed_max"]]) * 1.12)
        ax.tick_params(axis="x", labelsize=7.5)
    ax = axes[2]
    rules = sorted({r for p in POL for r in d["FB1"][p]["by_rule"]},
                   key=lambda r: -sum(d["FB1"][p]["by_rule"].get(r, 0) for p in POL))
    cols = [C1, C2, C3, C4, "#6250d6", "#e87ba4"]
    left = np.zeros(2)
    for r, c in zip(rules, cols):
        v = np.array([d["FB1"][p]["by_rule"].get(r, 0) for p in POL])
        ax.barh([0, 1], v, left=left, color=c, label=r, edgecolor="white", linewidth=1)
        left += v
    for i, p in enumerate(POL):
        ax.text(left[i] + 80, i, f"{int(left[i])} / {d['FB1'][p]['n']}", va="center", fontsize=8, color=INK)
    ax.set_yticks([0, 1], POL)
    ax.set_xlim(0, left.max() * 1.3)
    ax.set_xlabel("blocked clean (node, window), by rule_id (Method 1, D0)")
    ax.legend(fontsize=7.5, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=2)
    fig.suptitle("E20-F1  False block (correct report blocked) — D-30 clean replay, 15,534 (node, window)", fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.94]); fig.savefig(path, dpi=180); plt.close(fig)


def f2(d, path):
    rows = d["per_ue_run"]
    mc = np.array([r["M_count"] for r in rows]); mf = np.array([r["M_frac"] for r in rows])
    edge = np.array([r["group"] == "edge" for r in rows])
    fig, axes = plt.subplots(2, 2, figsize=(11, 7.5), sharey="row")
    rng = np.random.default_rng(0)
    for row, (key, ylab) in enumerate([("block_share_strict", "share of its 300 windows in which\nits node is blocked with its D1 evidence (strict)"),
                                       ("pivotal_share_strict", "share of windows in which removing\nits D1 evidence alone would admit the node (strict)")]):
        y = np.array([r[key] for r in rows])
        for col, (x, xl) in enumerate([(mc, "M-count: mmWave → LTE-only transitions per 300 s"),
                                       (mf, "M-frac: LTE-only share of present windows")]):
            ax = axes[row, col]
            jit = rng.uniform(-0.25, 0.25, len(x)) if col == 0 else 0
            for sel, c, lab in [(~edge, C1, "resident (M-frac < 0.55)"), (edge, C2, "edge (M-frac ≥ 0.55)")]:
                ax.scatter((x + jit)[sel], y[sel], s=22, color=c, alpha=0.75, edgecolors="white", linewidths=0.5, label=lab)
            ax.set_xlabel(xl)
            if col == 0:
                ax.set_ylabel(ylab, fontsize=8.5)
                rho = d["mobility"]["spearman_Mcount_vs_block_share_strict" if row == 0 else "spearman_Mcount_vs_pivotal_share_strict"]
                ax.set_title(f"Spearman ρ = {rho:.2f}", fontsize=9, loc="right")
            elif row == 0:
                ax.set_title(f"Spearman ρ = {d['mobility']['spearman_Mfrac_vs_block_share_strict']:.2f}", fontsize=9, loc="right")
                ax.axvline(0.55, color=INK2, lw=0.8, ls="--")
            else:
                ax.axvline(0.55, color=INK2, lw=0.8, ls="--")
    h, l = axes[0, 0].get_legend_handles_labels()
    fig.legend(h, l, fontsize=8.5, frameon=False, loc="upper center", bbox_to_anchor=(0.5, 0.955), ncol=2)
    fig.suptitle(f"E20-F2  Which UEs cause false blocks? {len(rows)} UE-runs (8 seeds × 30 UEs), D-30 clean, uebound", fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.93]); fig.savefig(path, dpi=180); plt.close(fig)


def f3(d, path):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.3), sharey=True)
    drl = d["DRL_method1"]
    for ax, pol in zip(axes, POL):
        xs = np.arange(len(ATK)); w = 0.35
        m1 = [d["MF"][a]["MF1"][pol] for a, _ in ATK]; m2 = [d["MF"][a]["MF2"][pol] for a, _ in ATK]
        ax.bar(xs - w / 2, m1, w, color=C1, label="Method 1 (D0, end-to-end)")
        ax.bar(xs + w / 2, m2, w, color=C2, label="Method 2 (composition, independence)")
        for x, v in zip(xs - w / 2, m1): _lab(ax, x, v + 0.01, f"{v:.3f}")
        for x, v in zip(xs + w / 2, m2): _lab(ax, x, v + 0.01, f"{v:.3f}")
        k = "MF1_strict" if pol == "strict" else "MF1_restrict_annotated"
        dr = [r["A-script_worst_by_TPR"][k] for r in drl.values()]
        x = len(ATK)
        ax.bar([x], [np.mean(dr)], 0.5, color=C4, label="Method 1, DRL (6 runs), worst scripted attack")
        ax.errorbar([x], [np.mean(dr)], yerr=[[np.mean(dr) - min(dr)], [max(dr) - np.mean(dr)]], fmt="none", ecolor=INK, capsize=4, lw=1)
        _lab(ax, x, max(dr) + 0.01, f"{min(dr):.3f}–{max(dr):.3f}")
        ax.set_xticks(list(xs) + [x], [l for _, l in ATK] + ["DRL vs worst\n(step ×0.8)"])
        ax.set_title(f"admission = {pol}", fontsize=10); ax.set_ylim(0, 1.1)
        ax.set_ylabel("MF: tampered (node, window) admitted")
    axes[0].legend(fontsize=7.5, frameon=False, loc="upper left")
    fig.suptitle("E20-F3  Missed falsification (falsified report kept) — scripted attacks, 56 episodes each", fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.93]); fig.savefig(path, dpi=180); plt.close(fig)


def f4(d, path):
    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    mk = {"A0_step_0.6": "o", "A0_step_0.8": "s", "A0_drift_0.01": "^"}
    for pol, c in zip(POL, [C1, C2]):
        fb = d["FB1"][pol]["FB"]
        for a, lab in ATK:
            ax.scatter(fb, d["MF"][a]["MF1"][pol], marker=mk[a], s=70, color=c, edgecolors="white", linewidths=0.8, zorder=3)
        k = "MF1_strict" if pol == "strict" else "MF1_restrict_annotated"
        for r in d["DRL_method1"].values():
            ax.scatter(r["FB1"][pol], r["A-script_worst_by_TPR"][k], marker="D", s=30, facecolors="none", edgecolors=c, linewidths=1.1, zorder=2)
    for pol, c in zip(POL, [C1, C2]):
        ax.scatter([], [], color=c, s=50, label=f"admission = {pol}")
    for a, lab in ATK:
        ax.scatter([], [], marker=mk[a], color=INK2, s=40, label=f"D0 vs {lab}")
    ax.scatter([], [], marker="D", facecolors="none", edgecolors=INK2, s=30, label="DRL (6 runs) vs worst scripted (×0.8)")
    ax.set_xlim(-0.02, 0.6); ax.set_ylim(-0.02, 1.05)
    ax.set_xlabel("FB: correct report blocked (clean replay)")
    ax.set_ylabel("MF: falsified report kept (scripted attack)")
    ax.annotate("ideal", (0, 0), (0.05, 0.08), fontsize=8, color=INK2, arrowprops=dict(arrowstyle="->", color=INK2, lw=0.8))
    ax.legend(fontsize=7.5, frameon=False, loc="upper right")
    ax.set_title("E20-F4  The two errors on one plane (Method 1)", fontsize=11)
    fig.tight_layout(); fig.savefig(path, dpi=180); plt.close(fig)


def draw_all(d, out):
    for name, fn in [("fig_E20_F1_false_block.png", f1), ("fig_E20_F2_mobility.png", f2),
                     ("fig_E20_F3_missed_falsification.png", f3), ("fig_E20_F4_tradeoff.png", f4)]:
        fn(d, os.path.join(out, name)); print("圖已存:", os.path.join(out, name))


if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "results",
                                                          "d30_fusion_order", "severity", "E20", "E20_error_rates.json")
    draw_all(json.load(open(p, encoding="utf-8")), os.path.dirname(os.path.abspath(p)))
