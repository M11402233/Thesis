#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diag_si_zero_handling.py — 第二階段步 2 之診斷（探索性，2026-11-20；結果未經作者審閱，不得直接作為正文主結果）

回答使用者 11-20 之問題（S_i 主版本「排除零延遲」vs 對照「含零延遲」操作點差異之原因）：
  D1 量測定義：零延遲 PDU 是否即「無 RLC 時間戳」（nRxZeroDelay vs nRxNoRlcTag，逐列、逐窗差分）；
     DL mmWave 樣本之零值比例；(窗, cell, UE) 覆蓋率（主版本：全為零值 → 缺值；對照版：該 UE 值 = 0）。
  D2 重現檢查：兩版本之空間乾淨誤報（own 集合）須逐位重現步 2 之 E9_operating_regime_rt.json；不符即停止。
  D3 共同集合：兩版本之同一 (seed, cell, 窗) 且 peer 集合相同者；比較未標準化殘差 |v − c|、尺度 s、z 與誤報；
     交換尺度（A 之殘差 ÷ B 之 s）以分辨差異來自觀測值或尺度。
  D4 訓練 seed（尺度之估計資料）與測試 seed 之誤報：s 是否在訓練資料上就已給出相同誤報（跨 seed 失效 vs 本身未校準）。
  D5 分層：依受測 cell 該窗之最少有效 PDU 數（UE 間最小值）、cell 零值比例、UE 數分層之誤報。
注意：τ_S = 4 為凍結值，S_i 從未被校準到任何目標誤報率；s = 1.4826·MAD(訓練 seed 之 cell 延遲水準)。

跑法（新機器 ~/zt_dev/p2 佈局）：
  ZT_DATASET=d30p python3 diag_si_zero_handling.py [--out <dir>]
"""
import os
import sys
import glob
import json
import argparse
import collections
import numpy as np

import datasets as DS
import percell_source as PS
import planB_rt as P

VARS = ("percell", "percell_zero")
TAU = P.TAU_S


def q(a, ps=(0.1, 0.25, 0.5, 0.75, 0.9)):
    a = np.asarray(a, float)
    return {str(p): (float(np.quantile(a, p)) if len(a) else None) for p in ps}


def cell_means(sw):
    """與 interval_source.cell_delay_means 相同：{w: {cell: UE 延遲之未加權平均}}，排除 cell 1"""
    return {w: {c: float(sum(u.values()) / len(u)) for c, u in cells.items() if c != 1 and u} for w, cells in sw}


def load(path):
    aux = os.path.dirname(DS.aux_path(DS.seed_of(path), "x")); mw = DS.CFG["max_window"] - 1
    pc = PS.percell_delta(aux, mw); z = PS.zero_delta(aux, mw)
    Wd = {v: cell_means(PS.si_windows(aux, zero=(v == "percell_zero"), max_window=mw, _pc=pc, _z=z)) for v in VARS}
    return aux, pc, z, Wd


def measurement(pc, z):
    """D1：DL mmWave 之零值 = 無時間戳？與覆蓋率；並回傳逐 (w, cell) 之 UE 有效數、零值比例"""
    n_rows = n_ne = n_unk = 0
    tot = zer = 0
    ue_win = ue_allzero = 0
    per_cw = {}
    for k in pc:
        acc = collections.defaultdict(lambda: [0, 0])          # (c, i) → [nRx, nZero]
        for key, d in pc[k].items():
            c = key[0]
            zz = z.get(k, {}).get(key)
            if zz is None:
                zz = (d[2], 0, 0, 0)
            n_rows += 1
            if zz[1] != zz[2]:
                n_ne += 1
            n_unk += zz[3]
            if zz[0] != d[2]:
                raise SystemExit(f"✗ r9rx 與 percell 之 ΔnRx 不符 k={k} {key}")
            if c == 1:
                continue
            tot += d[2]; zer += zz[1]
            acc[(c, key[1])][0] += d[2]; acc[(c, key[1])][1] += zz[1]
        cw = collections.defaultdict(lambda: {"nvalid": [], "nrx": 0, "nz": 0})
        for (c, i), (n, nz) in acc.items():
            if n == 0:
                continue
            ue_win += 1
            if n == nz:
                ue_allzero += 1
            cw[c]["nvalid"].append(n - nz); cw[c]["nrx"] += n; cw[c]["nz"] += nz
        for c, r in cw.items():
            per_cw[(k, c)] = {"nvalid_min_main": min([x for x in r["nvalid"] if x > 0], default=0),
                              "n_ue_main": sum(x > 0 for x in r["nvalid"]), "n_ue_zero": len(r["nvalid"]),
                              "zero_share": r["nz"] / r["nrx"] if r["nrx"] else None}
    return {"rows": n_rows, "rows_zero_ne_notag": n_ne, "tag_unknown": n_unk,
            "dl_mmw_pdus": tot, "dl_mmw_zero_pdus": zer, "dl_mmw_zero_share": zer / tot if tot else None,
            "ue_windows_with_rx": ue_win, "ue_windows_all_zero": ue_allzero,
            "ue_windows_all_zero_share": ue_allzero / ue_win if ue_win else None}, per_cw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(DS.ROOT, "results", "d30p_diag_zero"))
    a = ap.parse_args()
    if DS.NAME != "d30p":
        raise SystemExit("只適用 ZT_DATASET=d30p")
    os.makedirs(a.out, exist_ok=True)
    files = sorted(glob.glob(os.path.join(DS.DATA_DIR, DS.PATTERN)))
    seeds = [f.split("seed")[-1].replace(".txt", "")[-4:] for f in files]
    data = {v: {} for v in VARS}; meas = {}; cwinfo = {}
    for s, f in zip(seeds, files):
        aux, pc, z, Wd = load(f)
        for v in VARS:
            data[v][s] = Wd[v]
        meas[s], cwinfo[s] = measurement(pc, z)
        print(f"seed {s}：DL mmWave 零值比例 {meas[s]['dl_mmw_zero_share']:.4f}；零值≠無時間戳之列 {meas[s]['rows_zero_ne_notag']}；"
              f"UE 窗全為零值 {meas[s]['ue_windows_all_zero']}/{meas[s]['ue_windows_with_rx']}", flush=True)
    out = {"note": "探索性診斷，2026-11-20 建立，結果未經作者審閱", "tau_S": TAU, "measurement": meas}
    bad = [s for s in seeds if meas[s]["rows_zero_ne_notag"] or meas[s]["tag_unknown"]]
    out["D1_zero_equals_notag_all_rows"] = not bad

    # ---- D2：重現步 2 ----
    S = {v: {} for v in VARS}; smp = {v: {} for v in VARS}
    for v in VARS:
        acc = []
        for ts in seeds:
            S[v][ts] = P.fold_scale(data[v], seeds, ts)
            smp[v][ts] = {sm.cell: sm for sm in P.samples_of(ts, data[v][ts])}
            for sm in smp[v][ts].values():
                acc.append((ts, P.rate(P.flags_from_z(P.z_spatial(sm, sm.own, S[v][ts])), P.own_set(sm, "spatial"))))
        got = P.agg_seed([(sd, x) for sd, x in acc if x is not None])["mean"]
        ref = json.load(open(os.path.join(DS.ROOT, "results", f"d30p_delay_{v}", "E9_operating_regime_rt.json"),
                             encoding="utf-8"))["own"]["spatial"]["clean_fpr"]["mean"]
        print(f"D2 {v}：空間乾淨誤報 {got:.6f}（步 2：{ref:.6f}）")
        if got != ref:
            raise SystemExit(f"✗ D2 未重現步 2（{v}）：{got} vs {ref}")
    out["D2_reproduces_step2"] = True

    # ---- D3／D5：共同集合 ----
    rows = []                                   # 逐 (seed, cell, w)
    n_own = {v: 0 for v in VARS}; n_peerdiff = 0
    for ts in seeds:
        for c in set(smp["percell"][ts]) | set(smp["percell_zero"][ts]):
            sa = smp["percell"][ts].get(c); sb = smp["percell_zero"][ts].get(c)
            for v, sm in (("percell", sa), ("percell_zero", sb)):
                if sm:
                    n_own[v] += len(sm.post)
            if not (sa and sb):
                continue
            for w in sorted(set(sa.post) & set(sb.post)):
                pa = set(data["percell"][ts][w]) - {c}; pb = set(data["percell_zero"][ts][w]) - {c}
                if pa != pb:
                    n_peerdiff += 1
                    continue
                info = cwinfo[ts].get((w, c), {})
                r = {"seed": ts, "cell": c, "w": w, "n_peer": len(pa),
                     "nvalid_min": info.get("nvalid_min_main"), "n_ue_main": info.get("n_ue_main"),
                     "n_ue_zero": info.get("n_ue_zero"), "zero_share": info.get("zero_share"),
                     "n_ue_diff": (info["n_ue_zero"] - info["n_ue_main"]) if info else None}
                for v, sm in (("percell", sa), ("percell_zero", sb)):
                    r[f"res_{v}"] = abs(sm.own[w] - sm.pm[w]); r[f"lvl_{v}"] = sm.own[w]; r[f"pm_{v}"] = sm.pm[w]
                rows.append(r)
    n_com = len(rows)
    print(f"D3 共同集合 {n_com} 窗（主版本 own {n_own['percell']}、對照 own {n_own['percell_zero']}；peer 集合不同而排除 {n_peerdiff}）")
    d3 = {"n_common": n_com, "n_own": n_own, "n_excluded_peer_differs": n_peerdiff, "per_fold": {}}
    tot = collections.defaultdict(list)
    for ts in seeds:
        R = [r for r in rows if r["seed"] == ts]
        f = {"s": {v: S[v][ts] for v in VARS}, "n": len(R)}
        for va in VARS:
            res = np.array([r[f"res_{va}"] for r in R])
            f[f"median_residual_ms_{va}"] = float(np.median(res))
            for vb in VARS:
                fp = float((res / S[vb][ts] > TAU).mean())
                f[f"fpr_res_{va}_scale_{vb}"] = fp
                tot[f"fpr_res_{va}_scale_{vb}"].append(fp)
        d3["per_fold"][ts] = f
        print(f"  fold {ts}：s 主 {S['percell'][ts]:.3f}／對照 {S['percell_zero'][ts]:.3f} ms；"
              f"殘差中位數 主 {f['median_residual_ms_percell']:.3f}／對照 {f['median_residual_ms_percell_zero']:.3f} ms；"
              f"誤報 主 {f['fpr_res_percell_scale_percell']:.3f}、對照 {f['fpr_res_percell_zero_scale_percell_zero']:.3f}；"
              f"交換尺度 主殘差/對照 s {f['fpr_res_percell_scale_percell_zero']:.3f}、對照殘差/主 s {f['fpr_res_percell_zero_scale_percell']:.3f}")
    d3["fold_mean"] = {k: float(np.mean(v)) for k, v in tot.items()}
    for v in VARS:
        d3[f"residual_ms_quantiles_{v}"] = q([r[f"res_{v}"] for r in rows])
        d3[f"level_ms_quantiles_{v}"] = q([r[f"lvl_{v}"] for r in rows])
    out["D3_common"] = d3

    # ---- D4：訓練 seed vs 測試 seed ----
    d4 = {}
    for v in VARS:
        tr, te = [], []
        for ts in seeds:
            s = S[v][ts]
            for x in seeds:
                for sm in smp[v][x].values():
                    fp = P.rate(P.flags_from_z(P.z_spatial(sm, sm.own, s)), P.own_set(sm, "spatial"))
                    (te if x == ts else tr).append(fp)
        d4[v] = {"train_seeds_fpr": float(np.mean(tr)), "test_seed_fpr": float(np.mean(te))}
        print(f"D4 {v}：以 fold 之 s 於訓練 seed 之空間乾淨誤報 {d4[v]['train_seeds_fpr']:.3f}；測試 seed {d4[v]['test_seed_fpr']:.3f}")
    out["D4_train_vs_test"] = d4

    # ---- D5：分層（共同集合，各用自身尺度）----
    def strat(key, edges, label):
        res = {}
        for lo, hi in edges:
            R = [r for r in rows if r[key] is not None and lo <= r[key] < hi]
            if not R:
                continue
            e = {"n": len(R)}
            for v in VARS:
                e[f"fpr_{v}"] = float(np.mean([r[f"res_{v}"] / S[v][r["seed"]] > TAU for r in R]))
                e[f"median_residual_ms_{v}"] = float(np.median([r[f"res_{v}"] for r in R]))
            res[f"[{lo},{hi})"] = e
        print(f"D5 依{label}：")
        for b, e in res.items():
            print(f"   {b:>14} n={e['n']:5d}  誤報 主 {e['fpr_percell']:.3f}／對照 {e['fpr_percell_zero']:.3f}；"
                  f"殘差中位數 主 {e['median_residual_ms_percell']:.3f}／對照 {e['median_residual_ms_percell_zero']:.3f} ms")
        return res
    inf = float("inf")
    out["D5"] = {
        "nvalid_min": strat("nvalid_min", [(1, 10), (10, 100), (100, 1000), (1000, inf)], "受測 cell 之最少有效 PDU 數（UE 間）"),
        "zero_share": strat("zero_share", [(0, 0.05), (0.05, 0.1), (0.1, 0.2), (0.2, 0.4), (0.4, 1.01)], "受測 cell 之零值比例"),
        "ue_count_diff": strat("n_ue_diff", [(0, 1), (1, 2), (2, 100)], "對照版多出之 UE 數（全為零值之 UE）"),
    }
    with open(os.path.join(a.out, "diag_si_zero_handling.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)
    print("寫出", os.path.join(a.out, "diag_si_zero_handling.json"))


if __name__ == "__main__":
    main()
