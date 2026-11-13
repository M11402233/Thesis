#!/usr/bin/env python3
"""S_i 修正規格 §9 Q-1／Q-2（使用者決定 2026-11-13）：尺度對照與 E-i 舊尺度凍結。只讀。
(1) 同 seed 對照：R-5 run 之 exact vs reconstructed 尺度，C-1（UE 層級）與 C-2（cell 平均層級）分開
    → 檢查反推本身是否改變尺度。
(2) 跨 seed 對照：D-30 各 LOSO fold（留一 seed）之 reconstructed 尺度，C-1、C-2 分開，列逐 fold 值與範圍
    → 檢查單一 run 之驗收能否合理延伸。不以「一個 seed vs 八 seed 合併」之單一數字比較。
(3) 10 % 只是**人工複核旗標**，不是代表性判決：超過 ≠ 已證明 seed 4200 無代表性；未超過 ≠ 其餘 seed 之重建精度已驗證。
(4) Q-2：E-i 之舊尺度 s_old^(−k) = 其餘七 seed 之**原累計輸入**、原公式（C-1、C-2 各自）；逐 fold 寫出，附資料 md5 與程式版本。
內建一致性檢查（失敗即 exit 1）：fold 0 之 C-1 自算值 = TrustAnchor(...).scale；C-2 自算值 = run_E9_operating_regime.global_scale。
用法：check_Q1_scales.py <r5_run_dir> --json out.json [--freeze-ei out_ei_scales.json]
"""
import os, sys, json, argparse, hashlib, subprocess
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["ZT_DATASET"] = "d30"
import datasets, interval_source as IS
ap = argparse.ArgumentParser(); ap.add_argument("run"); ap.add_argument("--json"); ap.add_argument("--freeze-ei"); a = ap.parse_args()
LTE = 1
def mad(v):
    v = np.asarray(v, float); m = np.median(v); return 1.4826 * (float(np.median(np.abs(v - m))) + 1e-9)
def ue_vals(windows, drop_last=False):
    W = dict(windows); 
    if drop_last: W.pop(max(W))
    return [d for cells in W.values() for c, u in cells.items() if c != LTE for d in u.values()]
def cell_vals(windows, drop_last=False):
    W = dict(windows)
    if drop_last: W.pop(max(W))
    return [float(sum(u.values()) / len(u)) for cells in W.values() for c, u in cells.items() if c != LTE and u]
def with_mode(m, fn):
    old = os.environ.get("ZT_DELAY_SOURCE"); os.environ["ZT_DELAY_SOURCE"] = m
    try: return fn()
    finally:
        if old is None: os.environ.pop("ZT_DELAY_SOURCE", None)
        else: os.environ["ZT_DELAY_SOURCE"] = old
FLAG = 0.10; out = {"flag_threshold": FLAG, "flag_meaning": "人工複核旗標，非代表性判決"}
# (1) 同 seed
f5 = os.path.join(a.run, "DlE2RlcStats.txt")
EX = IS.parse_interval(f5, "exact"); RC = IS.parse_interval(f5, "reconstructed")
s = {"C1_exact": mad(ue_vals(EX, True)), "C1_rec": mad(ue_vals(RC, True)), "C2_exact": mad(cell_vals(EX, True)), "C2_rec": mad(cell_vals(RC, True))}
s["windows"] = [min(dict(EX)), max(dict(EX)) - 1]
for c in ("C1", "C2"):
    r = s[f"{c}_rec"] / s[f"{c}_exact"] - 1; s[f"{c}_rel_diff"] = r; s[f"{c}_flag"] = abs(r) > FLAG
out["same_seed_4200"] = s
# (2)(4) 跨 seed（逐 fold）
files = datasets.files(); assert len(files) == 8, files
def per_file(m):
    P = {f: IS.parse_interval(f, m) if m != "cumulative" else None for f in files}
    if m == "cumulative":
        import zt_kpm_xapp as X
        P = {f: list(X.TraceReplaySource(f).windows()) for f in files}
    return {f: (ue_vals(P[f]), cell_vals(P[f])) for f in files}
folds = {}
for m in ("reconstructed", "cumulative"):
    V = with_mode(m, lambda: per_file(m))
    for k, fk in enumerate(files):
        tr = [f for f in files if f != fk]
        folds.setdefault(m, []).append({"test_seed": os.path.basename(fk), "C1": mad([x for f in tr for x in V[f][0]]), "C2": mad([x for f in tr for x in V[f][1]])})
# 內建一致性檢查
import zt_kpm_xapp as X, run_E9_operating_regime as E9
chk = {}
for m in ("reconstructed", "cumulative"):
    tr = files[1:]
    ta = with_mode(m, lambda: X.TrustAnchor(tr).scale)
    gs = with_mode(m, lambda: E9.global_scale([E9.load_cell_delay(f) for f in tr]))
    chk[m] = {"C1_self": folds[m][0]["C1"], "C1_TrustAnchor": ta, "C2_self": folds[m][0]["C2"], "C2_global_scale": gs,
              "ok": abs(ta - folds[m][0]["C1"]) < 1e-12 and abs(gs - folds[m][0]["C2"]) < 1e-12}
out["consistency_checks"] = chk
rec = folds["reconstructed"]
out["cross_seed_reconstructed"] = {"folds": rec}
for c in ("C1", "C2"):
    v = [r[c] for r in rec]; ex = s[f"{c}_exact"]
    out["cross_seed_reconstructed"][c] = {"min": min(v), "max": max(v),
        "r5_exact_rel_to_fold_min": ex / min(v) - 1, "r5_exact_rel_to_fold_max": ex / max(v) - 1,
        "flag": (ex < min(v) * (1 - FLAG)) or (ex > max(v) * (1 + FLAG))}
if a.freeze_ei:
    git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__))).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "--", "."], capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__))).stdout.strip() != ""
    md5 = {os.path.basename(f): hashlib.md5(open(f, "rb").read()).hexdigest() for f in files}
    ei = {"definition": "s_old^(-k)：其餘七 seed 之原累計輸入（ZT_DELAY_SOURCE=cumulative）、原公式；C-1=TrustAnchor（UE 層級）、C-2=global_scale（cell 平均層級）",
          "folds": folds["cumulative"], "data_md5": md5, "code_git_head": git, "code_dirty": dirty}
    json.dump(ei, open(a.freeze_ei, "w"), ensure_ascii=False, indent=1); out["ei_frozen_to"] = a.freeze_ei
print(json.dumps(out, ensure_ascii=False, indent=1))
if a.json: json.dump(out, open(a.json, "w"), ensure_ascii=False, indent=1)
sys.exit(0 if all(c["ok"] for c in chk.values()) else 1)
