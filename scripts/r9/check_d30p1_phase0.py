#!/usr/bin/env python3
"""D-30P1 acceptance checks (docs/thesis/D30P1_r10_recollection_spec.md §3).  Read-only.  Exit 1 on failure.
  q0  <p1_aux> <ns3_dir> <tag>            Q-0: meta.txt records ZT_R7_S2=1 and ZT_R10_RETX_TAG=<tag>; binary / lte-rlc-am.cc md5
                                          recorded in meta equal the current files of <ns3_dir>.
  q2  <p1_aux> <p_aux>                    Q-2a/b/d vs D-30P (r9-g13) of the same seed:
        a  every file NOT in the allowlist is identical after decompression (wall-clock first column of du-cell/cu-* and bsState
           time removed, exactly as P-2); the two directories have the same file set (SKIP excluded).
        b  allowlist files: same line count and same non-delay fields; only the listed delay fields may differ.
        d  DlE2RlcStats_percell.txt: delaySumNs (cumulative) never smaller than D-30P; a row where it is larger must have
           D-30P cumulative nRxZeroDelay > 0 for that key.
  q2c <p1_analysis_main> <d30_analysis_main>   Q-2c: same rows; only columns 11-14 (delay, stdDev, min, max) may differ."""
import os, sys, json, hashlib, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_d30p_phase0 as C

RLC_DELAY = {  # file -> set of allowed differing 0-based tab columns (data rows)
    "DlE2RlcStats.txt": {10, 11, 12, 13}, "DlE2RlcStatsLte.txt": {10, 11, 12, 13}, "DlRlcStats.txt": {10, 11, 12, 13},
    "DlE2RlcStats_exact.txt": {9}, "DlE2RlcStatsLte_exact.txt": {9},
    "DlE2RlcStats_percell.txt": {9}, "DlE2RlcStatsLte_percell.txt": {9},
    "DlE2RlcStats_r9rx.txt": {6, 7}, "DlE2RlcStatsLte_r9rx.txt": {6, 7},
}
DU_ALLOWED = {"DRB.UEThpDl.UEID"}
ALLOW = set(RLC_DELAY) | {"R7b_rlc_rx_tag_hist.txt"} | {f"du-cell-{c}.txt" for c in range(2, 9)}


def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def raw_lines(d, n):
    f = C.opn(d, n); L = f.read().decode().split("\n"); f.close(); return L


def q0(aux, ns3, tag):
    m = open(os.path.join(aux, "meta.txt")).read()
    bad = []
    if "ZT_R7_S2=1 " not in m: bad.append("ZT_R7_S2")
    if f"ZT_R10_RETX_TAG={tag} " not in m: bad.append("ZT_R10_RETX_TAG")
    want = {os.path.join(ns3, "build/scratch/ns3.38.rc1-scenario-three-optimized"), os.path.join(ns3, "src/lte/model/lte-rlc-am.cc")} | \
        {os.path.join(ns3, f"build/lib/libns3.38.rc1-{m}-optimized.so") for m in ("network", "lte", "mmwave")}   # 修補編入 lte 函式庫
    rec = {l.split()[1]: l.split()[0] for l in m.splitlines() if len(l.split()) == 2 and l.split()[1].startswith("/")}
    for p in want:
        if rec.get(p) != md5(p): bad.append(f"md5 {os.path.basename(p)}")
    return {"check": "Q-0", "pass": not bad, "failed": bad}


def q2(pa1, pa):
    res = {}; bad = []
    n1 = set(C.names(pa1)) - C.SKIP; n0 = set(C.names(pa)) - C.SKIP
    if n1 != n0:
        bad.append("file set"); res["only_in_p1"] = sorted(n1 - n0); res["only_in_p"] = sorted(n0 - n1)
    for n in sorted(n0 & n1):
        if n not in ALLOW:
            ok = C.lines(pa1, n) == C.lines(pa, n); res[n] = "identical" if ok else "DIFF"
            ok or bad.append(n); continue
        A = raw_lines(pa1, n); B = raw_lines(pa, n)
        if n == "R7b_rlc_rx_tag_hist.txt":                      # 區間數依設計會變（無時間戳之區間消失）；只比總數
            tot = lambda L: sum(int(l.split("\t")[3]) for l in L if l and not l.startswith("%"))
            ok = tot(A) == tot(B); res[n] = f"total {tot(A)} vs {tot(B)}"; ok or bad.append(n); continue
        if len(A) != len(B):
            res[n] = f"line count {len(A)} vs {len(B)}"; bad.append(n); continue
        if n.startswith("du-cell-"):
            hdr = A[0].split(",")
            cols = set(); shape = A[0] != B[0]
            for x, y in zip(A[1:], B[1:]):
                x = x.split(",")[1:]; y = y.split(",")[1:]          # wall-clock first column removed (as P-2)
                if len(x) != len(y): shape = True; continue
                cols |= {hdr[i + 1] for i, (u, v) in enumerate(zip(x, y)) if u != v}
            ok = not shape and cols <= DU_ALLOWED; res[n] = {"differing_columns": sorted(cols), "shape_ok": not shape}
            ok or bad.append(n); continue
        allow = RLC_DELAY[n]; cols = set(); shape = False
        for x, y in zip(A, B):
            if x.startswith("%") or not x:
                shape |= x != y; continue
            x = x.split("\t"); y = y.split("\t")
            if len(x) != len(y): shape = True; continue
            cols |= {i for i, (u, v) in enumerate(zip(x, y)) if u != v}
        ok = not shape and cols <= allow; res[n] = {"differing_columns": sorted(cols), "allowed": sorted(allow), "shape_ok": not shape}
        ok or bad.append(n)
    # d
    P1 = [l.split("\t") for l in raw_lines(pa1, "DlE2RlcStats_percell.txt") if l and not l.startswith("%")]
    P0 = [l.split("\t") for l in raw_lines(pa, "DlE2RlcStats_percell.txt") if l and not l.startswith("%")]
    Z0 = {tuple(r[:5]): int(r[6]) for r in (l.split("\t") for l in raw_lines(pa, "DlE2RlcStats_r9rx.txt") if l and not l.startswith("%"))}
    dec = pos_wo_zero = inc = 0
    for x, y in zip(P1, P0):
        a, b = int(x[9]), int(y[9])
        if a < b: dec += 1
        elif a > b:
            inc += 1
            if Z0.get(tuple(y[:5]), 0) == 0: pos_wo_zero += 1
    res["Q-2d"] = {"rows": len(P1), "increased": inc, "decreased": dec, "increased_without_zero": pos_wo_zero}
    if dec or pos_wo_zero or len(P1) != len(P0): bad.append("Q-2d")
    return {"check": "Q-2", "pass": not bad, "failed": bad, "files": res}


def q2c(m1, m0):
    A = open(m1).read().split("\n"); B = open(m0).read().split("\n")
    if len(A) != len(B): return {"check": "Q-2c", "pass": False, "failed": [f"lines {len(A)} vs {len(B)}"]}
    cols = set(); shape = False
    for x, y in zip(A, B):
        if x.startswith("%") or not x: shape |= x != y; continue
        x = x.split("\t"); y = y.split("\t")
        if len(x) != len(y): shape = True; continue
        cols |= {i for i, (u, v) in enumerate(zip(x, y)) if u != v}
    ok = not shape and cols <= {10, 11, 12, 13}
    return {"check": "Q-2c", "pass": ok, "differing_columns": sorted(cols), "shape_ok": not shape}


if __name__ == "__main__":
    cmd = sys.argv[1]
    r = {"q0": lambda: q0(*sys.argv[2:5]), "q2": lambda: q2(*sys.argv[2:4]), "q2c": lambda: q2c(*sys.argv[2:4])}[cmd]()
    print(json.dumps(r, indent=1, ensure_ascii=False)); sys.exit(0 if r["pass"] else 1)
