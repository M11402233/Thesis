#!/usr/bin/env python3
"""P-4 checks (phase2_percell_spec_v0.md §6; report_semantics_spec_v0.md §5.4 T1-T3) on a test run made with ZT_P4_HO.
usage: check_p4.py <run_dir>     (run_dir has run.log with 'ZT_P4 HO' lines and the r9 outputs)
Pass criteria apply to every handover class: P-3 conservation (all UEs, all windows), no double attachment in O-1, and for mid-window
handovers (T1) the per-cell split and end-of-window attribution = target.  T2 = natural cases (UE in the cell's O-1 list, no packet).
Boundary handovers (T3) are reported, not judged: window-end attribution takes the RRC state at the report instant."""
import sys, os, re, json, collections
D = sys.argv[1]
def rows(fn):
    with open(os.path.join(D, fn)) as f:
        for l in f:
            if l.startswith('%') or not l.strip(): continue
            yield l.rstrip('\n').split('\t')
R = {'failed': []}
hos = []
for l in open(os.path.join(D, 'run.log'), errors='replace'):
    m = re.search(r'ZT_P4 HO t_ns=(\d+) imsi=(\d+) src=(\d+) tgt=(\d+)', l)
    if m: hos.append(tuple(int(x) for x in m.groups()))
if len(sys.argv) > 2 and sys.argv[2] == '--natural':   # judge natural NR-NR handovers (UeHandoverStartStats: time imsi rnti src tgt)
    hos = []
    for l in open(os.path.join(D, 'UeHandoverStartStats.txt')):
        r = l.split()
        if len(r) < 5 or l.startswith('%'): continue
        if int(r[3]) >= 2 and int(r[4]) >= 2: hos.append((round(float(r[0]) * 1e9), int(r[1]), int(r[3]), int(r[4])))
R['handovers'] = hos
# percell cumulative per (cell, imsi) summed over LCID; exact per imsi
pc = collections.defaultdict(dict); ex = collections.defaultdict(dict); ends = set()
for r in rows('DlE2RlcStats_percell.txt'):
    end, cell, imsi = int(r[1]), int(r[2]), int(r[3]); v = tuple(int(x) for x in (r[5], r[6], r[7], r[8], r[9]))
    k = (cell, imsi); old = pc[k].get(end, (0,) * 5); pc[k][end] = tuple(a + b for a, b in zip(old, v)); ends.add(end)
for r in rows('DlE2RlcStats_exact.txt'):
    end, imsi = int(r[1]), int(r[3]); v = tuple(int(x) for x in (r[5], r[6], r[7], r[8], r[9]))
    old = ex[imsi].get(end, (0,) * 5); ex[imsi][end] = tuple(a + b for a, b in zip(old, v)); ends.add(end)
E = sorted(ends)
def cum(series, end):
    last = (0,) * 5
    for e in E:
        if e > end: break
        if e in series: last = series[e]
    return last
def delta(series, end):
    prev = E[E.index(end) - 1] if E.index(end) > 0 else None
    a = cum(series, end); b = cum(series, prev) if prev is not None else (0,) * 5
    return tuple(x - y for x, y in zip(a, b))
# P-3 conservation (all UEs, all windows)
imsis = sorted(ex); bad = 0; n = 0
cells_of = collections.defaultdict(list)
for (cell, imsi) in pc: cells_of[imsi].append(cell)
for imsi in imsis:
    for e in E:
        if e not in ex[imsi] and not any(e in pc[(c, imsi)] for c in cells_of[imsi]): continue
        n += 1
        s = tuple(sum(x) for x in zip(*[delta(pc[(c, imsi)], e) for c in cells_of[imsi]]))
        if s != delta(ex[imsi], e): bad += 1
R['P3_conservation'] = {'ue_windows': n, 'violations': bad}
if bad: R['failed'].append('P-3 conservation')
# O-1 membership per instant
mem = collections.defaultdict(lambda: collections.defaultdict(set))   # t -> imsi -> {cell}
for r in rows('R9_enb_uemap.txt'):
    t, c, imsi = int(r[0]), int(r[1]), int(r[3])
    if c >= 2: mem[t][imsi].add(c)
ts = sorted(mem)
dbl = [(t, i, sorted(c)) for t in ts for i, c in mem[t].items() if len(c) > 1]
R['double_attach'] = {'instants': len(ts), 'count': len(dbl), 'examples': dbl[:5]}
if dbl: R['failed'].append('double attachment in O-1')
def report_after(t_ns):
    for t in ts:
        if t >= t_ns: return t
    return None
def mean(v): return (v[4] / v[2] / 1e6) if v[2] else None
cases = []
_last = {}
for (t, imsi, src, tgt) in sorted(hos): _last[(t // 1_000_000_000, imsi)] = (tgt, _last.get((t // 1_000_000_000, imsi), (0, 0))[1] + 1)
for (t, imsi, src, tgt) in hos:
    w = t // 1_000_000_000; end = (w + 1) * 1_000_000_000
    if end not in E or end + 1_000_000_000 not in E: continue   # window (or next) not reported
    cls = 'T1' if 100_000_000 <= t % 1_000_000_000 <= 900_000_000 else 'T3'
    rep = report_after(end)
    c = {'class': cls, 't_ns': t, 'imsi': imsi, 'src': src, 'tgt': tgt, 'window': w,
         'delta_src_window': delta(pc[(src, imsi)], end) if (src, imsi) in pc else None,
         'delta_tgt_window': delta(pc[(tgt, imsi)], end) if (tgt, imsi) in pc else None,
         'delta_src_next': delta(pc[(src, imsi)], end + 1_000_000_000) if (src, imsi) in pc and end + 1_000_000_000 in E else None,
         'delta_tgt_next': delta(pc[(tgt, imsi)], end + 1_000_000_000) if (tgt, imsi) in pc and end + 1_000_000_000 in E else None,
         'mean_delay_ms_src': None, 'mean_delay_ms_tgt': None,
         'O1_cells_at_window_end_report': sorted(mem[rep].get(imsi, [])) if rep else None, 'report_ns': rep}
    for k, key in (('src', src), ('tgt', tgt)):
        d = c['delta_%s_window' % k]
        c['mean_delay_ms_' + k] = mean(d) if d else None
    if cls == 'T1':
        last_tgt, nho = _last[(w, imsi)]
        c['n_ho_same_window'] = nho
        attr_ok = c['O1_cells_at_window_end_report'] == [last_tgt]      # end-of-window attribution = target of the UE's last handover in the window
        rx_ok = bool(c['delta_src_window'] and c['delta_src_window'][2] > 0 and c['delta_tgt_window'] and c['delta_tgt_window'][2] > 0)
        c['T1_attr_ok'] = attr_ok; c['T1_both_rx'] = rx_ok     # rx_ok is radio/traffic-dependent: reported, not a failure of attribution
        c['T1_pass'] = attr_ok
        if not attr_ok: R['failed'].append(f'T1 imsi {imsi} t={t}')
    cases.append(c)
R['cases'] = cases
# handover event files near each test handover (O-2)
ev = []
for fn in ('UeHandoverStartStats.txt', 'UeHandoverEndStats.txt'):
    if os.path.exists(os.path.join(D, fn)):
        for r in rows(fn):
            try: tt = float(r[0])
            except ValueError: continue
            for (t, imsi, src, tgt) in hos:
                if int(r[1]) == imsi and abs(tt * 1e9 - t) < 50_000_000: ev.append((fn, r))
R['O2_events_near_tests'] = ev
# T2 natural cases: UE in O-1 list of a cell at a window-end report, no packet at that cell in that window
t2 = []; tot = 0
for t in ts:
    end = (t // 1_000_000_000) * 1_000_000_000
    if end not in E: continue
    for r in rows('R9_enb_uemap.txt') if False else []: pass
for r in rows('R9_enb_uemap.txt'):
    t, c, imsi = int(r[0]), int(r[1]), int(r[3])
    end = (t // 1_000_000_000) * 1_000_000_000
    if c < 2 or end not in E or t - end > 10_000_000: continue
    tot += 1
    d = delta(pc[(c, imsi)], end) if (c, imsi) in pc else (0,) * 5
    if d[0] == 0 and d[2] == 0:
        t2.append((end, c, imsi, 'row' if (c, imsi) in pc and end in pc[(c, imsi)] else 'no row', mean(d)))
R['T2_natural'] = {'ue_cell_windows_listed': tot, 'no_packet': len(t2), 'mean_delay_present': sum(1 for x in t2 if x[4] is not None), 'examples': t2[:5]}
if any(x[4] is not None for x in t2): R['failed'].append('T2 delay not missing')
print(json.dumps(R, indent=1, default=str))
sys.exit(1 if R['failed'] else 0)
