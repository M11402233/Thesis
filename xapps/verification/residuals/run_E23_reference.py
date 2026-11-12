#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_E23_reference.py — 規格 docs/thesis/E23_external_reference_spec.md（逐 UE 外部參照之抽查，E_i 暫名）。

Ref-P：D-30 aux 之 DlE2PdcpStats（逐 UE PDCP 延遲）；Ref-0：只有截距之對照；Ref-O：假設性探測（真值 × exp(N(0,σ²))）。
階段：checks（資料對齊，不產生結果）／s0（乾淨資料：Ref-P 是否夠緊）／s1（固定攻擊者之抽查與准入組合）。

跑法（舊機器）：
  ZT_DATASET=d30 ZT_FUSION_ORDER=severity python3 xapps/verification/residuals/run_E23_reference.py --stage checks
"""
import os
import sys
import gzip
import json
import math
import time
import argparse
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run_E21_S0_membership as S0                                    # noqa: E402
from run_E21_S0_membership import X, DS, load_windows, replay, stop   # noqa: E402
from run_E21_S1_boff import relaxed                                   # noqa: E402
from run_RQ3_decision_replay import apply_attack, true_delays         # noqa: E402

OUT_DIR = os.path.join(S0.SEV_DIR, "E23")
S1_JSON = os.path.join(S0.SEV_DIR, "E21_S1", "E21_S1_boff.json")
QS = [0.1, 0.25, 0.5, 1.0]
SIGMAS = [0.02, 0.05, 0.10, 0.20]
FA_TARGET = 0.05
A_S0 = [0.892, 0.822, 0.8, 0.6]
ATTACKS = [("A0_step_0.6", "step", 0.60), ("A0_step_0.8", "step", 0.80), ("A0_drift_0.01", "drift", 0.01),
           ("step_0.892", "step", 0.892), ("step_0.822", "step", 0.822)]
S1_KEYS = ["A0_step_0.6", "A0_step_0.8", "A0_drift_0.01"]
MAIN_ATK = ["step_0.892", "A0_step_0.8"]


def load_pdcp(seed):
    out, wins, n = {}, set(), 0
    with gzip.open(DS.aux_path(seed, "DlE2PdcpStats.txt.gz"), "rt") as fh:
        fh.readline()
        for line in fh:
            p = line.rstrip("\n").split("\t")
            if len(p) < 11:
                continue
            w, i, nrx, d = int(float(p[0])), int(p[3]), int(p[8]), float(p[10]) * 1000.0
            n += 1
            wins.add(w)
            if nrx > 0 and d > 0:
                out[(w, i)] = d
    return out, wins, n


def load_all(with_replay):
    """逐 seed：窗序列、PDCP、mmWave 之 UE 紀錄 [(w, j, i, x, p 或 None)]、（選）anchor 與乾淨註記"""
    files = DS.files()
    if len(files) != 8:
        stop(f"seed 數 {len(files)} ≠ 8")
    ref = [json.loads(l) for l in open(S0.REF_ANN, encoding="utf-8")] if with_replay else None
    pos, seeds = 0, []
    for f in files:
        sd = DS.seed_of(f)
        base = load_windows(f)
        pd, pw, pn = load_pdcp(sd)
        if pw != set(range(300)) or pn != 9000:
            stop(f"E23-0 seed {sd}：PDCP 窗 {len(pw)}、列 {pn}（應為 300／9,000）")
        recs = [(w, j, i, cells[j][i], pd.get((w, i)))
                for w, cells in base for j in sorted(cells) if j != X.LTE_CELL for i in sorted(cells[j])]
        cov = sum(r[4] is not None and r[3] > 0 for r in recs) / len(recs)
        if cov < 0.99:
            stop(f"E23-0 seed {sd}：mmWave (UE, 窗) 之 PDCP 涵蓋率 {cov:.4f} < 0.99")
        s = {"seed": sd, "file": f, "base": base, "recs": recs, "cov": cov}
        if with_replay:
            s["anchor"] = X.TrustAnchor([g for g in files if g != f])
            ann, _ = replay(base, s["anchor"])
            seg = ref[pos:pos + len(ann)]
            pos += len(ann)
            if len(seg) != len(ann) or any(json.loads(json.dumps(a, ensure_ascii=False)) != r for a, r in zip(ann, seg)):
                stop(f"E23-1 seed {sd} 之乾淨回放與註記檔不同")
            s["ann"] = ann
        seeds.append(s)
        print(f"  seed {sd}：mmWave UE 紀錄 {len(recs)}，PDCP 涵蓋率 {cov:.4f}")
    if with_replay and pos != 15534:
        stop(f"E23-1 註記筆數 {pos} ≠ 15,534")
    print("  E23-0 ✓" + ("  E23-1（乾淨回放 15,534 筆）✓" if with_replay else ""))
    return seeds


def usable(r):
    return r[4] is not None and r[3] > 0


def fit(train, beta0):
    """log x = α + β·log p；beta0=True 為 Ref-0（只有截距）"""
    lx = np.array([math.log(r[3]) for s in train for r in s["recs"] if usable(r)])
    lp = np.array([math.log(r[4]) for s in train for r in s["recs"] if usable(r)])
    if beta0:
        return float(lx.mean()), 0.0, lx, lp
    b, a = np.polyfit(lp, lx, 1)
    return float(a), float(b), lx, lp


def node_stat(recs, efun, mask=None):
    """m(w, j) = 被抽中且可用之 UE 之 e 平均；回傳 {(w, j): m}"""
    acc = {}
    for n, r in enumerate(recs):
        if mask is not None and not mask[n]:
            continue
        e = efun(n, r)
        if e is None:
            continue
        t = acc.setdefault((r[0], r[1]), [0.0, 0])
        t[0] += e
        t[1] += 1
    return {k: v[0] / v[1] for k, v in acc.items()}


def theta_of(ms):
    v = np.abs(np.array([x for m in ms for x in m.values()]))
    return float(np.quantile(v, 1.0 - FA_TARGET))


def spearman(a, b):
    ra, rb = np.argsort(np.argsort(a)), np.argsort(np.argsort(b))
    return float(np.corrcoef(ra, rb)[0, 1])


def stage_s0(seeds):
    out = {}
    for ref, beta0 in (("Ref-P", False), ("Ref-0", True)):
        fa_n = fa_k = 0
        det = {a: 0 for a in A_S0}
        folds = []
        for s in seeds:
            train = [t for t in seeds if t is not s]
            al, be, lx, lp = fit(train, beta0)
            ef = lambda n, r, al=al, be=be: (math.log(r[3]) - (al + be * math.log(r[4]))) if usable(r) else None  # noqa: E731
            th = theta_of([node_stat(t["recs"], ef) for t in train])
            m = node_stat(s["recs"], ef)
            v = np.array(list(m.values()))
            if any(abs(x + math.log(1.0)) != abs(x) for x in v):
                stop("E23-2 a=1 時 m′ ≠ m")
            fa_n += len(v)
            fa_k += int((np.abs(v) >= th).sum())
            for a in A_S0:
                det[a] += int((np.abs(v + math.log(a)) >= th).sum())
            res = lx - (al + be * lp)
            folds.append({"seed": s["seed"], "alpha": al, "beta": be, "theta": th,
                          "R2": float(1 - res.var() / lx.var()), "spearman": spearman(lp, lx),
                          "resid_scale": float(1.4826 * np.median(np.abs(res - np.median(res))))})
        r = {"n": fa_n, "FA": fa_k / fa_n, "DET": {str(a): det[a] / fa_n for a in A_S0}, "folds": folds}
        out[ref] = r
        th = [f["theta"] for f in folds]
        print(f"  {ref}：β [{min(f['beta'] for f in folds):.3f}, {max(f['beta'] for f in folds):.3f}]  "
              f"R² [{min(f['R2'] for f in folds):.3f}, {max(f['R2'] for f in folds):.3f}]  "
              f"Spearman [{min(f['spearman'] for f in folds):.3f}, {max(f['spearman'] for f in folds):.3f}]  "
              f"θ [{min(th):.3f}, {max(th):.3f}]（倍數 ×{math.exp(-max(th)):.3f}～×{math.exp(max(th)):.3f}）")
        print(f"    (節點, 窗) {fa_n}  FA {r['FA']:.3f}  " + "  ".join(f"DET(×{a}) {r['DET'][str(a)]:.3f}" for a in A_S0))
    p = out["Ref-P"]
    verdict = ("可行" if p["FA"] <= 0.10 and p["DET"]["0.892"] >= 0.80
               else "不可行" if p["DET"]["0.892"] < 0.50 or p["FA"] > 0.20 else "不確定")
    print(f"  E23-2 ✓   S0 判定（Ref-P）：{verdict}；Ref-P − Ref-0 之 DET(×0.892) 差 "
          f"{p['DET']['0.892'] - out['Ref-0']['DET']['0.892']:+.3f}")
    out["verdict"] = verdict
    return out


def stage_s1(seeds):
    s1 = json.load(open(S1_JSON, encoding="utf-8"))["results"]
    # ---- 回放（與參照設定無關，只做一次）----
    clean, tam = [], {name: [] for name, _, _ in ATTACKS}
    for s in seeds:
        base, anchor = s["base"], s["anchor"]
        clean += [(s["seed"], a["window"], a["node"], a["decision"] == "trusted", relaxed(a)) for a in s["ann"]]
        t0 = len(base) // 2
        cells = sorted({c for d in true_delays(base) for c in d})
        for name, kind, param in ATTACKS:
            for cell in cells:
                mod = apply_attack(base, cell, kind, param, t0)
                for a in replay(mod, anchor)[0]:
                    k, j = a["window"], a["node"]
                    if (j == cell and k >= t0 and cell in mod[k][1]
                            and any(mod[k][1][cell][i] != base[k][1][cell][i] for i in mod[k][1][cell])):
                        ak = param if kind == "step" else max(0.05, 1.0 - param * (k - t0))
                        tam[name].append((s["seed"], k, j, a["decision"] == "trusted", relaxed(a), ak))
        print(f"  seed {s['seed']} 回放完成")
    nC = len(clean)
    fb0 = 1 - sum(t for *_, t, r in clean) / nC
    fb1 = 1 - sum(t or r for *_, t, r in clean) / nC
    if abs(fb0 - s1["clean"]["FB_strict_rule"]) > 1e-12 or abs(fb1 - s1["clean"]["FB_strict_boff"]) > 1e-12:
        stop(f"E23-1 FB {fb0}／{fb1} 未重現 E21-S1")
    for name in S1_KEYS:
        n = len(tam[name])
        m0 = sum(t for *_, t, r, a in tam[name]) / n
        m1 = sum(t or r for *_, t, r, a in tam[name]) / n
        d = s1["delay"][name]
        if n != d["tampered"] or abs(m0 - d["MF_strict_rule"]) > 1e-12 or abs(m1 - d["MF_strict_boff"]) > 1e-12:
            stop(f"E23-1 {name}：{n}／{m0}／{m1} 未重現 E21-S1")
    print("  E23-1 ✓（FB 與三種延遲攻擊之 MF 重現 E21-S1）")

    # ---- E23-3：Ref-O、σ=0、q=1 ----
    for s in seeds:
        m = node_stat(s["recs"], lambda n, r: 0.0 if r[3] > 0 else None)
        if any(x != 0.0 for x in m.values()):
            stop("E23-3 σ=0 時乾淨 m ≠ 0")
    for name in tam:
        if any(math.log(a) == 0.0 for *_, a in tam[name]):
            stop(f"E23-3 {name} 有 a=1 之竄改紀錄")
    print("  E23-3 ✓")

    # ---- 各參照設定 ----
    cfgs = [("Ref-P", None)] + [("Ref-O", sg) for sg in SIGMAS]
    results = {}
    for ref, sg in cfgs:
        for q in QS:
            stats = {}
            for s in seeds:
                sdi = int(s["seed"])
                mask = (np.random.default_rng([23, sdi, int(q * 1000)]).random(len(s["recs"])) < q) if q < 1 else None
                s["_mask"] = mask
                if ref == "Ref-O":
                    s["_eps"] = np.random.default_rng([2300, sdi, int(sg * 1000)]).normal(0.0, sg, len(s["recs"]))
            for s in seeds:
                train = [t for t in seeds if t is not s]
                if ref == "Ref-P":
                    al, be, _, _ = fit(train, False)
                    mk = lambda t: node_stat(t["recs"], lambda n, r: (math.log(r[3]) - (al + be * math.log(r[4])))  # noqa: E731
                                             if usable(r) else None, t["_mask"])
                else:
                    mk = lambda t: node_stat(t["recs"], lambda n, r, t=t: (-float(t["_eps"][n])) if r[3] > 0 else None,  # noqa: E731
                                             t["_mask"])
                th = theta_of([mk(t) for t in train])
                stats[s["seed"]] = (mk(s), th)

            def flag(sd, w, j, shift=0.0):
                m, th = stats[sd]
                x = m.get((w, j))
                return x is not None and abs(x + shift) >= th

            cov = sum((w, j) in stats[sd][0] for sd, w, j, *_ in clean) / nC
            fl = [flag(sd, w, j) for sd, w, j, *_ in clean]
            r = {"coverage": cov, "E_FA": sum(fl) / nC,
                 "FB": {"V0": fb0, "V1": fb1,
                        "V0+E": 1 - sum(t and not f for (*_, t, rr), f in zip(clean, fl)) / nC,
                        "V1+E": 1 - sum((t or rr) and not f for (*_, t, rr), f in zip(clean, fl)) / nC,
                        "V1+E_failclosed": 1 - sum((t or rr) and not f and (w, j) in stats[sd][0]
                                                   for (sd, w, j, t, rr), f in zip(clean, fl)) / nC},
                 "attacks": {}}
            for name in tam:
                T = tam[name]
                n = len(T)
                ft = [flag(sd, k, j, math.log(a)) for sd, k, j, t, rr, a in T]
                r["attacks"][name] = {
                    "n": n, "E_DET": sum(ft) / n,
                    "MF": {"V0": sum(t for *_, t, rr, a in T) / n, "V1": sum(t or rr for *_, t, rr, a in T) / n,
                           "V0+E": sum(t and not f for (*_, t, rr, a), f in zip(T, ft)) / n,
                           "V1+E": sum((t or rr) and not f for (*_, t, rr, a), f in zip(T, ft)) / n}}
            r["effective"] = bool(r["FB"]["V1+E"] <= 0.10
                                  and all(r["attacks"][k]["MF"]["V1+E"] <= 0.20 for k in MAIN_ATK))
            key = f"{ref}|sigma={sg}|q={q}" if sg is not None else f"{ref}|q={q}"
            results[key] = r
            print(f"  {key:26s} 涵蓋 {cov:.3f}  E_FA {r['E_FA']:.3f}  FB V1+E {r['FB']['V1+E']:.3f}  "
                  + "  ".join(f"{k}: DET {r['attacks'][k]['E_DET']:.3f} MF(V1+E) {r['attacks'][k]['MF']['V1+E']:.3f}"
                              for k in MAIN_ATK) + ("  ✓有效" if r["effective"] else ""))
    return {"FB_V0": fb0, "FB_V1": fb1, "configs": results}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["checks", "s0", "s1"], required=True)
    args = ap.parse_args()
    t_start = time.time()
    if DS.NAME != "d30":
        stop("須 ZT_DATASET=d30")
    print(f"── E23 {args.stage} ──")
    seeds = load_all(with_replay=(args.stage != "s0"))
    if args.stage == "checks":
        print(f"檢查完成（{time.time() - t_start:.0f} s）；未產生結果、未寫輸出。")
        return
    res = stage_s0(seeds) if args.stage == "s0" else stage_s1(seeds)
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, f"E23_{args.stage}.json")
    json.dump({"spec": "docs/thesis/E23_external_reference_spec.md", "stage": args.stage, "results": res,
               "elapsed_s": time.time() - t_start}, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"寫入 {out}（{time.time() - t_start:.0f} s）")


if __name__ == "__main__":
    main()
