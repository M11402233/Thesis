#!/usr/bin/env python3
"""D-30P1 有換手之小型驗證分析（docs/thesis/D30P1_ho_pilot_spec.md §4–6；結果出來前寫定）。唯讀。
用法：analyze_r11c_ho.py <data/r11c_ho> <data/r11c_causal>      HO 組與 NoAuto 對照組以同一函式、同一窗（0–29）處理。
K1 失敗 → 結束碼 2。解析邏輯與 analyze_r11c.py 相同（已修正 Q 行欄數 = 7、r11eff 為累計值、C 行重複）。"""
import bisect, collections as Co, gzip, json, os, sys
import numpy as np
HO, NA = sys.argv[1], sys.argv[2]
OUT = os.environ.get('R11C_OUT', HO)   # 乾跑時指向暫存目錄，避免寫入實驗目錄
SEEDS = tuple(int(x) for x in os.environ.get('R11C_SEEDS', '4200,4201,4202,4203').split(','))
NW = int(os.environ.get('R11C_NWIN', '30')); QOUT = -8.0
LEN = {'T': 11, 'D': 19, 'R': 14, 'Q': 7, 'E': 10}
def op(p): return gzip.open(p, 'rt') if p.endswith('.gz') else open(p)
def eff_file(d):
    for n in ('DlE2RlcStats_r11eff.txt', 'DlE2RlcStats_r11eff.txt.gz'):
        if os.path.exists(os.path.join(d, n)): return os.path.join(d, n)
    raise SystemExit(f'no r11eff in {d}')
def read_eff(p, nwin):
    rows = {}
    for l in op(p):
        if l.startswith('%'): continue
        f = l.split('\t'); k = int(f[0]) // 10**9
        if k >= nwin: continue
        rows[(k, int(f[2]), int(f[3]), int(f[4]))] = (int(f[9]), int(f[10]))
    by = Co.defaultdict(list)
    for (k, c, i, l), v in rows.items(): by[(c, i, l)].append((k, v))
    out = {}
    for key, lst in by.items():
        prev = (0, 0)
        for k, v in sorted(lst):
            d = (v[0] - prev[0], v[1] - prev[1])
            if d[0] < 0: raise SystemExit(f'r11eff 非單調 {p}')
            out[(k,) + key] = d; prev = v
    return out
def ho_events(md):
    ev = {}
    for kind, fn in (('start', 'EnbHandoverStartStats.txt'), ('end', 'EnbHandoverEndStats.txt')):
        p = os.path.join(md, fn); lst = Co.defaultdict(list)
        if os.path.exists(p):
            for l in open(p):
                f = l.split()
                if len(f) >= 2: lst[int(f[1])].append(float(f[0]))
        ev[kind] = lst
    return ev
def extract(D, s):
    tr, md = os.path.join(D, f'trace_{s}'), os.path.join(D, f'main_{s}')
    retx = Co.defaultdict(list); newk = {}; Q = []; E = []; bad = Co.Counter()
    for l in open(os.path.join(tr, 'R10_trace.txt')):
        f = l.rstrip('\n').split('\t'); t = f[0]
        if len(f) != LEN.get(t, -1): bad[t] += 1; continue
        if t == 'T':
            k = (int(f[10]), int(f[2]), int(f[3]), int(f[5]), int(f[8]))
            if f[4] == 'N': newk[k] = int(f[1])
            else: retx[k].append(int(f[1]))
        elif t == 'Q': Q.append(int(f[5]))
        elif t == 'E': E.append((int(f[5]), int(f[7]), int(f[8])))
    dq = Co.defaultdict(list)
    for l in open(os.path.join(tr, 'R10_trace.txt')):
        if l[0] != 'D': continue
        f = l.rstrip('\n').split('\t')
        if len(f) == 19: dq[(int(f[1]), int(f[2]), int(f[3]), int(f[5]), int(f[6]), int(f[8]))].append(int(f[13]))
    samples = []; seen = set(); unmatched = 0
    for l in open(os.path.join(tr, 'R10_trace_calc.txt')):
        f = l.rstrip('\n').split('\t')
        if len(f) != 14 or int(f[11]) < 0: continue
        ns, cell, imsi, rnti, lcid, delay, tagT, off, sn = int(f[2]), int(f[3]), int(f[4]), int(f[5]), int(f[6]), int(f[8]), int(f[10]), int(f[13]), int(f[11])
        key = (ns, rnti, lcid, sn, tagT, off); ck = (key, cell, imsi)
        if ck in seen: continue
        seen.add(ck); lst = dq.get(key)
        if not lst: unmatched += 1; continue
        if lst.pop(0) == 1: samples.append((ns, cell, imsi, lcid, delay, tagT, rnti, sn))
    ref = read_eff(eff_file(md), NW); mine = Co.defaultdict(lambda: [0, 0])
    for ns, cell, imsi, lcid, delay, tagT, rnti, sn in samples:
        k = ns // 10**9
        if k < NW: m = mine[(k, cell, imsi, lcid)]; m[0] += 1; m[1] += delay
    def rv(k): v = ref.get(k, (0, 0)); return v if v[0] else (0, 0)
    mism = [k for k in set(ref) | set(mine) if rv(k) != tuple(mine.get(k, [0, 0]))]
    k1 = {'rows_ref': len(ref), 'rows_mine': len(mine), 'mismatch': len(mism), 'unmatched_calc': unmatched, 'bad_trace_lines': dict(bad)}
    U = Co.defaultdict(list); nW = 0; rrcp = os.path.join(tr, 'R11C_rrc.txt')
    for l in open(rrcp):
        f = l.rstrip('\n').split('\t')
        if f[0] == 'U' and len(f) == 9: U[int(f[2])].append((int(f[1]), float(f[4])))
        elif f[0] == 'W': nW += 1
    return dict(samples=samples, retx=retx, newk=newk, Q=Q, E=E, k1=k1, U=U, nW=nW, ev=ho_events(md), md=md,
                rlf=os.path.exists(os.path.join(tr, 'R11C_rlf.txt')))
def metrics(x, with_mech):
    mm = [t for t in x['samples'] if t[1] != 1 and t[0] // 10**9 < NW]
    d = np.array([t[4] for t in mm], dtype=np.int64); n = len(d)
    out = {'n_mmw_samples': n, 'n_lte_samples': sum(1 for t in x['samples'] if t[1] == 1 and t[0] // 10**9 < NW)}
    out['n_gt1s'] = int((d > 10**9).sum()); out['R_gt1s'] = out['n_gt1s'] / n if n else None
    out['median_ms'] = float(np.median(d)) / 1e6 if n else None; out['p99_ms'] = float(np.percentile(d, 99)) / 1e6 if n else None
    out['max_ms'] = float(d.max()) / 1e6 if n else None
    blk = Co.defaultdict(lambda: [0, 0])
    for t in mm: b = (t[0] // 10**9) // 10; blk[b][0] += 1; blk[b][1] += t[4] > 10**9
    out['R_by_10s_block'] = {str(b): (v[1] / v[0] if v[0] else None) for b, v in sorted(blk.items())}
    out['dropped_sdu_total'] = len(x['Q'])
    ue = set((t[0] // 10**9, t[2]) for t in mm if t[0] // 10**9 < NW); out['ue_window_covered'] = len(ue)
    cu = Co.defaultdict(set)
    for t in mm: cu[(t[0] // 10**9, t[1])].add(t[2])
    out['cell_window_n_ue_dist(4=>=4)'] = dict(sorted(Co.Counter(min(len(v), 4) for v in cu.values()).items()))
    if with_mech:
        st = {i: sorted(v) for i, v in x['ev']['start'].items()}; g = [t for t in mm if t[4] > 10**9]; has = out_ = 0
        for ns, cell, imsi, lcid, delay, tagT, rnti, sn in g:
            ts = st.get(imsi, []); a, b = bisect.bisect_left(ts, tagT / 1e9), bisect.bisect_right(ts, ns / 1e9)
            has += b > a
            u = x['U'].get(imsi, []); tt = [q[0] for q in u]; i0, i1 = bisect.bisect_left(tt, tagT), bisect.bisect_right(tt, ns)
            seg = u[i0:i1]
            if seg and sum(1 for q in seg if q[1] < QOUT) / len(seg) >= 0.5: out_ += 1
        out['M_H2'] = {'n_gt1s': len(g), 'frac_with_handover_in_interval': has / len(g) if g else None,
                       'frac_serving_sinr_below_qout_half': out_ / len(g) if g else None}
    return out
def hostats(x):
    dur = []; unmatched = 0; n = 0
    for imsi, sts in x['ev']['start'].items():
        ens = x['ev']['end'].get(imsi, []); n += len(sts)
        for i, t in enumerate(sts):
            if i < len(ens): dur.append(ens[i] - t)
            else: unmatched += 1
    dur = np.array(dur) if dur else np.array([0.0])
    return {'n_start': n, 'n_end': sum(len(v) for v in x['ev']['end'].values()), 'start_without_end': unmatched,
            'dur_median_ms': float(np.median(dur)) * 1e3, 'dur_p99_ms': float(np.percentile(dur, 99)) * 1e3}
status = open(os.path.join(HO, 'status.txt')).read()
if not os.environ.get('R11C_SKIPGATE'):
    for g in ('G0 PASS', 'G1 PASS') + tuple(f'G2 {s} PASS' for s in SEEDS):
        if g not in status: raise SystemExit(f'gate missing: {g}')
res = {'spec': 'D30P1_ho_pilot_spec.md v0', 'HO': {}, 'NoAuto': {}}
pool = {'HO': Co.Counter(), 'NoAuto': Co.Counter()}
for lab, D in (('HO', HO), ('NoAuto', NA)):
    for s in SEEDS:
        x = extract(D, s)
        if x['k1']['mismatch']:
            res[lab][s] = {'K1': x['k1']}; json.dump(res, open(os.path.join(OUT, 'analysis_K1_fail.json'), 'w'), indent=1, default=str)
            print('K1 FAIL', lab, s, x['k1']); sys.exit(2)
        m = metrics(x, lab == 'HO'); m['K1'] = x['k1']; m['W_lines'] = x['nW']; m['rlf_file'] = x['rlf']; m['handover'] = hostats(x)
        res[lab][s] = m
        pool[lab]['n'] += m['n_mmw_samples']; pool[lab]['gt1'] += m['n_gt1s']; pool[lab]['cov'] += m['ue_window_covered']
        pool[lab]['ho'] += m['handover']['n_start']
        print(lab, s, 'done', m['n_mmw_samples'], m['R_gt1s'], flush=True)
R = {k: pool[k]['gt1'] / pool[k]['n'] for k in pool}; cov = {k: pool[k]['cov'] / (30 * NW * len(SEEDS)) for k in pool}
ratio = R['HO'] / R['NoAuto'] if R['NoAuto'] else None
verdict = ('換手使長尾變大（停止，回報）' if ratio is not None and ratio >= 1.5 else '換手使長尾明顯縮小' if ratio is not None and ratio <= 0.2 else '無明顯差異')
valid = {'k1_all_pass': True, 'handover_count_gt0': pool['HO']['ho'] > 0, 'coverage_HO_ge_0.70': cov['HO'] >= 0.70, 'coverage': cov}
valid['all'] = valid['k1_all_pass'] and valid['handover_count_gt0'] and valid['coverage_HO_ge_0.70']
res['summary'] = {'R_gt1s_pooled': R, 'ratio_HO_over_NoAuto': ratio, 'verdict': verdict, 'validity': valid, 'n_handover_starts_HO': pool['HO']['ho']}
os.makedirs(os.path.join(OUT, 'analysis'), exist_ok=True)
json.dump(res, open(os.path.join(OUT, 'analysis', 'r11c_ho_analysis.json'), 'w'), indent=1, ensure_ascii=False, default=str)
print(json.dumps(res['summary'], indent=1, ensure_ascii=False, default=str))
