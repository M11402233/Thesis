#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_fig_lstm_rt.py — Fig 4-7（時間單位標示修訂版）：僅讀 lstm_baseline_results.json 作圖，不重新訓練。

LTE 錨點（cell 1）於 D-SH 四個 seed 皆為 299–300 個實際連續秒、無空窗，
故 lstm_baseline_anchor.py 之「每窗」即「每秒」；本圖僅將軸標改為 %/s，數值不變。
【內建檢查】錨點窗須為連續秒（相鄰差皆為 1）。
"""
import os
import glob
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import datasets as DS

ROOT = os.path.expanduser("~/oran-zt-kpm-verification/data")
R = os.path.join(ROOT, "results")


def anchor_seconds(path):
    ws = set()
    with open(path) as fh:
        fh.readline()
        for line in fh:
            p = line.split("\t")
            if len(p) >= 11 and p[2].strip() == "1":
                ws.add(int(float(p[0])))
    return sorted(ws)


def main():
    for f in sorted(glob.glob(os.path.join(DS.DATA_DIR, DS.PATTERN))):
        w = anchor_seconds(f)
        if any(b - a != 1 for a, b in zip(w, w[1:])):
            raise SystemExit(f"✗ 檢查：{os.path.basename(f)} 之錨點窗非連續秒")
    print("── 檢查：LTE 錨點窗皆為實際連續秒 ✓")
    d = json.load(open(os.path.join(R, "lstm_baseline_results.json"), encoding="utf-8"))
    sm = d["summary"]
    rates = d["drift_rates"]
    dets = [sm["mean_drift_detection_by_rate"][str(r)] for r in rates]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot([r * 100 for r in rates], dets, "o-", color="#c92a2a", label="LSTM detection rate (slow drift)")
    ax.axhline(sm["mean_step_detection_full"], ls="--", color="#495057",
               label=f"step attack full-window (det={sm['mean_step_detection_full']:.2f})")
    ax.axhline(sm["mean_step_detection_onset"]["1"], ls=":", color="#495057",
               label=f"step attack onset k=1 (hit={sm['mean_step_detection_onset']['1']:.2f})")
    ax.axhline(sm["mean_fpr"], ls="-.", color="#adb5bd", label=f"clean FPR ({sm['mean_fpr']:.2f})")
    ax.set_xlabel("drift rate (% of mean throughput per second)")
    ax.set_ylabel("detection rate")
    ax.set_title("Self-referencing LSTM baseline (LTE anchor throughput)")
    ax.set_ylim(-0.05, 1.05)
    ax.legend(); ax.grid(alpha=0.3)
    fig.tight_layout()
    out = os.path.join(R, "fig_lstm_drift_evasion_rt.png")
    fig.savefig(out, dpi=150)
    print("寫入", out)


if __name__ == "__main__":
    main()
