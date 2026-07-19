# -*- coding: utf-8 -*-
"""
test_cardinality.py — C_i 的視覺化與 sanity test。

跑法：
    python3 test_cardinality.py <DlE2RlcStats.txt> [out.png]

產出：
  * 終端印出 baseline / 灌水 / 虛減 三情境的 C_i 表
  * 一張三面板 PNG（N_total 時序、C_i 時序、C_i 響應曲線）
  * assert baseline 全部 trusted、灌水被 reject（自動 sanity check）
"""

import sys
import math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import cardinality as C


def run(path: str, out_png: str) -> None:
    result = C.load_rlc(path)
    # 適配 loader.py 返回 DataFrame 的情況
    try:
        import pandas as pd
        if isinstance(result, pd.DataFrame):
            records = result.to_dict('records')
        else:
            records = list(result)
    except ImportError:
        records = list(result)
    cfg = C.CardinalityConfig(n_known=35, eps_low=0.15, eps_high=0.0, kappa=0.10)
    n_lo, n_hi = cfg.bounds()

    windows = sorted(C.field_cardinality_series(records, cfg.include_lte).keys())
    late = windows[len(windows) // 2:]

    scenarios = {
        "baseline": records,
        "fabricate +3 (attack A)": C.inject_fabrication(records, 3, at_windows=late),
        "collude delete -8 (attack A)": C.inject_deletion(records, 8, at_windows=late, victim_cell=None),
    }
    results = {name: C.compute_cardinality_over_time(recs, cfg)
               for name, recs in scenarios.items()}

    # ---- sanity checks（自動化 test）----
    base = results["baseline"]
    assert all(r["grade"] == "trusted" for r in base.values()), "baseline 應全 trusted"
    assert all(abs(r["C"] - 1.0) < 1e-9 for r in base.values()), "baseline C_i 應為 1.0"
    fab = results["fabricate +3 (attack A)"]
    assert any(r["grade"] == "rejected" for r in fab.values()), "灌水應被 reject"
    print("[test] sanity checks PASSED [OK]")

    colors = {"baseline": "#2e7d32",
              "fabricate +3 (attack A)": "#c62828",
              "collude delete -8 (attack A)": "#e65100"}

    fig, ax = plt.subplots(1, 3, figsize=(16, 4.6))

    # ---- Panel 1: N_total(t) ----
    a = ax[0]
    a.axhspan(n_lo, n_hi, color="#a5d6a7", alpha=0.35, label=f"known-population band [{n_lo:.0f},{n_hi:.0f}]")
    a.axhline(cfg.n_known, color="#1b5e20", ls="--", lw=1, label=f"N_known={cfg.n_known} (ues.txt)")
    for name, res in results.items():
        ts = list(res.keys())
        ys = [res[t]["N_total"] for t in ts]
        a.plot(ts, ys, "o-", color=colors[name], label=name, lw=2, ms=6)
    a.set_title("(a) Field-wide UE cardinality  N_total(t)")
    a.set_xlabel("granularity period start (s)")
    a.set_ylabel("distinct IMSI across all cells")
    a.legend(fontsize=7, loc="center left")
    a.grid(alpha=0.3)

    # ---- Panel 2: C_i(t) ----
    a = ax[1]
    a.axhspan(0.90, 1.0, color="#c8e6c9", alpha=0.5)
    a.axhspan(0.50, 0.90, color="#fff9c4", alpha=0.6)
    a.axhspan(0.0, 0.50, color="#ffcdd2", alpha=0.5)
    a.axhline(0.90, color="#666", ls=":", lw=1)
    a.axhline(0.50, color="#666", ls=":", lw=1)
    a.text(windows[0], 0.95, "trusted (θ_high)", fontsize=7, va="center")
    a.text(windows[0], 0.70, "low-trust", fontsize=7, va="center")
    a.text(windows[0], 0.25, "rejected (θ_low)", fontsize=7, va="center")
    for name, res in results.items():
        ts = list(res.keys())
        ys = [res[t]["C"] for t in ts]
        a.plot(ts, ys, "o-", color=colors[name], label=name, lw=2, ms=6)
    a.set_ylim(-0.03, 1.05)
    a.set_title("(b) Cardinality residual  C_i(t)")
    a.set_xlabel("granularity period start (s)")
    a.set_ylabel("C_i  (1 = perfect conservation)")
    a.legend(fontsize=7, loc="lower left")
    a.grid(alpha=0.3)

    # ---- Panel 3: response curve C_i vs N_total ----
    a = ax[2]
    xs = np.arange(20, 51)
    ys = [C.cardinality_residual(int(x), cfg) for x in xs]
    a.plot(xs, ys, "-", color="#1565c0", lw=2)
    a.axvspan(n_lo, n_hi, color="#a5d6a7", alpha=0.35, label="deadband (C_i=1)")
    a.axvline(cfg.n_known, color="#1b5e20", ls="--", lw=1)
    a.axhline(0.90, color="#666", ls=":", lw=1)
    a.axhline(0.50, color="#666", ls=":", lw=1)
    a.annotate("fabrication\n(N>N_hi): no tolerance",
               xy=(40, C.cardinality_residual(40, cfg)), xytext=(41, 0.55),
               fontsize=7, color="#c62828",
               arrowprops=dict(arrowstyle="->", color="#c62828"))
    a.annotate("depletion\n(N<N_lo): ε tolerant",
               xy=(26, C.cardinality_residual(26, cfg)), xytext=(20.5, 0.35),
               fontsize=7, color="#e65100",
               arrowprops=dict(arrowstyle="->", color="#e65100"))
    a.set_title(f"(c) Response curve  (eps_low={cfg.eps_low}, eps_high={cfg.eps_high}, kappa={cfg.kappa})")
    a.set_xlabel("N_total")
    a.set_ylabel("C_i")
    a.set_ylim(-0.03, 1.05)
    a.legend(fontsize=7, loc="lower center")
    a.grid(alpha=0.3)

    fig.suptitle("C_i — Field-wide UE Cardinality Conservation Residual (NPN O-RAN E2 KPM ZTA)",
                 fontsize=12, y=1.02)
    fig.tight_layout()
    fig.savefig(out_png, dpi=140, bbox_inches="tight")
    print(f"[viz] saved -> {out_png}")


if __name__ == "__main__":
    import os
    path = sys.argv[1] if len(sys.argv) > 1 else "data/sim_60s_baseline/DlE2RlcStats.txt"
    out_png = sys.argv[2] if len(sys.argv) > 2 else "cardinality_Ci.png"
    # 支持相對路徑和絕對路徑
    if not os.path.isabs(path) and not os.path.exists(path):
        # 如果相對路徑不存在，試著從 project root 找
        proj_root = os.path.join(os.path.dirname(__file__), "../../..")
        alt_path = os.path.join(proj_root, path)
        if os.path.exists(alt_path):
            path = alt_path
    run(path, out_png)
