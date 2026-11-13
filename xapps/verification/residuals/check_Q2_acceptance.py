#!/usr/bin/env python3
"""語意規格 v0.1 §8.1 Q2：反推（reconstructed）相對於精確（exact）之預定工程準則。只讀。
輸入：同一 run 之 DlE2RlcStats.txt 與 DlE2RlcStats_exact.txt（R-5 加裝輸出）。
  (A) 尺度 s′：以凍結之校準程序（zt_kpm_xapp.TrustAnchor，1.4826·MAD，含 +1e-9）於**精確值**上計算。
      精確值目前只有 R-5 之 run（單一 seed），無法做 LOSO；此處 s′ 用該 run 自身，並另報同 run 之反推值尺度
      及（若給 --loso-files）7 個 D-30 seed 反推值之 LOSO 尺度供對照。此偏離 §8.1 之處須由使用者決定（見輸出 note）。
  (B) 逐 (UE, 窗) 誤差：|rec − exact|；全體與窗 ≥ --late（預設 270）兩組。準則：p99 ≤ 0.05·s′ 且 max ≤ 0.25·s′。
  (C) S_i 判定：同 cell 歸屬、同 τ_S、同 MIN_PEER，以 s′ 對 exact 與 rec 各跑 verify_si；逐 (節點, 窗) 判定相同比例 ≥ 99.9 %。
  (D) 門檻附近：Δz_bound(j,w) = (|Δtgt| 之上限 + |Δref| 之上限) / s′，上限取該窗各 UE 誤差之最大值
      （tgt 為 UE 平均、ref 為 peer cell 平均之中位數，兩者之變動皆 ≤ 該窗 UE 誤差最大值）；
      列出 |z_exact − τ_S| < Δz_bound 之 (節點, 窗) 與其判定是否翻轉。
用法：check_Q2_acceptance.py <run_dir> [--late 270] [--loso-files f1 ...] --json out.json
"""
import os, sys, json, argparse
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("ZT_DATASET", "d30")
import zt_kpm_xapp as X
import interval_source as IS

ap = argparse.ArgumentParser(); ap.add_argument("run"); ap.add_argument("--late", type=int, default=270)
ap.add_argument("--loso-files", nargs="*", default=[]); ap.add_argument("--json"); a = ap.parse_args()
f = os.path.join(a.run, "DlE2RlcStats.txt")
EX = dict(IS.parse_interval(f, "exact")); RC = dict(IS.parse_interval(f, "reconstructed"))
# 最後一窗可能不完整（E2 NR 副作用，CLAUDE.md），不計
last = max(EX); EX.pop(last, None); RC.pop(last, None)

def scale_of(file_list, m):
    old = os.environ.get("ZT_DELAY_SOURCE"); os.environ["ZT_DELAY_SOURCE"] = m
    try:
        return X.TrustAnchor(file_list).scale
    finally:
        if old is None: os.environ.pop("ZT_DELAY_SOURCE")
        else: os.environ["ZT_DELAY_SOURCE"] = old
# TrustAnchor 讀整個檔（含最後一窗）；為與 (B)(C) 一致，另以同公式於去掉最後一窗之值上重算並比對
def mad_scale(windows):
    v = [d for cells in windows.values() for c, u in cells.items() if c != X.LTE_CELL for d in u.values()]
    med = np.median(v); return 1.4826 * (float(np.median(np.abs(np.array(v) - med))) + 1e-9)
s_ex = mad_scale(EX); s_rc = mad_scale(RC)
s_ex_anchor = scale_of([f], "exact")
out = {"run": a.run, "windows": [min(EX), max(EX)], "scale_exact_s_prime_ms": s_ex, "scale_reconstructed_ms": s_rc,
       "scale_exact_via_TrustAnchor_incl_last_window_ms": s_ex_anchor,
       "note": "s′ 取自單一 R-5 run 之精確值（精確值僅此一 run，無法 LOSO）；是否接受此偏離待使用者決定"}
if a.loso_files:
    out["scale_reconstructed_d30_pooled_ms"] = scale_of(a.loso_files, "reconstructed")
# (B)
err, err_late = [], []
for w in EX:
    for c in EX[w]:
        for i, d in EX[w][c].items():
            e = abs(RC[w][c][i] - d); err.append(e)
            if w >= a.late: err_late.append(e)
def summ(x):
    x = np.array(x); return dict(n=int(len(x)), median=float(np.median(x)), p99=float(np.percentile(x, 99)), max=float(x.max())) if len(x) else None
B, BL = summ(err), summ(err_late)
crit = lambda s: (s is not None) and s["p99"] <= 0.05 * s_ex and s["max"] <= 0.25 * s_ex
out["B_abs_err_ms"] = B; out["B_abs_err_ms_late"] = BL
out["B_pass_all"] = crit(B); out["B_pass_late"] = crit(BL) if BL else None
if BL is None: out["B_late_note"] = f"run 未達窗 {a.late}（短跑），後期驗證不適用"
# (C)(D)
same = tot = 0; near = []; flips = 0
for w in EX:
    werr = max(abs(RC[w][c][i] - EX[w][c][i]) for c in EX[w] for i in EX[w][c])
    for j in EX[w]:
        if j == X.LTE_CELL: continue
        ve, ze, _ = X.verify_si(EX[w], j, s_ex); vr, zr, _ = X.verify_si(RC[w], j, s_ex)
        if ve in ("n/a", "unavailable") and vr == ve: same += 1; tot += 1; continue
        tot += 1; same += (ve == vr)
        bound = 2 * werr / s_ex
        if ze is not None and abs(ze - X.TAU_S) < bound:
            near.append(dict(w=w, node=j, z_exact=ze, z_rec=zr, bound=round(bound, 4), flip=(ve != vr)))
        flips += (ve != vr)
out["C_verdict_identical_share"] = same / tot if tot else None; out["C_node_windows"] = tot; out["C_flips"] = flips
out["C_pass"] = (same / tot >= 0.999) if tot else None
out["D_near_threshold"] = near; out["D_near_threshold_n"] = len(near); out["D_near_flips"] = sum(n["flip"] for n in near)
out["Q2_pass"] = bool(out["B_pass_all"] and (out["B_pass_late"] in (True, None)) and out["C_pass"])
print(json.dumps({k: v for k, v in out.items() if k != "D_near_threshold"}, ensure_ascii=False, indent=1))
if a.json: json.dump(out, open(a.json, "w"), ensure_ascii=False, indent=1)
