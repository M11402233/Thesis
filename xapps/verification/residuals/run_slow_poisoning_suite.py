#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_slow_poisoning_suite.py — 慢性中毒題組 Q1／Q2／Q4／Q6（第四章 4.7.x 延伸；RQ2）

【要回答的問題】
  Q1 偵測前沿：在「漂移速率 × 注入後觀察窗數 D」上，兩種參照各自需要多快的漂移才偵測得到？
     r*_D = 最低之速率使 P(於注入後 D 窗內偵測) ≥ 0.5。
  Q2 偵測前已灌入多少偏差：首次偵測時之瞬時偏移（% of mean）與累積偏移（mean·窗），
     未偵測者以序列結尾設限（censored），另報未偵測比例。
  Q4 貼著門檻之適應型攻擊者：白箱知道 s 與 τ_S，每窗偽造值停在門檻下 β·τ_S·s，
     可長期維持之最大偏差為何？空間參照（有界）vs 時間參照（可無界累積）。
  Q6 校準期中毒：凍結尺度 s 由 training seeds 估計；若攻擊者於校準資料期間即已竄改
     k 個 cell，s 被灌大多少、測試期偵測率掉多少？

【設計：完全沿用 4.7.4／E9】
  資料／尺度／門檻／評估範圍／注入起點 t0 = len//2 均與 run_E9_operating_regime.py 相同
  （直接 import 其函式），統計單位為 seed。

【偵測準則】
  any   注入後第一個 z > τ_S 之窗
  2c    注入後第一次「連續 2 窗 z > τ_S」之第二窗（與 L_C = 2 之持續概念對應）
  兩者均另以乾淨序列計算同一準則之「底線」（clean floor：未注入時於同一區間觸發之機率），
  r* 只在偵測率超過底線時才有意義，腳本一併輸出。

【內建一致性檢查】
  1. 乾淨 FPR 與漂移族偵測率須與 E9_operating_regime.json 逐位相同（同一實作）。
  2. Q4 之 oracle 攻擊於門檻下（β < 1）偵測率依構造須為 0；若不為 0 代表實作有誤。
  任一失敗即停止、不寫檔。

【誠實聲明（寫進論文）】
  - 所有攻擊僅作用於 delay 維度；為本研究觀測維度上之合成注入，非既有工作之重現。
  - Q4 之 oracle 假設攻擊者於上報前即知同窗 peer 中位數，為上界（實際 O-DU 無法於上報前
    取得他節點同窗值）；另報 lag-1（僅知上一窗 peer 中位數）與 own（不知 peer）兩種較實際之版本。
  - full-consensus 窗序列為壓縮序列（跳過 peer < 2 之窗），「每窗」指每個受評估窗。

【輸出】
  <out>/slow_poisoning_suite.json
  <out>/fig_slow_Q1_frontier.png、fig_slow_Q2_bias.png、fig_slow_Q4_hugging.png

跑法：
  python3 run_slow_poisoning_suite.py
  python3 run_slow_poisoning_suite.py --data-dir ... --out-dir ...
"""
import os
import sys
import glob
import json
import argparse
import collections
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_E9_operating_regime as E9
from run_E9_operating_regime import (load_cell_delay, global_scale, inject_drift,
                                     TAU_S, MIN_NEIGHBOR, W_HIST, MIN_LEN)

DATA_DIR = E9.DATA_DIR
OUT_DIR = E9.OUT_DIR

REFS = ("spatial", "temporal")
# Q1／Q2：較 4.7.4 更細之速率格點（含 4.7.4 之 8 點）
Q1_RATES = [0.001, 0.002, 0.003, 0.005, 0.0075, 0.01, 0.015, 0.02,
            0.03, 0.04, 0.06, 0.08, 0.15]
Q1_HORIZONS = [5, 10, 20, 40]
CRITERIA = ("any", "2c")
# Q4
Q4_BETAS = [0.5, 0.75, 0.9, 0.99]
Q4_VARIANTS = ("oracle", "lag1", "own")
# Q6
Q6_K = [1, 2, 3]
Q6_POISON = [("drift", 0.005), ("drift", 0.01), ("drift", 0.02),
             ("bias", 0.5), ("bias", 1.0), ("bias", 2.0)]
Q6_EVAL_RATES = [0.005, 0.01, 0.02, 0.04]


# ==========================================================================
# 共用：樣本建構（與 E9 相同之篩選）
# ==========================================================================
def find_files(data_dir):
    search = [data_dir] if data_dir else [DATA_DIR, os.path.join("seeds", "si_lstm_seeds"), "."]
    for d in search:
        files = sorted(glob.glob(os.path.join(d, "ues1_t300_seed*.txt")))
        if len(files) >= 2:
            return files
    return []


def build_samples(Wd):
    """回傳 [(tc, idx, ser, peer_med)]，與 E9 之 seed×cell 樣本一一對應"""
    wins = sorted(Wd)
    cells = set()
    for w in Wd:
        cells |= set(Wd[w])
    out = []
    for tc in cells:                       # 與 E9 相同之迭代順序（set 順序）
        idx = [w for w in wins if tc in Wd[w]
               and len([c for c in Wd[w] if c != tc]) >= MIN_NEIGHBOR]
        if len(idx) < MIN_LEN:
            continue
        ser = np.array([Wd[w][tc] for w in idx], dtype=float)
        peer_med = np.array([np.median([Wd[w][c] for c in Wd[w] if c != tc]) for w in idx])
        out.append((tc, idx, ser, peer_med))
    return out


def z_spatial(v, peer_med, s):
    return np.abs(v - peer_med) / s


def z_temporal(v, s):
    out = np.zeros(len(v))
    for i in range(1, len(v)):
        lo = max(0, i - W_HIST)
        out[i] = abs(v[i] - np.median(v[lo:i])) / s
    return out


def zfun(ref, v, peer_med, s):
    return z_spatial(v, peer_med, s) if ref == "spatial" else z_temporal(v, s)


def first_detection(flags, t0, criterion):
    """回傳首次偵測之索引（相對於序列起點），未偵測回傳 None"""
    n = len(flags)
    if criterion == "any":
        for t in range(t0, n):
            if flags[t]:
                return t
    else:  # 2c：連續兩窗，且兩窗皆在注入區間內
        for t in range(t0 + 1, n):
            if flags[t] and flags[t - 1]:
                return t
    return None


def agg_seed(pairs):
    """pairs = [(seed, value)] → 樣本等權平均 + seed 範圍（各 seed 內樣本平均之 min/max）+ per-seed"""
    by = collections.defaultdict(list)
    for sd, v in pairs:
        by[sd].append(v)
    sm = {sd: float(np.mean(v)) for sd, v in by.items()}
    vals = [v for _, v in pairs]
    return {"mean": float(np.mean(vals)) if vals else None,
            "seed_min": float(min(sm.values())) if sm else None,
            "seed_max": float(max(sm.values())) if sm else None,
            "per_seed": sm, "n": len(vals)}


# ==========================================================================
# Q1 + Q2
# ==========================================================================
def run_q1_q2(data, seeds):
    q1 = {r: {c: {D: collections.defaultdict(list) for D in Q1_HORIZONS} for c in CRITERIA}
          for r in REFS}
    floor = {r: {c: {D: [] for D in Q1_HORIZONS} for c in CRITERIA} for r in REFS}
    # Q2：每個樣本 × 速率之首次偵測
    q2 = {r: {c: collections.defaultdict(list) for c in CRITERIA} for r in REFS}
    # 一致性：重算 E9 之 fpr 與漂移偵測率
    chk_fpr = {r: [] for r in REFS}
    chk_drift = {r: collections.defaultdict(list) for r in REFS}

    for ts in seeds:
        s = global_scale([data[x] for x in seeds if x != ts])
        for tc, idx, ser, pm in build_samples(data[ts]):
            mean = ser.mean(); t0 = len(ser) // 2; n_atk = len(ser) - t0
            for r in REFS:
                zc = zfun(r, ser, pm, s)
                fc = zc > TAU_S
                chk_fpr[r].append((ts, float(fc[t0:].mean())))
                for c in CRITERIA:
                    k = first_detection(fc, t0, c)
                    for D in Q1_HORIZONS:
                        floor[r][c][D].append((ts, float(k is not None and k - t0 < D)))
                for rate in Q1_RATES:
                    z = zfun(r, inject_drift(ser, t0, rate, mean), pm, s)
                    f = z > TAU_S
                    if rate in E9.DRIFT_RATES:
                        chk_drift[r][rate].append((ts, float(f[t0:].mean())))
                    for c in CRITERIA:
                        k = first_detection(f, t0, c)
                        for D in Q1_HORIZONS:
                            q1[r][c][D][rate].append((ts, float(k is not None and k - t0 < D)))
                        if k is None:
                            n = n_atk - 1          # 設限：序列結尾之偏移
                            q2[r][c][rate].append({"seed": ts, "detected": False,
                                                   "windows": n_atk,
                                                   "offset_pct": rate * n * 100,
                                                   "cum_mean_windows": rate * n * (n + 1) / 2,
                                                   "offset_ms": rate * n * mean})
                        else:
                            n = k - t0
                            q2[r][c][rate].append({"seed": ts, "detected": True,
                                                   "windows": n,
                                                   "offset_pct": rate * n * 100,
                                                   "cum_mean_windows": rate * n * (n + 1) / 2,
                                                   "offset_ms": rate * n * mean})

    res_q1 = {}
    for r in REFS:
        res_q1[r] = {}
        for c in CRITERIA:
            res_q1[r][c] = {}
            for D in Q1_HORIZONS:
                det = {str(rate): agg_seed(q1[r][c][D][rate]) for rate in Q1_RATES}
                fl = agg_seed(floor[r][c][D])
                rstar = None
                for rate in Q1_RATES:
                    m = det[str(rate)]["mean"]
                    if m >= 0.5 and m > fl["mean"]:
                        rstar = rate
                        break
                # per-seed r*
                rstar_seed = {}
                for sd in fl["per_seed"]:
                    rs = None
                    for rate in Q1_RATES:
                        m = det[str(rate)]["per_seed"].get(sd)
                        if m is not None and m >= 0.5 and m > fl["per_seed"][sd]:
                            rs = rate
                            break
                    rstar_seed[sd] = rs
                res_q1[r][c][str(D)] = {"detect": det, "clean_floor": fl,
                                        "r_star": rstar, "r_star_per_seed": rstar_seed}

    res_q2 = {}
    for r in REFS:
        res_q2[r] = {}
        for c in CRITERIA:
            res_q2[r][c] = {}
            for rate in Q1_RATES:
                rows = q2[r][c][rate]
                det = [x for x in rows if x["detected"]]
                res_q2[r][c][str(rate)] = {
                    "n": len(rows),
                    "undetected_frac": agg_seed([(x["seed"], float(not x["detected"])) for x in rows]),
                    "detected_median_windows": float(np.median([x["windows"] for x in det])) if det else None,
                    "detected_median_offset_pct": float(np.median([x["offset_pct"] for x in det])) if det else None,
                    "detected_median_cum_mean_windows": float(np.median([x["cum_mean_windows"] for x in det])) if det else None,
                    "detected_median_offset_ms": float(np.median([x["offset_ms"] for x in det])) if det else None,
                    # 全樣本（未偵測者以序列結尾設限）之中位數：為偵測前偏差之下界
                    "all_median_offset_pct_censored": float(np.median([x["offset_pct"] for x in rows])),
                    "all_median_cum_mean_windows_censored": float(np.median([x["cum_mean_windows"] for x in rows])),
                }
    chk = {"fpr": {r: float(np.mean([v for _, v in chk_fpr[r]])) for r in REFS},
           "drift": {r: {str(k): float(np.mean([v for _, v in vv])) for k, vv in chk_drift[r].items()}
                     for r in REFS}}
    return res_q1, res_q2, chk


# ==========================================================================
# Q4：貼著門檻之適應型攻擊者
# ==========================================================================
def hug_spatial(ser, pm, t0, beta, s, variant):
    """回傳偽造序列；僅注入區間被改寫，方向為上偏（灌大 delay）"""
    v = ser.copy()
    for t in range(t0, len(v)):
        if variant == "oracle":
            v[t] = pm[t] + beta * TAU_S * s
        elif variant == "lag1":
            v[t] = pm[t - 1] + beta * TAU_S * s
        else:  # own：不知 peer，只在自身真值上加固定偏移
            v[t] = ser[t] + beta * TAU_S * s
    return v


def hug_temporal(ser, t0, beta, s, variant):
    """時間參照之貼門檻攻擊：參照為自身前 W 窗（攻擊者自己控制之歷史）中位數"""
    v = ser.copy()
    for t in range(t0, len(v)):
        lo = max(0, t - W_HIST)
        if variant == "own":
            v[t] = ser[t] + beta * TAU_S * s
        else:
            # oracle 與 lag1 對時間參照等價：參照完全由攻擊者自身之歷史上報決定
            v[t] = np.median(v[lo:t]) + beta * TAU_S * s
    return v


def run_q4(data, seeds):
    out = {r: {vr: {str(b): {"det": [], "bias_pct": [], "bias_ms": [], "end_bias_pct": []}
                    for b in Q4_BETAS} for vr in Q4_VARIANTS} for r in REFS}
    scale_info = []
    for ts in seeds:
        s = global_scale([data[x] for x in seeds if x != ts])
        for tc, idx, ser, pm in build_samples(data[ts]):
            mean = ser.mean(); t0 = len(ser) // 2
            scale_info.append((ts, s, float(np.median(ser))))
            for b in Q4_BETAS:
                for vr in Q4_VARIANTS:
                    for r in REFS:
                        if r == "spatial":
                            v = hug_spatial(ser, pm, t0, b, s, vr)
                        else:
                            v = hug_temporal(ser, t0, b, s, vr)
                        z = zfun(r, v, pm, s)
                        d = v[t0:] - ser[t0:]
                        cell = out[r][vr][str(b)]
                        cell["det"].append((ts, float((z[t0:] > TAU_S).mean())))
                        cell["bias_pct"].append((ts, float(d.mean() / mean * 100)))
                        cell["bias_ms"].append((ts, float(d.mean())))
                        cell["end_bias_pct"].append((ts, float(d[-1] / mean * 100)))
    res = {}
    for r in REFS:
        res[r] = {}
        for vr in Q4_VARIANTS:
            res[r][vr] = {b: {k: agg_seed(v) for k, v in d.items()}
                          for b, d in out[r][vr].items()}
    ss = sorted({(sd, sc) for sd, sc, _ in scale_info})
    res["scale"] = {"per_fold_s_ms": {sd: sc for sd, sc in ss},
                    "tau_s_times_s_ms": {sd: TAU_S * sc for sd, sc in ss},
                    "median_cell_delay_ms": float(np.median([m for _, _, m in scale_info]))}
    return res


# ==========================================================================
# Q6：校準期中毒（凍結尺度 s）
# ==========================================================================
def poison_training(Wd, k, kind, mag):
    """於一個 training seed 中，對出現窗數最多之 k 個 cell（最壞情況）自 t=0 起竄改"""
    cnt = collections.Counter(c for w in Wd for c in Wd[w])
    targets = [c for c, _ in sorted(cnt.items(), key=lambda x: (-x[1], x[0]))[:k]]
    out = {}
    for t, w in enumerate(sorted(Wd)):
        row = dict(Wd[w])
        for c in targets:
            if c in row:
                row[c] = row[c] * (1 + mag * t) if kind == "drift" else row[c] * (1 + mag)
        out[w] = row
    return out, targets


def run_q6(data, seeds):
    res = {"baseline": {}, "poisoned": {}}
    # 基線（未中毒）
    base_s = {ts: global_scale([data[x] for x in seeds if x != ts]) for ts in seeds}

    def eval_with(scales):
        det = {r: {rate: [] for rate in Q6_EVAL_RATES} for r in REFS}
        fpr = {r: [] for r in REFS}
        for ts in seeds:
            s = scales[ts]
            for tc, idx, ser, pm in build_samples(data[ts]):
                mean = ser.mean(); t0 = len(ser) // 2
                for r in REFS:
                    fpr[r].append((ts, float((zfun(r, ser, pm, s)[t0:] > TAU_S).mean())))
                    for rate in Q6_EVAL_RATES:
                        z = zfun(r, inject_drift(ser, t0, rate, mean), pm, s)
                        det[r][rate].append((ts, float((z[t0:] > TAU_S).mean())))
        return ({r: agg_seed(fpr[r]) for r in REFS},
                {r: {str(rate): agg_seed(det[r][rate]) for rate in Q6_EVAL_RATES} for r in REFS})

    f0, d0 = eval_with(base_s)
    res["baseline"] = {"s_ms": base_s, "clean_fpr": f0, "drift": d0}
    for k in Q6_K:
        for kind, mag in Q6_POISON:
            scales, tgt, eps = {}, {}, {}
            for ts in seeds:
                train, n_all, n_bad = [], 0, 0
                for x in seeds:
                    if x == ts:
                        continue
                    pw, tg = poison_training(data[x], k, kind, mag)
                    train.append(pw)
                    tgt[x] = tg
                    for w in data[x]:
                        n_all += len(data[x][w])
                        n_bad += sum(1 for c in data[x][w] if c in tg)
                scales[ts] = global_scale(train)
                eps[ts] = n_bad / n_all
            f, d = eval_with(scales)
            res["poisoned"][f"k{k}_{kind}{mag}"] = {
                "k": k, "kind": kind, "mag": mag,
                "s_ms": scales,
                "s_ratio": {ts: scales[ts] / base_s[ts] for ts in seeds},
                "s_ratio_max": max(scales[ts] / base_s[ts] for ts in seeds),
                "poisoned_cells_per_train_seed": tgt,
                # 校準資料中被竄改之值所佔比例（MAD 之崩潰點為 0.5）
                "contamination_frac": eps,
                "contamination_frac_max": max(eps.values()),
                "clean_fpr": f, "drift": d}
    return res


# ==========================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=None)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--no-fig", action="store_true")
    args = ap.parse_args()
    out_dir = args.out_dir or OUT_DIR
    os.makedirs(out_dir, exist_ok=True)

    files = find_files(args.data_dir)
    if len(files) < 2:
        print("資料不足，用 --data-dir 指定。"); return
    seeds = [os.path.basename(f).split("seed")[-1].replace(".txt", "") for f in files]
    data = {s: load_cell_delay(f) for s, f in zip(seeds, files)}
    print(f"載入 {len(seeds)} seed: {seeds}\n")

    q1, q2, chk = run_q1_q2(data, seeds)

    # ---------------- 一致性檢查 1：與 E9 逐位相同 ----------------
    e9_path = os.path.join(out_dir, "E9_operating_regime.json")
    if not os.path.exists(e9_path):
        raise SystemExit(f"找不到 {e9_path}，請先跑 run_E9_operating_regime.py")
    e9 = json.load(open(e9_path, encoding="utf-8"))
    bad = []
    for r in REFS:
        if abs(chk["fpr"][r] - e9["clean_fpr"][r]["mean"]) > 1e-12:
            bad.append(("fpr", r, e9["clean_fpr"][r]["mean"], chk["fpr"][r]))
        for rate, v in chk["drift"][r].items():
            if abs(v - e9["drift"][r][rate]["mean"]) > 1e-12:
                bad.append(("drift", r, rate, e9["drift"][r][rate]["mean"], v))
    print("── 一致性檢查 1（與 E9_operating_regime.json）──")
    if bad:
        for b in bad:
            print("  ✗", b)
        raise SystemExit("與 E9 不一致，停止，不寫檔。")
    print("  ✓ 乾淨 FPR 與 8 個漂移速率之偵測率逐位相同\n")

    q4 = run_q4(data, seeds)
    # ---------------- 一致性檢查 2：oracle 於門檻下須為 0 ----------------
    bad = []
    for b in Q4_BETAS:
        if b < 1:
            for r in REFS:
                m = q4[r]["oracle"][str(b)]["det"]["mean"]
                if m != 0.0:
                    bad.append((r, b, m))
    print("── 一致性檢查 2（oracle 貼門檻攻擊依構造不可偵測）──")
    if bad:
        for x in bad:
            print("  ✗", x)
        raise SystemExit("oracle 攻擊被偵測到，實作有誤，停止，不寫檔。")
    print("  ✓ β < 1 時兩種參照之偵測率皆為 0\n")

    q6 = run_q6(data, seeds)

    res = {"n_seeds": len(seeds), "tau_S": TAU_S, "W_hist": W_HIST,
           "min_neighbors": MIN_NEIGHBOR, "rates": Q1_RATES, "horizons": Q1_HORIZONS,
           "Q1_frontier": q1, "Q2_bias_at_detection": q2,
           "Q4_threshold_hugging": q4, "Q6_calibration_poisoning": q6,
           "consistency": {"E9_reproduced": "ok", "Q4_oracle_zero": "ok"},
           "note": ("delay-dimension synthetic injection on D-SH; seed is the statistical unit; "
                    "Q4 oracle is an upper bound (peer median known before reporting)")}
    path = os.path.join(out_dir, "slow_poisoning_suite.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, ensure_ascii=False)

    report(res)
    print(f"\n寫入 {path}")
    if not args.no_fig:
        draw(res, out_dir)


def report(res):
    q1, q2, q4, q6 = (res["Q1_frontier"], res["Q2_bias_at_detection"],
                      res["Q4_threshold_hugging"], res["Q6_calibration_poisoning"])
    print("══ Q1 偵測前沿 r*（P(於 D 窗內偵測) ≥ 0.5 且高於乾淨底線之最低速率）══")
    print(f"{'準則':>4} {'D':>3} | {'空間 r*':>8} {'底線':>6} | {'時間 r*':>8} {'底線':>6}")
    for c in CRITERIA:
        for D in Q1_HORIZONS:
            a = q1["spatial"][c][str(D)]; b = q1["temporal"][c][str(D)]
            fa = lambda x: f"{x*100:.2f}%" if x is not None else "  >15%"
            print(f"{c:>4} {D:>3} | {fa(a['r_star']):>8} {a['clean_floor']['mean']:>6.2f} | "
                  f"{fa(b['r_star']):>8} {b['clean_floor']['mean']:>6.2f}")

    print("\n══ Q2 首次偵測時之偏移（準則 2c；中位數，僅偵測到者）／未偵測比例 ══")
    print(f"{'速率':>7} | {'空間 窗':>6} {'偏移%':>7} {'未偵測':>6} | {'時間 窗':>6} {'偏移%':>7} {'未偵測':>6}")
    for rate in res["rates"]:
        a = q2["spatial"]["2c"][str(rate)]; b = q2["temporal"]["2c"][str(rate)]
        f = lambda x, p: f"{x:{p}}" if x is not None else "     —"
        print(f"{rate*100:>6.2f}% | {f(a['detected_median_windows'], '6.0f')} "
              f"{f(a['detected_median_offset_pct'], '7.1f')} {a['undetected_frac']['mean']:>6.2f} | "
              f"{f(b['detected_median_windows'], '6.0f')} {f(b['detected_median_offset_pct'], '7.1f')} "
              f"{b['undetected_frac']['mean']:>6.2f}")

    print("\n══ Q4 貼門檻攻擊：偵測率／平均誘導偏差（% of mean）／注入區間末之偏差 ══")
    sc = q4["scale"]
    print(f"   τ_S·s（每 fold）= " + ", ".join(f"{k}:{v:.3f} ms" for k, v in sc["tau_s_times_s_ms"].items())
          + f"；cell delay 中位數 {sc['median_cell_delay_ms']:.3f} ms")
    for vr in Q4_VARIANTS:
        for b in Q4_BETAS:
            a = q4["spatial"][vr][str(b)]; t = q4["temporal"][vr][str(b)]
            print(f"  {vr:>6} β={b:<4} | 空間 det {a['det']['mean']:.2f} 偏差 {a['bias_pct']['mean']:>6.1f}% "
                  f"末 {a['end_bias_pct']['mean']:>7.1f}% | 時間 det {t['det']['mean']:.2f} "
                  f"偏差 {t['bias_pct']['mean']:>7.1f}% 末 {t['end_bias_pct']['mean']:>8.1f}%")

    print("\n══ Q6 校準期中毒：s 放大倍數（最大 fold）／測試期空間偵測率（漂移 1%/窗）／乾淨 FPR ══")
    b0 = q6["baseline"]
    print(f"  未中毒            s×1.00  det1% {b0['drift']['spatial']['0.01']['mean']:.2f}  "
          f"FPR {b0['clean_fpr']['spatial']['mean']:.3f}")
    for name, v in q6["poisoned"].items():
        print(f"  {name:<16}  ε≤{v['contamination_frac_max']:.2f}  s×{v['s_ratio_max']:.2f}  det1% {v['drift']['spatial']['0.01']['mean']:.2f}  "
              f"FPR {v['clean_fpr']['spatial']['mean']:.3f}")


def draw(res, out_dir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    C = {"spatial": "#2b8a3e", "temporal": "#c92a2a"}
    rates = res["rates"]; x = [r * 100 for r in rates]

    # Q1
    fig, axes = plt.subplots(1, len(Q1_HORIZONS), figsize=(14, 3.8), sharey=True)
    for ax, D in zip(axes, Q1_HORIZONS):
        for r in REFS:
            d = res["Q1_frontier"][r]["2c"][str(D)]
            ax.plot(x, [d["detect"][str(k)]["mean"] for k in rates], marker="o", ms=4,
                    color=C[r], ls="-" if r == "spatial" else "--", label=r)
            ax.axhline(d["clean_floor"]["mean"], color=C[r], lw=0.8, ls=":")
        ax.set_xscale("log"); ax.set_title(f"detected within {D} windows", fontsize=10)
        ax.set_xlabel("drift rate (%/window, log)"); ax.grid(alpha=0.3)
    axes[0].set_ylabel("P(detected), criterion 2c"); axes[0].legend(fontsize=8)
    fig.suptitle("Q1 detection frontier (dotted = clean floor)", fontsize=11)
    fig.tight_layout(); fig.savefig(os.path.join(out_dir, "fig_slow_Q1_frontier.png"), dpi=200)
    plt.close(fig)

    # Q2
    fig, ax = plt.subplots(figsize=(6.5, 4))
    for r in REFS:
        d = res["Q2_bias_at_detection"][r]["2c"]
        ax.plot(x, [d[str(k)]["all_median_offset_pct_censored"] for k in rates], marker="o",
                color=C[r], ls="-" if r == "spatial" else "--", label=f"{r} (censored median)")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("drift rate (% per evaluated window, log)")
    ax.set_ylabel("median offset (% of mean)\nundetected samples censored at end of series")
    ax.grid(alpha=0.3); ax.legend(fontsize=8)
    ax.set_title("Q2 censored median offset (all samples; differs from the detected-only table)", fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(out_dir, "fig_slow_Q2_bias.png"), dpi=200)
    plt.close(fig)

    # Q4
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for ax, key, lab in ((axes[0], "det", "detection rate"),
                         (axes[1], "end_bias_pct", "bias at end of interval (% of mean)")):
        for r in REFS:
            for vr, ls in zip(Q4_VARIANTS, ("-", "--", ":")):
                ax.plot(Q4_BETAS, [res["Q4_threshold_hugging"][r][vr][str(b)][key]["mean"]
                                   for b in Q4_BETAS], marker="o", ms=4, color=C[r], ls=ls,
                        label=f"{r}/{vr}")
        ax.set_xlabel("β (fraction of τ_S·s)"); ax.set_ylabel(lab); ax.grid(alpha=0.3)
    axes[1].set_yscale("symlog"); axes[0].legend(fontsize=7, ncol=2)
    fig.suptitle("Q4 threshold-hugging attacker", fontsize=11)
    fig.tight_layout(); fig.savefig(os.path.join(out_dir, "fig_slow_Q4_hugging.png"), dpi=200)
    plt.close(fig)
    print(f"圖已存: {out_dir}/fig_slow_Q*.png")


if __name__ == "__main__":
    main()
