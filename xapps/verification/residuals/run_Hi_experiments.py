#!/usr/bin/env python3
"""run_Hi_experiments.py v2 — H_i 成員轉移一致性驗證
   D1: Hampel robust z + 經驗 p 值(非參數) + θ 分位數分級
   D2: 瞬移近確定性斷言
   無自訂函數;門檻皆對應 3.4 的 θ_high=3 / θ_low=2(robust z 常態等價分位數)
"""
import collections, glob, os, json
import numpy as np

DATA_DIR = os.path.expanduser("~/oran-zt-kpm-verification/data/si_lstm_seeds")
OUT_DIR  = os.path.expanduser("~/oran-zt-kpm-verification/data/results")
THETA_HIGH = 3.0   # rejected 門檻(≈3σ, p_emp≲0.01)
THETA_LOW  = 2.0   # low-trust 門檻(≈2σ)

def load(path):
    rec=collections.defaultdict(dict)
    with open(path) as fh:
        fh.readline()
        for line in fh:
            p=line.split('\t')
            if len(p)<4: continue
            try: w=int(float(p[0])); cell=int(p[2]); imsi=int(p[3])
            except: continue
            rec[imsi].setdefault(w,set()).add(cell)
    return rec

def state_seq(wm, all_w):
    s=[]
    for w in all_w:
        cells=wm.get(w,set())
        if any(c!=1 for c in cells): s.append('mmw')
        elif 1 in cells: s.append('lte')
        else: s.append('absent')
    return s

def mmw_cell_seq(wm, all_w):
    return [frozenset(c for c in wm.get(w,set()) if c!=1) for w in all_w]

def dwell_events(seq):
    ev=[]; i=0
    while i<len(seq):
        if seq[i]=='mmw':
            j=i+1; run=0
            while j<len(seq) and seq[j]=='lte': run+=1; j+=1
            if run>0: ev.append(run)
            i=j
        else: i+=1
    return ev

# ---------- D1: 建 per-UE Hampel 中心/離散 + 乾淨經驗分布 ----------
def build_baseline(train_files):
    dwell=collections.defaultdict(list)       # imsi -> 乾淨停留事件
    ltefrac=collections.defaultdict(list)
    for f in train_files:
        rec=load(f); all_w=sorted(set(w for im,wm in rec.items() for w in wm))
        for imsi,wm in rec.items():
            seq=state_seq(wm,all_w)
            dwell[imsi]+=dwell_events(seq)
            na=sum(1 for s in seq if s!='absent')
            if na: ltefrac[imsi].append(sum(1 for s in seq if s=='lte')/na)
    # per-UE Hampel 參數 + group fallback(依LTE佔比分常駐/邊緣兩群)
    hampel={}; emp={}
    grp_events={'resident':[], 'edge':[]}
    for imsi,d in dwell.items():
        lf=np.mean(ltefrac[imsi]) if ltefrac[imsi] else 0.5
        grp='edge' if lf>=0.55 else 'resident'
        grp_events[grp]+=d
    for imsi,d in dwell.items():
        if len(d)>=8:
            med=np.median(d); mad=np.median(np.abs(np.array(d)-med))
            hampel[imsi]=(med, 1.4826*mad if mad>0 else 1.0)
            emp[imsi]=sorted(d)
    return hampel, emp, {k:sorted(v) for k,v in grp_events.items()}, ltefrac

def robust_z(d, med, sigma):
    return (d-med)/sigma if sigma>0 else 0.0

def emp_pvalue(d, clean_sorted):
    if not clean_sorted: return 1.0
    ge=sum(1 for x in clean_sorted if x>=d)
    return ge/len(clean_sorted)

def grade(z):
    if z>=THETA_HIGH: return 'rejected'
    if z>=THETA_LOW:  return 'low-trust'
    return 'trusted'

# ---------- 攻擊注入 ----------
def inject_teleport(mmw_seq, state, t0):
    ms=list(mmw_seq)
    for t in range(t0, len(ms)-1):
        if ms[t]:
            cur=set(ms[t]); other=frozenset({(max(cur)%7)+2})
            if other!=ms[t]:
                ms[t+1]=other; return ms, t+1
    return ms, None

def inject_disappear(seq, t0, length):
    s=list(seq)
    for t in range(t0, min(t0+length,len(s))): s[t]='lte'
    return s

def detect_D2(mmw_seq, state):
    cnt=0
    for t in range(1,len(mmw_seq)):
        if state[t]=='mmw' and state[t-1]=='mmw':
            a,b=mmw_seq[t-1],mmw_seq[t]
            if a and b and a!=b and not (a&b): cnt+=1
    return cnt

def main():
    files=sorted(glob.glob(os.path.join(DATA_DIR,"ues1_t300_seed*.txt"))) or \
          sorted(glob.glob("ues1_t300_seed*.txt"))
    seeds=[os.path.basename(f).split('seed')[-1].replace('.txt','') for f in files]
    print(f"載入 {len(seeds)} seeds: {seeds}")
    results={'theta_high':THETA_HIGH,'theta_low':THETA_LOW}

    # === D2 ===
    clean=0
    for f in files:
        rec=load(f); all_w=sorted(set(w for im,wm in rec.items() for w in wm))
        for imsi,wm in rec.items():
            clean+=detect_D2(mmw_cell_seq(wm,all_w), state_seq(wm,all_w))
    det=0; nin=0
    for f in files:
        rec=load(f); all_w=sorted(set(w for im,wm in rec.items() for w in wm))
        for imsi,wm in rec.items():
            ms,st=mmw_cell_seq(wm,all_w),state_seq(wm,all_w)
            ms2,pos=inject_teleport(ms,st,len(all_w)//2)
            if pos:
                nin+=1; st2=list(st); st2[pos]='mmw'
                if detect_D2(ms2,st2)>clean: det+=1
    print(f"\n=== D2 瞬移 ===")
    print(f"  乾淨基線={clean}(應0), 注入{nin}例偵測{det} → 偵測率{det/max(nin,1):.2f}")
    results['D2']={'clean_baseline':clean,'inject':nin,'detected':det}

    # === D1: LOSO,輸出 robust z / 經驗p值 / θ分級 ===
    print(f"\n=== D1 消失: robust z + 經驗p值 + θ分級(θ_high={THETA_HIGH},θ_low={THETA_LOW}) ===")
    rows=collections.defaultdict(lambda: {'n':0,'rejected':0,'low':0,'trusted':0,'z':[],'p':[]})
    for ts in seeds:
        hampel,emp,grp,ltefrac=build_baseline([f for f,s in zip(files,seeds) if s!=ts])
        tf=[f for f,s in zip(files,seeds) if s==ts][0]
        rec=load(tf); all_w=sorted(set(w for im,wm in rec.items() for w in wm))
        for imsi,wm in rec.items():
            seq=state_seq(wm,all_w)
            na=sum(1 for s in seq if s!='absent')
            lf=sum(1 for s in seq if s=='lte')/na if na else 0.5
            grpname='edge' if lf>=0.55 else 'resident'
            if imsi in hampel: med,sig=hampel[imsi]; clean_d=emp[imsi]
            else:
                cd=grp[grpname]; med=np.median(cd) if cd else 2
                mad=np.median(np.abs(np.array(cd)-med)) if cd else 1
                sig=1.4826*mad if mad>0 else 1.0; clean_d=cd
            # 直接以『目標 z 值』反推注入長度
            for target_z in [1.5, 2.5, 4.0]:
                L=max(2,int(round(med+target_z*sig)))
                t0=len(all_w)//2
                # 找一個乾淨的注入點:t0起本來是mmw(不黏到既有lte段),避免測量污染
                inj=t0
                while inj<len(seq)-L and seq[inj]!='mmw': inj+=1
                st2=inject_disappear(seq,inj,L)
                # 只量注入點開始的那段連續lte長度(注入的攻擊本身)
                d=0; k=inj
                while k<len(st2) and st2[k]=='lte': d+=1; k+=1
                z=robust_z(d,med,sig); pv=emp_pvalue(d,clean_d); g=grade(z)
                key=f"z={target_z:.1f}"
                r=rows[key]; r['n']+=1; r['z'].append(z); r['p'].append(pv)
                r[{'rejected':'rejected','low-trust':'low','trusted':'trusted'}[g]]+=1
    for k in sorted(rows,key=lambda x:float(x.split('=')[1])):
        r=rows[k]
        print(f"  注入{k}: rejected率={r['rejected']/r['n']:.2f} "
              f"(mean z={np.mean(r['z']):.1f}, mean p_emp={np.mean(r['p']):.3f}, "
              f"low-trust={r['low']}/{r['n']})")
        results.setdefault('D1',{})[k]={'rejected_rate':r['rejected']/r['n'],
            'mean_z':float(np.mean(r['z'])),'mean_p_emp':float(np.mean(r['p']))}
    print("\n判讀:注入越長→z越高、p_emp越小→rejected率跳升;低倍數應留在low-trust(不誤判邊緣UE)")

if __name__=="__main__": main()
