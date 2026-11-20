#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analyze_r10_dup_v4.py — 重複接收與分段／部分重疊之判定核對（2026-11-20；驗證用，不得作為論文資料）
每筆 KPM 計入之資料 RX（統計回呼 C 行）對上接收端判定（D 行，同一 DoReceivePdu 呼叫）：
  W 窗外丟棄｜DW 整包重複｜AS 分段接續｜OE 分段不接續、PDU 未完整 → 清除緩衝｜OI 分段不接續、已完整 → 忽略｜AN 新 SN 放入｜DO 新 SN 但 offset>0 → 忽略
另以位元組覆蓋（逐 PDU 實例 = (IMSI,rnti,lcid,SN,首次傳送時間)，範圍 [segOff,lastOff)）分類：
  NEW 全新｜PART 部分重疊｜DUP 全為已收位元組｜EMPTY 長度 0
 J  C 行 ↔ D 行一對一對上（未對上 0）
 X  判定 × 位元組覆蓋 交叉表
 R  被 OE 清除之位元組，之後再收到時之判定（說明位元組覆蓋與接收端判定為何不同）
 F  兩種「首次接收」定義下之逐窗新統計（有效延遲樣本數、延遲總和、重複接收數）與原生 nRx
"""
import os, sys, collections, bisect
import numpy as np
D = os.path.expanduser("~/oran-zt-kpm-verification/data/r10_trace/on")
fails = []
TX = []; DL = collections.defaultdict(list); byptr = collections.defaultdict(list); trunc = 0
for ln in open(f"{D}/R10_trace.txt"):
    p = ln.split()
    if p[0] == "T":
        if len(p) != 11: trunc += 1; continue
        TX.append((int(p[1]), int(p[2]), int(p[3]), p[4], int(p[5]), int(p[6]), int(p[7]), int(p[8]), int(p[9]), int(p[10])))
    elif p[0] == "D":
        if len(p) != 12: trunc += 1; continue
        t, rnti, lcid, imsi, sn, tag, seg, so, lo, last = map(int, p[1:11])
        DL[(t, rnti, lcid, sn, so, tag)].append((lo, last, p[11], imsi))
for ln in open(f"{D}/R10_trace_calc.txt"):
    p = ln.split()
    if len(p) != 14: trunc += 1; continue
    byptr[p[1]].append(tuple(int(x) for x in p[2:]))
# C: t cell imsi rnti lcid size delay found tagT sn seg segoff
pc = [l.split("\t") for l in open(f"{D}/DlE2RlcStats_percell.txt") if not l.startswith("%")]
last = {}; PC = {}
for r in pc:
    k = (int(r[2]), int(r[3]), int(r[4])); w = int(r[0]) // 10**9; v = (int(r[7]), int(r[9]))
    pv = last.get(k, (0, 0)); PC[(k, w)] = (v[0] - pv[0], v[1] - pv[1]); last[k] = v
tot = sum(v[0] for (k, w), v in PC.items() if w < 5)
cand = [k for k, v in byptr.items() if sum(1 for r in v if r[0] < 5 * 10**9) == tot]
print(f"截斷末行 {trunc}；統計回呼主實例候選 {len(cand)}（取第一個）")
if not cand: print("✗ 無主實例"); sys.exit(1)
C = byptr[cand[0]]
# J
dec = []; unm = []
tmaxD = max(k[0] for k in DL)
for r in C:
    if r[9] < 0: dec.append(None); continue
    k = (r[0], r[3], r[4], r[9], r[11], r[8]); v = DL.get(k)
    if not v: unm.append(r); dec.append(None); continue
    dec.append(v.pop(0))
ndata = sum(1 for r in C if r[9] >= 0)
late = [r for r in unm if r[0] >= tmaxD]          # 僅限追蹤檔最後時刻（未 flush）才可豁免
print(f"J   KPM 資料 RX {ndata}；對不上接收端判定 {len(unm)}；其中發生於判定檔最後時刻（{tmaxD} ns，未 flush）{len(late)}；"
      f"判定行未被消耗 {sum(len(v) for v in DL.values())}")
if len(unm) != len(late) or sum(len(v) for v in DL.values()): fails.append("J")
# 實例：有時間戳 → tag；無 → 該 SN 於 RX 前最近一次 N 型 TX 之時間
txN = collections.defaultdict(list)
for t in TX:
    if t[3] == "N": txN[(t[9], t[1], t[2], t[4])].append(t[0])
for v in txN.values(): v.sort()
cov = collections.defaultdict(list)          # inst -> [(a,b)] 已收（位元組覆蓋，不因 OE 清除）
erased = collections.defaultdict(list)       # inst -> 被 OE 清除前接收端緩衝之範圍
buf = collections.defaultdict(list)          # inst -> 接收端緩衝內之範圍（模擬 AN/AS/OE）
def overlap(rs, a, b):
    o = 0
    for x, y in rs: o += max(0, min(b, y) - max(a, x))
    return o
X = collections.Counter(); Rr = collections.Counter(); cls = []
for r, d in zip(C, dec):
    if d is None: cls.append(None); continue
    lo, lastf, dd, _ = d; a = r[11]; b = lo if r[10] == 1 else lo
    inst_t = r[8]
    if inst_t < 0:
        v = txN.get((r[2], r[3], r[4], r[9]), []); i = bisect.bisect_right(v, r[0]) - 1; inst_t = v[i] if i >= 0 else -1
    inst = (r[2], r[3], r[4], r[9], inst_t); L = b - a
    o = overlap(cov[inst], a, b)
    c = "EMPTY" if L <= 0 else ("NEW" if o == 0 else ("DUP" if o >= L else "PART"))
    if L > 0 and overlap(erased[inst], a, b) > 0: Rr[(c, dd)] += 1
    X[(dd, c)] += 1; cls.append(c)
    if L > 0: cov[inst].append((a, b))
    if dd in ("AN", "AS"): buf[inst].append((a, b))
    if dd == "OE": erased[inst].extend(buf.pop(inst, []))
decs = ["AN", "AS", "DW", "OI", "OE", "DO", "W"]; cs = ["NEW", "PART", "DUP", "EMPTY"]
print("X   判定 × 位元組覆蓋（KPM 資料 RX）")
print("        " + "".join(f"{c:>8}" for c in cs) + "     合計")
for dd in decs:
    row = [X[(dd, c)] for c in cs]
    if sum(row): print(f"    {dd:>3} " + "".join(f"{x:>8}" for x in row) + f"{sum(row):>9}")
print(f"R   與先前被 OE 清除之位元組重疊之 RX：{dict(Rr)}")
# F：兩種首次接收定義
defs = {"Fb 接收端接受（AN／AS）": lambda r, d, c: d is not None and d[2] in ("AN", "AS"),
        "Fa 位元組首次（NEW／PART）": lambda r, d, c: c in ("NEW", "PART")}
for name, f in defs.items():
    nd = sd = ndup = 0; sel = []
    for r, d, c in zip(C, dec, cls):
        if r[9] < 0: continue
        first = f(r, d, c)
        if not first: ndup += 1
        if first and r[7] == 1: nd += 1; sd += r[6]; sel.append(r[6] / 1e6)
    print(f"F   {name}：有效延遲樣本 {nd}（占 KPM 資料 RX {nd/ndata:.4f}）；非首次 {ndup}；"
          f"平均 {sd/max(1,nd)/1e6:.2f} ms；P50/P90/P99 {'/'.join(f'{np.quantile(sel,q):.2f}' for q in (.5,.9,.99))} ms")
fa = [(r, d, c) for r, d, c in zip(C, dec, cls) if r[9] >= 0 and r[7] == 1 and c in ("NEW", "PART")]
n_fa = len(fa); sum_fa = sum(r[6] for r, d, c in fa)
part = [(r, d, c) for r, d, c in fa if c == "PART"]
print(f"P   Fa 有效延遲樣本 {n_fa}：其中部分重疊（PART）{len(part)}（占樣本 {len(part)/n_fa:.5f}；占延遲總和 {sum(r[6] for r,d,c in part)/sum_fa:.5f}）；全新（NEW）{n_fa-len(part)}")
rej = collections.Counter((d[2] if d else "?") for r, d, c in fa)
print(f"    Fa 樣本依接收端判定：{dict(rej)}")
dis = [(r, d, c) for r, d, c in fa if d and d[2] in ("W", "DO", "OI", "DW")]
print(f"    Fa 計入但接收端實際丟棄／忽略（W／DO／OI／DW）：{len(dis)}（占樣本 {len(dis)/n_fa:.5f}；占延遲總和 {sum(r[6] for r,d,c in dis)/sum_fa:.5f}）")
wm = sum(r[6] * 0 for r, d, c in fa)
# 位元組比例加權版（敏感度）：權重 = 新位元組數 / 該次接收位元組數；以 PART 代表部分重疊
print("    （位元組比例加權之敏感度版本須另行計算，本腳本未實作；見規格 §6）")
old = [r[6] / 1e6 for r in C if r[9] >= 0 and r[7] == 1]
print(f"    對照（原生，含重複）：樣本 {len(old)}；平均 {np.mean(old):.2f} ms")
print("\n" + ("✓ 無失敗項" if not fails else f"✗ {fails}"))
sys.exit(1 if fails else 0)
