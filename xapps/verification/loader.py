"""
loader.py — RLC trace 載入與 cell 級聚合
把 ns-O-RAN 的 DlE2RlcStats.txt 轉成每個時間窗、每個 cell 的觀測量 U_j / TP_j / DLY_j
這是 S_i / H_i / C_i 三殘差的共同前處理層。
"""
import pandas as pd
import numpy as np

# RLC trace 前 11 個欄位（第 12 欄之後 ns-O-RAN 有黏欄 bug，不讀）
RLC_COLS = ["start", "end", "CellId", "IMSI", "RNTI", "LCID",
            "nTxPDUs", "TxBytes", "nRxPDUs", "RxBytes", "delay"]

# LTE 錨點 cell（PDCP 聚在這，不是 mmWave gNB，空間驗證要排除）
LTE_CELL_ID = 1


def load_rlc(path):
    """讀 DlE2RlcStats.txt，只取前 11 欄，避開黏欄 bug。"""
    rows = []
    with open(path) as f:
        next(f)  # 跳過標頭
        for line in f:
            parts = line.split()
            if len(parts) < 11:
                continue
            try:
                rows.append([
                    float(parts[0]), float(parts[1]),   # start, end
                    int(parts[2]), int(parts[3]),       # CellId, IMSI
                    int(parts[4]), int(parts[5]),       # RNTI, LCID
                    int(parts[6]), int(parts[7]),       # nTxPDUs, TxBytes
                    int(parts[8]), int(parts[9]),       # nRxPDUs, RxBytes
                    float(parts[10]),                   # delay
                ])
            except ValueError:
                continue  # 壞行直接跳過
    df = pd.DataFrame(rows, columns=RLC_COLS)
    return df


def aggregate_cell_level(df, exclude_lte=True):
    """
    聚合成 per-(window, cell) 的觀測量：
      U_j   = 該 cell 該窗的相異 IMSI 數（Active UEs，C_i/H_i 用）
      TP_j  = 該 cell DL 吞吐量 = Σ RxBytes×8 / 窗長 (bit/s)
      DLY_j = 該 cell 平均 delay
      ue_set= 該 cell 該窗的 IMSI 集合（H_i 成員轉移要用）
    """
    if exclude_lte:
        df = df[df["CellId"] != LTE_CELL_ID].copy()

    df["win"] = df["start"].round(3).astype(str) + "-" + df["end"].round(3).astype(str)
    df["win_len"] = (df["end"] - df["start"]).clip(lower=1e-6)

    records = []
    for (win, cell), g in df.groupby(["win", "CellId"]):
        win_len = g["win_len"].iloc[0]
        ue_set = set(g["IMSI"].unique())
        records.append({
            "win": win,
            "start": g["start"].iloc[0],
            "cell": int(cell),
            "U": len(ue_set),                              # UE 基數
            "TP": g["RxBytes"].sum() * 8.0 / win_len,      # DL 吞吐量 bit/s
            "DLY": g["delay"].mean(),                       # 平均延遲
            "ue_set": ue_set,                               # IMSI 集合
        })
    out = pd.DataFrame(records).sort_values(["start", "cell"]).reset_index(drop=True)
    return out


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "DlE2RlcStats.txt"

    df = load_rlc(path)
    print(f"[*] 載入 {len(df)} 列有效 RLC 紀錄")
    print(f"[*] 出現的 CellId: {sorted(df['CellId'].unique())}")
    print(f"[*] 相異 IMSI 數: {df['IMSI'].nunique()}")

    agg = aggregate_cell_level(df)
    print(f"\n[*] 聚合後 {len(agg)} 筆 (window, cell) 觀測")
    print(f"[*] 時間窗數: {agg['win'].nunique()}")
    print(f"[*] mmWave cell 數（排除 LTE）: {agg['cell'].nunique()}")
    print("\n[*] 前 8 筆觀測量：")
    print(agg[["win", "cell", "U", "TP", "DLY"]].head(8).to_string(index=False))

    # H_i 生死線：同一 IMSI 是否出現在多個 cell
    ue_cells = df[df["CellId"] != LTE_CELL_ID].groupby("IMSI")["CellId"].nunique()
    cross = (ue_cells > 1).sum()
    print(f"\n[*] 跨 cell 出現的 UE 數（H_i 需 > 0）: {cross}")
