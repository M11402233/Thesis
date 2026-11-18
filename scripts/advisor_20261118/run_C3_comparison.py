#!/usr/bin/env python3
"""C3 v1 (spec docs/thesis/C3_same_condition_comparison_spec_v0.md §7 post-hoc v1: LSTM threshold from held-out calibration seed; clean_any / lift metrics). Run from xapps/verification/residuals.
usage: ZT_DELAY_SOURCE=reconstructed ZT_DATASET=d30 python3 run_C3_comparison.py OUT.json"""
import os, sys, glob, json, time, collections, numpy as np
os.environ.setdefault("ZT_DELAY_SOURCE", "reconstructed"); os.environ.setdefault("ZT_DATASET", "d30")
sys.path.insert(0, os.getcwd())
import run_E9_operating_regime as E9, datasets as DS
import torch, torch.nn as nn
assert os.environ["ZT_DELAY_SOURCE"] == "reconstructed" and os.environ["ZT_DATASET"] == "d30"
torch.set_num_threads(4); torch.use_deterministic_algorithms(True)
SEQ, HIDDEN, LAYERS, EPOCHS, BATCH, LR = 10, 64, 2, 25, 256, 1e-3
BASE_SEED, FIT_GATE, W_HIST = 20261118, 0.80, 10
K_ON = {"M7": 5, "M8": 3}
AF = {"M7": [1.2, 1.3, 1.4, 1.5], "M8": [0.6, 0.7, 0.8, 0.9, 1.2, 1.3, 1.4, 1.5]}
K_CU, ARL0 = 0.5, 1000
FLOOR, CAP = 0.5, 2.0
OUT = sys.argv[1]
B1J = os.path.join(os.path.dirname(OUT), "B1_log_onesided.json")
T0 = time.time()

def stop(m):
    print("✗ 檢查失敗：", m, "\n停止，不寫輸出。"); sys.exit(2)

files = sorted(glob.glob(os.path.join(E9.DATA_DIR, DS.PATTERN)))
seeds = [os.path.basename(f).split("seed")[-1][:4] for f in files]
data = {s: E9.load_cell_delay(f) for s, f in zip(seeds, files)}

def samples(Wd):
    cells = sorted({c for w in Wd for c in Wd[w]})
    for tc in cells:
        idx = [w for w in sorted(Wd) if tc in Wd[w] and len([c for c in Wd[w] if c != tc]) >= E9.MIN_NEIGHBOR]
        if len(idx) < E9.MIN_LEN: continue
        d = np.array([Wd[w][tc] for w in idx]); pm = np.array([np.median([Wd[w][c] for c in Wd[w] if c != tc]) for w in idx])
        pl = np.array([np.median(np.log([Wd[w][c] for c in Wd[w] if c != tc])) for w in idx])
        yield tc, d, pm, pl
SM = {s: list(samples(data[s])) for s in seeds}
if len(seeds) != 8 or sum(len(v) for v in SM.values()) != 56: stop(f"C3-0 seeds {len(seeds)} samples {sum(len(v) for v in SM.values())}")

def mad(x): x = np.asarray(x); return 1.4826 * (float(np.median(np.abs(x - np.median(x)))) + 1e-9)

def attacks(d):
    n = len(d); t0 = n // 2; t = np.arange(n - t0); out = {}
    for f in (1.2, 1.3, 1.5, 0.9, 0.8, 0.6):
        fac = np.ones(n); fac[t0:] = f; out[f"step_x{f}"] = fac
    fac = np.ones(n); fac[t0:] = np.maximum(FLOOR, 1 - 0.01 * t); out["driftDown_0.01"] = fac
    fac = np.ones(n); fac[t0:] = np.minimum(CAP, 1 + 0.01 * t); out["driftUpCap_0.01"] = fac
    return out, t0

def selfref(o):
    r = np.full(len(o), np.nan)
    for t in range(W_HIST, len(o)): r[t] = o[t] - np.median(o[t - W_HIST:t])
    return r

def cusum(z, h, side):
    s = 0.0; al = np.zeros(len(z), bool)
    for t, x in enumerate(z):
        s = max(0.0, s + (x if side == "up" else -x) - K_CU)
        if s > h: al[t] = True; s = 0.0
    return al

def calib_cusum(zs, side):
    lo, hi = 0.0, 200.0
    for _ in range(40):
        mid = (lo + hi) / 2
        n = sum(len(z) for z in zs); m = sum(int(cusum(z, mid, side).sum()) for z in zs)
        if (n / m if m else float("inf")) < ARL0: lo = mid
        else: hi = mid
    return hi

class Clf(nn.Module):
    def __init__(self, ch):
        super().__init__(); self.lstm = nn.LSTM(ch, HIDDEN, num_layers=LAYERS, batch_first=True); self.head = nn.Linear(HIDDEN, 1)
    def forward(self, x):
        h, _ = self.lstm(x); return self.head(h[:, -1, :]).squeeze(-1)

def feats(o, pl, med, s, sl, ch):
    lv = (o - med) / s
    chans = [lv] if ch == 1 else [lv, (np.log(o) - pl) / sl]
    st = np.stack(chans, -1).astype(np.float32)
    idx = np.arange(SEQ - 1, len(o))
    return idx, np.stack([st[t - SEQ + 1:t + 1] for t in idx])

def predict(m, X):
    with torch.no_grad():
        return torch.sigmoid(m(torch.from_numpy(X))).numpy()

def predict_logit(m, X):  # v2: threshold on logits (sigmoid saturates to 1.0 in float32 -> ties, v1 thr = 1.0)
    with torch.no_grad():
        return m(torch.from_numpy(X)).numpy()

def train_lstm(tag, trs, cals, med, s, sl, seed):
    ch = 1 if tag == "M7" else 2
    rng = np.random.default_rng(seed)
    Xs, ys, cal = [], [], []
    for d, pm, pl in trs:
        n = len(d)
        idx, X = feats(d, pl, med, s, sl, ch); Xs.append(X); ys.append(np.zeros(len(idx), np.float32)); cal.append(X[idx >= n // 2])
        for af in AF[tag]:
            for _ in range(K_ON[tag]):
                w0 = int(rng.integers(SEQ, n - SEQ)); o = d.copy(); o[w0:] *= af
                idx, X = feats(o, pl, med, s, sl, ch); Xs.append(X); ys.append((idx >= w0).astype(np.float32))
    X = np.concatenate(Xs); y = np.concatenate(ys)
    torch.manual_seed(seed); m = Clf(ch)
    opt = torch.optim.Adam(m.parameters(), lr=LR)
    pos = float(y.sum()); lossf = nn.BCEWithLogitsLoss(pos_weight=torch.tensor((len(y) - pos) / max(pos, 1.0)))
    Xt, yt = torch.from_numpy(X), torch.from_numpy(y); g = torch.Generator().manual_seed(seed)
    for _ in range(EPOCHS):
        perm = torch.randperm(len(yt), generator=g); m.train()
        for i in range(0, len(perm), BATCH):
            b = perm[i:i + BATCH]; opt.zero_grad(); lossf(m(Xt[b]), yt[b]).backward(); opt.step()
    m.eval(); p = predict(m, X)
    tpr = float((p[y == 1] > 0.5).mean()); tnr = float((p[y == 0] <= 0.5).mean())
    thr_tr = float(np.quantile(predict_logit(m, np.concatenate(cal)), 0.99))
    hc = []
    for d, pm, pl in cals:
        idx, X = feats(d, pl, med, s, sl, ch); hc.append(predict_logit(m, X[idx >= len(d) // 2]))
    hcc = np.concatenate(hc); thr = float(np.quantile(hcc, 0.99))
    sat32 = float((torch.sigmoid(torch.from_numpy(hcc)).numpy() >= 1.0).mean())
    return m, thr, {"balanced_acc": (tpr + tnr) / 2, "tpr": tpr, "tnr": tnr, "n_train": int(len(y)), "thr_1pct_heldout": thr, "thr_1pct_trainfit_v0_logit": thr_tr, "thr_space": "logit", "cal_frac_sigmoid_saturated_f32": sat32, "cal_frac_logit_gt0": float((hcc > 0).mean()), "n_cal_windows": int(sum(len(x) for x in hc))}

METHODS = ["M1_range", "M2_selfref", "M3_peer_lin", "M4_peer_log2", "M5_peer_log_low", "M6_cusum_low", "M6_cusum_up", "M7_prior_lstm", "M8_sup_lstm"]
st = {m: collections.defaultdict(lambda: collections.defaultdict(list)) for m in METHODS}
folds = {}
for fi, ts in enumerate(seeds):
    tr = [s for s in seeds if s != ts]; trs = [(d, pm, pl) for s in tr for _, d, pm, pl in SM[s]]
    sV0 = E9.global_scale([data[x] for x in tr])
    lgraw = np.concatenate([np.log(d) - pl for d, pm, pl in trs]); sl = mad(lgraw)
    sT = mad(np.concatenate([selfref(d)[W_HIST:] for d, _, _ in trs]))
    alld = np.concatenate([d for d, _, _ in trs]); lo, hi = float(alld.min()), float(alld.max())
    med = float(np.median(alld))
    def half(f): return np.concatenate([f(d, pm, pl)[len(d) // 2:] for d, pm, pl in trs])
    scorers = {
        "M2_selfref": lambda o, pm, pl: np.abs(selfref(o)) / sT,
        "M3_peer_lin": lambda o, pm, pl: np.abs(o - pm) / sV0,
        "M4_peer_log2": lambda o, pm, pl: np.abs(np.log(o) - pl) / sl,
        "M5_peer_log_low": lambda o, pm, pl: -(np.log(o) - pl) / sl}
    thr = {k: float(np.nanquantile(half(f), 0.99)) for k, f in scorers.items()}
    zc = [(np.log(d) - pl) / sl for d, pm, pl in trs]
    h = {"low": calib_cusum(zc, "low"), "up": calib_cusum(zc, "up")}
    cs = seeds[(fi + 1) % len(seeds)]
    trs_l = [(d, pm, pl) for s in tr if s != cs for _, d, pm, pl in SM[s]]
    cals = [(d, pm, pl) for _, d, pm, pl in SM[cs]]
    models = {}
    for tag in ("M7", "M8"):
        t1 = time.time(); models[tag] = train_lstm(tag, trs_l, cals, med, sV0, sl, BASE_SEED + 1000 * fi + (0 if tag == "M7" else 1))
        print(f"  fold {ts} {tag}: fit {models[tag][2]['balanced_acc']:.3f}  thr {models[tag][1]:.4f}  ({time.time() - t1:.0f} s)", flush=True)
    folds[ts] = {"range": [lo, hi], "thr": thr, "cusum_h": h, "scales": {"V0": sV0, "log": sl, "selfref": sT},
                 "fit": {t: models[t][2] for t in models}, "lstm_cal_seed": cs}

    def alarms(meth, o, pm, pl):
        if meth == "M1_range": return (o < lo) | (o > hi)
        if meth in scorers: z = scorers[meth](o, pm, pl); return np.nan_to_num(z, nan=-np.inf) > thr[meth]
        if meth.startswith("M6"): return cusum((np.log(o) - pl) / sl, h["low" if meth.endswith("low") else "up"], "low" if meth.endswith("low") else "up")
        tag = meth[:2]; m, th, _ = models[tag]
        idx, X = feats(o, pl, med, sV0, sl, 1 if tag == "M7" else 2)
        a = np.zeros(len(o), bool); a[idx] = predict_logit(m, X) > th; return a
    for _, d, pm, pl in SM[ts]:
        n = len(d); t0 = n // 2; cache = {}
        for meth in METHODS:
            ca = alarms(meth, d, pm, pl)[t0:]
            st[meth]["clean_fpr"][ts].append(float(ca.mean())); st[meth]["clean_any"][ts].append(float(ca.any()))
            cache[meth] = float(ca.mean())
            if meth.startswith("M6"): st[meth]["clean_alarms"][ts].append((int(alarms(meth, d, pm, pl).sum()), n))
        atk, t0 = attacks(d)
        for name, fac in atk.items():
            o = d * fac
            for meth in METHODS:
                hit = alarms(meth, o, pm, pl)[t0:]
                st[meth][name + "|rate"][ts].append(float(hit.mean())); st[meth][name + "|lift"][ts].append(float(hit.mean()) - cache[meth])
                st[meth][name + "|undetected"][ts].append(0.0 if hit.any() else 1.0)
                if hit.any(): st[meth][name + "|delay"][ts].append(float(np.argmax(hit)))
    print(f"fold {ts} done ({time.time() - T0:.0f} s)", flush=True)

def agg(by):
    allv = [x for l in by.values() for x in l]; per = {s: float(np.mean(l)) for s, l in by.items() if l}
    return {"mean": float(np.mean(allv)) if allv else None, "median": float(np.median(allv)) if allv else None, "n": len(allv),
            "seed_min": min(per.values()) if per else None, "seed_max": max(per.values()) if per else None}
res = {}
for meth in METHODS:
    res[meth] = {}
    for k, by in st[meth].items():
        if k == "clean_alarms":
            a = sum(x for l in by.values() for x, _ in l); n = sum(y for l in by.values() for _, y in l)
            res[meth]["ARL0_test"] = n / a if a else None
        else:
            res[meth][k] = agg(by)
# C3-1: reproduce B1 V0e / V3e
b1 = json.load(open(B1J))["results"]
bad = []
for meth, v in (("M3_peer_lin", "V0e"), ("M5_peer_log_low", "V3e")):
    for k in res[meth]:
        if k in b1[v] and k != "ARL0_test":
            for q in ("mean", "n"):
                if abs((res[meth][k][q] or 0) - (b1[v][k][q] or 0)) > 1e-12: bad.append((meth, k, q, res[meth][k][q], b1[v][k][q]))
if bad: stop(f"C3-1 未重現 B1：{bad[:5]}")
gate = {t: all(folds[s]["fit"][t]["balanced_acc"] >= FIT_GATE for s in seeds) for t in ("M7", "M8")}
json.dump({"spec": "docs/thesis/C3_same_condition_comparison_spec_v0.md", "version": "v2", "checks": {"C3-0": "pass", "C3-1": "pass", "C3-2_fit_gate": gate},
           "config": {"SEQ": SEQ, "HIDDEN": HIDDEN, "LAYERS": LAYERS, "EPOCHS": EPOCHS, "K_ON": K_ON, "AF": AF, "ARL0": ARL0, "K_CU": K_CU},
           "folds": folds, "results": res, "elapsed_s": round(time.time() - T0, 1)}, open(OUT, "w"), indent=1)
print("C3-1 ✓  C3-2 fit gate:", gate)
for meth in METHODS:
    r = res[meth]
    print(f"{meth:16s} FPR {r['clean_fpr']['mean']:.4f} [{r['clean_fpr']['seed_min']:.4f},{r['clean_fpr']['seed_max']:.4f}]" + (f" ARL0 {r.get('ARL0_test')}" if 'ARL0_test' in r else "") + " | " +
          "  ".join(f"{a.replace('step_','').replace('drift','d')}: {r[a+'|rate']['mean']:.3f}/{r[a+'|undetected']['mean']:.2f}/{r[a+'|delay']['median'] if r.get(a+'|delay', {}).get('n') else '-'}" for a in attacks(np.ones(10))[0]))
print(f"寫入 {OUT}（{time.time() - T0:.0f} s）")
