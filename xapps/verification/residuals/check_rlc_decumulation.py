#!/usr/bin/env python3
"""語意規格 v0 §5 之 R-1～R-4：DlE2RlcStats 反推每窗平均延遲之前提檢查（只讀）。
R-1 樣本對應（程式層，見規格；此處檢查 nRxPDUs 不減、delay 於 N=0 時為 0）
R-2 邊界：每窗列齊全、窗連續、計數不減（無重置）
R-3 第一窗：窗 0 之累計即該窗（計算器於 t=0 建立，m_startTime=0）
R-4 精度：印出 6 位有效數字 → ε = 0.5·10^(floor(log10 D)−5)；
     |Δd_w| ≤ (N_w ε_w + N_{w−1} ε_{w−1}) / (N_w − N_{w−1})
用法：check_rlc_decumulation.py <seed.txt> [...] --json out.json
"""
import sys, json, math, argparse, collections
import numpy as np
ap = argparse.ArgumentParser(); ap.add_argument('files', nargs='+'); ap.add_argument('--json'); a = ap.parse_args()
eps = lambda D: 0.0 if D == 0 else 0.5 * 10 ** (math.floor(math.log10(abs(D))) - 5)
out = {}
for f in a.files:
    R = collections.defaultdict(dict); dup = 0
    for ln in open(f):
        if ln[0] == '%': continue
        p = ln.split('\t')
        w, i = int(float(p[0])), int(p[3]); key = (int(p[5]),)   # LCID
        if w in R[(i, key)]: dup += 1
        R[(i, key)][w] = (int(p[8]), float(p[10]), int(p[6]), int(p[7]))
    wins = sorted({w for S in R.values() for w in S})
    c = collections.Counter(); bnd = []; bnd_late = []; bnd_early = []; dn_list = []; step = []
    for (i, k), S in R.items():
        ws = sorted(S)
        if ws != list(range(ws[0], ws[-1] + 1)): c['gap_in_windows'] += 1
        prev_d = None
        for w0, w1 in zip(ws, ws[1:]):
            (N0, D0, T0, B0), (N1, D1, T1, B1) = S[w0], S[w1]
            c['pairs'] += 1
            if N1 < N0 or T1 < T0 or B1 < B0: c['decrease'] += 1; continue
            if N0 == 0 and D0 != 0: c['delay_nonzero_with_N0'] += 1
            dn = N1 - N0
            if dn == 0: c['no_new_rx'] += 1; continue
            d = (D1 * N1 - D0 * N0) / dn
            if d < 0: c['negative'] += 1
            b = (N1 * eps(D1) + N0 * eps(D0)) / dn
            bnd.append(b); dn_list.append(dn)
            (bnd_late if w1 >= 270 else bnd_early if w1 <= 30 else []).append(b)
            if prev_d is not None: step.append(abs(d - prev_d))
            prev_d = d
    bnd = np.array(bnd) * 1e3; ms = lambda x, q: float(np.percentile(np.array(x) * 1e3, q)) if len(x) else None
    out[f.split('/')[-1]] = dict(rows_dup=dup, ue_lcid=len(R), windows=[wins[0], wins[-1], len(wins)], **c,
        bound_ms=dict(median=float(np.median(bnd)), p99=float(np.percentile(bnd, 99)), max=float(bnd.max())),
        bound_ms_early_w1_30=dict(median=ms(bnd_early, 50), max=ms(bnd_early, 100)),
        bound_ms_late_w270_299=dict(median=ms(bnd_late, 50), p99=ms(bnd_late, 99), max=ms(bnd_late, 100)),
        new_rx_per_window=dict(min=int(min(dn_list)), median=float(np.median(dn_list))),
        recon_step_ms_median=float(np.median(step)) * 1e3)
    o = out[f.split('/')[-1]]
    print(f.split('/')[-1], {k: o[k] for k in ('ue_lcid', 'pairs', 'decrease') if k in o}, 'neg', o.get('negative', 0), 'no_new', o.get('no_new_rx', 0),
          'bound med/p99/max ms %.2e/%.2e/%.2e' % tuple(o['bound_ms'].values()), 'late max %.2e' % o['bound_ms_late_w270_299']['max'],
          'recon step %.3f' % o['recon_step_ms_median'], 'minNew', o['new_rx_per_window']['min'])
if a.json: json.dump(out, open(a.json, 'w'), indent=1)
