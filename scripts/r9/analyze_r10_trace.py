#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analyze_r10_trace.py — 逐 PDU 核對（r10t，mode 1；驗證用，不得作為論文資料）
配對鍵：(rnti, lcid, SN, 首次傳送時間, packet uid)；不只用 SN。同時報告「只用 SN／(rnti,lcid,SN)」之歧義數。
 O   追蹤開／關（同一二進位、同模擬長度 6 s）：除 R10_trace.txt、run.log 外，所有輸出檔 md5 全同
 A   計時：有時間戳之資料 RX：delay == rx − tag（逐筆）；其配對鍵 ∈ N 型 TX 之鍵集合（起點 = 首次傳送）
 B   重傳：該鍵於 (tag, rx] 間有 R/S 型 TX 者 = 經重傳；延遲 ≥ 首次傳送→最早重傳之間隔；分布 vs 未重傳
 C   重複／分段：每鍵之接收次數分布；segFlag 計數
 D   殘留無時間戳：分類；能以 uid 回溯到 TX 者其 TX 種類
 E   數量：percell nRx 總數 vs trace（同窗、同類）
"""
import sys, os, collections, hashlib
import numpy as np
D = os.path.expanduser("~/oran-zt-kpm-verification/data/r10_trace")
fails = []

# ---- O
def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()
names = sorted(n for n in os.listdir(f"{D}/off") if os.path.isfile(f"{D}/off/{n}") and n != "run.log")
diff = [n for n in names if not os.path.exists(f"{D}/on/{n}") or md5(f"{D}/off/{n}") != md5(f"{D}/on/{n}")]
print(f"O   追蹤開／關（simTime 6 s）：檔案 {len(names)}，md5 不同 {len(diff)} {diff}")
if diff:
    fails.append("O trace on/off differs")

TX = []; RX = []
with open(f"{D}/on/R10_trace.txt") as fh:
    for ln in fh:
        p = ln.split()
        if p[0] == "T":
            TX.append((int(p[1]), int(p[2]), int(p[3]), p[4], int(p[5]), int(p[6]), int(p[7]), int(p[8]), int(p[9])))
        else:
            RX.append(tuple(int(x) for x in p[1:]))   # t rnti lcid size found tagT delay isData sn seg last off uid
print(f"TX {len(TX)}（N {sum(t[3]=='N' for t in TX)}／R {sum(t[3]=='R' for t in TX)}／S {sum(t[3]=='S' for t in TX)}）；RX {len(RX)}")
# TX: t rnti lcid kind sn size has tagT uid
Nkey = collections.defaultdict(list)
for t in TX:
    if t[3] == "N":
        Nkey[(t[1], t[2], t[4], t[0], t[8])].append(t[0])   # 首次傳送時間 = 傳送紀錄自身之 Now()，與 tag 讀回值獨立
dupN = sum(1 for v in Nkey.values() if len(v) > 1)
print(f"A0' 首次傳送時間獨立確認：N 型 TX 之 tag 讀回時間 ≠ 傳送紀錄時間之筆數 {sum(1 for t in TX if t[3]=='N' and t[7]!=t[0])}")
print(f"A0  N 型 TX 鍵 {len(Nkey)}；同鍵重複 {dupN}；N 型 TX 之 tagTime == 傳送時間：{sum(1 for t in TX if t[3]=='N' and t[7]==t[0])}／{sum(1 for t in TX if t[3]=='N')}")
sn_only = collections.defaultdict(set)
for k in Nkey:
    sn_only[k[:3]].add(k)
print(f"    若只用 (rnti,lcid,SN)：{sum(1 for v in sn_only.values() if len(v) > 1)}／{len(sn_only)} 組對應到 >1 個不同 PDU（SN 繞回／重用）")
untagged_tx = [t for t in TX if t[6] == 0]
print(f"    TX 時即無時間戳：{len(untagged_tx)}（R {sum(t[3]=='R' for t in untagged_tx)}／S {sum(t[3]=='S' for t in untagged_tx)}）")
RS = collections.defaultdict(list)
for t in TX:
    if t[3] in "RS" and t[6] == 1:
        RS[(t[1], t[2], t[4], t[7], t[8])].append((t[0], t[3]))
rs_unmatched = [k for k in RS if k not in Nkey]
print(f"    R/S 型 TX 之鍵 {len(RS)}；對不上任何 N 型 TX 之鍵 {len(rs_unmatched)}")

dat = [r for r in RX if r[7] == 1]
tagged = [r for r in dat if r[4] == 1]
key = lambda r: (r[1], r[2], r[8], r[5], r[12])
bad_delay = [r for r in tagged if r[6] != r[0] - r[5]]
nokey = [r for r in tagged if key(r) not in Nkey]
print(f"A   有時間戳資料 RX {len(tagged)}：delay ≠ rx − tag {len(bad_delay)}；配對鍵不在 N 型 TX 集合 {len(nokey)}")
if bad_delay:
    fails.append("A delay")
for r in nokey[:3]:
    print("     例", r)
if nokey:
    # 退而以 (rnti,lcid,SN,tagTime) 配對（不含 uid）看是否為 uid 在傳輸中改變
    Nk2 = {(k[0], k[1], k[2], k[3]) for k in Nkey}
    print("     其中以 (rnti,lcid,SN,tagTime) 仍可配對者：", sum(1 for r in nokey if (r[1], r[2], r[8], r[5]) in Nk2))
# 配對統計（有時間戳之資料 RX）
paired = sum(1 for r in tagged if len(Nkey.get(key(r), [])) == 1)
multi = sum(1 for r in tagged if len(Nkey.get(key(r), [])) > 1)
unp = sum(1 for r in tagged if key(r) not in Nkey)
n = len(tagged) or 1
print(f"A1  配對（鍵 = rnti,lcid,SN,首次傳送時間,uid；首次傳送時間取自傳送紀錄）：成功且唯一 {paired}（{paired/n:.5f}）；多重配對 {multi}；未配對 {unp}")
sn_multi = sum(1 for r in tagged if len(sn_only.get((r[1], r[2], r[8]), ())) > 1)
print(f"    對照：只用 (rnti,lcid,SN) 時，會對應到 >1 個不同 PDU 之 RX {sn_multi}（{sn_multi/n:.5f}）")
if multi or unp:
    fails.append(f"A1 pairing multi={multi} unpaired={unp}")
un_d = [r for r in RX if r[4] == 0 and r[7] == 1]
_nu = {(k[0], k[1], k[2], k[4]) for k in Nkey}
print(f"    無時間戳之資料 RX {len(un_d)}：以 (rnti,lcid,SN,uid) 對得上 N 型 TX 者 {sum(1 for r in un_d if (r[1],r[2],r[8],r[12]) in _nu)}")
dl_ret = []; dl_new = []; viol = 0
for r in tagged:
    k = key(r)
    rts = [t for t, _ in RS.get(k, []) if r[5] < t <= r[0]]
    if rts:
        dl_ret.append(r[6] / 1e6)
        if r[6] < min(rts) - r[5]:
            viol += 1
    else:
        dl_new.append(r[6] / 1e6)
q = lambda a: "/".join(f"{np.quantile(a, p):.2f}" for p in (0.1, 0.5, 0.9)) if a else "-"
print(f"B   經重傳 {len(dl_ret)} 筆 延遲 P10/50/90 ms = {q(dl_ret)}；未見重傳 {len(dl_new)} 筆 = {q(dl_new)}；延遲 < 首次傳送→最早重傳 之筆數 {viol}")
if viol:
    fails.append("B viol")
c = collections.Counter(key(r) for r in tagged)
print(f"C   接收次數分布（每鍵）{dict(sorted(collections.Counter(c.values()).items()))}；分段 RX（segFlag=1）{sum(r[9]==1 for r in dat)}／資料 RX {len(dat)}")
un = [r for r in RX if r[4] == 0]
cls = collections.Counter(("data" if r[7] else "control", f"seg{r[9]}", f"last{r[10]}") for r in un)
print(f"D   無時間戳 RX {len(un)}（{len(un)/len(RX):.5f}）；分類 {dict(cls)}")
uid_tx = collections.defaultdict(set)
for t in TX:
    uid_tx[(t[1], t[2], t[4], t[8])].add(t[3])
kinds = collections.Counter()
for r in un:
    if r[7]:
        kinds[tuple(sorted(uid_tx.get((r[1], r[2], r[8], r[12]), {"?無對應TX"})))] += 1
print(f"    無時間戳之資料 RX 以 (rnti,lcid,SN,uid) 回溯到之 TX 種類：{dict(kinds)}")
for r in un[:5]:
    print("     例", r)
print(f"    有時間戳但 delay = 0：{sum(1 for r in RX if r[4]==1 and r[6]==0)}")
pc = [l.split("\t") for l in open(f"{D}/on/DlE2RlcStats_percell.txt") if not l.startswith("%")]
last = {}
for r in pc:
    if int(r[0]) < 5 * 10**9:
        last[(r[2], r[3], r[4])] = int(r[7])
print(f"E   percell 累計 nRx（窗 < 5 s）{sum(last.values())}；trace 資料 PDU RX（時間 < 5 s，UE 端所有 RLC AM 實體）{sum(1 for r in dat if r[0] < 5*10**9)}")
print("\n" + ("✓ 無失敗項" if not fails else f"✗ {fails}"))
sys.exit(1 if fails else 0)
