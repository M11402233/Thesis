#!/usr/bin/env python3
"""
run_Ci_depletion_A1.py — A1 修正:釐清虛減與可信 LTE 錨點的關係

背景(review 指出的威脅模型矛盾):
  若 LTE 錨點可信且上報所有 IMSI,單一 mmWave O-DU 刪紀錄不應使全域聯集減少。
  但原實驗說虛減 −1 被抓到 → 矛盾。

本腳本釐清真相(實測,非假設):
  『所有 UE 每窗都掛 LTE 錨點』為假 —— 實測僅約 45% 的 (窗,UE) 同時掛 LTE,
  約 55% 當下只掛 mmWave。故單一 O-DU 虛減的可偵測性是【條件性】的:
    - 受害 UE 當下只掛 mmWave  → 全域聯集少 1 → C_i 抓得到
    - 受害 UE 當下同時掛 LTE    → 錨點仍上報   → C_i 抓不到,須由 H_i 補

  這精確劃出 C_i 與 H_i 的分工線,是 limitation-as-contribution。

三種虛減情境對照:
  S1 單一O-DU虛減(符合威脅模型): 只刪 target IMSI 在某 mmWave cell 的紀錄
  S2 全域壓制(不符單節點威脅模型): 刪 target IMSI 在所有 cell(含LTE)的紀錄
  S3 後處理直接改全域集合(原實驗實際做的): 等價 S2,但語意上是 RIC 端竄改

輸出: data/results/Ci_depletion_A1_results.json + 終端條件式偵測率
跑法: python3 xapps/verification/residuals/run_Ci_depletion_A1.py
"""
import os, glob, json, collections
import numpy as np

DATA_DIR = os.path.expanduser("~/oran-zt-kpm-verification/data/si_lstm_seeds")
OUT_DIR  = os.path.expanduser("~/oran-zt-kpm-verification/data/results")
os.makedirs(OUT_DIR, exist_ok=True)
N_KNOWN = 7


def load_records(path):
    recs = []
    with open(path) as fh:
        fh.readline()
        for line in fh:
            p = line.split("\t")
            if len(p) < 4:
                continue
            try:
                w = int(float(p[0])); cell = int(p[2]); imsi = int(p[3])
            except ValueError:
                continue
            recs.append((w, cell, imsi))
    return recs


def field_cardinality(recs):
    by_w = collections.defaultdict(set)
    for w, cell, imsi in recs:
        by_w[w].add(imsi)
    return {w: len(s) for w, s in by_w.items()}


def analyze(path):
    recs = load_records(path)
    base = field_cardinality(recs)

    # 每個 (窗,UE) 掛在哪些 cell
    by_wi = collections.defaultdict(set)
    for w, c, i in recs:
        by_wi[(w, i)].add(c)

    # 統計 co-anchoring 比例
    total = len(by_wi)
    co_lte = sum(1 for cells in by_wi.values() if 1 in cells)
    only_mmw = sum(1 for cells in by_wi.values()
                   if 1 not in cells and any(c != 1 for c in cells))

    imsis = sorted(set(i for _, _, i in recs))
    # S1:對每個 UE、每個它所在的 mmWave cell,做單一O-DU虛減,量 C_i 觸發的窗比例
    s1_detect_windows = 0
    s1_total_windows = 0
    s1_by_coanchor = {"only_mmw": [0, 0], "co_lte": [0, 0]}  # [detected, total]
    for imsi in imsis:
        mmw_cells = sorted(set(c for w, c, i in recs if i == imsi and c != 1))
        for vc in mmw_cells:
            recs_s1 = [(w, c, i) for w, c, i in recs if not (i == imsi and c == vc)]
            card_s1 = field_cardinality(recs_s1)
            # 只看該 UE 實際掛在 vc 的窗
            windows_in_vc = sorted(set(w for w, c, i in recs if i == imsi and c == vc))
            for w in windows_in_vc:
                s1_total_windows += 1
                co = 1 in by_wi[(w, imsi)]
                bucket = "co_lte" if co else "only_mmw"
                s1_by_coanchor[bucket][1] += 1
                if card_s1.get(w, N_KNOWN) < base.get(w, N_KNOWN):
                    s1_detect_windows += 1
                    s1_by_coanchor[bucket][0] += 1

    # S2:全域壓制(刪所有 cell 含 LTE)
    s2_detect = 0; s2_total = 0
    for imsi in imsis:
        recs_s2 = [(w, c, i) for w, c, i in recs if i != imsi]
        card_s2 = field_cardinality(recs_s2)
        for w in base:
            s2_total += 1
            if card_s2.get(w, N_KNOWN) < base.get(w, N_KNOWN):
                s2_detect += 1

    return {
        "coanchor_ratio": co_lte / total,
        "only_mmw_ratio": only_mmw / total,
        "S1_single_ODU": {
            "detect_rate": s1_detect_windows / max(s1_total_windows, 1),
            "by_only_mmw": s1_by_coanchor["only_mmw"][0] / max(s1_by_coanchor["only_mmw"][1], 1),
            "by_co_lte":   s1_by_coanchor["co_lte"][0]  / max(s1_by_coanchor["co_lte"][1], 1),
        },
        "S2_global_suppression": {"detect_rate": s2_detect / max(s2_total, 1)},
    }


def main():
    files = sorted(glob.glob(os.path.join(DATA_DIR, "ues1_t300_seed*.txt"))) or \
            sorted(glob.glob("ues1_t300_seed*.txt"))
    if not files:
        print(f"找不到資料於 {DATA_DIR}"); return
    print(f"分析 {len(files)} 個 seed\n")

    agg = collections.defaultdict(list)
    for f in files:
        r = analyze(f)
        agg["coanchor"].append(r["coanchor_ratio"])
        agg["s1_all"].append(r["S1_single_ODU"]["detect_rate"])
        agg["s1_onlymmw"].append(r["S1_single_ODU"]["by_only_mmw"])
        agg["s1_colte"].append(r["S1_single_ODU"]["by_co_lte"])
        agg["s2"].append(r["S2_global_suppression"]["detect_rate"])

    summary = {
        "coanchor_ratio_mean": float(np.mean(agg["coanchor"])),
        "S1_single_ODU_detect_rate": float(np.mean(agg["s1_all"])),
        "S1_when_only_mmw": float(np.mean(agg["s1_onlymmw"])),
        "S1_when_co_lte": float(np.mean(agg["s1_colte"])),
        "S2_global_suppression_detect_rate": float(np.mean(agg["s2"])),
    }
    with open(os.path.join(OUT_DIR, "Ci_depletion_A1_results.json"), "w") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)

    print("=== A1 虛減偵測能力(條件性)===")
    print(f"  UE 同時掛 LTE 錨點的比例         : {summary['coanchor_ratio_mean']:.1%}")
    print(f"  S1 單一O-DU虛減 整體偵測率       : {summary['S1_single_ODU_detect_rate']:.1%}")
    print(f"     └ 受害UE當下【只掛mmWave】時   : {summary['S1_when_only_mmw']:.1%}  (C_i 抓得到)")
    print(f"     └ 受害UE當下【同時掛LTE】時    : {summary['S1_when_co_lte']:.1%}  (C_i 抓不到→須H_i)")
    print(f"  S2 全域壓制(不符單節點威脅模型)  : {summary['S2_global_suppression_detect_rate']:.1%}")
    print()
    print("論文結論:C_i 對單一O-DU虛減的偵測是【條件性】的——僅當受害UE當下未雙掛LTE時可偵測。")
    print("         此精確劃出 C_i(基數)與 H_i(成員追蹤)的分工,為 limitation-as-contribution。")


if __name__ == "__main__":
    main()
