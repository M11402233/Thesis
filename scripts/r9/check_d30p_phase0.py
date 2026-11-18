#!/usr/bin/env python3
"""Phase-2 step 0 acceptance checks on D-30P (docs/thesis/phase2_percell_spec_v0.md §6).  Read-only.
  p2 <d30p_aux> <d30p_main> <d30_aux> <d30_main>   P-2: every file D-30 has is bit-identical in D-30P (decompressed content;
        wall-clock first column of du-cell-*/cu-*-cell-* removed, as in report_semantics_spec_v0.md §5.9). mem_trace/run.log skipped.
  p3 <d30p_aux>    P-3: per (IMSI, LCID, window) and per counter, delta of sum over cells of *_percell = delta of *_exact (integers).
        RLC: both files are cumulative; a (cell, IMSI, LCID) row missing in a later window carries its last value (counted and reported).
        PDCP (decided 2026-11-18 from the 8 s r9 runs G21/G22, before any D-30P result): *_exact is reset after every report (E2 NR side
        effect, CLAUDE.md), so exact level is compared with the delta of the cumulative percell sum, per field.  P-3 pass/fail is decided
        by the RLC files only (the pipeline uses RLC); PDCP mismatches are reported per field, not hidden.
  p5 <d30p_aux>    P-5: every change of a UE's serving mmWave cell in O-1 (R9_ue_rrc mmCell; and the set of mmWave cells whose
        UeManager lists the IMSI in R9_enb_uemap) has an O-2 event (CellIdStats / MmWaveSwitchStats / Ue/EnbHandover*Stats /
        CellIdStatsHandover) of that IMSI and new cell in (t_prev, t_cur].  No threshold: mismatches are listed.
  p6 <short_aux> <full_aux>   P-6: for every common file, the short (31 s) run equals the full run up to the first line at sim t >= 29.9 s.
Prints one JSON object; exit 0 always for p5 (report only), exit 1 on failure for p2/p3/p6."""
import os, sys, gzip, json, collections

def opn(d, n):
    p = os.path.join(d, n)
    if os.path.exists(p): return open(p, 'rb')
    if os.path.exists(p + '.gz'): return gzip.open(p + '.gz', 'rb')
    return None
def names(d):
    return sorted({f[:-3] if f.endswith('.gz') else f for f in os.listdir(d)})
WALL = lambda n: n.startswith('du-cell-') or n.startswith('cu-cp-cell-') or n.startswith('cu-up-cell-')
SKIP = {'mem_trace.tsv', 'run.log', 'meta.txt', 'check_r9_outputs.json', 'check_r9_outputs.err'}
def lines(d, n):
    f = opn(d, n); L = f.read().split(b'\n'); f.close()
    if WALL(n): L = [l.split(b',', 1)[1] if b',' in l and not l.startswith(b'timestamp') else l for l in L]
    if n == 'bsState.txt': L = [b' '.join(l.split()[1:]) for l in L]
    return L

def p2(pa, pm, ra, rm):
    res = {}; bad = []
    a = open(pm, 'rb').read(); b = open(rm, 'rb').read()
    res['main'] = 'identical' if a == b else 'DIFF'; (a != b) and bad.append('main')
    for n in names(ra):
        if n in SKIP: continue
        if opn(pa, n) is None: res[n] = 'missing in D-30P'; bad.append(n); continue
        x, y = lines(pa, n), lines(ra, n)
        if x == y: res[n] = 'identical'
        else:
            i = next((k for k in range(min(len(x), len(y))) if x[k] != y[k]), min(len(x), len(y)))
            res[n] = 'DIFF at line %d (D-30P %d lines, D-30 %d lines)' % (i + 1, len(x), len(y)); bad.append(n)
    return {'check': 'P-2', 'pass': not bad, 'failed': bad, 'files': res}

PAIRS = ['DlE2RlcStats', 'DlE2RlcStatsLte', 'DlE2PdcpStats', 'DlE2PdcpStatsLte']
def table(d, n):
    f = opn(d, n)
    if f is None: return None
    out = []
    for l in f:
        l = l.decode()
        if l.startswith('%') or not l.strip(): continue
        r = l.split('\t'); out.append((int(r[0]), int(r[2]), int(r[3]), int(r[4]), tuple(int(v) for v in r[5:10])))
    f.close(); return out
def p3(pa):
    res = {}; ok = True
    for base in PAIRS:
        ex, pc = table(pa, base + '_exact.txt'), table(pa, base + '_percell.txt')
        if ex is None or pc is None: res[base] = 'file missing'; ok = False; continue
        starts = sorted({r[0] for r in ex} | {r[0] for r in pc})
        E = collections.defaultdict(dict); dupE = 0
        for s, c, i, l, v in ex:
            if (i, l) in E[s]: dupE += 1; E[s][(i, l)] = tuple(a + b for a, b in zip(E[s][(i, l)], v))
            else: E[s][(i, l)] = v
        P = collections.defaultdict(dict)
        for s, c, i, l, v in pc: P[s][(c, i, l)] = v
        last = {}; carried = 0; mism = []; nchk = 0
        prevE = {}; prevP = {}; interval = 'Pdcp' in base; fm = [0] * 5
        for s in starts:
            for k, v in P[s].items(): last[k] = v
            carried += sum(1 for k in last if k not in P[s])
            sumP = collections.defaultdict(lambda: (0,) * 5)
            for (c, i, l), v in last.items(): sumP[(i, l)] = tuple(a + b for a, b in zip(sumP[(i, l)], v))
            curE = dict(E[s]) if interval else {**prevE, **E[s]}
            for k in set(curE) | set(sumP):
                e, p = curE.get(k, (0,) * 5), sumP.get(k, (0,) * 5)
                de = e if interval else tuple(a - b for a, b in zip(e, prevE.get(k, (0,) * 5))); dp = tuple(a - b for a, b in zip(p, prevP.get(k, (0,) * 5)))
                nchk += 1
                for j in range(5): fm[j] += de[j] != dp[j]
                if de != dp and len(mism) < 20: mism.append({'start': s, 'imsi': k[0], 'lcid': k[1], 'd_exact': de, 'd_sum_percell': dp})
                elif de != dp: mism.append(None)
            prevE = curE; prevP = dict(sumP)
        nm = len(mism); res[base] = {'windows': len(starts), 'checked': nchk, 'mismatch': nm, 'examples': [m for m in mism if m][:20],
                                     'exact_duplicate_rows': dupE, 'percell_rows_carried': carried, 'exact_semantics': 'interval' if interval else 'cumulative',
                                     'mismatch_by_field': dict(zip(['nTx', 'TxBytes', 'nRx', 'RxBytes', 'delaySumNs'], fm)), 'counts_for_pass': not interval}
        if not interval: ok &= nm == 0
    return {'check': 'P-3', 'pass': ok, 'files': res}

def p5(pa):
    ev = collections.defaultdict(list)  # imsi -> [(t_s, cell, source)]
    def add(n, parse):
        f = opn(pa, n)
        if f is None: return 0
        k = 0
        for l in f:
            r = l.decode().split()
            if not r or r[0].startswith('%') or r[0].startswith('#'): continue
            try: t, imsi, cell = parse(r)
            except (ValueError, IndexError): continue
            ev[imsi].append((t, cell, n)); k += 1
        f.close(); return k
    cnt = {'CellIdStats.txt': add('CellIdStats.txt', lambda r: (float(r[0]), int(r[1]), int(r[2]))),
           'MmWaveSwitchStats.txt': add('MmWaveSwitchStats.txt', lambda r: (float(r[1]), int(r[2]), int(r[3]))),
           'CellIdStatsHandover.txt': add('CellIdStatsHandover.txt', lambda r: (float(r[0]), int(r[1]), int(r[2])))}
    for n in ['UeHandoverEndStats.txt', 'EnbHandoverEndStats.txt', 'UeHandoverStartStats.txt', 'EnbHandoverStartStats.txt']:
        f = opn(pa, n); cnt[n] = 0 if f is None else sum(1 for l in f if l.strip()); f and f.close()
    def changes(seq):  # imsi -> list of (t_ns, value)
        out = []
        for imsi, s in seq.items():
            s.sort()
            for (t0, v0), (t1, v1) in zip(s, s[1:]):
                if v1 != v0: out.append((imsi, t0, t1, v0, v1))
        return out
    ue = collections.defaultdict(list)
    f = opn(pa, 'R9_ue_rrc.txt')
    for l in f:
        l = l.decode()
        if l.startswith('%') or not l.strip(): continue
        r = l.split('\t'); ue[int(r[1])].append((int(r[0]), int(r[5])))
    f.close()
    um = collections.defaultdict(lambda: collections.defaultdict(set)); inst = set()
    f = opn(pa, 'R9_enb_uemap.txt')
    for l in f:
        l = l.decode()
        if l.startswith('%') or not l.strip(): continue
        r = l.split('\t'); t, c, imsi = int(r[0]), int(r[1]), int(r[3])
        if c != 1: um[imsi][t].add(c); inst.add(t)
    f.close()
    inst = sorted(inst)
    em = {imsi: [(t, tuple(sorted(d.get(t, set())))) for t in inst] for imsi, d in um.items()}
    def match(chs, newcells):
        unm = []
        for imsi, t0, t1, v0, v1 in chs:
            need = newcells(v1)
            if not need: continue
            ok = any(t0 / 1e9 < t <= t1 / 1e9 + 1e-9 and c in need for t, c, _ in ev.get(imsi, []))
            if not ok: unm.append({'imsi': imsi, 't_prev_s': t0 / 1e9, 't_cur_s': t1 / 1e9, 'from': v0, 'to': v1})
        return unm
    c1 = changes(ue); u1 = match(c1, lambda v: {v} if v else set())
    c2 = changes(em); u2 = match(c2, lambda v: set(v))
    return {'check': 'P-5', 'pass': None, 'o2_event_counts': cnt,
            'ue_rrc_mmcell_changes': len(c1), 'ue_rrc_to_zero': sum(1 for x in c1 if x[4] == 0), 'ue_rrc_unmatched': len(u1), 'ue_rrc_unmatched_list': u1[:50],
            'uemap_set_changes': len(c2), 'uemap_to_empty': sum(1 for x in c2 if not x[4]), 'uemap_unmatched': len(u2), 'uemap_unmatched_list': u2[:50]}

def tfirst(l):
    for tok in l.replace(b',', b' ').replace(b'\t', b' ').split()[:3]:
        try: v = float(tok)
        except ValueError: continue
        return v / 1e9 if v > 1e6 else v
    return None
def p6(sa, fa):
    res = {}; bad = []
    for n in sorted(set(names(sa)) & set(names(fa))):
        if n in SKIP: continue
        x, y = lines(sa, n), lines(fa, n)
        i = next((k for k in range(min(len(x), len(y))) if x[k] != y[k]), None)
        if i is None: res[n] = 'prefix identical (%d lines)' % len(x); continue
        t = tfirst(x[i])
        if t is not None and t >= 29.9: res[n] = 'identical before t=%.3f s (line %d)' % (t, i + 1)
        else: res[n] = 'DIFF at line %d, t=%s' % (i + 1, t); bad.append(n)
    return {'check': 'P-6', 'pass': not bad, 'failed': bad, 'files': res}

if __name__ == '__main__':
    c = sys.argv[1]
    r = {'p2': lambda: p2(*sys.argv[2:6]), 'p3': lambda: p3(sys.argv[2]), 'p5': lambda: p5(sys.argv[2]), 'p6': lambda: p6(*sys.argv[2:4])}[c]()
    print(json.dumps(r, indent=1, default=str))
    sys.exit(0 if r['pass'] in (True, None) else 1)
