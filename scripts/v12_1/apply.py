import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from edits import E
src='docs/thesis/thesis_v12.md'; dst='docs/thesis/thesis_v12_1.md'
b=open(src,'rb').read(); crlf=b'\r\n' in b
s=b.decode('utf-8').replace('\r\n','\n')
bad=0
for i,(o,n) in enumerate(E):
    c=s.count(o)
    if c!=1: print(f'[{i}] count={c}: {o[:60]!r}'); bad+=1
if bad: sys.exit(f'{bad} edits not applicable; nothing written')
for o,n in E:
    assert s.count(o)==1, o[:40]
    s=s.replace(o,n)
if crlf: s=s.replace('\n','\r\n')
open(dst,'wb').write(s.encode('utf-8')); print('written',dst,len(E),'edits; crlf',crlf)
