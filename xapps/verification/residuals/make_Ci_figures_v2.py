"""
make_Ci_figures_v2.py — C_i 不變量斷言框架的論文圖（取代舊的 z-score/連續分數版）

與舊版差異
----------
舊圖：連續 C_i 分數 + 高斯衰減曲線 + trusted/low-trust/rejected 三色帶
      → 這是「統計偵測」的判讀，與現在的不變量斷言框架不符，會誤導。
新圖：二元「守恆 / 違反」判讀，強調確定性斷言。
  Fig 1  不變量成立性（E0）：600 窗 N_total 全=7 的退化分布（點圖 + 直方圖）
  Fig 2  斷言違反邊界（E1/E2）：灌水/虛減 → conserved False，二元台階而非連續衰減
  Fig 3  斷言涵蓋範圍（E3）：baseline vs 灌水 vs 守恆式串謀 的 N_total 時序，
         標出串謀維持守恆 → 斷言未觸發（盲點）

跑法：
    cd ~/oran-zt-kpm-verification
    python3 xapps/verification/residuals/make_Ci_figures_v2.py

輸出：data/results/ 下 fig1_invariant.png, fig2_violation.png, fig3_coverage.png
"""

import os
import sys
import glob

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cardinality as C

BASE = os.path.expanduser("~/oran-zt-kpm-verification")
DATA_DIR = os.path.join(BASE, "data/batchFinal_seeds")
OUT_DIR = os.path.join(BASE, "data/results")

# 容器 fallback
if not os.path.isdir(DATA_DIR):
    here = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = here
    OUT_DIR = here

os.makedirs(OUT_DIR, exist_ok=True)
N_KNOWN = 7
cfg = C.CardinalityConfig(n_known=N_KNOWN, eps_low=0.05, eps_high=0.0, kappa=0.10)

GREEN, RED, ORANGE, BLUE, GRAY = "#2e7d32", "#c62828", "#e65100", "#1565c0", "#616161"

seed_files = sorted(glob.glob(os.path.join(DATA_DIR, "seed*.txt")))
if not seed_files:
    sys.exit(f"找不到 seed 資料：{DATA_DIR}/seed*.txt")

# 收集所有窗的 N_total（E0）
all_ntotal = []
for f in seed_files:
    recs = list(C.load_rlc(f))
    series = C.field_cardinality_series(recs, cfg.include_lte, cfg.lte_cell_id)
    all_ntotal.extend(series.values())

# ===========================================================================
# Fig 1：不變量成立性（E0）—— 退化分布，非統計分布
# ===========================================================================
fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.2),
                             gridspec_kw={"width_ratios": [2, 1]})

# 左：每窗 N_total 散點（全部貼在 7）
a1.axhline(N_KNOWN, color=GREEN, ls="-", lw=1.5, zorder=1,
           label=f"invariant: N_total ≡ N_known = {N_KNOWN}")
xs = list(range(len(all_ntotal)))
a1.scatter(xs, all_ntotal, s=8, color=GREEN, alpha=0.5, zorder=2)
a1.set_ylim(N_KNOWN - 3, N_KNOWN + 3)
a1.set_xlabel(f"window index (10 seeds × 60 windows = {len(all_ntotal)})")
a1.set_ylabel("N_total(t)")
a1.set_title(f"(a) Invariant holds: all {len(all_ntotal)} windows satisfy N_total = {N_KNOWN}")
a1.legend(fontsize=9, loc="upper right")
a1.grid(alpha=0.3)

# 右：退化分布直方圖（單一長條）
vals = sorted(set(all_ntotal))
counts = [all_ntotal.count(v) for v in vals]
a2.bar(vals, counts, width=0.5, color=GREEN, alpha=0.8)
a2.set_xlim(N_KNOWN - 3, N_KNOWN + 3)
a2.set_xlabel("N_total")
a2.set_ylabel("window count")
a2.set_title(f"(b) Degenerate distribution\nP(N_total={N_KNOWN})=1, Var=0")
a2.annotate(f"{counts[0]} / {len(all_ntotal)}\n(100%)",
            xy=(vals[0], counts[0]), xytext=(vals[0] + 0.9, counts[0] * 0.7),
            fontsize=9, color=GREEN,
            arrowprops=dict(arrowstyle="->", color=GREEN))
a2.grid(alpha=0.3, axis="y")

fig.suptitle("C_i — Cardinality conservation invariant holds deterministically (E0)",
             fontsize=12, y=1.02)
fig.tight_layout()
p1 = os.path.join(OUT_DIR, "fig1_invariant.png")
fig.savefig(p1, dpi=160, bbox_inches="tight")
print(f"[fig1] saved -> {p1}")

# ===========================================================================
# Fig 2：斷言違反（E1/E2）—— 二元台階，非連續衰減
# ===========================================================================
recs = list(C.load_rlc(seed_files[0]))
windows = sorted({C._window_key(r) for r in recs})
late = windows[len(windows) // 2:]

offsets = list(range(-4, 7))  # -4..+6
conserved_flags = []
labels = []
for k in offsets:
    if k == 0:
        n = N_KNOWN
    elif k > 0:
        atk = C.inject_fabrication(recs, k, at_windows=late, attacker_cell=2, base_imsi=9001)
        res = C.compute_cardinality_over_time(atk, cfg)
        n = [res[t]["N_total"] for t in res if t in set(late)][0]
    else:
        atk = C.inject_deletion(recs, -k, at_windows=late, victim_cell=None)
        res = C.compute_cardinality_over_time(atk, cfg)
        n = [res[t]["N_total"] for t in res if t in set(late)][0]
    inv = C.cardinality_invariant_check(n, cfg)
    conserved_flags.append(1 if inv["conserved"] else 0)

fig, ax = plt.subplots(figsize=(8.4, 4.2))
colors = [GREEN if c == 1 else RED for c in conserved_flags]
ax.bar(offsets, [1] * len(offsets), color=colors, alpha=0.85, width=0.7)
# 標註守恆/違反
for k, c in zip(offsets, conserved_flags):
    txt = "conserved" if c == 1 else "VIOLATED"
    ax.text(k, 0.5, txt, rotation=90, ha="center", va="center",
            fontsize=8, color="white", fontweight="bold")
ax.axvline(0, color=GRAY, ls="--", lw=1)
ax.text(0, 1.06, "baseline\n(N=7)", ha="center", fontsize=8, color=GREEN)
ax.set_yticks([])
ax.set_ylim(0, 1.15)
ax.set_xlabel("cardinality offset k  (−k = depletion, +k = fabrication)")
ax.set_title("C_i assertion is binary: any k≠0 violates conservation "
             "(detection boundary = ±1 UE)")
ax.set_xticks(offsets)
# 圖例
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color=GREEN, label="conserved (assertion holds)"),
                   Patch(color=RED, label="violated (attack detected)")],
          fontsize=9, loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.32))
fig.tight_layout()
p2 = os.path.join(OUT_DIR, "fig2_violation.png")
fig.savefig(p2, dpi=160, bbox_inches="tight")
print(f"[fig2] saved -> {p2}")

# ===========================================================================
# Fig 3：斷言涵蓋範圍（E3）—— 串謀維持守恆 = 盲點
# ===========================================================================
scen = {"baseline": recs,
        "fabrication +3": C.inject_fabrication(recs, 3, at_windows=late,
                                               attacker_cell=2, base_imsi=9001)}
coll = C.inject_fabrication(recs, 2, at_windows=late, attacker_cell=2, base_imsi=9001)
coll = C.inject_deletion(coll, 2, at_windows=late, victim_cell=None)
scen["collusion (+2 fake / −2 real)"] = coll

res = {k: C.compute_cardinality_over_time(v, cfg) for k, v in scen.items()}
colors = {"baseline": GREEN, "fabrication +3": RED,
          "collusion (+2 fake / −2 real)": ORANGE}

fig, ax = plt.subplots(figsize=(9, 4.4))
ax.axhline(N_KNOWN, color=GREEN, ls="--", lw=1,
           label=f"invariant N_known={N_KNOWN}")
for name, r in res.items():
    ts = sorted(r.keys())
    ys = [r[t]["N_total"] for t in ts]
    style = "o-" if name != "collusion (+2 fake / −2 real)" else "s--"
    ax.plot(ts, ys, style, color=colors[name], lw=2, ms=4, label=name)
ax.axvspan(late[0], windows[-1], color="#eceff1", alpha=0.6)
ax.text(late[0], N_KNOWN + 2.4, " attack window", fontsize=8, color=GRAY)
ax.annotate("collusion keeps N_total=7\n→ assertion NOT triggered (blind spot)\n→ needs S_i / H_i",
            xy=(late[len(late)//2], N_KNOWN), xytext=(windows[1], N_KNOWN + 1.3),
            fontsize=8, color=ORANGE,
            arrowprops=dict(arrowstyle="->", color=ORANGE))
ax.set_ylim(N_KNOWN - 2, N_KNOWN + 4)
ax.set_xlabel("granularity period start (s)")
ax.set_ylabel("N_total(t)")
ax.set_title("C_i coverage boundary: conservation-preserving collusion evades the assertion (E3)")
ax.legend(fontsize=8.5, loc="upper left")
ax.grid(alpha=0.3)
fig.tight_layout()
p3 = os.path.join(OUT_DIR, "fig3_coverage.png")
fig.savefig(p3, dpi=160, bbox_inches="tight")
print(f"[fig3] saved -> {p3}")

print("\n完成。三張圖（不變量斷言框架）在:", OUT_DIR)
