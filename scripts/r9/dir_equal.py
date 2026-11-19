import os,sys,re,json
A,B=sys.argv[1],sys.argv[2]
SKIP={'run.log','meta.txt','EXIT','mem_trace.tsv'}
def norm(name,l):
    if re.match(r'(du-cell|cu-cp-cell|cu-up-cell)-',name): return l.split(',',1)[1] if ',' in l else l
    if name.startswith('bsState'):
        f=l.split(); return ' '.join(f[:1]+f[2:])
    return l
fa=set(os.listdir(A))-SKIP; fb=set(os.listdir(B))-SKIP
res={"only_A":sorted(fa-fb),"only_B":sorted(fb-fa),"diff":{}}
for f in sorted(fa&fb):
    la=open(os.path.join(A,f),errors='replace').readlines(); lb=open(os.path.join(B,f),errors='replace').readlines()
    if len(la)!=len(lb): res["diff"][f]=f"lines {len(la)} vs {len(lb)}"; continue
    for i,(x,y) in enumerate(zip(la,lb)):
        if norm(f,x)!=norm(f,y): res["diff"][f]=f"line {i+1}"; break
res["n_compared"]=len(fa&fb); res["pass"]=not res["diff"] and not res["only_A"] and not res["only_B"]
print(json.dumps(res,indent=1))
