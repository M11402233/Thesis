#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_E12_persist.py — E12：候選規則 R2_SI_PERSIST 之評估（補充分析；定案政策不變）

規格：docs/thesis/E11_E12_B4_spec.md（v2）之 E12 段。

規則：同一節點於**每個實際連續秒窗**皆 S_i 可評估且 violated 才累加；S_i 正常、不可得或節點未上報
皆中斷計數。插入 L2，位於 R2_SI_D1_BOUND 之後、R2_SI_ALONE 之前：計數 ≥ L_S → rejected。
實作為 xApp 註記之後處理：僅原判 R2_SI_ALONE 者可被改判（L1 與 R2_SI_D1_BOUND 優先）。
掃描 L_S ∈ {2, 3, 5, 10}；∞ 表示定案政策（不加新規則）。

量測：
  1. 新增之乾淨誤拒（分母 3,150；各 seed；序列前半／後半）
  2. 到達 rejected 之延遲：S_i 上偏漂移 0.5／1／2 %/秒、階躍 ×1.3／×1.5（自 t0 持續至序列結束）
  3. 可用性成本：乾淨資料上各准入政策（strict／restrict_annotated／C_notrej）之新增不准入
  4. 4.12 RQ3 以新規則重跑（四種准入政策），重點 C_notrej

【內建檢查】
  1. L_S = ∞ 時，xApp 乾淨註記 = runtime_20261006 註記（逐筆）
  2. 連續計數之兩份實作（xApp 註記版、獨立推導 trace 版）逐筆相同
  3. L_S = ∞ 時，本檔重算之 RQ3（uebound）各指標須與 RQ3_decision_replay.json 逐位相同
"""
import os
import sys
import copy
import json
import argparse
import statistics
import collections
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zt_kpm_xapp as X
import run_RQ3_decision_replay as RQ3
import run_E11_transitions as E11
import planB_rt as P

X.FUSION_MODE = "bound"
OUT_DIR = os.path.expanduser("~/oran-zt-kpm-verification/data/results")
L_S_LIST = [None, 2, 3, 5, 10]            # None = ∞（定案政策）
DRIFTS = [0.005, 0.01, 0.02]
STEPS = [1.3, 1.5]
ADMIT = {"strict": lambda a: a["decision"] == "trusted",
         "restrict_annotated": lambda a: a["decision"] in ("trusted", "low-trust"),
         "C_notrej": lambda a: a["decision"] != "rejected"}


def xapp_ann(windows, anchor):
    return X.run_xapp(RQ3.ListSource(windows), anchor, "all", binding="uebound", admission="strict")[0]


def apply_persist(ann, L_S):
    """xApp 註記版：回傳新註記 list 與每筆之連續計數"""
    if L_S is None:
        return ann, None
    out, cnt, last = [], {}, {}
    for a in ann:
        j, w = a["node"], a["window"]
        if a["S_i"] == "violated":
            c = cnt.get(j, 0) + 1 if last.get(j) == w - 1 else 1
        else:
            c = 0
        cnt[j] = c
        last[j] = w if a["S_i"] == "violated" else None
        b = dict(a)
        b["persist_count"] = c
        if a["rule_id"] == "R2_SI_ALONE" and c >= L_S:
            b.update(decision="rejected", rule_id="R2_SI_PERSIST", action="exclude", admitted=False)
        out.append(b)
    return out, None


def persist_counts_trace(tr):
    """獨立推導版：由 E11.trace 之 S_i 證據計算每 (k, node) 之連續計數"""
    cnt, prev = {}, {}
    for (k, j) in sorted(tr):
        v = tr[(k, j)]["ev"]["S_i"] == "violated"
        c = (prev.get(j, (None, 0))[1] + 1 if prev.get(j, (None, 0))[0] == k - 1 else 1) if v else 0
        cnt[(k, j)] = c
        prev[j] = (k, c) if v else (None, 0)
    return cnt


def rq3_metrics(files, L_S):
    """沿用 run_RQ3_decision_replay 之攻擊、真值、決策與准入函式；只計 uebound"""
    acc = collections.defaultdict(lambda: {"win": 0, "avail": 0, "regret": [], "regret_rel": [], "wrong": 0,
                                           "lured": 0, "lure_opportunity": 0, "ann": 0, "usable_ann": 0,
                                           "cap_base": 0.0, "cap_kept": 0.0, "opt_excluded": 0})
    for test in files:
        anchor = X.TrustAnchor([f for f in files if f != test])
        base = RQ3.load_windows(test)
        td_base = RQ3.true_delays(base)
        t0 = len(base) // 2
        cells_all = sorted({c for d in td_base for c in d})
        for atk_name, kind, param in RQ3.ATTACKS:
            for atk_cell in (cells_all if kind else [None]):
                mod = RQ3.apply_attack(base, atk_cell, kind, param, t0)
                rep = RQ3.true_delays(mod)
                ann, _ = apply_persist(xapp_ann(mod, anchor), L_S)
                idx = {w: k for k, (w, _) in enumerate(mod)}
                by_win = collections.defaultdict(dict)
                for a in ann:
                    by_win[idx[a["window"]]][a["node"]] = a
                for k in range(t0, len(base)):
                    truth = td_base[k]
                    if len(truth) < 2:
                        continue
                    opt = min(truth, key=lambda c: truth[c])
                    anns = by_win.get(k, {})
                    for consumer in RQ3.CONSUMERS:
                        a = acc[(atk_name, consumer)]
                        a["win"] += 1; a["ann"] += len(anns)
                        adm = RQ3.admitted(consumer, anns, rep[k])
                        a["usable_ann"] += len(adm)
                        a["cap_base"] += sum(RQ3.RESOURCE_INVENTORY[j] for j in rep[k])
                        a["cap_kept"] += sum(RQ3.RESOURCE_INVENTORY[j] for j in adm)
                        if opt not in adm:
                            a["opt_excluded"] += 1
                        ch = RQ3.decide(rep[k], adm)
                        if ch is None:
                            continue
                        a["avail"] += 1
                        g = truth.get(ch, np.nan) - truth[opt]
                        a["regret"].append(g)
                        if truth[opt] > 0:
                            a["regret_rel"].append(g / truth[opt])
                        if ch != opt:
                            a["wrong"] += 1
                        if atk_cell is not None and atk_cell in truth and atk_cell != opt:
                            a["lure_opportunity"] += 1
                            if ch == atk_cell:
                                a["lured"] += 1
    res = {}
    for (atk, consumer), a in acc.items():
        reg = [r for r in a["regret"] if not np.isnan(r)]
        res[f"uebound|{atk}|{consumer}"] = {
            "windows": a["win"],
            "rho": a["cap_kept"] / a["cap_base"] if a["cap_base"] else None,
            "usable_yield": a["usable_ann"] / a["ann"] if a["ann"] else None,
            "availability": a["avail"] / a["win"] if a["win"] else None,
            "regret_mean_ms": float(np.mean(reg)) if reg else None,
            "regret_p95_ms": float(np.percentile(reg, 95)) if reg else None,
            "regret_rel_mean": (float(np.mean([r for r in a["regret_rel"] if not np.isnan(r)]))
                                if a["regret_rel"] else None),
            "optimal_excluded_rate": a["opt_excluded"] / a["win"] if a["win"] else None,
            "wrong_rate": a["wrong"] / a["avail"] if a["avail"] else None,
            "lured_rate": a["lured"] / a["lure_opportunity"] if a["lure_opportunity"] else None}
    return res


def lab(L):
    return "∞" if L is None else str(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=OUT_DIR)
    args = ap.parse_args()
    files = P.find_files(None)
    seeds = [os.path.basename(f).split("seed")[-1].replace(".txt", "") for f in files]
    rt = E11.load_runtime_ann(len(seeds))

    clean = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    latency = collections.defaultdict(list)
    n_cnt = 0
    for si, (sd, f) in enumerate(zip(seeds, files)):
        anchor = X.TrustAnchor([g for g in files if g != f])
        wins = RQ3.load_windows(f)
        nk = len({i for _, c in wins for u in c.values() for i in u})
        base_ann = xapp_ann(wins, anchor)
        if [(a["window"], a["node"], a["decision"], a["rule_id"]) for a in base_ann] != \
           [(r["window"], r["node"], r["decision"], r["rule_id"]) for r in rt[si]]:
            raise SystemExit(f"✗ 檢查 1：seed {sd} xApp 乾淨註記與 runtime 不符")
        tr_cnt = persist_counts_trace(E11.trace(wins, anchor, nk))
        _, _ = apply_persist(base_ann, 2)
        x_cnt = {(a["window"], a["node"]): a["persist_count"] for a in apply_persist(base_ann, 2)[0]}
        if x_cnt != tr_cnt:
            bad = [k for k in set(x_cnt) | set(tr_cnt) if x_cnt.get(k) != tr_cnt.get(k)]
            raise SystemExit(f"✗ 檢查 2：seed {sd} 連續計數兩份實作不符 {sorted(bad)[:5]}")
        n_cnt += len(x_cnt)
        half = len(wins) // 2
        for L in L_S_LIST:
            ann, _ = apply_persist(base_ann, L)
            for a0, a in zip(base_ann, ann):
                part = "前半" if a["window"] < half else "後半"
                clean[lab(L)][sd]["n"] += 1
                if a["decision"] == "rejected" and a0["decision"] != "rejected":
                    clean[lab(L)][sd]["新增誤拒"] += 1
                    clean[lab(L)][sd][f"新增誤拒|{part}"] += 1
                for pol, fn in ADMIT.items():
                    if fn(a0) and not fn(a):
                        clean[lab(L)][sd][f"新增不准入|{pol}"] += 1
        # 攻擊下到達 rejected 之延遲（自 t0 持續至序列結束；未到達者設限）
        for sm in P.samples_of(sd, P.load_cell_delay(f)):
            for kind, prm in [("drift", r) for r in DRIFTS] + [("step", s) for s in STEPS]:
                att = copy.deepcopy(wins)
                for k in range(sm.w_on, len(att)):
                    c = att[k][1]
                    if sm.cell in c:
                        for i in c[sm.cell]:
                            c[sm.cell][i] = (c[sm.cell][i] + prm * (k - sm.w_on) * sm.mean if kind == "drift"
                                             else c[sm.cell][i] * prm)
                a_base = xapp_ann(att, anchor)
                for L in L_S_LIST:
                    ann, _ = apply_persist(a_base, L)
                    hit = next((a["window"] - sm.w_on for a in ann
                                if a["node"] == sm.cell and a["window"] >= sm.w_on and a["decision"] == "rejected"), None)
                    latency[(f"{kind}{prm}", lab(L))].append({"seed": sd, "target": sm.cell, "latency_s": hit,
                                                             "censor_s": len(wins) - 1 - sm.w_on})
        print(f"seed {sd} 完成")
    print(f"── 檢查 1：L_S=∞ xApp 乾淨註記 = runtime 註記 ✓")
    print(f"── 檢查 2：連續計數兩份實作逐筆相同 ✓（{n_cnt} 筆）")

    rq3 = {}
    old = json.load(open(os.path.join(args.out_dir, "RQ3_decision_replay.json"), encoding="utf-8"))
    for L in L_S_LIST:
        rq3[lab(L)] = rq3_metrics(files, L)
        if L is None:
            bad = [k for k, v in rq3["∞"].items() if old.get(k) != v]
            if bad:
                raise SystemExit(f"✗ 檢查 3：L_S=∞ 之 RQ3 與既有輸出不符：{bad[:4]}")
            print(f"── 檢查 3：L_S=∞ 之 RQ3（uebound，{len(rq3['∞'])} 組指標）與 RQ3_decision_replay.json 逐位相同 ✓")

    lat = {}
    for (atk, L), rows in latency.items():
        got = [r["latency_s"] for r in rows if r["latency_s"] is not None]
        lat.setdefault(atk, {})[L] = {"n": len(rows), "reached": len(got),
                                       "median_s_reached": statistics.median(got) if got else None,
                                       "rows": rows}
    out = {"spec": "docs/thesis/E11_E12_B4_spec.md v2 (E12)", "L_S": [lab(L) for L in L_S_LIST],
           "clean": {L: {sd: dict(c) for sd, c in v.items()} for L, v in clean.items()},
           "latency": lat, "rq3_uebound": rq3,
           "note": "candidate rule evaluation; adopted policy unchanged"}
    path = os.path.join(args.out_dir, "E12_persist.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)

    print("\n══ 1／3. 乾淨資料（分母 3,150）：新增誤拒（前半／後半）與新增不准入 ══")
    for L in [lab(x) for x in L_S_LIST]:
        tot = collections.Counter()
        for c in clean[L].values():
            tot.update(c)
        per = {sd: clean[L][sd].get("新增誤拒", 0) for sd in seeds}
        print(f"  L_S={L:<3} 新增誤拒 {tot['新增誤拒']}（{tot['新增誤拒'] / tot['n'] * 100:.2f}%；前半 {tot['新增誤拒|前半']}／後半 {tot['新增誤拒|後半']}；各 seed {per}）"
              f"｜新增不准入 strict {tot['新增不准入|strict']}、restrict_annotated {tot['新增不准入|restrict_annotated']}、C_notrej {tot['新增不准入|C_notrej']}")
    print("\n══ 2. 到達 rejected（受測節點；到達數／16，中位延遲秒）══")
    for atk in lat:
        print(f"  {atk:<10} " + "  ".join(f"L_S={L}: {lat[atk][L]['reached']}/{lat[atk][L]['n']}，{lat[atk][L]['median_s_reached']}"
                                        for L in [lab(x) for x in L_S_LIST]))
    print("\n══ 4. RQ3（uebound）C_notrej 之誘導率／相對 regret／決策可用 ══")
    for atk, *_ in RQ3.ATTACKS:
        row = []
        for L in [lab(x) for x in L_S_LIST]:
            m = rq3[L][f"uebound|{atk}|C_notrej"]
            lr = m["lured_rate"]
            row.append(f"L_S={L}: {'—' if lr is None else f'{lr*100:.1f}%'}／{m['regret_rel_mean']*100:.1f}%／{m['availability']*100:.1f}%")
        print(f"  {atk:<11} " + "  ".join(row))
    print(f"\n寫入 {path}")


if __name__ == "__main__":
    main()
