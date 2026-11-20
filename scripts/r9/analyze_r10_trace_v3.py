#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analyze_r10_trace_v3.py — 逐 PDU 核對 v3（2026-11-20；驗證用，不得作為論文資料）
TX：RLC AM 傳送端（eNB）之 m_imsi；RX：DL 統計回呼（含 cellId、IMSI，即 KPM 計數之同一批接收）。
配對主鍵 = (IMSI, lcid, SN, 首次傳送時間)；首次傳送時間取自 N 型傳送紀錄自身之時間。
 O   追蹤開／關同長度：除 R10_trace*.txt、run.log 外 md5 全同
 Q   兩個統計回呼實例（mmWave／LTE 計算器）之 RX 序列關係；以 percell 計數相符者為主
 K   主鍵於 N 型 TX 之唯一性；傳送端 IMSI = 0 之筆數
 A   有時間戳之 RX：delay == rx − tag；A0' N 型 TX 之 tag 讀回 == 傳送時間
 A1  RX 配對：唯一／多重／未配對（成功率）；對照：只用 SN、只用 (rnti,lcid,SN,時間)
 W   逐 (cell, IMSI, lcid, 窗)：追蹤重算之 nRx、ΣdelayNs、nZero == percell／r9rx 之區間值（窗 0–4）
 B   經重傳之延遲；延遲 ≥ 首次傳送→最早重傳
 C   每鍵多次接收：不同分段 vs 同分段重複（及是否跨 cell）
 D   殘留無時間戳之 RX：該 SN 最近一次 TX 之種類與時間戳狀態
"""
import os, sys, collections, bisect, hashlib
import numpy as np
B0 = os.path.expanduser("~/oran-zt-kpm-verification/data/r10_trace"); D = B0 + "/on"
fails = []
def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()
names = sorted(n for n in os.listdir(f"{B0}/off") if os.path.isfile(f"{B0}/off/{n}") and n != "run.log")
diff = [n for n in names if not os.path.exists(f"{D}/{n}") or md5(f"{B0}/off/{n}") != md5(f"{D}/{n}")]
extra = sorted(set(os.listdir(D)) - set(os.listdir(f"{B0}/off")))
print(f"O   追蹤開／關（6 s）：檔案 {len(names)}，md5 不同 {len(diff)} {diff}；僅追蹤開才有之檔 {extra}")
if diff: fails.append("O")
TX = []
for ln in open(f"{D}/R10_trace.txt"):
    p = ln.split()
    if p[0] == "T":
        TX.append((int(p[1]), int(p[2]), int(p[3]), p[4], int(p[5]), int(p[6]), int(p[7]), int(p[8]), int(p[9]), int(p[10])))
# t rnti lcid kind sn size has tagT uid imsi
byptr = collections.defaultdict(list)
for ln in open(f"{D}/R10_trace_calc.txt"):
    p = ln.split()
    byptr[p[1]].append(tuple(int(x) for x in p[2:]))
# t cell imsi rnti lcid size delay found tagT sn seg segoff
pc = [l.split("\t") for l in open(f"{D}/DlE2RlcStats_percell.txt") if not l.startswith("%")]
zr = [l.split("\t") for l in open(f"{D}/DlE2RlcStats_r9rx.txt") if not l.startswith("%")]
def deltas(rows, cols):
    last = {}; out = {}
    for r in rows:
        k = (int(r[2]), int(r[3]), int(r[4])); w = int(r[0]) // 10**9; v = tuple(int(r[c]) for c in cols)
        pv = last.get(k, (0,) * len(v)); out[(k, w)] = tuple(a - b for a, b in zip(v, pv)); last[k] = v
    return out
PCd = deltas(pc, (7, 9)); ZRd = deltas(zr, (6,))
tot_pc = sum(v[0] for (k, w), v in PCd.items() if w < 5)
print("Q   統計回呼實例：", {k[-6:]: len(v) for k, v in byptr.items()}, f"；percell 窗 0–4 nRx 總和 {tot_pc}")
cand = [k for k, v in byptr.items() if sum(1 for r in v if r[0] < 5 * 10**9) == tot_pc]
if not cand: fails.append("Q"); print("✗ 無一實例之 RX 數 == percell"); sys.exit(1)
RX = byptr[cand[0]]
others = [k for k in byptr if k != cand[0]]
for k in others:
    s_main = collections.Counter(RX); s_o = collections.Counter(byptr[k])
    print(f"    另一實例 …{k[-6:]}：{len(byptr[k])} 筆；為主實例之子集 {all(s_main[x] >= c for x, c in s_o.items())}；相同 {s_main == s_o}")
N = collections.defaultdict(list)
for t in TX:
    if t[3] == "N": N[(t[9], t[2], t[4], t[0])].append(t)
print(f"A0' N 型 TX tag 讀回 ≠ 傳送時間：{sum(1 for t in TX if t[3]=='N' and t[7]!=t[0])}；傳送端 IMSI = 0 之 TX：{sum(1 for t in TX if t[9]==0)}")
multiN = sum(1 for v in N.values() if len(v) > 1)
print(f"K   N 型 TX {sum(len(v) for v in N.values())}；主鍵 {len(N)}；同主鍵 >1 個 N 型 TX：{multiN}")
if multiN: fails.append("K")
dat = [r for r in RX if r[9] >= 0]; tg = [r for r in dat if r[7] == 1]
bad = sum(1 for r in tg if r[6] != r[0] - r[8])
print(f"A   有時間戳 RX {len(tg)}：delay ≠ rx − tag {bad}；有時間戳但 delay = 0：{sum(1 for r in tg if r[6]==0)}")
if bad: fails.append("A")
key = lambda r: (r[2], r[4], r[9], r[8])
uni = sum(1 for r in tg if len(N.get(key(r), [])) == 1); mul = sum(1 for r in tg if len(N.get(key(r), [])) > 1)
unp = sum(1 for r in tg if key(r) not in N)
print(f"A1  配對：唯一 {uni}（{uni/len(tg):.6f}）；多重 {mul}；未配對 {unp}")
if mul or unp: fails.append("A1")
s1 = collections.defaultdict(set); s2 = collections.defaultdict(set)
for k, v in N.items():
    s1[(k[0], k[1], k[2])].add(k)
    for t in v: s2[(t[1], t[2], t[4], t[0])].add(k)
print(f"    對照：只用 (IMSI,lcid,SN) 時歧義 RX {sum(1 for r in tg if len(s1[(r[2],r[4],r[9])]) > 1)}；"
      f"只用 (rnti,lcid,SN,時間) 時歧義 RX {sum(1 for r in tg if len(s2[(r[3],r[4],r[9],r[8])]) > 1)}")
# W
acc = collections.defaultdict(lambda: [0, 0, 0])
for r in RX:
    w = r[0] // 10**9
    if w >= 5: continue
    a = acc[((r[1], r[2], r[4]), w)]; a[0] += 1; a[1] += r[6]; a[2] += (r[6] == 0)
wbad = 0; nw = 0
for (k, w), v in PCd.items():
    if w >= 5: continue
    nw += 1; got = acc.get((k, w), [0, 0, 0])
    if (got[0], got[1]) != v or got[2] != ZRd.get((k, w), (0,))[0]: wbad += 1
wextra = sum(1 for kw in acc if kw not in PCd)
print(f"W   (cell,IMSI,lcid,窗) {nw} 組：nRx／ΣdelayNs／nZero 與統計檔不符 {wbad}；追蹤有而統計檔無 {wextra}")
if wbad or wextra: fails.append("W")
RS = collections.defaultdict(list)
for t in TX:
    if t[3] in "RS" and t[6] == 1: RS[(t[9], t[2], t[4], t[7])].append(t)
print(f"B0  帶時間戳 R/S 型 TX 鍵 {len(RS)}；對不上 N 型 TX {sum(1 for k in RS if k not in N)}")
if any(k not in N for k in RS): fails.append("B0")
ret, new, viol = [], [], 0
for r in tg:
    ts = [t[0] for t in RS.get(key(r), []) if r[8] < t[0] <= r[0]]
    if ts:
        ret.append(r[6] / 1e6); viol += r[6] < min(ts) - r[8]
    else:
        new.append(r[6] / 1e6)
q = lambda a: "/".join(f"{np.quantile(a, p):.2f}" for p in (0.1, 0.5, 0.9, 0.99)) if a else "-"
print(f"B   經重傳 {len(ret)} 筆 延遲 P10/50/90/99 ms = {q(ret)}；未經重傳 {len(new)} 筆 = {q(new)}；違反下界 {viol}")
if viol: fails.append("B")
byk = collections.defaultdict(list)
for r in tg: byk[key(r)].append(r)
seg = dup = dupx = 0; ex = []
for k, v in byk.items():
    if len(v) < 2: continue
    c = collections.Counter((r[10], r[11]) for r in v)
    if max(c.values()) > 1:
        dup += 1; dupx += len({r[1] for r in v}) > 1
        if len(ex) < 2: ex.append([(r[0], r[1], r[5], r[10], r[11]) for r in v])
    else:
        seg += 1
print(f"C   接收 >1 次之鍵：全為不同分段 {seg}；含同分段重複 {dup}（其中跨 cell {dupx}）")
for e in ex: print("     重複例 (t, cell, size, seg, off)", e)
txby = collections.defaultdict(list)
for t in TX: txby[(t[9], t[2], t[4])].append(t)
for v in txby.values(): v.sort()
un = [r for r in dat if r[7] == 0]; cls = collections.Counter(); exd = []
for r in un:
    v = txby.get((r[2], r[4], r[9]), []); i = bisect.bisect_right([t[0] for t in v], r[0]) - 1
    if i < 0: cls["無先前 TX"] += 1; continue
    t = v[i]; cls[(t[3], "帶時間戳" if t[6] else "無時間戳")] += 1
    if len(exd) < 3: exd.append((r, t))
print(f"D   無時間戳之資料 RX {len(un)}（占 DL RX {len(un)/max(1,len(dat)):.5f}）：最近一次 TX {dict(cls)}")
for r, t in exd: print("     例 RX (t,cell,imsi) ", r[:3], "seg/off", r[10:12], "size", r[5], "← TX", t[:8])
print("\n" + ("✓ 無失敗項" if not fails else f"✗ {fails}"))
sys.exit(1 if fails else 0)
