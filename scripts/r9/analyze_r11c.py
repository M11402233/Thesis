#!/usr/bin/env python3
"""D-30P1 因果驗證分析（docs/thesis/D30P1_causal_maxretx_spec.md §6–7；結果出來前寫定）。唯讀。
用法：analyze_r11c.py <data/r11c_causal> <data/ues30_p_r10_seeds>  → <out>/analysis/{r11c_analysis.json,.md}
K1 失敗 → 結束碼 2，不產生結論。"""
import bisect, collections as Co, glob, gzip, json, os, sys
OUT, FULL = sys.argv[1], sys.argv[2]
SEEDS = tuple(int(x) for x in os.environ.get('R11C_SEEDS', '4200,4201,4202,4203').split(',')); MAXRETX = 5; QOUT, OUTAGE = -8.0, -5.0; T310MAX = 6.0e9
def op(p): return gzip.open(p, 'rt') if p.endswith('.gz') else open(p)
def eff_file(d):
    for n in ('DlE2RlcStats_r11eff.txt', 'DlE2RlcStats_r11eff.txt.gz'):
        if os.path.exists(os.path.join(d, n)): return os.path.join(d, n)
    raise SystemExit(f'no r11eff in {d}')
def read_eff(p, nwin, cumulative=False):
    """DlE2RlcStats_r11eff：每列為 (cell, IMSI, LCID) 自 t=0 起之累計 nEff／delaySumEff。cumulative=False 時回傳逐窗差分。"""
    rows = {}
    for l in op(p):
        if l.startswith('%'): continue
        f = l.split('\t'); k = int(f[0]) // 1000000000
        if k >= nwin: continue
        rows[(k, int(f[2]), int(f[3]), int(f[4]))] = (int(f[9]), int(f[10]))
    if cumulative: return rows
    by = Co.defaultdict(list)
    for (k, c, i, l), v in rows.items(): by[(c, i, l)].append((k, v))
    out = {}
    for (c, i, l), lst in by.items():
        prev = (0, 0)
        for k, v in sorted(lst):
            d = (v[0] - prev[0], v[1] - prev[1])
            if d[0] < 0: raise SystemExit(f'r11eff 非單調 {p} {(k, c, i, l)}')
            out[(k, c, i, l)] = d; prev = v
    return out
def bin_d(d): return '<=100ms' if d <= 1e8 else ('100ms-1s' if d <= 1e9 else '>1s')
def bin_r(r): return '0' if r == 0 else ('1-4' if r < MAXRETX else '>=5')

res = {'spec': 'D30P1_causal_maxretx_spec.md v0', 'seeds': {}, 'K1': {}}
status = open(os.path.join(OUT, 'status.txt')).read()
for g in ('G0 PASS', 'G1 PASS') + tuple(f'G2 {s} PASS' for s in SEEDS):
    if g not in status: raise SystemExit(f'gate missing: {g}')
agg = {'M1': Co.Counter(), 'gt1': [], 'groups_gt1': set()}
for s in SEEDS:
    tr = os.path.join(OUT, f'trace_{s}'); md = os.path.join(OUT, f'main_{s}')
    # T：傳送
    retx = Co.defaultdict(list); newk = {}; cellof = {}
    Q = []; E = []; trunc_t = Co.Counter()
    for l in open(os.path.join(tr, 'R10_trace.txt')):
        f = l.rstrip('\n').split('\t'); t = f[0]
        if len(f) != {'T': 11, 'D': 19, 'R': 14, 'Q': 7, 'E': 10}.get(t, -1): trunc_t[t] += 1; continue   # 截斷行／未知行
        if t == 'T':
            k = (int(f[10]), int(f[2]), int(f[3]), int(f[5]), int(f[8]))       # imsi, rnti, lcid, sn, tagT
            if f[4] == 'N': newk[k] = int(f[1])
            else: retx[k].append(int(f[1]))
        elif t == 'Q': Q.append((int(f[4]), int(f[2]), int(f[3]), int(f[5])))
        elif t == 'E': E.append((int(f[4]), int(f[2]), int(f[3]), int(f[5]), int(f[6]), int(f[7]), int(f[8]), int(f[9])))
    # D：接收端有效旗標（UE 側，imsi 欄為 0）；以 (ns, rnti, lcid, sn, tagT, segOff) 對 C 行
    dq = Co.defaultdict(list)
    for l in open(os.path.join(tr, 'R10_trace.txt')):
        if l[0] != 'D': continue
        f = l.rstrip('\n').split('\t')
        if len(f) != 19: continue
        dq[(int(f[1]), int(f[2]), int(f[3]), int(f[5]), int(f[6]), int(f[8]))].append(int(f[13]))
    samples = []; amb = 0; unmatched = 0; seenc = set(); trunc = 0
    for l in open(os.path.join(tr, 'R10_trace_calc.txt')):
        f = l.rstrip('\n').split('\t')
        if len(f) != 14: trunc += 1; continue                                # 結束時未 flush 之截斷行（只可能在檔尾）
        # C <this> <ns> <cellId> <imsi> <rnti> <lcid> <size> <delay> <tagFound> <tagT> <sn> <seg> <segOff>
        sn = int(f[11])
        if sn < 0: continue
        ns, cell, imsi, rnti, lcid, delay, tagT, off = int(f[2]), int(f[3]), int(f[4]), int(f[5]), int(f[6]), int(f[8]), int(f[10]), int(f[13])
        cellof[(imsi, rnti)] = cell
        key = (ns, rnti, lcid, sn, tagT, off)
        ck = (key, cell, imsi)
        if ck in seenc: continue                                            # 同一接收由多個計算器實例各寫一行（只差 this 欄）
        seenc.add(ck); lst = dq.get(key)
        if not lst: unmatched += 1; continue
        if len(lst) > 1: amb += 1
        if lst.pop(0) == 1: samples.append((ns, cell, imsi, rnti, lcid, sn, tagT, delay))
    # K1
    NW = int(os.environ.get('R11C_NWIN', '30')); ref = read_eff(eff_file(md), NW); mine = Co.defaultdict(lambda: [0, 0])
    for ns, cell, imsi, rnti, lcid, sn, tagT, delay in samples:
        k = ns // 1000000000
        if k < NW: m = mine[(k, cell, imsi, lcid)]; m[0] += 1; m[1] += delay
    def refv(k):
        v = ref.get(k, (0, 0)); return v if v[0] else (0, 0)
    bad = [k for k in set(ref) | set(mine) if refv(k) != tuple(mine.get(k, [0, 0]))]   # ref 為逐窗差分（read_eff）
    res['K1'][s] = {'rows_ref': len(ref), 'rows_mine': len(mine), 'mismatch': len(bad), 'example': [list(map(str, b)) for b in bad[:3]],
                    'ambiguous_keys': amb, 'calc_unmatched': unmatched, 'calc_truncated_lines': trunc, 'trace_bad_lines': dict(trunc_t)}
    if bad:
        json.dump(res, open(os.path.join(OUT, 'analysis_K1_fail.json'), 'w'), indent=1)
        print('K1 FAIL', s, res['K1'][s]); sys.exit(2)
    # U：RRC 視角
    U = Co.defaultdict(list)
    for l in open(os.path.join(tr, 'R11C_rrc.txt')):
        f = l.rstrip('\n').split('\t')
        if f[0] == 'U': U[int(f[2])].append((int(f[1]), int(f[3]), float(f[4]), int(f[5]), float(f[6])))
    nW = sum(1 for l in open(os.path.join(tr, 'R11C_rrc.txt')) if l[0] == 'W')
    sd = {'n_eff_samples_all': len(samples), 'W_lines': nW, 'rlf_file_exists': os.path.exists(os.path.join(tr, 'R11C_rlf.txt'))}
    M1 = Co.Counter(); gt1 = []
    for ns, cell, imsi, rnti, lcid, sn, tagT, delay in samples:
        if cell == 1 or ns // 1000000000 >= NW: continue
        rt = sorted(retx.get((imsi, rnti, lcid, sn, tagT), [])); before = [x for x in rt if x < ns]
        M1[(bin_d(delay), bin_r(len(before)))] += 1
        if delay > 1e9:
            u = U.get(imsi, []); ts = [x[0] for x in u]; i0, i1 = bisect.bisect_left(ts, tagT), bisect.bisect_right(ts, ns)
            seg = u[i0:i1]; n = len(seg)
            out = [x[2] < QOUT for x in seg]; hoc = [(x[3] != x[1] and x[4] >= OUTAGE) for x in seg]
            run = best = 0; start = None
            for j, o in enumerate(out):
                if o:
                    if start is None: start = seg[j][0]
                    best = max(best, seg[j][0] - start + 100000000)
                else: start = None
            post = (ns - before[MAXRETX - 1]) / delay if len(before) >= MAXRETX else None
            gt1.append({'imsi': imsi, 'cell': cell, 'delay': delay, 'retx': len(before), 'n_u': n,
                        'frac_out': (sum(out) / n) if n else None, 'frac_hoc': (sum(hoc) / n) if n else None,
                        'longest_out_ns': best, 'post_maxretx_frac': post})
    sd['M1'] = {f'{a}|{b}': v for (a, b), v in sorted(M1.items())}
    sd['n_gt1'] = len(gt1); sd['groups_gt1'] = len({(g['imsi'], g['cell']) for g in gt1})
    # M5
    def ctype(imsi, rnti): c = cellof.get((imsi, rnti)); return 'unknown' if c is None else ('lte' if c == 1 else 'mmw')
    delivered = {(imsi, rnti, lcid, sn, tagT) for ns, cell, imsi, rnti, lcid, sn, tagT, delay in samples}
    m5 = Co.defaultdict(Co.Counter)
    for k in newk:
        c = ctype(k[0], k[1]); m5[c]['new_pdus'] += 1; m5[c]['new_pdus_delivered'] += k in delivered
        nr = len(retx.get(k, [])); m5[c]['new_pdus_retx_ge5'] += nr >= MAXRETX
        m5[c]['new_pdus_retx_ge5_delivered'] += (nr >= MAXRETX and k in delivered)
    for imsi, rnti, lcid, size in Q: c = ctype(imsi, rnti); m5[c]['Q_sdu_dropped'] += 1; m5[c]['Q_bytes'] += size
    for imsi, rnti, lcid, txonN, txonB, txedN, retxN, oldest in E:
        c = ctype(imsi, rnti) if imsi else 'ue_side'; m5[c]['E_txon_sdus'] += txonN; m5[c]['E_txed_pdus'] += txedN; m5[c]['E_retx_pdus'] += retxN
    sd['M5'] = {c: dict(v) for c, v in m5.items()}
    res['seeds'][s] = sd; agg['M1'].update(M1); agg['gt1'] += gt1; agg['groups_gt1'] |= {(s, g['imsi'], g['cell']) for g in gt1}
# 合計與判定
M1 = agg['M1']; tot = Co.Counter(); ge5 = Co.Counter()
for (a, b), v in M1.items(): tot[a] += v; ge5[a] += v if b == '>=5' else 0
P = {a: (ge5[a] / tot[a] if tot[a] else None) for a in ('<=100ms', '100ms-1s', '>1s')}
g = agg['gt1']; n = len(g)
def frac(pred): return (sum(1 for x in g if pred(x)) / n) if n else None
post = sorted(x['post_maxretx_frac'] for x in g if x['post_maxretx_frac'] is not None)
summ = {'M1_table': {f'{a}|{b}': v for (a, b), v in sorted(M1.items())}, 'P_ge5_given': P, 'n_gt1': n, 'groups_gt1': len(agg['groups_gt1']),
        'M2_post_maxretx_frac_median': post[len(post) // 2] if post else None,
        'M3_frac_samples_out_ge_half': frac(lambda x: x['frac_out'] is not None and x['frac_out'] >= 0.5),
        'M3_frac_samples_hoc_ge_half': frac(lambda x: x['frac_hoc'] is not None and x['frac_hoc'] >= 0.5),
        'M3_no_U_in_interval': frac(lambda x: not x['n_u']),
        'M4_frac_longest_out_gt_T310max': frac(lambda x: x['longest_out_ns'] > T310MAX)}
p1, p0 = P['>1s'], P['<=100ms']
D1 = None if p1 is None else ('成立' if (p1 >= 0.8 and p0 is not None and p0 <= 0.2) else ('不成立' if p1 < 0.5 else '未定'))
nou = summ['M3_no_U_in_interval']
D2 = None if (n == 0 or nou is None or nou > 0.2) else summ['M4_frac_longest_out_gt_T310max'] >= 0.8   # 缺 RRC 資料 > 20 % → 未定
D3 = None if (n == 0 or nou is None or nou > 0.2) else summ['M3_frac_samples_hoc_ge_half'] >= 0.8
concl = ('實作缺陷（可修；修補前先回報使用者）' if (D1 == '成立' and D2) else
         '情境之正常結果（保留為方法限制）' if (D1 == '不成立' or D2 is False) else '未定（回報使用者，不修補）')
if D1 == '不成立' and D2:
    concl = '長尾與 maxRetx 無關；RLM 缺失為必要因素 → 回報使用者（規則未涵蓋，不修補）'
summ.update({'D1': D1, 'D2': D2, 'D3': D3, 'conclusion': concl})
res['summary'] = summ
# 量測覆蓋率（主跑 30 窗＋正式 8 seed × 300 窗）
def coverage(p, nwin):
    rows = read_eff(p, nwin); ue = Co.Counter(); cellue = Co.defaultdict(set)
    for (k, cell, imsi, lcid), (ne, ds) in rows.items():
        if cell == 1 or ne == 0: continue
        ue[(k, imsi)] += ne; cellue[(k, cell)].add(imsi)
    dist = Co.Counter(min(len(v), 4) for v in cellue.values())
    return {'ue_window_covered': len(ue), 'ue_window_total': 30 * nwin, 'frac': len(ue) / (30 * nwin), 'cell_window_n_ue_dist(4=>=4)': dict(sorted(dist.items()))}
res['coverage_main'] = {s: coverage(eff_file(os.path.join(OUT, f'main_{s}')), 30) for s in SEEDS}
res['coverage_official'] = {s: coverage(eff_file(os.path.join(FULL, f'D30P1_ues30_t300_seed{s}_aux')), 300) for s in range(4200, 4208)}
os.makedirs(os.path.join(OUT, 'analysis'), exist_ok=True)
json.dump(res, open(os.path.join(OUT, 'analysis', 'r11c_analysis.json'), 'w'), indent=1, ensure_ascii=False, default=str)
print(json.dumps({'K1': res['K1'], 'summary': summ}, indent=1, ensure_ascii=False, default=str))
