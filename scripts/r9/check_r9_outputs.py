#!/usr/bin/env python3
"""Internal-consistency checks of the r9 outputs of one run directory (read-only).  Exit 1 on any failure.
 K1 O-1 vs CU-CP reports: for every cell c, the k-th report instant in R9_enb_uemap.txt lists exactly the IMSIs of the
    k-th report block of cu-cp-cell-c.txt (CU-CP builds its list from the same GetUeMap(); F5).
 K2 O-1 UE view vs eNB view: at each R9_ue_rrc instant, a UE whose mmWave RRC is CONNECTED_NORMALLY (9) on cell m is in
    cell m's UeManager list at that same instant (reported, not required: list mismatches).
 K3 O-4 vs _percell: for every E2 stats file with both outputs, every row (start, cell, IMSI, LCID) has the same nRx.
    nRxNoRlcTag <= nRxZeroDelay; for RLC files nRxTagUnknown = 0; counters are non-decreasing per key.
 K4 O-5: lastSetCell = reportedCellId on every row; lastSetTimeNs < end.
 K5 O-3: counters non-decreasing per (rnti, lcid); 0 <= perPckToLte <= 1 when live.
Usage: check_r9_outputs.py <run_dir> [--json out]"""
import os, sys, json, argparse, collections
ap = argparse.ArgumentParser(); ap.add_argument("run"); ap.add_argument("--json"); a = ap.parse_args()
D = a.run; R = {}; bad = []
def rows(fn):
    with open(os.path.join(D, fn)) as f:
        for l in f:
            if l.startswith('%') or not l.strip(): continue
            yield l.rstrip('\n').split('\t')
# K1
um = collections.defaultdict(lambda: collections.OrderedDict())
for r in rows('R9_enb_uemap.txt'):
    t, c, rnti, imsi, st = int(r[0]), int(r[1]), int(r[2]), int(r[3]), int(r[4])
    um[c].setdefault(t, {})[imsi] = st
for c in sorted(um):  # make sure empty report instants are not lost: they have no rows, so count from cu-cp
    pass
k1 = {}
for c in sorted(um):
    fn = f'cu-cp-cell-{c}.txt'
    if not os.path.exists(os.path.join(D, fn)): k1[c] = 'no cu-cp file'; bad.append(f'K1 cell {c} (no cu-cp file)'); continue
    blocks = collections.OrderedDict()
    with open(os.path.join(D, fn)) as f:
        next(f)
        for l in f:
            x = l.split(',')
            if len(x) < 2 or not x[1].strip(): continue
            blocks.setdefault(x[0], set()).add(int(x[1]))
    B = list(blocks.values()); U = [set(v) for v in um[c].values()]
    # cu-cp writes no block when the list is empty; R9 writes no row either -> compare the non-empty sequences
    U = [u for u in U if u]
    n = min(len(B), len(U)); mism = [i for i in range(n) if B[i] != U[i]]
    k1[c] = {'cucp_blocks': len(B), 'r9_instants': len(U), 'compared': n, 'mismatch': len(mism), 'first': mism[:3]}
    if mism or abs(len(B) - len(U)) > 1 or n == 0: bad.append(f'K1 cell {c}')
R['K1'] = k1
# K2
ue = collections.defaultdict(list)
for r in rows('R9_ue_rrc.txt'): ue[int(r[0])].append(r)
allt = {t: {} for c in um for t in um[c]}
inst = collections.defaultdict(dict)
for c in um:
    for t, m in um[c].items(): inst[t][c] = m
k2 = {'instants': len(ue), 'connected_mm_rows': 0, 'not_in_enb_list': 0, 'examples': []}
for t, L in ue.items():
    for r in L:
        if r[7] == 'NA' or int(r[7]) != 9: continue
        k2['connected_mm_rows'] += 1; m = int(r[5]); imsi = int(r[1])
        if imsi not in inst.get(t, {}).get(m, {}):
            k2['not_in_enb_list'] += 1
            if len(k2['examples']) < 5: k2['examples'].append([t, imsi, m])
R['K2'] = k2
# K3
k3 = {}
for fn in sorted(os.listdir(D)):
    if not fn.endswith('_r9rx.txt'): continue
    base = fn[:-len('_r9rx.txt')]; pc = base + '_percell.txt'
    P = {}
    for r in rows(pc): P[(r[0], r[2], r[3], r[4])] = int(r[7])
    n = mis = tag = unk = mono = 0; last = {}
    isrlc = 'Rlc' in base
    for r in rows(fn):
        k = (r[0], r[2], r[3], r[4]); nRx, nZ, nNo, nU = map(int, r[5:9]); n += 1
        if P.get(k) != nRx: mis += 1
        if nNo > nZ: tag += 1
        if isrlc and nU != 0: unk += 1
        kk = k[1:]
        if kk in last and any(v < w for v, w in zip((nRx, nZ, nNo, nU), last[kk])): mono += 1
        last[kk] = (nRx, nZ, nNo, nU)
    # percell rows with nRx == 0 (send-only at that cell/window) legitimately have no r9rx row
    extra = len([k for k in set(P) - {(r[0], r[2], r[3], r[4]) for r in rows(fn)} if P[k] != 0])
    zero = sum(v[1] for v in last.values()); notag = sum(v[2] for v in last.values()); tot = sum(v[0] for v in last.values())
    k3[base] = {'rows': n, 'nRx_mismatch': mis, 'percell_rows_without_r9rx': extra, 'noTag_gt_zero': tag,
                'unknown_in_rlc': unk, 'non_monotone': mono, 'final_nRx': tot, 'final_zero': zero, 'final_noTag': notag}
    if mis or extra or tag or unk or mono or n == 0: bad.append(f'K3 {base}')
R['K3'] = k3
# K4
k4 = {}
for fn in sorted(os.listdir(D)):
    if not fn.endswith('_r9lastset.txt'): continue
    n = m = t = 0
    for r in rows(fn):
        n += 1
        if r[6] != r[7]: m += 1
        if int(r[4]) >= int(r[1]): t += 1
    k4[fn] = {'rows': n, 'cell_mismatch': m, 'time_not_before_end': t}
    if m or t or n == 0: bad.append(f'K4 {fn}')
R['K4'] = k4
# K5
last = {}; mono = rng = n = 0; live = 0
for r in rows('R9_pdcp_split.txt'):
    n += 1; k = (r[2], r[3]); v = tuple(map(int, r[4:8]))
    if k in last and any(x < y for x, y in zip(v, last[k])): mono += 1
    last[k] = v
    if r[8] == '1':
        live += 1; p = float(r[9])
        if not (0 <= p <= 1): rng += 1
R['K5'] = {'rows': n, 'keys': len(last), 'live_rows': live, 'non_monotone': mono, 'perPck_out_of_range': rng,
           'final_lte_sdus': sum(v[0] for v in last.values()), 'final_nr_sdus': sum(v[2] for v in last.values())}
if mono or rng or n == 0: bad.append('K5')
R['failed'] = bad
print(json.dumps(R, indent=1, ensure_ascii=False))
if a.json: json.dump(R, open(a.json, 'w'), indent=1, ensure_ascii=False)
sys.exit(1 if bad else 0)
