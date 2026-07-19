"""
make_Ci_figures.py — 從 Ci_experiment_results.json + 10 seed 資料產出論文三張圖

跑法（在你機器上）：
    cd ~/oran-zt-kpm-verification
    python3 xapps/verification/residuals/make_Ci_figures.py

輸出（data/results/ 底下）：
    fig1_Ci_sweep.png        灌水/虛減強度掃描（偵測邊界圖，RQ1 主圖）
    fig2_Ci_timeseries.png   baseline vs 灌水 vs 串謀 時間序列（含 C_i 盲點，E3 視覺化）
    fig3_Ci_response.png     響應曲線 + N_known=7 vs 35 敏感度對照（參數解釋圖）
"""

import os
import sys
import json
import glob
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cardinality as C

BASE = os.path.expanduser("~/oran-zt-kpm-verification")
RESULTS_JSON = os.path.join(BASE, "data/results/Ci_experiment_results.json")
DATA_DIR = os.path.join(BASE, "data/batchFinal_seeds")
OUT_DIR = os.path.join(BASE, "data/results")

# 容器測試用 fallback（在你機器上不會觸發）
if not os.path.exists(RESULTS_JSON):
    RESULTS_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "Ci_experiment_results.json")
    OUT_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seeds")

os.makedirs(OUT_DIR, exist_ok=True)

with open(RESULTS_JSON) as f:
    R = json.load(f)

cfg = C.CardinalityConfig.from_dict(R["config"])
N_KNOWN = cfg.n_known
n_lo, n_hi = cfg.bounds()
TH_HIGH, TH_LOW = 0.90, 0.50

GREEN, RED, ORANGE, BLUE, GRAY = "#2e7d32", "#c62828", "#e65100", "#1565c0", "#616161"


def shade_grades(ax):
    ax.axhspan(TH_HIGH, 1.02, color="#c8e6c9", alpha=0.45)
    ax.axhspan(TH_LOW, TH_HIGH, color="#fff9c4", alpha=0.55)
    ax.axhspan(-0.02, TH_LOW, color="#ffcdd2", alpha=0.45)
    ax.axhline(TH_HIGH, color=GRAY, ls=":", lw=1)
    ax.axhline(TH_LOW, color=GRAY, ls=":", lw=1)


# ===========================================================================
# 圖 1：灌水/虛減強度掃描（RQ1 偵測邊界主圖）
# ===========================================================================
fab = R["E1_fabrication"]
dep = R["E2_depletion"]

fig, ax = plt.subplots(figsize=(7.2, 4.6))
shade_grades(ax)

xs_f = [row["amount"] for row in fab]
ys_f = [row["C_i_mean"] for row in fab]
xs_d = [-row["drop"] for row in dep]
ys_d = [row["C_i_mean"] for row in dep]

ax.plot(xs_f, ys_f, "o-", color=RED, lw=2, ms=7,
        label="fabrication (+k fake IMSI)")
ax.plot(xs_d, ys_d, "s-", color=ORANGE, lw=2, ms=7,
        label="depletion (−k real IMSI)")
ax.plot([0], [1.0], "D", color=GREEN, ms=9, label="baseline (k=0), 600 windows, std=0")

for x, y in zip(xs_f, ys_f):
    ax.annotate(f"{y:.3f}", (x, y), textcoords="offset points",
                xytext=(0, 9), ha="center", fontsize=7.5, color=RED)
for x, y in zip(xs_d, ys_d):
    ax.annotate(f"{y:.3f}", (x, y), textcoords="offset points",
                xytext=(0, 9), ha="center", fontsize=7.5, color=ORANGE)

ax.text(max(xs_f) - 0.1, TH_HIGH + 0.045, "trusted", fontsize=8, ha="right", color="#33691e")
ax.text(max(xs_f) - 0.1, (TH_LOW + TH_HIGH) / 2, "low-trust", fontsize=8, ha="right", color="#8d6e63")
ax.text(max(xs_f) - 0.1, TH_LOW / 2, "rejected", fontsize=8, ha="right", color="#b71c1c")

ax.set_xlabel("injected cardinality offset k  (fake IMSIs added / real IMSIs dropped)")
ax.set_ylabel("C_i")
ax.set_ylim(-0.05, 1.08)
ax.set_title(f"C_i detection boundary — identical across 10 seeds (N_known={N_KNOWN}, "
             f"eps_low={cfg.eps_low}, eps_high={cfg.eps_high})")
ax.legend(fontsize=8, loc="center right")
ax.grid(alpha=0.3)
fig.tight_layout()
p1 = os.path.join(OUT_DIR, "fig1_Ci_sweep.png")
fig.savefig(p1, dpi=160, bbox_inches="tight")
print(f"[fig1] saved -> {p1}")

# ===========================================================================
# 圖 2：時間序列 baseline vs 灌水+3 vs 串謀(灌2丟2)——含 C_i 盲點
#        需要 seed 原始資料；預設用第一個 seed
# ===========================================================================
seed_files = sorted(glob.glob(os.path.join(DATA_DIR, "seed*.txt")))
if seed_files:
    recs = list(C.load_rlc(seed_files[0]))
    seed_name = os.path.basename(seed_files[0])
    windows = sorted({C._window_key(r) for r in recs})
    late = windows[len(windows) // 2:]

    scen = {
        "baseline": recs,
        "fabrication +3": C.inject_fabrication(recs, 3, at_windows=late,
                                               attacker_cell=2, base_imsi=9001),
    }
    coll = C.inject_fabrication(recs, 2, at_windows=late, attacker_cell=2, base_imsi=9001)
    coll = C.inject_deletion(coll, 2, at_windows=late, victim_cell=None)
    scen["collusion (+2 fake, −2 real)"] = coll

    res = {k: C.compute_cardinality_over_time(v, cfg) for k, v in scen.items()}
    colors = {"baseline": GREEN, "fabrication +3": RED,
              "collusion (+2 fake, −2 real)": ORANGE}

    fig, (a1, a2) = plt.subplots(2, 1, figsize=(8.6, 6.4), sharex=True)

    a1.axhline(N_KNOWN, color=GREEN, ls="--", lw=1,
               label=f"N_known={N_KNOWN} (closed NPN population)")
    for name, r in res.items():
        ts = list(r.keys())
        a1.plot(ts, [r[t]["N_total"] for t in ts], "-", color=colors[name],
                lw=2, label=name, marker="o", ms=3)
    a1.axvspan(late[0], windows[-1], color="#eceff1", alpha=0.6)
    a1.text(late[0], N_KNOWN + 2.4, " attack window", fontsize=8, color=GRAY)
    a1.annotate("collusion keeps N_total = N_known\n→ invisible to C_i (blind spot)",
                xy=(late[len(late)//2], N_KNOWN), xytext=(windows[2], N_KNOWN + 1.4),
                fontsize=8, color=ORANGE,
                arrowprops=dict(arrowstyle="->", color=ORANGE))
    a1.set_ylabel("N_total(t)")
    a1.set_title(f"Field-wide cardinality & C_i under attack ({seed_name})")
    a1.legend(fontsize=8, loc="upper left")
    a1.grid(alpha=0.3)

    shade_grades(a2)
    for name, r in res.items():
        ts = list(r.keys())
        a2.plot(ts, [r[t]["C"] for t in ts], "-", color=colors[name],
                lw=2, label=name, marker="o", ms=3)
    a2.annotate("C_i = 1.0 under collusion\n→ motivates S_i / H_i",
                xy=(late[len(late)//2], 1.0), xytext=(late[0], 0.62),
                fontsize=8, color=ORANGE,
                arrowprops=dict(arrowstyle="->", color=ORANGE))
    a2.set_ylim(-0.05, 1.08)
    a2.set_xlabel("granularity period start (s)")
    a2.set_ylabel("C_i(t)")
    a2.legend(fontsize=8, loc="center left")
    a2.grid(alpha=0.3)

    fig.tight_layout()
    p2 = os.path.join(OUT_DIR, "fig2_Ci_timeseries.png")
    fig.savefig(p2, dpi=160, bbox_inches="tight")
    print(f"[fig2] saved -> {p2}")
else:
    print(f"[fig2] SKIP：找不到 seed 資料（{DATA_DIR}/seed*.txt）")

# ===========================================================================
# 圖 3：響應曲線 + 場域規模敏感度（N_known=7 vs 35）
# ===========================================================================
fig, (b1, b2) = plt.subplots(1, 2, figsize=(11.5, 4.4))

# (a) 響應曲線（以實際 config）
xs = [x * 0.05 for x in range(0, int(N_KNOWN * 2 / 0.05) + 1)]
ys = [C.cardinality_residual(x, cfg) for x in xs]
b1.plot(xs, ys, "-", color=BLUE, lw=2)
b1.axvspan(n_lo, n_hi, color="#a5d6a7", alpha=0.4,
           label=f"deadband [{n_lo:.2f}, {n_hi:.2f}] (C_i=1)")
b1.axvline(N_KNOWN, color=GREEN, ls="--", lw=1)
b1.axhline(TH_HIGH, color=GRAY, ls=":", lw=1)
b1.axhline(TH_LOW, color=GRAY, ls=":", lw=1)
b1.set_xlabel("N_total")
b1.set_ylabel("C_i")
b1.set_ylim(-0.05, 1.08)
b1.set_title(f"(a) Response curve (N_known={N_KNOWN}, eps_low={cfg.eps_low}, "
             f"eps_high={cfg.eps_high}, kappa={cfg.kappa})")
b1.legend(fontsize=8, loc="lower right")
b1.grid(alpha=0.3)

# (b) 小場域敏感度：C_i vs 灌水數，N_known=7 與 35 對照
cfg35 = C.CardinalityConfig(n_known=35, eps_low=cfg.eps_low,
                            eps_high=cfg.eps_high, kappa=cfg.kappa)
ks = list(range(0, 8))
y7 = [C.cardinality_residual(7 + k, cfg) for k in ks]
y35 = [C.cardinality_residual(35 + k, cfg35) for k in ks]
b2.plot(ks, y7, "o-", color=RED, lw=2, ms=6,
        label=f"N_known=7 (this work: small closed NPN)")
b2.plot(ks, y35, "s--", color=GRAY, lw=2, ms=6,
        label="N_known=35 (larger field, same params)")
b2.axhline(TH_LOW, color=GRAY, ls=":", lw=1)
b2.text(ks[-1], TH_LOW + 0.02, "θ_low", fontsize=8, ha="right", color=GRAY)
b2.set_xlabel("number of fabricated IMSIs k")
b2.set_ylabel("C_i")
b2.set_ylim(-0.05, 1.08)
b2.set_title("(b) Small-field sensitivity: each fake UE is a larger\n"
             "fraction of the population → earlier rejection")
b2.legend(fontsize=8, loc="upper right")
b2.grid(alpha=0.3)

fig.tight_layout()
p3 = os.path.join(OUT_DIR, "fig3_Ci_response.png")
fig.savefig(p3, dpi=160, bbox_inches="tight")
print(f"[fig3] saved -> {p3}")

print("\n完成。三張圖在:", OUT_DIR)
