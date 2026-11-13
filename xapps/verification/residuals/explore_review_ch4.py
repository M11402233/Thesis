#!/usr/bin/env python3
"""探索性檢查（事後、只讀；不得當結果引用）：外部審稿對第四章之質疑之資料核對。
X1 同窗跨 mmWave cell 延遲 CV（定義同 audit_delay_cv.py）：累計平均（須重現 0.0583）vs 反推之每窗平均（同一 cell 歸屬）
X2 每 (UE, 窗) 是否有新 Rx PDU（「出列 ≠ 有新量測」之疑慮）
X3 cell=1（LTE-only）列數 vs RRC SwitchToLte 事件數（aux/MmWaveSwitchStats.txt）
X4 吞吐量時間尺度對照：每窗 ΔRxBytes 之跨 cell CV（同 X1 之窗與 cell 歸屬）
"""
import json, collections, glob, os
import numpy as np
LTE = 1
out = {}; cv_c, cv_r, cv_tp = [], [], []; new_rx_zero = 0; ue_win = 0; lte_rows = 0; sw_lte = 0; sw_mm = 0
for s in range(4200, 4208):
    f = f'data/ues30_seeds/analysis/ues30_t300_seed{s}.txt'
    rows = collections.defaultdict(dict)
    for ln in open(f):
        if ln[0] == '%': continue
        p = ln.split('\t'); rows[int(p[3])][int(float(p[0]))] = (int(p[2]), int(p[8]), float(p[10]), int(p[9]))
    win = collections.defaultdict(lambda: collections.defaultdict(dict))
    for i, S in rows.items():
        for w in sorted(S):
            c, N, D, B = S[w]
            if w == 0: rec, dB, dn = D, B, N
            else:
                c0, N0, D0, B0 = S[w - 1]; dn = N - N0; dB = B - B0
                rec = (D * N - D0 * N0) / dn if dn > 0 else None
            ue_win += 1; new_rx_zero += (dn == 0)
            if c == LTE: lte_rows += 1
            win[w][c][i] = (D, rec, dB)
    for w, cells in win.items():
        mm = [c for c in cells if c != LTE]
        if len(mm) < 2: continue
        dc = np.array([np.mean([v[0] for v in cells[c].values()]) for c in mm])
        dr = np.array([np.mean([v[1] for v in cells[c].values()]) for c in mm])
        tp = np.array([np.sum([v[2] for v in cells[c].values()]) for c in mm])
        cv_c.append(dc.std() / dc.mean()); cv_r.append(dr.std() / dr.mean()); cv_tp.append(tp.std() / tp.mean())
    for ln in open(f'data/ues30_seeds/ues30_t300_seed{s}_aux/MmWaveSwitchStats.txt'):
        if ln.startswith('SwitchToLte'): sw_lte += 1
        elif ln.startswith('SwitchToMmWave'): sw_mm += 1
q = lambda x: dict(median=float(np.median(x)), q25=float(np.percentile(x, 25)), q75=float(np.percentile(x, 75)), n=len(x))
out['X1_cv_cumulative'] = q(cv_c); out['X1_cv_reconstructed'] = q(cv_r)
out['X1_reproduces_0.0583'] = abs(out['X1_cv_cumulative']['median'] - 0.05833094978296878) < 1e-9
out['X2'] = dict(ue_windows=ue_win, windows_without_new_rx=new_rx_zero)
out['X3'] = dict(lte_cell_rows=lte_rows, switch_to_lte_events=sw_lte, switch_to_mmwave_events=sw_mm)
out['X4_tp_cv_interval'] = q(cv_tp)
os.makedirs('data/results/semantics_v0', exist_ok=True)
json.dump(out, open('data/results/semantics_v0/explore_review_ch4.json', 'w'), indent=1)
print(json.dumps(out, indent=1))
