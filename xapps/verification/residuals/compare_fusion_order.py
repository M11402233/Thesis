"""比較融合順序檢查之輸出(規格 docs/thesis/fusion_severity_order_spec.md §3 C1/C4)。

用法:python3 compare_fusion_order.py <dirA> <dirB> [檔名...]
逐檔比較 JSON／JSONL(.gz):列出相異路徑;時間類欄位(延遲、環境)另列,不算差異。
回傳碼:0 = 除時間類欄位外完全相同;1 = 有實質差異。
"""
import gzip, json, os, re, sys

TIMING = re.compile(r"(^|_)(ms|us|p\d+|mean_ms|lat|latency|runtime|env|environment|elapsed|time|cpu|"
                    r"benchmark|timing|wall|seconds|date|generated|commit)($|_)", re.I)


def load(p):
    op = gzip.open if p.endswith(".gz") else open
    with op(p, "rt", encoding="utf-8") as fh:
        if ".jsonl" in p:
            return [json.loads(l) for l in fh]
        return json.load(fh)


def walk(a, b, path, out):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b), key=str):
            walk(a.get(k, "<missing>"), b.get(k, "<missing>"), path + [str(k)], out)
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            walk(x, y, path + [f"[{i}]"], out)
    elif a != b:
        out.append(("/".join(path), a, b))


def main():
    da, db = sys.argv[1], sys.argv[2]
    names = sys.argv[3:] or sorted(f for f in os.listdir(db)
                                   if re.search(r"\.jsonl?(\.gz)?$", f))
    bad = 0
    for n in names:
        pa, pb = os.path.join(da, n), os.path.join(db, n)
        if not os.path.exists(pa):
            print(f"  ? {n}:{da} 無此檔"); continue
        diffs = []
        walk(load(pa), load(pb), [], diffs)
        real = [d for d in diffs if not any(TIMING.search(seg) for seg in d[0].split("/"))]
        tim = len(diffs) - len(real)
        if real:
            bad += 1
            print(f"  ✗ {n}:{len(real)} 處實質差異(時間類 {tim})")
            for p, x, y in real[:8]:
                print(f"      {p}: {str(x)[:70]} → {str(y)[:70]}")
        else:
            print(f"  ✓ {n}" + (f"(僅時間類 {tim} 處)" if tim else ""))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
