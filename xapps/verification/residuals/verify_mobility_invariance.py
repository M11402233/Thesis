"""
verify_mobility_invariance.py — 證明場域基數守恆與 UE 移動速度無關

目的（回應論文 4.5 穩健性檢驗 Q3）
----------------------------------
C_i 的 σ=0 是「封閉場域物理必然」還是「特定速度的巧合」？
若對每一檔移動速度，N_total 都退化於 N_known（Var=0），即證明守恆為速度不變
（speed-invariant）的物理性質，而非參數僥倖。這比任何 goodness-of-fit 都直接。

注意：這不是統計分布擬合，是「不變量在不同速度下是否皆成立」的實證檢驗。

跑法：
    cd ~/oran-zt-kpm-verification
    python3 xapps/verification/residuals/verify_mobility_invariance.py

輸入：data/mobility_seeds/speed{MIN}_{MAX}_seed{SEED}.txt（collect_mobility_sweep.sh 產出）
輸出：終端表格 + data/results/mobility_invariance.json + 一張對照圖
"""

import os
import re
import sys
import json
import glob
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cardinality as C

BASE = os.path.expanduser("~/oran-zt-kpm-verification")
DATA_DIR = os.path.join(BASE, "data/mobility_seeds")
OUT_DIR = os.path.join(BASE, "data/results")

# 容器 fallback
if not os.path.isdir(DATA_DIR):
    here = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.path.join(here, "mobility_seeds")
    OUT_DIR = here

os.makedirs(OUT_DIR, exist_ok=True)
N_KNOWN = 7
_PAT = re.compile(r"speed(\d+)_(\d+)_seed(\d+)\.txt$")


def load_by_speed():
    """回傳 {speed_label: {seed: records}}。"""
    files = sorted(glob.glob(os.path.join(DATA_DIR, "speed*_seed*.txt")))
    if not files:
        sys.exit(f"找不到資料：{DATA_DIR}/speed*_seed*.txt\n"
                 f"請先跑 collect_mobility_sweep.sh")
    by_speed = defaultdict(dict)
    for f in files:
        m = _PAT.search(os.path.basename(f))
        if not m:
            continue
        smin, smax, seed = m.group(1), m.group(2), m.group(3)
        label = f"{smin}-{smax} m/s"
        by_speed[label][seed] = list(C.load_rlc(f))
    return dict(by_speed)


def main():
    by_speed = load_by_speed()
    cfg = C.CardinalityConfig(n_known=N_KNOWN, eps_low=0.05, eps_high=0.0, kappa=0.10)

    print("=" * 68)
    print("移動性不變性檢驗：場域基數守恆是否與速度無關")
    print("=" * 68)
    print(f"{'速度檔':>12} | {'seed數':>5} | {'總窗數':>6} | {'N_total support':>18} | "
          f"{'std':>6} | {'退化?':>5}")
    print("-" * 72)

    summary = {}
    all_speed_degenerate = True
    for label in sorted(by_speed.keys()):
        seed_recs = by_speed[label]
        rob = C.verify_invariant_robustness(seed_recs, cfg)
        support_str = "{" + ",".join(map(str, rob["pooled_support"])) + "}"
        degen = "✓" if (rob["is_degenerate"] and rob["matches_n_known"]) else "✗"
        if not (rob["is_degenerate"] and rob["matches_n_known"]):
            all_speed_degenerate = False
        print(f"{label:>12} | {len(seed_recs):>5} | {rob['total_windows']:>6} | "
              f"{support_str:>18} | {rob['pooled_std']:>6.3f} | {degen:>5}")
        summary[label] = {
            "n_seeds": len(seed_recs),
            "total_windows": rob["total_windows"],
            "pooled_support": rob["pooled_support"],
            "pooled_std": rob["pooled_std"],
            "is_degenerate_at_n_known": bool(rob["is_degenerate"] and rob["matches_n_known"]),
        }

    print("-" * 72)
    if all_speed_degenerate:
        print(f"\n結論：三檔速度下 N_total 皆退化於 N_known={N_KNOWN}（Var=0）")
        print("→ 場域基數守恆為【速度不變的物理性質】，σ=0 非特定速度巧合。")
        print("→ 直接反駁『σ=0 是模擬假象 / 資料量不足』的質疑。")
    else:
        print("\n⚠️ 有速度檔非退化 → 存在移動性引起的瞬態，需檢視並據此設 ε_low。")

    verdict = ("speed-invariant conservation confirmed" if all_speed_degenerate
               else "non-degenerate at some speed; inspect transients")
    out = {"config": cfg.to_dict(), "n_known": N_KNOWN,
           "per_speed": summary, "all_speed_degenerate": all_speed_degenerate,
           "verdict": verdict}
    jpath = os.path.join(OUT_DIR, "mobility_invariance.json")
    with open(jpath, "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\n結果已存：{jpath}")

    # ---- 圖：三檔速度的 N_total(t) 疊圖（應三條全平在 N_known）----
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(8.4, 4.4))
        colors = ["#1565c0", "#2e7d32", "#e65100", "#6a1b9a"]
        for i, label in enumerate(sorted(by_speed.keys())):
            first_seed = sorted(by_speed[label].keys())[0]
            recs = by_speed[label][first_seed]
            series = C.field_cardinality_series(recs, cfg.include_lte, cfg.lte_cell_id)
            ts = sorted(series.keys())
            ys = [series[t] for t in ts]
            ax.plot(ts, ys, "-", color=colors[i % len(colors)], lw=2,
                    marker="o", ms=3, label=f"{label} (seed {first_seed})")
        ax.axhline(N_KNOWN, color="#000", ls="--", lw=1,
                   label=f"N_known={N_KNOWN}")
        ax.set_ylim(N_KNOWN - 3, N_KNOWN + 3)
        ax.set_xlabel("granularity period start (s)")
        ax.set_ylabel("N_total(t)")
        ax.set_title("Cardinality conservation is speed-invariant "
                     "(all speeds flat at N_known)")
        ax.legend(fontsize=8, loc="upper right")
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig_path = os.path.join(OUT_DIR, "fig4_mobility_invariance.png")
        fig.savefig(fig_path, dpi=160, bbox_inches="tight")
        print(f"圖已存：{fig_path}")
    except Exception as e:
        print(f"（繪圖略過：{e}）")


if __name__ == "__main__":
    main()
