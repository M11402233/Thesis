"""
validate_existing_300s.py — 驗證 oran-data/sim_300s_baseline 能否直接拿來用
（不用再跑一次 8 小時收集）

跑法（在你的 VM 上）：
    cd ~/oran-zt-kpm-verification
    python3 xapps/verification/residuals/validate_existing_300s.py

檢查項目：
  1. 讀取是否成功、記錄數多少
  2. 窗數與窗寬（確認是 0.1s 還是 1s 粒度，決定要不要重採樣對齊 baseline）
  3. C_i 基數守恆是否仍成立（額外證據：更長時間下守恆是否維持）
  4. Per-cell KPM 增量變異（決定 S_i/LSTM 能不能直接用這份，不用等新收集）
"""
import os
import sys
from collections import defaultdict
import statistics as st

sys.path.insert(0, os.path.expanduser(
    "~/oran-zt-kpm-verification/xapps/verification/residuals"))
import cardinality as C

TARGET = os.path.expanduser("~/oran-data/sim_300s_baseline/DlE2RlcStatsLte.txt")
# 也一併檢查 mmWave 版本（非 Lte）如果存在
TARGET_MMW = os.path.expanduser("~/oran-data/sim_300s_baseline/DlE2RlcStats.txt")

N_KNOWN = 7  # 依你目前定案；若這份資料的 ues.txt 顯示不同數字，以下會提醒你調整


def analyze(path, label):
    if not os.path.exists(path):
        print(f"[{label}] 檔案不存在: {path}")
        return
    print(f"\n{'='*60}\n[{label}] {path}\n{'='*60}")
    recs = list(C.load_rlc(path))
    print(f"總記錄數: {len(recs)}")
    if not recs:
        print("空檔案，略過")
        return

    windows = sorted({C._window_key(r) for r in recs})
    print(f"窗數: {len(windows)}")
    print(f"窗範圍: {windows[0]} -> {windows[-1]}")
    if len(windows) >= 2:
        gaps = [round(windows[i+1] - windows[i], 6) for i in range(min(5, len(windows)-1))]
        print(f"窗間隔樣本（前5個）: {gaps}")

    # ---- C_i 基數守恆檢查 ----
    cfg = C.CardinalityConfig(n_known=N_KNOWN, eps_low=0.05, eps_high=0.0, kappa=0.10)
    series = C.field_cardinality_series(recs, cfg.include_lte, cfg.lte_cell_id)
    vals = list(series.values())
    uniq = sorted(set(vals))
    print(f"\nC_i 基數守恆檢查（N_known={N_KNOWN}）:")
    print(f"  N_total 值域: {uniq}")
    print(f"  是否全部守恆 (=={N_KNOWN}): "
          f"{'是 ✓' if uniq == [N_KNOWN] else '否，需檢查'}")
    if uniq != [N_KNOWN]:
        n_viol = sum(1 for v in vals if v != N_KNOWN)
        print(f"  違反窗數: {n_viol} / {len(vals)}"
              f"（若 N_known 應為其他值，請檢查對應的 ues.txt）")

    # ---- Per-cell KPM 增量變異（S_i / LSTM 可行性）----
    print(f"\nPer-cell TxBytes 增量變異（判斷能否支撐 S_i/LSTM）:")
    agg = defaultdict(lambda: defaultdict(float))
    for r in recs:
        t = C._window_key(r)
        agg[r["CellId"]][t] += float(r["TxBytes"])
    for cell in sorted(agg.keys()):
        ws = sorted(agg[cell].keys())
        deltas = [agg[cell][ws[i+1]] - agg[cell][ws[i]] for i in range(len(ws)-1)]
        deltas = [d for d in deltas if d >= 0]
        if len(deltas) < 3:
            continue
        m, s = st.mean(deltas), st.pstdev(deltas)
        cv = s / m if m > 0 else 0
        flag = "有結構" if 0.15 <= cv <= 2.0 else ("太平" if cv < 0.15 else "過雜")
        print(f"  cell {cell}: 增量點數={len(deltas)}, CV={cv:.2f} [{flag}]")

    print(f"\n序列長度評估: {len(windows)} 個時間點"
          f"（{'足夠' if len(windows) >= 100 else '仍偏少'} 給 LSTM 用）")


analyze(TARGET, "DlE2RlcStatsLte (LTE)")
analyze(TARGET_MMW, "DlE2RlcStats (mmWave, 若存在)")

print(f"\n{'='*60}")
print("結論指引")
print(f"{'='*60}")
print("若上面兩份都顯示：")
print("  - N_total 守恆值域符合預期")
print("  - 窗數 >= 100")
print("  - 多數 cell 的 TxBytes CV 落在有結構區間")
print("→ 這份 7/3 已存在的 300s 資料可直接拿來做 S_i 初步分析與 LSTM 序列，")
print("  不需要再跑一次收集腳本。")
print()
print("若窗數只有 60（代表其實是用 1 秒窗但跑了 60 個 —— 也就是 60s 模擬，")
print("不是真的 300s），或 N_known 對不上，請把輸出貼回來，我們再判斷。")
