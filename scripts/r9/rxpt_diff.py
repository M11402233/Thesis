import gzip,sys,json
a,b=sys.argv[1],sys.argv[2]
fa,fb=gzip.open(a,'rt'),gzip.open(b,'rt')
n=0;nd=0;cols={};maxabs={};ex=[];nonnum=0
for la,lb in zip(fa,fb):
    n+=1
    if la==lb: continue
    nd+=1
    ta,tb=la.split(),lb.split()
    if len(ta)!=len(tb): nonnum+=1; ex.append((n,la,lb)) if len(ex)<5 else None; continue
    for i,(x,y) in enumerate(zip(ta,tb)):
        if x!=y:
            cols[i]=cols.get(i,0)+1
            try: d=abs(float(x)-float(y)); maxabs[i]=max(maxabs.get(i,0),d)
            except: nonnum+=1
    if len(ex)<3: ex.append((n,la.strip(),lb.strip()))
rest=sum(1 for _ in fa)+sum(1 for _ in fb)
print(json.dumps({"lines":n,"diff_lines":nd,"diff_cols":cols,"maxabs":maxabs,"nonnum_or_len":nonnum,"leftover":rest,"examples":ex}))
