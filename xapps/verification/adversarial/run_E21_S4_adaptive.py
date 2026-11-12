# -*- coding: utf-8 -*-
"""run_E21_S4_adaptive.py — 規格 E21 §8.9（E21-S4 v1）：B-off（＋全域較低 S_i 殘差門檻）對學習型攻擊者。

防守變體以 game_core.FLOOR_FN 改寫規則下限（預設 None = E19 之 D0，逐位不變）；偵測端恆取下限。
攻擊者：E19 之 A0 腳本，與對每個變體 × 觀測層級 × fold 訓練之 A-BR（直接呼叫 psro._train_job）。

階段（--stage）：checks｜abr｜eval｜report（可續跑；結果逐對快取於 pairs.json）
用法（新機器）：
  ZT_DATASET=d30 ZT_FUSION_ORDER=severity ~/venvs/drl/bin/python3 run_E21_S4_adaptive.py --stage checks --workers 10
"""
import os
import sys
import json
import time
import argparse
import multiprocessing as mp
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SEV = os.path.join(ROOT, "data", "results", "d30_fusion_order", "severity")
OUT = os.path.join(SEV, "E21_S4")
SPEC = "docs/thesis/E21_relaxable_component_spec.md §8.9 v1"
VARIANTS = ["V0", "V1", "V2_s2", "V2_s2.5", "V2_s3"]
LEVELS = ["O-full", "O-outcome"]
FOLDS = list(range(8))
SCRIPTS = [("A0_step_0.6", "step", 0.60), ("A0_step_0.8", "step", 0.80), ("A0_drift_0.01", "drift", 0.01)]
D1R = {"R2_D1_STRONG", "R2_D1_WEAK"}
PAIRS_REF = [os.path.join(ROOT, "data", "results", "d30", "drl", "eval_final", "pairs.json"),
             os.path.join(ROOT, "data", "results", "d30", "drl", "psro_newmachine_20261111", "eval_final", "pairs.json")]
S1_JSON = os.path.join(SEV, "E21_S1", "E21_S1_boff.json")
S3_JSON = os.path.join(SEV, "E21_S3", "E21_S3_gate.json")

_W = {}


def variant_s(vid):
    return None if vid in ("V0", "V1") else float(vid.split("_s")[1])


def make_floor_fn(vid):
    if vid == "V0":
        return None
    s = variant_s(vid)

    def fn(dec, rid, also, si, z):
        if dec == "low-trust" and rid in D1R and set(also) <= D1R:
            dec, rid = "trusted", "R2_D1_RELAXED"
        if s is not None and dec == "trusted" and si != "unavailable" and z is not None and z >= s:
            dec, rid = "low-trust", "R2_SI_SOFT"
        return dec, rid
    return fn


def _init(vid):
    import psro as PS
    PS._init_worker()
    PS._W["G"].FLOOR_FN = make_floor_fn(vid)
    _W.update(PS=PS, vid=vid)


def det_strat(vid):
    return {"kind": "floor", "name": vid}


def atk_strats():
    """id → 描述（腳本 3 個；A-BR 存在者）"""
    a = {i: {"id": i, "kind": "scripted", "attack": k, "param": p} for i, k, p in SCRIPTS}
    for v in VARIANTS:
        for lv in LEVELS:
            base = os.path.join(OUT, "abr", v, lv, "ABR")
            if all(os.path.exists(f"{base}_f{f}.zip") for f in FOLDS):
                i = f"ABR[{v}]{lv}"
                a[i] = {"id": i, "kind": "ppo", "level": lv, "name": i,
                        "paths": {str(f): f"{base}_f{f}" for f in FOLDS}, "target": v}
    return a


def _job(args):
    """(atk 描述或 None, fold) → {'tot', 'seed', 'dev'}；變體由行程初始化決定"""
    aS, fold = args
    PS = _W["PS"]
    G, E, ds = PS._W["G"], PS._W["E"], PS._W["ds"]
    sd = ds.get(ds.files[fold])
    det = PS._load(det_strat(_W["vid"]), fold, "det")
    if aS is None:
        ep = G.run_episode(G.Episode(sd, None), det)
        return {"tot": dict(ep.stats), "seed": sd.seed, "dev": []}
    atk = PS._load(aS, fold, "atk")
    tot, dev = {}, []
    for cell in sd.cells_all:
        ep = PS._W["cache"].get(sd, cell, det, E.new_episode)
        G.run_episode(ep, det, atk)
        for k, v in ep.stats.items():
            tot[k] = tot.get(k, 0) + v
        dev += [abs(a - 1.0) for a in ep.a_hist.values()]
    return {"tot": tot, "seed": sd.seed, "dev": dev}


class Runner:
    def __init__(self, workers):
        self.workers = workers
        self.path = os.path.join(OUT, "pairs.json")
        self.cache = json.load(open(self.path, encoding="utf-8")) if os.path.exists(self.path) else {}

    def run(self, vid, atks):
        """atks: [描述或 None]；回傳 {key: {'tot','per_seed','dev_median'}}"""
        key = lambda a: f"{vid}|{a['id'] if a else 'CLEAN'}"
        todo = [a for a in atks if key(a) not in self.cache]
        if todo:
            t = time.time()
            with mp.Pool(self.workers, initializer=_init, initargs=(vid,)) as p:
                res = p.map(_job, [(a, f) for a in todo for f in FOLDS], chunksize=1)
            for i, a in enumerate(todo):
                rs = res[i * len(FOLDS):(i + 1) * len(FOLDS)]
                tot, per_seed, dev = {}, {}, []
                for r in rs:
                    for k, v in r["tot"].items():
                        tot[k] = tot.get(k, 0) + v
                    per_seed[str(r["seed"])] = r["tot"]
                    dev += r["dev"]
                self.cache[key(a)] = {"tot": tot, "per_seed": per_seed,
                                      "dev_median": float(np.median(dev)) if dev else None, "dev_n": len(dev)}
            os.makedirs(OUT, exist_ok=True)
            json.dump(self.cache, open(self.path + ".tmp", "w", encoding="utf-8"))
            os.replace(self.path + ".tmp", self.path)
            print(f"  {vid}：{len(todo)} 組 × 8 fold（{time.time() - t:.0f} s）", flush=True)
        return {key(a): self.cache[key(a)] for a in atks}


def fail(msg):
    print(f"✗ {msg}\n一致性檢查失敗；停止，請回報，勿調參數。", flush=True)
    sys.exit(2)


def stage_checks(args):
    R = Runner(args.workers)
    ref_path = next((p for p in PAIRS_REF if os.path.exists(p)), None)
    if ref_path is None:
        fail("找不到 eval_final/pairs.json")
    ref = json.load(open(ref_path, encoding="utf-8"))
    sa = atk_strats()
    scripts = [sa[i] for i, _, _ in SCRIPTS]
    got = R.run("V0", [None] + scripts)
    for a in [None] + scripts:
        k_new = f"V0|{a['id'] if a else 'CLEAN'}"
        k_ref = f"D0|{a['id'] if a else 'CLEAN'}|"
        if got[k_new]["per_seed"] != ref[k_ref]["per_seed"]:
            fail(f"S4-0 {k_new} 之 per_seed 與 {os.path.relpath(ref_path, ROOT)} 之 {k_ref} 不同")
    print(f"  S4-0 ✓ V0 × 乾淨／3 個腳本之 per_seed 逐位重現 {os.path.relpath(ref_path, ROOT)}", flush=True)
    s1 = json.load(open(S1_JSON, encoding="utf-8"))["results"]
    s3 = json.load(open(S3_JSON, encoding="utf-8"))["results"]
    for vid in VARIANTS[1:]:
        s = variant_s(vid)
        g = R.run(vid, [None] + scripts)
        c = g[f"{vid}|CLEAN"]["tot"]
        fb = c["clean_nontrust"] / c["clean_n"]
        for name, _, _ in SCRIPTS:
            curve = {(p["s"] if p["s"] != "inf" else None): p for p in s3[name]["global_curve"]}
            pt = curve[s]
            if fb != pt["FB_strict"]:
                fail(f"S4-1 {vid} 乾淨 FB {fb} ≠ E21-S3 {pt['FB_strict']}")
            t = g[f"{vid}|{name}"]["tot"]
            mf = (t["tam_n"] - t["tam_nontrust"]) / t["tam_n"]
            if t["tam_n"] != s1["delay"][name]["tampered"] or mf != pt["MF_strict"]:
                fail(f"S4-2 {vid} × {name}：竄改 {t['tam_n']}（S1 {s1['delay'][name]['tampered']}）、MF {mf}（S3 {pt['MF_strict']}）")
        print(f"  S4-1 ✓ S4-2 ✓ {vid}：FB {fb:.4f}；三個腳本之竄改／准入計數重現 E21-S3", flush=True)
    json.dump({"spec": SPEC, "passed": True, "ref": os.path.relpath(ref_path, ROOT), "time": time.strftime("%FT%TZ", time.gmtime())},
              open(os.path.join(OUT, "checks.json"), "w", encoding="utf-8"), indent=1)
    print("全部一致性檢查通過。", flush=True)


def stage_abr(args):
    import psro as PS
    for vi, vid in enumerate(VARIANTS):
        jobs = []
        for li, lv in enumerate(LEVELS):
            for f in FOLDS:
                path = os.path.join(OUT, "abr", vid, lv, f"ABR_f{f}")
                seed = 900000 + 10000 * vi + 1000 * li + 10 * f + 1
                jobs.append(("atk", f, [det_strat(vid)], [1.0], lv, PS.BR_MAX, PS.BR_EVERY, seed, path))
        todo = [j for j in jobs if not os.path.exists(j[-1] + ".zip")]
        print(f"A-BR {vid}：{len(jobs)} 個（尚待 {len(todo)}）", flush=True)
        t = time.time()
        with mp.Pool(args.workers, initializer=_init, initargs=(vid,), maxtasksperchild=1) as p:
            for i, path in enumerate(p.imap_unordered(_train, todo, chunksize=1)):
                print(f"  完成 {os.path.relpath(path, OUT)}（{i + 1}／{len(todo)}，{time.time() - t:.0f} s）", flush=True)
    print("A-BR 完成。", flush=True)


def _train(job):
    return _W["PS"]._train_job(job)


def stage_eval(args):
    if not json.load(open(os.path.join(OUT, "checks.json"), encoding="utf-8")).get("passed"):
        fail("checks 未通過")
    sa = atk_strats()
    n_abr = sum(1 for a in sa.values() if a["kind"] == "ppo")
    if n_abr != len(VARIANTS) * len(LEVELS):
        fail(f"A-BR 不齊：{n_abr}／{len(VARIANTS) * len(LEVELS)}")
    R = Runner(args.workers)
    for vid in VARIANTS:
        R.run(vid, [None] + list(sa.values()))
    print("評估完成。", flush=True)


def stage_report(args):
    sa = atk_strats()
    cache = json.load(open(os.path.join(OUT, "pairs.json"), encoding="utf-8"))
    g = lambda t, a, b: t.get(a, 0) / t[b] if t.get(b) else None

    def metr(t):
        return {"TPR_nontrusted": g(t, "tam_nontrust", "tam_n"), "MF_strict": (t["tam_n"] - t["tam_nontrust"]) / t["tam_n"],
                "TPR_rejected": g(t, "tam_rej", "tam_n"), "lure_rate_C_strict": g(t, "lure", "lure_opp"), "u_atk": g(t, "atk_R", "atk_n")}
    rep = {"spec": SPEC, "variants": {}, "verdicts": {}}
    for vid in VARIANTS:
        c = cache[f"{vid}|CLEAN"]["tot"]
        ent = {"FB_strict": c["clean_nontrust"] / c["clean_n"], "attackers": {}}
        for aid, a in sa.items():
            r = cache[f"{vid}|{aid}"]
            ent["attackers"][aid] = {**metr(r["tot"]), "dev_median": r["dev_median"],
                                     "per_fold_lure": {s: g(t, "lure", "lure_opp") for s, t in r["per_seed"].items()}}
        for lv in LEVELS:
            pool = [i for i, a in sa.items() if a["kind"] == "scripted" or a.get("level") == lv]
            wl = max(pool, key=lambda i: ent["attackers"][i]["lure_rate_C_strict"])
            wm = max(pool, key=lambda i: ent["attackers"][i]["MF_strict"])
            ent[f"worst_{lv}"] = {"lure": [wl, ent["attackers"][wl]["lure_rate_C_strict"]],
                                  "MF_strict": [wm, ent["attackers"][wm]["MF_strict"]]}
        rep["variants"][vid] = ent
    v0 = rep["variants"]["V0"]
    print("\n── 結果 ──")
    for vid in VARIANTS:
        e = rep["variants"][vid]
        print(f"  {vid:8s} FB {e['FB_strict']:.4f}  " + "  ".join(
            f"{lv}: 最壞誘導 {e[f'worst_{lv}']['lure'][1]:.3f}（{e[f'worst_{lv}']['lure'][0]}） 最壞 MF {e[f'worst_{lv}']['MF_strict'][1]:.3f}（{e[f'worst_{lv}']['MF_strict'][0]}）"
            for lv in LEVELS))
        for lv in LEVELS:
            own = e["attackers"][f"ABR[{vid}]{lv}"]
            print(f"      own A-BR {lv}: 誘導 {own['lure_rate_C_strict']:.3f}  MF {own['MF_strict']:.3f}  TPR_rej {own['TPR_rejected']:.3f}  |a−1| 中位數 {own['dev_median']:.3f}")
    for vid in VARIANTS[1:]:
        e = rep["variants"][vid]
        for lv in LEVELS:
            a_ok = e[f"worst_{lv}"]["lure"][1] <= v0[f"worst_{lv}"]["lure"][1]
            b_ok = e[f"worst_{lv}"]["MF_strict"][1] <= v0[f"worst_{lv}"]["MF_strict"][1]
            mine = e["attackers"][f"ABR[{vid}]{lv}"]["per_fold_lure"]
            base = v0["attackers"][f"ABR[V0]{lv}"]["per_fold_lure"]
            n_ok = sum(1 for s in mine if mine[s] is not None and base[s] is not None and mine[s] <= base[s])
            verdict = "保持" if (a_ok and b_ok and n_ok >= 7) else "不保持"
            rep["verdicts"][f"{vid}|{lv}"] = {"a_worst_lure": a_ok, "b_worst_MF": b_ok, "c_folds_own_BR": n_ok, "verdict": verdict}
            print(f"  判準 {vid} {lv}：(a) {a_ok} (b) {b_ok} (c) {n_ok}/8 → {verdict}")
    json.dump(rep, open(os.path.join(OUT, "E21_S4_adaptive.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"寫入 {os.path.join(OUT, 'E21_S4_adaptive.json')}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["checks", "abr", "eval", "report"], required=True)
    ap.add_argument("--workers", type=int, default=10)
    args = ap.parse_args()
    {"checks": stage_checks, "abr": stage_abr, "eval": stage_eval, "report": stage_report}[args.stage](args)


if __name__ == "__main__":
    mp.set_start_method("fork", force=True)
    main()
