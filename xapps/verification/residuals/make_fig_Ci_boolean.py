#!/usr/bin/env python3
"""
make_fig_Ci_boolean.py — C_i 布林響應圖(取代舊的高斯響應+N=35對照圖)
純分析:conserved(t) ⟺ N_total = N_known(嚴格相等,零容忍帶),無模擬資料需求。
對齊 4.6.1:布林 safety property,非連續分數、無 κ/deadband/θ。
風格對齊本專案其他圖(fig_Si_vs_lstm / fig_Hi_D1):figsize≈(8,5)、dpi=150、彩色標記、grid alpha=0.3。
"""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT_DIR = os.path.expanduser("~/oran-zt-kpm-verification/data/results")
os.makedirs(OUT_DIR, exist_ok=True)

N_KNOWN = 7
xs = np.arange(0, 15)                     # N_total 候選值
conserved = (xs == N_KNOWN).astype(int)   # 布林:只有 =7 為 1

fig, ax = plt.subplots(figsize=(8, 5))

# 布林階梯
ax.step(xs, conserved, where="mid", color="#343a40", lw=2.0, zorder=2)

# conserved(綠實心,對齊 S_i 綠) vs violated(紅空心,對齊 LSTM/告警紅)
ax.scatter([N_KNOWN], [1], s=90, facecolor="#2b8a3e", edgecolor="#1b5e20",
           linewidths=1.5, zorder=4, label="conserved  (N_total = N_known)")
viol_x = xs[xs != N_KNOWN]
ax.scatter(viol_x, np.zeros_like(viol_x), s=55, facecolor="white",
           edgecolor="#c92a2a", linewidths=1.6, zorder=4,
           label="violated  (N_total ≠ N_known)")

# N_known 參考線 + 標註(移到圖中央偏上,避開左上 note 與圖例)
ax.axvline(N_KNOWN, ls="--", color="#868e96", lw=1.0, zorder=1)
ax.annotate("N_known = 7", xy=(N_KNOWN, 1.0), xytext=(N_KNOWN + 0.35, 0.60),
            fontsize=10, color="#343a40",
            arrowprops=dict(arrowstyle="->", color="#868e96", lw=0.9))

ax.set_xlabel("observed field cardinality  N_total(t)", fontsize=11)
ax.set_ylabel("C_i assertion  conserved(t)", fontsize=11)
ax.set_title("C_i boolean assertion:  conserved ⟺ N_total = N_known  (zero tolerance)",
             fontsize=12)
ax.set_xticks(xs)
ax.set_yticks([0, 1]); ax.set_ylim(-0.15, 1.28)
ax.set_yticklabels(["0  (violated)", "1  (conserved)"])
ax.grid(alpha=0.3, zorder=0)
ax.legend(loc="center right", fontsize=9.5, framealpha=0.95)

# note 放最上緣、獨立一行,不與 N_known 標註重疊
ax.text(0.5, 1.19, "single-window decidable · no threshold · no tolerance band",
        transform=ax.transAxes, ha="center", fontsize=9, color="#666666")

fig.tight_layout()
out = os.path.join(OUT_DIR, "fig_Ci_boolean_response.png")
fig.savefig(out, dpi=150)
print(f"saved {out}")
