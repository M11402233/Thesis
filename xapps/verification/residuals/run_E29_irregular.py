#!/usr/bin/env python3
"""
run_E29_irregular.py — E29：一般攻擊者（規律／不規則）下之 Rule 欄評估（規格 docs/thesis/E29_irregular_attack_spec.md）

圖 1a（調低）／1b（調高）之 Rule 欄：B1 = 規則版 L2、嚴重度序（須 ZT_FUSION_ORDER=severity）、uebound。
Rule + DRL 欄不在本腳本（須 D-30P 上之完整 PSRO，使用者 2026-11-19 決定）。

指標（每列）：
  DR_flag      被竄改之 (node, s) 判為 low-trust 或 rejected 之比例
  DR_rej       同上，只算 rejected
  gain_none    攻擊者得利，無驗證（C_none）    down：lured／機會；up：repelled／機會
  gain_strict  攻擊者得利，嚴格准入（C_strict）
  regret_*     t ≥ t0 且真值 ≥ 2 候選之窗之平均 regret（ms）
  attacked_share  t ≥ t0 之 (攻擊 cell, s) 中實際被竄改之比例
  lured：steering 選中「當秒正在竄改之 cell」且其非真值最佳；機會 = 某竄改中 cell 在場且非最佳
  repelled：真值最佳 cell 當秒正在竄改，steering 未選它；機會 = 真值最佳 cell 當秒正在竄改
另報乾淨資料之 flag／rej 比例（同一 anchor、同一 seed），兩欄須於相同乾淨誤拒下比較。

--dev：開發試跑，輸出標 NOT_CITABLE。正式結果僅於 D-30P 驗收後產生。
"""
import os, sys, json, glob, time, argparse, collections
import numpy as np
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zt_kpm_xapp as X
import datasets as DS
import attack_generators as AG
from run_E10_D1_policy_ablation import load_windows
from run_RQ3_decision_replay import annotate, admitted, true_delays, decide

X.FUSION_MODE = "bound"
FLAG = {"low-trust", "rejected"}


def rows_def(n_rng):
    R = []
    for fam, regs in (("down", [("Step x0.6", "step", 0.6), ("Step x0.8", "step", 0.8),
                                ("Drift down 1%/s", "drift_down", 0.01), ("Drift down 2%/s", "drift_down", 0.02)]),
                      ("up", [("Step x1.2", "step", 1.2), ("Step x1.5", "step", 1.5),
                              ("Drift up 1%/s", "drift_up", 0.01)])):
        for name, kind, p in regs:
            R.append((fam, name, kind, p, [None]))
        R.append((fam, f"Irregular {fam} 1 node", "irr", ("single", None), list(range(n_rng))))
        for ma in AG.MEAN_ARRIVALS:
            R.append((fam, f"Irregular {fam} multi {ma}s", "irr", ("multi", ma), list(range(n_rng))))
    return R


def make_gen(kind, p, sd, cell, r, fam, T):
    if kind == "step":
        return AG.step(cell, p, T)
    if kind == "drift_down":
        return AG.drift_down(cell, p, T)
    if kind == "drift_up":
        return AG.drift_up(cell, p, T)
    mode, ma = p
    return AG.irregular(sd, cell, r, fam, mode, T, **({"mean_arrival": ma} if ma else {}))


def new_acc():
    return {"att": 0, "flag": 0, "rej": 0, "att_possible": 0,
            "opp_none": 0, "gain_none": 0, "opp_strict": 0, "gain_strict": 0,
            "reg_none": [], "reg_strict": [], "eps": 0}


def eval_seed(args):
    test, files, n_rng = args
    anchor = X.TrustAnchor([f for f in files if f != test])
    base = load_windows(test)
    T = len(base)
    sd = DS.seed_of(test)
    td = true_delays(base)
    cells_all = sorted({c for d in td for c in d})
    out = collections.defaultdict(new_acc)
    # 乾淨
    cl = annotate(base, anchor, "uebound")
    c = out[("clean", "clean")]
    for k, d in cl.items():
        for j, a in d.items():
            c["att"] += 1; c["flag"] += a["decision"] in FLAG; c["rej"] += a["decision"] == "rejected"
    for fam, name, kind, p, rs in rows_def(n_rng):
        for cell in cells_all:
            for r in rs:
                g = make_gen(kind, p, sd, cell, r, fam, T)
                S = g["schedule"]; t0 = g["t0"]
                mod = AG.apply(base, g)
                rep = true_delays(mod)
                anns = annotate(mod, anchor, "uebound")
                a = out[(fam, name)]; a["eps"] += 1
                for k in range(t0, T):
                    on = {j for j, m in S.items() if m[k] != 1.0 and j in rep[k]}
                    for j, m in S.items():
                        if j in td[k]:
                            a["att_possible"] += 1
                    for j in on:
                        dec = anns.get(k, {}).get(j)
                        if dec is None:
                            continue
                        a["att"] += 1; a["flag"] += dec["decision"] in FLAG; a["rej"] += dec["decision"] == "rejected"
                    truth = td[k]
                    if len(truth) < 2:
                        continue
                    opt = min(truth, key=lambda x: truth[x])
                    for cons, tag in (("C_none", "none"), ("C_strict", "strict")):
                        adm = admitted(cons, anns.get(k, {}), rep[k])
                        ch = decide(rep[k], adm)
                        if ch is not None:
                            a[f"reg_{tag}"].append(truth.get(ch, np.nan) - truth[opt])
                        if fam == "down":
                            if any(j in truth and j != opt for j in on):
                                a[f"opp_{tag}"] += 1
                                a[f"gain_{tag}"] += ch in on and ch != opt
                        else:
                            if opt in on:
                                a[f"opp_{tag}"] += 1
                                a[f"gain_{tag}"] += ch != opt
    return sd, {f"{k[0]}|{k[1]}": v for k, v in out.items()}


def summarize(per_seed):
    keys = sorted({k for d in per_seed.values() for k in d})
    res = {}
    for key in keys:
        tot = new_acc(); seeds = {}
        for sd, d in per_seed.items():
            v = d.get(key)
            if not v:
                continue
            for f in tot:
                tot[f] = tot[f] + v[f]
            seeds[sd] = v["flag"] / v["att"] if v["att"] else None
        rg = lambda L: float(np.nanmean(L)) if L else None
        res[key] = {"episodes": tot["eps"], "attacked_node_s": tot["att"],
                    "DR_flag": tot["flag"] / tot["att"] if tot["att"] else None,
                    "DR_rej": tot["rej"] / tot["att"] if tot["att"] else None,
                    "DR_flag_seed_range": [min(x for x in seeds.values() if x is not None),
                                           max(x for x in seeds.values() if x is not None)] if seeds else None,
                    "gain_none": tot["gain_none"] / tot["opp_none"] if tot["opp_none"] else None,
                    "gain_strict": tot["gain_strict"] / tot["opp_strict"] if tot["opp_strict"] else None,
                    "regret_none_ms": rg(tot["reg_none"]), "regret_strict_ms": rg(tot["reg_strict"]),
                    "attacked_share": tot["att"] / tot["att_possible"] if tot["att_possible"] else None}
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", action="store_true", help="開發試跑（不得引用）")
    ap.add_argument("--n-rng", type=int, default=AG.N_RNG)
    ap.add_argument("--seeds", default=None, help="逗號分隔，只跑部分 seed（計時用）")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()
    if X.FUSION_ORDER != "severity":
        sys.exit("須 ZT_FUSION_ORDER=severity（B1）")
    if not a.dev:
        sys.exit("正式版僅於 D-30P 驗收後執行；目前只允許 --dev")
    files = sorted(glob.glob(os.path.join(DS.DATA_DIR, DS.PATTERN)))
    run = [f for f in files if (a.seeds is None or str(DS.seed_of(f)) in a.seeds.split(","))]
    os.makedirs(a.out_dir, exist_ok=True)
    t = time.time()
    with Pool(a.workers) as P:
        per = dict(P.map(eval_seed, [(f, files, a.n_rng) for f in run]))
    res = summarize(per)
    meta = {"NOT_CITABLE": a.dev, "dataset": os.environ.get("ZT_DATASET"),
            "delay_source": os.environ.get("ZT_DELAY_SOURCE", "cumulative"),
            "fusion_order": X.FUSION_ORDER, "binding": "uebound", "n_rng": a.n_rng,
            "seeds": [DS.seed_of(f) for f in run], "wall_s": round(time.time() - t, 1)}
    json.dump({"meta": meta, "rows": res, "per_seed": per}, open(os.path.join(a.out_dir, "E29_rule.json"), "w"),
              ensure_ascii=False, indent=1, default=float)
    print(json.dumps(meta, ensure_ascii=False))
    for k, v in res.items():
        f = lambda x: "—" if x is None else f"{x:.3f}"
        print(f"{k:32s} eps {v['episodes']:4d}  DR {f(v['DR_flag'])}  rej {f(v['DR_rej'])}  "
              f"gain none {f(v['gain_none'])} strict {f(v['gain_strict'])}  share {f(v['attacked_share'])}")


if __name__ == "__main__":
    main()
