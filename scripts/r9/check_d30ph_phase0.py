#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""D-30PH 專用檢查（規格 docs/thesis/D30PH_collection_spec.md §4）。其餘檢查（Q-0／Q-4／P-3／P-5）沿用 check_d30p1_phase0.py／check_d30p_phase0.py。

  q2h <ph_aux> <d30h_aux> [PREFIX_SIMT]
      Q-2H：D-30PH（r11 ＋ FixedTtt，GCC 13）之 aux 與同 seed 之 D-30H（r8d，GCC 11，`data/ues30_ho_r8d_seeds`）：
        · 排除（與 2026-11-22 換手小型驗證之 G2′ 相同）：RLC 延遲相關檔（DlE2RlcStats{,Lte}{,_exact,_percell,_r9rx}、DlRlcStats）、
          R7b_rlc_rx_tag_hist、du-cell-*、*_r11eff；D-30H 所無之檔（r9 以後新增者）不比；mem_trace.tsv／run.log／meta.txt 不比。
        · 其餘檔須逐行相同（du-cell／cu-* 去牆鐘首欄；bsState 去第二欄）。唯一容忍：RxPacketTrace.txt 之 SINR(dB)（第 14 欄，index 13）
          ——GCC 11 與 GCC 13 之浮點輸出末位差（2026-11-22 小型驗證已證實僅此欄、最大差 1e-4；同編譯器參照則 0 差異）。
        · D-30H 有而 D-30PH 無之檔 → 失敗。
        · 追蹤檔最後一行若任一方未以換行結束（未 flush），差異記為註記而非失敗（只限最後一行）。
      PREFIX_SIMT（僅供自我檢查）：給定時，視為短跑對全長，採 p6_prefix.py 之結尾效應容許（差異不得早於 PREFIX_SIMT − 0.1 s）。
輸出 JSON；退出碼 0 通過、1 失敗。"""
import gzip, json, os, re, sys

EXCL = re.compile(r'^(DlE2RlcStats(Lte)?(_exact|_percell|_r9rx)?\.txt|DlRlcStats\.txt|R7b_rlc_rx_tag_hist\.txt|du-cell-[0-9]+\.txt|.*_r11eff\.txt)(\.gz)?$')
SKIP = {'mem_trace.tsv', 'run.log', 'meta.txt'}
AGG = {'DlPdcpStats.txt', 'DlRlcStats.txt', 'UlRlcStats.txt', 'R7b_rlc_rx_tag_hist.txt'}
FRAME = {'EnbSchedAllocTraces.txt', 'DlPhyTransmissionTrace.txt'}
SINR_COL = 13
TOL_SINR = True            # q2h：True（GCC 差異）；equal：False（同二進位，須逐位相同）


def op(p):
    return gzip.open(p, 'rt') if p.endswith('.gz') else open(p)


def base(fn):
    return fn[:-3] if fn.endswith('.gz') else fn


def norm(name, l):
    if re.match(r'(du-cell|cu-cp-cell|cu-up-cell)-', name):
        return l.split(',', 1)[1] if ',' in l else l
    if name.startswith('bsState'):
        f = l.split()
        return ' '.join(f[:1] + f[2:])
    if name == 'RxPacketTrace.txt' and TOL_SINR:
        f = l.rstrip('\n').split('\t')
        if len(f) > SINR_COL:
            f[SINR_COL] = '*'
        return '\t'.join(f)
    return l


def tline(name, l):
    tok = re.split(r'[\t, ]+', l.strip())
    for x in tok[:3]:
        try:
            v = float(x)
        except ValueError:
            continue
        if name in FRAME:
            return v * 0.01
        return v / 1e9 if v > 1e6 else v
    return None


def end_effect_ok(name, l, simt):
    if name in AGG:
        return True
    t = tline(name, l)
    if t is None:
        return False
    if re.match(r'D[lu]E2.*Lte', name) or name.startswith('UlE2'):
        return t >= simt - 1.0 - 1e-9
    return t >= simt - 0.1 - 1e-9


def find(d, fn):
    for c in (os.path.join(d, fn), os.path.join(d, base(fn)), os.path.join(d, base(fn) + '.gz')):
        if os.path.exists(c):
            return c
    return None


def compare(name, pa, pb, prefix_simt):
    a, b = op(pa), op(pb)
    n = 0
    note = None
    while True:
        la = a.readline()
        lb = b.readline()
        if la == '' and lb == '':
            return 'IDENTICAL' + (f' ({n} lines)' if n else ''), note, True
        n += 1
        if prefix_simt is not None and la == '' and lb != '':
            return f'PREFIX_OK ({n - 1} lines)', note, True          # 短跑對全長：短跑先結束
        if la == '' or lb == '':
            who = 'ph' if la == '' else 'ref'
            return f'LENGTH line {n}: {who} ended first', note, False
        if norm(name, la) == norm(name, lb):
            continue
        trunc = (not la.endswith('\n')) or (not lb.endswith('\n'))
        if trunc:                                                       # 只限最後一行（未 flush 之截斷）
            if a.readline() == '' and b.readline() == '':
                return f'IDENTICAL_EXCEPT_TRUNCATED_LAST_LINE ({n} lines)', 'last line truncated', True
        if prefix_simt is not None and end_effect_ok(name, la, prefix_simt):
            return f'END_EFFECT line {n}', note, True
        return f'DIFF line {n}: ph={la.strip()[:110]!r} ref={lb.strip()[:110]!r}', note, False


def q2h(ph, ref, prefix_simt=None):
    res, notes, bad = {}, {}, []
    for fn in sorted(os.listdir(ph)):
        b = base(fn)
        if b in SKIP or b.startswith('check_r9') or EXCL.match(fn):
            continue
        pr = find(ref, fn)
        if pr is None:
            continue                                                    # D-30H 所無（r9 以後新增）
        st, note, ok = compare(b, os.path.join(ph, fn), pr, prefix_simt)
        res[b] = st
        if note:
            notes[b] = note
        if not ok:
            bad.append(b)
    for fn in sorted(os.listdir(ref)):
        b = base(fn)
        if b in SKIP or EXCL.match(fn):
            continue
        if find(ph, fn) is None:
            res[b] = 'MISSING_IN_PH'
            bad.append(b)
    return {'check': 'Q-2H', 'pass': not bad, 'failed': bad, 'n_compared': len(res), 'notes': notes, 'files': res}


def equal(a, b):
    """確定性檢查：兩個 aux 目錄（同二進位、同命令列、同 seed）之全部檔案須逐位相同（同 q2h 之牆鐘欄處理，無 SINR 容忍、無排除清單）。"""
    global TOL_SINR
    TOL_SINR = False
    res, bad = {}, []
    names = {base(f) for f in os.listdir(a)} | {base(f) for f in os.listdir(b)}
    for n in sorted(names):
        if n in SKIP or n.startswith('check_r9'):
            continue
        pa, pb = find(a, n), find(b, n)
        if pa is None or pb is None:
            res[n] = 'MISSING_IN_' + ('A' if pa is None else 'B'); bad.append(n); continue
        st, _, ok = compare(n, pa, pb, None)
        res[n] = st
        if not ok:
            bad.append(n)
    return {'check': 'EQUAL', 'pass': not bad, 'failed': bad, 'n_compared': len(res), 'files': res}


if __name__ == '__main__':
    if len(sys.argv) >= 4 and sys.argv[1] == 'equal':
        r = equal(sys.argv[2], sys.argv[3])
        print(json.dumps(r, ensure_ascii=False, indent=1))
        sys.exit(0 if r['pass'] else 1)
    if len(sys.argv) < 4 or sys.argv[1] != 'q2h':
        raise SystemExit(__doc__)
    r = q2h(sys.argv[2], sys.argv[3], float(sys.argv[4]) if len(sys.argv) > 4 else None)
    print(json.dumps(r, ensure_ascii=False, indent=1))
    sys.exit(0 if r['pass'] else 1)
