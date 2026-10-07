#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
datasets.py — 資料集登錄（2026-10-06；第四章改用單一資料集 D-28 之準備）

所有實驗腳本經本模組取得資料路徑、N_known、aux 路徑與輸出目錄，不再各自寫死。

選擇資料集：環境變數 ZT_DATASET ∈ {dsh, dc, d28, d30}，預設 dsh（＝修訂前之行為，逐位不變）。
輸出目錄：dsh／dc → data/results（不變）；d28 → data/results/d28（與既有結果分開，避免覆寫）。
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
            "results": os.path.join(ROOT, "results")},
    "dc": {"dir": os.path.join(ROOT, "batchFinal_seeds"), "pattern": "seed42*.txt", "n_known": 7, "ues": 1,
           "aux_dir": None, "aux_fmt": None,
           "results": os.path.join(ROOT, "results")},
    "d28": {"dir": os.path.join(ROOT, "ues28_seeds"), "pattern": "ues4_t300_seed*.txt", "n_known": 28, "ues": 4,
            "aux_dir": os.path.join(ROOT, "ues28_seeds"), "aux_fmt": "ues4_t300_seed{seed}_aux",
            "results": os.path.join(ROOT, "results", "d28")},
    # D-30（2026-10-06 定案之主資料）：--totalUes=30 --e2nrEnabled=true --simTime=301，seed 4200–4207；分析取 0–299 窗
    "d30": {"dir": os.path.join(ROOT, "ues30_seeds"), "pattern": "ues30_t300_seed*.txt", "n_known": 30, "ues": None,
            "aux_dir": os.path.join(ROOT, "ues30_seeds"), "aux_fmt": "ues30_t300_seed{seed}_aux",
            "results": os.path.join(ROOT, "results", "d30")},
}

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


def skip_note(what):
    """非 D-SH 時略過「重現既有數字」類檢查之統一訊息"""
    print(f"── {what}：資料集 {NAME} 無既有期望值，略過（程式未變更之保證來自 ZT_DATASET=dsh 之回歸重現）")
