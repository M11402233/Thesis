#!/usr/bin/env python3
"""R-7 第 1 項（ByteTagList free list 關閉）之逐位等價檢查。只讀。
比對 <run> 與 <ref> 共同之輸出檔：
  - 一般 trace 檔：逐位相同（ref 若較長，只比 run 之完整行數前綴；最後一行可能不完整故不比）。
  - E2 報表（du-cell-*、cu-cp-cell-*、cu-up-cell-*）：首欄為實際時間（CLAUDE.md），去掉首欄後逐行比較。
  - 跳過：meta.txt、mem.tsv、run.log、*_exact.txt、*_percell.txt（R-5 加裝輸出，ref 可能沒有）。
用法：check_r7_equivalence.py <run_dir> <ref_dir> [--json out]；任何差異 exit 1。
"""
import os, sys, json, argparse
ap = argparse.ArgumentParser(); ap.add_argument("run"); ap.add_argument("ref"); ap.add_argument("--json"); a = ap.parse_args()
SKIP = {"meta.txt", "mem.tsv", "run.log", "print_massif.log"}
E2 = ("du-cell-", "cu-cp-cell-", "cu-up-cell-")
def lines(p):
    with open(p, "rb") as f: L = f.read().split(b"\n")
    return L[:-1]  # 最後一段（可能不完整或空）不比
res = {}; bad = 0
for fn in sorted(set(os.listdir(a.run)) & set(os.listdir(a.ref))):
    if fn in SKIP or fn.endswith(("_exact.txt", "_percell.txt")) or not os.path.isfile(os.path.join(a.run, fn)): continue
    A, B = lines(os.path.join(a.run, fn)), lines(os.path.join(a.ref, fn))
    if fn.startswith(E2):
        A = [l.split(b",", 1)[-1] if b"," in l else l.split(b"\t", 1)[-1] for l in A]
        B = [l.split(b",", 1)[-1] if b"," in l else l.split(b"\t", 1)[-1] for l in B]
    n = min(len(A), len(B)); diff = next((i for i in range(n) if A[i] != B[i]), None)
    res[fn] = {"lines_run": len(A), "lines_ref": len(B), "compared": n, "first_diff_line": diff}
    if diff is not None or n == 0: bad += 1
out = {"run": a.run, "ref": a.ref, "files": len(res), "files_with_diff_or_empty": bad,
       "diffs": {k: v for k, v in res.items() if v["first_diff_line"] is not None or v["compared"] == 0}}
print(json.dumps(out, ensure_ascii=False, indent=1))
if a.json: json.dump({**out, "all": res}, open(a.json, "w"), ensure_ascii=False, indent=1)
sys.exit(1 if bad else 0)
