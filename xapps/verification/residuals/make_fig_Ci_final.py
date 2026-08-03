#!/usr/bin/env python3
"""
make_fig_Ci_final.py — C_i 四張獨立圖(取代 fig1_Ci_sweep / fig3_Ci_response /
fig_Ci_boolean_response / fig_Ci_fabrication_sweep 等舊版本)

收錄原則:僅呈現「結果可能與預期相反」之實證發現;純由布林斷言定義推導之結果
(偵測延遲恆為 0、N_total = N_known + k)以正文一句話交代,不佔圖版面。

輸出(各自獨立檔案):
  fig_Ci_1_trajectories.png   N_total(t) 四情境軌跡
  fig_Ci_2_boolean.png        C_i(t) 布林判定(E3 盲點)
  fig_Ci_3_persistence.png    E6 L_C 持續窗脆弱性
  fig_Ci_4_attack_surface.png E8 單點虛減攻擊面
"""
import os, glob, collections
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

DATA_DIR = os.path.expanduser("~/oran-zt-kpm-verification/data/batchFinal_seeds")
OUT_DIR  = os.path.expanduser("~/oran-zt-kpm-verification/data/results")
os.makedirs(OUT_DIR, exist_ok=True)
N_KNOWN, ATK, L_C = 7, 30, 2
C_BASE, C_FAB, C_COL, C_DEP = "#2b8a3e", "#c92a2a", "#e8590c", "#1971c2"

def load(f):
    occ = collections.defaultdict(lambda: collections.defaultdict(set))
    with open(f) as fh:
        fh.readline()
        for line in fh:
            p = line.split("\t")
            if len(p) < 11: continue
            try: w = int(float(p[0])); c = int(p[2]); i = int(p[3])
            except ValueError: continue
            occ[w][i].add(c)
    return occ

files = sorted(glob.glob(os.path.join(DATA_DIR, "seed42*.txt"))) or sorted(glob.glob("seed42*.txt"))
occ0 = load(files[0]); wins = sorted(occ0); T = len(wins)

def traj(mode):
    out = []
    for i, w in enumerate(wins):
        s = set(occ0[w].keys()); real = sorted(s)
        if i >= ATK:
            if mode == "fab":   s = s | {9001, 9002, 9003}
            elif mode == "col": s = (s - set(real[:2])) | {8001, 8002}
            elif mode == "dep": s = s - set(real[:2])
        out.append(len(s))
    return np.array(out)

tb, tf, tc, td = traj("base"), traj("fab"), traj("col"), traj("dep")
bo = lambda a: (a == N_KNOWN).astype(int)
save = lambda fig, n: (fig.tight_layout(),
                       fig.savefig(os.path.join(OUT_DIR, n), dpi=150, bbox_inches="tight"),
                       print(f"  saved {n}"), plt.close(fig))

# ===== 圖 1:N_total 軌跡 =====
fig, ax = plt.subplots(figsize=(9, 4.6))
ax.axvspan(ATK, T-1, color="#f1f3f5", zorder=0)
ax.axhline(N_KNOWN, ls="--", color=C_BASE, lw=1.1, zorder=1)
ax.plot(tb, "-",  color=C_BASE, lw=1.8, label="baseline")
ax.plot(tf, "-",  color=C_FAB,  lw=1.8, label="fabrication (+3 fake)")
ax.plot(tc, "--", color=C_COL,  lw=2.0, label="collusion (+2 fake / −2 real)")
ax.plot(td, "-",  color=C_DEP,  lw=1.8, label="depletion (−2 real)")
ax.annotate("collusion holds N_total = N_known\n→ C_i cannot observe it",
            xy=(46, 7.12), xytext=(31, 8.7), fontsize=9, color=C_COL,
            arrowprops=dict(arrowstyle="->", color=C_COL, lw=1.0))
ax.annotate(f"arbitrary injection onset\n(experimental design, t={ATK})",
            xy=(ATK, 5.35), xytext=(ATK-26, 4.45), fontsize=8.5, color="#495057",
            arrowprops=dict(arrowstyle="->", color="#868e96", lw=0.9))
ax.set_xlabel("granularity window (1 s)"); ax.set_ylabel("N_total(t)")
ax.set_ylim(4.1, 11.3); ax.set_xlim(0, T-1)
ax.set_title("Field-wide cardinality under four attack scenarios (seed 4200)", fontsize=11)
ax.grid(alpha=0.3); ax.legend(fontsize=9, loc="upper left", ncol=2)
save(fig, "fig_Ci_1_trajectories.png")

# ===== 圖 2:C_i 布林判定 =====
fig, ax = plt.subplots(figsize=(9, 3.9))
ax.axvspan(ATK, T-1, color="#f1f3f5", zorder=0)
ax.step(range(T), bo(tb), where="mid", color=C_BASE, lw=1.8, label="baseline")
ax.step(range(T), bo(tf), where="mid", color=C_FAB,  lw=2.4, label="fabrication")
ax.step(range(T), bo(tc), where="mid", color=C_COL,  lw=1.6, ls=(0,(4,2)), label="collusion")
ax.step(range(T), bo(td), where="mid", color=C_DEP,  lw=1.6, ls=(0,(1,1.5)), label="depletion")
ax.annotate("collusion: conserved throughout\n→ E3 blind spot, motivates S_i / H_i",
            xy=(46, 1.0), xytext=(20, 0.42), fontsize=9, color=C_COL,
            arrowprops=dict(arrowstyle="->", color=C_COL, lw=1.0))
ax.set_yticks([0, 1]); ax.set_yticklabels(["0  (violated)", "1  (conserved)"], fontsize=9.5)
ax.set_ylim(-0.28, 1.32); ax.set_xlim(0, T-1)
ax.set_xlabel("granularity window (1 s)"); ax.set_ylabel("C_i(t)")
ax.set_title("C_i boolean assertion — conservation-preserving collusion is invisible", fontsize=11)
ax.grid(alpha=0.3); ax.legend(fontsize=8.5, loc="center left", ncol=2)
save(fig, "fig_Ci_2_boolean.png")

# ===== 圖 3:E6 持續窗脆弱性 =====
durs = [1, 2, 3, 5]; esc = []
for D in durs:
    e = 0
    for f in files:
        o = load(f); ws = sorted(o); t0 = len(ws)//2
        v = [(len(set(o[w].keys()) | ({9001} if t0 <= i < t0+D else set())) != N_KNOWN)
             for i, w in enumerate(ws)]
        run = 0; rej = False
        for x in v:
            run = run+1 if x else 0
            if run >= L_C: rej = True; break
        if not rej: e += 1
    esc.append(100*e/len(files))
fig, ax = plt.subplots(figsize=(7, 4.6))
ax.bar([str(d) for d in durs], esc,
       color=[C_FAB if d < L_C else C_BASE for d in durs], width=0.55)
for i, v in enumerate(esc):
    ax.text(i, v+3, f"{v:.0f}%", ha="center", fontsize=11,
            color=C_FAB if durs[i] < L_C else C_BASE, fontweight="bold")
ax.set_xlabel(f"attack injection duration D (windows),  policy L_C = {L_C}")
ax.set_ylabel("escape rate from hard veto (%)")
ax.set_title("E6: pulse attacks shorter than L_C evade rejection", fontsize=11)
ax.set_ylim(0, 118); ax.grid(alpha=0.3, axis="y")
save(fig, "fig_Ci_3_persistence.png")

# ===== 圖 4:E8 攻擊面 =====
per = collections.defaultdict(list)
for f in files:
    o = load(f)
    for w, im in o.items():
        cm = collections.defaultdict(set)
        for i, cs in im.items():
            for c in cs:
                if c != 1: cm[c].add(i)
        for c in range(2, 9): per[c].append(len(cm.get(c, set())))
cells = sorted(per); means = [np.mean(per[c]) for c in cells]
idle  = [100*np.mean(np.array(per[c]) == 0) for c in cells]
fig, ax = plt.subplots(figsize=(7.5, 4.6))
ax.bar([f"cell {c}" for c in cells], means, color=C_DEP, width=0.55)
for i, (m, idl) in enumerate(zip(means, idle)):
    ax.text(i, m+0.03, f"{m:.2f}", ha="center", fontsize=9.5)
    ax.text(i, -0.10, f"idle {idl:.0f}%", ha="center", fontsize=8, color="#868e96")
ax.set_xlabel("compromised O-DU  (idle % = windows with no attachable UE)")
ax.set_ylabel("erasable UEs per window (mean)")
ax.set_title("E8: single-O-DU depletion surface is structurally bounded", fontsize=11)
ax.set_ylim(-0.145, max(means)*1.30); ax.grid(alpha=0.3, axis="y")
save(fig, "fig_Ci_4_attack_surface.png")

print(f"\nE6 escape: {dict(zip(durs, esc))}")
print(f"E8 per-cell mean: {dict(zip(cells,[round(m,2) for m in means]))}")
