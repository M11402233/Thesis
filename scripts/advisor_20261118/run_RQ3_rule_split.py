#!/usr/bin/env python3
"""RQ3 rule split (docs/thesis/RQ3_rule_split_spec_v0.md). Run from xapps/verification/residuals with
ZT_DELAY_SOURCE=reconstructed ZT_FUSION_ORDER=severity ZT_DATASET=d30.  usage: run_RQ3_rule_split.py OUT.json"""
import os, sys, glob, json, collections
sys.path.insert(0, os.getcwd())
import numpy as np
import run_RQ3_decision_replay as RQ
X = RQ.X; DS = RQ.DS
assert os.environ.get("ZT_DELAY_SOURCE") == "reconstructed" and X.FUSION_ORDER == "severity"
files = sorted(glob.glob(os.path.join(RQ.DATA_DIR, DS.PATTERN)))
def cause(a):
    if a is None: return "no_annotation"
    if a.get("S_i") == "violated": return "S_i"
    if a.get("H_i_D1") in ("strong", "weak"): return "D1"
    if a.get("C_i") == "violated": return "C_i"
    return "other:" + str(a.get("rule_id"))
C = collections.defaultdict(lambda: collections.Counter())
overlap = collections.defaultdict(collections.Counter)
clean_block = {}   # (seed, cell, k) -> cause or None (admitted)
yield_clean = [0, 0]
for test in files:
    anchor = X.TrustAnchor([f for f in files if f != test]); base = RQ.load_windows(test); sd = DS.seed_of(test)
    td = RQ.true_delays(base); t0 = len(base) // 2; cells = sorted({c for d in td for c in d})
    ann0 = RQ.annotate(base, anchor, "uebound")
    for k in range(t0, len(base)):
        for c in cells:
            a = ann0.get(k, {}).get(c)
            if a is None: continue
            yield_clean[1] += 1; yield_clean[0] += int(a["admitted"])
            clean_block[(sd, c, k)] = None if a["admitted"] else cause(a)
    for name, kind, p in RQ.ATTACKS:
        if kind is None: continue
        for ac in cells:
            mod = RQ.apply_attack(base, ac, kind, p, t0); rep = RQ.true_delays(mod); ann = RQ.annotate(mod, anchor, "uebound")
            for k in range(t0, len(base)):
                truth = td[k]
                if len(truth) < 2 or ac not in rep[k]: continue
                opt = min(truth, key=truth.get)
                raw_choice = RQ.decide(rep[k], set(rep[k]))
                lure_opp = (raw_choice == ac and ac != opt)
                a = ann.get(k, {}).get(ac)
                adm = bool(a and a["admitted"])
                key = name
                C[key]["attacker_windows"] += 1
                if lure_opp: C[key]["lure_opportunity"] += 1
                if not adm:
                    cz = cause(a); C[key]["blocked"] += 1; C[key]["blocked|" + cz] += 1
                    if lure_opp: C[key]["lure_blocked"] += 1; C[key]["lure_blocked|" + cz] += 1
                    cb = clean_block.get((sd, ac, k), "absent")
                    C[key]["blocked_and_clean_also_blocked" if cb not in (None, "absent") else "blocked_but_clean_admitted"] += 1
                    if a:
                        overlap[key][(a.get("S_i") == "violated", a.get("H_i_D1") in ("strong", "weak"), a.get("C_i") == "violated")] += 1
    print("done", sd, flush=True)
out = {"spec": "docs/thesis/RQ3_rule_split_spec_v0.md", "yield_clean_attack_half": yield_clean[0] / yield_clean[1], "n_clean_node_windows": yield_clean[1],
       "clean_block_causes": dict(collections.Counter(v for v in clean_block.values())),
       "attacks": {k: dict(v) for k, v in C.items()},
       "overlap_SiD1Ci": {k: {str(t): n for t, n in v.items()} for k, v in overlap.items()}}
json.dump(out, open(sys.argv[1], "w"), indent=1, ensure_ascii=False)
print(json.dumps(out, indent=1, ensure_ascii=False)[:3000])
