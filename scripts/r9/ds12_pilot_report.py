#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""D-S12（12 UE）小型試跑之接收檢查（docs/thesis/DS12_pilot_spec.md；結果出來前寫定，2026-11-26）。
用法：ds12_pilot_report.py <pilot_dir> <ns3_dir>      pilot_dir 下：ho/（seed 4200、4201）、det/（seed 4200 重複）
輸出 <pilot_dir>/decision.json 與標準輸出。退出碼 0＝全部接收檢查通過；1＝任一失敗（停止回報，不調參數）。
只讀 pilot_dir；只寫 <pilot_dir>/decision.json、tail.json。"""
import collections, gzip, json, os, subprocess, sys

PD, NS = sys.argv[1], sys.argv[2]
R9 = os.path.dirname(os.path.abspath(__file__))
N, NWIN = 12, 30
SEEDS = (4200, 4201)
tag = lambda s: f'DS12_ues12_t300_seed{s}'
aux = lambda arm, s: os.path.join(PD, arm, tag(s) + '_aux')
main = lambda arm, s: os.path.join(PD, arm, tag(s) + '.txt')


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    try:
        j = json.loads(p.stdout)
    except Exception:
        j = {'raw': p.stdout[-300:], 'err': p.stderr[-300:]}
    return p.returncode, j


def count_lines(p):
    for c in (p, p + '.gz'):
        if os.path.exists(c):
            op = gzip.open if c.endswith('.gz') else open
            with op(c, 'rt') as f:
                return sum(1 for l in f if l.strip() and not l.startswith('%'))
    return None


res = {'spec': 'DS12_pilot_spec.md', 'checks': {}, 'fail': []}
for arm, seeds in (('ho', SEEDS), ('det', (4200,))):
    for s in seeds:
        k = f'{arm}_{s}'
        a = aux(arm, s)
        log = os.path.join(PD, arm, f'collect_{s}.log')
        ok_log = os.path.exists(log) and '✓ 通過' in open(log, errors='replace').read()      # K1–K5 與 N（12 IMSI／窗）
        rc0, j0 = run(['python3', f'{R9}/check_d30p1_phase0.py', 'q0', a, NS, '1'])
        rc4, j4 = run(['python3', f'{R9}/check_d30p1_phase0.py', 'q4', a])
        rc3, j3 = run(['python3', f'{R9}/check_d30p_phase0.py', 'p3', a])
        ok = ok_log and rc0 == 0 and rc4 == 0 and rc3 == 0
        res['checks'][k] = {'collector_K1K5_N': ok_log, 'Q0': rc0 == 0, 'Q4': rc4 == 0, 'P3': rc3 == 0}
        if not ok:
            res['fail'].append(k)
# 確定性：seed 4200 與其重複跑逐位相同（同機器、同二進位）
rce, je = run(['python3', f'{R9}/check_d30ph_phase0.py', 'equal', aux('ho', 4200), aux('det', 4200)])
res['determinism'] = {'pass': rce == 0, 'n_compared': je.get('n_compared'), 'failed': je.get('failed')}
if rce != 0:
    res['fail'].append('determinism')
# 換手次數
hos = {f'ho_{s}': count_lines(os.path.join(aux('ho', s), 'EnbHandoverStartStats.txt')) for s in SEEDS}
res['handover_starts'] = hos
if not all((v or 0) > 0 for v in hos.values()):
    res['fail'].append('handover_count')
# 覆蓋率、跳窗（analyze_d30ph_tail 需兩個目錄；兩者皆給 ho，只取 PH 之覆蓋率與 key_gaps；W1 僅供參考）
rct, _ = run(['python3', f'{R9}/analyze_d30ph_tail.py', os.path.join(PD, 'ho'), os.path.join(PD, 'ho'), '--nwin', str(NWIN), '--nue', str(N),
              '--seeds', ','.join(map(str, SEEDS)), '--out', os.path.join(PD, 'tail.json')])
tail = json.load(open(os.path.join(PD, 'tail.json'))) if os.path.exists(os.path.join(PD, 'tail.json')) else {}
ph = (tail.get('pooled') or {}).get('PH', {})
res['tail'] = {'PH_pooled': ph, 'key_gaps_total': tail.get('key_gaps_total'), 'note': 'W1 僅供參考（無 na 臂，不作判準）'}
if ph.get('coverage') is None or ph['coverage'] < 0.70:
    res['fail'].append('coverage<0.70')
if (tail.get('key_gaps_total') or 0) != 0:
    res['fail'].append('key_gaps')
# 資源（報告，非門檻）：RSS、牆鐘；輸出大小
use = {}
for s in SEEDS:
    p = os.path.join(aux('ho', s), 'mem_trace.tsv')
    if os.path.exists(p):
        rows = [l.split('\t') for l in open(p).read().splitlines()[1:] if l]
        use[f'ho_{s}'] = {'peak_rss_mb': max(int(r[2]) for r in rows), 'wall_s': int(rows[-1][0]), 'n_samples': len(rows)}
    sz = 0
    for d in (aux('ho', s),):
        for fn in os.listdir(d):
            sz += os.path.getsize(os.path.join(d, fn))
    use.setdefault(f'ho_{s}', {})['aux_bytes'] = sz
res['resources'] = use
# 可用 peer 之分布（報告，非門檻）：每 (cell, 窗) 之 UE 數
dist = {}
for s in SEEDS:
    cw = collections.defaultdict(set)
    for l in open(main('ho', s)):
        if l.startswith('%'):
            continue
        p = l.split('\t')
        try:
            cw[(int(float(p[0])), int(p[2]))].add(int(p[3]))
        except (ValueError, IndexError):
            pass
    cnt = collections.Counter(len(v) for v in cw.values())
    dist[f'ho_{s}'] = {'n_cell_windows': len(cw), 'ue_per_cell_window_hist': dict(sorted(cnt.items())),
                       'share_lt2': sum(c for k, c in cnt.items() if k < 2) / max(1, len(cw)),
                       'share_lt3': sum(c for k, c in cnt.items() if k < 3) / max(1, len(cw))}
res['ue_per_cell_window'] = dist
res['valid'] = not res['fail']
json.dump(res, open(os.path.join(PD, 'decision.json'), 'w'), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
sys.exit(0 if res['valid'] else 1)
