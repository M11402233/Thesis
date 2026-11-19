import gzip,os,sys,json,re
S,F=sys.argv[1],sys.argv[2]
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
            st=f'DIFF line {n}: short={la.strip()[:120]!r} full={lb.strip()[:120]!r}'; break
    res[base]=st if st!='PREFIX' else f'PREFIX ({n} lines)'
bad={k:v for k,v in res.items() if not v.startswith('PREFIX')}
print(json.dumps({"n_files":len(res),"n_not_prefix":len(bad),"not_prefix":bad},ensure_ascii=False,indent=1))
