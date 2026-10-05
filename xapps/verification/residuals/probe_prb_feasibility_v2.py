#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
probe_prb_feasibility_v2.py — 修正版探測

v1 的問題：
  1. 判準寫死在 CV<0.60，而實測 0.609 剛好被踢出，掩蓋了「加入 MCS 後殘差僅 0.115」這個關鍵結果
  2. RLC 差分沒有處理 cell change 與缺窗（違反 4.3.3 自己的規定），
     導致檢查 C 的 RLC/PHY 比值 1.878、相關係數 0.262 極可能是假象

v2 修正：
  - RLC 差分僅在「同一 (cell, imsi)、窗連續」時計算，其餘標為 missing
  - 先檢查 RxBytes 是否真為單調累積 counter（4.3.3 之前提）
  - 掃描窗位移 −2…+2，找出 PHY 與 RLC 的最佳對齊
  - 同時做「逐 cell」與「全場域聚合」兩種比對，區分「cell 歸屬錯誤」與「兩層真的不一致」
  - 判準改為以 MCS 殘差為主，不再用單一 CV 門檻

跑法：
  python3 probe_prb_feasibility_v2.py --aux "$HOME/oran-zt-kpm-verification/data/batchFinal_seeds_VERIFY/_logs_*/seed4200_aux"
"""
import os
import glob
import argparse
import collections
import numpy as np

LTE_CELL = 1


def load_rx_trace(path):
    agg = collections.defaultdict(lambda: {"sym": 0, "tb": 0, "mcs": [], "sinr": [],
                                           "n": 0, "corrupt": 0})
    with open(path) as fh:
        header = fh.readline().split()
        col = {n: i for i, n in enumerate(header)}
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
            k["n"] += 1; k["sym"] += sym; k["mcs"].append(mcs)
            k["sinr"].append(sinr); k["corrupt"] += bad
            if not bad:
                k["tb"] += tb
    return agg


def load_rlc_strict(path):
    """嚴格差分：僅在同一 (cell,imsi) 且窗連續時計算；並回報 counter 語意檢查結果"""
    series = collections.defaultdict(dict)       # (cell,imsi) -> {win: RxBytes}
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
            series[(c, i)][w] = rx

    mono = tot = 0
    for wm in series.values():
        ws = sorted(wm)
        for a, b in zip(ws, ws[1:]):
            tot += 1
            if wm[b] >= wm[a]:
                mono += 1
    mono_rate = mono / tot if tot else float("nan")

    diffs = collections.defaultdict(float)       # (cell,win) -> bytes
    kept = dropped = 0
    for (c, i), wm in series.items():
        ws = sorted(wm)
        for a, b in zip(ws, ws[1:]):
            if b - a != 1:                       # 缺窗 → 不可比
                dropped += 1; continue
            d = wm[b] - wm[a]
            if d < 0:                            # counter reset → 不可比
                dropped += 1; continue
            diffs[(c, b)] += d; kept += 1
    return diffs, mono_rate, kept, dropped, series


def cv(x):
    x = np.asarray([v for v in x if np.isfinite(v)])
    return float(np.std(x) / np.mean(x)) if len(x) and np.mean(x) > 0 else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--aux", required=True)
    args = ap.parse_args()
    aux = sorted(glob.glob(os.path.expanduser(args.aux)))[0]
    print(f"aux = {aux}\n")

    phy = load_rx_trace(os.path.join(aux, "RxPacketTrace.txt"))
    rlc, mono_rate, kept, dropped, series = load_rlc_strict(
        os.path.join(aux, "DlE2RlcStats.txt"))

    print("── 檢查 0：RxBytes 之 counter 語意（4.3.3 之前提）──")
    print(f"  相鄰窗單調不減之比例 = {mono_rate:.3f}"
          f"  （接近 1 → 確為累積 counter，差分正確）")
    print(f"  有效差分 {kept} 筆；因缺窗或 reset 丟棄 {dropped} 筆")
    if mono_rate < 0.9:
        print("  ⚠ 單調性偏低 → RxBytes 可能非累積量，4.3.3 之差分前處理須重新檢驗")
    print()

    rows = []
    for (c, w), v in phy.items():
        if c == LTE_CELL or v["sym"] == 0 or v["n"] < 5:
            continue
        rows.append({"cell": c, "win": w, "sym": v["sym"], "tb": v["tb"],
                     "mcs": float(np.mean(v["mcs"])), "sinr": float(np.mean(v["sinr"])),
                     "bps": v["tb"] / v["sym"]})
    bps = [r["bps"] for r in rows]

    print("── 檢查 A/B：資源—吞吐量約束之緊度 ──")
    print(f"  每符號位元組  n={len(bps)}  mean={np.mean(bps):.2f}  CV={cv(bps):.3f}")
    X = np.array([[r["mcs"], 1.0] for r in rows]); y = np.array(bps)
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid_cv = float(np.std(y - X @ coef) / np.mean(y))
    print(f"  bps ≈ {coef[0]:.3f}·MCS + {coef[1]:.3f}   →  相對殘差 {resid_cv:.3f}")
    print(f"  對照：S_i 所用之同窗跨 cell 延遲 CV ≈ 0.052\n")

    print("── 檢查 C：RLC 回報量 vs PHY 交付量（掃描窗位移）──")
    print(f"  {'位移':>4} {'逐cell n':>9} {'逐cell r':>9} {'比值中位':>9} "
          f"{'聚合 n':>7} {'聚合 r':>8} {'聚合比值':>9}")
    best = None
    for off in (-2, -1, 0, 1, 2):
        pc = [(rlc.get((r["cell"], r["win"] + off), np.nan), r["tb"])
              for r in rows if r["tb"] > 0]
        pc = [(a, b) for a, b in pc if np.isfinite(a) and a > 0]
        agg_r = collections.defaultdict(float); agg_p = collections.defaultdict(float)
        for r in rows:
            v = rlc.get((r["cell"], r["win"] + off), np.nan)
            if np.isfinite(v):
                agg_r[r["win"]] += v; agg_p[r["win"]] += r["tb"]
        ks = [k for k in agg_p if agg_p[k] > 0 and agg_r[k] > 0]
        if len(pc) >= 10:
            a = np.array(pc); rr = float(np.corrcoef(a[:, 0], a[:, 1])[0, 1])
            med = float(np.median(a[:, 0] / a[:, 1]))
        else:
            rr = med = float("nan")
        if len(ks) >= 10:
            ar = np.array([agg_r[k] for k in ks]); ap_ = np.array([agg_p[k] for k in ks])
            ar_r = float(np.corrcoef(ar, ap_)[0, 1]); ar_med = float(np.median(ar / ap_))
        else:
            ar_r = ar_med = float("nan")
        print(f"  {off:>4} {len(pc):>9} {rr:>9.3f} {med:>9.3f} "
              f"{len(ks):>7} {ar_r:>8.3f} {ar_med:>9.3f}")
        if best is None or (np.isfinite(rr) and rr > best[1]):
            best = (off, rr, med, ar_r)

    print("\n── 判讀 ──")
    off, rr, med, ar_r = best
    print(f"  最佳窗位移 {off}，逐 cell 相關 {rr:.3f}，聚合相關 {ar_r:.3f}")
    if not np.isfinite(rr):
        print("  樣本不足，無法判讀")
    elif rr >= 0.8:
        print("  兩層一致 → 檢查 A/B 之結果可信")
        print(f"  MCS 殘差 {resid_cv:.3f} → " +
              ("**路線 B 可行**（不變量須含 MCS）" if resid_cv < 0.25
               else "殘差偏大，路線 B 報酬有限"))
    elif ar_r >= 0.8 > rr:
        print("  聚合層一致但逐 cell 不一致 → **cell 歸屬有問題**")
        print("  （RLC 的 CellId 與 PHY 的 cellId 可能語意不同，或 UE 移動時歸屬錯位）")
        print("  須先釐清 cell 對應，再重新評估路線 B")
    else:
        print("  兩層皆不一致 → RLC 回報量與 PHY 交付量之間沒有穩定關係")
        print("  **路線 B 不可行**：建立在二者之上的一致性不變量會有高誤報")
        print("  改走路線 A（以 PHY trace 作為 RQ3 之真值，不作為驗證證據）")


if __name__ == "__main__":
    main()
