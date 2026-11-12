#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_E21_S1_boff.py — 規格 E21 §8.3（E21-S1 v1）：關閉 D1 單獨降級（B-off）之代價。

B-off：low-trust 且觸發規則只有 R2_D1_STRONG／R2_D1_WEAK 者改為 trusted（事後改標，等價於改 fuse，
因判定不跨窗繼承）。比較規則版與 B-off 之 MF_strict（成員關係攻擊 A1–A4、延遲攻擊 ×0.6／×0.8／漂移）
與乾淨 FB_strict。內建檢查 S1-0～S1-2，任一失敗即停。

跑法（舊機器）：
  ZT_DATASET=d30 ZT_FUSION_ORDER=severity python3 xapps/verification/residuals/run_E21_S1_boff.py
"""
import os
import sys
import json
import time
import collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run_E21_S0_membership as S0                                # noqa: E402  (含環境檢查)
from run_E21_S0_membership import X, DS, load_windows, replay, inject, stop, T0S, L, KS, ATTACKS, LTE  # noqa: E402
from run_RQ3_decision_replay import apply_attack, true_delays      # noqa: E402

SEV_DIR = S0.SEV_DIR
OUT_DIR = os.path.join(SEV_DIR, "E21_S1")
E20_JSON = os.path.join(SEV_DIR, "E20", "E20_error_rates.json")
S0_JSON = os.path.join(SEV_DIR, "E21_S0", "E21_S0_membership.json")
DELAY = [("A0_step_0.6", "step", 0.60), ("A0_step_0.8", "step", 0.80), ("A0_drift_0.01", "drift", 0.01)]
D1R = {"R2_D1_STRONG", "R2_D1_WEAK"}


def relaxed(a):
    return (a["decision"] == "low-trust" and a["rule_id"] in D1R
            and set(a.get("also_matched", [])) <= D1R)


def dec_boff(a):
    return "trusted" if relaxed(a) else a["decision"]


def main():
    t_start = time.time()
    files = DS.files()
    e20 = json.load(open(E20_JSON, encoding="utf-8"))["MF"]
    s0 = json.load(open(S0_JSON, encoding="utf-8"))["results"]

    # ---- 乾淨 ----
    clean_n = clean_rule_block = clean_boff_block = n_relabel = 0
    seeds = []
    for f in files:
        anchor = X.TrustAnchor([g for g in files if g != f])
        wins = load_windows(f)
        ann, _ = replay(wins, anchor)
        seeds.append((DS.seed_of(f), anchor, wins, ann))
        for a in ann:
            clean_n += 1
            clean_rule_block += a["decision"] != "trusted"
            clean_boff_block += dec_boff(a) != "trusted"
            n_relabel += relaxed(a)
    if n_relabel != 7316 or clean_boff_block != 408 or clean_n != 15534:
        stop(f"S1-1 改標 {n_relabel}（應 7316）、B-off 擋下 {clean_boff_block}（應 408）、筆數 {clean_n}")
    print(f"  S1-1 ✓ 改標 7,316；FB_strict 規則 {clean_rule_block / clean_n:.4f} → B-off {clean_boff_block / clean_n:.4f}")
    res = {"clean": {"n": clean_n, "FB_strict_rule": clean_rule_block / clean_n,
                     "FB_strict_boff": clean_boff_block / clean_n, "n_relabelled": n_relabel}}

    # ---- 延遲攻擊 ----
    dres = {}
    for name, kind, param in DELAY:
        c = collections.Counter()
        still = collections.Counter()
        for sd, anchor, base, _ in seeds:
            t0 = len(base) // 2
            for cell in sorted({c_ for d in true_delays(base) for c_ in d}):
                mod = apply_attack(base, cell, kind, param, t0)
                ann, _ = replay(mod, anchor)
                for a in ann:
                    k, j = a["window"], a["node"]
                    tam = (j == cell and k >= t0 and cell in mod[k][1]
                           and any(mod[k][1][cell][i] != base[k][1][cell][i] for i in mod[k][1][cell]))
                    if not tam:
                        continue
                    c["n"] += 1
                    c["rule_adm"] += a["decision"] == "trusted"
                    c["boff_adm"] += dec_boff(a) == "trusted"
                    if dec_boff(a) != "trusted":
                        still[a["rule_id"]] += 1
        mf_rule = c["rule_adm"] / c["n"]
        if mf_rule != e20[name]["MF1"]["strict"] or c["n"] != e20[name]["tampered"]:
            stop(f"S1-0 {name} 規則版 MF {mf_rule}（E20 {e20[name]['MF1']['strict']}），竄改 {c['n']}（E20 {e20[name]['tampered']}）")
        dres[name] = {"tampered": c["n"], "MF_strict_rule": mf_rule, "MF_strict_boff": c["boff_adm"] / c["n"],
                      "boff_still_blocked_by_rule": dict(still)}
        print(f"  {name:14s} 竄改 {c['n']}  MF_strict 規則 {mf_rule:.4f} → B-off {c['boff_adm'] / c['n']:.4f}")
    print("  S1-0 ✓ 規則版逐位重現 E20 MF-1 strict")
    res["delay"] = dres

    # ---- 成員關係攻擊 ----
    acc = {(a, k): collections.Counter() for a in ATTACKS for k in KS}
    stl = {(a, k): collections.Counter() for a in ATTACKS for k in KS}
    dj = {(a, k): collections.Counter() for a in ATTACKS for k in KS}
    for sd, anchor, wins, _ in seeds:
        widx = {w: t for t, (w, _) in enumerate(wins)}
        for j in sorted({c for _, cc in wins for c in cc if c != LTE}):
            for t0 in T0S:
                hi = min(t0 + L + S0.POST, len(wins))
                for k in KS:
                    for atk in ATTACKS:
                        iw, nmod = inject(wins, j, t0, k, atk)
                        if sum(nmod) == 0:
                            continue
                        ann, _ = replay(iw[:hi], anchor)
                        for a in ann:
                            if a["node"] != j:
                                continue
                            t = widx[a["window"]]
                            if not (t0 <= t < t0 + L):
                                continue
                            dj[(atk, k)][a["decision"]] += 1
                            if nmod[t - t0] == 0:
                                continue
                            g = acc[(atk, k)]
                            g["n"] += 1
                            g["rule_adm"] += a["decision"] == "trusted"
                            g["boff_adm"] += dec_boff(a) == "trusted"
                            if dec_boff(a) != "trusted":
                                stl[(atk, k)][a["rule_id"]] += 1
        print(f"  seed {sd} 完成（{time.time() - t_start:.0f} s）")
    mres = {}
    for (atk, k), g in acc.items():
        key = f"{atk}|k={k}"
        tot = sum(dj[(atk, k)].values())
        got = {d: dj[(atk, k)][d] / tot for d in X.SEVERITY}
        if got != s0[key]["j_decisions_attacked"]:
            stop(f"S1-2 {key} 判定分布 {got} ≠ S0 {s0[key]['j_decisions_attacked']}")
        mres[key] = {"tampered": g["n"], "MF_strict_rule": g["rule_adm"] / g["n"],
                     "MF_strict_boff": g["boff_adm"] / g["n"], "boff_still_blocked_by_rule": dict(stl[(atk, k)])}
        print(f"  {key:22s} 竄改 {g['n']:5d}  MF_strict 規則 {g['rule_adm'] / g['n']:.4f} → B-off {g['boff_adm'] / g['n']:.4f}  "
              f"仍擋：{dict(stl[(atk, k)].most_common(3))}")
    print("  S1-2 ✓ 規則版 j 判定分布重現 E21-S0")
    res["membership"] = mres
    os.makedirs(OUT_DIR, exist_ok=True)
    out = {"spec": "docs/thesis/E21_relaxable_component_spec.md §8.3 v1",
           "checks": {"S1-0": "pass", "S1-1": "pass", "S1-2": "pass"}, "results": res,
           "elapsed_s": round(time.time() - t_start, 1)}
    p = os.path.join(OUT_DIR, "E21_S1_boff.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"寫入 {p}（{time.time() - t_start:.0f} s）")


if __name__ == "__main__":
    main()
