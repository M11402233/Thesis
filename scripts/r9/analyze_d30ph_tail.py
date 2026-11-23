#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""D-30PH 長尾判讀（docs/thesis/D30PH_collection_spec.md §6a；資料出來前寫定，2026-11-23）。只讀，輸出 JSON 到 stdout 或 --out。

單位＝(UE, 窗)，只用 mmWave cell（cell ≠ 1）之 DlE2RlcStats_r11eff：每 (cell, IMSI, LCID) 為自 t=0 之累計 (nEff, delaySumEffNs)，
逐窗差分（每鍵每窗皆有列，已查：換手與不換手皆無跳窗）；同一 UE 同一窗各 mmWave cell 之差分相加；ΔnEff > 0 者為有效 (UE, 窗)，
其區間平均延遲 = ΣΔdelaySumEff ÷ ΣΔnEff。
  W1 = 有效 (UE, 窗) 中區間平均 > 1 s 之比例（主指標）
  W2 = 有效 (UE, 窗) 中區間平均 > 30 s 之個數
  W3 = 區間平均最大值（秒）
  C  = 有效 (UE, 窗) 占 30 UE × 窗數之比例（覆蓋）
判準（D-30PH 對 D-30P1，同 8 seed、窗 0–299，8 seed 合併）：比值 W1(PH)／W1(P1) ≤ 0.2 → 「明顯縮小」；≥ 1.5 → 「變大」；其餘 → 「無明顯差異」。
W2、W3 只報告。注意：此為 (UE, 窗) 層級之比例，與小型驗證之逐封包比例單位不同，兩者不可直接比較。

用法：analyze_d30ph_tail.py <ph_dir> <p1_dir> [--nwin 300] [--seeds 4200,...] [--out file]
  ph_dir／p1_dir 下為 <VAR>_ues30_t300_seed<s>_aux/DlE2RlcStats_r11eff.txt（VAR = D30PH／D30P1）；--self 可用其他目錄配置（乾跑用）。"""
import argparse, collections as Co, gzip, json, os, sys

LTE = 1


def op(p):
    return gzip.open(p, 'rt') if p.endswith('.gz') else open(p)


def ue_windows(p, nwin):
    cum = Co.defaultdict(dict)                           # (cell, imsi, lcid) -> {k: (nEff, sumNs)}
    for l in op(p):
        if l.startswith('%'):
            continue
        f = l.rstrip('\n').split('\t')
        k = int(f[0]) // 1000000000
        if k >= nwin or int(f[2]) == LTE:
            continue
        cum[(int(f[2]), int(f[3]), int(f[4]))][k] = (int(f[9]), int(f[10]))
    agg = Co.defaultdict(lambda: [0, 0])                 # (imsi, k) -> [ΣΔn, ΣΔsum]
    gaps = 0
    for key, d in cum.items():
        prev, pk = (0, 0), None
        for k in sorted(d):
            if pk is not None and k != pk + 1:
                gaps += 1
            v = d[k]
            dn, ds = v[0] - prev[0], v[1] - prev[1]
            if dn < 0 or ds < 0:
                raise SystemExit(f'非單調 {p} {key} k={k}')
            a = agg[(key[1], k)]; a[0] += dn; a[1] += ds
            prev, pk = v, k
    return agg, gaps


def metrics(agg, nue, nwin):
    m = [s / n / 1e9 for (n, s) in agg.values() if n > 0]
    return {'n_eff_ue_win': len(m), 'coverage': len(m) / (nue * nwin), 'W1_gt1s': sum(x > 1 for x in m) / len(m) if m else None,
            'W2_gt30s': sum(x > 30 for x in m), 'W3_max_s': max(m) if m else None}


def find(d, s):
    for v in ('D30PH', 'D30P1'):
        p = os.path.join(d, f'{v}_ues30_t300_seed{s}_aux', 'DlE2RlcStats_r11eff.txt')
        if os.path.exists(p):
            return p
    raise SystemExit(f'找不到 seed {s} 之 r11eff 於 {d}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ph'); ap.add_argument('p1')
    ap.add_argument('--nwin', type=int, default=300); ap.add_argument('--seeds', default='4200,4201,4202,4203,4204,4205,4206,4207')
    ap.add_argument('--self', nargs=2, metavar=('PH_FILE_FMT', 'P1_FILE_FMT'), help='乾跑：以 {s} 代 seed 之完整路徑格式')
    ap.add_argument('--out')
    a = ap.parse_args()
    seeds = [int(x) for x in a.seeds.split(',')]
    res = {'spec': 'D30PH_collection_spec.md §6a', 'nwin': a.nwin, 'seeds': seeds, 'per_seed': {}}
    pool = {'PH': {}, 'P1': {}}
    for s in seeds:
        r = {}
        for lab, d, fmt in (('PH', a.ph, a.self[0] if a.self else None), ('P1', a.p1, a.self[1] if a.self else None)):
            p = fmt.format(s=s) if fmt else find(d, s)
            agg, gaps = ue_windows(p, a.nwin)
            r[lab] = dict(metrics(agg, 30, a.nwin), key_gaps=gaps, file=p)
            pool[lab].update({(s,) + k: v for k, v in agg.items()})
        res['per_seed'][s] = r
    P = {lab: metrics(v, 30 * len(seeds), a.nwin) for lab, v in pool.items()}
    res['pooled'] = P
    w_ph, w_p1 = P['PH']['W1_gt1s'], P['P1']['W1_gt1s']
    ratio = None if not w_p1 else w_ph / w_p1
    res['ratio_W1_PH_over_P1'] = ratio
    res['verdict'] = ('無法判定（P1 之 W1 = 0）' if ratio is None else '明顯縮小' if ratio <= 0.2 else '變大' if ratio >= 1.5 else '無明顯差異')
    res['key_gaps_total'] = sum(r[l]['key_gaps'] for r in res['per_seed'].values() for l in ('PH', 'P1'))
    out = json.dumps(res, ensure_ascii=False, indent=1, default=str)
    if a.out:
        open(a.out, 'w').write(out)
    print(out if not a.out else json.dumps({k: res[k] for k in ('pooled', 'ratio_W1_PH_over_P1', 'verdict', 'key_gaps_total')}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
