#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_E15_E16_D1_robustness.py — E15（D1 分群門檻敏感度）與 E16（超時消失之嚴重度–反應曲線）
規格：docs/thesis/E15_E18_supplementary_spec.md v1（主結果產出後新增之補充實驗；不改凍結參數）

實作：判定、基線、注入一律取自 run_Hi_D1_performance.py（H）；E15 僅覆寫 H.EDGE_SPLIT 後呼叫 H.run_once；
      E16 以 H 之函式重跑注入迴圈，僅將注入倍數改為參數。
內建檢查（失敗即停止、不寫檔）：
  1. E15 之 0.55 逐 seed 結果 = 既有 Hi_D1_performance.json。
  2. E16 以倍數 {1.5, 2.0, 3.0} 合併之逐 seed TPR 與平均延遲 = 既有 Hi_D1_performance.json。
  3. 結束時 H.EDGE_SPLIT、H.TAU_Z_REJECT 已還原。
"""
import os
import sys
import glob
import json
import argparse
import numpy as np
import datasets as DS
import run_Hi_D1_performance as H

TAU_Z = 3.0
SPLITS = [0.50, 0.55, 0.60]
MULTS = [0.5, 0.75, 1.0, 1.1, 1.25, 1.5, 2.0, 3.0]
REF_MULTS = (1.5, 2.0, 3.0)
FROZEN_SPLIT = 0.55


def files_seeds():
    files = sorted(glob.glob(os.path.join(H.DATA_DIR, DS.PATTERN)))
    return files, [os.path.basename(f).split("seed")[-1].replace(".txt", "") for f in files]


def agg(vals):
    v = [x for x in vals if x == x]
    return {"mean": float(np.mean(v)) if v else None, "seed_min": float(min(v)) if v else None,
            "seed_max": float(max(v)) if v else None}


def group_sizes(split):
    files, _ = files_seeds()
    n = {"edge": 0, "resident": 0}
    for f in files:
        rec = H.load(f)
        all_w = sorted(set(w for im, wm in rec.items() for w in wm))
        for imsi, wm in rec.items():
            n["edge" if H.ue_lte_fraction(H.state_seq(wm, all_w)) >= split else "resident"] += 1
    return n


def e15():
    out, raw = {}, {}
    for sp in SPLITS:
        H.EDGE_SPLIT = sp
        ps = H.run_once(TAU_Z)
        raw[sp] = ps
        out[str(sp)] = {"groups": group_sizes(sp),
                        **{k: agg([p[k] for p in ps]) for k in ("fpr_all", "fpr_edge", "fpr_resident", "tpr_all",
                                                                 "tpr_edge", "tpr_resident", "mean_detection_delay")},
                        "edge_fpr_gt_resident_seeds": sum(1 for p in ps if p["fpr_edge"] > p["fpr_resident"]),
                        "per_seed": ps}
    H.EDGE_SPLIT = FROZEN_SPLIT
    return out, raw


def severity(mults):
    """回傳 {mult: [逐 seed {tpr_all, tpr_edge, tpr_resident, delays:[...]}]}；迴圈結構同 H.run_once 之注入段"""
    H.EDGE_SPLIT = FROZEN_SPLIT; H.TAU_Z_REJECT = TAU_Z
    files, seeds = files_seeds()
    res = {m: [] for m in mults}
    for ts, tf in zip(seeds, files):
        hampel, emp, grp_hampel, grp_emp = H.build_baseline([f for f in files if f != tf])
        rec = H.load(tf)
        all_w = sorted(set(w for im, wm in rec.items() for w in wm))
        tp = {m: {"edge": [0, 0], "resident": [0, 0]} for m in mults}
        delays = {m: [] for m in mults}
        # 分解（E16b）：偵測發生於注入段之內或之後；注入長度是否受「至少 2 窗」之下限抬高
        dec = {m: {g: {"within": 0, "beyond": 0, "floor": 0} for g in ("edge", "resident")} for m in mults}
        for imsi, wm in rec.items():
            seq = H.state_seq(wm, all_w)
            grp = "edge" if H.ue_lte_fraction(seq) >= H.EDGE_SPLIT else "resident"
            med, sig, clean = H.get_params(imsi, grp, hampel, emp, grp_hampel, grp_emp)
            base_hi = med + H.TAU_Z_REJECT * sig
            for m in mults:
                extra = max(2, int(round(base_hi * m)))
                s2, inj = H.inject_disappearance(seq, len(all_w) // 3, extra)
                detected, run = False, 0
                for t in range(inj, len(s2)):
                    if s2[t] == "lte":
                        run += 1
                        if H.is_violated(run, med, sig, clean)[0]:
                            delays[m].append(t - inj + 1); detected = True
                            dec[m][grp]["within" if run <= extra else "beyond"] += 1
                            break
                    else:
                        break
                tp[m][grp][1] += 1
                if base_hi * m < 2:
                    dec[m][grp]["floor"] += 1
                if detected:
                    tp[m][grp][0] += 1
        r = lambda p: p[0] / p[1] if p[1] else float("nan")
        for m in mults:
            e, rs = tp[m]["edge"], tp[m]["resident"]
            res[m].append({"seed": ts, "tpr_all": r([e[0] + rs[0], e[1] + rs[1]]), "tpr_edge": r(e),
                           "tpr_resident": r(rs), "n": e[1] + rs[1], "det": e[0] + rs[0], "delays": delays[m],
                           "n_edge": e[1], "n_resident": rs[1], "decomp": dec[m]})
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()
    out_dir = args.out_dir or DS.results_dir()
    ref = json.load(open(os.path.join(out_dir, "Hi_D1_performance.json"), encoding="utf-8"))["per_seed"]
    print(f"資料集 {DS.NAME}；τ_z = {TAU_Z}；z_only\n")

    E15, raw = e15()
    ok1 = raw[FROZEN_SPLIT] == ref
    print(f"── 檢查 1：E15 之 {FROZEN_SPLIT} 逐 seed = Hi_D1_performance.json {'✓' if ok1 else '✗'}")

    sev = severity(sorted(set(MULTS) | set(REF_MULTS)))
    ok2 = True
    for i, p in enumerate(ref):
        det = sum(sev[m][i]["det"] for m in REF_MULTS); n = sum(sev[m][i]["n"] for m in REF_MULTS)
        dl = [d for m in REF_MULTS for d in sev[m][i]["delays"]]
        # 既有腳本之延遲依 UE、倍數之巡訪順序累加；平均值與順序無關，惟浮點加總順序可能不同，故以 1e-12 比較
        ok2 &= (det / n == p["tpr_all"]) and abs(float(np.mean(dl)) - p["mean_detection_delay"]) <= 1e-12
    print(f"── 檢查 2：E16 倍數 {REF_MULTS} 合併 = Hi_D1_performance.json {'✓' if ok2 else '✗'}")
    ok3 = H.EDGE_SPLIT == FROZEN_SPLIT and H.TAU_Z_REJECT == TAU_Z
    print(f"── 檢查 3：模組參數已還原 {'✓' if ok3 else '✗'}")
    if not (ok1 and ok2 and ok3):
        print("  ✗ 檢查未通過。停止：不寫入任何輸出。請回報，勿調參數。"); sys.exit(2)

    f = lambda e, pct=False: "—" if e["mean"] is None else f"{e['mean']:.3f}（{e['seed_min']:.3f}–{e['seed_max']:.3f}）"
    print("\n══ E15：分群門檻敏感度（★ = 沿用值）══")
    print(f"{'split':<7}{'resident/edge':>15}{'FPR 整體':>26}{'FPR resident':>26}{'FPR edge':>26}{'TPR':>8}{'延遲':>7}  edge>resident 之 seed 數")
    for sp in SPLITS:
        r = E15[str(sp)]; g = r["groups"]
        print(f"{sp:<5}{'★' if sp == FROZEN_SPLIT else ' ':<2}{str(g['resident']) + '/' + str(g['edge']):>15}{f(r['fpr_all']):>26}"
              f"{f(r['fpr_resident']):>26}{f(r['fpr_edge']):>26}{r['tpr_all']['mean']:>8.2f}{r['mean_detection_delay']['mean']:>7.1f}  {r['edge_fpr_gt_resident_seeds']}/8")

    E16 = {}
    print("\n══ E16：嚴重度–反應曲線（注入長度 = 倍數 × 正常上界；分群門檻 0.55）══")
    print(f"{'倍數':<6}{'偵測率 整體':>26}{'resident':>26}{'edge':>26}{'平均延遲（窗）':>14}")
    for m in MULTS:
        rows = sev[m]
        dl = [d for r in rows for d in r["delays"]]
        E16[str(m)] = {"tpr_all": agg([r["tpr_all"] for r in rows]), "tpr_resident": agg([r["tpr_resident"] for r in rows]),
                       "tpr_edge": agg([r["tpr_edge"] for r in rows]), "n": sum(r["n"] for r in rows),
                       "detected": sum(r["det"] for r in rows), "mean_delay_detected": float(np.mean(dl)) if dl else None}
        e = E16[str(m)]
        print(f"{m:<6}{f(e['tpr_all']):>26}{f(e['tpr_resident']):>26}{f(e['tpr_edge']):>26}"
              f"{('—' if e['mean_delay_detected'] is None else format(e['mean_delay_detected'], '.1f')):>14}   （{e['detected']}/{e['n']}）")

    # ---- E16b：偵測之分解（描述性；回應 E16 之「未分解」）----
    E16b = {}
    print("\n══ E16b：偵測發生之位置（注入段之內／注入段結束後仍連續停留於 LTE）與 2 窗下限 ══")
    print(f"{'倍數':<6}{'群':<10}{'注入數':>6}{'段內偵測':>9}{'段後偵測':>9}{'受 2 窗下限抬高之注入':>20}")
    for m in MULTS:
        E16b[str(m)] = {}
        for g in ("resident", "edge"):
            n = sum(r["n_" + g] for r in sev[m])
            d = {k: sum(r["decomp"][g][k] for r in sev[m]) for k in ("within", "beyond", "floor")}
            E16b[str(m)][g] = dict(d, n=n)
            print(f"{m:<6}{g:<10}{n:>6}{d['within']:>9}{d['beyond']:>9}{d['floor']:>20}")
        tot = sum(E16b[str(m)][g]["within"] + E16b[str(m)][g]["beyond"] for g in ("resident", "edge"))
        if tot != E16[str(m)]["detected"]:
            print("  ✗ 分解之合計與偵測數不符。停止。"); sys.exit(2)
    print("── 檢查 4：各倍數之（段內 + 段後）= 偵測數 ✓")

    out = {"spec": "docs/thesis/E15_E18_supplementary_spec.md v1", "post_hoc": True, "dataset": DS.NAME, "tau_z": TAU_Z,
           "decision_rule": H.DECISION_RULE, "checks": "ok", "E15_edge_split": E15, "E16_severity": E16, "E16b_decomposition": E16b,
           "clean_fpr_reference": E15[str(FROZEN_SPLIT)]["fpr_all"]}
    p = os.path.join(out_dir, "E15_E16_D1_robustness.json")
    json.dump(out, open(p, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"\n寫入 {p}")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    for key, col, lab in (("tpr_all", "#212529", "all UEs"), ("tpr_resident", "#1971c2", "resident"), ("tpr_edge", "#e67700", "edge")):
        y = [E16[str(m)][key]["mean"] for m in MULTS]
        ax.plot(MULTS, y, "o-", color=col, label=lab)
        if key == "tpr_all":
            ax.fill_between(MULTS, [E16[str(m)][key]["seed_min"] for m in MULTS],
                            [E16[str(m)][key]["seed_max"] for m in MULTS], color=col, alpha=0.10)
    ax.axhline(E15[str(FROZEN_SPLIT)]["fpr_all"]["mean"], color="#868e96", ls=":", label="clean per-UE false-alarm rate")
    ax.axvline(1.0, color="k", lw=0.6, ls=":")
    ax.set_xlabel("injected LTE-only dwell (multiple of the normal upper bound, median + 3σ)")
    ax.set_ylabel("detection rate"); ax.set_ylim(-0.03, 1.05); ax.grid(alpha=0.3); ax.legend(fontsize=8)
    ax.set_title(f"E16: D1 severity–response ({DS.NAME}, shaded = seed range)", fontsize=10)
    fig.tight_layout(); fp = os.path.join(out_dir, "fig_E16_D1_severity.png"); fig.savefig(fp, dpi=180)
    print("圖已存:", fp)


if __name__ == "__main__":
    main()
