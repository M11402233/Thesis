#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_slow_poisoning_rt.py — 方案 B：慢性中毒題組 Q1／Q2／Q4／Q6（以實際秒數為時間單位）

規格：docs/thesis/planB_realtime_spec.md。舊版 slow_poisoning_suite.json 保留不動。

  Q1 偵測前沿：r*_D = P(注入後 D 秒內以「實際連續兩秒」準則偵測) ≥ 0.5 且高於乾淨底線之最低速率
  Q2 偵測前之偏差：首次偵測（2c）時之偏移；未偵測者以比較集合中最後一窗之偏移設限
  Q4 貼門檻攻擊：上報 = 參照值 + β·τ_S·s
       空間 oracle：同窗 peer 中位數（上界）；lag1：最近一個已評估窗之 peer 中位數；
       own：自身真值 + β·τ_S·s（所有上報窗）
       時間 oracle／lag1（等價）：依實際時間逐秒，參照 = 前 10 秒已上報之偽造值之中位數；
       前 10 秒上報 < 5 時，上報 = 自身真值 + β·τ_S·s
  Q6 校準期中毒：訓練 seed 中出現窗數最多之 k 個 cell 自 t = 0 起竄改
       漸進：× (1 + mag · w)（w 為實際秒）；固定：× (1 + mag)
比較集合：own（各方法自身可評估集合）與 common（共同集合；主結果）。

【內建檢查】
  1. Q4 oracle、β < 1：兩種參照於其可評估窗之偵測率依構造須為 0。
  2. Q6 未中毒之空間乾淨誤報（own）須等於 E9_rt 之值。
  3. 回歸基準 slow_rt（人工核對後建立）。
"""
import os
import sys
import json
import argparse
import collections
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import planB_rt as P
import run_E9_operating_regime as E9
from run_E9_operating_regime import global_scale

Q1_RATES = [0.001, 0.002, 0.003, 0.005, 0.0075, 0.01, 0.015, 0.02, 0.03, 0.04, 0.06, 0.08, 0.15]
HORIZONS = [5, 10, 20, 40]
BETAS = [0.5, 0.75, 0.9, 0.99]
VARIANTS = ("oracle", "lag1", "own")
Q6_K = [1, 2, 3]
Q6_POISON = [("drift", 0.005), ("drift", 0.01), ("drift", 0.02), ("bias", 0.5), ("bias", 1.0), ("bias", 2.0)]
Q6_RATES = [0.005, 0.01, 0.02, 0.04]
REFS = ("spatial", "temporal")
SETS = ("own", "common")


def zfun(sm, r, v, s):
    return P.z_spatial(sm, v, s) if r == "spatial" else P.z_temporal(sm, v, s)


def sets_of(sm):
    return {"own": {r: P.own_set(sm, r) for r in REFS}, "common": {r: P.common_set(sm) for r in REFS}}


# ---------------- Q4 ----------------
def hug_spatial(sm, beta, s, variant):
    v = dict(sm.own)
    last_pm = None
    for w in sorted(sm.own):
        if w < sm.w_on:
            if w in sm.pm:
                last_pm = sm.pm[w]
            continue
        if variant == "own":
            v[w] = sm.own[w] + beta * P.TAU_S * s
        elif variant == "oracle" and w in sm.pm:
            v[w] = sm.pm[w] + beta * P.TAU_S * s
        elif variant == "lag1" and last_pm is not None:
            v[w] = last_pm + beta * P.TAU_S * s
        else:
            v[w] = sm.own[w] + beta * P.TAU_S * s
        if w in sm.pm:
            last_pm = sm.pm[w]          # 本窗之 peer 中位數於下一窗起才可得
    return v


def hug_temporal(sm, beta, s, variant):
    v = dict(sm.own)
    for w in sorted(sm.own):
        if w < sm.w_on:
            continue
        if variant == "own":
            v[w] = sm.own[w] + beta * P.TAU_S * s
            continue
        hist = [v[u] for u in range(w - P.HIST_WIN, w) if u in v]
        v[w] = (float(np.median(hist)) if len(hist) >= P.MIN_OBS else sm.own[w]) + beta * P.TAU_S * s
    return v


# ---------------- Q6 ----------------
def poison_training(Wd, k, kind, mag):
    cnt = collections.Counter(c for w in Wd for c in Wd[w])
    targets = [c for c, _ in sorted(cnt.items(), key=lambda x: (-x[1], x[0]))[:k]]
    out = {}
    for w in sorted(Wd):
        row = dict(Wd[w])
        for c in targets:
            if c in row:
                row[c] = row[c] * (1 + mag * w) if kind == "drift" else row[c] * (1 + mag)
        out[w] = row
    return out, targets


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=E9.OUT_DIR)
    ap.add_argument("--set-baseline", action="store_true")
    ap.add_argument("--no-fig", action="store_true")
    args = ap.parse_args()
    seeds, data = P.load_data()
    acc = collections.defaultdict(list)
    q2rows = collections.defaultdict(list)
    q4 = collections.defaultdict(list)

    for ts in seeds:
        s = P.fold_scale(data, seeds, ts)
        for sm in P.samples_of(ts, data[ts]):
            SS = sets_of(sm)
            for r in REFS:
                f0 = P.flags_from_z(zfun(sm, r, sm.own, s))
                for st in SETS:
                    S = SS[st][r]
                    k0 = P.first_detection(f0, S, sm.w_on, "2c")
                    for D in HORIZONS:
                        acc[("floor", st, r, D)].append((ts, float(k0 is not None and k0 - sm.w_on < D)))
                for rate in Q1_RATES:
                    f = P.flags_from_z(zfun(sm, r, P.inject_drift(sm.own, sm.w_on, rate, sm.mean), s))
                    for st in SETS:
                        S = SS[st][r]
                        k = P.first_detection(f, S, sm.w_on, "2c")
                        for D in HORIZONS:
                            acc[("q1", st, r, D, rate)].append((ts, float(k is not None and k - sm.w_on < D)))
                        if not S:
                            continue
                        sec = (k - sm.w_on) if k is not None else (max(S) - sm.w_on)
                        q2rows[(st, r, rate)].append({"seed": ts, "detected": k is not None, "seconds": sec,
                                                      "offset_pct": rate * sec * 100,
                                                      "cum_mean_s": rate * sec * (sec + 1) / 2})
            # Q4
            for beta in BETAS:
                for vr in VARIANTS:
                    for r in REFS:
                        v = hug_spatial(sm, beta, s, vr) if r == "spatial" else hug_temporal(sm, beta, s, vr)
                        f = P.flags_from_z(zfun(sm, r, v, s))
                        for st in SETS:
                            S = [w for w in SS[st][r] if f.get(w) is not None]
                            if not S:
                                continue
                            d = np.array([v[w] - sm.own[w] for w in S])
                            q4[(st, r, vr, beta, "det")].append((ts, float(np.mean([f[w] for w in S]))))
                            q4[(st, r, vr, beta, "bias_pct")].append((ts, float(d.mean() / sm.mean * 100)))
                            q4[(st, r, vr, beta, "end_bias_pct")].append((ts, float(d[-1] / sm.mean * 100)))

    A = lambda d, key: P.agg_seed([(sd, v) for sd, v in d[key] if v is not None])
    res = {"spec": "docs/thesis/planB_realtime_spec.md", "time_unit": "second", "rates": Q1_RATES,
           "horizons_s": HORIZONS, "criterion": "2c = two truly consecutive seconds"}
    Q1 = {}
    for st in SETS:
        Q1[st] = {}
        for r in REFS:
            Q1[st][r] = {}
            for D in HORIZONS:
                det = {str(k): A(acc, ("q1", st, r, D, k)) for k in Q1_RATES}
                fl = A(acc, ("floor", st, r, D))
                rstar = next((k for k in Q1_RATES if det[str(k)]["mean"] >= 0.5 and det[str(k)]["mean"] > fl["mean"]), None)
                Q1[st][r][str(D)] = {"detect": det, "clean_floor": fl, "r_star": rstar}
    res["Q1_frontier"] = Q1
    Q2 = {}
    for st in SETS:
        Q2[st] = {}
        for r in REFS:
            Q2[st][r] = {}
            for k in Q1_RATES:
                rows = q2rows[(st, r, k)]; det = [x for x in rows if x["detected"]]
                Q2[st][r][str(k)] = {
                    "n": len(rows),
                    "undetected_frac": P.agg_seed([(x["seed"], float(not x["detected"])) for x in rows]),
                    "detected_median_seconds": float(np.median([x["seconds"] for x in det])) if det else None,
                    "detected_median_offset_pct": float(np.median([x["offset_pct"] for x in det])) if det else None,
                    "all_median_offset_pct_censored": float(np.median([x["offset_pct"] for x in rows])),
                    "all_median_cum_mean_s_censored": float(np.median([x["cum_mean_s"] for x in rows]))}
    res["Q2_bias_at_detection"] = Q2
    res["Q4_threshold_hugging"] = {st: {r: {vr: {str(b): {m: A(q4, (st, r, vr, b, m)) for m in ("det", "bias_pct", "end_bias_pct")}
                                                     for b in BETAS} for vr in VARIANTS} for r in REFS} for st in SETS}

    bad = [(st, r, b) for st in SETS for r in REFS for b in BETAS
           if res["Q4_threshold_hugging"][st][r]["oracle"][str(b)]["det"]["mean"] != 0.0]
    print("── 檢查 1：Q4 oracle β<1 依構造不可偵測 ──", "✗ " + str(bad) if bad else "✓")
    if bad:
        raise SystemExit("先查原因，不寫檔。")

    # ---------------- Q6 ----------------
    def eval_scales(scales):
        out = collections.defaultdict(list)
        for ts in seeds:
            s = scales[ts]
            for sm in P.samples_of(ts, data[ts]):
                SS = sets_of(sm)
                for r in REFS:
                    for st in SETS:
                        out[(st, r, "clean")].append((ts, P.rate(P.flags_from_z(zfun(sm, r, sm.own, s)), SS[st][r])))
                    for k in Q6_RATES:
                        f = P.flags_from_z(zfun(sm, r, P.inject_drift(sm.own, sm.w_on, k, sm.mean), s))
                        for st in SETS:
                            out[(st, r, k)].append((ts, P.rate(f, SS[st][r])))
        return {st: {r: {"clean_fpr": A(out, (st, r, "clean")), "drift": {str(k): A(out, (st, r, k)) for k in Q6_RATES}}
                     for r in REFS} for st in SETS}

    base_s = {ts: P.fold_scale(data, seeds, ts) for ts in seeds}
    Q6 = {"baseline": {"s_ms": base_s, **eval_scales(base_s)}, "poisoned": {}}
    e9rt = json.load(open(os.path.join(args.out_dir, "E9_operating_regime_rt.json"), encoding="utf-8"))
    ok2 = Q6["baseline"]["own"]["spatial"]["clean_fpr"]["mean"] == e9rt["own"]["spatial"]["clean_fpr"]["mean"]
    print("── 檢查 2：Q6 未中毒空間乾淨誤報 = E9_rt ──", "✓" if ok2 else "✗")
    if not ok2:
        raise SystemExit("先查原因，不寫檔。")
    for k in Q6_K:
        for kind, mag in Q6_POISON:
            scales, eps = {}, {}
            for ts in seeds:
                train, n_all, n_bad = [], 0, 0
                for x in seeds:
                    if x == ts:
                        continue
                    pw, tg = poison_training(data[x], k, kind, mag)
                    train.append(pw)
                    for w in data[x]:
                        n_all += len(data[x][w]); n_bad += sum(1 for c in data[x][w] if c in tg)
                scales[ts] = global_scale(train); eps[ts] = n_bad / n_all
            Q6["poisoned"][f"k{k}_{kind}{mag}"] = {"k": k, "kind": kind, "mag": mag, "s_ms": scales,
                                                  "s_ratio": {t: scales[t] / base_s[t] for t in seeds},
                                                  "contamination_frac": eps, **eval_scales(scales)}
    res["Q6_calibration_poisoning"] = Q6

    vals = {}
    for st in SETS:
        for r in REFS:
            for D in HORIZONS:
                vals[f"q1|{st}|{r}|{D}|rstar"] = Q1[st][r][str(D)]["r_star"]
                vals[f"q1|{st}|{r}|{D}|floor"] = Q1[st][r][str(D)]["clean_floor"]["mean"]
            for k in Q1_RATES:
                vals[f"q2|{st}|{r}|{k}|undet"] = Q2[st][r][str(k)]["undetected_frac"]["mean"]
            for vr in VARIANTS:
                for b in BETAS:
                    vals[f"q4|{st}|{r}|{vr}|{b}|bias"] = res["Q4_threshold_hugging"][st][r][vr][str(b)]["bias_pct"]["mean"]
    for name, v in Q6["poisoned"].items():
        vals[f"q6|{name}|common|spatial|0.01"] = v["common"]["spatial"]["drift"]["0.01"]["mean"]
    res["baseline_status"] = P.check_baseline("slow_rt", vals, args.set_baseline, note="2026-10-06 人工核對")
    print("── 回歸基準 slow_rt：", res["baseline_status"], "──\n")
    path = os.path.join(args.out_dir, "slow_poisoning_suite_rt.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, ensure_ascii=False)
    report(res)
    print(f"\n寫入 {path}")
    if not args.no_fig:
        draw(res, args.out_dir)


def report(res):
    st = "common"
    Q1, Q2, Q4, Q6 = (res["Q1_frontier"][st], res["Q2_bias_at_detection"][st],
                      res["Q4_threshold_hugging"][st], res["Q6_calibration_poisoning"])
    fmt = lambda x: f"{x*100:g}%" if x is not None else ">15%"
    print("══ Q1（common）：r*_D ／乾淨底線 ══")
    for D in HORIZONS:
        a, b = Q1["spatial"][str(D)], Q1["temporal"][str(D)]
        print(f"  D={D:>2}s  空間 {fmt(a['r_star']):>6}／{a['clean_floor']['mean']:.2f}   時間 {fmt(b['r_star']):>6}／{b['clean_floor']['mean']:.2f}")
    print("══ Q2（common, 2c）：未偵測比例｜偵測秒數中位｜偵測時偏移% ══")
    for k in res["rates"]:
        a, b = Q2["spatial"][str(k)], Q2["temporal"][str(k)]
        g = lambda q: f"{q['undetected_frac']['mean']:.2f}｜{q['detected_median_seconds']}｜{q['detected_median_offset_pct']}"
        print(f"  {k*100:>5.2f}%/s  空間 {g(a)}    時間 {g(b)}")
    print("══ Q4（common）：偵測率／平均偏差%／區間末偏差% ══")
    for vr in VARIANTS:
        for bta in BETAS:
            a, b = Q4["spatial"][vr][str(bta)], Q4["temporal"][vr][str(bta)]
            print(f"  {vr:>6} β={bta:<4} 空間 {a['det']['mean']:.2f}/{a['bias_pct']['mean']:.1f}/{a['end_bias_pct']['mean']:.1f}"
                  f"   時間 {b['det']['mean']:.2f}/{b['bias_pct']['mean']:.1f}/{b['end_bias_pct']['mean']:.1f}")
    print("══ Q6（common, 空間）：s 倍數範圍｜1%/s 偵測｜乾淨誤報 ══")
    b0 = Q6["baseline"]["common"]["spatial"]
    print(f"  未中毒  {b0['drift']['0.01']['mean']:.2f}｜{b0['clean_fpr']['mean']:.3f}")
    for n, v in Q6["poisoned"].items():
        print(f"  {n:<16} s×{min(v['s_ratio'].values()):.2f}–{max(v['s_ratio'].values()):.2f}｜"
              f"{v['common']['spatial']['drift']['0.01']['mean']:.2f}｜{v['common']['spatial']['clean_fpr']['mean']:.3f}")


def draw(res, out_dir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    C = {"spatial": "#2b8a3e", "temporal": "#c92a2a"}
    st = "common"; rates = res["rates"]; x = [r * 100 for r in rates]
    fig, axes = plt.subplots(1, len(HORIZONS), figsize=(14, 3.8), sharey=True)
    for ax, D in zip(axes, HORIZONS):
        for r in REFS:
            d = res["Q1_frontier"][st][r][str(D)]
            ax.plot(x, [d["detect"][str(k)]["mean"] for k in rates], marker="o", ms=4, color=C[r],
                    ls="-" if r == "spatial" else "--", label=r)
            ax.axhline(d["clean_floor"]["mean"], color=C[r], lw=0.8, ls=":")
        ax.set_xscale("log"); ax.set_title(f"detected within {D} s", fontsize=10)
        ax.set_xlabel("drift rate (% per second, log)"); ax.grid(alpha=0.3)
    axes[0].set_ylabel("P(detected), 2 truly consecutive seconds"); axes[0].legend(fontsize=8)
    fig.suptitle("Q1 detection frontier, common set (dotted = clean floor)", fontsize=11)
    fig.tight_layout(); fig.savefig(os.path.join(out_dir, "fig_slow_Q1_frontier_rt.png"), dpi=200); plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.5, 4))
    for r in REFS:
        d = res["Q2_bias_at_detection"][st][r]
        ax.plot(x, [d[str(k)]["all_median_offset_pct_censored"] for k in rates], marker="o", color=C[r],
                ls="-" if r == "spatial" else "--", label=r)
    ax.set_xscale("log"); ax.set_yscale("log"); ax.grid(alpha=0.3); ax.legend(fontsize=8)
    ax.set_xlabel("drift rate (% per second, log)")
    ax.set_ylabel("median offset (% of mean)\nundetected samples censored at last window")
    ax.set_title("Q2 censored median offset (all samples; differs from the detected-only table)", fontsize=9.5)
    fig.tight_layout(); fig.savefig(os.path.join(out_dir, "fig_slow_Q2_bias_rt.png"), dpi=200); plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for ax, key, lab in ((axes[0], "det", "alarm rate"), (axes[1], "end_bias_pct", "bias at end of interval (% of mean)")):
        for r in REFS:
            for vr, ls in zip(VARIANTS, ("-", "--", ":")):
                ax.plot(BETAS, [res["Q4_threshold_hugging"][st][r][vr][str(b)][key]["mean"] for b in BETAS],
                        marker="o", ms=4, color=C[r], ls=ls, label=f"{r}/{vr}")
        ax.set_xlabel("β (fraction of τ_S·s)"); ax.set_ylabel(lab); ax.grid(alpha=0.3)
    axes[1].set_yscale("symlog"); axes[0].legend(fontsize=7, ncol=2)
    fig.suptitle("Q4 threshold-hugging attacker, common set (real-time seconds)", fontsize=11)
    fig.tight_layout(); fig.savefig(os.path.join(out_dir, "fig_slow_Q4_hugging_rt.png"), dpi=200); plt.close(fig)
    print(f"圖已存: {out_dir}/fig_slow_Q*_rt.png")


if __name__ == "__main__":
    main()
