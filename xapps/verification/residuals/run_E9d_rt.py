#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_E9d_rt.py — 方案 B：真實 trace 中「其他 cell 高負載、高延遲背景」與乾淨誤報之關聯（使用 E9b_rt 之分類器）

規格：docs/thesis/planB_realtime_spec.md。舊版 E9d_real_load_alarms.json 保留不動。
負載代理、場域指標、分組規則與 run_E9d_real_load_alarms.py 完全相同（事前固定，不得調整），
改變者為：三方法之判定依方案 B 定義；評估窗 = 各樣本後半段 full-consensus 窗中三方法共同可評估者。

【口徑】
  - 分組名稱：「其他 cell 高負載、高延遲背景」（F、D 皆 ≥ 該 seed 之第 q 分位數）。百分位分組
    描述的是同窗其他 cell 之相對水準，**不代表時間上之上升**。
  - 樣本單位：(seed, cell, 評估窗)；同一 seed × cell 內之窗彼此相關，非獨立樣本。
  - 倍數比較一律註明對照組（「負載低、延遲低」組）。
  - 某組未觀察到告警，不代表該背景下誤報率為零。
  - 觀察性關聯，非因果。
【內建檢查】資料一致性（四 seed aux cmp）；三方法於評估窗之乾淨誤報與 E9_rt／E9b_rt 之 common 值逐位相同。
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
import run_E9b_rt as BR
import run_E9c_rt as CR
from run_E9d_real_load_alarms import check_aux, load_phy, norm, field_index, Q_MAIN, Q_SENS

METHODS = CR.METHODS
G_HH, G_LL = "其他cell高負載高延遲", "其他cell低負載低延遲"
LABEL = {"F高D高": G_HH, "F高D低": "其他cell高負載低延遲", "F低D高": "其他cell低負載高延遲", "F低D低": G_LL}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=E9.OUT_DIR)
    ap.add_argument("--set-baseline", action="store_true")
    args = ap.parse_args()
    seeds, data = P.load_data()
    ok = check_aux(seeds)
    print("── 資料一致性 ──", " ".join(f"{s}:{'✓' if v else '✗'}" for s, v in ok.items()))
    if not all(ok.values()):
        raise SystemExit("並非全部 seed 通過逐位比對，拒絕分析。")
    phy_all, phy_new, nd = {}, {}, {}
    for sd in seeds:
        a, n = load_phy(sd)
        cells = {c for w in data[sd] for c in data[sd][w]}
        phy_all[sd] = {c: norm({w: a[c].get(w, 0) for w in data[sd] if c in data[sd][w]}) for c in cells}
        phy_new[sd] = {c: norm({w: n[c].get(w, 0) for w in data[sd] if c in data[sd][w]}) for c in cells}
        nd[sd] = {c: norm({w: data[sd][w][c] for w in data[sd] if c in data[sd][w]}) for c in cells}

    e9rt = json.load(open(os.path.join(args.out_dir, "E9_operating_regime_rt.json"), encoding="utf-8"))
    e9brt = json.load(open(os.path.join(args.out_dir, "E9b_supervised_baseline_rt.json"), encoding="utf-8"))
    rows, chk, n_none = [], {m: [] for m in METHODS}, 0
    for fi, ts in enumerate(seeds):
        m, med, s, thr, _ = BR.get_fold_model(data, seeds, fi, ts)
        model = (m, med, thr)
        for sm in P.samples_of(ts, data[ts]):
            C = P.common_set(sm)
            fl = {mt: CR.flags(mt, sm, sm.own, s, model) for mt in METHODS}
            for mt in METHODS:
                chk[mt].append((ts, P.rate(fl[mt], C)))
            for w in C:
                F, D = field_index(data[ts], phy_all[ts], nd[ts], sm.cell, w)
                Fn, _ = field_index(data[ts], phy_new[ts], nd[ts], sm.cell, w)
                if F is None or Fn is None:
                    n_none += 1; continue
                rows.append({"seed": ts, "cell": sm.cell, "w": w, "F": F, "Fnew": Fn, "D": D,
                             **{mt: bool(fl[mt][w]) for mt in METHODS}})
    ref = {"spatial": e9rt["common"]["spatial"]["clean_fpr"]["mean"],
           "temporal": e9rt["common"]["temporal"]["clean_fpr"]["mean"],
           "supervised": e9brt["thr_cal"]["common"]["clean_fpr"]["mean"]}
    bad = [(mt, ref[mt]) for mt in METHODS
           if P.agg_seed([(sd, v) for sd, v in chk[mt] if v is not None])["mean"] != ref[mt]]
    print("── 乾淨誤報 vs E9_rt／E9b_rt ──", "✗ " + str(bad) if bad else "✓")
    if bad:
        raise SystemExit("先查原因，不寫檔。")

    def grouping(q, fkey):
        thrF = {sd: float(np.quantile([r[fkey] for r in rows if r["seed"] == sd], q)) for sd in seeds}
        thrD = {sd: float(np.quantile([r["D"] for r in rows if r["seed"] == sd], q)) for sd in seeds}
        groups = collections.defaultdict(list)
        for r in rows:
            g = ("F高" if r[fkey] >= thrF[r["seed"]] else "F低") + ("D高" if r["D"] >= thrD[r["seed"]] else "D低")
            groups[LABEL[g]].append(r)
        out = {}
        for g in LABEL.values():
            rs = groups.get(g, [])
            out[g] = {"n_seed_cell_window": len(rs),
                      **{mt: {"alarms": int(sum(r[mt] for r in rs)),
                              "rate": float(np.mean([r[mt] for r in rs])) if rs else None} for mt in METHODS},
                      "per_seed": {sd: {"n": sum(1 for r in rs if r["seed"] == sd),
                                        **{mt: (float(np.mean([r[mt] for r in rs if r["seed"] == sd]))
                                                if any(r["seed"] == sd for r in rs) else None) for mt in METHODS}}
                                   for sd in seeds}}
        return {"q": q, "load": fkey, "groups": out}

    analyses = {"main": grouping(Q_MAIN, "F"), "sens_newtx": grouping(Q_MAIN, "Fnew"),
                **{f"sens_q{q}": grouping(q, "F") for q in Q_SENS}}
    res = {"spec": "docs/thesis/planB_realtime_spec.md", "unit": "(seed, cell, evaluated window)",
           "n_rows": len(rows), "n_excluded_no_field_index": n_none,
           "overall_pooled": {mt: float(np.mean([r[mt] for r in rows])) for mt in METHODS},
           "analyses": analyses,
           "wording": {"group": "其他 cell 高負載、高延遲背景（非時間上之上升）",
                       "ratio_reference": G_LL, "zero_alarm": "未觀察到告警不代表誤報率為零",
                       "nature": "observational association, not causal"}}
    g = analyses["main"]["groups"]
    vals = {f"{a}|{grp}|{mt}": analyses[a]["groups"][grp][mt]["alarms"] for a in analyses for grp in LABEL.values() for mt in METHODS}
    vals.update({f"{a}|{grp}|n": analyses[a]["groups"][grp]["n_seed_cell_window"] for a in analyses for grp in LABEL.values()})
    res["baseline_status"] = P.check_baseline("E9d_rt", vals, args.set_baseline, note="2026-10-06 人工核對")
    print("── 回歸基準 E9d_rt：", res["baseline_status"], "──\n")
    path = os.path.join(args.out_dir, "E9d_real_load_alarms_rt.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, ensure_ascii=False)
    print(f"樣本 {len(rows)} 個 (seed, cell, 評估窗)；排除 {n_none}；整體窗合併告警率 " +
          "、".join(f"{k} {v:.3f}" for k, v in res["overall_pooled"].items()))
    for name, a in analyses.items():
        print(f"\n══ {name}（q = {a['q']}，負載 = {a['load']}）══")
        for grp, v in a["groups"].items():
            print(f"  {grp:<12} n={v['n_seed_cell_window']:>4} | " + "  ".join(
                f"{mt} {v[mt]['alarms']:>3}/{v['n_seed_cell_window']} = {v[mt]['rate'] if v[mt]['rate'] is None else round(v[mt]['rate'], 3)}"
                for mt in METHODS))
        hh, ll = a["groups"][G_HH], a["groups"][G_LL]
        print("  各 seed 監督式（" + G_HH + " vs " + G_LL + "）：" + "；".join(
            f"{sd} {hh['per_seed'][sd]['supervised']}(n={hh['per_seed'][sd]['n']}) vs "
            f"{None if ll['per_seed'][sd]['supervised'] is None else round(ll['per_seed'][sd]['supervised'], 3)}(n={ll['per_seed'][sd]['n']})"
            for sd in seeds))
    print(f"\n寫入 {path}")


if __name__ == "__main__":
    main()
