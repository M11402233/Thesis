#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
probe_prb_feasibility_v4.py — 多 seed 確認與尾部誤報率：在「成員穩定窗」上量不變量的緊度與覆蓋率

【v2 留下的問題】
聚合層相關 0.909、逐 cell 僅 0.716。最可能的原因是窗內換手：
UE 在一秒之中途由 cell A 換到 cell B，RLC 差分被歸到結束時所在的 cell，
但位元組實際上由兩個 cell 分別交付。此種情形無法以重新對應修正。

【出路】
只在「成員穩定」之窗上套用該不變量，成員有變動之窗判為證據不可得（abstain）——
與 S_i 於 peer < 2 時之處置為同一哲學。

【本腳本回答兩個問題】
  Q1 在成員穩定窗上，RLC 回報量與「資源 × MCS」之關係有多緊？（穩健殘差離散度）
  Q2 成員穩定窗佔多少？（覆蓋率——決定該證據的可用率）

【判準】
  穩健殘差 < 0.20 且覆蓋率 > 40%  → 路線 B 可行
  穩健殘差 < 0.20 但覆蓋率低      → 可行但可用率差，價值有限
  穩健殘差 ≥ 0.30                 → 不可行，改走路線 A

跑法：
  python3 probe_prb_feasibility_v3.py --aux "$HOME/oran-zt-kpm-verification/data/batchFinal_seeds_VERIFY/_logs_*/seed4200_aux"
  # 想跑多個 seed：--aux "...../_logs_*/seed42??_aux" --all
"""
import os
import glob
import argparse
import collections
import numpy as np

LTE_CELL = 1


def load_phy(path):
    agg = collections.defaultdict(lambda: {"sym": 0, "tb": 0, "mcs_w": 0.0, "n": 0})
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
                mcs = int(p[col["mcs"]]); bad = int(p[col["corrupt"]])
            except ValueError:
                continue
            k = agg[(cid, int(t))]
            k["n"] += 1; k["sym"] += sym; k["mcs_w"] += mcs * sym
            if not bad:
                k["tb"] += tb
    out = {}
    for key, v in agg.items():
        if v["sym"] > 0:
            out[key] = {"sym": v["sym"], "tb": v["tb"],
                        "mcs": v["mcs_w"] / v["sym"], "n": v["n"]}
    return out


def load_rlc(path):
    """回傳 per-(cell,win) 差分位元組、以及 per-(cell,win) 之 IMSI 集合"""
    series = collections.defaultdict(dict)
    member = collections.defaultdict(set)
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
            member[(c, w)].add(i)

    diffs = collections.defaultdict(float)
    contrib = collections.defaultdict(set)      # (cell,win) -> 有有效差分之 imsi
    for (c, i), wm in series.items():
        ws = sorted(wm)
        for a, b in zip(ws, ws[1:]):
            if b - a != 1:
                continue
            d = wm[b] - wm[a]
            if d < 0:
                continue
            diffs[(c, b)] += d
            contrib[(c, b)].add(i)
    return diffs, member, contrib


def robust_disp(resid, center):
    """穩健相對離散度：1.4826·MAD(resid) / median(center)"""
    r = np.asarray(resid); c = np.asarray(center)
    mad = float(np.median(np.abs(r - np.median(r))))
    med = float(np.median(c))
    return 1.4826 * mad / med if med > 0 else float("nan")


def analyse(aux, verbose=True):
    phy = load_phy(os.path.join(aux, "RxPacketTrace.txt"))
    rlc, member, contrib = load_rlc(os.path.join(aux, "DlE2RlcStats.txt"))

    rows = []
    for (c, w), v in phy.items():
        if c == LTE_CELL or v["n"] < 5:
            continue
        b = rlc.get((c, w))
        if b is None or b <= 0:
            continue
        prev, cur = member.get((c, w - 1), set()), member.get((c, w), set())
        stable = (prev == cur) and len(cur) > 0 and contrib.get((c, w), set()) == cur
        rows.append({"cell": c, "win": w, "sym": v["sym"], "mcs": v["mcs"],
                     "tb": v["tb"], "rlc": b, "stable": stable})
    return rows


def fit_report(rows, tag):
    if len(rows) < 15:
        print(f"  {tag}: 樣本不足 (n={len(rows)})")
        return None
    # 預測式：bytes ≈ sym × (a·MCS + b)  →  線性於 (sym·MCS, sym)
    X = np.array([[r["sym"] * r["mcs"], r["sym"]] for r in rows], dtype=float)
    y = np.array([r["rlc"] for r in rows], dtype=float)
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    pred = X @ coef
    disp = robust_disp(y - pred, y)
    r = float(np.corrcoef(y, pred)[0, 1])
    print(f"  {tag}: n={len(rows):<4} 相關={r:.3f}  穩健相對殘差={disp:.3f}"
          f"   (bytes ≈ sym×({coef[0]:.2f}·MCS + {coef[1]:.2f}))")
    rel = (y - pred) / np.where(pred > 0, pred, np.nan)
    rel = rel[np.isfinite(rel)]
    sig = 1.4826 * float(np.median(np.abs(rel - np.median(rel))))
    z = np.abs(rel - np.median(rel)) / sig if sig > 0 else np.zeros_like(rel)
    tail = {k: float((z > k).mean()) for k in (3, 4, 5)}
    return disp, r, len(rows), tail, coef


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--aux", required=True)
    ap.add_argument("--all", action="store_true", help="彙整所有符合的 seed")
    args = ap.parse_args()
    auxes = sorted(glob.glob(os.path.expanduser(args.aux)))
    if not auxes:
        raise SystemExit("找不到 aux 目錄")
    if not args.all:
        auxes = auxes[:1]

    allrows = []
    for a in auxes:
        rows = analyse(a)
        print(f"{os.path.basename(a)}: 可配對 (cell,窗) = {len(rows)}，"
              f"其中成員穩定 = {sum(r['stable'] for r in rows)}")
        allrows += rows

    st = [r for r in allrows if r["stable"]]
    cover = len(st) / len(allrows) if allrows else 0

    if len(auxes) > 1:
        print("\n── 逐 seed 穩健殘差（成員穩定窗）──")
        per = []
        for a in auxes:
            rr = [r for r in analyse(a) if r["stable"]]
            if len(rr) >= 15:
                X = np.array([[q["sym"] * q["mcs"], q["sym"]] for q in rr], float)
                y = np.array([q["rlc"] for q in rr], float)
                c, *_ = np.linalg.lstsq(X, y, rcond=None)
                d = robust_disp(y - X @ c, y); per.append(d)
                print(f"  {os.path.basename(a)}: n={len(rr):<4} 殘差={d:.3f}")
        if per:
            print(f"  範圍 {min(per):.3f}–{max(per):.3f}，中位數 {np.median(per):.3f}")

    print(f"\n── Q1 不變量緊度 ──")
    fit_report(allrows, "全部窗  ")
    res = fit_report(st, "成員穩定")

    print(f"\n── Q2 覆蓋率 ──")
    print(f"  成員穩定窗 / 可配對窗 = {len(st)}/{len(allrows)} = {cover:.1%}")
    print(f"  對照：S_i 之 full-consensus 覆蓋率 = 54.8%")

    if res is not None:
        print(f"\n── Q3 乾淨資料之尾部誤報率（成員穩定窗）──")
        for k, v in res[3].items():
            print(f"  |z| > {k}σ : {v:.1%}")
        print("  （此即該殘差作為驗證證據時之乾淨誤報率；對照 S_i 注入區間 0.037）")

    print(f"\n── 判讀 ──")
    if res is None:
        print("  樣本不足")
        return
    disp = res[0]
    fpr4 = res[3][4]
    if fpr4 > 0.10:
        print(f"  ⚠ 4σ 誤報率 {fpr4:.1%} 偏高：尾部厚，殘差之中位數雖緊但門檻處誤報多")
    if disp < 0.20 and cover > 0.40:
        print(f"  穩健殘差 {disp:.3f} < 0.20 且覆蓋率 {cover:.1%} > 40%")
        print("  → **路線 B 可行**：可建立「回報吞吐量 vs 回報資源×MCS」之一致性不變量，")
        print("     成員不穩定之窗判為證據不可得（abstain）")
    elif disp < 0.20:
        print(f"  殘差夠緊（{disp:.3f}）但覆蓋率僅 {cover:.1%}")
        print("  → 技術上可行，惟可用率低；先評估是否值得投入")
    elif disp < 0.30:
        print(f"  殘差 {disp:.3f} 介於邊界 → 誤報率會偏高，建議只作為條件性佐證，不獨立判定")
    else:
        print(f"  殘差 {disp:.3f} ≥ 0.30 → **路線 B 不可行**，改走路線 A")
        print("     （以 PHY trace 作為 RQ3 之真值，不作為驗證證據）")


if __name__ == "__main__":
    main()
