#!/usr/bin/env python3
"""4.7.1 之同窗跨 mmWave cell 延遲 CV，依 ZT_DELAY_SOURCE 選擇延遲語意（定義同 audit_delay_cv.py）。只讀。
CV(t) = std(cell 延遲) / mean(cell 延遲)，cell 延遲 = 該 cell 當窗各 UE delay 之平均；僅計活躍 mmWave cell ≥ 2 之窗。
內建檢查：ZT_DELAY_SOURCE=cumulative 於 D-30 8 seed 須重現 audit_delay_cv.json 之中位數 0.05833094978296878，否則停止。
cell 歸屬仍為最後一筆 PDU 所在 cell（規格 F1）；每 cell 拆分屬第二階段。
用法：ZT_DATASET=d30 ZT_DELAY_SOURCE=reconstructed cv_interval.py [files...] [--json out]
"""
import os, sys, json, argparse
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import datasets as DS, zt_kpm_xapp as X, interval_source as IS
ap = argparse.ArgumentParser(); ap.add_argument("files", nargs="*"); ap.add_argument("--json"); a = ap.parse_args()
files = a.files or DS.files(); m = IS.mode()
cvs = []
for f in files:
    for w, cells in (IS.si_cells(f) if IS.is_percell() else X.TraceReplaySource(f).windows()):
        mm = [c for c in cells if c != X.LTE_CELL]
        if len(mm) >= 2:
            d = np.array([IS.node_value(list(cells[c].values()), np.mean) for c in mm])
            if d.mean() > 0: cvs.append(float(d.std() / d.mean()))
q = lambda x: dict(median=float(np.median(x)), q25=float(np.percentile(x, 25)), q75=float(np.percentile(x, 75)), n=len(x))
out = {"delay_source": m, "files": [os.path.basename(f) for f in files], "delay_cv": q(cvs)}
if m == "cumulative" and not a.files and DS.NAME == "d30":
    ok = abs(out["delay_cv"]["median"] - 0.05833094978296878) < 1e-12
    out["check_reproduces_audit_delay_cv"] = ok
    if not ok:
        print(json.dumps(out, indent=1)); raise SystemExit("內建檢查失敗：累計模式未重現 0.0583")
print(json.dumps(out, ensure_ascii=False, indent=1))
p = a.json or os.path.join(DS.results_dir(), "cv_interval.json")
json.dump(out, open(p, "w"), ensure_ascii=False, indent=1); print("寫入", p)
