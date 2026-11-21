import gzip,os,sys,json,re
# P-6（短跑須為完整跑之前綴）。短跑之差異不得早於 SIMTIME_SHORT − 0.1 s：scenario-three.cc:977 為 clientApp.Stop(simTime − 0.1)，
# 短跑最後 0.1 s 無新流量，干擾與排程因而不同（2026-11-22 查明；D-30P 之 P-6 同一現象）。此判準由程式碼推得，非由資料決定。
# 用法：p6_prefix.py <short_aux> <full_aux> [SIMTIME_SHORT=31]
S,F=sys.argv[1],sys.argv[2]; SIMT=float(sys.argv[3]) if len(sys.argv)>3 else 31.0
T_APP=SIMT-0.1                      # 流量停止時間
AGG={'DlPdcpStats.txt','DlRlcStats.txt','UlRlcStats.txt','R7b_rlc_rx_tag_hist.txt'}   # 結尾彙總檔（依總模擬時間／累計寫出；非逐行時序檔）
FRAME={'EnbSchedAllocTraces.txt','DlPhyTransmissionTrace.txt'}                         # 第 1 欄為訊框編號（10 ms）
def tline(name,l):
    tok=re.split(r'[\t, ]+',l.strip())
    for x in tok[:3]:
        try: v=float(x)
        except ValueError: continue
        if name in FRAME: return v*0.01
        return v/1e9 if v>1e6 else v
    return None
def allowed(name,l):
    """第一個差異行是否落在允許範圍。回傳 (是否, 說明)"""
    if name in AGG: return True,'AGG'
    t=tline(name,l)
    if t is None: return False,'t=None'
    if re.match(r'D[lu]E2.*Lte',name) or name.startswith('UlE2'):   # 窗列檔：窗起點 ≥ SIMT−1（含最後 0.1 s 之窗）
        return t>=SIMT-1.0-1e-9, f'window start {t:g}'
    return t>=T_APP-1e-9, f't={t:g}'

SKIP={'mem_trace.tsv','run.log','meta.txt'}
def op(p): return gzip.open(p,'rt') if p.endswith('.gz') else open(p)
def strip(name,l):
    if re.match(r'(du-cell|cu-cp-cell|cu-up-cell)-',name): return l.split(',',1)[1] if ',' in l else l
    if name.startswith('bsState'):
        f=l.split(); return ' '.join(f[:1]+f[2:])  # col 2 = UNIX wall clock
    return l
res={}
for fn in sorted(os.listdir(S)):
    base=fn[:-3] if fn.endswith('.gz') else fn
    if base in SKIP or base.startswith('check_r9'): continue
    fp=os.path.join(F,fn)
    if not os.path.exists(fp):
        alt=os.path.join(F,base) if fn.endswith('.gz') else fp+'.gz'
        if os.path.exists(alt): fp=alt
        else: res[base]='MISSING_IN_FULL'; continue
    a,b=op(os.path.join(S,fn)),op(fp); n=0; st='PREFIX'
    for la in a:
        lb=b.readline(); n+=1
        if strip(base,la)!=strip(base,lb):
            ok,why=allowed(base,la)
            st=(f'EXPECTED_END_EFFECT line {n} ({why})' if ok else f'DIFF line {n} ({why}): short={la.strip()[:120]!r} full={lb.strip()[:120]!r}'); break
    res[base]=st if st!='PREFIX' else f'PREFIX ({n} lines)'
bad={k:v for k,v in res.items() if not (v.startswith('PREFIX') or v.startswith('EXPECTED_END_EFFECT'))}
print(json.dumps({"n_files":len(res),"simtime_short":SIMT,"n_expected_end_effect":sum(v.startswith("EXPECTED") for v in res.values()),"n_not_prefix":len(bad),"not_prefix":bad,"files":res},ensure_ascii=False,indent=1))
# 失敗時須回傳非零（d30p1_chain.sh 以結束碼判斷 P-6）：有任何非前綴／缺檔，或完全沒有可比對之檔案
sys.exit(0 if (res and not bad) else 1)
