#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_E9d_real_load_alarms.py — E9d：真實 trace 中之全場域負載變化與乾淨誤報之關聯（第四章 4.7.5.2 延伸）

【要回答的問題（限定）】
  監督式分類器（E9b level 變體）之乾淨誤報，是否集中於「同窗其他 cell 之負載與延遲共同上升」之窗？
  不修改模型、尺度或門檻；E9c 以合成共模擾動所揭示之機制，於真實 trace 中是否有對應之觀察。
  此為觀察性分析：相關不等於因果，不得據以斷言負載上升造成誤報。

【事先固定之定義（於看到任何告警結果前訂定，不得事後調整）】
  負載代理    L_c(w) = Σ tbSize（位元組）over RxPacketTrace 中 DL 列、cellId = c、⌊time⌋ = w
              稱為「排程 TB 位元組量（DL，含重傳與解碼失敗之 TB）」，**不是** PRB 使用率或流量需求。
              敏感度：僅計新傳輸（rv = 0）之版本。
              來源說明：DlMacStats 於本資料中 cellId／IMSI 恆為 0、MCS 與 TB size 恆為定值
              （LTE 錨點之 MAC 紀錄），不含逐 mmWave cell 之負載變化，故不採用。
  正規化      ℓ_c(w) = L_c(w) / median_w' L_c(w')；d_c(w) = delay_c(w) / median_w' delay_c(w')
              （median 取該 seed 中 cell c 有 RLC 上報之窗）
  場域指標    對評估窗 (seed, 受測 cell j, w)：P = 該窗有上報之其他 mmWave cell（full-consensus，|P| ≥ 2）
              F = median_{k∈P} ℓ_k(w)；D = median_{k∈P} d_k(w)
              **以同窗其他 cell 定義，不含受測 cell 自身之值**，使分組獨立於受測 cell 之上報。
  分組        依 F、D 是否 ≥ 該 seed 全部評估窗之第 q 分位數，分為 2 × 2 四組；
              「共模上升窗」= F 高且 D 高。主分析 q = 0.75；敏感度 q ∈ {0.5, 0.9}。
              分組只使用 trace 之負載與延遲，**不使用任何告警結果**。
  評估窗      與 E9b 相同：各 seed × cell 樣本 full-consensus 序列之後半段（以序列中點為界）。
  告警        空間共識（τ_S = 4）、時間自我參照（E9）、監督式分類器（E9b level、thr_cal，同種子重新訓練）。
  彙總        各組內之窗合併告警率；另列各 seed 之組內告警率與窗數，避免結論由單一 seed 驅動。

【內建檢查】
  1. 資料一致性：4 個 seed 之 aux DlE2RlcStats.txt 須與 si_lstm_seeds 逐位元組相同，否則拒絕分析。
  2. 三種方法於評估窗之乾淨誤報率須與 E9／E9b 輸出逐位相同。
  3. 對齊：每個評估窗之受測 cell 與 peer 均須於 PHY trace 中有對應之 cellId（否則報告缺漏數）。

【輸出】
  <out>/E9d_real_load_alarms.json

跑法：
  python3 run_E9d_real_load_alarms.py --selftest   # 僅檢查資料對齊，不計算任何告警率
  python3 run_E9d_real_load_alarms.py
"""
import os
import sys
import gzip
import json
import filecmp
import argparse
import collections
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_E9_operating_regime as E9
from run_E9_operating_regime import load_cell_delay, global_scale, TAU_S
from run_slow_poisoning_suite import find_files, build_samples
import run_E9c_common_mode as C

ROOT = os.path.expanduser("~/oran-zt-kpm-verification/data")
AUX = os.path.join(ROOT, "si_lstm_aux")
SEEDS_DIR = os.path.join(ROOT, "si_lstm_seeds")
Q_MAIN = 0.75
Q_SENS = [0.5, 0.9]
METHODS = C.METHODS


def aux_dir(sd):
    return os.path.join(AUX, f"ues1_t300_seed{sd}_aux")


def check_aux(seeds):
    res = {}
    for sd in seeds:
        a = os.path.join(aux_dir(sd), "DlE2RlcStats.txt")
        b = os.path.join(SEEDS_DIR, f"ues1_t300_seed{sd}.txt")
        res[sd] = os.path.exists(a) and filecmp.cmp(a, b, shallow=False)
    return res


def load_phy(sd):
    """回傳 {cell: {w: bytes_all}}, {cell: {w: bytes_newtx}}"""
    allb = collections.defaultdict(lambda: collections.defaultdict(int))
    newb = collections.defaultdict(lambda: collections.defaultdict(int))
    with gzip.open(os.path.join(aux_dir(sd), "RxPacketTrace.txt.gz"), "rt") as fh:
        fh.readline()
        for line in fh:
            if not line.startswith("DL"):
                continue
            p = line.split("\t")
            c = int(p[7]); w = int(float(p[1])); tb = int(p[10])
            allb[c][w] += tb
            if p[12] == "0":
                newb[c][w] += tb
    return allb, newb


def norm(series):
    """{w: v} → {w: v / median}（median = 0 時回傳 None）"""
    med = float(np.median(list(series.values()))) if series else 0.0
    return {w: (v / med if med > 0 else None) for w, v in series.items()}


def field_index(Wd, phy, ts_norm_delay, tc, w):
    peers = [c for c in Wd[w] if c != tc]
    lo = [phy[c].get(w) for c in peers]
    de = [ts_norm_delay[c][w] for c in peers]
    if any(v is None for v in lo) or any(v is None for v in de):
        return None, None
    return float(np.median(lo)), float(np.median(de))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--selftest", action="store_true", help="只檢查資料與對齊，不計算任何告警率")
    args = ap.parse_args()
    out_dir = args.out_dir or E9.OUT_DIR
    files = find_files(None)
    seeds = [os.path.basename(f).split("seed")[-1].replace(".txt", "") for f in files]

    ok = check_aux(seeds)
    print("── 資料一致性（aux DlE2RlcStats vs si_lstm_seeds）──")
    for sd, v in ok.items():
        print(f"  {sd}: {'✓' if v else '✗ 或未產出'}")
    avail = [sd for sd, v in ok.items() if v]
    if not args.selftest and not all(ok.values()):
        raise SystemExit("並非全部 seed 通過逐位比對，拒絕分析。")

    data = {s: load_cell_delay(f) for s, f in zip(seeds, files)}
    phy_all, phy_new, ndelay = {}, {}, {}
    for sd in (avail if args.selftest else seeds):
        a, n = load_phy(sd)
        rlc_cells = {c for w in data[sd] for c in data[sd][w]}
        phy_all[sd] = {c: norm({w: a[c].get(w, 0) for w in data[sd] if c in data[sd][w]}) for c in rlc_cells}
        phy_new[sd] = {c: norm({w: n[c].get(w, 0) for w in data[sd] if c in data[sd][w]}) for c in rlc_cells}
        ndelay[sd] = {c: norm({w: data[sd][w][c] for w in data[sd] if c in data[sd][w]}) for c in rlc_cells}
        miss = sorted(c for c in rlc_cells if c not in a)
        print(f"  {sd}: RLC cells {sorted(rlc_cells)}；PHY DL cells {sorted(a)}；PHY 缺漏 {miss}")

    if args.selftest:
        n_win, n_none = 0, 0
        for sd in avail:
            for tc, idx, ser, pm in build_samples(data[sd]):
                for w in idx[len(ser) // 2:]:
                    F, D = field_index(data[sd], phy_all[sd], ndelay[sd], tc, w)
                    n_win += 1; n_none += F is None
        print(f"\n[selftest] 評估窗 {n_win}，場域指標無法計算 {n_none}；未計算任何告警率。")
        return

    e9 = json.load(open(os.path.join(out_dir, "E9_operating_regime.json"), encoding="utf-8"))
    e9b = json.load(open(os.path.join(out_dir, "E9b_supervised_baseline.json"), encoding="utf-8"))
    target_fpr = e9b["target_fpr_from_E9_spatial"]

    rows = []           # 每個評估窗一列
    chk = {m: [] for m in METHODS}
    n_none = 0
    for fi, ts in enumerate(seeds):
        m, s, med, thr = C.train_fold(data, seeds, fi, ts, target_fpr)
        model = (m, med, thr)
        for tc, idx, ser, pm in build_samples(data[ts]):
            t0 = len(ser) // 2
            fl = {meth: C.flags(meth, ser, pm, s, model) for meth in METHODS}
            for meth in METHODS:
                chk[meth].append(float(fl[meth][t0:].mean()))
            for i in range(t0, len(ser)):
                w = idx[i]
                F, D = field_index(data[ts], phy_all[ts], ndelay[ts], tc, w)
                Fn, _ = field_index(data[ts], phy_new[ts], ndelay[ts], tc, w)
                if F is None or Fn is None:
                    n_none += 1
                    continue
                rows.append({"seed": ts, "cell": tc, "w": w, "F": F, "Fnew": Fn, "D": D,
                             **{meth: bool(fl[meth][i]) for meth in METHODS}})

    bad = []
    for meth, ref in (("spatial", e9["clean_fpr"]["spatial"]["mean"]),
                      ("temporal", e9["clean_fpr"]["temporal"]["mean"]),
                      ("supervised", e9b["results"]["level"]["thr_cal"]["clean_fpr"]["mean"])):
        got = float(np.mean(chk[meth]))
        if abs(got - ref) > 1e-12:
            bad.append((meth, ref, got))
    print("\n── 一致性檢查（評估窗乾淨誤報率 vs E9／E9b）──")
    if bad:
        print("  ✗", bad); raise SystemExit("不一致，停止，不寫檔。")
    print(f"  ✓ 三者逐位相同；評估窗 {len(rows)}，場域指標無法計算而排除 {n_none}\n")

    def grouping(q, fkey):
        thrF = {sd: float(np.quantile([r[fkey] for r in rows if r["seed"] == sd], q)) for sd in seeds}
        thrD = {sd: float(np.quantile([r["D"] for r in rows if r["seed"] == sd], q)) for sd in seeds}
        groups = collections.defaultdict(list)
        for r in rows:
            g = ("F高" if r[fkey] >= thrF[r["seed"]] else "F低") + ("D高" if r["D"] >= thrD[r["seed"]] else "D低")
            groups[g].append(r)
        out = {}
        for g in ("F高D高", "F高D低", "F低D高", "F低D低"):
            rs = groups.get(g, [])
            per_seed = {}
            for sd in seeds:
                rr = [r for r in rs if r["seed"] == sd]
                per_seed[sd] = {"n": len(rr), **{meth: (float(np.mean([r[meth] for r in rr])) if rr else None)
                                               for meth in METHODS}}
            out[g] = {"n": len(rs), **{meth: (float(np.mean([r[meth] for r in rs])) if rs else None)
                                      for meth in METHODS}, "per_seed": per_seed}
        return {"q": q, "load": fkey, "thrF": thrF, "thrD": thrD, "groups": out}

    analyses = {"main": grouping(Q_MAIN, "F"),
                "sens_newtx": grouping(Q_MAIN, "Fnew"),
                **{f"sens_q{q}": grouping(q, "F") for q in Q_SENS}}
    res = {"definitions": {"load_proxy": "sum of DL tbSize bytes per cell per 1-s window (RxPacketTrace), incl. retx and corrupt",
                           "field_index": "median over same-window peer cells (target excluded) of per-cell median-normalized load / delay",
                           "common_mode_rise": "F >= per-seed q-quantile AND D >= per-seed q-quantile",
                           "q_main": Q_MAIN, "q_sens": Q_SENS},
           "n_eval_windows": len(rows), "n_excluded_no_field_index": n_none,
           "overall": {meth: float(np.mean([r[meth] for r in rows])) for meth in METHODS},
           "analyses": analyses, "consistency": "ok",
           "note": "observational association only; not causal"}
    path = os.path.join(out_dir, "E9d_real_load_alarms.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, ensure_ascii=False)

    for name, a in analyses.items():
        print(f"══ {name}（q = {a['q']}，負載 = {a['load']}）：組內窗合併告警率 ══")
        print(f"{'組':>6} {'窗數':>5} | " + " ".join(f"{m:>10}" for m in METHODS))
        for g, v in a["groups"].items():
            print(f"{g:>6} {v['n']:>5} | " + " ".join(
                f"{v[m]:>10.3f}" if v[m] is not None else f"{'—':>10}" for m in METHODS))
        if name == "main":
            print("  各 seed（F高D高 vs F低D低；監督式）：")
            for sd in seeds:
                hh = a["groups"]["F高D高"]["per_seed"][sd]; ll = a["groups"]["F低D低"]["per_seed"][sd]
                fmt = lambda x: f"{x:.3f}" if x is not None else "—"
                print(f"    {sd}: {fmt(hh['supervised'])}（n={hh['n']}） vs {fmt(ll['supervised'])}（n={ll['n']}）"
                      f"；空間 {fmt(hh['spatial'])} vs {fmt(ll['spatial'])}")
        print()
    print(f"寫入 {path}")


if __name__ == "__main__":
    main()
