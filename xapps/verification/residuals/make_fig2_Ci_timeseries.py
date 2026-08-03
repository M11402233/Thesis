#!/usr/bin/env python3
"""fig2_Ci_timeseries (布林版) — 用真實 seed4200 資料,視覺化 E3 守恆式串謀盲點。
對齊 4.6.1 布林斷言:C_i(t) 只有 {0,1},無 trusted/low-trust/rejected 分級帶、無 0.9/0.5 門檻。"""
import os, collections
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT_DIR = os.path.expanduser("~/oran-zt-kpm-verification/data/results")
os.makedirs(OUT_DIR, exist_ok=True)
SRC = os.path.expanduser("~/oran-zt-kpm-verification/data/si_lstm_seeds/ues1_t300_seed4200.txt"); N_KNOWN = 7; ATK_START = 30

# 每窗全域 IMSI 聯集(含 LTE 錨點 cell 1)
win_imsi = collections.defaultdict(set)
with open(SRC) as f:
    next(f)
    for line in f:
        p = line.split("\t")
        if len(p) < 4: continue
        try: w = int(float(p[0])); imsi = int(p[3])
        except: continue
        win_imsi[w].add(imsi)
wins = sorted(win_imsi)[:60]
base_N = np.array([len(win_imsi[w]) for w in wins])   # 應恆為 7

t = np.arange(len(wins))
baseline   = base_N.copy()
fabricate  = base_N.copy(); fabricate[t >= ATK_START] += 3            # +3 假IMSI
collusion  = base_N.copy()                                            # +2假 −2真 → 不變

def ci_bool(N): return (N == N_KNOWN).astype(int)

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 6.2), sharex=True,
                               gridspec_kw={"height_ratios": [1.15, 1]})

# ---- 上:N_total(t) ----
ax1.axhline(N_KNOWN, ls="--", color="#2b8a3e", lw=1.2, label="N_known = 7 (closed NPN)")
ax1.axvspan(ATK_START, len(wins)-1, color="#f1f3f5", zorder=0)
ax1.plot(t, baseline,  "-o", color="#2b8a3e", ms=3, lw=1.6, label="baseline")
ax1.plot(t, fabricate, "-o", color="#c92a2a", ms=3, lw=1.6, label="fabrication +3")
ax1.plot(t, collusion, "-o", color="#e8590c", ms=3, lw=1.6, label="collusion (+2 fake, −2 real)")
ax1.annotate("collusion keeps N_total = N_known\n→ invisible to C_i (blind spot)",
             xy=(45, 7.05), xytext=(20, 8.6), fontsize=9, color="#e8590c",
             arrowprops=dict(arrowstyle="->", color="#e8590c", lw=1.0))
ax1.set_ylabel("N_total(t)"); ax1.set_ylim(6.4, 10.6)
ax1.legend(loc="upper left", fontsize=8.5, framealpha=0.95); ax1.grid(alpha=0.3)
ax1.set_title("Field-wide cardinality & C_i under attack (seed4200, boolean assertion)")

# ---- 下:C_i(t) 布林 ----
ax2.step(t, ci_bool(baseline),  where="mid", color="#2b8a3e", lw=1.6, label="baseline")
ax2.step(t, ci_bool(fabricate), where="mid", color="#c92a2a", lw=2.0, label="fabrication +3")
ax2.step(t, ci_bool(collusion), where="mid", color="#e8590c", lw=1.4, ls=(0,(4,2)), label="collusion")
ax2.axvspan(ATK_START, len(wins)-1, color="#f1f3f5", zorder=0)
ax2.annotate("collusion: conserved throughout\n→ C_i blind, motivates S_i / H_i",
             xy=(45, 1.0), xytext=(20, 0.55), fontsize=9, color="#e8590c",
             arrowprops=dict(arrowstyle="->", color="#e8590c", lw=1.0))
ax2.set_xlabel("granularity window (s)"); ax2.set_ylabel("C_i(t)")
ax2.set_yticks([0, 1]); ax2.set_yticklabels(["0 (violated)", "1 (conserved)"])
ax2.set_ylim(-0.2, 1.3); ax2.legend(loc="center left", fontsize=8.5, framealpha=0.95)
ax2.grid(alpha=0.3)

fig.tight_layout()
out = os.path.join(OUT_DIR, "fig2_Ci_timeseries.png")
fig.savefig(out, dpi=150); print("saved", out)
print(f"baseline N_total 範圍: {base_N.min()}~{base_N.max()} (應恆=7)")
