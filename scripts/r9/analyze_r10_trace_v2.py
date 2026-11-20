#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analyze_r10_trace_v2.py — 逐 PDU 核對 v2（2026-11-20；驗證用，不得作為論文資料）
v1 之 uid 鍵於 mmWave 路徑不成立（RX uid 與 TX uid 不同）；v2 主鍵 = (rnti, lcid, SN, 首次傳送時間)，
首次傳送時間取自 N 型傳送紀錄自身之時間（A0' 已確認與 tag 讀回值一致）。uid 改為診斷項。
 K   主鍵於 N 型 TX 中之唯一性（同鍵對應 >1 個 N 型 TX 即多重）
 A1  有時間戳資料 RX：唯一配對／多重配對／未配對（及成功率）；只用 SN 之歧義數（對照）
 U   uid 診斷：同一接收時刻、同一 rnti 之多個 RX 是否共用 uid（支持「uid 為傳輸區塊之 uid」）
 B   經重傳（主鍵於 (首次傳送, 接收] 間有 R/S 型 TX）之延遲分佈與「延遲 ≥ 首次傳送→最早重傳」
 C   每鍵多次接收：區分「分段」（segOffset 不同）與「重複」（同 segOffset 再次收到）
 D   無時間戳之資料 RX：以 (rnti,lcid,SN) 與時間回溯該 SN 最近之 TX 紀錄（N／R／S、是否帶時間戳）
"""
import os, sys, collections, bisect
import numpy as np
D = os.path.expanduser("~/oran-zt-kpm-verification/data/r10_trace/on")
TX = []; RX = []
for ln in open(os.path.join(D, "R10_trace.txt")):
    p = ln.split()
    if p[0] == "T":
        TX.append((int(p[1]), int(p[2]), int(p[3]), p[4], int(p[5]), int(p[6]), int(p[7]), int(p[8]), int(p[9])))
    else:
        RX.append(tuple(int(x) for x in p[1:]))
fails = []
N = collections.defaultdict(list)                  # (rnti,lcid,sn,t_first) -> [TX]
for t in TX:
    if t[3] == "N":
        N[(t[1], t[2], t[4], t[0])].append(t)
multiN = sum(1 for v in N.values() if len(v) > 1)
print(f"K   N 型 TX {sum(len(v) for v in N.values())}；主鍵 {len(N)}；同主鍵對應 >1 個 N 型 TX：{multiN}")
if multiN: fails.append("K")
dat = [r for r in RX if r[7] == 1]; tg = [r for r in dat if r[4] == 1]
key = lambda r: (r[1], r[2], r[8], r[5])
uni = sum(1 for r in tg if len(N.get(key(r), [])) == 1); mul = sum(1 for r in tg if len(N.get(key(r), [])) > 1)
unp = sum(1 for r in tg if key(r) not in N)
print(f"A1  有時間戳資料 RX {len(tg)}：唯一配對 {uni}（{uni/len(tg):.5f}）；多重配對 {mul}；未配對 {unp}")
if mul or unp: fails.append("A1")
sn = collections.defaultdict(set)
for k in N: sn[k[:3]].add(k)
print(f"    對照：只用 (rnti,lcid,SN) 時對應到 >1 個 PDU 之 RX {sum(1 for r in tg if len(sn[(r[1],r[2],r[8])]) > 1)}")
# U
g = collections.defaultdict(list)
for r in dat: g[(r[0], r[1], r[2])].append(r[12])
multi_pdu = [v for v in g.values() if len(v) > 1]
shared = sum(1 for v in multi_pdu if len(set(v)) == 1)
print(f"U   同一接收時刻與 rnti 收到 >1 個 PDU 之組 {len(multi_pdu)}；其中所有 PDU 共用同一 uid {shared}（{shared/max(1,len(multi_pdu)):.4f}）")
uidmatch = sum(1 for r in tg if len(N.get(key(r), [])) == 1 and N[key(r)][0][8] == r[12])
print(f"    唯一配對中 TX uid == RX uid 者 {uidmatch}／{uni}")
# B
RS = collections.defaultdict(list)
for t in TX:
    if t[3] in "RS":
        RS[(t[1], t[2], t[4], t[7])].append(t)       # R/S 之 tag 時間 = 首次傳送時間（mode 1）
rs_unp = sum(1 for k, v in RS.items() if k[3] >= 0 and k not in N)
print(f"B0  帶時間戳之 R/S 型 TX 鍵 {sum(1 for k in RS if k[3] >= 0)}；對不上 N 型 TX 者 {rs_unp}")
if rs_unp: fails.append("B0")
ret, new, viol = [], [], 0
for r in tg:
    ts = [t[0] for t in RS.get(key(r), []) if r[5] < t[0] <= r[0]]
    if ts:
        ret.append(r[6] / 1e6)
        if r[6] < min(ts) - r[5]: viol += 1
    else:
        new.append(r[6] / 1e6)
q = lambda a: "/".join(f"{np.quantile(a, p):.2f}" for p in (0.1, 0.5, 0.9)) if a else "-"
print(f"B   經重傳 {len(ret)} 筆 延遲 P10/50/90 ms = {q(ret)}；未經重傳 {len(new)} 筆 = {q(new)}；延遲 < 首次傳送→最早重傳 {viol}")
if viol: fails.append("B")
# C
byk = collections.defaultdict(list)
for r in tg: byk[key(r)].append(r)
seg_only = dup = 0; dup_ex = []
for k, v in byk.items():
    if len(v) < 2: continue
    offs = collections.Counter((r[9], r[11]) for r in v)
    if max(offs.values()) > 1:
        dup += 1; dup_ex.append(v) if len(dup_ex) < 2 else None
    else:
        seg_only += 1
print(f"C   接收 >1 次之鍵：全為不同分段 {seg_only}；含同一分段重複接收 {dup}")
for v in dup_ex:
    print("     重複例", [(r[0], r[9], r[10], r[11], r[3]) for r in v])
# D
txby = collections.defaultdict(list)
for t in TX: txby[(t[1], t[2], t[4])].append(t)
for v in txby.values(): v.sort()
un = [r for r in dat if r[4] == 0]
cls = collections.Counter(); ex = []
for r in un:
    v = txby.get((r[1], r[2], r[8]), [])
    i = bisect.bisect_right([t[0] for t in v], r[0]) - 1
    if i < 0: cls["無先前 TX"] += 1; continue
    t = v[i]; cls[(t[3], "帶時間戳" if t[6] else "無時間戳")] += 1
    if len(ex) < 3: ex.append((r, t))
print(f"D   無時間戳之資料 RX {len(un)}：該 SN 最近一次 TX 之種類 {dict(cls)}")
for r, t in ex: print("     例 RX", r[:4], "seg", r[9:12], "← TX", t[:8])
print("\n" + ("✓ 無失敗項" if not fails else f"✗ {fails}"))
sys.exit(1 if fails else 0)
