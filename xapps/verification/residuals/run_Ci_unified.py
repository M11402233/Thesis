#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_Ci_unified.py — C_i 實驗 E0–E8 之統一版（規格 docs/thesis/Ci_unified_spec.md v1）

與 S_i／H_i／xApp 統一：
  規則  = zt_kpm_xapp.verify_ci（嚴格相等）+ fuse 之 C_i 分支（L_C → R1_CI_VETO／R1_CI_PENDING）
  載入  = zt_kpm_xapp.TraceReplaySource（窗 = 實際秒）
  N_known = 參數（預設由資料推得；給 --ues 時須 = 7 × ues）
  注入時點 = 序列中點；後半段 = ≥ 中點之窗

模式：
  --mode unified（預設）：規格 v1 之定義
  --mode legacy        ：修訂前之注入點（僅供內建檢查 1；須搭配 D-C）

【內建檢查】（任一不符即停止、不寫檔）
  1. legacy 模式於 D-C 重現 Ci_experiment_results.json 與 Ci_extended_E6E8.json
  2. TraceReplaySource 之逐窗 IMSI 聯集 = 修訂前解析器
  3. 所有判定經 verify_ci／fuse；獨立以 len(union) != N_known 重算，逐窗相同
  4. N_known 於各 seed 相同；給 --ues 時 = 7 × ues
用法：
  python3 run_Ci_unified.py --data "~/oran-zt-kpm-verification/data/batchFinal_seeds/seed42*.txt" --mode legacy
  python3 run_Ci_unified.py --data "<D-28 之 DlE2RlcStats 檔案 glob>" --ues 4
"""
import os
import sys
import glob
import json
import argparse
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zt_kpm_xapp as X
import datasets as DS

OUT_DIR = DS.results_dir()
FAKE0 = 9001
NET_CASES = [(2, 2), (3, 3), (1, 1), (4, 4), (2, 1), (3, 2), (1, 2), (2, 3), (1, 0), (0, 1)]
DURATIONS = [1, 2, 3, 5]


# ---------------------------------------------------------------- 載入與規則
def load(path):
    """[(w, {cell: set(imsi)})]，經 TraceReplaySource"""
    return [(w, {c: set(u) for c, u in cells.items()}) for w, cells in X.TraceReplaySource(path).windows()]


def legacy_union(path):
    """修訂前 run_Ci_extended_E6E8.load 之逐窗聯集（檢查 2 用）"""
    occ = collections.defaultdict(set)
    with open(path) as fh:
        fh.readline()
        for line in fh:
            p = line.split("\t")
            if len(p) < 11:
                continue
            try:
                w = int(float(p[0])); int(p[2]); i = int(p[3])
            except ValueError:
                continue
            occ[w].add(i)
    return dict(occ)


def union(cells):
    u = set()
    for s in cells.values():
        u |= s
    return u


def judge(seq):
    """seq：逐窗 {cell: set}。回傳逐窗 (violated, rule_id or None)；經 xApp 之 verify_ci／fuse。"""
    out, run = [], 0
    for cells in seq:
        ci, run, _ = X.verify_ci({c: dict.fromkeys(s) for c, s in cells.items()}, run)
        if (ci == "violated") != (len(union(cells)) != X.N_KNOWN):       # 檢查 3
            raise SystemExit("✗ 檢查 3：verify_ci 與獨立重算不一致")
        if ci == "violated":
            _, rid = X.fuse(ci, run, "normal", "normal", "normal")
            out.append((True, rid))
        else:
            out.append((False, None))
    return out


# ---------------------------------------------------------------- 注入（作用於單窗）
def fab(cells, k, cell):
    c = {x: set(s) for x, s in cells.items()}
    c.setdefault(cell, set()).update(range(FAKE0, FAKE0 + k))
    return c


def drop_global(cells, k):
    """自所有 cell 移除當窗編號最小之 k 個真 IMSI"""
    real = sorted(i for i in union(cells) if i < 9000)[:k]
    return {x: s - set(real) for x, s in cells.items()}, len(real) == k


def replace(cells, add, rem, cell):
    c, ok = drop_global(cells, rem)
    return fab(c, add, cell), ok


# ---------------------------------------------------------------- 實驗
def run(data, mode, mm_cells, attacker):
    R = {}
    seeds = sorted(data)
    mid = {s: len(data[s]) // 2 for s in seeds}
    late = {s: list(range(mid[s], len(data[s]))) for s in seeds}

    def per_window(transform, idxs):
        """對每個 seed 之指定窗逐一施加 transform（單窗注入，不影響他窗），回傳 (偵測, 總數, 逐 seed 比例)"""
        det = tot = 0; ps = {}
        for s in seeds:
            d = t = 0
            for i in idxs[s]:
                cells = data[s][i][1]
                new = transform(cells)
                if new is None:
                    continue
                t += 1
                d += int(len(union(new)) != X.N_KNOWN)
                judge([new])                                   # 規則路徑（檢查 3）
            det += d; tot += t; ps[s] = d / t if t else None
        return {"detected": det, "total": tot, "rate": det / tot if tot else None, "per_seed": ps}

    allw = {s: list(range(len(data[s]))) for s in seeds}
    # E0
    clean = {s: judge([c for _, c in data[s]]) for s in seeds}
    ntot = collections.Counter(len(union(c)) for s in seeds for _, c in data[s])
    R["E0"] = {"windows": sum(ntot.values()), "N_total_distribution": dict(ntot),
               "violations": sum(v for s in seeds for v, _ in clean[s]),
               "clean_rejected": sum(r == "R1_CI_VETO" for s in seeds for _, r in clean[s])}
    # E1
    R["E1"] = {}
    for k in range(1, 7):
        r = per_window(lambda c, k=k: fab(c, k, attacker), late)
        delay_v, delay_r = [], []
        for s in seeds:
            seq = [c if i < mid[s] else fab(c, k, attacker) for i, (_, c) in enumerate(data[s])]
            j = judge(seq)
            fv = next((i - mid[s] for i in late[s] if j[i][0]), None)
            fr = next((i - mid[s] for i in late[s] if j[i][1] == "R1_CI_VETO"), None)
            delay_v.append(fv); delay_r.append(fr)
        r["delay_to_violation_s"] = delay_v; r["delay_to_rejected_s"] = delay_r
        R["E1"][k] = r
    # E2a 全域壓制
    R["E2a"] = {k: per_window(lambda c, k=k: (lambda x: x[0] if x[1] else None)(drop_global(c, k)), late)
                for k in range(1, 5)}
    # E3 守恆式替換
    R["E3"] = per_window(lambda c: (lambda x: x[0] if x[1] else None)(replace(c, 2, 2, attacker)), late)
    # E4
    R["E4"] = {}
    for name, a, b in (("early", 0, 1), ("mid", 1, 2), ("late", 2, 3)):
        idx = {s: list(range(a * len(data[s]) // 3, b * len(data[s]) // 3)) for s in seeds}
        R["E4"][name] = per_window(lambda c: fab(c, 3, attacker), idx)
    # E5
    R["E5"] = {"clean": per_window(lambda c: c, allw),
               "fab+1": per_window(lambda c: fab(c, 1, attacker), allw),
               "global-1": per_window(lambda c: (lambda x: x[0] if x[1] else None)(drop_global(c, 1)), allw),
               "replace": per_window(lambda c: (lambda x: x[0] if x[1] else None)(replace(c, 2, 2, attacker)), allw),
               "fab+3_late": per_window(lambda c: fab(c, 3, attacker), late)}
    # E6
    R["E6"] = {}
    for D in DURATIONS:
        esc = tot = 0; ps = {}
        for s in seeds:
            starts = [mid[s]] if mode == "legacy" else \
                [t for t in late[s] if t + D <= len(data[s]) and not clean[s][t - 1][0]]
            e = 0
            for t0 in starts:
                seq = [fab(c, 1, attacker) if t0 <= i < t0 + D else c for i, (_, c) in enumerate(data[s])]
                j = judge(seq)
                rej = any(j[i][1] == "R1_CI_VETO" for i in range(t0, len(seq)))
                e += int(not rej)
            esc += e; tot += len(starts); ps[s] = e / len(starts) if starts else None
        R["E6"][D] = {"escaped": esc, "trials": tot, "escape_rate": esc / tot if tot else None, "per_seed": ps,
                      "unit": "seed" if mode == "legacy" else "(seed, start second)"}
    # E7
    R["E7"] = []
    for add, rem in NET_CASES:
        r = per_window(lambda c, a=add, m=rem: (lambda x: x[0] if x[1] else None)(replace(c, a, m, attacker)), allw)
        R["E7"].append({"add": add, "remove": rem, "net": add - rem, **{k: r[k] for k in ("detected", "total", "rate")}})
    # E8
    dual = mmonly = lteonly = 0; per_cell = collections.defaultdict(list); field = []; cond_det = cond_tot = 0
    for s in seeds:
        for _, cells in data[s]:
            where = collections.defaultdict(set)
            for c, us in cells.items():
                for i in us:
                    where[i].add(c)
            for i, cs in where.items():
                if X.LTE_CELL in cs and cs - {X.LTE_CELL}:
                    dual += 1
                elif cs - {X.LTE_CELL}:
                    mmonly += 1
                else:
                    lteonly += 1
            for c in mm_cells:
                us = cells.get(c, set())
                per_cell[c].append(len(us))
                for i in us:                                # 單點抹除：僅自 cell c 移除 IMSI i
                    new = {x: (s2 - {i} if x == c else s2) for x, s2 in cells.items()}
                    cond_tot += 1; cond_det += int(len(union(new)) != X.N_KNOWN)
            field.append(sum(len(cells.get(c, set())) for c in mm_cells))
    n = dual + mmonly + lteonly
    R["E8"] = {"window_ue_pairs": n, "mmwave_only": mmonly, "dual_homed": dual, "lte_only": lteonly,
               "field_mean": sum(field) / len(field), "zero_attach_windows": sum(x == 0 for x in field),
               "total_windows": len(field),
               "per_cell": {c: {"mean": sum(v) / len(v), "max": max(v), "idle_ratio": sum(x == 0 for x in v) / len(v)}
                            for c, v in sorted(per_cell.items())},
               "single_odu_erasure_conditional_detection": {"detected": cond_det, "total": cond_tot}}
    return R


# ---------------------------------------------------------------- 檢查 1（legacy）
def check_legacy(R):
    bad = []
    o = json.load(open(os.path.join(OUT_DIR, "Ci_experiment_results.json"), encoding="utf-8"))
    e = json.load(open(os.path.join(OUT_DIR, "Ci_extended_E6E8.json"), encoding="utf-8"))
    if R["E0"]["windows"] != o["E0_baseline"]["total_windows"] or set(R["E0"]["N_total_distribution"]) != {7}:
        bad.append("E0")
    for row in o["E1_fabrication"]:
        if (row["C_i_mean"] < 1) != (R["E1"][row["amount"]]["rate"] == 1.0):
            bad.append(f"E1 k={row['amount']}")
    for row in o["E2_depletion"]:
        if (row["C_i_mean"] < 1) != (R["E2a"][row["drop"]]["rate"] == 1.0):
            bad.append(f"E2 k={row['drop']}")
    if (o["E3_collusion"]["collusion_C_i"] == 1.0) != (R["E3"]["detected"] == 0):
        bad.append("E3")
    for k, v in o["E4_timing"].items():
        if (v < 1) != (R["E4"][k]["rate"] == 1.0):
            bad.append(f"E4 {k}")
    p = o["E5_protection"]
    if (R["E5"]["fab+3_late"]["total"], R["E5"]["fab+3_late"]["rate"]) != (p["attack_windows"], p["accuracy_with_verify"]):
        bad.append("E5")
    for row in e["E6_persistence"]:
        r = R["E6"][row["duration"]]
        if (r["escaped"], r["trials"]) != (row["escaped"], row["trials"]):
            bad.append(f"E6 D={row['duration']}")
    for a, b in zip(e["E7_imprecise_conservation"], R["E7"]):
        if (a["add"], a["remove"], a["detected"], a["total"]) != (b["add"], b["remove"], b["detected"], b["total"]):
            bad.append(f"E7 {a['add']}/{a['remove']}")
    e8o, e8n = e["E8_attack_surface"], R["E8"]
    for k in ("window_ue_pairs", "mmwave_only", "dual_homed", "lte_only", "zero_attach_windows", "total_windows"):
        if e8o[k] != e8n[k]:
            bad.append(f"E8 {k}")
    if abs(e8o["field_mean"] - e8n["field_mean"]) > 1e-12:
        bad.append("E8 field_mean")
    for c, v in e8o["per_cell"].items():
        w = e8n["per_cell"].get(int(c))
        if w is None or abs(v["mean"] - w["mean"]) > 1e-12 or v["max"] != w["max"] or abs(v["idle_ratio"] - w["idle_ratio"]) > 1e-12:
            bad.append(f"E8 cell {c}")
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=None, help="RLC 檔案之 glob（DlE2RlcStats 格式）；預設依 ZT_DATASET")
    ap.add_argument("--mode", choices=("unified", "legacy"), default="unified")
    ap.add_argument("--n-known", type=int, default=None)
    ap.add_argument("--ues", type=int, default=None, help="預設依 ZT_DATASET（未給 --data 時）")
    ap.add_argument("--tag", default=None, help="輸出檔名標記")
    ap.add_argument("--out-dir", default=OUT_DIR)
    args = ap.parse_args()
    if args.data is None:
        files = DS.files()
        args.ues = DS.CFG["ues"] if args.ues is None else args.ues
        if args.n_known is None and args.ues is None:
            args.n_known = DS.N_KNOWN                      # 非 7 倍數之資料集（d30）以登錄之 N_known 檢查
    else:
        files = sorted(glob.glob(os.path.expanduser(args.data)))
    if not files:
        raise SystemExit(f"找不到資料：{args.data}")
    data, nk = {}, set()
    for f in files:
        s = os.path.basename(f).split("seed")[-1].split(".")[0].split("_")[0]
        data[s] = load(f)
        lu = legacy_union(f)                                                     # 檢查 2
        if [w for w, _ in data[s]] != sorted(lu) or any(union(c) != lu[w] for w, c in data[s]):
            raise SystemExit(f"✗ 檢查 2：{os.path.basename(f)} 之逐窗聯集與修訂前解析器不同")
        nk.add(len({i for _, c in data[s] for i in union(c) if i < 9000}))
    if len(nk) != 1:
        raise SystemExit(f"✗ 檢查 4：各 seed 推得之 N_known 不同：{sorted(nk)}")
    n_known = args.n_known if args.n_known is not None else nk.pop()
    if args.ues is not None and n_known != 7 * args.ues:
        raise SystemExit(f"✗ 檢查 4：N_known = {n_known} ≠ 7 × ues = {7 * args.ues}")
    X.N_KNOWN = n_known
    mm_cells = sorted({c for s in data for _, cells in data[s] for c in cells if c != X.LTE_CELL})
    attacker = mm_cells[0]
    print(f"載入 {len(files)} 個 seed；N_known = {n_known}；L_C = {X.L_C}；mmWave cell = {mm_cells}；"
          f"灌水注入 cell = {attacker}；模式 = {args.mode}")
    print("── 檢查 2：逐窗聯集與修訂前解析器相同 ✓；檢查 4：N_known 一致 ✓")
    R = run(data, args.mode, mm_cells, attacker)
    print("── 檢查 3：所有判定經 verify_ci／fuse，與獨立重算逐窗相同 ✓")
    if args.mode == "legacy":
        bad = check_legacy(R)
        if bad:
            raise SystemExit(f"✗ 檢查 1：legacy 未重現修訂前輸出：{bad}")
        print("── 檢查 1：legacy 模式重現 Ci_experiment_results.json 與 Ci_extended_E6E8.json ✓")
    band_tol = int(n_known - n_known * 0.95 + 1e-9)
    R["meta"] = {"spec": "docs/thesis/Ci_unified_spec.md v1", "mode": args.mode, "files": [os.path.basename(f) for f in files],
                 "N_known": n_known, "L_C": X.L_C, "mm_cells": mm_cells, "attacker_cell": attacker,
                 "tolerance_band_5pct_would_tolerate_missing_UEs": band_tol}
    # ---- 報表 ----
    f_ = lambda r: f"{r['detected']}/{r['total']}"
    print(f"\nE0 乾淨：{R['E0']['windows']} 窗；N_total 分布 {R['E0']['N_total_distribution']}；"
          f"違反 {R['E0']['violations']}；rejected {R['E0']['clean_rejected']}")
    print("E1 灌水 +k：" + "；".join(f"+{k} {f_(v)}" for k, v in R["E1"].items())
          + f"；延遲(違反/rejected) = {R['E1'][1]['delay_to_violation_s']}/{R['E1'][1]['delay_to_rejected_s']}")
    print("E2a 全域壓制 −k：" + "；".join(f"−{k} {f_(v)}" for k, v in R["E2a"].items()))
    print(f"E3 守恆式替換：{f_(R['E3'])}")
    print("E4：" + "；".join(f"{k} {f_(v)}" for k, v in R["E4"].items()))
    print("E5：" + "；".join(f"{k} {f_(v)}" for k, v in R["E5"].items()))
    print("E6：" + "；".join(f"D={D} 未升級 {v['escaped']}/{v['trials']}" for D, v in R["E6"].items()))
    print("E7：" + "；".join(f"+{r['add']}/−{r['remove']} {r['detected']}/{r['total']}" for r in R["E7"]))
    e8 = R["E8"]
    print(f"E8：(窗,UE) {e8['window_ue_pairs']}；mmWave-only {e8['mmwave_only']}；雙掛 {e8['dual_homed']}；"
          f"LTE-only {e8['lte_only']}；每窗 mmWave UE 平均 {e8['field_mean']:.2f}；無目標窗 {e8['zero_attach_windows']}/{e8['total_windows']}；"
          f"單點抹除條件偵測 {e8['single_odu_erasure_conditional_detection']}")
    for c, v in e8["per_cell"].items():
        print(f"    cell {c}: mean {v['mean']:.2f}  max {v['max']}  無目標 {v['idle_ratio']:.1%}")
    print(f"（揭露：5 % 容忍帶於 N = {n_known} 可容忍缺漏 {band_tol} 個 UE；本腳本採嚴格相等）")
    tag = args.tag or args.mode
    path = os.path.join(args.out_dir, f"Ci_unified_{tag}.json")
    json.dump(R, open(path, "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=str)
    print(f"\n寫入 {path}")


if __name__ == "__main__":
    main()
