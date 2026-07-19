# 規則回放:對每種攻擊,實際跑 C_i/S_i/H_i 三個判定,套階層融合規則,驗證邏輯無矛盾
import collections, glob
import numpy as np

def load_full(path):
    """回傳 per-window: {cell: {imsi: delay_ms}}, 及每窗全域IMSI集合"""
    W=collections.defaultdict(lambda: collections.defaultdict(dict))
    with open(path) as fh:
        fh.readline()
        for line in fh:
            p=line.split('\t')
            if len(p)<11: continue
            try:
                w=int(float(p[0])); cell=int(p[2]); imsi=int(p[3]); d=float(p[10])
            except: continue
            W[w][cell][imsi]=d*1000
    return W

files=sorted(glob.glob('/home/cindy1/oran-zt-kpm-verification/data/si_lstm_seeds/ues1_t300_seed420*.txt'))
N_KNOWN=7
# S_i 全域尺度
allv=[]
for f in files:
    W=load_full(f)
    for w in W:
        for c in W[w]:
            if c!=1: allv+=list(W[w][c].values())
med_g=np.median(allv); SCALE=1.4826*np.median(np.abs(np.array(allv)-med_g))
TAU_S=4.0

def global_imsi_set(Wt):
    s=set()
    for c in Wt:
        s|=set(Wt[c].keys())
    return s

# ---- 三個殘差的判定函式(對單一窗) ----
def C_i_verdict(Wt):
    n=len(global_imsi_set(Wt))
    return 'violated' if n!=N_KNOWN else 'conserved', n

def S_i_verdict(Wt, target_cell):
    mmw=[c for c in Wt if c!=1]
    if target_cell not in Wt or target_cell==1: return 'n/a',None
    peers=[c for c in mmw if c!=target_cell]
    if len(peers)<2: return 'unavailable',None
    tgt=np.mean(list(Wt[target_cell].values()))
    peer_delays=[np.mean(list(Wt[c].values())) for c in peers]
    z=abs(tgt-np.median(peer_delays))/SCALE
    return ('violated' if z>TAU_S else 'normal'), round(z,2)

def H_i_D2_verdict(prev_cells_of_imsi, cur_cells_of_imsi):
    """teleport: imsi 從 mmwA 直接到 mmwB 無 LTE 過渡"""
    for imsi in cur_cells_of_imsi:
        prev=prev_cells_of_imsi.get(imsi,set())
        cur=cur_cells_of_imsi[imsi]
        prev_mmw={c for c in prev if c!=1}; cur_mmw={c for c in cur if c!=1}
        if prev_mmw and cur_mmw and not (prev_mmw & cur_mmw) and 1 not in cur:
            return 'violated'
    return 'normal'

# ---- 階層融合規則(對齊修正後的定義:D1不再hard veto)----
def fuse(c_v, s_v, h_d2_v, h_d1_evidence):
    # 第一層 hard veto
    if c_v=='violated': return 'rejected','C_i hard veto (基數違反)'
    if h_d2_v=='violated': return 'rejected','H_i-D2 hard veto (瞬移)'
    # 第二層 統計證據
    if s_v=='violated' and h_d1_evidence:
        return 'rejected','S_i + H_i-D1 交叉佐證'
    if s_v=='violated':
        return 'low-trust','S_i 單獨違反→多窗後升級'
    if h_d1_evidence:
        return 'low-trust','H_i-D1 單獨→investigation'
    # 第三層 證據不可得
    if s_v=='unavailable':
        return 'abstain','S_i 證據不可得(peer<2)'
    return 'trusted','無反例'

# ---- 對每種攻擊,取一個代表窗實際跑 ----
def get_imsi_cells(Wt):
    m=collections.defaultdict(set)
    for c in Wt:
        for imsi in Wt[c]: m[imsi].add(c)
    return m

f=files[0]; W=load_full(f); wins=sorted(W)
# 找一個 mmWave cell 多、且有雙掛的窗
tw=None
for w in wins[10:]:
    mmw=[c for c in W[w] if c!=1]
    if len(mmw)>=3: tw=w; break
prev_w=tw-1 if tw-1 in W else tw

print(f"規則回放(seed {f.split('seed')[-1][:4]}, window {tw}, {len([c for c in W[tw] if c!=1])} 個 mmWave cell)")
print("="*78)

results=[]
target=[c for c in W[tw] if c!=1][0]

# baseline
Wt=W[tw]
c,_=C_i_verdict(Wt); s,z=S_i_verdict(Wt,target)
d2=H_i_D2_verdict(get_imsi_cells(W[prev_w]),get_imsi_cells(Wt))
dec,why=fuse(c,s,d2,False)
results.append(('baseline(無攻擊)',c,f'{s}',d2,'—',dec,why))

# A. fabrication +1
Wa={cc:dict(W[tw][cc]) for cc in W[tw]}
Wa[target]=dict(Wa[target]); Wa[target][9999]=med_g  # 偽造IMSI,正常delay
c,_=C_i_verdict(Wa); s,z=S_i_verdict(Wa,target)
dec,why=fuse(c,s,'normal',True)  # 新IMSI觸發D1 new-member
results.append(('A.灌水+1',c,f'{s}',d2,'D1 new-member',dec,why))

# E2b. LTE遮蔽depletion:刪一個雙掛UE在mmw的紀錄(全域集合不變)
dual=[i for i in W[tw][target] if 1 in get_imsi_cells(W[tw]).get(i,set())]
Wd={cc:dict(W[tw][cc]) for cc in W[tw]}
if dual:
    victim=dual[0]; Wd[target]=dict(Wd[target])
    if victim in Wd[target]: del Wd[target][victim]
c,_=C_i_verdict(Wd); s,z=S_i_verdict(Wd,target)
dec,why=fuse(c,s,'normal',True)  # D1 消失證據
results.append(('E2b.LTE遮蔽虛減',c,f'{s}',d2,'D1 disappear',dec,why))

# delay drift:把target的delay拉到共識+6σ
Wdr={cc:dict(W[tw][cc]) for cc in W[tw]}
Wdr[target]={i:med_g+6*SCALE for i in Wdr[target]}
c,_=C_i_verdict(Wdr); s,z=S_i_verdict(Wdr,target)
dec,why=fuse(c,s,'normal',False)
results.append(('delay drift',c,f'{s}(z={z})',d2,'—',dec,why))

# teleport:偽造某imsi直接跳到別的mmw cell
imsi_cells_prev=get_imsi_cells(W[prev_w])
imsi_cells_cur=get_imsi_cells(W[tw])
# 人工製造:取一個prev在mmwA的imsi,cur塞到另一個mmwB且無LTE
tele_prev=dict(imsi_cells_prev)
tele_cur=dict(imsi_cells_cur)
some=[i for i in imsi_cells_prev if any(c!=1 for c in imsi_cells_prev[i])]
if some:
    ii=some[0]; other=[c for c in W[tw] if c!=1 and c not in imsi_cells_prev[ii]]
    if other: tele_cur[ii]={other[0]}
d2t=H_i_D2_verdict(tele_prev,tele_cur)
c,_=C_i_verdict(W[tw]); s,z=S_i_verdict(W[tw],target)
dec,why=fuse(c,s,d2t,False)
results.append(('teleport',c,f'{s}',d2t,'—',dec,why))

# 守恆式替換:+1假 -1真(基數不變),delay正常
Wc={cc:dict(W[tw][cc]) for cc in W[tw]}
Wc[target]=dict(Wc[target])
real=list(Wc[target].keys())
if real:
    del Wc[target][real[0]]; Wc[target][8888]=med_g  # 換一個,基數守恆
c,_=C_i_verdict(Wc); s,z=S_i_verdict(Wc,target)
dec,why=fuse(c,s,'normal',True)  # 成員組成變→D1/轉移證據
results.append(('守恆式替換',c,f'{s}',d2,'D1/轉移',dec,why))

# 印表
print(f"{'攻擊':<16}{'C_i':<11}{'S_i':<14}{'H-D2':<10}{'H-D1':<14}{'決策':<10}{'觸發規則'}")
print("-"*78)
for r in results:
    print(f"{r[0]:<16}{r[1]:<11}{r[2]:<14}{r[3]:<10}{r[4]:<14}{r[5]:<10}{r[6]}")

# 邏輯無矛盾檢查
print("\n邏輯一致性檢查:")
checks=[
 ('baseline→trusted', results[0][5]=='trusted'),
 ('灌水→C_i veto→rejected', results[1][5]=='rejected'),
 ('LTE遮蔽虛減→C_i conserved但D1證據→非trusted', results[2][5]!='trusted' and results[2][1]=='conserved'),
 ('delay drift→S_i violated→至少low-trust', results[3][5] in ('low-trust','rejected')),
 ('teleport→D2 veto→rejected', results[4][5]=='rejected'),
 ('守恆替換→C_i conserved但非trusted', results[5][5]!='trusted' and results[5][1]=='conserved'),
]
for name,ok in checks:
    print(f"  {'✓' if ok else '✗ 矛盾!'} {name}")
print(f"\n{'全部一致,融合規則無邏輯矛盾' if all(ok for _,ok in checks) else '有矛盾需修規則'}")
