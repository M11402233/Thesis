#!/usr/bin/env python3
"""check_d30h_r8.py — D-30H 重收（修正版 r8＋S2）之逐 seed 檢查。只讀，輸出 JSON。
規格：docs/thesis/D30H_handover_data_spec.md §3、§4、§7；report_semantics_spec_v0.md §5.11。
用法：check_d30h_r8.py <aux_dir> [--max-window 300] [--n-known 30] [--json out.json] [--skip-prb]
  aux_dir 為 collect_d30h_r8.sh 之 <tag>_aux/（亦可給 r7_validate 之 run 目錄作測試）。

硬性檢查（任一失敗 → exit 1，不得直接使用該 seed）：
  H1 主檔 0 … max_window−1 每窗皆在；IMSI 集合 = {1..n_known}
  H2 R-5 旁路檔一致：check_R5_R6.py（累計值與 _exact 之結構對帳，無 --ref）R5_pass
  H3 執行設定：meta.txt 含 ZT_R7_S2=1 且 ns3_dir 為 r8（r7_validate 測試目錄則讀其 meta 之同欄位）
  H4 換手事件完整：UE 端 start 數 = end 數；UeFailures 0 筆
只記錄（PRB）：prb_reader.py 交叉驗證於換手資料**已知不通過**（原 binary M1 與 r8 皆同；2026-11-14 查得：
  du-cell 之 Σ_UE RRU.PrbUsedDl.UEID 與 RxPacketTrace 符號換算差中位數 −16.3、範圍 −103～+94（V4，402 筆 (cell, 窗)；
  NoAuto R8d 為 ±0.09）），故於本資料只記錄差異分布並發警報，不作硬性判定；PRB 於 D-30H 之用法另訂。
另記錄、不判定（規格 §4、§6.1：換手瞬間 N_total 可能不恆為 30；乒乓為警報非驗收）：
  N_total 分布、換手數與每 UE 換手率、1 秒內 A→B→A 比例、峰值 RSS、R-7b 每 PDU PdcpTag 上限。
警報（印出，不 exit 1）：多數 UE 換手率 ≥ 1 次／秒（規格 §3：停下回報使用者，不自行改參數）。
"""
import os, sys, re, json, gzip, argparse, subprocess, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser(); ap.add_argument("aux"); ap.add_argument("--max-window", type=int, default=300)
ap.add_argument("--n-known", type=int, default=30); ap.add_argument("--json"); ap.add_argument("--skip-prb", action="store_true")
a = ap.parse_args(); D = a.aux.rstrip("/")


def op(name):
    p = os.path.join(D, name)
    if os.path.exists(p): return open(p)
    if os.path.exists(p + ".gz"): return gzip.open(p + ".gz", "rt")
    raise FileNotFoundError(p)


out = {"aux": D, "max_window": a.max_window, "hard": {}, "record": {}, "alerts": []}
H = out["hard"]; R = out["record"]

# H1
win = collections.defaultdict(set)
for ln in op("DlE2RlcStats.txt"):
    if ln[0] == "%": continue
    p = ln.split("\t")
    try: win[int(float(p[0]))].add(int(p[3]))
    except (ValueError, IndexError): pass
need = set(range(a.max_window)); missing = sorted(need - set(win))
allim = set().union(*(win[w] for w in need if w in win)) if win else set()
H["H1_windows_and_imsi"] = not missing and allim == set(range(1, a.n_known + 1))
R["missing_windows"] = missing[:20]; R["n_imsi"] = len(allim)
R["N_total_distribution"] = dict(sorted(collections.Counter(len(win[w]) for w in need if w in win).items()))

# H2
j = os.path.join("/tmp", f"r5r6_{os.getpid()}.json")
rc = subprocess.run([sys.executable, os.path.join(HERE, "check_R5_R6.py"), D, "--json", j], capture_output=True, text=True).returncode
r56 = json.load(open(j)) if os.path.exists(j) else {}
H["H2_side_channel_R5"] = rc == 0 and r56.get("R5_pass") is True
R["R5_counts"] = r56.get("counts"); R["R5_structural_failures"] = r56.get("R5_structural_failures")
os.path.exists(j) and os.remove(j)

# H3
meta = open(os.path.join(D, "meta.txt")).read() if os.path.exists(os.path.join(D, "meta.txt")) else ""
H["H3_r8_with_S2"] = "ZT_R7_S2=1" in meta and "ns-3-mmwave-oran-r8" in meta
R["meta_first_line"] = meta.splitlines()[0] if meta else None

# H4
def nums(name):
    rows = []
    for ln in op(name):
        p = ln.split()
        if p and re.match(r"^[0-9.]+$", p[0]): rows.append(p)
    return rows
us, ue = nums("UeHandoverStartStats.txt"), nums("UeHandoverEndStats.txt")
fails = sum(1 for ln in op("UeFailures.txt") if ln.strip() and ln[0].isdigit())
H["H4_handover_complete"] = len(us) == len(ue) and fails == 0
R["handover"] = {"ue_start": len(us), "ue_end": len(ue), "ue_failures": fails}
T = max(a.max_window, 1)
per = collections.Counter(int(p[1]) for p in ue if float(p[0]) < T)
rates = [per.get(i, 0) / T for i in range(1, a.n_known + 1)]
R["handover"].update(n_in_windows=sum(per.values()), ue_rate_ge_0_5=sum(r >= 0.5 for r in rates),
                     ue_rate_ge_1=sum(r >= 1 for r in rates), ue_no_handover=sum(r == 0 for r in rates),
                     rate_per_ue_per_s_mean=sum(rates) / len(rates))
seq = collections.defaultdict(list)                       # 1 秒內 A→B→A（同 diag_d30h_handover.py 之定義：以 UE 端 end 之 cell 序列）
for p in sorted(ue, key=lambda p: float(p[0])): seq[int(p[1])].append((float(p[0]), int(p[3])))
start_src = collections.defaultdict(list)
for p in sorted(us, key=lambda p: float(p[0])): start_src[int(p[1])].append((float(p[0]), int(p[3])))
pp = 0
for i, s in seq.items():
    src = start_src[i]
    for k in range(1, len(s)):
        if s[k][0] - s[k - 1][0] <= 1.0 and k - 1 < len(src) and s[k][1] == src[k - 1][1]: pp += 1
R["handover"]["ping_pong_1s"] = pp; R["handover"]["ping_pong_1s_share"] = pp / max(len(ue), 1)
if sum(r >= 1 for r in rates) > a.n_known / 2:
    out["alerts"].append("多數 UE 換手率 ≥ 1 次／秒：依規格 §3 停下回報使用者，不自行改參數")

# PRB（只記錄＋警報；見檔頭）
if a.skip_prb:
    R["prb"] = "skipped"
else:
    sys.path.insert(0, HERE); import prb_reader as P
    du, ph = P.load_du_prb(D, a.max_window), P.symbols_from_phy(D, a.max_window)
    dif = sorted(v["prb"] - ph[k] / (P.SLOTS_PER_S * 14) * P.PRB_CONST for k, v in du.items() if k in ph)
    q = lambda f: dif[min(len(dif) - 1, int(f * len(dif)))] if dif else None
    R["prb"] = {"n_cell_windows": len(dif), "sumUE_minus_phy_median": q(0.5), "q10": q(0.1), "q90": q(0.9),
                "min": dif[0] if dif else None, "max": dif[-1] if dif else None,
                "share_abs_gt_tol": sum(abs(x) > P.TOL for x in dif) / max(len(dif), 1), "tol": P.TOL}
    if R["prb"]["share_abs_gt_tol"] > 0:
        out["alerts"].append(f"PRB：Σ_UE 與 PHY 符號換算不符之 (cell, 窗) 比例 {R['prb']['share_abs_gt_tol']:.2f}（換手資料之已知現象，PRB 不可直接用）")

# 記錄：RSS、R-7b
for mf, col in (("mem_trace.tsv", 2), ("mem.tsv", 2)):
    pth = os.path.join(D, mf)
    if os.path.exists(pth):
        v = [int(l.split("\t")[col]) for l in open(pth).readlines()[1:] if len(l.split("\t")) > col and l.split("\t")[col].strip().isdigit()]
        R["peak_rss_mb"] = max(v, default=None); break
try:
    h = [l.split() for l in op("R7b_rlc_rx_tag_hist.txt") if l[0] != "%"]
    n = sum(int(x[3]) for x in h)
    R["R7b"] = {"pdus": n, "max_pdcp_tags": max(int(x[1]) for x in h), "mean_pdcp_tags": sum(int(x[1]) * int(x[3]) for x in h) / n}
except FileNotFoundError:
    R["R7b"] = None

out["pass"] = all(v is not False for v in H.values())
print(json.dumps(out, ensure_ascii=False, indent=1))
if a.json: json.dump(out, open(a.json, "w"), ensure_ascii=False, indent=1)
sys.exit(0 if out["pass"] else 1)
