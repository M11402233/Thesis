#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_E9_rt.py — 方案 B：4.7.4 參照機制消融 + 4.7.5 E9 操作區對照，以實際秒數為時間單位

規格：docs/thesis/planB_realtime_spec.md。舊版（以被評估窗為單位）之結果
E9_operating_regime.json 保留不動，本檔輸出 E9_operating_regime_rt.json。

【攻擊族】漂移 r ∈ {0.1, 0.2, 0.5, 1, 2, 4, 8, 15} %/秒；階躍 AF ∈ {1.2, 1.3, 1.4, 1.5}
【比較集合】own（各方法自身可評估集合）與 common（三方法共同可評估集合，主結果）
【指標】注入區間告警比例、onset 命中（注入後前 5 秒）、乾淨誤報率；另報可評估率

【內建檢查（附條件之逐筆相同，見規格第五節）】
  1. 空間參照之乾淨判定：於原始評估集合，逐窗與舊實作（z = |ser − c| / s）相同。
  2. 空間參照之乾淨誤報率與四個階躍之偵測率（原始評估集合、同注入時點）須與
     E9_operating_regime.json 逐位相同。
  任一失敗即停止、不寫檔。
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

DRIFT_RATES = E9.DRIFT_RATES
STEP_AFS = E9.STEP_AFS
REFS = ("spatial", "temporal")
SETS = ("own", "common")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=E9.OUT_DIR)
    ap.add_argument("--no-fig", action="store_true")
    ap.add_argument("--set-baseline", action="store_true", help="僅於人工核對後使用")
    args = ap.parse_args()
    seeds, data = P.load_data()

    acc = collections.defaultdict(list)          # key -> [(seed, value)]
    avail = collections.defaultdict(list)
    chk_rows = 0
    for ts in seeds:
        s = P.fold_scale(data, seeds, ts)
        for sm in P.samples_of(ts, data[ts]):
            # 檢查 1：空間乾淨判定逐窗與舊實作相同
            ser = np.array([sm.own[w] for w in sm.idx]); pmv = np.array([sm.pm[w] for w in sm.idx])
            old = (np.abs(ser - pmv) / s) > P.TAU_S
            new = P.flags_from_z(P.z_spatial(sm, sm.own, s))
            if any(bool(old[i]) != new[w] for i, w in enumerate(sm.idx)):
                raise SystemExit(f"✗ 空間乾淨判定與舊實作不同：seed {ts} cell {sm.cell}")
            chk_rows += len(sm.idx)

            sets = {"own": {r: P.own_set(sm, r) for r in REFS}, "common": {r: P.common_set(sm) for r in REFS}}
            n = len(sm.post)
            avail["temporal"].append((ts, len(P.own_set(sm, "temporal")) / n))
            avail["supervised"].append((ts, len(P.own_set(sm, "supervised")) / n))
            avail["common"].append((ts, len(P.common_set(sm)) / n))
            avail["full10"].append((ts, float(np.mean([sm.full10[w] for w in sm.post]))))

            def fl(r, v):
                return P.flags_from_z(P.z_spatial(sm, v, s) if r == "spatial" else P.z_temporal(sm, v, s))

            for r in REFS:
                f0 = fl(r, sm.own)
                for st in SETS:
                    acc[(st, r, "clean")].append((ts, P.rate(f0, sets[st][r])))
                for rate in DRIFT_RATES:
                    f = fl(r, P.inject_drift(sm.own, sm.w_on, rate, sm.mean))
                    for st in SETS:
                        acc[(st, r, "drift", rate)].append((ts, P.rate(f, sets[st][r])))
                for af in STEP_AFS:
                    f = fl(r, P.inject_step(sm.own, sm.w_on, af))
                    for st in SETS:
                        acc[(st, r, "step", af)].append((ts, P.rate(f, sets[st][r])))
                        acc[(st, r, "onset", af)].append((ts, P.onset_hit(f, sets[st][r], sm.w_on)))

    def A(key):
        return P.agg_seed([(sd, v) for sd, v in acc[key] if v is not None])

    res = {"spec": "docs/thesis/planB_realtime_spec.md", "time_unit": "second",
           "tau_S": P.TAU_S, "hist_win_s": P.HIST_WIN, "seq_s": P.SEQ, "min_obs": P.MIN_OBS,
           "onset_s": P.ONSET_S, "n_samples": len(acc[("own", "spatial", "clean")]),
           "availability_of_original_set": {k: P.agg_seed(v) for k, v in avail.items()}}
    for st in SETS:
        res[st] = {r: {"clean_fpr": A((st, r, "clean")),
                       "drift": {str(k): A((st, r, "drift", k)) for k in DRIFT_RATES},
                       "step": {str(k): A((st, r, "step", k)) for k in STEP_AFS},
                       "step_onset_hit": {str(k): A((st, r, "onset", k)) for k in STEP_AFS}}
                   for r in REFS}

    # 檢查 2：空間乾淨誤報與階躍（原始評估集合 = 空間之 own 集合）逐位重現舊 E9
    old = json.load(open(os.path.join(args.out_dir, "E9_operating_regime.json"), encoding="utf-8"))
    bad = []
    if res["own"]["spatial"]["clean_fpr"]["mean"] != old["clean_fpr"]["spatial"]["mean"]:
        bad.append(("clean", old["clean_fpr"]["spatial"]["mean"], res["own"]["spatial"]["clean_fpr"]["mean"]))
    for af in STEP_AFS:
        a, b = res["own"]["spatial"]["step"][str(af)]["mean"], old["step"]["spatial"][str(af)]["mean"]
        if a != b:
            bad.append(("step", af, b, a))
    print("── 內建檢查 ──")
    print(f"  1. 空間乾淨判定逐窗與舊實作相同（{chk_rows} 窗） ✓")
    if bad:
        print("  2. ✗", bad); raise SystemExit("與舊 E9 不一致，先查原因，不寫檔。")
    print("  2. 空間乾淨誤報與 4 個階躍（原始評估集合、同注入時點）逐位重現舊 E9 ✓\n")

    vals = {f"{st}|{r}|{fam}|{k}": res[st][r][fam][k]["mean"]
            for st in SETS for r in REFS for fam in ("drift", "step", "step_onset_hit") for k in res[st][r][fam]}
    vals.update({f"{st}|{r}|clean": res[st][r]["clean_fpr"]["mean"] for st in SETS for r in REFS})
    vals.update({f"avail|{k}": v["mean"] for k, v in res["availability_of_original_set"].items()})
    st_ = P.check_baseline("E9_rt", vals, args.set_baseline,
                           note="2026-10-06 人工核對：時間參照獨立重算 4,268 窗 0 不一致；缺窗、注入邊界、歷史不足、缺窗隔開之告警皆抽查")
    print(f"  3. 回歸基準 E9_rt：{st_}\n")
    path = os.path.join(args.out_dir, "E9_operating_regime_rt.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, ensure_ascii=False)

    av = res["availability_of_original_set"]
    print("可評估率（相對原始評估集合，樣本等權）：" + "、".join(f"{k} {v['mean']:.3f}" for k, v in av.items()))
    for st in SETS:
        print(f"\n══ {st} 集合 ══  乾淨誤報：空間 {res[st]['spatial']['clean_fpr']['mean']:.3f}、"
              f"時間 {res[st]['temporal']['clean_fpr']['mean']:.3f}")
        print(f"{'漂移 %/秒':>9} {'空間':>6} {'時間':>6}")
        for k in DRIFT_RATES:
            print(f"{k*100:>9.1f} {res[st]['spatial']['drift'][str(k)]['mean']:>6.2f} "
                  f"{res[st]['temporal']['drift'][str(k)]['mean']:>6.2f}")
        print(f"{'階躍':>9} {'空間':>6} {'時間':>6} {'空間onset':>9} {'時間onset':>9}")
        for k in STEP_AFS:
            print(f"{'×'+str(k):>9} {res[st]['spatial']['step'][str(k)]['mean']:>6.2f} "
                  f"{res[st]['temporal']['step'][str(k)]['mean']:>6.2f} "
                  f"{res[st]['spatial']['step_onset_hit'][str(k)]['mean']:>9.2f} "
                  f"{res[st]['temporal']['step_onset_hit'][str(k)]['mean']:>9.2f}")
    print(f"\n寫入 {path}")
    if not args.no_fig:
        draw(res, os.path.join(args.out_dir, "fig_E9_operating_regime_rt.png"))


def draw(res, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    C = {"spatial": "#2b8a3e", "temporal": "#c92a2a"}
    R = res["common"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.8), sharey=True, gridspec_kw={"width_ratios": [1.6, 1]})
    x = [r * 100 for r in DRIFT_RATES]
    for r, mk, ls in (("spatial", "o", "-"), ("temporal", "s", "--")):
        d = R[r]["drift"]
        a1.plot(x, [d[str(k)]["mean"] for k in DRIFT_RATES], marker=mk, ls=ls, color=C[r], lw=2, label=r)
        a1.fill_between(x, [d[str(k)]["seed_min"] for k in DRIFT_RATES],
                        [d[str(k)]["seed_max"] for k in DRIFT_RATES], color=C[r], alpha=0.12)
        d = R[r]["step"]; xs = range(len(STEP_AFS))
        a2.plot(xs, [d[str(k)]["mean"] for k in STEP_AFS], marker=mk, ls=ls, color=C[r], lw=2)
    o = R["temporal"]["step_onset_hit"]
    a2.plot(range(len(STEP_AFS)), [o[str(k)]["mean"] for k in STEP_AFS], "^:", color=C["temporal"],
            label="temporal: onset hit (first 5 s)")
    a1.set_xscale("log"); a1.set_xticks(x); a1.set_xticklabels([f"{v:g}" for v in x])
    a1.set_xlabel("gradual drift: rate per second (% of mean delay, log)")
    a1.set_ylabel("alarm rate in injection interval (common set)"); a1.grid(alpha=0.3); a1.legend(fontsize=9)
    a2.set_xticks(range(len(STEP_AFS))); a2.set_xticklabels([f"×{a}" for a in STEP_AFS])
    a2.set_xlabel("step amplification factor"); a2.grid(alpha=0.3); a2.legend(fontsize=8)
    av = res["availability_of_original_set"]["common"]["mean"]
    fig.suptitle(f"Plan B (real-time seconds): spatial vs temporal reference — common evaluable set "
                 f"({av*100:.1f}% of original windows); shaded = seed range", fontsize=10.5)
    fig.tight_layout(); fig.savefig(path, dpi=200)
    print(f"圖已存: {path}")


if __name__ == "__main__":
    main()
