#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""D-50PH 小型換手試跑之接收檢查與判讀（docs/thesis/D50PH_pilot_spec.md；結果出來前寫定，2026-11-23）。
用法：d50_pilot_report.py <pilot_dir> <ns3_dir>      pilot_dir 下：ho/、na/（各 4 seed）、det/（HO seed 4200 重複）
輸出 <pilot_dir>/decision.json 與標準輸出。退出碼 0＝有效且「明顯縮小」；2＝有效但非「明顯縮小」；1＝無效（任一接收檢查失敗）。"""
import gzip, json, os, subprocess, sys

PD, NS = sys.argv[1], sys.argv[2]
R9 = os.path.dirname(os.path.abspath(__file__))
SEEDS = (4200, 4201, 4202, 4203)
tag = lambda s: f'D50PH_ues50_t300_seed{s}'
aux = lambda arm, s: os.path.join(PD, arm, tag(s) + '_aux')


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


res = {'spec': 'D50PH_pilot_spec.md', 'checks': {}, 'fail': []}
for arm, seeds in (('ho', SEEDS), ('na', SEEDS), ('det', (4200,))):
    for s in seeds:
        k = f'{arm}_{s}'
        a = aux(arm, s)
        log = os.path.join(PD, arm, f'collect_{s}.log')
        ok_log = os.path.exists(log) and '✓ 通過' in open(log, errors='replace').read()      # K1–K5 與 N（50 IMSI／窗）
        rc0, j0 = run(['python3', f'{R9}/check_d30p1_phase0.py', 'q0', a, NS, '1'])
        rc4, j4 = run(['python3', f'{R9}/check_d30p1_phase0.py', 'q4', a])
        rc3, j3 = run(['python3', f'{R9}/check_d30p_phase0.py', 'p3', a])
        ok = ok_log and rc0 == 0 and rc4 == 0 and rc3 == 0
        res['checks'][k] = {'collector_K1K5_N': ok_log, 'Q0': rc0 == 0, 'Q4': rc4 == 0, 'P3': rc3 == 0}
        if not ok:
            res['fail'].append(k)
# 確定性：HO seed 4200 與其重複跑逐位相同
rce, je = run(['python3', f'{R9}/check_d30ph_phase0.py', 'equal', aux('ho', 4200), aux('det', 4200)])
res['determinism'] = {'pass': rce == 0, 'n_compared': je.get('n_compared'), 'failed': je.get('failed')}
if rce != 0:
    res['fail'].append('determinism')
# 換手次數（HO 臂須 > 0；NA 臂應為 0，僅報告）
hos = {}
for arm in ('ho', 'na'):
    for s in SEEDS:
        hos[f'{arm}_{s}'] = count_lines(os.path.join(aux(arm, s), 'EnbHandoverStartStats.txt'))
res['handover_starts'] = hos
if not all((hos[f'ho_{s}'] or 0) > 0 for s in SEEDS):
    res['fail'].append('handover_count')
# 長尾（W1 比值）
rct, jt = run(['python3', f'{R9}/analyze_d30ph_tail.py', os.path.join(PD, 'ho'), os.path.join(PD, 'na'), '--nwin', '30', '--nue', '50',
               '--seeds', ','.join(map(str, SEEDS)), '--out', os.path.join(PD, 'tail.json')])
tail = json.load(open(os.path.join(PD, 'tail.json'))) if os.path.exists(os.path.join(PD, 'tail.json')) else {}
res['tail'] = {k: tail.get(k) for k in ('pooled', 'ratio_W1_PH_over_P1', 'verdict', 'key_gaps_total')}
cov = (tail.get('pooled') or {}).get('PH', {}).get('coverage')
if cov is None or cov < 0.70:
    res['fail'].append('coverage_HO<0.70')
if (tail.get('key_gaps_total') or 0) != 0:
    res['fail'].append('key_gaps')
# 資源（報告）
res_use = {}
for arm in ('ho', 'na'):
    for s in SEEDS:
        p = os.path.join(aux(arm, s), 'mem_trace.tsv')
        if os.path.exists(p):
            rows = [l.split('\t') for l in open(p).read().splitlines()[1:] if l]
            res_use[f'{arm}_{s}'] = {'peak_rss_mb': max(int(r[2]) for r in rows), 'wall_s': int(rows[-1][0])}
res['resources'] = res_use
res['valid'] = not res['fail']
res['verdict'] = res['tail'].get('verdict')
json.dump(res, open(os.path.join(PD, 'decision.json'), 'w'), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
sys.exit(1 if not res['valid'] else (0 if res['verdict'] == '明顯縮小' else 2))
