#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""train_symmetric_abr.py — 對稱 A-BR：對每個規則基線偵測端訓練攻擊者最佳回應
（docs/thesis/phase2_percell_spec_v0.md §5.1、§9.2 Q-P8 (b)；2026-11-22）。

與 DRL 之 A-BR **完全相同之程序**：直接呼叫 psro._train_job（PPO、至多 300k 步、每 50k 步以訓練 seed 驗證保留最佳；
O-full 與 O-outcome 各一；8 fold；訓練 seed 0–2），只把對手換成規則偵測端（混合 = 100 % 該偵測端）。程式共用、不複製（§5.1 檢查 (i)）。
不修改 psro.py：B2 以包裝載入函式（見 _load_ext）接入；PSRO 之任何輸出不受影響（§5.1 檢查 (iii)）。

偵測端（8 個不同者；規格之 9 個中 B3_tau2_3 之 τ_H = (2, 3) = 凍結值 = D0，同一偵測端，不重複訓練）：
  D0（B1）、B2_L{2,3,5,10}（E12 持續窗）、B3_tau{3_4, 4_5, 6_7}（τ_H^warn／reject；改 SeedData 之 D1 證據，須於工作行程初始化時設定）。
規模：8 偵測端 × 2 層級 × 3 seed × 8 fold = 384 個最佳回應（規格 §5.1 估每 48 個約 4–6 h → 約 32–48 h）。

種子規則（寫定於執行前；不與 PSRO（輪數 ≤ 12：100000·t + 1000·r + 10·f + {0,1}）及 E19 eval_final（r = 7）重複）：
  seed = 100000·t + 20000 + 100·i_det + 10·f + 1        （i_det = DETS 之索引 0–7；f ≤ 7 → 個位十位不跨偵測端）

用法（~/venvs/drl；第二階段）：
  ZT_DATASET=d30p1 ZT_DELAY_SOURCE=percell ZT_FUSION_ORDER=severity python3 train_symmetric_abr.py --det D0 --workers 12
  python3 train_symmetric_abr.py --selftest                       # 靜態檢查（不訓練）
  … --smoke --out <暫存目錄>                                       # 管線冒煙（fold 0、2048 步）；結果不得引用
"""
import argparse
import json
import multiprocessing as mp
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "residuals"))

DETS = [("D0", "floor", None, None), ("B2_L2", "b2", 2, None), ("B2_L3", "b2", 3, None), ("B2_L5", "b2", 5, None),
        ("B2_L10", "b2", 10, None), ("B3_tau3_4", "floor", None, (3.0, 4.0)), ("B3_tau4_5", "floor", None, (4.0, 5.0)),
        ("B3_tau6_7", "floor", None, (6.0, 7.0))]
ALIAS = {"B3_tau2_3": "D0"}                           # τ_H = (2, 3) = 凍結值 → 與 D0 同一偵測端
LEVELS, TSEEDS, FOLDS = ("O-full", "O-outcome"), (0, 1, 2), list(range(8))


def seed_of(t, i_det, f):
    return 100000 * t + 20000 + 100 * i_det + 10 * f + 1


def job_list(out_root, br_max, br_every, dets=None, levels=LEVELS, tseeds=TSEEDS, folds=FOLDS):
    jobs = []
    for i, (name, kind, L, tau) in enumerate(DETS):
        if dets and name not in dets:
            continue
        desc = {"name": name, "kind": kind}
        if L:
            desc["L_S"] = L
        for lv in levels:
            for t in tseeds:
                for f in folds:
                    path = os.path.join(out_root, name, lv, f"t{t}", f"ABR_f{f}")
                    jobs.append(("atk", f, [desc], [1.0], lv, br_max, br_every, seed_of(t, i, f), path))
    return jobs


def _make_init(tau):
    def _init():
        import psro as PS
        PS._init_worker()
        if tau:                                                  # B3：只影響 SeedData 建立時之 D1 證據（同 eval_final）
            PS._W["G"].X.TAU_H_WARN, PS._W["G"].X.TAU_H_REJECT = tau
        _orig = PS._load

        def _load_ext(strat, fold, role):
            if strat.get("kind") == "b2":
                key = (strat["name"], role)
                if key not in PS._W["models"]:
                    PS._W["models"][key] = _B2(strat["L_S"], strat["name"])
                return PS._W["models"][key]
            return _orig(strat, fold, role)
        PS._load = _load_ext
    return _init


class _B2:
    """E12 R2_SI_PERSIST（與 eval_final.B2Persist 同一定義；連續 L_S 個實際秒 S_i violated 且下限規則為 R2_SI_ALONE → rejected）"""

    def __init__(self, L, name):
        self.L, self.name = L, name

    def __call__(self, ep, j):
        import psro as PS
        G = PS._W["G"]
        base = G.det_floor_policy(ep, j)
        if ep.floor[j][1] != "R2_SI_ALONE" or ep.info[j]["si"] != "violated":
            return base
        c, k = 1, ep.k - 1
        while c < self.L:
            rec = ep.hist[j].get(k)
            if rec is None or not rec[0] or not rec[1] > 1.0:
                break
            c, k = c + 1, k - 1
        return 2 if c >= self.L else base


def default_out():
    import psro as PS
    return os.path.join(os.path.dirname(PS.OUT_BASE), "symabr")


def selftest():
    jobs = job_list("/x", 300000, 50000)
    chk = []
    chk.append(("384 個最佳回應", len(jobs) == 8 * 2 * 3 * 8))
    seeds = [j[7] for j in jobs]
    per = {lv: [j[7] for j in jobs if j[4] == lv] for lv in LEVELS}
    chk.append(("同一層級內種子兩兩不同", all(len(set(v)) == len(v) for v in per.values())))
    chk.append(("兩層級共用同一套種子規則（同 PSRO／eval_final）", set(per["O-full"]) == set(per["O-outcome"])))
    chk.append(("路徑兩兩不同", len({j[-1] for j in jobs}) == len(jobs)))
    psro_max = max(100000 * t + 1000 * r + 10 * f + b for t in TSEEDS for r in range(0, 13) for f in FOLDS for b in (0, 1))
    chk.append(("不與 PSRO 種子（輪數 ≤ 12）重複", all(s % 100000 >= 20000 for s in seeds) and
                not set(seeds) & {100000 * t + 1000 * r + 10 * f + b for t in TSEEDS for r in range(0, 13) for f in FOLDS for b in (0, 1)}))
    chk.append(("不與 eval_final（r = 7）重複", not set(seeds) & {100000 * t + 7000 + 10 * f + 1 for t in TSEEDS for f in FOLDS}))
    chk.append(("對手 = 單一規則偵測端、σ = 1", all(len(j[2]) == 1 and j[3] == [1.0] for j in jobs)))
    chk.append(("BR 預算與 DRL A-BR 相同（300k／50k）", all(j[5] == 300000 and j[6] == 50000 for j in jobs)))
    chk.append(("B3_tau2_3 對應 D0", ALIAS["B3_tau2_3"] == "D0" and "B3_tau2_3" not in [d[0] for d in DETS]))
    chk.append(("每偵測端 48 個", all(sum(1 for j in jobs if j[2][0]["name"] == d[0]) == 48 for d in DETS)))
    bad = [n for n, ok in chk if not ok]
    for n, ok in chk:
        print(("✓ " if ok else "✗ ") + n)
    print("selftest", "通過" if not bad else f"失敗 {bad}")
    return 0 if not bad else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--det", help="偵測端名稱（逗號分隔）或 all")
    ap.add_argument("--level", choices=list(LEVELS))
    ap.add_argument("--train-seed", type=int, choices=list(TSEEDS))
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--out")
    ap.add_argument("--smoke", action="store_true", help="冒煙：fold 0、每個偵測端 2048 步；須指定 --out；結果不得引用")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    if not a.det:
        raise SystemExit("須 --det")
    import psro as PS
    names = [d[0] for d in DETS] if a.det == "all" else [ALIAS.get(x, x) for x in a.det.split(",")]
    unknown = [n for n in names if n not in [d[0] for d in DETS]]
    if unknown:
        raise SystemExit(f"未知偵測端 {unknown}")
    if a.smoke and not a.out:
        raise SystemExit("--smoke 須指定 --out（暫存目錄），不得寫入結果目錄")
    out = a.out or default_out()
    br_max, br_every = (2048, 2048) if a.smoke else (PS.BR_MAX, PS.BR_EVERY)
    jobs = job_list(out, br_max, br_every, set(names), [a.level] if a.level else LEVELS,
                    [a.train_seed] if a.train_seed is not None else TSEEDS, [0] if a.smoke else FOLDS)
    os.makedirs(out, exist_ok=True)
    meta = {"spec": "phase2_percell_spec_v0.md §5.1", "dataset": os.environ.get("ZT_DATASET"), "delay_source": os.environ.get("ZT_DELAY_SOURCE"),
            "br_max": br_max, "br_every": br_every, "smoke": a.smoke, "seed_rule": "100000*t+20000+100*i_det+10*f+1",
            "dets": [list(d) for d in DETS], "alias": ALIAS, "time": time.strftime("%F %T")}
    json.dump(meta, open(os.path.join(out, f"meta_{'smoke' if a.smoke else 'main'}.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    t0 = time.time()
    for name in names:                                            # 每偵測端獨立之 pool（B3 之 τ 於行程初始化設定；T0Cache 以偵測端名稱為鍵，故 maxtasksperchild=1）
        tau = next(d[3] for d in DETS if d[0] == name)
        todo = [j for j in jobs if j[2][0]["name"] == name and not os.path.exists(j[-1] + ".zip")]
        print(f"{name}：{sum(1 for j in jobs if j[2][0]['name'] == name)} 個（尚待 {len(todo)}）", flush=True)
        if not todo:
            continue
        with mp.Pool(a.workers, initializer=_make_init(tau), maxtasksperchild=1) as p:
            for i, path in enumerate(p.imap_unordered(PS._train_job, todo, chunksize=1)):
                print(f"  完成 {os.path.relpath(path, out)}（{i + 1}／{len(todo)}，{time.time() - t0:.0f} s）", flush=True)
    print("完成。")


if __name__ == "__main__":
    main()
