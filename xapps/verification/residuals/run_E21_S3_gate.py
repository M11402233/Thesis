#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_E21_S3_gate.py — 規格 E21 §8.7（E21-S3 v1.1）：低於門檻之 S_i 殘差是否需要 D1 閘門。

Gated(s)：R（D1 單獨觸發之 low-trust）內 z_S ≥ s 才擋（= E21-S2 之 Z_S 族）。
Global(s)：B-off 下判為 trusted 之任一 (節點, 窗)，z_S ≥ s 即擋。
同一 FB 下比較 MF（Global 曲線線性內插）。探索性、事後訂定。內建檢查 S3-0、S3-1。

跑法（舊機器）：
  ZT_DATASET=d30 ZT_FUSION_ORDER=severity python3 xapps/verification/residuals/run_E21_S3_gate.py
"""
import os
import sys
import json
import time
import collections
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run_E21_S0_membership as S0                                # noqa: E402
from run_E21_S0_membership import X, DS, load_windows, replay, inject, stop, T0S, L, LTE  # noqa: E402
from run_E21_S2_frontier import rec, DELAY, MEMB, MAIN, S_SI       # noqa: E402
from run_RQ3_decision_replay import apply_attack, true_delays      # noqa: E402

SEV_DIR = S0.SEV_DIR
OUT_DIR = os.path.join(SEV_DIR, "E21_S3")
S1_JSON = os.path.join(SEV_DIR, "E21_S1", "E21_S1_boff.json")
S2_JSON = os.path.join(SEV_DIR, "E21_S2", "E21_S2_frontier.json")
S_GLOBAL = S_SI + [float("inf")]      # v1.1：端點 = B-off（s = ∞）


def blocked_gated(r, s):
    _, tr, inR, zs, _ = r
    return (not tr) and ((not inR) or zs >= s)


def blocked_global(r, s):
    _, tr, inR, zs, _ = r
    trusted_boff = tr or inR
    if s == float("inf"):
        return not trusted_boff
    return (not trusted_boff) or (zs is not None and zs >= s)


def fb_mf(cl, tm, fn, s):
    fb = sum(1 for r in cl if fn(r, s)) / len(cl)
    mf = sum(1 for r in tm if not fn(r, s)) / len(tm)
    return fb, mf


def collect(files):
    clean, tam = [], collections.defaultdict(list)
    t_start = time.time()
    for f in files:
        sd = DS.seed_of(f)
        anchor = X.TrustAnchor([g for g in files if g != f])
        base = load_windows(f)
        clean += [rec(sd, a) for a in replay(base, anchor)[0]]
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
    return clean, tam


def compare(cl, tm):
    """回傳 Gated 各點之 (s, FB, MF_gated, MF_global_interp 或 None, Δ 或 None) 與 Global 曲線"""
    glob = sorted((fb_mf(cl, tm, blocked_global, s) + (s,) for s in S_GLOBAL), key=lambda x: x[0])
    gfb = np.array([g[0] for g in glob]); gmf = np.array([g[1] for g in glob])
    out = []
    for s in S_SI:
        fb, mf = fb_mf(cl, tm, blocked_gated, s)
        if gfb.min() <= fb <= gfb.max():
            mg = float(np.interp(fb, gfb, gmf))
            out.append((s, fb, mf, mg, mg - mf))
        else:
            out.append((s, fb, mf, None, None))
    return out, glob


def main():
    t_start = time.time()
    files = DS.files()
    s1 = json.load(open(S1_JSON, encoding="utf-8"))["results"]
    s2 = json.load(open(S2_JSON, encoding="utf-8"))["results"]
    clean, tam = collect(files)

    for name, rs in tam.items():
        ref = {p["threshold"]: p for p in s2[name]["points"] if p["family"] == "Z_S"}
        for s in S_SI:
            fb, mf = fb_mf(clean, rs, blocked_gated, s)
            if fb != ref[s]["FB_strict"] or mf != ref[s]["MF_strict"]:
                stop(f"S3-0 {name} s={s}：({fb},{mf}) ≠ S2 ({ref[s]['FB_strict']},{ref[s]['MF_strict']})")
        fb, mf = fb_mf(clean, rs, blocked_global, float("inf"))
        sec = s1["delay"].get(name) or s1["membership"].get(name)
        if fb != s1["clean"]["FB_strict_boff"] or mf != sec["MF_strict_boff"]:
            stop(f"S3-1 {name} Global(∞)：({fb},{mf}) ≠ B-off ({s1['clean']['FB_strict_boff']},{sec['MF_strict_boff']})")
    print("  S3-0 ✓ Gated 逐位重現 E21-S2；S3-1 ✓ Global(∞) = B-off")

    seeds = sorted({r[0] for r in clean})
    res = {}
    for name, rs in tam.items():
        pts, glob = compare(clean, rs)
        per_seed = collections.Counter()
        n_cmp_seed = collections.Counter()
        for sd in seeds:
            cs = [r for r in clean if r[0] == sd]
            ts = [r for r in rs if r[0] == sd]
            if not ts:
                continue
            for s, fb, mf, mg, d in compare(cs, ts)[0]:
                if d is not None:
                    n_cmp_seed[s] += 1
                    per_seed[s] += d > 0
        cmp_pts = [p for p in pts if p[4] is not None]
        if cmp_pts and all(p[4] <= 0 for p in cmp_pts):
            verdict = "閘門不需要"
        elif any(p[4] > 0 and per_seed[p[0]] >= 7 for p in cmp_pts):
            verdict = "閘門有幫助"
        else:
            verdict = "不確定"
        res[name] = {"main": name in MAIN, "verdict": verdict,
                     "global_curve": [{"s": (g[2] if g[2] != float("inf") else "inf"), "FB_strict": g[0], "MF_strict": g[1]} for g in glob],
                     "gated_points": [{"s": s, "FB_strict": fb, "MF_gated": mf, "MF_global_interp": mg, "delta": d,
                                       "n_seeds_delta_pos": per_seed[s], "n_seeds_comparable": n_cmp_seed[s]}
                                      for s, fb, mf, mg, d in pts]}
        print(f"\n  {name:22s} {'主' if name in MAIN else '對照'}  → {verdict}")
        print("    Global：" + "  ".join(f"s{g[2]}: FB {g[0]:.3f} MF {g[1]:.3f}" for g in glob))
        for s, fb, mf, mg, d in pts:
            print(f"    Gated s≥{s}: FB {fb:.3f}  MF {mf:.3f}  Global@FB {('%.3f' % mg) if mg is not None else 'n/a'}  "
                  f"Δ {('%+.4f' % d) if d is not None else 'n/a'}  seeds Δ>0 {per_seed[s]}/{n_cmp_seed[s]}")
    os.makedirs(OUT_DIR, exist_ok=True)
    out = {"spec": "docs/thesis/E21_relaxable_component_spec.md §8.7 v1.1（探索性、事後訂定）",
           "checks": {"S3-0": "pass", "S3-1": "pass"}, "results": res,
           "elapsed_s": round(time.time() - t_start, 1)}
    p = os.path.join(OUT_DIR, "E21_S3_gate.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"寫入 {p}（{time.time() - t_start:.0f} s）")


if __name__ == "__main__":
    main()
