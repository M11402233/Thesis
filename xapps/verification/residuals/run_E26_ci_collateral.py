#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_E26_ci_collateral.py — 規格 docs/thesis/E26_ci_collateral_spec.md v1。
C_i 連帶排除之量化（V-field）與歸因式縮小（V-cand：candidate_cells；V-D4：CU-CP 成員對帳）。
內建檢查 E26-0～E26-3（任一失敗即停，不寫輸出）。

跑法（舊機器）：
  ZT_DATASET=d30 ZT_FUSION_ORDER=severity python3 xapps/verification/residuals/run_E26_ci_collateral.py
"""
import os
import sys
import json
import time
import collections
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run_E25_cucp_membership as E25                             # noqa: E402
from run_E25_cucp_membership import X, DS, S0, load_windows, inject, stop, T0S, L, KS, LTE, d4, adm  # noqa: E402

OUT_DIR = os.path.join(S0.SEV_DIR, "E26")
S1_JSON = E25.S1_JSON
ATTACKS = ["A1_delete", "A5_inflate"]
VARIANTS = ["V-field", "V-cand", "V-D4", "V-D4s"]
CI_RULES = {"R1_CI_VETO", "R1_CI_PENDING"}
SEV = X.SEVERITY


def inflate(wins, j, t0, k):
    out, nmod = list(wins), []
    for t in range(t0, min(t0 + L, len(wins))):
        w, cells = wins[t]
        if j not in cells:
            nmod.append(0)
            continue
        c2 = {c: dict(u) for c, u in cells.items()}
        m = float(np.mean(list(cells[j].values())))
        for f in range(9001, 9001 + k):
            c2[j][f] = m
        out[t] = (w, c2)
        nmod.append(k)
    return out, nmod


def without_ci(a):
    """自符合集合 M 移除 R1_CI_* 後依嚴重度序重選；回傳判定"""
    m = [r for r in [a["rule_id"]] + list(a.get("also_matched", [])) if r not in CI_RULES and r != "R0_CLEAN"]
    if not m:
        return "trusted"
    rid = min(m, key=lambda r: (-SEV[X.RULE[r][0]], X._RULE_ORDER[r]))
    return X.RULE[rid][0]


def main():
    t_start = time.time()
    files = DS.files()
    ref = [json.loads(l) for l in open(S0.REF_ANN, encoding="utf-8")]
    s1 = json.load(open(S1_JSON, encoding="utf-8"))["results"]
    seeds, pos = [], 0
    for f in files:
        sd = DS.seed_of(f)
        anchor = X.TrustAnchor([g for g in files if g != f])
        wins = load_windows(f)
        maps = E25.load_cucp(os.path.dirname(DS.aux_path(sd, "x")), len(wins))
        off = E25.run(wins, anchor, False)
        seg = ref[pos:pos + len(off)]
        pos += len(off)
        if len(seg) != len(off) or any(json.loads(json.dumps(x, ensure_ascii=False)) != r for x, r in zip(off, seg)):
            stop(f"E26-0 seed {sd}：乾淨回放與註記檔不同")
        if any(without_ci(a) != a["decision"] for a in off):
            stop(f"E26-3 seed {sd}：重選函式於乾淨註記不等於原判定")
        if any(any(d4(cl, maps[t], cc)) for t, (w, cl) in enumerate(wins) for cc in maps[t]):
            stop(f"E26-4 seed {sd}：乾淨資料對全部 cell（含沉默者）之 D4 觸發 ≠ 0")
        seeds.append((sd, anchor, wins, maps, {(a["window"], a["node"]): a["decision"] for a in off}))
    if pos != len(ref):
        stop(f"E26-0 總筆數 {pos} ≠ {len(ref)}")
    print("  E26-0 ✓  E26-3 ✓  E26-4 ✓")

    res = {}
    for atk in ATTACKS:
        for k in KS:
            c = collections.Counter()
            for sd, anchor, wins, maps, clean in seeds:
                for j in sorted({cc for _, cl in wins for cc in cl if cc != LTE}):
                    for t0 in T0S:
                        hi = min(t0 + L + S0.POST, len(wins))
                        iw, nmod = inject(wins, j, t0, k, atk) if atk == "A1_delete" else inflate(wins, j, t0, k)
                        if sum(nmod) == 0:
                            continue
                        ann = E25.run(iw[:hi], anchor, False)
                        cellmap = {w: cl for w, cl in iw[:hi]}
                        c["episodes"] += 1
                        byw = collections.defaultdict(list)
                        for a in ann:
                            byw[a["window"]].append(a)
                        for t, row in byw.items():
                            inj = t0 <= t < t0 + L and nmod[t - t0] > 0
                            if not inj:
                                for a in row:
                                    if a["node"] != j:
                                        c["outside_n"] += 1
                                        c["outside_diff"] += a["decision"] != clean[(t, a["node"])]
                                continue
                            if any(a["C_i"] != "violated" for a in row):
                                stop(f"E26-2 {atk} k={k} seed {sd} j={j} 窗 {t}：注入窗之 C_i 非 violated")
                            cand = set(row[0]["evidence"].get("C_i", {}).get("candidate_cells", []))
                            d4v = {a["node"] for a in row if any(d4(cellmap[t], maps[t], a["node"]))}
                            d4s = {cc for cc in maps[t] if any(d4(cellmap[t], maps[t], cc))}     # v1.1：含沉默之 cell
                            for a in row:
                                node = a["node"]
                                dec = {"V-field": a["decision"],
                                       "V-cand": a["decision"] if (not cand or node in cand) else without_ci(a),
                                       "V-D4": a["decision"] if (not d4v or node in d4v) else without_ci(a),
                                       "V-D4s": a["decision"] if (not d4s or node in d4s) else without_ci(a)}
                                if node == j:
                                    c["tam"] += 1
                                    for v in VARIANTS:
                                        if SEV[dec[v]] < SEV[dec["V-field"]]:
                                            stop(f"E26-2 {atk} k={k}：{v} 下 j 之判定較 V-field 寬鬆（seed {sd} j={j} 窗 {t}）")
                                        c[f"{v}_j_strict"] += adm(dec[v], "strict")
                                        c[f"{v}_j_restrict"] += adm(dec[v], "restrict_annotated")
                                    continue
                                cl = clean[(t, node)]
                                c["honest"] += 1
                                c["clean_strict"] += adm(cl, "strict")
                                c["clean_restrict"] += adm(cl, "restrict_annotated")
                                for v in VARIANTS:
                                    c[f"{v}_strict"] += adm(dec[v], "strict")
                                    c[f"{v}_restrict"] += adm(dec[v], "restrict_annotated")
                                    c[f"{v}_to_rejected"] += dec[v] == "rejected" and cl != "rejected"
                                    c[f"{v}_to_lowtrust"] += dec[v] == "low-trust" and cl == "trusted"
                                    c[f"{v}_differs_from_clean"] += dec[v] != cl
            key = f"{atk}|k={k}"
            if atk == "A1_delete" and c["tam"] != s1["membership"][key]["tampered"]:
                stop(f"E26-1 {key}：竄改 {c['tam']} ≠ E21-S1 {s1['membership'][key]['tampered']}")
            h, n = c["honest"], c["tam"]
            r = {"episodes": c["episodes"], "tampered": n, "honest": h,
                 "clean_adm_strict": c["clean_strict"] / h, "clean_adm_restrict": c["clean_restrict"] / h,
                 "outside": {"n": c["outside_n"], "differs_from_clean": c["outside_diff"]}}
            for v in VARIANTS:
                r[v] = {"adm_strict": c[f"{v}_strict"] / h, "adm_restrict": c[f"{v}_restrict"] / h,
                        "collateral_strict": (c["clean_strict"] - c[f"{v}_strict"]) / h,
                        "collateral_restrict": (c["clean_restrict"] - c[f"{v}_restrict"]) / h,
                        "to_rejected": c[f"{v}_to_rejected"], "to_lowtrust": c[f"{v}_to_lowtrust"],
                        "differs_from_clean": c[f"{v}_differs_from_clean"],
                        "honest_excluded_per_tampered_restrict": (c["clean_restrict"] - c[f"{v}_restrict"]) / n,
                        "MF_j_strict": c[f"{v}_j_strict"] / n, "MF_j_restrict": c[f"{v}_j_restrict"] / n}
            res[key] = r
            print(f"  {key:16s} 竄改 {n:5d}  誠實 (節點, 窗) {h:6d}  乾淨准入 strict {r['clean_adm_strict']:.3f}／restrict {r['clean_adm_restrict']:.3f}"
                  f"  區間外與乾淨不同 {c['outside_diff']}／{c['outside_n']}")
            for v in VARIANTS:
                x = r[v]
                print(f"      {v:8s} 准入 strict {x['adm_strict']:.3f}／restrict {x['adm_restrict']:.3f}  連帶排除 strict {x['collateral_strict']:.3f}／restrict {x['collateral_restrict']:.3f}"
                      f"  →rejected {x['to_rejected']}  每筆竄改連帶 {x['honest_excluded_per_tampered_restrict']:.2f}  j 之 MF strict {x['MF_j_strict']:.3f}／restrict {x['MF_j_restrict']:.3f}", flush=True)
    print("  E26-1 ✓  E26-2 ✓")
    os.makedirs(OUT_DIR, exist_ok=True)
    p = os.path.join(OUT_DIR, "E26_ci_collateral.json")
    json.dump({"spec": "docs/thesis/E26_ci_collateral_spec.md v1.1",
               "checks": {"E26-0": "pass", "E26-1": "pass", "E26-2": "pass", "E26-3": "pass", "E26-4": "pass"},
               "results": res, "elapsed_s": round(time.time() - t_start, 1)},
              open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"寫入 {p}（{time.time() - t_start:.0f} s）")


if __name__ == "__main__":
    main()
