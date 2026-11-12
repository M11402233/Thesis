# -*- coding: utf-8 -*-
"""run_M2_service_time.py — 規格 docs/thesis/M2_service_time_spec.md v1。

用法（舊機器、閒置、同一核心依序）：
  ZT_DATASET=d30 ZT_FUSION_ORDER=severity taskset -c 2 python3 run_M2_service_time.py --part V --run 1
  ZT_DATASET=d30 ZT_FUSION_ORDER=severity taskset -c 2 ~/venvs/drl/bin/python3 run_M2_service_time.py --part L --run 1
  python3 run_M2_service_time.py --part report
"""
import os
import sys
import gc
import json
import time
import argparse
import subprocess
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(ROOT, "data", "results", "d30_fusion_order", "severity", "M2")
BK = os.path.join(ROOT, "data", "results", "d30", "drl", "psro_newmachine_20261111")
NEW_PREFIX = "/home/cindy/oran-zt-kpm-verification/data/results/d30/drl/psro/"
RUNS = [(lv, t) for lv in ("O-full", "O-outcome") for t in (0, 1, 2)]
WARMUP, REPEAT = 3, 5


def stats(v):
    v = np.asarray(v, float)
    return {"mean": float(v.mean()), "p95": float(np.percentile(v, 95)), "p99": float(np.percentile(v, 99)), "max": float(v.max()), "n": int(v.size)}


def idle_check():
    procs = subprocess.run("pgrep -af 'scenario-three|collect_' | grep -v pgrep || true", shell=True, capture_output=True, text=True).stdout.strip()
    load1 = os.getloadavg()[0]
    cpu = subprocess.run("lscpu | grep 'Model name'", shell=True, capture_output=True, text=True).stdout.strip()
    aff = sorted(os.sched_getaffinity(0))
    ok = (not procs) and load1 < 0.3
    return ok, {"load1": load1, "procs": procs, "cpu": cpu, "affinity": aff, "time": time.strftime("%F %T")}


def part_V(run):
    sys.path.insert(0, os.path.join(HERE, "..", "residuals"))
    import datasets as DS
    import resource_eval_xapp as R
    files = DS.files()
    res = R.run_benchmark(files, OUT, DS.CFG.get("max_window"), "strict", WARMUP, REPEAT, return_arrays=True)
    return res


def part_L(run):
    import torch
    torch.set_num_threads(1)
    sys.path.insert(0, HERE)
    import game_core as G
    import env_kpm_game as E
    from sb3_contrib import MaskablePPO
    ds = G.DataStore()
    pairs = json.load(open(os.path.join(BK, "eval_final", "pairs.json"), encoding="utf-8"))
    out = {"detectors": {}, "versions": {"torch": torch.__version__}}
    import stable_baselines3, sb3_contrib
    out["versions"].update({"stable-baselines3": stable_baselines3.__version__, "sb3-contrib": sb3_contrib.__version__})
    bad = []
    for lv, t in RUNS:
        st = json.load(open(os.path.join(BK, "psro", lv, f"t{t}", "state.json"), encoding="utf-8"))
        r = f"{lv}/t{t}"
        for d, p in zip(st["D"], st["sigma"]["D"]):
            if p <= 0:
                continue
            did = f"{r}:{d['name']}"
            if d["kind"] == "floor":
                continue                                   # D0 無學習決策
            if did in out["detectors"]:
                continue
            arrs, seeds = [], []
            for fold, f in enumerate(ds.files):
                path = d["paths"][str(fold)].replace(NEW_PREFIX, os.path.join(BK, "psro") + "/")
                det = E.LearnedDetector(MaskablePPO.load(path, device="cpu"), f"{did}@f{fold}")
                sd = ds.get(f)
                runs_ = []
                for i in range(WARMUP + REPEAT):
                    ep = G.Episode(sd, None)
                    lat = []
                    gc.collect(); gc.disable()
                    try:
                        while ep.k < sd.n:
                            ep.begin()
                            t0 = time.perf_counter_ns()
                            G.decide_pending(ep, det)
                            lat.append((time.perf_counter_ns() - t0) / 1e6)
                            ep.end()
                    finally:
                        gc.enable()
                    if i >= WARMUP:
                        runs_.append(lat)
                # M2-1：乾淨判定計數須與 eval_final 之 pairs.json 相同
                ref = pairs[f"{did}|CLEAN|"]["per_seed"][str(sd.seed)]
                got = {k: int(ep.stats.get(k, 0)) for k in ("clean_n", "clean_rej", "clean_nontrust")}
                if any(got[k] != ref[k] for k in got):
                    bad.append((did, sd.seed, got, {k: ref[k] for k in got}))
                arrs.append(np.median(np.array(runs_), axis=0).tolist()); seeds.append(str(sd.seed))
            allv = np.concatenate([np.asarray(a) for a in arrs])
            out["detectors"][did] = {"run": r, "sigma": p, "L": stats(allv), "_arrays": {"seeds": seeds, "L": arrs}}
            print(f"  {did:<22} σ={p:.3f}  L mean={allv.mean():.3f} ms  P99={np.percentile(allv, 99):.3f}  max={allv.max():.3f}", flush=True)
    if bad:
        print(f"✗ M2-1 不符：{bad[:3]}\n停止：不寫結果。請回報，勿調參數。"); sys.exit(2)
    print("  M2-1 ✓ 13 個偵測端 × 8 seed 之乾淨判定計數與 pairs.json 相同")
    return out


def report():
    V, L = {}, {}
    for n in (1, 2, 3):
        pv, pl = os.path.join(OUT, f"M2_V_run{n}.json"), os.path.join(OUT, f"M2_L_run{n}.json")
        if os.path.exists(pv) and os.path.exists(pl):
            V[n], L[n] = json.load(open(pv)), json.load(open(pl))
    out = {"spec": "docs/thesis/M2_service_time_spec.md v1", "runs": {}}
    for n in V:
        va = V[n]["_arrays"]
        v = {s: np.asarray(a) + np.asarray(b) for s, a, b in zip(va["seeds"], va["P1_P3"], va["resource_eval_xapp"])}
        vall = np.concatenate([v[s] for s in va["seeds"]])
        rr = {"V": stats(vall), "detectors": {}, "per_run_max_p99": {}}
        for did, d in L[n]["detectors"].items():
            la = d["_arrays"]
            tot = np.concatenate([v[s] + np.asarray(x) for s, x in zip(la["seeds"], la["L"])])
            rr["detectors"][did] = {"run": d["run"], "sigma": d["sigma"], "L": d["L"], "V_plus_L": stats(tot),
                                    "p99V_plus_p99L": rr["V"]["p99"] + d["L"]["p99"]}
        for r in sorted({d["run"] for d in rr["detectors"].values()}):
            sup = [x for x in rr["detectors"].values() if x["run"] == r]
            rr["per_run_max_p99"][r] = {"L": max(x["L"]["p99"] for x in sup), "V_plus_L": max(x["V_plus_L"]["p99"] for x in sup)}
        out["runs"][str(n)] = rr
    if out["runs"]:
        g = lambda f: [f(r) for r in out["runs"].values()]
        out["summary"] = {"V_p99_range": [min(g(lambda r: r["V"]["p99"])), max(g(lambda r: r["V"]["p99"]))],
                          "L_p99_range_over_detectors_and_runs": [min(g(lambda r: min(d["L"]["p99"] for d in r["detectors"].values()))),
                                                                  max(g(lambda r: max(d["L"]["p99"] for d in r["detectors"].values())))],
                          "V_plus_L_p99_range": [min(g(lambda r: min(d["V_plus_L"]["p99"] for d in r["detectors"].values()))),
                                                 max(g(lambda r: max(d["V_plus_L"]["p99"] for d in r["detectors"].values())))],
                          "n_runs": len(out["runs"])}
        print(json.dumps(out["summary"], indent=1))
    json.dump(out, open(os.path.join(OUT, "M2_service_time.json"), "w"), indent=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", choices=["V", "L", "report"], required=True)
    ap.add_argument("--run", type=int, default=1)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    if a.part == "report":
        return report()
    if os.environ.get("ZT_DATASET") != "d30" or os.environ.get("ZT_FUSION_ORDER") != "severity":
        raise SystemExit("須 ZT_DATASET=d30 ZT_FUSION_ORDER=severity")
    ok, env = idle_check()
    with open(os.path.join(OUT, f"env_run{a.run}_{a.part}.txt"), "w") as fh:
        fh.write(json.dumps(env, ensure_ascii=False, indent=1))
    if not ok:
        print(f"✗ M2-3 閒置條件不符：{env}\n停止。"); sys.exit(2)
    print(f"── M2 part {a.part} run {a.run}：{env}", flush=True)
    res = part_V(a.run) if a.part == "V" else part_L(a.run)
    res["environment"] = env
    json.dump(res, open(os.path.join(OUT, f"M2_{a.part}_run{a.run}.json"), "w"), indent=1)
    print("寫入", os.path.join(OUT, f"M2_{a.part}_run{a.run}.json"))


if __name__ == "__main__":
    main()
