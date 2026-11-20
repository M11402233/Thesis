#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_E21_S0_membership.py — 規格 E21 §8.1（E21-S0 v1）：只改自身報表之成員關係攻擊對 D1 證據之影響。

被攻陷節點 j 只改自己的報表（A1 刪除／A2 k-for-k 替換／A3 宣稱錨點 UE／A4 宣稱 peer 之 UE），
錨點與其他節點逐位不變。以現行 zt_kpm_xapp.run_xapp（uebound、severity、strict）重放，
逐窗紀錄 zt_kpm_xapp.d1_ue_levels 之輸出（包裝後呼叫原函式，不改判定）。

主預測 P1：所有 episode 之 UE 層級 D1 證據事件數不增加（ΔUE ≤ 0）。
內建檢查 S0-0～S0-2（任一失敗即停，不寫輸出）。

跑法（舊機器）：
  ZT_DATASET=d30 ZT_FUSION_ORDER=severity python3 xapps/verification/residuals/run_E21_S0_membership.py
"""
import os
import sys
import json
import time
import collections
import numpy as np
import interval_source as _IS                    # 第二階段：延遲缺值（None）輔助


if os.environ.get("ZT_DATASET") not in ("d30", "d30p") or os.environ.get("ZT_FUSION_ORDER") != "severity":
    raise SystemExit("E21-S0 須在 ZT_DATASET=d30 與 ZT_FUSION_ORDER=severity 下執行")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import zt_kpm_xapp as X                                          # noqa: E402
import datasets as DS                                             # noqa: E402
from run_E10_D1_policy_ablation import load_windows               # noqa: E402
from run_RQ3_decision_replay import ListSource                    # noqa: E402

X.FUSION_MODE = "bound"
assert X.FUSION_ORDER == "severity" and X.D1_BINDING == "uebound"

REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SEV_DIR = (DS.results_dir() if DS.NAME == "d30p"            # 第二階段：參照＝同資料集之 severity xApp 輸出（步 4）
           else os.path.join(REPO, "data", "results", "d30_fusion_order", "severity"))
REF_ANN = os.path.join(SEV_DIR, "xapp_trust_annotations_bound_all_uebound_strict_severity.jsonl")
OUT_DIR = os.path.join(SEV_DIR, "E21_S0")

T0S = [50, 100, 150, 200, 250]
L = 10
POST = 10
KS = [1, 3]
ATTACKS = ["A1_delete", "A2_swap", "A3_claim_anchor", "A4_claim_peer"]
LTE = X.LTE_CELL
D1_ON = ("strong", "weak")

_ORIG_LEVELS = X.d1_ue_levels
LEV = []


def _recording_levels(dwell_runs, anchor):
    out = _ORIG_LEVELS(dwell_runs, anchor)
    LEV.append({i: v[0] for i, v in out.items()})
    return out


X.d1_ue_levels = _recording_levels


def stop(msg):
    print(f"\n✗ 檢查失敗：{msg}\n停止，不寫輸出（硬性規則 5）。")
    sys.exit(2)


def replay(wins, anchor):
    LEV.clear()
    ann = X.run_xapp(ListSource(wins), anchor, "all", binding="uebound", admission="strict")[0]
    if len(LEV) != len(wins):
        stop(f"d1_ue_levels 紀錄數 {len(LEV)} ≠ 窗數 {len(wins)}")
    return ann, list(LEV)


def inject(wins, j, t0, k, atk):
    """回傳 (注入後之窗序列, 每窗實際修改筆數)；只改 cell j，只在 [t0, t0+L)"""
    out = list(wins)
    prev, nmod = [], []
    fake = list(range(9001, 9001 + k))
    for t in range(t0, min(t0 + L, len(wins))):
        w, cells = wins[t]
        c2 = {c: dict(u) for c, u in cells.items()}
        if j not in c2:
            nmod.append(0); out[t] = (w, c2); prev = []; continue
        mine = c2[j]
        if atk in ("A1_delete", "A2_swap"):
            elig = set(mine)
        elif atk == "A3_claim_anchor":
            elig = {i for i in c2.get(LTE, {}) if not any(i in c2[c] for c in c2 if c != LTE)}
        else:
            elig = {i for c in c2 if c not in (LTE, j) for i in c2[c]} - set(mine)
        sel = [i for i in prev if i in elig][:k]
        for i in sorted(elig):
            if len(sel) >= k:
                break
            if i not in sel:
                sel.append(i)
        if atk in ("A1_delete", "A2_swap"):
            removed = [mine.pop(i) for i in sel]
            if atk == "A2_swap":
                for f, d in zip(fake, removed):
                    mine[f] = d
            if not mine:
                del c2[j]
        else:
            m = float(np.mean(_IS.valid_vals(cells[j])))
            for i in sel:
                mine[i] = m
        prev = sel
        nmod.append(len(sel))
        out[t] = (w, c2)
    return out, nmod


def check_s01(clean, inj, j, t0):
    for t, (a, b) in enumerate(zip(clean, inj)):
        if a[0] != b[0]:
            return f"窗 id 不同 t={t}"
        ca, cb = a[1], b[1]
        if not (t0 <= t < t0 + L):
            if b is not a and {c: dict(u) for c, u in ca.items()} != {c: dict(u) for c, u in cb.items()}:
                return f"攻擊區間外之窗被修改 t={t}"
            continue
        for c in set(ca) | set(cb):
            if c == j:
                continue
            if dict(ca.get(c, {})) != dict(cb.get(c, {})):
                return f"非 j 之 cell {c} 被修改 t={t}"
    return None


def main():
    t_start = time.time()
    files = DS.files()
    if len(files) != 8:
        stop(f"seed 數 {len(files)} ≠ 8")
    ref = [json.loads(l) for l in open(REF_ANN, encoding="utf-8")]

    print("── S0-0 乾淨重放 ──")
    seeds = []
    pos = 0
    for f in files:
        anchor = X.TrustAnchor([g for g in files if g != f])
        wins = load_windows(f)
        ann, lev = replay(wins, anchor)
        seg = ref[pos:pos + len(ann)]
        pos += len(ann)
        n_mis = sum(json.loads(json.dumps(a, ensure_ascii=False)) != r for a, r in zip(ann, seg))
        if len(seg) != len(ann) or n_mis:
            stop(f"S0-0 seed {DS.seed_of(f)} 與註記檔不同（{n_mis} 筆；長度 {len(ann)} vs {len(seg)}）")
        seeds.append((DS.seed_of(f), f, anchor, wins, ann, lev))
        print(f"  seed {DS.seed_of(f)}: {len(ann)} 筆 ✓")
    if pos != len(ref):
        stop(f"S0-0 總筆數 {pos} ≠ 註記檔 {len(ref)}")
    print(f"  S0-0 ✓ 共 {pos} 筆與註記檔逐筆相同")

    agg = {(a, k): collections.defaultdict(list) for a in ATTACKS for k in KS}
    p1_viol = []
    excluded = collections.Counter()
    n_ep = 0
    first_ep = None
    for sd, f, anchor, wins, cann, clev in seeds:
        widx = {w: t for t, (w, _) in enumerate(wins)}
        cells_all = sorted({c for _, cc in wins for c in cc if c != LTE})
        for j in cells_all:
            for t0 in T0S:
                hi = min(t0 + L + POST, len(wins))
                for k in KS:
                    for atk in ATTACKS:
                        iw, nmod = inject(wins, j, t0, k, atk)
                        if sum(nmod) == 0:
                            excluded[(atk, k)] += 1
                            continue
                        err = check_s01(wins, iw, j, t0)
                        if err:
                            stop(f"S0-1 seed {sd} j={j} t0={t0} {atk} k={k}：{err}")
                        aann, alev = replay(iw[:hi], anchor)
                        if first_ep is None:
                            first_ep = (sd, j, t0, k, atk, anchor, iw[:hi], aann, alev)
                        n_ep += 1
                        rng = range(t0, hi)
                        ue_c = sum(len(clev[t]) for t in rng)
                        ue_a = sum(len(alev[t]) for t in rng)
                        wl_c = sum(sum(clev[t].values()) for t in rng)
                        wl_a = sum(sum(alev[t].values()) for t in rng)

                        def in_rng(a, lo=t0, up=hi):
                            return lo <= widx[a["window"]] < up
                        cA = [a for a in cann if in_rng(a)]
                        aA = [a for a in aann if in_rng(a)]
                        dj = (sum(a["node"] == j and a["H_i_D1"] in D1_ON for a in aA)
                              - sum(a["node"] == j and a["H_i_D1"] in D1_ON for a in cA))
                        do = (sum(a["node"] != j and a["H_i_D1"] in D1_ON for a in aA)
                              - sum(a["node"] != j and a["H_i_D1"] in D1_ON for a in cA))
                        atk_ann = [a for a in aann if in_rng(a, t0, t0 + L)]
                        cln_ann = [a for a in cann if in_rng(a, t0, t0 + L)]
                        perwin = {}
                        for a in atk_ann:
                            perwin[a["window"]] = (a["C_i"], a["H_i_D2"])
                        g = agg[(atk, k)]
                        g["dUE"].append(ue_a - ue_c)
                        g["dWL"].append(wl_a - wl_c)
                        g["dJ"].append(dj)
                        g["dOthers"].append(do)
                        g["nmod"].append(sum(nmod))
                        g["ci_viol"].append(sum(v[0] == "violated" for v in perwin.values()))
                        g["d2_viol"].append(sum(v[1] == "violated" for v in perwin.values()))
                        g["n_win"].append(len(perwin))
                        g["dec_att"] += [a["decision"] for a in atk_ann if a["node"] == j]
                        g["dec_cln"] += [a["decision"] for a in cln_ann if a["node"] == j]
                        if ue_a > ue_c:
                            p1_viol.append({"seed": sd, "j": j, "t0": t0, "k": k, "attack": atk,
                                            "dUE": ue_a - ue_c, "nmod": nmod})
        print(f"  seed {sd} 完成（累計 episode {n_ep}，{time.time() - t_start:.0f} s）")

    # S0-2
    sd, j, t0, k, atk, anchor, iw, aann, alev = first_ep
    b_ann, b_lev = replay(iw, anchor)
    if json.dumps(b_ann, sort_keys=True, default=str) != json.dumps(aann, sort_keys=True, default=str) or b_lev != alev:
        stop("S0-2 同一 episode 重跑結果不同")
    print(f"  S0-2 ✓ episode (seed {sd}, j={j}, t0={t0}, k={k}, {atk}) 重跑逐位相同")

    def summ(v):
        v = np.array(v)
        return {"n": int(len(v)), "sum": int(v.sum()), "mean": float(v.mean()), "min": int(v.min()),
                "max": int(v.max()), "n_pos": int((v > 0).sum()), "n_neg": int((v < 0).sum())}

    res = {}
    print("\n── 結果（每列：攻擊 × k）──")
    for (atk, k), g in agg.items():
        if not g["dUE"]:
            continue
        nwin = sum(g["n_win"])
        dc_a, dc_c = collections.Counter(g["dec_att"]), collections.Counter(g["dec_cln"])
        na, nc = max(len(g["dec_att"]), 1), max(len(g["dec_cln"]), 1)
        r = {"n_episodes": len(g["dUE"]), "n_excluded_zero_mod": excluded[(atk, k)],
             "n_modified_total": int(sum(g["nmod"])),
             "dUE": summ(g["dUE"]), "dUE_level_weighted": summ(g["dWL"]),
             "dJ_node_D1": summ(g["dJ"]), "dOthers_node_D1": summ(g["dOthers"]),
             "ci_violated_share_attack_windows": sum(g["ci_viol"]) / nwin if nwin else None,
             "d2_violated_share_attack_windows": sum(g["d2_viol"]) / nwin if nwin else None,
             "j_decisions_attacked": {d: dc_a[d] / na for d in X.SEVERITY},
             "j_decisions_clean": {d: dc_c[d] / nc for d in X.SEVERITY},
             "j_strict_admitted_attacked": dc_a["trusted"] / na,
             "j_strict_admitted_clean": dc_c["trusted"] / nc}
        res[f"{atk}|k={k}"] = r
        print(f"  {atk:16s} k={k}  ep={r['n_episodes']:4d}  ΔUE sum={r['dUE']['sum']:6d} max={r['dUE']['max']:3d} "
              f"(>0: {r['dUE']['n_pos']})  Δj sum={r['dJ_node_D1']['sum']:5d} (>0: {r['dJ_node_D1']['n_pos']})  "
              f"Δothers sum={r['dOthers_node_D1']['sum']:5d}  C_i viol {r['ci_violated_share_attack_windows']:.3f}  "
              f"D2 viol {r['d2_violated_share_attack_windows']:.3f}  j trusted {r['j_strict_admitted_clean']:.3f}→{r['j_strict_admitted_attacked']:.3f}")
    p1 = not p1_viol
    print(f"\n主預測 P1（所有 episode ΔUE ≤ 0）：{'成立' if p1 else '不成立'}；違反 episode {len(p1_viol)}")
    for v in p1_viol[:10]:
        print("   ", v)
    os.makedirs(OUT_DIR, exist_ok=True)
    out = {"spec": "docs/thesis/E21_relaxable_component_spec.md §8.1 v1",
           "settings": {"T0S": T0S, "L": L, "POST": POST, "KS": KS, "attacks": ATTACKS,
                        "dataset": "d30", "fusion_order": "severity", "binding": "uebound", "admission": "strict",
                        "trust_anchor": "LOSO (other 7 seeds)"},
           "checks": {"S0-0": "pass", "S0-1": "pass", "S0-2": "pass"},
           "P1_holds": p1, "P1_violations": p1_viol, "results": res,
           "elapsed_s": round(time.time() - t_start, 1)}
    p = os.path.join(OUT_DIR, "E21_S0_membership.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"寫入 {p}（{time.time() - t_start:.0f} s）")


if __name__ == "__main__":
    main()
