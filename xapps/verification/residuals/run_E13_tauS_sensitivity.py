#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_E13_tauS_sensitivity.py — E13：S_i 門檻 τ_S 之敏感度與誤報非穩態（第四章 4.7.x；回應 4.7.6 門檻選擇洩漏）

【要回答的問題】
  τ_S = 4 由全體 seed 掃描選定（門檻選擇層級之洩漏，4.7.6 已揭露）。本實驗報告：
  1. 殘差層：τ_S ∈ {3, 3.5, 4, 4.5, 5} 下之乾淨 FPR、漂移／階躍偵測率（seed 層級範圍）。
     結論不應只在 τ_S = 4 成立——若空間 vs 時間之差距於整個區間皆存在，洩漏不影響主張。
  2. 誤報非穩態：逐 seed 之乾淨 FPR 分前半／後半（序列位置），檢驗是否需要 startup 排除窗。
     另以「窗層級合併、序列位置十等分」重現 4.7.7 之表（FPR、平均 z_j、平均 peer 數）。
     注意口徑：4.7.7 之前半／後半（0.111／0.025）為十等分 FPR 之未加權平均（窗合併），
     4.7.4／E9 之乾淨 FPR 0.037 為 seed×cell 樣本之等權平均且僅含後半段——二者不同口徑。
  3. 融合層：定案政策（uebound, L_H = 1）於不同 τ_S 下之乾淨決策分布與觸發規則。

【設計】
  殘差層完全沿用 run_E9_operating_regime.py（LOSO 尺度、full-consensus、t0 = len//2）。
  融合層沿用 run_E10_D1_policy_ablation.run_policy（P3_uebound_L1），僅改 zt_kpm_xapp.TAU_S。

【內建一致性檢查】
  1. τ_S = 4 之殘差層結果須與 E9_operating_regime.json 逐位相同。
  2. τ_S = 4 之融合層須重現 4.9.6.5 之 P3：trusted 1,803／low-trust 575／abstain 766／
     rejected 6（分母 3,150）。
  3. τ_S = 4 之十等分表須與 4.7.7 已發表之數字（三位／兩位小數）相同。
  任一失敗即停止、不寫檔。

【輸出】
  <out>/E13_tauS_sensitivity.json
  <out>/fig_E13_tauS_sensitivity.png
"""
import os
import sys
import json
import argparse
import collections
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_E9_operating_regime as E9
from run_E9_operating_regime import load_cell_delay, global_scale, inject_drift, inject_step
from run_slow_poisoning_suite import find_files, build_samples, zfun, agg_seed, REFS
import run_E10_D1_policy_ablation as E10
X = E10.X

TAUS = [3.0, 3.5, 4.0, 4.5, 5.0]
# 4.7.7 已發表之十等分表：(FPR, 平均 z_j, 平均 peer 數)
PUBLISHED_477 = [(0.121, 1.88, 2.59), (0.114, 1.54, 2.50), (0.131, 1.58, 2.52),
                 (0.110, 1.43, 2.51), (0.079, 1.31, 2.43), (0.033, 1.10, 2.50),
                 (0.014, 1.08, 2.55), (0.028, 1.07, 2.38), (0.047, 1.13, 2.37),
                 (0.005, 0.82, 2.48)]
PUBLISHED_477_HALVES = (0.111, 0.025)
EXPECTED_P3 = {"trusted": 1803, "low-trust": 575, "abstain": 766, "rejected": 6}


def residual_level(data, seeds):
    fpr = {t: {r: [] for r in REFS} for t in TAUS}
    half = {t: {r: {"first": [], "second": []} for r in REFS} for t in TAUS}
    drift = {t: {r: collections.defaultdict(list) for r in REFS} for t in TAUS}
    step = {t: {r: collections.defaultdict(list) for r in REFS} for t in TAUS}
    for ts in seeds:
        s = global_scale([data[x] for x in seeds if x != ts])
        for tc, idx, ser, pm in build_samples(data[ts]):
            mean = ser.mean(); t0 = len(ser) // 2
            for r in REFS:
                zc = zfun(r, ser, pm, s)
                zd = {rate: zfun(r, inject_drift(ser, t0, rate, mean), pm, s)
                      for rate in E9.DRIFT_RATES}
                zs = {af: zfun(r, inject_step(ser, t0, af), pm, s) for af in E9.STEP_AFS}
                for t in TAUS:
                    fpr[t][r].append((ts, float((zc[t0:] > t).mean())))
                    half[t][r]["first"].append((ts, float((zc[:t0] > t).mean())))
                    half[t][r]["second"].append((ts, float((zc[t0:] > t).mean())))
                    for rate, z in zd.items():
                        drift[t][r][rate].append((ts, float((z[t0:] > t).mean())))
                    for af, z in zs.items():
                        step[t][r][af].append((ts, float((z[t0:] > t).mean())))
    out = {}
    for t in TAUS:
        out[str(t)] = {r: {"clean_fpr": agg_seed(fpr[t][r]),
                           "clean_fpr_first_half": agg_seed(half[t][r]["first"]),
                           "clean_fpr_second_half": agg_seed(half[t][r]["second"]),
                           "drift": {str(k): agg_seed(v) for k, v in drift[t][r].items()},
                           "step": {str(k): agg_seed(v) for k, v in step[t][r].items()}}
                       for r in REFS}
    return out


def decile_table(data, seeds, tau=4.0):
    """空間參照之乾淨 z 依序列位置十等分（窗層級合併）；peer 數 = 同窗活躍 mmWave cell − 1"""
    F = [[] for _ in range(10)]; Z = [[] for _ in range(10)]; P = [[] for _ in range(10)]
    pooled_half = [[], []]
    per_seed_half = {sd: [[], []] for sd in seeds}
    for ts in seeds:
        s = global_scale([data[x] for x in seeds if x != ts])
        Wd = data[ts]
        for tc, idx, ser, pm in build_samples(Wd):
            z = zfun("spatial", ser, pm, s); n = len(z)
            for i in range(n):
                d = int(10 * i / n)
                F[d].append(z[i] > tau); Z[d].append(z[i]); P[d].append(len(Wd[idx[i]]) - 1)
                h = 0 if i < n // 2 else 1
                pooled_half[h].append(z[i] > tau)
                per_seed_half[ts][h].append(z[i] > tau)
    rows = [{"decile": d, "fpr": float(np.mean(F[d])), "mean_z": float(np.mean(Z[d])),
             "mean_peer": float(np.mean(P[d])), "n": len(F[d])} for d in range(10)]
    return {"rows": rows,
            "halves_decile_mean": [float(np.mean([r["fpr"] for r in rows[:5]])),
                                   float(np.mean([r["fpr"] for r in rows[5:]]))],
            "halves_pooled": [float(np.mean(pooled_half[0])), float(np.mean(pooled_half[1]))],
            "per_seed_halves_pooled": {sd: [float(np.mean(v[0])) if v[0] else None,
                                            float(np.mean(v[1])) if v[1] else None]
                                       for sd, v in per_seed_half.items()}}


def fusion_level(files):
    out = {}
    orig = X.TAU_S
    try:
        for t in TAUS:
            X.TAU_S = t
            dec, rule = collections.Counter(), collections.Counter()
            per_seed = {}
            for test in files:
                anchor = X.TrustAnchor([f for f in files if f != test])
                ann, _ = E10.run_policy(E10.load_windows(test), anchor, "uebound", 1)
                c = collections.Counter(a["decision"] for a in ann)
                dec.update(c)
                rule.update(a["rule_id"] for a in ann)
                sd = os.path.basename(test).split("seed")[-1].replace(".txt", "")
                n = sum(c.values())
                per_seed[sd] = {k: c.get(k, 0) / n for k in ("trusted", "low-trust", "abstain", "rejected")}
            n = sum(dec.values())
            out[str(t)] = {"n": n, "counts": dict(dec),
                           "frac": {k: dec.get(k, 0) / n for k in ("trusted", "low-trust", "abstain", "rejected")},
                           "rules": dict(rule), "per_seed": per_seed}
    finally:
        X.TAU_S = orig
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=None)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--no-fig", action="store_true")
    args = ap.parse_args()
    out_dir = args.out_dir or E9.OUT_DIR
    os.makedirs(out_dir, exist_ok=True)
    files = find_files(args.data_dir)
    if len(files) < 2:
        print("資料不足，用 --data-dir 指定。"); return
    seeds = [os.path.basename(f).split("seed")[-1].replace(".txt", "") for f in files]
    data = {s: load_cell_delay(f) for s, f in zip(seeds, files)}
    print(f"載入 {len(seeds)} seed: {seeds}\n")

    res_r = residual_level(data, seeds)

    # ---- 一致性檢查 1 ----
    e9 = json.load(open(os.path.join(out_dir, "E9_operating_regime.json"), encoding="utf-8"))
    bad = []
    for r in REFS:
        got = res_r["4.0"][r]
        if abs(got["clean_fpr"]["mean"] - e9["clean_fpr"][r]["mean"]) > 1e-12:
            bad.append(("fpr", r))
        for k in got["drift"]:
            if abs(got["drift"][k]["mean"] - e9["drift"][r][k]["mean"]) > 1e-12:
                bad.append(("drift", r, k))
        for k in got["step"]:
            if abs(got["step"][k]["mean"] - e9["step"][r][k]["mean"]) > 1e-12:
                bad.append(("step", r, k))
    print("── 一致性檢查 1（τ_S = 4 vs E9_operating_regime.json）──")
    if bad:
        print("  ✗", bad); raise SystemExit("不一致，停止，不寫檔。")
    print("  ✓ 乾淨 FPR、漂移、階躍逐位相同\n")

    dec = decile_table(data, seeds)
    # ---- 一致性檢查 3 ----
    bad = []
    for r, (f, z, p) in zip(dec["rows"], PUBLISHED_477):
        if (round(r["fpr"], 3), round(r["mean_z"], 2), round(r["mean_peer"], 2)) != (f, z, p):
            bad.append((r["decile"], (f, z, p), (round(r["fpr"], 3), round(r["mean_z"], 2),
                                                 round(r["mean_peer"], 2))))
    if tuple(round(x, 3) for x in dec["halves_decile_mean"]) != PUBLISHED_477_HALVES:
        bad.append(("halves", PUBLISHED_477_HALVES, dec["halves_decile_mean"]))
    print("── 一致性檢查 3（十等分表 vs 4.7.7）──")
    if bad:
        print("  ✗", bad); raise SystemExit("不一致，停止，不寫檔。")
    print(f"  ✓ 十列逐位相同；前半／後半（十等分平均）{dec['halves_decile_mean'][0]:.3f}／"
          f"{dec['halves_decile_mean'][1]:.3f}，窗合併 {dec['halves_pooled'][0]:.3f}／"
          f"{dec['halves_pooled'][1]:.3f}\n")

    res_f = fusion_level(files)
    # ---- 一致性檢查 2 ----
    got = {k: res_f["4.0"]["counts"].get(k, 0) for k in EXPECTED_P3}
    print("── 一致性檢查 2（τ_S = 4 融合層 vs 4.9.6.5 P3）──")
    if got != EXPECTED_P3 or res_f["4.0"]["n"] != 3150:
        print(f"  ✗ 期望 {EXPECTED_P3}（n=3150）／本次 {got}（n={res_f['4.0']['n']}）")
        raise SystemExit("不一致，停止，不寫檔。")
    print("  ✓ 1,803／575／766／6（n = 3,150）\n")

    res = {"taus": TAUS, "residual": res_r, "fusion_uebound_L1": res_f,
           "decile_spatial_tau4": dec,
           "consistency": {"E9_reproduced_at_4": "ok", "P3_reproduced_at_4": "ok",
                           "decile_477_reproduced": "ok"}}
    path = os.path.join(out_dir, "E13_tauS_sensitivity.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, ensure_ascii=False)

    print("══ 殘差層：乾淨 FPR（前半／後半）與漂移偵測率（空間 | 時間）══")
    print(f"{'τ_S':>4} | {'FPR':>6} {'前半':>6} {'後半':>6} {'0.5%':>5} {'1%':>5} {'2%':>5} | "
          f"{'FPR':>6} {'0.5%':>5} {'1%':>5} {'2%':>5} | 差距@1%")
    for t in TAUS:
        a = res_r[str(t)]["spatial"]; b = res_r[str(t)]["temporal"]
        print(f"{t:>4} | {a['clean_fpr']['mean']:>6.3f} {a['clean_fpr_first_half']['mean']:>6.3f} "
              f"{a['clean_fpr_second_half']['mean']:>6.3f} "
              + " ".join(f"{a['drift'][k]['mean']:>5.2f}" for k in ("0.005", "0.01", "0.02"))
              + f" | {b['clean_fpr']['mean']:>6.3f} "
              + " ".join(f"{b['drift'][k]['mean']:>5.2f}" for k in ("0.005", "0.01", "0.02"))
              + f" | {a['drift']['0.01']['mean'] - b['drift']['0.01']['mean']:+.2f}")
    print("\n══ 逐 seed 空間乾淨 FPR（前半 → 後半），τ_S = 4 ══")
    a = res_r["4.0"]["spatial"]
    for sd in seeds:
        print(f"  {sd}: {a['clean_fpr_first_half']['per_seed'][sd]:.3f} → "
              f"{a['clean_fpr_second_half']['per_seed'][sd]:.3f}")
    print("\n══ 融合層（uebound, L_H = 1）══")
    print(f"{'τ_S':>4} | {'trusted':>8} {'low-trust':>9} {'abstain':>8} {'rejected':>8} | R2_SI_ALONE R2_SI_D1_BOUND")
    for t in TAUS:
        f = res_f[str(t)]
        print(f"{t:>4} | {f['frac']['trusted']*100:>7.1f}% {f['frac']['low-trust']*100:>8.1f}% "
              f"{f['frac']['abstain']*100:>7.1f}% {f['frac']['rejected']*100:>7.2f}% | "
              f"{f['rules'].get('R2_SI_ALONE', 0):>11} {f['rules'].get('R2_SI_D1_BOUND', 0):>14}")
    print(f"\n寫入 {path}")
    if not args.no_fig:
        draw(res, out_dir)


def draw(res, out_dir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    C = {"spatial": "#2b8a3e", "temporal": "#c92a2a"}
    rates = E9.DRIFT_RATES; x = [r * 100 for r in rates]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    cmap = plt.get_cmap("viridis")
    for i, t in enumerate(TAUS):
        for r in REFS:
            d = res["residual"][str(t)][r]["drift"]
            axes[0].plot(x, [d[str(k)]["mean"] for k in rates], color=C[r],
                         alpha=0.35 + 0.13 * i, lw=2.2 if t == 4.0 else 1.0,
                         ls="-" if r == "spatial" else "--",
                         label=f"{r} τ={t:g}" if t in (3.0, 4.0, 5.0) else None)
    axes[0].set_xscale("log"); axes[0].set_xlabel("drift rate (%/window, log)")
    axes[0].set_ylabel("detection rate"); axes[0].grid(alpha=0.3); axes[0].legend(fontsize=7, ncol=2)
    for r in REFS:
        axes[1].plot(TAUS, [res["residual"][str(t)][r]["clean_fpr"]["mean"] for t in TAUS],
                     marker="o", color=C[r], label=f"{r} clean FPR")
    axes[1].plot(TAUS, [res["fusion_uebound_L1"][str(t)]["frac"]["trusted"] for t in TAUS],
                 marker="s", color="#1971c2", label="fusion: trusted fraction")
    axes[1].set_xlabel("τ_S"); axes[1].grid(alpha=0.3); axes[1].legend(fontsize=8)
    fig.suptitle("E13 τ_S sensitivity (bold = operating point τ_S = 4)", fontsize=11)
    fig.tight_layout(); fig.savefig(os.path.join(out_dir, "fig_E13_tauS_sensitivity.png"), dpi=200)
    print(f"圖已存: {out_dir}/fig_E13_tauS_sensitivity.png")


if __name__ == "__main__":
    main()
