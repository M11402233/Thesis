#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
datasets.py — 資料集登錄（2026-10-06；第四章改用單一資料集 D-28 之準備）

所有實驗腳本經本模組取得資料路徑、N_known、aux 路徑與輸出目錄，不再各自寫死。

選擇資料集：環境變數 ZT_DATASET ∈ {dsh, dc, d28, d30}，預設 dsh（＝修訂前之行為，逐位不變）。
輸出目錄：dsh／dc → data/results（不變）；d28／d30 → data/results/d28、d30（與既有結果分開，避免覆寫）。
D-30：原始檔含第 300 窗，分析讀 analysis/（prepare_d30.py 產出，僅 0–299 窗）。
         環境變數 ZT_RESULTS_DIR 可整體覆寫（回歸測試用）。
內建檢查之期望值（742／2335／83／0、1803／575／766／6 等）僅屬於 D-SH：
         腳本以 is_reference() 判斷；非 D-SH 時略過「重現既有數字」類檢查並明示，其餘檢查照常。
"""
import os
import glob

ROOT = os.path.expanduser("~/oran-zt-kpm-verification/data")

REGISTRY = {
    "dsh": {"dir": os.path.join(ROOT, "si_lstm_seeds"), "pattern": "ues1_t300_seed*.txt", "n_known": 7, "ues": 1,
            "aux_dir": os.path.join(ROOT, "si_lstm_aux"), "aux_fmt": "ues1_t300_seed{seed}_aux",
            "results": os.path.join(ROOT, "results"), "max_window": None},
    "dc": {"dir": os.path.join(ROOT, "batchFinal_seeds"), "pattern": "seed42*.txt", "n_known": 7, "ues": 1,
           "aux_dir": None, "aux_fmt": None,
           "results": os.path.join(ROOT, "results"), "max_window": None},
    "d28": {"dir": os.path.join(ROOT, "ues28_seeds"), "pattern": "ues4_t300_seed*.txt", "n_known": 28, "ues": 4,
            "aux_dir": os.path.join(ROOT, "ues28_seeds"), "aux_fmt": "ues4_t300_seed{seed}_aux",
            "results": os.path.join(ROOT, "results", "d28"), "max_window": None},
    # D-30（2026-10-06 定案之主資料）：--totalUes=30 --e2nrEnabled=true --simTime=301，seed 4200–4207。
    # 原始主檔含第 300 窗；分析一律讀 prepare_d30.py 產出之 analysis/（僅 0–299 窗，內建檢查）。
    "d30": {"dir": os.path.join(ROOT, "ues30_seeds", "analysis"), "pattern": "ues30_t300_seed*.txt", "n_known": 30,
            "ues": None, "raw_dir": os.path.join(ROOT, "ues30_seeds"),
            "aux_dir": os.path.join(ROOT, "ues30_seeds"), "aux_fmt": "ues30_t300_seed{seed}_aux",
            "results": os.path.join(ROOT, "results", "d30"), "max_window": 300},
    # D-30P（第二階段主資料，phase2_percell_spec_v0.md §3；r9-g13 ＋ S2）：舊檔與 D-30 逐位相同（P-2 8/8），
    # 故主檔沿用 D-30 之 analysis/（0–299 窗）；新輸入一律自 r9 aux（_percell 等）讀取。aux_matches_main 再核對一次。
    "d30p": {"dir": os.path.join(ROOT, "ues30_seeds", "analysis"), "pattern": "ues30_t300_seed*.txt", "n_known": 30,
             "ues": None, "raw_dir": os.path.join(ROOT, "ues30_p_r9g13_seeds"),
             "aux_dir": os.path.join(ROOT, "ues30_p_r9g13_seeds"), "aux_fmt": "D30P_ues30_t300_seed{seed}_aux",
             "results": os.path.join(ROOT, "results", "d30p"), "max_window": 300, "percell": True},
    # D-30P1（D30P1_r10_recollection_spec.md；r10 模式 1 ＋ S2）：延遲欄依設計與 D-30／D-30P 不同，故主檔用自身截斷版
    # （prepare_d30.py，ZT_DATASET=d30p1），非延遲欄與 D-30 之一致性由 Q-2c 另行核對。
    "d30p1": {"dir": os.path.join(ROOT, "ues30_p_r10_seeds", "analysis"), "pattern": "D30P1_ues30_t300_seed*.txt",
              "n_known": 30, "ues": None, "raw_dir": os.path.join(ROOT, "ues30_p_r10_seeds"),
              "aux_dir": os.path.join(ROOT, "ues30_p_r10_seeds"), "aux_fmt": "D30P1_ues30_t300_seed{seed}_aux",
              "results": os.path.join(ROOT, "results", "d30p1"), "max_window": 300, "percell": True,
             "eff": True},   # r11：延遲 = 有效延遲樣本平均（D30P1_r10_recollection_spec.md §6.1）
}
PHASE2 = ("d30p", "d30p1")          # 第二階段（逐 cell 輸入）資料集

NAME = os.environ.get("ZT_DATASET", "dsh")
if NAME not in REGISTRY:
    raise SystemExit(f"ZT_DATASET={NAME} 不在 {sorted(REGISTRY)}")
CFG = REGISTRY[NAME]
N_KNOWN = CFG["n_known"]
DATA_DIR = CFG["dir"]
PATTERN = CFG["pattern"]


def is_reference():
    """是否為既有內建期望值所屬之資料集（D-SH）"""
    return NAME == "dsh"


def results_dir():
    d = os.environ.get("ZT_RESULTS_DIR") or CFG["results"]
    _m = os.environ.get("ZT_DELAY_SOURCE", "cumulative")   # 語意規格 v0.1：非預設來源寫入另一目錄，不覆寫舊結果
    if _m != "cumulative":
        d = d.rstrip("/") + "_delay_" + _m
    os.makedirs(d, exist_ok=True)
    return d


def files(data_dir=None, pattern=None):
    return sorted(glob.glob(os.path.join(data_dir or DATA_DIR, pattern or PATTERN)))


def seed_of(path):
    return os.path.basename(path).split("seed")[-1].split(".")[0].split("_")[0]


def aux_path(seed, fname):
    if not CFG["aux_dir"]:
        raise SystemExit(f"資料集 {NAME} 未登錄 aux 目錄")
    return os.path.join(CFG["aux_dir"], CFG["aux_fmt"].format(seed=seed), fname)


def window_of(line):
    """RLC 統計列之窗編號（第一欄為窗起點秒）；表頭或無法解析者回傳 None"""
    try:
        return int(float(line.split("\t", 1)[0]))
    except ValueError:
        return None


def aux_matches_main(seed):
    """aux 之 DlE2RlcStats 是否與分析用主檔一致。
    max_window 為 None：逐位元組相同（修訂前之檢查）；否則：aux 截斷至 < max_window 之列（含表頭）須與主檔逐位元組相同。"""
    a = aux_path(seed, "DlE2RlcStats.txt")
    b = os.path.join(DATA_DIR, PATTERN.replace("*", seed))
    if not (os.path.exists(a) and os.path.exists(b)):
        return False
    mw = CFG.get("max_window")
    with open(a, "rb") as fa, open(b, "rb") as fb:
        if mw is None:
            return fa.read() == fb.read()
        keep = [l for l in fa.read().decode().splitlines(True)
                if window_of(l) is None or window_of(l) < mw]
        return "".join(keep).encode() == fb.read()


def skip_note(what):
    """非 D-SH 時略過「重現既有數字」類檢查之統一訊息"""
    print(f"── {what}：資料集 {NAME} 無既有期望值，略過（程式未變更之保證來自 ZT_DATASET=dsh 之回歸重現）")
