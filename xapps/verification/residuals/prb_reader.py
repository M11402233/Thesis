#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prb_reader.py — 讀取 ns-O-RAN 原生 E2SM-KPM 之 PRB（du-cell-<c>.txt，--e2nrEnabled=true 產出）

定義（ns-3 mmwave-enb-net-device.cc，第 1193–1216 行）：
  RRU.PrbUsedDl.UEID = 該 UE 於報告窗之排程 OFDM 符號數 ÷（報告窗之 slot 數 × 14）× 139
  RRU.PrbUsedDl（cell 欄位）= 各 UE 值以 uint32 逐次累加（每次截斷小數）→ 系統性偏低，**不採用**
本模組以 Σ_UE RRU.PrbUsedDl.UEID 為 cell 之 PRB 用量；139 為原始碼寫死之常數（PRB_CONST）。

報表對應：du-cell 之 timestamp 欄為實際時間（ms），報表依出現順序對應模擬第 k 秒（[k, k+1)）。
交叉驗證：同窗 RxPacketTrace 之 DL 排程符號數 ÷ (SLOTS_PER_S × 14) × 139 須與 Σ_UE 相符（容許 TOL）。

用法：python3 prb_reader.py <aux 目錄> [--max-window 300]     # 印出交叉驗證結果
"""
import os
import csv
import gzip
import argparse
import collections

PRB_CONST = 139          # 原始碼寫死之 dlAvailablePrbs（= ceil(100 MHz ÷ 720 kHz)，即 configuration 2 之載波）
N_RB_CFG1 = 28           # configuration 1 之實際 RB 數：numerology 2（RB 寬 12 × 60 kHz = 720 kHz），
                         # MmWavePhyMacCommon::SetBandwidth 以 ceil(20 MHz ÷ 720 kHz) = 28 計（未扣保護頻帶）


def utilization(prb):
    """PRB 時間占用率（0–1）：與 139 常數無關，等於排程符號占用比例"""
    return prb / PRB_CONST


def prb_cfg1(prb):
    """換算為 configuration 1 之實際 RB 數尺度（× 28／139）"""
    return prb * N_RB_CFG1 / PRB_CONST
SLOTS_PER_S = 4000       # numerology 2：slot = 0.25 ms
SYMS_PER_SLOT = 14
TOL = 0.5                # PRB；校準實測最大差 0.089
MM_CELLS = range(2, 9)


def _open(path):
    if os.path.exists(path):
        return open(path, encoding="utf-8")
    if os.path.exists(path + ".gz"):
        return gzip.open(path + ".gz", "rt", encoding="utf-8")
    raise FileNotFoundError(path + "(.gz)")


def load_du_prb(aux_dir, max_window=None, cells=MM_CELLS):
    """回傳 {(cell, w): {"prb": Σ_UE, "prb_cell_field": 原始 cell 欄位, "per_ue": {imsi: prb}}}"""
    out = {}
    for c in cells:
        with _open(os.path.join(aux_dir, f"du-cell-{c}.txt")) as fh:
            rows = list(csv.DictReader(fh))
        order = []
        for r in rows:
            if r["timestamp"] not in order:
                order.append(r["timestamp"])
        idx = {t: k for k, t in enumerate(order)}
        for r in rows:
            k = idx[r["timestamp"]]
            if max_window is not None and k >= max_window:
                continue
            if int(r["nrCellId"]) != c:
                raise ValueError(f"du-cell-{c}.txt 含 nrCellId={r['nrCellId']}")
            e = out.setdefault((c, k), {"prb": 0.0, "prb_cell_field": float(r["RRU.PrbUsedDl"]), "per_ue": {}})
            v = float(r["RRU.PrbUsedDl.UEID"])
            e["per_ue"][int(r["ueImsiComplete"])] = v
            e["prb"] += v
    return out


def symbols_from_phy(aux_dir, max_window=None):
    """RxPacketTrace 之 DL 排程符號數 {(cell, w): symbols}"""
    sym = collections.defaultdict(float)
    with _open(os.path.join(aux_dir, "RxPacketTrace.txt")) as fh:
        fh.readline()
        for line in fh:
            p = line.split("\t")
            if p[0] != "DL":
                continue
            w = int(float(p[1]))
            if max_window is not None and w >= max_window:
                continue
            sym[(int(p[7]), w)] += int(p[6])
    return sym


def cross_check(aux_dir, max_window=None):
    """回傳 (n, 最大差, cell 欄位低於 Σ_UE 之範圍, 不符清單)"""
    prb = load_du_prb(aux_dir, max_window)
    sym = symbols_from_phy(aux_dir, max_window)
    diffs, gaps, bad = [], [], []
    for (c, w), e in sorted(prb.items()):
        ref = sym.get((c, w), 0.0) / (SLOTS_PER_S * SYMS_PER_SLOT) * PRB_CONST
        d = abs(e["prb"] - ref)
        diffs.append(d); gaps.append(e["prb"] - e["prb_cell_field"])
        if d > TOL:
            bad.append((c, w, round(e["prb"], 3), round(ref, 3)))
    return len(diffs), max(diffs, default=0.0), (min(gaps, default=0.0), max(gaps, default=0.0)), bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("aux_dir")
    ap.add_argument("--max-window", type=int, default=None)
    args = ap.parse_args()
    n, mx, (g0, g1), bad = cross_check(args.aux_dir, args.max_window)
    print(f"比對 {n} 筆 (cell, 窗)：Σ_UE PRB 與符號換算最大差 {mx:.3f}（容許 {TOL}）；"
          f"cell 欄位低於 Σ_UE {g0:.2f}–{g1:.2f}")
    if bad or n == 0:
        raise SystemExit(f"✗ 交叉驗證未通過：{bad[:5]}")
    print("✓ 交叉驗證通過")


if __name__ == "__main__":
    main()
