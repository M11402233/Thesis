import os
SRC = os.path.expanduser('~/oran-zt-kpm-verification/docs/thesis/thesis_v12_3.md')
_lines = open(SRC, encoding='utf-8').read().split('\n')
def L(a, b):
    return '\n'.join(_lines[a-1:b]) + '\n'
def rep(t, pairs):
    for o, n in pairs:
        c = t.count(o)
        if c != 1:
            raise SystemExit(f'REPLACE COUNT {c}: {o[:80]}')
        t = t.replace(o, n)
    return t
def out(name, t):
    open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ch4', name) if not os.path.isabs(name) else name, 'w', encoding='utf-8').write(t)
