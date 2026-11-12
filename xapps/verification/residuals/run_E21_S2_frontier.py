#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_E21_S2_frontier.py — 規格 E21 §8.5（E21-S2 v1）：規則版與 B-off 之間之折衷點是否優於隨機對角線。

可放寬集合 R（同 E21-S1）內以 Z_D1 族（D1 z ≥ t 才擋）與 Z_S 族（S_i 殘差 z ≥ s 才擋）決定擋或放；
對角線為兩端點之線性組合（隨機擋 p，期望值精確）。探索性、事後訂定（規格已揭露）。
內建檢查 S2-0～S2-2。

跑法（舊機器）：
  ZT_DATASET=d30 ZT_FUSION_ORDER=severity python3 xapps/verification/residuals/run_E21_S2_frontier.py
"""
import os
import sys
import json
import time
import collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run_E21_S0_membership as S0                                # noqa: E402
from run_E21_S0_membership import X, DS, load_windows, replay, inject, stop, T0S, L, LTE  # noqa: E402
from run_E21_S1_boff import relaxed                               # noqa: E402
from run_RQ3_decision_replay import apply_attack, true_delays      # noqa: E402

SEV_DIR = S0.SEV_DIR
OUT_DIR = os.path.join(SEV_DIR, "E21_S2")
S1_JSON = os.path.join(SEV_DIR, "E21_S1", "E21_S1_boff.json")
DELAY = [("A0_step_0.6", "step", 0.60), ("A0_drift_0.01", "drift", 0.01), ("A0_step_0.8", "step", 0.80)]
MEMB = [("A3_claim_anchor", 1), ("A3_claim_anchor", 3), ("A2_swap", 1), ("A4_claim_peer", 1)]
MAIN = ["A0_step_0.6", "A0_drift_0.01", "A3_claim_anchor|k=1", "A3_claim_anchor|k=3"]
T_D1 = [2, 3, 4, 6, 8, 12, 16, 24]
S_SI = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5]


def rec(sd, a):
    """(seed, 規則版是否 trusted, 是否屬 R, z_S, z_D1)"""
    r = relaxed(a)
    zs = a.get("z_S")
    zd = (a.get("evidence", {}).get("D1") or {}).get("z")
    if r and (zs is None or zd is None):
        stop(f"S2-2 R 內缺 z_S 或 D1 z：{a['window']} {a['node']}")
    return (sd, a["decision"] == "trusted", r, zs, zd)


def rates(records, block):
    """回傳 (非 trusted 比例)；block(zs, zd) 決定 R 內是否擋"""
    n = len(records)
    nt = sum(1 for _, tr, r, zs, zd in records if (not tr) and (not r or block(zs, zd)))
    return nt / n


def adm_rate(records, block):
    """准入（trusted）比例，與 E21-S1 相同之算式：准入筆數 ÷ 總筆數"""
    n = len(records)
    adm = sum(1 for _, tr, r, zs, zd in records if tr or (r and not block(zs, zd)))
    return adm / n


def main():
    t_start = time.time()
    files = DS.files()
    s1 = json.load(open(S1_JSON, encoding="utf-8"))["results"]
    clean, tam = [], collections.defaultdict(list)
    for f in files:
        sd = DS.seed_of(f)
        anchor = X.TrustAnchor([g for g in files if g != f])
        base = load_windows(f)
        ann, _ = replay(base, anchor)
        clean += [rec(sd, a) for a in ann]
        t0 = len(base) // 2
        cells = sorted({c for d in true_delays(base) for c in d})
        for name, kind, param in DELAY:
            for cell in cells:
                mod = apply_attack(base, cell, kind, param, t0)
                for a in replay(mod, anchor)[0]:
                    k, j = a["window"], a["node"]
                    if (j == cell and k >= t0 and cell in mod[k][1]
                            and any(mod[k][1][cell][i] != base[k][1][cell][i] for i in mod[k][1][cell])):
                        tam[name].append(rec(sd, a))
        widx = {w: t for t, (w, _) in enumerate(base)}
        for j in sorted({c for _, cc in base for c in cc if c != LTE}):
            for t0m in T0S:
                hi = min(t0m + L + S0.POST, len(base))
                for atk, k in MEMB:
                    iw, nmod = inject(base, j, t0m, k, atk)
                    if sum(nmod) == 0:
                        continue
                    for a in replay(iw[:hi], anchor)[0]:
                        t = widx[a["window"]]
                        if a["node"] == j and t0m <= t < t0m + L and nmod[t - t0m] > 0:
                            tam[f"{atk}|k={k}"].append(rec(sd, a))
        print(f"  seed {sd} 完成（{time.time() - t_start:.0f} s）")

    never, always = (lambda zs, zd: False), (lambda zs, zd: True)
    nR = sum(r for _, _, r, _, _ in clean)
    if nR != 7316:
        stop(f"S2-1 乾淨 R 筆數 {nR} ≠ 7316")
    fb1, fb0 = rates(clean, always), rates(clean, never)
    if abs(fb1 - s1["clean"]["FB_strict_rule"]) > 0 or abs(fb0 - s1["clean"]["FB_strict_boff"]) > 0:
        stop(f"S2-0 乾淨端點 {fb1},{fb0} ≠ S1")
    for name, rs in tam.items():
        sec = s1["delay"].get(name) or s1["membership"].get(name)
        m1, m0 = adm_rate(rs, always), adm_rate(rs, never)
        if m1 != sec["MF_strict_rule"] or m0 != sec["MF_strict_boff"] or len(rs) != sec["tampered"]:
            stop(f"S2-0 {name} 端點 ({m1},{m0},{len(rs)}) ≠ S1 ({sec['MF_strict_rule']},{sec['MF_strict_boff']},{sec['tampered']})")
    print("  S2-0 ✓ 端點逐位重現 E21-S1；S2-1 ✓ R = 7,316；S2-2 ✓")

    fams = ([("Z_D1", t, (lambda t: lambda zs, zd: zd >= t)(t)) for t in T_D1]
            + [("Z_S", s, (lambda s: lambda zs, zd: zs >= s)(s)) for s in S_SI])
    seeds = sorted({r[0] for r in clean})

    def point(cl, tm, blk):
        fb, mf = rates(cl, blk), adm_rate(tm, blk)
        f1, f0 = rates(cl, always), rates(cl, never)
        m1, m0 = adm_rate(tm, always), adm_rate(tm, never)
        p = (fb - f0) / (f1 - f0) if f1 != f0 else 0.0
        return fb, mf, (m0 + p * (m1 - m0)) - mf

    res = {}
    for name, rs in tam.items():
        pts = []
        for fam, th, blk in fams:
            fb, mf, gap = point(clean, rs, blk)
            npos = 0
            for sd in seeds:
                cs = [r for r in clean if r[0] == sd]
                ts = [r for r in rs if r[0] == sd]
                if ts and point(cs, ts, blk)[2] > 0:
                    npos += 1
            pts.append({"family": fam, "threshold": th, "FB_strict": fb, "MF_strict": mf, "gap": gap,
                        "n_seeds_gap_pos": npos})
        sig = any(p["gap"] > 0 and p["n_seeds_gap_pos"] >= 7 for p in pts)
        res[name] = {"main": name in MAIN, "endpoints": {"rule": [fb1, adm_rate(rs, always)],
                                                          "boff": [fb0, adm_rate(rs, never)]},
                     "points": pts, "learnable_signal": sig}
        best = max(pts, key=lambda p: p["gap"])
        print(f"  {name:22s} {'主' if name in MAIN else '對照'}  可學訊號 {'有' if sig else '無'}  "
              f"最佳 {best['family']}≥{best['threshold']}: FB {best['FB_strict']:.3f} MF {best['MF_strict']:.3f} "
              f"gap {best['gap']:+.3f}（{best['n_seeds_gap_pos']}/8 seed）")
        for p in pts:
            print(f"      {p['family']:4s} ≥{p['threshold']:<5} FB {p['FB_strict']:.3f}  MF {p['MF_strict']:.3f}  gap {p['gap']:+.4f}  seeds {p['n_seeds_gap_pos']}/8")
    os.makedirs(OUT_DIR, exist_ok=True)
    out = {"spec": "docs/thesis/E21_relaxable_component_spec.md §8.5 v1（探索性、事後訂定）",
           "checks": {"S2-0": "pass", "S2-1": "pass", "S2-2": "pass"},
           "clean_endpoints": {"FB_rule": fb1, "FB_boff": fb0}, "results": res,
           "elapsed_s": round(time.time() - t_start, 1)}
    p = os.path.join(OUT_DIR, "E21_S2_frontier.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"寫入 {p}（{time.time() - t_start:.0f} s）")


if __name__ == "__main__":
    main()
