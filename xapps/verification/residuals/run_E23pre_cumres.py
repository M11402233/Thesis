#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_E23pre_cumres.py — 規格 docs/thesis/E23pre_cumulative_residual_precheck_spec.md v1。
帶符號空間殘差多窗平均之先決條件檢查（只讀乾淨 D-30；固定階躍、非適應）。

跑法：ZT_DATASET=d30 ZT_FUSION_ORDER=severity python3 xapps/verification/residuals/run_E23pre_cumres.py
"""
import os
import sys
import json
import time
import collections
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run_E21_S0_membership as S0                                    # noqa: E402
from run_E21_S0_membership import X, DS, load_windows, replay, stop   # noqa: E402

OUT_DIR = os.path.join(S0.SEV_DIR, "E23pre")
LS = [5, 10, 20, 30]
AS = [0.892, 0.822]
DEV_REF = 0.108


def signed(cells, target, scale):
    """與 verify_si 相同之 tgt／ref；回傳 (r, tgt÷scale) 或 None"""
    mmw = [c for c in cells if c != X.LTE_CELL]
    peers = [c for c in mmw if c != target]
    if target not in cells or target == X.LTE_CELL or len(peers) < X.MIN_PEER:
        return None
    tgt = float(np.mean(list(cells[target].values())))
    ref = float(np.median([np.mean(list(cells[c].values())) for c in peers]))
    return (tgt - ref) / scale, tgt / scale


def blocks(v, L):
    return [float(np.mean(v[i:i + L])) for i in range(0, len(v) - L + 1, L)]


def main():
    t_start = time.time()
    files = DS.files()
    series = {}                       # (seed, node) -> [(r, tgt/scale)]
    n_all = 0
    for f in files:
        sd = DS.seed_of(f)
        anchor = X.TrustAnchor([g for g in files if g != f])
        base = load_windows(f)
        ann, _ = replay(base, anchor)
        zs = {(a["window"], a["node"]): a["z_S"] for a in ann}
        n_all += len(ann)
        for w, cells in base:
            for j in sorted(c for c in cells if c != X.LTE_CELL):
                s = signed(cells, j, anchor.scale)
                z = zs.get((w, j))
                if s is None:
                    if z is not None:
                        stop(f"E23P-0 seed {sd} 窗 {w} 節點 {j}：註記有 z_S 但本程式判不可用")
                    continue
                if z is None or round(abs(s[0]), 2) != z:
                    stop(f"E23P-0 seed {sd} 窗 {w} 節點 {j}：|r|={abs(s[0]):.4f} vs z_S={z}")
                series.setdefault((sd, j), []).append(s)
    if n_all != 15534:
        stop(f"E23P-0 註記筆數 {n_all} ≠ 15,534")
    print(f"  E23P-0 ✓ {n_all} 筆；|r| 逐筆重現 z_S")

    allr = np.array([r for v in series.values() for r, _ in v])
    allt = np.array([t for v in series.values() for _, t in v])
    theta = 0.5 * float(np.median(DEV_REF * allt))
    print(f"  殘差筆數 {len(allr)}；整體平均 {allr.mean():+.3f}、SD {allr.std():.3f}；"
          f"tgt÷scale 中位數 {np.median(allt):.3f}；θ = {theta:.4f}")

    per = {}
    for (sd, j), v in sorted(series.items()):
        r = np.array([x[0] for x in v])
        ac = float(np.corrcoef(r[:-1], r[1:])[0, 1]) if len(r) > 2 and r.std() > 0 else None
        per[f"{sd}|{j}"] = {"n": len(r), "mean": float(r.mean()), "sd": float(r.std()), "lag1": ac}
    node_mean = collections.defaultdict(list)
    for k, v in per.items():
        node_mean[k.split("|")[1]].append(v["mean"])
    print("  逐節點跨 seed 之平均 r：" + "  ".join(
        f"{j}:{np.mean(m):+.2f}[{min(m):+.2f},{max(m):+.2f}]" for j, m in sorted(node_mean.items(), key=lambda x: int(x[0]))))
    lag = [v["lag1"] for v in per.values() if v["lag1"] is not None]
    print(f"  lag-1 自相關：中位數 {np.median(lag):.3f}，範圍 [{min(lag):.3f}, {max(lag):.3f}]；"
          f"|逐 (seed,節點) 平均| ≥ θ 者 {sum(abs(v['mean']) >= theta for v in per.values())}／{len(per)}")

    # E23P-1
    for v in series.values():
        if any((r + (1.0 - 1.0) * t) != r for r, t in v):
            stop("E23P-1 a=1 時 r′ ≠ r")
    print("  E23P-1 ✓")

    res = {}
    for L in LS:
        fa_b, det_b = [], {a: [] for a in AS}
        fa_by = {}
        for key, v in series.items():
            r = [x[0] for x in v]
            b = [abs(m) >= theta for m in blocks(r, L)]
            fa_b += b
            if b:
                fa_by[key] = float(np.mean(b))
            for a in AS:
                rp = [x[0] + (a - 1.0) * x[1] for x in v]
                det_b[a] += [abs(m) >= theta for m in blocks(rp, L)]
        res[L] = {"n_blocks": len(fa_b), "FA": float(np.mean(fa_b)),
                  "DET": {str(a): float(np.mean(det_b[a])) for a in AS},
                  "n_series_FA_gt_0.20": sum(x > 0.20 for x in fa_by.values()), "n_series": len(fa_by)}
        print(f"  L={L:2d}  區塊 {len(fa_b):5d}  FA {res[L]['FA']:.3f}  "
              + "  ".join(f"DET(a={a}) {res[L]['DET'][str(a)]:.3f}" for a in AS)
              + f"  FA>0.20 之序列 {res[L]['n_series_FA_gt_0.20']}／{len(fa_by)}")

    ok = [L for L in LS if res[L]["FA"] <= 0.05 and res[L]["DET"]["0.892"] >= 0.80]
    bad = all(res[L]["FA"] > 0.20 or res[L]["DET"]["0.892"] < 0.50 for L in LS)
    verdict = "成立" if ok else ("不成立" if bad else "不確定")
    print(f"  判定：{verdict}" + (f"（L = {ok}）" if ok else ""))

    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, "E23pre_cumres.json")
    json.dump({"spec": "docs/thesis/E23pre_cumulative_residual_precheck_spec.md v1",
               "theta": theta, "n": int(len(allr)), "overall_mean": float(allr.mean()), "overall_sd": float(allr.std()),
               "tgt_over_scale_median": float(np.median(allt)), "per_series": per,
               "node_mean": {j: [float(x) for x in m] for j, m in node_mean.items()},
               "by_L": {str(L): res[L] for L in LS}, "verdict": verdict, "L_ok": ok},
              open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"寫入 {out}（{time.time() - t_start:.0f} s）")


if __name__ == "__main__":
    main()
