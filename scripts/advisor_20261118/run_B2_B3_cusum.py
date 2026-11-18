#!/usr/bin/env python3
"""B2/B3 CUSUM (docs/thesis/B2_B3_cusum_spec_v0.md). Run from xapps/verification/residuals. usage: run_B2_B3_cusum.py OUT.json FIG.png"""
import os, sys, glob, json, collections, numpy as np
os.environ.setdefault("ZT_DELAY_SOURCE", "reconstructed"); os.environ.setdefault("ZT_DATASET", "d30")
sys.path.insert(0, os.getcwd())
import run_E9_operating_regime as E9, datasets as DS
K = 0.5; ARL = [100, 1000]; FLOOR, CAP = 0.5, 2.0
files = sorted(glob.glob(os.path.join(E9.DATA_DIR, DS.PATTERN)))
seeds = [os.path.basename(f).split("seed")[-1][:4] for f in files]
data = {s: E9.load_cell_delay(f) for s, f in zip(seeds, files)}
def series(Wd):
    cells = sorted({c for w in Wd for c in Wd[w]})
    for tc in cells:
        idx = [w for w in sorted(Wd) if tc in Wd[w] and len([c for c in Wd[w] if c != tc]) >= E9.MIN_NEIGHBOR]
        if len(idx) < E9.MIN_LEN: continue
        d = np.array([Wd[w][tc] for w in idx])
        pl = np.array([np.median(np.log([Wd[w][c] for c in Wd[w] if c != tc])) for w in idx])
        pmin = np.array([min(Wd[w][c] for c in Wd[w] if c != tc) for w in idx])
        pm = np.array([np.median([Wd[w][c] for c in Wd[w] if c != tc]) for w in idx])
        yield tc, d, pl, pmin, pm
def mad(x): x = np.asarray(x); return 1.4826 * (float(np.median(np.abs(x - np.median(x)))) + 1e-9)
def cusum_alarms(z, h, side):
    s = 0.0; al = np.zeros(len(z), bool)
    for t, x in enumerate(z):
        s = max(0.0, s + (x if side == "up" else -x) - K)
        if s > h: al[t] = True; s = 0.0
    return al
def det(kind, z, th):
    if kind == "sw_low": return -z > th
    if kind == "sw_two": return np.abs(z) > th
    if kind == "cu_low": return cusum_alarms(z, th, "low")
    if kind == "cu_up": return cusum_alarms(z, th, "up")
    if kind == "cu_two": return cusum_alarms(z, th, "low") | cusum_alarms(z, th, "up")
KINDS = ["sw_low", "sw_two", "cu_low", "cu_two"]
def arl(alarms_list):
    n = sum(len(a) for a in alarms_list); m = sum(int(a.sum()) for a in alarms_list); return n / m if m else float("inf")
def calib(kind, zs, target):
    if kind.startswith("sw"):
        v = np.concatenate([(-z if kind == "sw_low" else np.abs(z)) for z in zs]); return float(np.quantile(v, 1 - 1 / target))
    lo, hi = 0.0, 200.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if arl([det(kind, z, mid) for z in zs]) < target: lo = mid
        else: hi = mid
    return hi
def attacks(d):
    n = len(d); t0 = n // 2; t = np.arange(n - t0); out = {}
    for f in (0.5, 0.6, 0.7, 0.8, 0.9, 1.2, 1.5):
        fac = np.ones(n); fac[t0:] = f; out[f"step_x{f}"] = fac
    for r in (0.005, 0.01, 0.02):
        fac = np.ones(n); fac[t0:] = np.maximum(FLOOR, 1 - r * t); out[f"driftDown_{r}"] = fac
        fac = np.ones(n); fac[t0:] = np.minimum(CAP, 1 + r * t); out[f"driftUp_{r}"] = fac
    return out, t0
st = collections.defaultdict(lambda: collections.defaultdict(list)); folds = {}; qq = {"log": [], "lin": []}
chk_fpr = []
for ts in seeds:
    tr = [s for s in seeds if s != ts]
    trz_raw = [(np.log(d) - pl) for s in tr for _, d, pl, _, _ in series(data[s])]
    sl = mad(np.concatenate(trz_raw)); trz = [z / sl for z in trz_raw]
    sC2 = E9.global_scale([data[x] for x in tr])
    th = {(k, a): calib(k, trz, a) for k in KINDS for a in ARL}
    folds[ts] = {"s_log": sl, "thresholds": {f"{k}@{a}": v for (k, a), v in th.items()}}
    for tc, d, pl, pmin, pm in series(data[ts]):
        zc = (np.log(d) - pl) / sl; qq["log"] += list(zc); qq["lin"] += list((d - pm) / sC2)
        chk_fpr.append(float((-zc[len(d)//2:] > E9.TAU_S).mean()))
        atk, t0 = attacks(d)
        for (kind, a), h in th.items():
            tag = f"{kind}@{a}"
            al = det(kind, zc, h); st[tag]["clean_arl_test"].append(al)
            k0 = np.flatnonzero(al[t0:]); st[tag]["clean_first_alarm_delay"].append(float(k0[0]) if k0.size else np.nan)
            for name, fac in atk.items():
                o = d * fac; z = (np.log(o) - pl) / sl; al = det(kind, z, h)
                k1 = np.flatnonzero(al[t0:])
                if k1.size:
                    j = int(k1[0]); st[tag][name + "|delay"].append(float(j)); st[tag][name + "|bias"].append(float(abs(fac[t0 + j] - 1)))
                    st[tag][name + "|steer_before"].append(float((o[t0:t0 + j] < pmin[t0:t0 + j]).sum()))
                    st[tag][name + "|undetected"].append(0.0)
                else:
                    st[tag][name + "|undetected"].append(1.0); st[tag][name + "|steer_before"].append(float((o[t0:] < pmin[t0:]).sum()))
res = {"spec": "docs/thesis/B2_B3_cusum_spec_v0.md", "k": K, "folds": folds, "results": {}}
for tag, m in st.items():
    R = {"clean_ARL0_test": arl(m["clean_arl_test"]),
         "clean_first_alarm_delay_median": float(np.nanmedian(m["clean_first_alarm_delay"])),
         "clean_no_alarm_in_attack_half": float(np.mean(np.isnan(m["clean_first_alarm_delay"])))}
    for key, v in m.items():
        if key.startswith("clean"): continue
        R[key] = float(np.median(v)) if ("delay" in key or "bias" in key or "steer" in key) else float(np.mean(v))
    res["results"][tag] = R
b1 = json.load(open(os.path.join(os.path.dirname(E9.__file__), "../../../data/results/advisor_20261118/B1_log_onesided.json")))
res["check_V3_tau4_fpr"] = {"here": float(np.mean(chk_fpr)), "B1": b1["results"]["V3"]["clean_fpr"]["mean"]}
res["check_ok"] = abs(res["check_V3_tau4_fpr"]["here"] - res["check_V3_tau4_fpr"]["B1"]) < 1e-12
json.dump(res, open(sys.argv[1], "w"), indent=1)
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from statistics import NormalDist
fig, ax = plt.subplots(1, 2, figsize=(9, 4))
for a_, (lab, v) in zip(ax, (("linear residual / C-2 scale (V0)", qq["lin"]), ("log residual / log scale (V2)", qq["log"]))):
    v = np.sort(np.asarray(v)); q = np.array([NormalDist().inv_cdf((i - 0.5) / len(v)) for i in range(1, len(v) + 1)])
    a_.plot(q, v, ".", ms=2); a_.plot([-4, 4], [-4, 4], "k--", lw=1); a_.set_title(lab, fontsize=9); a_.set_xlabel("normal quantile"); a_.set_ylabel("z")
    a_.set_ylim(-8, 20)
fig.tight_layout(); fig.savefig(sys.argv[2], dpi=130)
print("check_ok", res["check_ok"], res["check_V3_tau4_fpr"])
