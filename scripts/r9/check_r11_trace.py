#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_r11_trace.py — r11 有效延遲樣本之逐筆驗證（2026-11-20；驗證用，不得作為論文資料）
輸入：data/r11_trace/{on,off}（r11t 同一二進位，ZT_R10_TRACE=1／未設；同為 6 s）
 O  追蹤開／關：除追蹤檔外 md5 全同（含 _r11eff.txt）
 J  C 行（KPM 回呼）↔ D 行（接收端實際分支）一對一（僅判定檔最後時刻之未 flush 可豁免）
 P1 預測判定碼 == 實際分支（逐筆）
 P2 獨立重算（每實例 (IMSI,rnti,lcid,SN,首次傳送時間) 之位元組聯集）：新位元組數、有效、部分重疊 == ns-3 預測（逐筆）
 P3 逐 (cell,IMSI,lcid,窗)：由 C×D 重算 nRx／nData／nEff／delaySumEff／nPart／delaySumPart／判定計數 == _r11eff.txt 窗增量
 P4 守恆：nEff + 非有效資料 + 控制 = nRx；nEff ≤ nData；Σ判定 = nData
 P5 報告：有效樣本、非有效資料之分項、部分重疊占樣本與延遲總和、延遲平均（有效 vs 原生含重複）
"""
import os, sys, collections, hashlib
import numpy as np
B0 = os.path.expanduser("~/oran-zt-kpm-verification/data/r11_trace"); D = B0 + "/on"
NAMES = ["AN", "AS", "DW", "OI", "OE", "DO", "W"]
fails = []
def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()
names = sorted(n for n in os.listdir(f"{B0}/off") if os.path.isfile(f"{B0}/off/{n}") and n != "run.log")
diff = [n for n in names if not os.path.exists(f"{D}/{n}") or md5(f"{B0}/off/{n}") != md5(f"{D}/{n}")]
print(f"O   追蹤開／關：檔案 {len(names)}，md5 不同 {len(diff)} {diff}；含 _r11eff：{any('r11eff' in n for n in names)}")
if diff or not any('r11eff' in n for n in names): fails.append("O")
DL = collections.defaultdict(list); C = collections.defaultdict(list); trunc = 0
for ln in open(f"{D}/R10_trace.txt"):
    p = ln.split()
    if p[0] != "D": continue
    if len(p) != 18: trunc += 1; continue
    t, rnti, lcid, imsi, sn, tag, seg, so, lo, last = map(int, p[1:11])
    pdec, peff, ppart, plen, pnew, payload = map(int, p[12:18])
    DL[(t, rnti, lcid, sn, so, tag)].append((imsi, p[11], pdec, peff, ppart, plen, pnew, payload))
for ln in open(f"{D}/R10_trace_calc.txt"):
    p = ln.split()
    if len(p) != 14: trunc += 1; continue
    C[p[1]].append(tuple(int(x) for x in p[2:]))
# C: t cell imsi rnti lcid size delay found tagT sn seg segoff
rows = lambda f: [l.split("\t") for l in open(f"{D}/{f}") if not l.startswith("%")]
pc = rows("DlE2RlcStats_percell.txt"); ef = rows("DlE2RlcStats_r11eff.txt")
last = {}; PC = {}
for r in pc:
    k = (int(r[2]), int(r[3]), int(r[4])); w = int(r[0]) // 10**9; v = int(r[7]); PC[(k, w)] = v - last.get(k, 0); last[k] = v
tot = sum(v for (k, w), v in PC.items() if w < 5)
cand = [k for k, v in C.items() if sum(1 for r in v if r[0] < 5 * 10**9) == tot]
print(f"截斷末行 {trunc}；主實例候選 {len(cand)}")
if not cand: print("✗ 無主實例"); sys.exit(1)
RX = C[cand[0]]
tmaxD = max(k[0] for k in DL)
# J + 取得每筆 C 對應之 D
pair = []; unm = []
for r in RX:
    if r[9] < 0: pair.append((r, None)); continue
    v = DL.get((r[0], r[3], r[4], r[9], r[11], r[8]))
    if v: pair.append((r, v.pop(0)))
    else: unm.append(r); pair.append((r, None))
late = [r for r in unm if r[0] >= tmaxD]
left = sum(len(v) for v in DL.values())
# 注意：D 行亦含 eNB 端（上行）實體；只要求 C 行全部對上，並另報未消耗之 D 行（非 KPM 回呼之實體）
print(f"J   KPM 資料 RX {sum(1 for r,d in pair if r[9]>=0)}；對不上 {len(unm)}（發生於最後時刻 {len(late)}）；未被 KPM 消耗之 D 行 {left}（非統計回呼之實體，僅報告）")
if len(unm) != len(late): fails.append("J")
# P1
bad1 = sum(1 for r, d in pair if d and NAMES[d[2]] != d[1])
print(f"P1  預測判定碼 ≠ 實際分支：{bad1}／{sum(1 for r,d in pair if d)}")
if bad1: fails.append("P1")
# 全部 D 行（含非 KPM 實體）之 P1
allD = [(k, v) for k, vs in ((k, [x for x in vs]) for k, vs in DL.items()) for v in vs]
# P2 獨立重算：依時間序，每實例 (imsi,rnti,lcid,sn,tag)；對全部 D 行（含已消耗者需重建）→ 重新讀檔
ev = []
for ln in open(f"{D}/R10_trace.txt"):
    p = ln.split()
    if p[0] == "D" and len(p) == 18:
        t, rnti, lcid, imsi, sn, tag, seg, so, lo, last_ = map(int, p[1:11]); ev.append((t, rnti, lcid, imsi, sn, tag, so, p[11], *map(int, p[12:18])))
cov = {}; bad2 = 0; n2 = 0
for (t, rnti, lcid, imsi, sn, tag, so, adec, pdec, peff, ppart, plen, pnew, payload) in ev:
    L = payload; new = 0; eff = 0; part = 0
    if tag >= 0 and L > 0:
        key = (imsi, rnti, lcid, sn, tag); iv = cov.get(key, [])
        inter = sum(max(0, min(y, so + L) - max(x, so)) for x, y in iv); new = L - inter
        a, b = so, so + L; m = []; placed = False
        for x, y in iv:
            if y < a: m.append((x, y))
            elif x > b:
                if not placed: m.append((a, b)); placed = True
                m.append((x, y))
            else: a = min(a, x); b = max(b, y)
        if not placed: m.append((a, b))
        cov[key] = m
        eff = int(new > 0 and adec in ("AN", "AS")); part = int(eff and new < L)
    n2 += 1
    if (new, eff, part, L) != (pnew if tag >= 0 and L > 0 else 0, peff if tag >= 0 and L > 0 else 0, ppart if tag >= 0 and L > 0 else 0, plen): bad2 += 1
print(f"P2  獨立重算（新位元組／有效／部分重疊／長度）≠ ns-3 預測：{bad2}／{n2}（D 行含非統計回呼實體；untagged 者只比長度）")
if bad2: fails.append("P2")
# P3
pe = collections.defaultdict(lambda: [0] * 14)
for r, d in pair:
    if r[9] < 0 or d is None: 
        w = r[0] // 10**9
        if w < 5: pe[((r[1], r[2], r[4]), w)][0] += 1
        continue
    w = r[0] // 10**9
    if w >= 5: continue
    a = pe[((r[1], r[2], r[4]), w)]; a[0] += 1
    imsi, adec, pdec, peff, ppart, plen, pnew, payload = d
    a[1] += 1; a[2] += (r[7] == 0); a[3] += (plen == 0)
    if peff == 1: a[4] += 1; a[5] += r[6]
    if ppart == 1: a[6] += 1; a[7] += r[6]
    a[8 + pdec] += 1 if pdec < 7 else 0
lastv = {}; bad3 = 0; n3 = 0
for r in ef:
    k = (int(r[2]), int(r[3]), int(r[4])); w = int(r[0]) // 10**9
    cur = [int(x) for x in r[5:]]            # nRx nData nNoTag nEmpty nEff sumEff nPart sumPart dec×7
    pv = lastv.get(k, [0] * len(cur)); lastv[k] = cur; d = [a - b for a, b in zip(cur, pv)]
    if w >= 5: continue
    n3 += 1; g = pe.get((k, w), [0] * 14)
    if d != g[:15]: bad3 += 1
print(f"P3  (cell,IMSI,lcid,窗) {n3} 組：新統計檔窗增量 ≠ 追蹤重算：{bad3}")
if bad3: fails.append("P3")
# P4 / P5
tot_rx = sum(1 for r, d in pair if r[0] < 5 * 10**9); eff = [(r, d) for r, d in pair if d and d[3] == 1 and r[0] < 5 * 10**9]
data = [(r, d) for r, d in pair if d and r[0] < 5 * 10**9]
sd = sum(r[6] for r, d in eff); nE = len(eff); part = [(r, d) for r, d in eff if d[4] == 1]
cnt = collections.Counter(NAMES[d[2]] for r, d in data)
print(f"P4  窗 0–4：nRx {tot_rx}；資料 {len(data)}；有效 {nE}；判定計數 {dict(cnt)}；Σ判定 {sum(cnt.values())} == 資料 {len(data)}")
if sum(cnt.values()) != len(data): fails.append("P4")
allt = [r[6] for r, d in data if r[7] == 1]
print(f"P5  有效樣本 {nE}（占 nRx {nE/tot_rx:.4f}）；部分重疊 {len(part)}（占樣本 {len(part)/max(1,nE):.5f}；占延遲總和 {sum(r[6] for r,d in part)/max(1,sd):.5f}）")
print(f"    延遲平均：有效樣本 {sd/max(1,nE)/1e6:.2f} ms；原生（有時間戳含重複）{np.mean(allt)/1e6:.2f} ms")
print("\n" + ("✓ 無失敗項" if not fails else f"✗ {fails}"))
sys.exit(1 if fails else 0)
