#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_r10.py — r10 小型驗證之檢查（2026-11-20；驗證用，不得作為論文資料）
 R-0  mode0 之 RLC 統計檔（start < K s 之列）與 D-30P seed 4200 逐位相同（r10 預設 == r9-g13）；RxPacketTrace 前綴相同
 R-1  mode1／2 與 mode0：非延遲輸出檔 md5 全同；含延遲之 RLC 統計檔只准 delaySumNs 欄不同（nTx/TxBytes/nRx/RxBytes 全同）
 R-2  delaySumNs 只增不減；增量 > 0 之列必為 mode0 之 nRxZeroDelay > 0 之列
 R-3  報告：殘留零延遲／無時間戳 PDU 數、原零延遲 PDU 之平均延遲分佈 vs 原有時間戳 PDU、RSS
 I-1  （資訊，不得引用）20 窗內三種 cell 值定義之空間乾淨誤報（以同窗資料自身 MAD 尺度，in-sample）
任一 R 檢查失敗：exit 1。"""
import os, sys, gzip, hashlib, collections, json
import numpy as np

K = 20
NS = 10**9
OUT = os.path.expanduser("~/oran-zt-kpm-verification/data/r10_validation")
REF = os.path.expanduser("~/oran-zt-kpm-verification/data/ues30_p_r9g13_seeds/D30P_ues30_t300_seed4200_aux")
RLC = ["DlE2RlcStats.txt", "DlE2RlcStats_exact.txt", "DlE2RlcStats_percell.txt", "DlE2RlcStats_r9rx.txt",
       "DlE2RlcStatsLte.txt", "DlE2RlcStatsLte_exact.txt", "DlE2RlcStatsLte_percell.txt", "DlE2RlcStatsLte_r9rx.txt"]
fails = []


def rows(path, k=K):
    op = gzip.open if path.endswith(".gz") else open
    out = []
    with op(path, "rt") as fh:
        for ln in fh:
            if ln.startswith("%") or not ln.strip():
                continue
            p = ln.rstrip("\n").split("\t")
            if p[0].lstrip("-").isdigit() and int(p[0]) < k * NS:
                out.append(ln)
    return out


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def tab(path):
    return [ln.rstrip("\n").split("\t") for ln in rows(path)]


# ---------- R-0
print("R-0  mode0 vs D-30P（start < %d s）" % K)
for f in [x for x in RLC if x not in ("DlE2RlcStats.txt", "DlE2RlcStatsLte.txt")]:  # 主檔列格式不同／REF 為 .gz，不比
    a = rows(os.path.join(OUT, "mode0", f)); b = rows(os.path.join(REF, f))
    ok = a == b and len(a) > 0
    print(f"   {f:34s} 列 {len(a):6d} / {len(b):6d}  {'相同' if ok else '✗ 不同'}")
    if not ok:
        fails.append(f"R-0 {f}")
# RxPacketTrace：時間 < K-1 秒之列（simTime 21 與 301 之結尾差異不比）
def trace_rows(path, tmax):
    op = gzip.open if path.endswith(".gz") else open
    out = []
    with op(path, "rt") as fh:
        for ln in fh:
            p = ln.split("\t", 3)
            if len(p) > 2 and p[0] in ("DL", "UL"):
                if float(p[1]) >= tmax:
                    break
                out.append(ln)
    return out
a = trace_rows(os.path.join(OUT, "mode0", "RxPacketTrace.txt"), K - 1)
b = trace_rows(os.path.join(REF, "RxPacketTrace.txt.gz"), K - 1)
ok = a == b and len(a) > 0
print(f"   RxPacketTrace（時間 < {K-1} s）列 {len(a)} / {len(b)}  {'相同' if ok else '✗ 不同'}")
if not ok:
    fails.append("R-0 RxPacketTrace")

# ---------- R-1／R-2／R-3
res = {}
for m in (1, 2):
    d0, dm = os.path.join(OUT, "mode0"), os.path.join(OUT, f"mode{m}")
    print(f"\nmode{m} vs mode0")
    names = sorted(n for n in os.listdir(d0) if os.path.isfile(os.path.join(d0, n)) and n != "run.log")
    diff = [n for n in names if not os.path.exists(os.path.join(dm, n)) or md5(os.path.join(d0, n)) != md5(os.path.join(dm, n))]
    unexpected = [n for n in diff if n not in RLC and n not in ("DlRlcStats.txt", "R7b_rlc_rx_tag_hist.txt")
                  and not n.startswith("du-cell-")]
    # 含延遲之衍生檔：只准指定欄不同（判準事前固定）
    for n in diff:
        pa = os.path.join(d0, n); pb = os.path.join(dm, n)
        if n.startswith("du-cell-"):
            A_ = open(pa).read().splitlines(); B_ = open(pb).read().splitlines()
            hdr = A_[0].split(","); cols = set()
            bad = len(A_) != len(B_)
            for x, y in zip(A_[1:], B_[1:]):
                x = x.split(","); y = y.split(",")
                if len(x) != len(y):
                    bad = True; continue
                cols |= {hdr[i] for i, (u, v) in enumerate(zip(x, y)) if u != v}
            if bad or not cols <= {"DRB.UEThpDl.UEID"}:
                unexpected.append(f"{n}:{sorted(cols)}")
        elif n == "DlRlcStats.txt":
            A_ = open(pa).read().splitlines(); B_ = open(pb).read().splitlines()
            cols = set(); bad = len(A_) != len(B_)
            for x, y in zip(A_[1:], B_[1:]):
                x = x.split("\t"); y = y.split("\t")
                if len(x) != len(y):
                    bad = True; continue
                cols |= {i for i, (u, v) in enumerate(zip(x, y)) if u != v}
            if bad or not cols <= {10, 11, 12, 13}:
                unexpected.append(f"{n}:{sorted(cols)}")
        elif n == "R7b_rlc_rx_tag_hist.txt":
            tot = lambda q: sum(int(l.split("\t")[3]) for l in open(q) if l and not l.startswith("%"))
            if tot(pa) != tot(pb):
                unexpected.append(f"{n}: total {tot(pa)} vs {tot(pb)}")
    print(f"   檔案 {len(names)}；md5 不同 {len(diff)}：{diff}")
    if unexpected:
        print(f"   ✗ 非延遲檔不同：{unexpected}"); fails.append(f"R-1 mode{m} {unexpected}")
    # percell：欄位比對
    A = tab(os.path.join(d0, "DlE2RlcStats_percell.txt")); B = tab(os.path.join(dm, "DlE2RlcStats_percell.txt"))
    Z = {tuple(r[:5]): r for r in tab(os.path.join(d0, "DlE2RlcStats_r9rx.txt"))}
    Z1 = {tuple(r[:5]): r for r in tab(os.path.join(dm, "DlE2RlcStats_r9rx.txt"))}
    assert [r[:5] for r in A] == [r[:5] for r in B], "鍵不同"
    bad_cols = bad_dec = bad_pos = 0
    prev0 = {}; prevm = {}
    newz = []; oldv = []
    nz0 = nzm = nt0 = ntm = nrx = 0
    for ra, rb in zip(A, B):
        key = tuple(ra[:5])
        if ra[5:9] != rb[5:9]:
            bad_cols += 1
        ds0 = int(ra[9]); dsm = int(rb[9])
        # 累計 → 區間
        i0 = ds0 - prev0.get(key[2:], 0); im = dsm - prevm.get(key[2:], 0)
        prev0[key[2:]] = ds0; prevm[key[2:]] = dsm
        if im < i0:
            bad_dec += 1
    # 以累計 delaySum 與 r9rx 之累計 nZero 求逐 (cell,UE,LCID) 之總量
    last = {}
    for ra, rb in zip(A, B):
        last[tuple(ra[2:5])] = (ra, rb)
    lastz = {}
    for r in tab(os.path.join(d0, "DlE2RlcStats_r9rx.txt")):
        lastz[tuple(r[2:5])] = r
    lastz1 = {}
    for r in tab(os.path.join(dm, "DlE2RlcStats_r9rx.txt")):
        lastz1[tuple(r[2:5])] = r
    tot_nrx = tot_z0 = tot_zm = tot_nt0 = tot_ntm = 0
    mean_new_zero = []; mean_tagged = []
    for k, (ra, rb) in last.items():
        if k[0] == "1":
            continue
        n_rx = int(ra[7]); ds0 = int(ra[9]); dsm = int(rb[9])
        z0 = int(lastz[k][6]); zm = int(lastz1[k][6]); t0 = int(lastz[k][7]); tm = int(lastz1[k][7])
        tot_nrx += n_rx; tot_z0 += z0; tot_zm += zm; tot_nt0 += t0; tot_ntm += tm
        if dsm < ds0:
            bad_dec += 1
        if dsm > ds0 and z0 == 0:
            bad_pos += 1
        if z0 > 0:
            mean_new_zero.append((dsm - ds0) / z0 / 1e6)          # 原零延遲 PDU 之平均延遲 ms
        if n_rx - z0 > 0:
            mean_tagged.append(ds0 / (n_rx - z0) / 1e6)           # 原有時間戳 PDU 之平均延遲 ms
    print(f"   percell 非延遲欄不同之列 {bad_cols}；delaySum 減少 {bad_dec}；增量 > 0 但 mode0 無零延遲之 (cell,UE) {bad_pos}")
    for nm, v in (("R-1 non-delay cols", bad_cols), ("R-2 decrease", bad_dec), ("R-2 pos-without-zero", bad_pos)):
        if v:
            fails.append(f"{nm} mode{m}={v}")
    mz = np.array(mean_new_zero); mt = np.array(mean_tagged)
    print(f"   mmWave 累計 nRx {tot_nrx}；零延遲 mode0 {tot_z0}（{tot_z0/tot_nrx:.4f}）→ mode{m} {tot_zm}（{tot_zm/tot_nrx:.4f}）；"
          f"無時間戳 mode0 {tot_nt0} → mode{m} {tot_ntm}")
    qs = [0.1, 0.5, 0.9]
    print(f"   原零延遲 PDU 平均延遲（逐 cell×UE，ms）P10/50/90 = " + "/".join(f"{np.quantile(mz,q):.2f}" for q in qs) +
          f"；原有時間戳 PDU = " + "/".join(f"{np.quantile(mt,q):.2f}" for q in qs))
    res[m] = {"zero_old": tot_z0, "zero_new": tot_zm, "notag_new": tot_ntm, "nrx": tot_nrx,
              "zero_pdu_mean_delay_ms_q": {str(q): float(np.quantile(mz, q)) for q in qs},
              "tagged_mean_delay_ms_q": {str(q): float(np.quantile(mt, q)) for q in qs}}
    lg = open(os.path.join(dm, "run.log")).read().strip().splitlines()[-1]
    print("   " + lg); res[m]["time"] = lg

# ---------- I-1（資訊）
def cellvals(mode, how):
    """{w: {cell: value}}，how = 'excl'（排除零延遲，主版本）／'incl'（含）。cell 值 = 該 cell 各 UE 區間平均之平均；排除 cell 1"""
    pc = tab(os.path.join(OUT, f"mode{mode}", "DlE2RlcStats_percell.txt"))
    zr = {(r[0], r[2], r[3], r[4]): r for r in tab(os.path.join(OUT, f"mode{mode}", "DlE2RlcStats_r9rx.txt"))}
    # mode0 之零延遲數（excl 用 mode0 之 r9rx；累計→區間）
    zr0 = {(r[0], r[2], r[3], r[4]): r for r in tab(os.path.join(OUT, "mode0", "DlE2RlcStats_r9rx.txt"))}
    prev = collections.defaultdict(lambda: (0, 0, 0))     # (nRx, ds, nz) 累計
    acc = collections.defaultdict(lambda: collections.defaultdict(dict))
    for r in pc:
        k = (r[2], r[3], r[4]); w = int(r[0]) // NS
        nrx, ds = int(r[7]), int(r[9]); nz = int(zr0[(r[0], r[2], r[3], r[4])][6])
        p = prev[k]; prev[k] = (nrx, ds, nz)
        dn, dd, dz = nrx - p[0], ds - p[1], nz - p[2]
        if r[2] == "1":
            continue
        n = dn - (dz if how == "excl" else 0)
        if n > 0:
            u = acc[w][r[2]].setdefault(r[3], [0, 0]); u[0] += dd; u[1] += n
    out = {}
    for w, cells in acc.items():
        out[w] = {c: float(np.mean([a / b / 1e6 for a, b in us.values()])) for c, us in cells.items() if us}
    return out


def fpr(W):
    lv = [v for w in W.values() for v in w.values()]
    med = np.median(lv); s = 1.4826 * (np.median(np.abs(np.array(lv) - med)) + 1e-9)
    fl = []
    for w, cs in W.items():
        for c, v in cs.items():
            pe = [x for cc, x in cs.items() if cc != c]
            if len(pe) >= 2:
                fl.append(abs(v - np.median(pe)) / s > 4)
    return float(np.mean(fl)), s, len(fl)


print("\nI-1（資訊；20 窗、in-sample 尺度，不得引用）空間乾淨誤報")
info = {}
for lab, mode, how in (("mode0 排除零延遲（r9 主版本）", 0, "excl"), ("mode0 含零延遲（r9 對照）", 0, "incl"),
                       ("mode1 全 PDU（首次傳送時間戳）", 1, "incl"), ("mode2 全 PDU（每次重傳重打）", 2, "incl")):
    f, s, n = fpr(cellvals(mode, how)); info[lab] = {"fpr": f, "s_ms": float(s), "n": n}
    print(f"   {lab:36s} 誤報 {f:.3f}  s = {s:.3f} ms  n = {n}")
json.dump({"R": res, "I1": info, "fails": fails}, open(os.path.join(OUT, "check_r10.json"), "w"), indent=2, ensure_ascii=False)
print("\n" + ("✓ R-0／R-1／R-2 全部通過" if not fails else f"✗ 失敗：{fails}"))
sys.exit(1 if fails else 0)
