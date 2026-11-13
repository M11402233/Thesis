#!/usr/bin/env python3
"""D-30H 換手診斷（使用者 2026-11-13 之三項要求）。只讀 ns-3 輸出目錄，不寫入任何資料目錄。
用法：diag_d30h_handover.py <work_dir> [--json out.json]
1. 計數來源核對：UE／eNB 端 start／end、MmWaveSwitchStats（去重後之 cell 變更）、SwitchToLte、初次接入、失敗。
   一次換手 = 一筆 UE 端 HandoverEndOk（來源→目標，來源取自同 UE 最近一筆 start）。
2. 分段換手率（每 5 秒）。
3. 停留時間分布、1 秒內 A→B→A 比例、最頻繁 UE 之來源／目標 SINR 與初始位置。
"""
import sys, json, argparse, math, re, bisect
from collections import defaultdict, Counter
import numpy as np

ap = argparse.ArgumentParser(); ap.add_argument('wd'); ap.add_argument('--json'); ap.add_argument('--seg', type=float, default=5.0)
a = ap.parse_args(); W = a.wd.rstrip('/')
def rows(f, skip_hdr=False):
    out = []
    for ln in open(f'{W}/{f}'):
        p = ln.split()
        if not p or not re.match(r'^[0-9.]', p[0] if p[0] not in ('SwitchToMmWave','SwitchToLte') else '0'): continue
        out.append(p)
    return out
R = {}
us = [(float(t), int(i), int(r), int(s), int(g)) for t,i,r,s,g in rows('UeHandoverStartStats.txt')]
ue = [(float(t), int(i), int(r), int(c)) for t,i,r,c in rows('UeHandoverEndStats.txt')]
es = [(float(t), int(i), int(r), int(s), int(g)) for t,i,r,s,g in rows('EnbHandoverStartStats.txt')]
ee = [(float(t), int(i), int(r), int(c)) for t,i,r,c in rows('EnbHandoverEndStats.txt')]
sw = [(p[0], float(p[1]), int(p[2]), int(p[3])) for p in rows('MmWaveSwitchStats.txt')]
fails = sum(1 for ln in open(f'{W}/UeFailures.txt') if ln.strip() and ln[0].isdigit())
T_END = max(t for _,t,_,_ in sw)
# 1. 計數核對
# 去重後 switch 序列之 cell 變更
seq = defaultdict(list)
for k,t,i,c in sw: seq[i].append((t,c,k))
first_attach = {}; sw_changes = 0; sw_lte = sum(1 for k,*_ in sw if k=='SwitchToLte')
for i,L in seq.items():
    L.sort(); first_attach[i] = (L[0][0], L[0][1]); cur = L[0][1]
    for t,c,k in L[1:]:
        if c != cur: sw_changes += 1; cur = c
# 配對 start→end（同 UE、依時間）
st_by = defaultdict(list)
for t,i,r,s,g in us: st_by[i].append((t,s,g))
ho = []   # (t_end, imsi, src, tgt, t_start)
unmatched_end = 0; mismatch_tgt = 0
for i in st_by: st_by[i].sort()
ptr = defaultdict(int)
for t,i,r,c in sorted(ue):
    L = st_by[i]; j = ptr[i]
    while j+1 < len(L) and L[j+1][0] <= t: j += 1
    if j >= len(L) or L[j][0] > t: unmatched_end += 1; continue
    ts,s,g = L[j]; ptr[i] = j+1
    if g != c: mismatch_tgt += 1
    ho.append((t,i,s,c,ts))
started_not_ended = len(us) - len(ho)
to_lte = sum(1 for h in ho if h[3]==1 or h[2]==1)
R['counts'] = dict(sim_end=round(T_END,3), ue_start=len(us), ue_end=len(ue), enb_start=len(es), enb_end=len(ee),
    switch_lines=len(sw), switch_dedup_cell_changes=sw_changes, switch_to_lte=sw_lte, initial_attach=len(first_attach),
    ue_failures=fails, paired_ho=len(ho), end_without_start=unmatched_end, start_without_end=started_not_ended,
    end_target_ne_start_target=mismatch_tgt, ho_involving_cell1=to_lte,
    enb_end_vs_ue_end_same=sorted((i,c) for _,i,_,c in ee)==sorted((i,c) for _,i,_,c in ue))
# 2. 分段
nseg = int(math.ceil(T_END/a.seg)); seg = [0]*nseg; seg_ue = [set() for _ in range(nseg)]
for t,i,*_ in ho: k=min(int(t//a.seg), nseg-1); seg[k]+=1; seg_ue[k].add(i)
R['segments'] = [dict(t0=k*a.seg, t1=min((k+1)*a.seg, T_END), ho=seg[k], ho_per_ue_s=round(seg[k]/30/(min((k+1)*a.seg,T_END)-k*a.seg),3), ues=len(seg_ue[k])) for k in range(nseg)]
# 3a. 停留時間：以 cell 序列（初次接入 + 每次換手）計；最後一段為設限（右截斷），另列
by = defaultdict(list)
for h in sorted(ho): by[h[1]].append(h)
dw = []; cens = []
for i in range(1,31):
    t0 = first_attach.get(i,(0,None))[0]; prev = t0
    for h in by.get(i,[]):
        dw.append(h[0]-prev); prev = h[0]
    cens.append(T_END-prev)
dw = np.array(dw)
q = lambda x,p: float(np.percentile(x,p)) if len(x) else None
R['dwell'] = dict(n_complete=len(dw), p10=q(dw,10), p25=q(dw,25), median=q(dw,50), p75=q(dw,75), p90=q(dw,90),
    share_lt_0_25=float((dw<0.25).mean()), share_lt_0_5=float((dw<0.5).mean()), share_lt_1=float((dw<1).mean()), share_lt_5=float((dw<5).mean()),
    censored_last_dwell_median=q(np.array(cens),50))
# 3b. A→B→A：換手 h_k（A→B）之後同 UE 下一筆為 B→A 且間隔 < 1 s
pp = 0; pp_any = 0; denom = 0
for i,L in by.items():
    for k in range(len(L)-1):
        denom += 1
        a1, b1 = L[k][2], L[k][3]; a2, b2 = L[k+1][2], L[k+1][3]
        if a2==b1 and b2==a1:
            pp_any += 1
            if L[k+1][0]-L[k][0] < 1.0: pp += 1
R['pingpong'] = dict(ho_with_next=denom, ABA_lt_1s=pp, ABA_lt_1s_share_of_ho_with_next=pp/denom if denom else None,
    ABA_lt_1s_share_of_all_ho=pp/len(ho) if ho else None, ABA_any_gap=pp_any)
# 每 UE
per = Counter(h[1] for h in ho)
R['per_ue'] = {i: dict(ho=per.get(i,0), rate=round(per.get(i,0)/T_END,3), cells=sorted({h[3] for h in by.get(i,[])}|{first_attach[i][1]})) for i in range(1,31)}
R['per_ue_summary'] = dict(zero=sum(1 for i in range(1,31) if per.get(i,0)==0), ge1_per_s=sum(1 for i in range(1,31) if per.get(i,0)/T_END>=1),
    ge0_5_per_s=sum(1 for i in range(1,31) if per.get(i,0)/T_END>=0.5), top5_share=sum(c for _,c in per.most_common(5))/len(ho) if ho else None)
# 3c. 最頻繁 UE：換手開始時來源／目標 SINR（MmWaveSinrTime 中各 cell 最近一筆 ≤ t_start）與初始位置
top = [i for i,_ in per.most_common(5)]
need = set(top) | set(range(1,31))
sinr = defaultdict(lambda: ([],[]))
with open(f'{W}/MmWaveSinrTime.txt') as f:
    for ln in f:
        p = ln.split()
        if len(p)!=4 or not p[0][0].isdigit(): continue
        i = int(p[1])
        L = sinr[(i,int(p[2]))]; L[0].append(float(p[0])); L[1].append(float(p[3]))
def at(i,c,t):
    T,V = sinr.get((i,c),([],[])); k = bisect.bisect_right(T,t)-1
    return V[k] if k>=0 else None
gaps = []
for t,i,s,g,ts in ho:
    vs, vg = at(i,s,ts), at(i,g,ts)
    if vs is not None and vg is not None: gaps.append(vg-vs)
gaps = np.array(gaps)
R['sinr_gap_all'] = dict(n=len(gaps), median=q(gaps,50), p10=q(gaps,10), p90=q(gaps,90), share_lt_3dB=float((gaps<3).mean()) if len(gaps) else None)
pos = {}
for ln in open(f'{W}/ues.txt'):
    m = re.search(r'label "(\d+)" at ([\d.]+),([\d.]+)', ln)
    if m: pos[int(m.group(1))] = (float(m.group(2)), float(m.group(3)))
enb = {}
for ln in open(f'{W}/enbs.txt'):
    m = re.search(r'label "(\d+)" at ([\d.]+),([\d.]+)', ln)
    if m: enb[int(m.group(1))] = (float(m.group(2)), float(m.group(3)))
d = lambda p,q_: math.hypot(p[0]-q_[0], p[1]-q_[1])
R['top_ues'] = []
for i in top:
    L = by[i]; g = []; srcs=[]; tgts=[]
    for t,_,s,c,ts in L:
        vs, vg = at(i,s,ts), at(i,c,ts)
        if vs is not None and vg is not None: g.append(vg-vs); srcs.append(vs); tgts.append(vg)
    pairs = Counter(f'{h[2]}->{h[3]}' for h in L)
    dist = sorted((round(d(pos[i],enb[c])), c) for c in enb) if i in pos else None
    R['top_ues'].append(dict(imsi=i, ho=len(L), pairs=dict(pairs.most_common(4)), src_sinr_med=q(np.array(srcs),50), tgt_sinr_med=q(np.array(tgts),50),
        gap_med=q(np.array(g),50), gap_min=float(min(g)) if g else None, init_pos=pos.get(i), nearest_cells_m=dist[:3] if dist else None,
        first_10=[(round(t,3),s,c) for t,_,s,c,_ in L[:10]]))
R['note'] = 'ues.txt 只有初始位置（scenario 於 t=0 輸出一次）；速度 3–10 m/s，46 秒內至多移動約 460 m，故位置僅供參考。ues.txt 標號假設 = IMSI。'
print(json.dumps(R, ensure_ascii=False, indent=1, default=str))
if a.json: json.dump(R, open(a.json,'w'), ensure_ascii=False, indent=1, default=str)
