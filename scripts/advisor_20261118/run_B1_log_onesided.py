#!/usr/bin/env python3
"""B1 (spec docs/thesis/B1_log_onesided_spec_v0.md). usage: ZT_DELAY_SOURCE=reconstructed ZT_DATASET=d30 python3 run_B1_log_onesided.py OUT.json
run from xapps/verification/residuals/ (imports run_E9_operating_regime)."""
import os, sys, glob, json, collections, numpy as np
os.environ.setdefault("ZT_DELAY_SOURCE", "reconstructed"); os.environ.setdefault("ZT_DATASET", "d30")
sys.path.insert(0, os.getcwd())
import run_E9_operating_regime as E9, datasets as DS
TAU = E9.TAU_S
files = sorted(glob.glob(os.path.join(E9.DATA_DIR, DS.PATTERN)))
seeds = [os.path.basename(f).split("seed")[-1][:4] for f in files]
data = {s: E9.load_cell_delay(f) for s, f in zip(seeds, files)}
STEPS = [0.5, 0.6, 0.7, 0.8, 0.9, 1.2, 1.3, 1.4, 1.5]
UP = [0.005, 0.01, 0.02, 0.04]; DOWN = [0.005, 0.01, 0.02, 0.04]; FLOOR = 0.5
def samples(Wd):
    """yield (cell, d, peer_med, peer_logmed) with windows that have >=MIN_NEIGHBOR peers"""
    cells = sorted({c for w in Wd for c in Wd[w]})
    for tc in cells:
        idx = [w for w in sorted(Wd) if tc in Wd[w] and len([c for c in Wd[w] if c != tc]) >= E9.MIN_NEIGHBOR]
        if len(idx) < E9.MIN_LEN: continue
        d = np.array([Wd[w][tc] for w in idx]); pm = np.array([np.median([Wd[w][c] for c in Wd[w] if c != tc]) for w in idx])
        pl = np.array([np.median(np.log([Wd[w][c] for c in Wd[w] if c != tc])) for w in idx])
        yield tc, d, pm, pl
def mad_scale(x):
    x = np.asarray(x); return 1.4826 * (float(np.median(np.abs(x - np.median(x)))) + 1e-9)
def zs(var, o, pm, pl, sc):
    if var == "V0": return np.abs(o - pm) / sc["V0"]
    if var == "V1": return np.abs(o - pm) / sc["V1"]
    r = np.log(o) - pl
    return np.abs(r) / sc["V2"] if var == "V2" else -r / sc["V2"]
VARS = ["V0", "V1", "V2", "V3"]
def attacks(d):
    mean = d.mean(); n = len(d); t0 = n // 2; out = {}
    for f in STEPS:
        o = d.copy(); o[t0:] *= f; out[f"step_x{f}"] = (o, t0)
    for r in UP:
        out[f"driftUp_{r}"] = (E9.inject_drift(d, t0, r, mean), t0)
    for r in DOWN:
        o = d.copy(); t = np.arange(n - t0); o[t0:] *= np.maximum(FLOOR, 1 - r * t); out[f"driftDown_{r}"] = (o, t0)
    return out
res = {"spec": "docs/thesis/B1_log_onesided_spec_v0.md", "tau": TAU, "seeds": seeds, "folds": {}}
store = {v: collections.defaultdict(lambda: collections.defaultdict(list)) for v in VARS + ["V1m", "V2m", "V3m", "V0e", "V1e", "V2e", "V3e"]}   # *e: threshold = 1% training clean FPR (added after first run, see spec addendum)   # variant -> metric -> seed -> list
for ts in seeds:
    tr = [s for s in seeds if s != ts]
    lin, lg, lvl = [], [], []
    trs = []
    for s in tr:
        for tc, d, pm, pl in samples(data[s]):
            lin += list(d - pm); lg += list(np.log(d) - pl); lvl += list(d)
            trs.append((d, pm, pl))
    sc = {"V0": E9.global_scale([data[x] for x in tr]), "V1": mad_scale(lin), "V2": mad_scale(lg)}
    # matched thresholds: V1..V3 threshold such that training clean FPR (attack half) equals V0's
    def clean_half(var, thr_sc):
        return np.concatenate([zs(var, d[len(d)//2:], pm[len(d)//2:], pl[len(d)//2:], thr_sc) for d, pm, pl in trs])
    f0 = float((clean_half("V0", sc) > TAU).mean())
    thr = {"V0": TAU}
    for v in ("V1", "V2", "V3"):
        z = clean_half(v, sc); thr[v] = float(np.quantile(z, 1 - f0)) if f0 > 0 else TAU
    thr1 = {v: float(np.quantile(clean_half(v, sc), 0.99)) for v in VARS}
    res["folds"][ts] = {"scales": sc, "train_fpr_V0": f0, "matched_thr": thr, "thr_1pct": thr1}
    for tc, d, pm, pl in samples(data[ts]):
        n = len(d); t0 = n // 2
        for v in VARS:
            store[v]["clean_fpr"][ts].append(float((zs(v, d[t0:], pm[t0:], pl[t0:], sc) > TAU).mean()))
            if v != "V0": store[v + "m"]["clean_fpr"][ts].append(float((zs(v, d[t0:], pm[t0:], pl[t0:], sc) > thr[v]).mean()))
            store[v + "e"]["clean_fpr"][ts].append(float((zs(v, d[t0:], pm[t0:], pl[t0:], sc) > thr1[v]).mean()))
        for name, (o, t0a) in attacks(d).items():
            for v in VARS:
                for tag, th in ((v, TAU), (v + "m", thr.get(v)), (v + "e", thr1[v])):
                    if tag not in store: continue
                    z = zs(v, o, pm, pl, sc); hit = z[t0a:] > th
                    store[tag][name + "|rate"][ts].append(float(hit.mean()))
                    k = int(np.argmax(hit)) if hit.any() else None
                    if k is None:
                        store[tag][name + "|undetected"][ts].append(1.0)
                    else:
                        store[tag][name + "|undetected"][ts].append(0.0)
                        store[tag][name + "|delay_win"][ts].append(float(k))
                        store[tag][name + "|bias_at_first"][ts].append(float(abs(o[t0a + k] / d[t0a + k] - 1)))
def agg(by):
    allv = [x for l in by.values() for x in l]; per = {s: float(np.mean(l)) for s, l in by.items() if l}
    return {"mean": float(np.mean(allv)) if allv else None, "median": float(np.median(allv)) if allv else None, "n": len(allv),
            "seed_min": min(per.values()) if per else None, "seed_max": max(per.values()) if per else None}
res["results"] = {v: {m: agg(by) for m, by in store[v].items()} for v in store}
# built-in check: V0 must reproduce E9 spatial numbers
ref = json.load(open(os.path.join(os.path.dirname(E9.__file__), "../../../data/results/d30_delay_reconstructed/E9_operating_regime.json")))
chk = {"clean_fpr": (res["results"]["V0"]["clean_fpr"]["mean"], ref["clean_fpr"]["spatial"]["mean"])}
for r in (0.005, 0.01, 0.02, 0.04): chk[f"drift{r}"] = (res["results"]["V0"][f"driftUp_{r}|rate"]["mean"], ref["drift"]["spatial"][str(r)]["mean"])
res["check_V0_vs_E9"] = {k: {"here": a, "E9": b, "diff": abs(a - b)} for k, (a, b) in chk.items()}
res["check_ok"] = all(v["diff"] < 1e-9 for v in res["check_V0_vs_E9"].values())
json.dump(res, open(sys.argv[1], "w"), indent=1)
print("check_ok", res["check_ok"], {k: round(v["diff"], 12) for k, v in res["check_V0_vs_E9"].items()})
