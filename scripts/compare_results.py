# -*- coding: utf-8 -*-
"""compare_results.py — 逐檔比對兩個結果目錄（重現檢查用）。

用法：python3 scripts/compare_results.py <既有目錄> <重跑目錄> [--json out.json]

- *.json：遞迴比對所有欄位；數值須逐位相同。鍵名看起來是執行時間／延遲／時間戳者（TIMING）另列，不算不一致。
- *.jsonl、*.jsonl.gz：逐行內容比對（先試逐位相同，再試解析後相同）。
- 圖檔（*.png）與子目錄 _logs、_pipeline_logs、drl、planB_models 不比對。
- 只存在於一邊之檔案分別列出。
"""
import sys, os, json, gzip, re, argparse

TIMING = re.compile(r"(^|_)(ms|us|sec|secs|seconds|time|times|elapsed|latency|lat|p50|p90|p95|p99|p999|mean_ms|max_ms|"
                    r"timestamp|date|utc|commit|host|wall|runtime|duration|cpu|benchmark|started|finished)($|_)", re.I)
SKIP_DIRS = {"_logs", "_pipeline_logs", "drl", "planB_models"}


def is_timing(path):
    return any(TIMING.search(str(k)) for k in path)


def walk(a, b, path, out):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b), key=str):
            if k not in a or k not in b:
                out.append((path + [k], "key-only-in-" + ("old" if k in a else "new"), None, None)); continue
            walk(a[k], b[k], path + [k], out)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append((path, "len", len(a), len(b)))
        for i, (x, y) in enumerate(zip(a, b)):
            walk(x, y, path + [i], out)
    else:
        if a != b and not (isinstance(a, float) and isinstance(b, float) and a != a and b != b):
            out.append((path, "value", a, b))


def read_lines(p):
    op = gzip.open if p.endswith(".gz") else open
    with op(p, "rt", encoding="utf-8") as f:
        return f.read().splitlines()


def files(root):
    res = {}
    for d, sub, fs in os.walk(root):
        sub[:] = [s for s in sub if s not in SKIP_DIRS]
        for f in fs:
            if f.endswith((".json", ".jsonl", ".jsonl.gz")):
                p = os.path.join(d, f); res[os.path.relpath(p, root)] = p
    return res


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("old"); ap.add_argument("new"); ap.add_argument("--json")
    a = ap.parse_args()
    fo, fn = files(a.old), files(a.new)
    rep = {"only_old": sorted(set(fo) - set(fn)), "only_new": sorted(set(fn) - set(fo)), "files": {}}
    n_same = n_timing_only = n_diff = 0
    for rel in sorted(set(fo) & set(fn)):
        po, pn = fo[rel], fn[rel]
        if open(po, "rb").read() == open(pn, "rb").read():
            n_same += 1; rep["files"][rel] = "identical"; continue
        if rel.endswith(".json"):
            diffs = []
            walk(json.load(open(po, encoding="utf-8")), json.load(open(pn, encoding="utf-8")), [], diffs)
        else:
            lo, ln = read_lines(po), read_lines(pn)
            if len(lo) != len(ln):
                diffs = [([], "n_lines", len(lo), len(ln))]
            else:
                diffs = []
                for i, (x, y) in enumerate(zip(lo, ln)):
                    if x != y:
                        try:
                            walk(json.loads(x), json.loads(y), [i], diffs)
                        except ValueError:
                            diffs.append(([i], "line", x[:80], y[:80]))
        real = [d for d in diffs if not is_timing(d[0])]
        tim = [d for d in diffs if is_timing(d[0])]
        if not real:
            n_timing_only += 1
            rep["files"][rel] = {"status": "timing-only", "n_timing": len(tim)}
        else:
            n_diff += 1
            rep["files"][rel] = {"status": "DIFF", "n_real": len(real), "n_timing": len(tim),
                                 "first": [{"path": "/".join(map(str, p)), "kind": k, "old": o, "new": n}
                                           for p, k, o, n in real[:15]]}
    print(f"{a.old}  vs  {a.new}")
    print(f"  逐位相同 {n_same}；僅時間欄位不同 {n_timing_only}；內容不同 {n_diff}")
    print(f"  只在既有目錄：{rep['only_old']}")
    print(f"  只在重跑目錄：{rep['only_new']}")
    for rel, v in rep["files"].items():
        if isinstance(v, dict) and v["status"] == "DIFF":
            print(f"  ✗ {rel}：{v['n_real']} 處不同（另有時間欄位 {v['n_timing']}）")
            for d in v["first"][:5]:
                print(f"      {d['path']} [{d['kind']}] {str(d['old'])[:60]} → {str(d['new'])[:60]}")
        elif isinstance(v, dict):
            print(f"  ~ {rel}：僅時間欄位（{v['n_timing']}）")
    if a.json:
        json.dump(rep, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    return 1 if n_diff else 0


if __name__ == "__main__":
    sys.exit(main())
