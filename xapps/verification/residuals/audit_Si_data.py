"""
audit_Si_data.py — S_i 資料盤點：現有 seed 的 per-cell KPM 變異是否足以支撐偵測 + LSTM

回答三個問題：
  Q1. TxBytes/RxBytes 是累積量還是每窗增量？（決定要不要做 diff 前處理）
  Q2. 轉成每窗增量後，per-cell KPM 有多少變異？（變異太小 = LSTM 學不到東西）
  Q3. 跨 cell 的 KPM 是否有空間差異？（S_i 靠這個，沒有差異就做不了空間一致性）

跑法：
    cd ~/oran-zt-kpm-verification
    python3 xapps/verification/residuals/audit_Si_data.py
"""
import os, sys, glob
from collections import defaultdict
import statistics as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cardinality as C

BASE = os.path.expanduser("~/oran-zt-kpm-verification")
# 可用命令列指定資料夾：python3 audit_Si_data.py [資料夾路徑]
if len(sys.argv) > 1:
    DATA_DIR = os.path.expanduser(sys.argv[1])
else:
    DATA_DIR = os.path.join(BASE, "data/batchFinal_seeds")
    if not os.path.isdir(DATA_DIR):
        DATA_DIR = os.path.dirname(os.path.abspath(__file__))

# 同時接受 seed*.txt 與 ues*_t*_seed*.txt 兩種命名
seed_files = sorted(glob.glob(os.path.join(DATA_DIR, "seed*.txt")) +
                    glob.glob(os.path.join(DATA_DIR, "ues*_t*_seed*.txt")))
if not seed_files:
    sys.exit(f"找不到 seed：{DATA_DIR}/seed*.txt")


def cell_window_series(recs, field):
    """回傳 {cell: {window: 該窗該cell所有UE的 field 總和}}。"""
    agg = defaultdict(lambda: defaultdict(float))
    for r in recs:
        t = C._window_key(r)
        agg[r["CellId"]][t] += float(r[field])
    return agg


def main():
    recs = list(C.load_rlc(seed_files[0]))
    windows = sorted({C._window_key(r) for r in recs})

    print("=" * 70)
    print(f"S_i 資料盤點（{os.path.basename(seed_files[0])}，共 {len(seed_files)} seed）")
    print("=" * 70)

    # ---- Q1: 累積 vs 增量 ----
    print("\n[Q1] TxBytes 是累積量還是每窗增量？")
    tx = cell_window_series(recs, "TxBytes")
    c1 = tx.get(1, {})
    ts = sorted(c1.keys())[:6]
    print("  Cell 1 前幾窗 TxBytes 總和:", [f"{c1[t]:.0f}" for t in ts])
    is_cumulative = all(c1[ts[i]] <= c1[ts[i+1]] for i in range(len(ts)-1)) if len(ts) > 1 else False
    print(f"  → 判定：{'累積量（單調遞增）→ 需 diff 成每窗增量' if is_cumulative else '每窗增量'}")

    # ---- Q2: 增量後的 per-cell 變異 ----
    print("\n[Q2] 轉每窗增量後，各 cell 的吞吐量變異（變異係數 CV = std/mean）")
    print("     CV 太小(<0.1) = 幾乎平線，LSTM 學不到；CV 適中(0.2~1.0) = 有結構可學")
    print(f"  {'Cell':>5} | {'窗數':>4} | {'增量均值':>12} | {'增量std':>12} | {'CV':>6}")
    print("  " + "-" * 55)
    cv_summary = {}
    for cell in sorted(tx.keys()):
        series = tx[cell]
        ws = sorted(series.keys())
        # diff 成增量
        deltas = [series[ws[i+1]] - series[ws[i]] for i in range(len(ws)-1)]
        deltas = [d for d in deltas if d >= 0]  # 濾掉換手造成的負值
        if len(deltas) < 3:
            continue
        m = st.mean(deltas); s = st.pstdev(deltas)
        cv = s/m if m > 0 else 0
        cv_summary[cell] = cv
        flag = "✓有結構" if 0.15 <= cv <= 2.0 else ("⚠️太平" if cv < 0.15 else "⚠️過雜")
        print(f"  {cell:>5} | {len(deltas):>4} | {m:>12.0f} | {s:>12.0f} | {cv:>6.2f} {flag}")

    # ---- Q3: 跨 cell 空間差異 ----
    print("\n[Q3] 跨 cell 空間差異（S_i 靠此做空間一致性；各 cell 增量均值差多少）")
    means = {}
    for cell in sorted(tx.keys()):
        ws = sorted(tx[cell].keys())
        deltas = [tx[cell][ws[i+1]]-tx[cell][ws[i]] for i in range(len(ws)-1)]
        deltas = [d for d in deltas if d >= 0]
        if deltas:
            means[cell] = st.mean(deltas)
    if len(means) >= 2:
        vals = list(means.values())
        spatial_cv = st.pstdev(vals)/st.mean(vals) if st.mean(vals) > 0 else 0
        print(f"  各 cell 增量均值: " + ", ".join(f"c{c}={means[c]:.0f}" for c in sorted(means)))
        print(f"  跨 cell 空間變異 CV = {spatial_cv:.2f} "
              f"{'✓ cell 間有差異，S_i 可做' if spatial_cv > 0.2 else '⚠️ cell 間太均勻，S_i 訊號弱'}")

    # ---- 綜合判定 ----
    print("\n" + "=" * 70)
    print("綜合判定")
    print("=" * 70)
    n_ok = sum(1 for cv in cv_summary.values() if 0.15 <= cv <= 2.0)
    print(f"  有可學結構的 cell 數：{n_ok} / {len(cv_summary)}")
    print(f"  每 seed 時間點數：{len(windows)} 窗")
    print(f"  總樣本量（LSTM 序列）：{len(seed_files)} seed × {len(windows)} 窗 ≈ "
          f"{len(seed_files)*len(windows)} 時間點")
    print()
    print("  LSTM 可行性參考：")
    print("    - LSTM 通常需要每條序列 ≥ 100+ 時間點、且有時間結構")
    print(f"    - 你現有：每 seed 僅 {len(windows)} 窗，時間點偏少")
    print("    - 若增量 CV 適中且跨 cell 有差異 → 可做 S_i 空間一致性（不一定要 LSTM）")


if __name__ == "__main__":
    main()
