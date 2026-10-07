#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_fig_E13_rt.py — Fig 4-7b（實際秒版）：僅讀 E13_tauS_sensitivity_rt.json 作圖，不重算。"""
import os
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

R = os.path.expanduser("~/oran-zt-kpm-verification/data/results")


def main():
    d = json.load(open(os.path.join(R, "E13_tauS_sensitivity_rt.json"), encoding="utf-8"))
    taus = d["taus"]
    res = d["residual_rt"]
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    for st, ls in (("spatial", "-"), ("temporal", "--")):
        for r, mk in (("0.005", "o"), ("0.01", "s"), ("0.02", "^")):
            y = [res[str(t)]["common"][st]["drift"][r]["mean"] for t in taus]
            ax[0].plot(taus, y, ls, marker=mk, label=f"{st} drift {float(r) * 100:g}%/s")
        y = [res[str(t)]["common"][st]["clean_fpr"]["mean"] for t in taus]
        ax[0].plot(taus, y, ls, color="gray", marker="x", label=f"{st} clean FPR")
    ax[0].axvline(4, color="k", lw=0.6, ls=":")
    ax[0].set_xlabel("τ_S"); ax[0].set_ylabel("alarm rate (common set)")
    ax[0].set_title("Residual layer (real seconds)"); ax[0].legend(fontsize=7, ncol=2)
    fu = d["fusion_uebound_L1"]
    ax[1].plot(taus, [fu[str(t)]["frac"]["trusted"] * 100 for t in taus], "o-", label="trusted %")
    ax[1].set_xlabel("τ_S"); ax[1].set_ylabel("trusted (%)"); ax[1].axvline(4, color="k", lw=0.6, ls=":")
    a2 = ax[1].twinx()
    a2.bar(taus, [fu[str(t)]["counts"]["rejected"] for t in taus], width=0.2, alpha=0.4, color="C3", label="clean rejected")
    a2.set_ylabel("clean rejected (of 3,150)")
    ax[1].set_title("Fusion layer (uebound, L_H = 1)")
    h1, l1 = ax[1].get_legend_handles_labels(); h2, l2 = a2.get_legend_handles_labels()
    ax[1].legend(h1 + h2, l1 + l2, fontsize=8, loc="center right")
    fig.tight_layout()
    out = os.path.join(R, "fig_E13_tauS_sensitivity_rt.png")
    fig.savefig(out, dpi=200)
    print("寫入", out)


if __name__ == "__main__":
    main()
