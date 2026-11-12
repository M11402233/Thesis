# -*- coding: utf-8 -*-
"""eval_posthoc.py — E19 最終評估之事後補充（規格 docs/thesis/E19_eval_final_spec.md §13，2026-11-12）。

  13.1  TPR_nt 前緣改以 clean_nontrusted 為橫軸重算（§12.3 原結果保留）
  13.2  事後新增基線 B3s（較嚴之 D1 門檻）；檢查 B3s-1：與 run_E10.run_policy（E14 所用之獨立實作）逐 seed 相同
  13.3  TPR_rej 無區分力之原因：H1–H4 之量測（含反事實策略 MaxEsc-SI，僅供診斷）

重用 eval_final 之 Runner／_job／mix／frontier_judge；既有 eval_final.json、pairs.json 只讀不寫。
用法：ZT_DATASET=d30 ZT_FUSION_ORDER=severity python eval_posthoc.py --workers 12
"""
import os
import sys
import json
import time
import argparse
import collections
import multiprocessing as mp
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import eval_final as EF                                      # noqa: E402

POUT = os.path.join(EF.OUT, "posthoc")
SPEC = "docs/thesis/E19_eval_final_spec.md §13"
B3S_TAU = [(1.75, 2.75), (1.5, 2.5), (1.0, 2.0)]


# ----------------------------------------------------------------------------
# 反事實策略 MaxEsc-SI（§13.3 H4）：待決節點只要 S_i violated 即判 rejected
class MaxEscSI:
    def __init__(self, name):
        self.name = name

    def __call__(self, ep, j):
        G = EF._W["G"]
        return 2 if ep.info[j]["si"] == "violated" else G.det_floor_policy(ep, j)


_orig_get = EF._get


def _get(s, fold):
    if s["kind"] == "maxesc":
        key = (s["id"], fold)
        if key not in EF._W["models"]:
            EF._W["models"][key] = MaxEscSI(s["id"])
        return EF._W["models"][key]
    return _orig_get(s, fold)


EF._get = _get                                               # 工作行程以 fork 繼承


def _diag_job(args):
    """(det, atk, fold) → 計數與竄改 (節點, 秒) 之逐筆診斷（與 eval_final._job 同一執行路徑）"""
    dS, aS, fold = args
    G, E, ds = EF._W["G"], EF._W["E"], EF._W["ds"]
    sd = ds.get(ds.files[fold])
    det, atk = EF._get(dS, fold), EF._get(aS, fold)
    c = collections.Counter()
    ratios_viol, ratios = [], []
    for cell in sd.cells_all:
        ep = EF._W["cache"].get(sd, cell, det, E.new_episode)
        G.run_episode(ep, det, atk)
        for k, v in ep.stats.items():
            c["tot|" + k] += v
        tam = {r["k"] for r in ep.atk_log if r["present"] and r["reported"] != r["true"]}
        for (k, j), (dec, rule, src) in ep.final.items():
            is_tam = j == ep.atk and k in tam
            grp = "tam" if is_tam else "clean"
            if src == "drl":                                 # H1：偵測端之升級
                c[f"esc|{grp}|{dec}"] += 1
            elif dec in ("trusted", "low-trust"):            # 待決但未升級
                c[f"keep|{grp}|{dec}"] += 1
            if is_tam:
                rec = ep.hist[j].get(k)
                viol = rec is not None and rec[0] and rec[1] > 1.0
                c["tam|n"] += 1
                c[f"tam|si_viol"] += viol
                if dec == "rejected":                        # H2：來源拆分
                    c[f"tamrej|{src}"] += 1
                    if src == "rule":
                        c[f"tamrej_rule|{rule}"] += 1
                r = next(x for x in ep.atk_log if x["k"] == k)
                ratios.append(r["reported"] / r["true"])
                if viol:
                    ratios_viol.append(r["reported"] / r["true"])
    return {"c": dict(c), "ratios": ratios, "seed": sd.seed}


def _policy_check(args):
    """B3s-1：以 run_E10.run_policy（E14 之實作）計算 τ 下逐 seed (n, trusted, rejected)"""
    tau, = args
    import game_core as G
    import run_E10_D1_policy_ablation as E10
    X = G.X
    X.TAU_H_WARN, X.TAU_H_REJECT = tau
    files = G.seed_files()
    out = {}
    for test in files:
        anchor = X.TrustAnchor([f for f in files if f != test])
        ann, _ = E10.run_policy(E10.load_windows(test), anchor, "uebound", 1)
        cnt = collections.Counter(a["decision"] for a in ann)
        out[str(G.DS.seed_of(test))] = [len(ann), cnt.get("trusted", 0), cnt.get("rejected", 0)]
    return tau, out


# ----------------------------------------------------------------------------
def worst_by(res, key, sD, aset, tpr, dkey):
    ms = {a: EF.mix(res, sD, {a: 1.0}, key) for a in aset}
    a_t = min(aset, key=lambda a: (ms[a][tpr], a))
    a_d = max(aset, key=lambda a: (ms[a][dkey]["median"], a))
    return {"by_TPR": {"attacker": a_t, **ms[a_t]}, "by_delay": {"attacker": a_d, **ms[a_d]}}


def judge_all(res, key, runs, A, base_ids, xkey, tpr, dkey):
    scripted = [a for a in A if a.startswith("A0_")]
    pool = [a for a in A if not a.endswith(":ABR")]
    sets = {"A-script": scripted, "A-pool": pool}

    def point(sD, sname, r):
        if sname in sets:
            w = worst_by(res, key, sD, sets[sname], tpr, dkey)
            return w["by_TPR"][tpr], w["by_delay"][dkey]["median"], w["by_TPR"]["attacker"]
        sA = runs[r]["sigma_A"] if sname == "A-eq" else {f"{r}:ABR": 1.0}
        m = EF.mix(res, sD, sA, key)
        return m[tpr], m[dkey]["median"], None

    out, summ = {}, {}
    for r in runs:
        sD = runs[r]["sigma_D"]
        x = EF.mix(res, sD, None, key)[xkey]
        J = {}
        for sname in ("A-script", "A-pool", "A-eq", "A-BR"):
            T, d, att = point(sD, sname, r)
            bp = []
            for b in base_ids:
                bt, bd, _ = point({b: 1.0}, sname, r)
                bp.append((b, EF.mix(res, {b: 1.0}, None, key)[xkey], bt, bd))
            v, why = EF.frontier_judge((x, T, d), bp)
            J[sname] = {"verdict": v, "why": why, "DRL": {"x": x, "TPR": T, "d_median": d, "worst_attacker": att},
                        "baselines": [{"id": b, "x": bx, "TPR": bt, "d_median": bd} for b, bx, bt, bd in bp]}
        out[r] = J
    for lv in ("O-full", "O-outcome"):
        for sname in ("A-script", "A-pool", "A-eq", "A-BR"):
            vs = [out[EF.rid(lv, t)][sname]["verdict"] for t in (0, 1, 2)]
            n = vs.count("優於")
            summ[f"{lv}|{sname}"] = {"verdicts": vs, "n_better": n,
                                     "conclusion": "優於" if n == 3 else ("多數情形優於" if n == 2 else "未優於")}
    return out, summ


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=12)
    a = ap.parse_args()
    if os.environ.get("ZT_DATASET") != "d30" or os.environ.get("ZT_FUSION_ORDER") != "severity":
        raise SystemExit("須在 ZT_DATASET=d30 與 ZT_FUSION_ORDER=severity 下執行")
    os.makedirs(POUT, exist_ok=True)
    dets, atks, runs = EF.strategies()
    base_orig = ["D0"] + [f"B2_L{L}" for L in EF.B2_LS] + [i for i in dets if i.startswith("B3_")]
    for tau in B3S_TAU:
        i = f"B3s_tau{tau[0]:g}_{tau[1]:g}"
        dets[i] = {"id": i, "kind": "floor", "tau": list(tau)}
    dets["MaxEsc-SI"] = {"id": "MaxEsc-SI", "kind": "maxesc", "tau": list(EF.FROZEN_TAU)}
    b3s = [f"B3s_tau{t[0]:g}_{t[1]:g}" for t in B3S_TAU]
    A = sorted(atks)
    log, ok = [], True

    def rep(name, cond, msg):
        nonlocal ok
        print(f"{'✓' if cond else '✗'} {name}：{msg}", flush=True)
        log.append({"check": name, "passed": bool(cond), "msg": msg}); ok = ok and bool(cond)

    # ---- 13.2：B3s 評估（全部攻擊者 + 乾淨），快取於 posthoc/pairs_posthoc.json ----
    R = EF.Runner(a.workers, os.path.join(POUT, "pairs_posthoc.json"))
    pairs = [(dets[b], atks[x], None) for b in b3s for x in A] + [(dets[b], None, None) for b in b3s]
    t = time.time()
    res_new = R.run(pairs)
    print(f"B3s：{len(pairs)} 組（{time.time() - t:.0f} s）", flush=True)
    # ---- B3s-1：與 run_policy 逐 seed 相同；(2,3) 為呼叫方式之對照（須等於 E14 輸出）----
    e14 = json.load(open(os.path.join(EF.SEV, "E14_D1_sensitivity.json"), encoding="utf-8"))["results"]
    with mp.Pool(4) as p:
        pol = dict(p.map(_policy_check, [((2.0, 3.0),)] + [(tau,) for tau in B3S_TAU]))
    ref23 = {s: [v["n"], v["trusted"], v["rejected"]] for s, v in e14["tau2_3|L1"]["per_seed"].items()}
    rep("B3s-1 對照", pol[(2.0, 3.0)] == ref23, "run_policy 於 τ=(2,3) 重現 E14 逐 seed (n, trusted, rejected)")
    for b, tau in zip(b3s, B3S_TAU):
        ps = res_new[EF.Runner.key(dets[b], None, None)]["per_seed"]
        got = {s: [v["clean_n"], v["clean_n"] - v["clean_nontrust"], v["clean_rej"]] for s, v in ps.items()}
        rep("B3s-1", got == pol[tau], f"τ_H={tau}：環境逐 seed 與 run_policy 相同 {got == pol[tau]}")
    if not ok:
        json.dump({"spec": SPEC, "passed": False, "checks": log}, open(os.path.join(POUT, "checks.json"), "w", encoding="utf-8"),
                  indent=1, ensure_ascii=False)
        R.close()
        raise SystemExit("B3s-1 失敗；停止，請回報，勿調參數。")

    # ---- 13.1 與 13.2 之判定 ----
    res = json.load(open(os.path.join(EF.OUT, "pairs.json"), encoding="utf-8"))
    res.update(R.cache)
    key = lambda d, x: f"{d}|{x or 'CLEAN'}|"
    J = {}
    J["TPR_nt|x=clean_nontrusted|base=B1-B3"] = judge_all(res, key, runs, A, base_orig, "clean_nontrusted", "TPR_nontrusted", "d_nontrusted")
    J["TPR_nt|x=clean_nontrusted|base=B1-B3+B3s"] = judge_all(res, key, runs, A, base_orig + b3s, "clean_nontrusted", "TPR_nontrusted", "d_nontrusted")
    J["TPR_rej|x=clean_false_reject|base=B1-B3+B3s"] = judge_all(res, key, runs, A, base_orig + b3s, "clean_false_reject", "TPR_rejected", "d_rejected")
    # 一致性：base=B1-B3 之 TPR_rej 判定須重現 eval_final.json 之 summary（確認判定函式同口徑）
    ef = json.load(open(os.path.join(EF.OUT, "eval_final.json"), encoding="utf-8"))
    chk = judge_all(res, key, runs, A, base_orig, "clean_false_reject", "TPR_rejected", "d_rejected")[1]
    same = all(chk[k]["verdicts"] == ef["summary"][k]["verdicts"] for k in chk)
    rep("P1", same, "以本程式之判定函式重算 §6 主判準（TPR_rej、原基線），與 eval_final.json 之 summary 相同")
    base_pts = {b: {"clean_false_reject": EF.mix(res, {b: 1.0}, None, key)["clean_false_reject"],
                    "clean_nontrusted": EF.mix(res, {b: 1.0}, None, key)["clean_nontrusted"]} for b in base_orig + b3s}

    # ---- 13.3：H1–H4 ----
    drl_dets = sorted({d for r in runs.values() for d in r["sigma_D"] if d != "D0"})
    worst_pool = sorted({ef["runs"][r]["A-pool"]["by_TPR"]["attacker"] for r in runs})
    diag_atks = sorted([x for x in A if x.startswith("A0_")] + [x for x in A if x.endswith(":ABR")] + worst_pool)
    diag_dets = ["D0", "MaxEsc-SI"] + drl_dets
    jobs = [(dets[d], atks[x], f) for d in diag_dets for x in diag_atks for f in EF.FOLDS]
    t = time.time()
    pool = R.pool(EF.FROZEN_TAU)
    out = pool.map(_diag_job, jobs, chunksize=1)
    print(f"診斷：{len(diag_dets)} 偵測端 × {len(diag_atks)} 攻擊者（{time.time() - t:.0f} s）", flush=True)
    clean_mx = R.run([(dets["MaxEsc-SI"], None, None)], use_cache=False)[EF.Runner.key(dets["MaxEsc-SI"], None, None)]["tot"]
    R.close()
    D = {}
    for i, (d, x, f) in enumerate(jobs):
        e = D.setdefault((d["id"], x["id"]), {"c": collections.Counter(), "ratios": []})
        e["c"].update(out[i]["c"]); e["ratios"] += out[i]["ratios"]

    def q(v):
        v = np.abs(np.asarray(v) - 1.0)
        return {"n": int(len(v)), "mean_abs_dev": float(v.mean()) if len(v) else None,
                "p50": float(np.quantile(v, .5)) if len(v) else None, "p90": float(np.quantile(v, .9)) if len(v) else None}

    diag = {}
    for (d, x), e in D.items():
        c = e["c"]
        esc = {g: {k.split("|")[2]: c[k] for k in c if k.startswith(f"esc|{g}|")} for g in ("tam", "clean")}
        keep = {g: {k.split("|")[2]: c[k] for k in c if k.startswith(f"keep|{g}|")} for g in ("tam", "clean")}
        diag[f"{d}|{x}"] = {
            "TPR_rejected": EF.ratio(c["tot|tam_rej"], c["tot|tam_n"]), "TPR_nontrusted": EF.ratio(c["tot|tam_nontrust"], c["tot|tam_n"]),
            "H1_escalations": esc, "H1_pending_not_escalated": keep,
            "H2_tampered_rejected_by_source": {"rule": c["tamrej|rule"], "drl": c["tamrej|drl"]},
            "H2_rule_ids": {k.split("|")[1]: c[k] for k in c if k.startswith("tamrej_rule|")},
            "H3_tampered_n": c["tam|n"], "H3_si_violated_rate": EF.ratio(c["tam|si_viol"], c["tam|n"]),
            "H3_multiplier": q(e["ratios"])}
    # 彙整（每個假說一行之數字；判斷留給正文，依 §13.3 之條件）
    agg = {}
    drl_esc = collections.Counter(); drl_tamrej = collections.Counter()
    for (d, x), e in D.items():
        if d in drl_dets:
            for k, v in e["c"].items():
                if k.startswith("esc|"):
                    drl_esc[k] += v
                if k.startswith("tamrej|"):
                    drl_tamrej[k] += v
    esc_all = sum(drl_esc.values())
    agg["H1"] = {"drl_escalations_total": esc_all, "to_rejected": drl_esc["esc|tam|rejected"] + drl_esc["esc|clean|rejected"],
                 "share_rejected": EF.ratio(drl_esc["esc|tam|rejected"] + drl_esc["esc|clean|rejected"], esc_all),
                 "by_group": {k: v for k, v in drl_esc.items()}}
    agg["H2"] = {"drl_detectors_tampered_rejected": {"rule": drl_tamrej["tamrej|rule"], "drl": drl_tamrej["tamrej|drl"]},
                 "rule_share": EF.ratio(drl_tamrej["tamrej|rule"], drl_tamrej["tamrej|rule"] + drl_tamrej["tamrej|drl"])}
    agg["H3"] = {x: {"si_violated_rate": diag[f"D0|{x}"]["H3_si_violated_rate"], "multiplier": diag[f"D0|{x}"]["H3_multiplier"],
                     "TPR_rejected_D0": diag[f"D0|{x}"]["TPR_rejected"]} for x in diag_atks}
    agg["H4"] = {"MaxEsc-SI_clean_false_reject": EF.ratio(clean_mx["clean_rej"], clean_mx["clean_n"]),
                 "D0_clean_false_reject": 159 / 15534,
                 "by_attacker": {x: {"MaxEsc-SI": diag[f"MaxEsc-SI|{x}"]["TPR_rejected"], "D0": diag[f"D0|{x}"]["TPR_rejected"]}
                                 for x in diag_atks}}
    json.dump({"spec": SPEC, "passed": ok, "checks": log}, open(os.path.join(POUT, "checks.json"), "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)
    json.dump({"spec": SPEC, "meta": EF.meta(), "B3s_tau": B3S_TAU, "baseline_points": base_pts,
               "judgements": {k: {"per_run": v[0], "summary": v[1]} for k, v in J.items()},
               "diagnostics": {"detectors": diag_dets, "attackers": diag_atks, "per_pair": diag, "aggregate": agg}},
              open(os.path.join(POUT, "posthoc.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    for k, v in J.items():
        print("==", k)
        for kk, vv in v[1].items():
            print("  ", kk, vv["verdicts"], vv["conclusion"])
    print("== H1", json.dumps(agg["H1"], ensure_ascii=False))
    print("== H2", json.dumps(agg["H2"], ensure_ascii=False))
    for x, v in agg["H3"].items():
        print("== H3", x, v)
    print("== H4 clean FRR MaxEsc-SI", agg["H4"]["MaxEsc-SI_clean_false_reject"])
    for x, v in agg["H4"]["by_attacker"].items():
        print("== H4", x, v)
    print("寫入", os.path.join(POUT, "posthoc.json"))


if __name__ == "__main__":
    main()
