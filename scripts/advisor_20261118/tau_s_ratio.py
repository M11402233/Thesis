import os, sys, glob, json, collections, numpy as np
os.environ.setdefault("ZT_DELAY_SOURCE", "reconstructed"); os.environ.setdefault("ZT_DATASET", "d30")
sys.path.insert(0, os.getcwd())
import run_E9_operating_regime as E9, datasets as DS
files = sorted(glob.glob(os.path.join(E9.DATA_DIR, DS.PATTERN)))
seeds = [os.path.basename(f).split("seed")[-1].replace(".txt", "") for f in files]
data = {s: E9.load_cell_delay(f) for s, f in zip(seeds, files)}
TAU = 4.0
out = {"tau": TAU, "delay_source": os.environ["ZT_DELAY_SOURCE"], "per_seed_cell": {}, "scales_C2": {}}
allr = []; drift_pred = collections.defaultdict(list)
for ts in seeds:
    s = E9.global_scale([data[x] for x in seeds if x != ts]); out["scales_C2"][ts] = s
    Wd = data[ts]; wins = sorted(Wd); cells = sorted({c for w in Wd for c in Wd[w]})
    for tc in cells:
        idx = [w for w in wins if tc in Wd[w] and len([c for c in Wd[w] if c != tc]) >= E9.MIN_NEIGHBOR]
        if len(idx) < E9.MIN_LEN: continue
        pm = np.array([np.median([Wd[w][c] for c in Wd[w] if c != tc]) for w in idx])
        ser = np.array([Wd[w][tc] for w in idx])
        r = TAU * s / pm; allr += list(r)
        mean = ser.mean(); T = len(idx) - len(idx)//2
        out["per_seed_cell"][f"{ts}/{tc}"] = {"n_win": len(idx), "s_ms": s, "peer_median_ms_median": float(np.median(pm)),
            "tau_s_over_median": {"median": float(np.median(r)), "p10": float(np.percentile(r, 10)), "p90": float(np.percentile(r, 90))},
            "frac_windows_low_report_undetectable": float((r >= 1).mean()),
            "tau_s_over_own_mean": TAU * s / mean, "attack_len_T": T}
        for rate in E9.DRIFT_RATES:   # advisor's A1 formula with actual c and actual T (offset grows rate*t*mean)
            drift_pred[rate].append(max(0.0, 1 - (TAU * s / mean) / (rate * T)))
a = np.array(allr)
out["overall"] = {"n": int(a.size), "median": float(np.median(a)), "p10": float(np.percentile(a, 10)), "p25": float(np.percentile(a, 25)),
                  "p75": float(np.percentile(a, 75)), "p90": float(np.percentile(a, 90)), "frac_ge_1": float((a >= 1).mean())}
meas = json.load(open(os.path.join(os.path.dirname(E9.__file__), "../../../data/results/d30_delay_reconstructed/E9_operating_regime.json")))
out["drift_formula_vs_measured_spatial"] = {str(r): {"predicted_mean": float(np.mean(v)), "measured_mean": meas["drift"]["spatial"][str(r)]["mean"]} for r, v in drift_pred.items()}
print(json.dumps({k: out[k] for k in ("overall", "scales_C2", "drift_formula_vs_measured_spatial")}, indent=1))
rows = sorted(out["per_seed_cell"].items(), key=lambda kv: kv[1]["tau_s_over_median"]["median"])
print("lowest:", [(k, round(v["tau_s_over_median"]["median"], 2)) for k, v in rows[:4]], "highest:", [(k, round(v["tau_s_over_median"]["median"], 2)) for k, v in rows[-4:]])
json.dump(out, open(sys.argv[1], "w"), indent=1)
