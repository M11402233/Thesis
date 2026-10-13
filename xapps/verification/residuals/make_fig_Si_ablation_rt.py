#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_fig_Si_ablation_rt.py — Fig 4-5（實際秒、共同集合）：僅讀 E9_operating_regime_rt.json 作圖，不重算。"""
import os
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import datasets as DS

R = DS.results_dir()


def main():
    d = json.load(open(os.path.join(R, "E9_operating_regime_rt.json"), encoding="utf-8"))
    c = d["common"]
    rates = sorted(c["spatial"]["drift"], key=float)
    x = [float(r) * 100 for r in rates]
    fig, ax = plt.subplots(figsize=(8, 4.8))
    for st, col, mk, ls, lab in (("spatial", "#2b8a3e", "o", "-", "spatial consensus reference"),
                                 ("temporal", "#c92a2a", "s", "--",
                                  f"temporal self-reference (previous {d['hist_win_s']} s)")):
        v = [c[st]["drift"][r] for r in rates]
        ax.plot(x, [e["mean"] for e in v], ls, marker=mk, color=col, lw=2, label=lab)
        ax.fill_between(x, [e["seed_min"] for e in v], [e["seed_max"] for e in v], color=col, alpha=0.12)
    ax.set_xscale("log"); ax.set_xticks(x); ax.set_xticklabels([f"{v:g}" for v in x])
    ax.set_xlabel("drift rate (% of mean delay per second, log)")
    ax.set_ylabel("alarm rate in injection interval")
    ax.set_title(f"Reference ablation, real-time drift, common evaluable set "
                 f"({d['availability_of_original_set']['common']['mean'] * 100:.1f}% of windows)\n"
                 f"shaded = seed range; τ_S = {d['tau_S']:g}, identical scale", fontsize=10)
    ax.set_ylim(-0.05, 1.04); ax.legend(fontsize=9); ax.grid(alpha=0.3)
    fig.tight_layout()
    out = os.path.join(R, "fig_Si_reference_ablation_rt.png")
    fig.savefig(out, dpi=200)
    print("寫入", out)


if __name__ == "__main__":
    main()
