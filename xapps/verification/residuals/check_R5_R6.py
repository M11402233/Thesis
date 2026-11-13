#!/usr/bin/env python3
"""語意規格 v0 §5.2 R-5 與 §5.3 R-6（只讀）。
R-5：同一 run 之 DlE2RlcStats.txt（舊格式，6 位）與 DlE2RlcStats_exact.txt（整數 Σdelay_ns、計數）：
     精確每窗平均 = ΔΣ / ΔN；反推 = (D_w N_w − D_{w−1} N_{w−1}) / ΔN；比較誤差。
     另驗：舊檔 nRxPDUs ＝ exact nRxPDUs（樣本對應之經驗檢查）；舊檔 delay ≈ Σ/N（捨入一致）。
R-6：舊檔前綴與參照檔（D-30 原始檔）逐位相同（窗 < n_cmp）。
用法：check_R5_R6.py <run_dir> --ref <D-30 raw seed file> --json out.json
2026-11-13 修正驗收漏洞：(1) 原版只印數字、永遠 exit 0 → 加 R5_pass／R6_pass 與非零 exit；
(2) 只迭代舊檔之鍵 → 加「exact 多出之列」；(3) 前一窗缺列時靜默略過 → 計 gap_prev_missing；
(4) 未比對 cell 欄 → 加 cell_mismatch；(5) 另報舊檔 min 欄 = 0 之列數（零延遲樣本之存在證據，僅資訊）。
"""
import sys, json, argparse, collections, math
import numpy as np
ap = argparse.ArgumentParser(); ap.add_argument('run'); ap.add_argument('--ref'); ap.add_argument('--json'); a = ap.parse_args()
old = collections.defaultdict(dict); ex = collections.defaultdict(dict)
for ln in open(f'{a.run}/DlE2RlcStats.txt'):
    if ln[0] == '%': continue
    p = ln.split('\t'); old[(int(p[3]), int(p[5]))][int(float(p[0]))] = (int(p[8]), float(p[10]), int(p[6]), int(p[2]), float(p[12]))
for ln in open(f'{a.run}/DlE2RlcStats_exact.txt'):
    if ln[0] == '%': continue
    p = ln.split('\t'); ex[(int(p[3]), int(p[4]))][int(p[0]) // 10**9] = (int(p[7]), int(p[9]), int(p[5]), int(p[2]))
R = collections.Counter(); err = []; exact_vals = []; late = []
for k, S in old.items():
    E = ex.get(k, {})
    for w in sorted(S):
        if w not in E: R['missing_exact_row'] += 1; continue
        No, Do, To, Co, MINo = S[w]; Ne, Se, Te, Ce = E[w]
        R['rows'] += 1
        if Co != Ce: R['cell_mismatch'] += 1
        if MINo == 0 and No > 0: R['info_rows_min_delay_zero'] += 1
        if No != Ne or To != Te: R['count_mismatch'] += 1
        if Ne > 0:
            m = Se / Ne * 1e-9
            if abs(Do - m) > 0.5 * 10 ** (math.floor(math.log10(m)) - 5) * (1 + 1e-9): R['rounding_inconsistent'] += 1
        if w > min(S) and not (w - 1 in S and w - 1 in E): R['gap_prev_missing'] += 1
        if w - 1 in S and w - 1 in E:
            N0, D0 = S[w - 1][0], S[w - 1][1]; N0e, S0e = E[w - 1][0], E[w - 1][1]; dn = Ne - N0e
            if dn <= 0: R['no_new_rx'] += 1; continue
            truth = (Se - S0e) / dn * 1e-9; rec = (Do * No - D0 * N0) / dn
            err.append(rec - truth); exact_vals.append(truth)
            if w >= 20: late.append(rec - truth)
last_w = max(w for S in old.values() for w in S)
for k, E in ex.items():
    for w in E:
        if w < last_w and w not in old.get(k, {}): R['extra_exact_row'] += 1
err = np.abs(np.array(err)) * 1e3; late = np.abs(np.array(late)) * 1e3
out = dict(counts=dict(R), n_pairs=len(err),
    abs_err_ms=dict(median=float(np.median(err)), p99=float(np.percentile(err, 99)), max=float(err.max())) if len(err) else None,
    abs_err_ms_w_ge20=dict(median=float(np.median(late)), p99=float(np.percentile(late, 99)), max=float(late.max())) if len(late) else None,
    exact_window_mean_ms=dict(median=float(np.median(exact_vals)) * 1e3) if exact_vals else None)
if a.ref:
    def rows(f, nmax):
        L = []
        for ln in open(f):
            if ln[0] == '%': L.append(ln); continue
            if int(float(ln.split('\t')[0])) < nmax: L.append(ln)
        return L
    wins = sorted({w for S in old.values() for w in S}); n_cmp = wins[-1]  # 最後一窗可能不完整（E2 NR 副作用），不比
    A, B = rows(f'{a.run}/DlE2RlcStats.txt', n_cmp), rows(a.ref, n_cmp)
    out['R6'] = dict(windows_compared=n_cmp, lines_run=len(A), lines_ref=len(B), identical=(A == B),
                     first_diff=next((i for i, (x, y) in enumerate(zip(A, B)) if x != y), None))
bad = {k: R[k] for k in ('missing_exact_row', 'extra_exact_row', 'count_mismatch', 'cell_mismatch', 'rounding_inconsistent', 'gap_prev_missing') if R[k]}
out['R5_structural_failures'] = bad; out['R5_pass'] = (not bad) and len(err) > 0
if a.ref: out['R6_pass'] = out['R6']['identical']
print(json.dumps(out, ensure_ascii=False, indent=1))
if a.json: json.dump(out, open(a.json, 'w'), ensure_ascii=False, indent=1)
sys.exit(0 if out['R5_pass'] and out.get('R6_pass', True) else 1)
