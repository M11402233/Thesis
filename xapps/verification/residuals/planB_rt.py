#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
planB_rt.py — 方案 B（以實際秒數為時間單位）之共用核心

規格：docs/thesis/planB_realtime_spec.md（2026-10-06 事前登記）。
所有方案 B 腳本（*_rt.py）只透過本模組取得樣本、注入、三種參照之判定與時間指標，
以確保定義一致。

【樣本】與舊實作（run_slow_poisoning_suite.build_samples）相同之 seed × cell 樣本與
  full-consensus 窗集合 idx；注入時點 w_on = idx[len(idx)//2]（與舊 t0 為同一窗）。
【注入】作用於受測 cell **所有有上報之窗**；漂移以實際秒數 (w − w_on) 累積。
【參照】
  空間：|v(w) − c(w)| / s，c(w) 為同窗其他 mmWave cell 之中位數（peer 未遭竄改）
  時間：|v(w) − median{ v(u) : u ∈ [w−10, w−1] 且有上報 }| / s；有上報 < 5 → 不可評估
  監督式：輸入 w−9 … w 共 10 秒（值 + 遮罩）；有上報 < 5 → 不可評估
【時間指標】連續兩秒：w 與 w−1 皆在比較集合內、皆 ≥ w_on 且皆告警；缺窗即中斷。
"""
import numpy as np

from run_E9_operating_regime import load_cell_delay, global_scale, TAU_S
from run_slow_poisoning_suite import find_files, build_samples, agg_seed

HIST_WIN = 10      # 時間參照之回看秒數（不含當窗）
SEQ = 10           # 監督式分類器之輸入秒數（含當窗）
MIN_OBS = 5        # 可評估之最少有上報秒數
ONSET_S = 5        # onset 命中：注入後前 5 秒


class Sample:
    __slots__ = ("seed", "cell", "idx", "t0", "w_on", "mean", "own", "pm", "post",
                 "avail_t", "avail_s", "full10")

    def __init__(self, seed, cell, idx, ser, pm, own):
        self.seed, self.cell, self.idx = seed, cell, list(idx)
        self.t0 = len(idx) // 2
        self.w_on = idx[self.t0]
        self.mean = float(np.mean(ser))                    # 沿用舊定義
        self.own = own                                     # {w: 乾淨 delay}，受測 cell 所有上報窗
        self.pm = {w: float(p) for w, p in zip(idx, pm)}   # 評估窗之 peer 中位數
        self.post = [w for w in idx if w >= self.w_on]     # 原始評估集合
        # 可評估條件只取決於有無上報（與攻擊無關）
        self.avail_t = {w: sum((w - k) in own for k in range(1, HIST_WIN + 1)) >= MIN_OBS for w in idx}
        self.avail_s = {w: sum((w - k) in own for k in range(0, SEQ)) >= MIN_OBS for w in idx}
        self.full10 = {w: all((w - k) in own for k in range(0, SEQ)) for w in idx}


def load_data(data_dir=None):
    files = find_files(data_dir)
    seeds = [f.split("seed")[-1].replace(".txt", "")[-4:] for f in files]
    return seeds, {s: load_cell_delay(f) for s, f in zip(seeds, files)}


def samples_of(seed, Wd):
    out = []
    for tc, idx, ser, pm in build_samples(Wd):
        own = {w: Wd[w][tc] for w in Wd if tc in Wd[w]}
        out.append(Sample(seed, tc, idx, ser, pm, own))
    return out


def fold_scale(data, seeds, ts):
    return global_scale([data[x] for x in seeds if x != ts])


# ---------------- 注入（回傳新之 {w: 上報值}） ----------------
def inject_drift(own, w_on, rate, mean):
    return {w: (v + rate * (w - w_on) * mean if w >= w_on else v) for w, v in own.items()}


def inject_step(own, w_on, af):
    return {w: (v * af if w >= w_on else v) for w, v in own.items()}


# ---------------- 參照 ----------------
def z_spatial(sm, v, s):
    return {w: abs(v[w] - sm.pm[w]) / s for w in sm.idx}


def z_temporal(sm, v, s):
    out = {}
    for w in sm.idx:
        if not sm.avail_t[w]:
            out[w] = None
            continue
        hist = [v[w - k] for k in range(1, HIST_WIN + 1) if (w - k) in v]
        out[w] = abs(v[w] - float(np.median(hist))) / s
    return out


def seq_features(sm, v, med, s, windows):
    """監督式分類器輸入：(n, SEQ, 2)；僅回傳可評估窗"""
    ws = [w for w in windows if sm.avail_s[w]]
    X = np.zeros((len(ws), SEQ, 2), np.float32)
    for i, w in enumerate(ws):
        for j in range(SEQ):
            u = w - (SEQ - 1) + j
            if u in v:
                X[i, j, 0] = (v[u] - med) / s
                X[i, j, 1] = 1.0
    return ws, X


def flags_from_z(z, tau=TAU_S):
    return {w: (None if val is None else bool(val > tau)) for w, val in z.items()}


# ---------------- 比較集合與時間指標 ----------------
def common_set(sm):
    return [w for w in sm.post if sm.avail_t[w] and sm.avail_s[w]]


def own_set(sm, method):
    if method == "spatial":
        return list(sm.post)
    if method == "temporal":
        return [w for w in sm.post if sm.avail_t[w]]
    return [w for w in sm.post if sm.avail_s[w]]


def rate(flags, S):
    S = [w for w in S if flags.get(w) is not None]
    return float(np.mean([flags[w] for w in S])) if S else None


def first_detection(flags, S, w_on, criterion):
    """回傳首次偵測之窗號（實際秒）；criterion = any 或 2c（實際連續兩秒）"""
    Sset = set(S)
    for w in sorted(S):
        if w < w_on or not flags.get(w):
            continue
        if criterion == "any":
            return w
        if (w - 1) >= w_on and (w - 1) in Sset and flags.get(w - 1):
            return w
    return None


def onset_hit(flags, S, w_on):
    return float(any(flags.get(w) for w in S if w_on <= w < w_on + ONSET_S))


# ---------------- 回歸基準（人工核對後才建立） ----------------
import json as _json
import os as _os
BASELINE_PATH = _os.path.expanduser("~/oran-zt-kpm-verification/data/results/planB_rt_baselines.json")


def check_baseline(name, values, set_baseline=False, note=""):
    """values：{key: float}。基準存在則須逐位相同；不存在時只有 set_baseline=True 才寫入。"""
    base = _json.load(open(BASELINE_PATH, encoding="utf-8")) if _os.path.exists(BASELINE_PATH) else {}
    if name in base and not set_baseline:
        bad = [(k, base[name]["values"].get(k), v) for k, v in values.items() if base[name]["values"].get(k) != v]
        if bad:
            raise SystemExit(f"✗ 回歸基準 {name} 不一致（先查原因，不直接替換）：{bad[:5]}")
        return "ok"
    if not set_baseline:
        print(f"  ⚠ 尚無回歸基準 {name}：本次輸出為「未核對」，須人工核對後以 --set-baseline 建立")
        return "missing (unverified)"
    base[name] = {"values": values, "note": note}
    with open(BASELINE_PATH, "w", encoding="utf-8") as fh:
        _json.dump(base, fh, indent=2, ensure_ascii=False)
    return "set"
