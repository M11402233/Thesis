#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
probe_prb_feasibility.py — PRB 路線可行性探測（跑完再決定要不要投入）

【它回答什麼】
路線 B（以「回報吞吐量 vs 回報資源用量」之內部一致性作為新驗證證據）成不成立，
取決於一個經驗問題：吞吐量與資源用量之間的關係夠不夠緊？
若離散度太大（缺 CQI/通道品質來解釋變異），該不變量之誤報率會高到不可用。

本腳本用你現有的 *_aux 資料回答，不需重跑 ns-3。

【資料來源】
  RxPacketTrace.txt   mmWave PHY 逐次傳輸：cellId、symbol#、tbSize、mcs、SINR、corrupt
  DlE2RlcStats.txt    RLC 層逐 UE 逐窗：CellId、IMSI、RxBytes（累積）

【三個檢查】
  A. 每符號承載位元組數之離散度（CV）——不變量的緊度
  B. 加入 MCS 後殘差是否顯著收斂——MCS 能否解釋變異
  C. RLC 回報量 vs PHY 實際交付量之相關性——兩層是否一致

【判準】
  A 的 CV < 0.30                 → 緊約束，路線 B 值得做
  0.30 ≤ CV < 0.60 且 B 明顯改善 → 需含 MCS 才可行，設計較複雜
  CV ≥ 0.60 或 B 無改善          → 不要做路線 B，改走路線 A

跑法：
  python3 probe_prb_feasibility.py \\
      --aux ~/oran-zt-kpm-verification/data/batchFinal_seeds_VERIFY/_logs_*/seed4200_aux
"""
import os
import glob
import argparse
import collections
import numpy as np

LTE_CELL = 1


def load_rx_trace(path):
    """RxPacketTrace.txt → per (cellId, 秒窗) 之 PHY 聚合"""
    agg = collections.defaultdict(lambda: {"sym": 0, "tb": 0, "mcs": [], "sinr": [],
                                           "n": 0, "corrupt": 0})
    with open(path) as fh:
        header = fh.readline().split()
        col = {name: i for i, name in enumerate(header)}
        need = ["DL/UL", "time", "symbol#", "cellId", "tbSize", "mcs", "SINR(dB)", "corrupt"]
        miss = [c for c in need if c not in col]
        if miss:
            raise SystemExit(f"RxPacketTrace 缺欄位 {miss}；實際欄位：{header}")
        for line in fh:
            p = line.split()
            if len(p) < len(header) or p[col["DL/UL"]] != "DL":
                continue
            try:
                t = float(p[col["time"]]); cid = int(p[col["cellId"]])
                sym = int(p[col["symbol#"]]); tb = int(p[col["tbSize"]])
                mcs = int(p[col["mcs"]]); sinr = float(p[col["SINR(dB)"]])
                bad = int(p[col["corrupt"]])
            except ValueError:
                continue
            k = agg[(cid, int(t))]
            k["n"] += 1; k["sym"] += sym; k["mcs"].append(mcs); k["sinr"].append(sinr)
            k["corrupt"] += bad
            if not bad:
                k["tb"] += tb
    return agg


def load_rlc(path):
    """DlE2RlcStats.txt → per (CellId, 窗) 之差分後 RxBytes"""
    cum = collections.defaultdict(dict)          # (cell,imsi) -> {win: RxBytes}
    with open(path) as fh:
        fh.readline()
        for line in fh:
            p = line.split("\t")
            if len(p) < 11:
                continue
            try:
                w = int(float(p[0])); c = int(p[2]); i = int(p[3]); rx = float(p[9])
            except ValueError:
                continue
            cum[(c, i)][w] = rx
    out = collections.defaultdict(float)
    for (c, i), wm in cum.items():
        ws = sorted(wm)
        for a, b in zip(ws, ws[1:]):
            d = wm[b] - wm[a]
            if d >= 0:
                out[(c, b)] += d
    return out


def cv(x):
    x = np.asarray([v for v in x if np.isfinite(v)])
    return float(np.std(x) / np.mean(x)) if len(x) and np.mean(x) > 0 else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--aux", required=True, help="某個 seed 的 *_aux 目錄（可含萬用字元）")
    args = ap.parse_args()
    cands = sorted(glob.glob(os.path.expanduser(args.aux)))
    if not cands:
        raise SystemExit("找不到 aux 目錄")
    aux = cands[0]
    print(f"aux = {aux}\n")

    phy = load_rx_trace(os.path.join(aux, "RxPacketTrace.txt"))
    rlc = load_rlc(os.path.join(aux, "DlE2RlcStats.txt"))

    cells = sorted({c for c, _ in phy} - {LTE_CELL})
    print(f"PHY 中的 mmWave cell：{cells}")
    print(f"PHY (cell,窗) 樣本 {len([1 for (c,_) in phy if c!=LTE_CELL])}；"
          f"RLC (cell,窗) 樣本 {len([1 for (c,_) in rlc if c!=LTE_CELL])}\n")

    rows = []
    for (c, w), v in phy.items():
        if c == LTE_CELL or v["sym"] == 0 or v["n"] < 5:
            continue
        rows.append({
            "cell": c, "win": w, "sym": v["sym"], "tb": v["tb"],
            "mcs": float(np.mean(v["mcs"])), "sinr": float(np.mean(v["sinr"])),
            "rlc": rlc.get((c, w), np.nan),
            "bps": v["tb"] / v["sym"],                    # 每符號位元組
        })
    if not rows:
        raise SystemExit("沒有有效樣本")

    bps = [r["bps"] for r in rows]
    print("── 檢查 A：每符號承載位元組數之離散度 ──")
    print(f"  全體  n={len(bps)}  mean={np.mean(bps):.2f}  CV={cv(bps):.3f}")
    for c in cells:
        s = [r["bps"] for r in rows if r["cell"] == c]
        if len(s) >= 10:
            print(f"  cell {c:<2} n={len(s):<5} mean={np.mean(s):7.2f}  CV={cv(s):.3f}")

    print("\n── 檢查 B：加入 MCS 後殘差是否收斂 ──")
    X = np.array([[r["mcs"], 1.0] for r in rows])
    y = np.array(bps)
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    pred = X @ coef
    resid_cv = float(np.std(y - pred) / np.mean(y))
    print(f"  bps ≈ {coef[0]:.3f}·MCS + {coef[1]:.3f}")
    print(f"  原始 CV {cv(bps):.3f}  →  以 MCS 解釋後之相對殘差 {resid_cv:.3f}"
          f"  （改善 {100*(1-resid_cv/cv(bps)):.0f}%）")
    X2 = np.array([[r["mcs"], r["sinr"], 1.0] for r in rows])
    c2, *_ = np.linalg.lstsq(X2, y, rcond=None)
    r2 = float(np.std(y - X2 @ c2) / np.mean(y))
    print(f"  再加 SINR 後之相對殘差 {r2:.3f}")

    print("\n── 檢查 C：RLC 回報量 vs PHY 實際交付量 ──")
    pair = [(r["rlc"], r["tb"]) for r in rows if np.isfinite(r["rlc"]) and r["tb"] > 0]
    if len(pair) >= 10:
        a = np.array(pair)
        print(f"  n={len(pair)}  相關係數={np.corrcoef(a[:,0], a[:,1])[0,1]:.3f}")
        ratio = a[:, 0] / a[:, 1]
        print(f"  RLC/PHY 比值  中位數={np.median(ratio):.3f}  CV={cv(ratio):.3f}")
    else:
        print("  可配對樣本不足——RLC 與 PHY 之窗對齊可能有問題")

    print("\n── 判讀 ──")
    v = cv(bps)
    if v < 0.30:
        print(f"  CV={v:.3f} < 0.30 → 緊約束，**路線 B 值得做**")
    elif v < 0.60 and resid_cv < 0.6 * v:
        print(f"  CV={v:.3f}，但以 MCS 解釋後降至 {resid_cv:.3f}")
        print("  → 需將 MCS 一併納入不變量方可行；設計較複雜，評估投入報酬後再決定")
    else:
        print(f"  CV={v:.3f}，MCS 解釋後 {resid_cv:.3f} → **不要做路線 B**，改走路線 A")
    print("\n  另注意：若檢查 C 之相關係數低於 0.8，代表 RLC 與 PHY 兩層對不上，")
    print("  即使 A、B 通過也要先釐清窗對齊與 counter scope。")


if __name__ == "__main__":
    main()
