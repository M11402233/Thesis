"""S3-TM3: per window, (a) registered UEs absent from the report union (no row), (b) UEs with a row but no new DL Rx in the window
(cumulative nRxPDUs unchanged = 'absent' under interval semantics), (c) UEs appearing in >=2 cells' rows in the same window."""
import sys, glob, collections, json, numpy as np
N = 30; out = {}
for f in sorted(glob.glob("S3-TM3_ues30_t300_seed*.txt")):
    seed = f.split("seed")[1][:4]
    rows = collections.defaultdict(lambda: collections.defaultdict(set)); nrx = collections.defaultdict(dict)
    for l in open(f):
        p = l.split("\t")
        if l.startswith("%") or len(p) < 11: continue
        w, c, i, lc = int(float(p[0])), int(p[2]), int(p[3]), int(p[5])
        if lc != 3: continue
        rows[w][i].add(c); nrx[i][w] = nrx[i].get(w, 0) + int(p[8])
    W = sorted(w for w in rows if w <= 299)
    absent, norx, dbl, dbl_mmw = [], [], [], []
    for w in W:
        present = rows[w]; absent.append(N - len(present))
        norx.append(sum(1 for i in present if w > 0 and nrx[i].get(w) == nrx[i].get(w - 1)))
        dbl.append(sum(1 for i, cs in present.items() if len(cs) > 1))
    a, b, d = map(np.array, (absent, norx, dbl))
    out[seed] = {"windows": len(W),
        "absent_no_row": {"max": int(a.max()), "windows_with_any": int((a > 0).sum()), "total": int(a.sum())},
        "row_but_no_new_rx": {"mean_per_window": float(b.mean()), "max": int(b.max()), "windows_with_any": int((b > 0).sum())},
        "in_two_or_more_cells": {"max": int(d.max()), "windows_with_any": int((d > 0).sum())}}
print(json.dumps(out, indent=1))
