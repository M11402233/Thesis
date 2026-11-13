#!/usr/bin/env python3
"""探索性（只讀；R-5 run 進行中，窗數會增加）：兩路（LTE cell 1／mmWave）分帳之影響。
輸入：<run>/DlE2RlcStats.txt（主檔：cell 欄、累計平均）、<run>/DlE2RlcStats_percell.txt（依事件 cellId 累計）。
(b) 每 (UE, 窗) 之 LTE 樣本比例；混合平均 vs 只計 mmWave 之平均之差。
(a) 主檔 cell 欄 = 1 之 (UE, 窗) 與當窗 mmWave Rx 數／比例之關係（「最後事件競賽」之可檢驗推論：
    mmWave 比例越低，被記為 cell 1 之機率越高）；以及當窗無 LTE 新事件卻被記為 cell 1 之個數（應為 0）。
"""
import sys, json, collections
import numpy as np
run = sys.argv[1]
pc = collections.defaultdict(lambda: collections.defaultdict(lambda: np.zeros(4)))  # (imsi)->{w: [nRx_lte, sum_lte, nRx_mmw, sum_mmw]}
for ln in open(f"{run}/DlE2RlcStats_percell.txt"):
    if ln[0] == "%": continue
    p = ln.split("\t"); w = int(p[0]) // 10**9; cell, imsi = int(p[2]), int(p[3]); nrx, s = int(p[7]), int(p[9])
    k = 0 if cell == 1 else 2
    pc[imsi][w][k] += nrx; pc[imsi][w][k + 1] += s
lab = {}
for ln in open(f"{run}/DlE2RlcStats.txt"):
    if ln[0] == "%": continue
    p = ln.split("\t"); lab[(int(p[3]), int(float(p[0])))] = int(p[2])
last = max(w for d in pc.values() for w in d)
rows = []
for i, d in pc.items():
    for w in sorted(d):
        if w == last or (i, w) not in lab: continue
        cur = d[w]; prev = d[w - 1] if w - 1 in d else np.zeros(4)
        dl, sl, dm, sm = cur - prev
        if dl + dm <= 0: continue
        rows.append(dict(i=i, w=w, lab1=lab[(i, w)] == 1, lte_share=dl / (dl + dm), n_mmw=dm, n_lte=dl,
                         mixed=(sl + sm) / (dl + dm) / 1e6, mmw_only=(sm / dm / 1e6) if dm > 0 else None,
                         lte_only=(sl / dl / 1e6) if dl > 0 else None))
sh = np.array([r["lte_share"] for r in rows]); diff = np.array([r["mixed"] - r["mmw_only"] for r in rows if r["mmw_only"] is not None])
lteonly = np.array([r["lte_only"] for r in rows if r["lte_only"] is not None])
out = {"run": run, "windows_used": [min(r["w"] for r in rows), max(r["w"] for r in rows)], "ue_windows": len(rows)}
out["b_lte_sample_share"] = dict(median=float(np.median(sh)), q10=float(np.percentile(sh, 10)), q90=float(np.percentile(sh, 90)))
out["b_lte_leg_delay_ms"] = dict(min=float(lteonly.min()), max=float(lteonly.max()))
out["b_mixed_minus_mmw_only_ms"] = dict(median=float(np.median(diff)), q10=float(np.percentile(diff, 10)), q90=float(np.percentile(diff, 90)))
mm = np.array([r["mmw_only"] for r in rows if r["mmw_only"] is not None]); mx = np.array([r["mixed"] for r in rows if r["mmw_only"] is not None])
out["b_median_ms"] = dict(mixed=float(np.median(mx)), mmw_only=float(np.median(mm)))
L1 = [r for r in rows if r["lab1"]]; L0 = [r for r in rows if not r["lab1"]]
out["a_label1_share"] = len(L1) / len(rows)
out["a_lte_share_median_by_label"] = dict(label1=float(np.median([r["lte_share"] for r in L1])) if L1 else None, label_mmw=float(np.median([r["lte_share"] for r in L0])))
out["a_label1_without_new_lte_events"] = sum(1 for r in L1 if r["n_lte"] == 0)
out["a_label_mmw_without_new_mmw_events"] = sum(1 for r in L0 if r["n_mmw"] == 0)
q = np.quantile(sh, [0, .25, .5, .75, 1])
out["a_label1_rate_by_lte_share_quartile"] = [dict(range=[round(float(q[k]), 3), round(float(q[k + 1]), 3)],
    rate=float(np.mean([r["lab1"] for r in rows if q[k] <= r["lte_share"] <= q[k + 1]]))) for k in range(4)]
print(json.dumps(out, ensure_ascii=False, indent=1))
