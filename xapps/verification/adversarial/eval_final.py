# -*- coding: utf-8 -*-
"""eval_final.py — PSRO 最終偵測端之評估（規格 docs/thesis/E19_eval_final_spec.md v1）。

階段（--stage）：
  checks  一致性檢查 V1、V2、V3、V4、V5、B2-1、B2-2、B3-1、B3-2、E9c-0；任一失敗即停（不寫結果）
  abr     對 6 組之最終 σ_D 訓練攻擊者最佳回應 A-BR（重用 psro._train_job；可續跑）
  eval    全部 (偵測端, 攻擊者) 對、乾淨評估、E9c 共模；結果逐對快取於 pairs.json（可續跑）
  report  混合指標、最壞情形、基線前緣與 §6 判準 → eval_final.json、圖

判定一律經 game_core（→ zt_kpm_xapp.fuse_detail）；攻擊 episode 之執行與 psro._eval_job 相同
（T0Cache → run_episode），另記錄每個 episode 之偵測延遲。V2 逐位核對與 PSRO 報酬表同口徑。

用法：ZT_DATASET=d30 ZT_FUSION_ORDER=severity python eval_final.py --stage checks --workers 12
"""
import os
import sys
import json
import time
import copy
import argparse
import subprocess
import multiprocessing as mp
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
PSRO_DIR = os.path.join(ROOT, "data", "results", "d30", "drl", "psro")
OUT = os.path.join(ROOT, "data", "results", "d30", "drl", "eval_final")
SEV = os.path.join(ROOT, "data", "results", "d30_fusion_order", "severity")
SPEC = "docs/thesis/E19_eval_final_spec.md v1"
RUNS = [(lv, t) for lv in ("O-full", "O-outcome") for t in (0, 1, 2)]
FROZEN_TAU = (2.0, 3.0)
B2_LS = [2, 3, 5, 10]
B3_TAU = [(2.0, 3.0), (3.0, 4.0), (4.0, 5.0), (6.0, 7.0)]
W_ON = 150                                                   # E9c（run_E9c_common_mode.W_ON）
CM_GRID = [("step", 1.1), ("step", 1.2), ("step", 1.3), ("step", 1.5), ("drift", 0.005), ("drift", 0.01), ("drift", 0.02)]
CM_MAIN = ("step", 1.1)
FOLDS = list(range(8))


def rid(lv, t):
    return f"{lv}/t{t}"


def load_state(lv, t):
    return json.load(open(os.path.join(PSRO_DIR, lv, f"t{t}", "state.json"), encoding="utf-8"))


# ----------------------------------------------------------------------------
# 工作行程
_W = {}


def _init(tau):
    import torch
    torch.set_num_threads(1)
    import game_core as G
    import env_kpm_game as E
    G.X.TAU_H_WARN, G.X.TAU_H_REJECT = tau                   # B3：只影響 SeedData 建立時之 D1 證據（run_xapp）
    _W.update(G=G, E=E, ds=G.DataStore(), cache=G.T0Cache(maxsize=1024), models={}, tau=tau)


class B2Persist:
    """E12 R2_SI_PERSIST：連續 L_S 個實際秒 S_i violated，且下限規則為 R2_SI_ALONE → rejected。
    連續計數由 ep.hist 還原（hist 之 (S_i 可得, min(z,4τ)/τ)；violated ⇔ z > τ_S ⇔ 第二欄 > 1）。"""

    def __init__(self, L, name):
        self.L, self.name = L, name

    def __call__(self, ep, j):
        G = _W["G"]
        base = G.det_floor_policy(ep, j)
        if ep.floor[j][1] != "R2_SI_ALONE" or ep.info[j]["si"] != "violated":
            return base
        c, k = 1, ep.k - 1
        while c < self.L:
            rec = ep.hist[j].get(k)
            if rec is None or not rec[0] or not rec[1] > 1.0:
                break
            c, k = c + 1, k - 1
        return 2 if c >= self.L else base


def _get(s, fold):
    key = (s["id"], fold)
    M = _W["models"]
    if key in M:
        return M[key]
    G, E = _W["G"], _W["E"]
    k = s["kind"]
    if k == "floor":
        o = E.FloorDetector()
        o.name = s["id"]
    elif k == "b2":
        o = B2Persist(s["L_S"], s["id"])
    elif k == "scripted":
        o = G.ScriptedAttack(s["attack"], s["param"])
    elif k == "maskppo":
        from sb3_contrib import MaskablePPO
        o = E.LearnedDetector(MaskablePPO.load(s["paths"][str(fold)], device="cpu"), f"{s['id']}@f{fold}")
    elif k == "ppo":
        from stable_baselines3 import PPO
        o = E.LearnedAttacker(PPO.load(s["paths"][str(fold)], device="cpu"), s["level"], f"{s['id']}@f{fold}")
    else:
        raise ValueError(k)
    M[key] = o
    return o


def _delays(ep):
    """自第一個竄改秒起至被攻陷節點首次判非 trusted／rejected 之秒數；未發生 = None（截尾）"""
    first = next((r["k"] for r in ep.atk_log if r["present"] and r["reported"] != r["true"]), None)
    if first is None:
        return None, None, None
    d_nt = d_rej = None
    for k in range(first, ep.sd.n):
        f = ep.final.get((k, ep.atk))
        if f is None:
            continue
        if d_nt is None and f[0] != "trusted":
            d_nt = k - first
        if f[0] == "rejected":
            d_rej = k - first
            break
    return first, d_nt, d_rej


def _cm_sd(sd, kind, mag):
    G = _W["G"]
    s = copy.copy(sd)
    wins = []
    for k, (w, cells) in enumerate(sd.windows):
        if w >= W_ON:
            f = mag if kind == "step" else 1.0 + mag * (w - W_ON)
            cells = {c: ({i: v * f for i, v in u.items()} if c != G.LTE else u) for c, u in cells.items()}
        wins.append((w, cells))
    s.windows = wins
    s.truth = [{c: float(np.mean(list(v.values()))) for c, v in cells.items() if c != G.LTE and v} for _, cells in wins]
    return s


def _job(args):
    """args = (det, atk 或 None, fold, cm 或 None)。回傳 {'tot': 計數, 'eps': [[cell, first, d_nt, d_rej]], 'post': {...}}"""
    dS, aS, fold, cm = args
    G, E, ds = _W["G"], _W["E"], _W["ds"]
    sd = ds.get(ds.files[fold])                              # 評估 anchor = 其餘 7 seed
    det = _get(dS, fold)
    if aS is None:
        sdx = sd if cm is None else _cm_sd(sd, *cm)
        ep = G.run_episode(G.Episode(sdx, None), det)
        post = {"n": 0, "rej": 0, "nontrust": 0}
        for (k, j), f in ep.final.items():
            if sdx.windows[k][0] >= W_ON:
                post["n"] += 1; post["rej"] += f[0] == "rejected"; post["nontrust"] += f[0] != "trusted"
        return {"tot": dict(ep.stats), "post": post, "seed": sd.seed}
    atk = _get(aS, fold)
    tot, eps = {}, []
    for cell in sd.cells_all:
        ep = _W["cache"].get(sd, cell, det, E.new_episode)
        G.run_episode(ep, det, atk)
        for k, v in ep.stats.items():
            tot[k] = tot.get(k, 0) + v
        eps.append([cell, *_delays(ep)])
    return {"tot": tot, "eps": eps, "seed": sd.seed}


# ----------------------------------------------------------------------------
# 策略描述
def strategies():
    """回傳 (dets, atks, runs)：dets/atks 為 id → 描述；runs 為 id → {sigma_D, sigma_A（皆 id → 機率）}"""
    dets = {"D0": {"id": "D0", "kind": "floor", "tau": list(FROZEN_TAU)}}
    for L in B2_LS:
        dets[f"B2_L{L}"] = {"id": f"B2_L{L}", "kind": "b2", "L_S": L, "tau": list(FROZEN_TAU)}
    for tau in B3_TAU:
        i = f"B3_tau{tau[0]:g}_{tau[1]:g}"
        dets[i] = {"id": i, "kind": "floor", "tau": list(tau)}
    atks, runs = {}, {}
    for lv, t in RUNS:
        st, r = load_state(lv, t), rid(lv, t)
        dmap, amap = {}, {}
        for s in st["D"]:
            if s["kind"] == "floor":
                dmap[s["name"]] = "D0"
            else:
                i = f"{r}:{s['name']}"
                dets[i] = {"id": i, "kind": "maskppo", "paths": s["paths"], "tau": list(FROZEN_TAU), "run": r}
                dmap[s["name"]] = i
        for s in st["A"]:
            if s["kind"] == "scripted":
                i = s["name"]
                atks[i] = {"id": i, "kind": "scripted", "attack": s["attack"], "param": s["param"]}
            else:
                i = f"{r}:{s['name']}"
                atks[i] = {"id": i, "kind": "ppo", "level": s["level"], "paths": s["paths"], "run": r}
            amap[s["name"]] = i
        sD = {dmap[s["name"]]: p for s, p in zip(st["D"], st["sigma"]["D"]) if p > 0}
        sA = {amap[s["name"]]: p for s, p in zip(st["A"], st["sigma"]["A"]) if p > 0}
        abr = os.path.join(OUT, "abr", lv, f"t{t}", "ABR")
        if all(os.path.exists(f"{abr}_f{f}.zip") for f in FOLDS):
            atks[f"{r}:ABR"] = {"id": f"{r}:ABR", "kind": "ppo", "level": lv,
                                "paths": {str(f): f"{abr}_f{f}" for f in FOLDS}, "run": r}
        runs[r] = {"sigma_D": sD, "sigma_A": sA, "state": st, "dmap": dmap, "amap": amap,
                   "n_rounds": len(st["history"]), "stop": st.get("stop")}
    return dets, atks, runs


# ----------------------------------------------------------------------------
class Runner:
    """依 τ 分組之工作行程池；結果逐對合併（8 fold）並快取。"""

    def __init__(self, workers, cache_path=None):
        self.workers, self.pools = workers, {}
        self.cache_path = cache_path
        self.cache = json.load(open(cache_path, encoding="utf-8")) if cache_path and os.path.exists(cache_path) else {}

    def pool(self, tau):
        tau = tuple(tau)
        if tau not in self.pools:
            self.pools[tau] = mp.Pool(self.workers, initializer=_init, initargs=(tau,))
        return self.pools[tau]

    @staticmethod
    def key(d, a, cm):
        return f"{d['id']}|{a['id'] if a else 'CLEAN'}|{'' if cm is None else f'{cm[0]}{cm[1]:g}'}"

    def run(self, pairs, use_cache=True):
        """pairs = [(det, atk|None, cm|None)] → {key: 合併結果}"""
        todo = [p for p in pairs if not (use_cache and self.key(*p) in self.cache)]
        by_tau = {}
        for p in todo:
            by_tau.setdefault(tuple(p[0]["tau"]), []).append(p)
        out = {}
        for tau, ps in by_tau.items():
            t = time.time()
            jobs = [(d, a, f, cm) for d, a, cm in ps for f in FOLDS]
            res = self.pool(tau).map(_job, jobs, chunksize=1)
            for i, p in enumerate(ps):
                rs = res[i * len(FOLDS):(i + 1) * len(FOLDS)]
                tot, eps, per_seed, post = {}, [], {}, {"n": 0, "rej": 0, "nontrust": 0}
                for f, r in zip(FOLDS, rs):
                    for k, v in r["tot"].items():
                        tot[k] = tot.get(k, 0) + v
                    per_seed[str(r["seed"])] = r["tot"]
                    if "eps" in r:
                        eps += [[f] + e for e in r["eps"]]
                    if "post" in r:
                        for k in post:
                            post[k] += r["post"][k]
                out[self.key(*p)] = {"tot": tot, "eps": eps, "per_seed": per_seed, "post": post}
            print(f"  τ={tau}：{len(ps)} 組 × 8 fold（{time.time() - t:.0f} s）", flush=True)
        if use_cache and out:
            self.cache.update(out)
            self.save()
        return {self.key(*p): (out.get(self.key(*p)) or self.cache[self.key(*p)]) for p in pairs}

    def save(self):
        if not self.cache_path:
            return
        os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
        tmp = self.cache_path + ".tmp"
        json.dump(self.cache, open(tmp, "w", encoding="utf-8"))
        os.replace(tmp, self.cache_path)

    def close(self):
        for p in self.pools.values():
            p.close(); p.join()


# ----------------------------------------------------------------------------
# 混合指標（§4.3：期望計數之比；延遲以 σ 權重之加權分位數，截尾 = +∞）
def ratio(n, d):
    return n / d if d else None


def mix(res, sD, sA, key):
    """res: key(d,a) → 結果；sD/sA: id → 機率（sA 為 None 表示乾淨）"""
    W, eps = {}, []
    for d, pd in sD.items():
        for a, pa in (sA.items() if sA is not None else [(None, 1.0)]):
            r = res[key(d, a)]
            w = pd * pa
            for k, v in r["tot"].items():
                W[k] = W.get(k, 0.0) + w * v
            for e in r["eps"]:
                if e[2] is not None:                         # 有竄改之 episode
                    eps.append((w, e[3], e[4]))
    m = {"TPR_rejected": ratio(W.get("tam_rej", 0), W.get("tam_n", 0)),
         "TPR_nontrusted": ratio(W.get("tam_nontrust", 0), W.get("tam_n", 0)),
         "clean_false_reject": ratio(W.get("clean_rej", 0), W.get("clean_n", 0)),
         "clean_nontrusted": ratio(W.get("clean_nontrust", 0), W.get("clean_n", 0)),
         "lure_rate_C_strict": ratio(W.get("lure", 0), W.get("lure_opp", 0)),
         "u_det": ratio(W.get("det_R", 0), W.get("det_n", 0)), "u_atk": ratio(W.get("atk_R", 0), W.get("atk_n", 0))}
    if sA is not None:
        for name, idx in (("d_nontrusted", 1), ("d_rejected", 2)):
            m[name] = wquant(eps, idx)
    return m


def wquant(eps, idx):
    if not eps:
        return None
    w = np.array([e[0] for e in eps], float)
    v = np.array([np.inf if e[idx] is None else e[idx] for e in eps], float)
    o = np.argsort(v, kind="stable")
    v, w = v[o], w[o]
    c = np.cumsum(w) / w.sum()
    q = lambda p: float(v[np.searchsorted(c, p - 1e-12)])
    return {"median": q(0.5), "p90": q(0.9), "censored": float(w[np.isinf(v)].sum() / w.sum()), "n_episodes": len(eps)}


def test_mix():
    """V3：小例子人工驗算"""
    res = {"x|p": {"tot": {"tam_rej": 1, "tam_n": 4, "clean_rej": 0, "clean_n": 10}, "eps": [[0, 2, 100, 0, 1], [0, 3, 100, None, None]]},
           "y|p": {"tot": {"tam_rej": 3, "tam_n": 4, "clean_rej": 2, "clean_n": 10}, "eps": [[0, 2, 100, 0, 0], [0, 3, 100, 5, 9]]}}
    m = mix(res, {"x": 0.25, "y": 0.75}, {"p": 1.0}, lambda d, a: f"{d}|{a}")
    assert abs(m["TPR_rejected"] - (0.25 * 1 + 0.75 * 3) / 4) < 1e-12
    assert abs(m["clean_false_reject"] - 0.75 * 2 / 10) < 1e-12
    # 延遲（d_rej）：x 之 1、∞（各 0.25）、y 之 0、9（各 0.75）→ 排序 0(.75) 1(.25) 9(.75) ∞(.25)；累積 .375 .5 .875 1
    d = m["d_rejected"]
    assert d["median"] == 1.0 and d["p90"] == float("inf") and abs(d["censored"] - 0.125) < 1e-12, d
    return True


# ----------------------------------------------------------------------------
def all_pairs(dets, atks, runs):
    """評估所需之全部 (偵測端, 攻擊者, cm)"""
    drl = sorted({d for r in runs.values() for d in r["sigma_D"]})
    base = ["D0"] + [f"B2_L{L}" for L in B2_LS] + [i for i in dets if i.startswith("B3_")]
    D = sorted(set(drl) | set(base))
    A = sorted(atks)
    pairs = [(dets[d], atks[a], None) for d in D for a in A]
    pairs += [(dets[d], None, None) for d in D]
    pairs += [(dets[d], None, cm) for d in D for cm in CM_GRID + [("step", 1.0)]]
    return pairs, D, A


def stage_checks(args):
    dets, atks, runs = strategies()
    R = Runner(args.workers)                                  # 檢查不用快取：一律重算
    ok, log = True, []

    def rep(name, cond, msg):
        nonlocal ok
        print(f"{'✓' if cond else '✗'} {name}：{msg}", flush=True)
        log.append({"check": name, "passed": bool(cond), "msg": msg})
        ok = ok and bool(cond)

    from psro import summarize
    rep("V3", test_mix(), "混合計算之小例子驗算")
    # V1：D0 × A0 誘導率（RQ3、C_strict）與乾淨誤拒
    rq3 = json.load(open(os.path.join(SEV, "RQ3_decision_replay.json"), encoding="utf-8"))
    rq3n = {("step", 0.6): "step_x0.6", ("step", 0.8): "step_x0.8", ("drift", 0.01): "drift_1pct"}
    scripted = [a for a in atks.values() if a["kind"] == "scripted"]
    res = R.run([(dets["D0"], a, None) for a in scripted] + [(dets["D0"], None, None)], use_cache=False)
    for a in scripted:
        got = ratio(res[Runner.key(dets["D0"], a, None)]["tot"]["lure"], res[Runner.key(dets["D0"], a, None)]["tot"]["lure_opp"])
        exp = rq3[f"uebound|{rq3n[(a['attack'], a['param'])]}|C_strict"]["lured_rate"]
        rep("V1", abs(got - exp) <= 1e-12, f"D0 × {a['id']} 誘導率 {got:.6%}（RQ3 {exp:.6%}）")
    c = res[Runner.key(dets["D0"], None, None)]["tot"]
    rep("V1", (c["clean_rej"], c["clean_n"]) == (159, 15534), f"D0 乾淨 rejected {c['clean_rej']}／{c['clean_n']}（159／15,534）")
    rep("V5", c["clean_n"] == 15534, f"乾淨評估 (節點, 秒) 數 {c['clean_n']}")
    # V2：各組最終 σ 支撐集之報酬表逐位重現
    for r, info in runs.items():
        P = info["state"]["payoff"]
        inv_d = {v: k for k, v in info["dmap"].items()}
        inv_a = {v: k for k, v in info["amap"].items()}
        ps = [(dets[d], atks[a], None) for d in info["sigma_D"] for a in info["sigma_A"]]
        rr = R.run(ps, use_cache=False)
        bad = []
        for d, a, _ in ps:
            got = summarize(rr[Runner.key(d, a, None)]["tot"])
            exp = P[f"{inv_d[d['id']]}|{inv_a[a['id']]}"]
            if json.loads(json.dumps(got)) != exp:
                bad.append(f"{d['id']}|{a['id']}")
        n_eps = {len(rr[Runner.key(d, a, None)]["eps"]) for d, a, _ in ps}
        rep("V2", not bad, f"{r}：{len(ps)} 對與報酬表逐位相同" + (f"；不符 {bad}" if bad else ""))
        rep("V5", n_eps == {56}, f"{r}：每對 episode 數 {sorted(n_eps)}（應為 56）")
    # V4：決定性（重跑一對學習型 × 學習型）
    r0 = runs[rid("O-full", 0)]
    d1, a1 = dets[next(iter(r0["sigma_D"]))], atks[next(iter(r0["sigma_A"]))]
    x = R.run([(d1, a1, None)], use_cache=False)
    y = R.run([(d1, a1, None)], use_cache=False)
    rep("V4", x == y, f"{d1['id']} × {a1['id']} 重跑逐位相同")
    # B2-1、B2-2
    e12 = json.load(open(os.path.join(SEV, "E12_persist.json"), encoding="utf-8"))
    b2 = R.run([(dets[f"B2_L{L}"], None, None) for L in B2_LS], use_cache=False)
    d0 = res[Runner.key(dets["D0"], None, None)]["per_seed"]
    for L in B2_LS:
        ps = b2[Runner.key(dets[f"B2_L{L}"], None, None)]["per_seed"]
        got = {s: ps[s]["clean_rej"] - d0[s]["clean_rej"] for s in ps}
        exp = {s: v.get("新增誤拒", 0) for s, v in e12["clean"][str(L)].items()}
        rep("B2-1", got == exp, f"L_S={L} 新增乾淨誤拒逐 seed {got}（E12 {exp}）")
    b2a = R.run([(dets[f"B2_L{L}"], a, None) for L in B2_LS for a in scripted], use_cache=False)
    for L in B2_LS:
        for a in scripted:
            t = b2a[Runner.key(dets[f"B2_L{L}"], a, None)]["tot"]
            got = ratio(t["lure"], t["lure_opp"])
            exp = e12["rq3_uebound"][str(L)][f"uebound|{rq3n[(a['attack'], a['param'])]}|C_strict"]["lured_rate"]
            rep("B2-2", abs(got - exp) <= 1e-12, f"L_S={L} × {a['id']} 誘導率 {got:.6%}（E12 {exp:.6%}）")
    # B3-1、B3-2
    e14 = json.load(open(os.path.join(SEV, "E14_D1_sensitivity.json"), encoding="utf-8"))["results"]
    b3 = R.run([(dets[i], None, None) for i in dets if i.startswith("B3_")], use_cache=False)
    rep("B3-1", b3[Runner.key(dets["B3_tau2_3"], None, None)]["per_seed"] == d0, "τ_H=(2,3) 乾淨評估與 D0 逐 seed 相同")
    for i in [i for i in dets if i.startswith("B3_")]:
        ps = b3[Runner.key(dets[i], None, None)]["per_seed"]
        tau = dets[i]["tau"]
        ref = e14[f"tau{tau[0]:g}_{tau[1]:g}|L1"]["per_seed"]
        got = {s: (ps[s]["clean_n"], ps[s]["clean_n"] - ps[s]["clean_nontrust"], ps[s]["clean_rej"]) for s in ps}
        exp = {s: (v["n"], v["trusted"], v["rejected"]) for s, v in ref.items()}
        rep("B3-2", got == exp, f"τ_H={tuple(tau)} 乾淨 (n, trusted, rejected) 逐 seed 重現 E14")
    # E9c-0
    e9 = R.run([(dets["D0"], None, ("step", 1.0)), (d1, None, ("step", 1.0)), (d1, None, None)], use_cache=False)
    rep("E9c-0", e9[Runner.key(dets["D0"], None, ("step", 1.0))]["per_seed"] == d0, "D0：g=1.0 與乾淨逐 seed 相同")
    rep("E9c-0", e9[Runner.key(d1, None, ("step", 1.0))]["per_seed"] == e9[Runner.key(d1, None, None)]["per_seed"],
        f"{d1['id']}：g=1.0 與乾淨逐 seed 相同")
    R.close()
    os.makedirs(OUT, exist_ok=True)
    json.dump({"spec": SPEC, "passed": ok, "checks": log, "meta": meta()},
              open(os.path.join(OUT, "checks.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    if not ok:
        raise SystemExit("一致性檢查失敗；停止，請回報，勿調參數。")
    print("全部一致性檢查通過。")


def stage_abr(args):
    import psro as PS
    _, _, runs = strategies()
    jobs = []
    for lv, t in RUNS:
        info = runs[rid(lv, t)]
        st = info["state"]
        for f in FOLDS:
            path = os.path.join(OUT, "abr", lv, f"t{t}", f"ABR_f{f}")
            seed = 100000 * t + 1000 * 7 + 10 * f + 1             # 「第 7 輪」編號（§9），不與 PSRO 重複
            jobs.append(("atk", f, st["D"], st["sigma"]["D"], lv, PS.BR_MAX, PS.BR_EVERY, seed, path))
    todo = [j for j in jobs if not os.path.exists(j[-1] + ".zip")]
    print(f"A-BR：{len(jobs)} 個（尚待 {len(todo)}）", flush=True)
    t = time.time()
    # maxtasksperchild=1：每個最佳回應用全新工作行程。各組偵測端之名稱（如 D2@f0）跨組重複，
    # 而 psro 之 T0Cache 以偵測端名稱為鍵；同一行程跨組重用快取會取到別組之注入前狀態。
    with mp.Pool(args.workers, initializer=PS._init_worker, maxtasksperchild=1) as p:
        for i, path in enumerate(p.imap_unordered(PS._train_job, todo, chunksize=1)):
            print(f"  完成 {os.path.relpath(path, OUT)}（{i + 1}／{len(todo)}，{time.time() - t:.0f} s）", flush=True)
    json.dump({"spec": SPEC, "meta": meta(), "jobs": [[j[0], j[1], j[4], j[7], os.path.relpath(j[8], ROOT)] for j in jobs]},
              open(os.path.join(OUT, "abr", "abr_meta.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("A-BR 完成。")


def stage_eval(args):
    if not json.load(open(os.path.join(OUT, "checks.json"), encoding="utf-8"))["passed"]:
        raise SystemExit("checks 未通過")
    dets, atks, runs = strategies()
    missing = [r for r in runs if f"{r}:ABR" not in atks]
    if missing and not args.allow_missing_abr:
        raise SystemExit(f"A-BR 尚未完成：{missing}（先跑 --stage abr，或加 --allow-missing-abr 先評估其餘）")
    pairs, D, A = all_pairs(dets, atks, runs)
    R = Runner(args.workers, os.path.join(OUT, "pairs.json"))
    print(f"偵測端 {len(D)}、攻擊者 {len(A)}；共 {len(pairs)} 組（已快取 {sum(Runner.key(*p) in R.cache for p in pairs)}）", flush=True)
    for i in range(0, len(pairs), 60):                       # 分批，便於中斷續跑
        R.run(pairs[i:i + 60])
    R.close()
    print("評估完成。")


def frontier_judge(drl, base):
    """§6：base = [(名稱, FRR, TPR, d)]；drl = (FRR, TPR, d)。回傳 (判定, 說明)"""
    pts = sorted(base, key=lambda p: (p[1], -p[2]))
    front = []
    for p in pts:                                            # Pareto：FRR 遞增時 TPR 須嚴格遞增
        if not front or p[2] > front[-1][2]:
            front.append(p)
    F, T, d = drl
    if F < front[0][1] or F > front[-1][1]:
        e = front[0] if F < front[0][1] else front[-1]
        dom = F <= e[1] and T > e[2] and d <= e[3]
        return ("優於" if dom else "不可比較"), f"FRR 超出前緣範圍；最近端點 {e[0]}"
    for lo, hi in zip(front, front[1:] + [front[-1]]):
        if lo[1] <= F <= hi[1]:
            tint = lo[2] if hi[1] == lo[1] else lo[2] + (hi[2] - lo[2]) * (F - lo[1]) / (hi[1] - lo[1])
            dlim = min(lo[3], hi[3])
            win = T > tint and d <= dlim
            return ("優於" if win else "未優於"), f"前緣內插 TPR {tint:.4f}（{lo[0]}–{hi[0]}），延遲上限 {dlim}"
    return "不可比較", "無法定位"


def stage_report(args):
    dets, atks, runs = strategies()
    pairs, D, A = all_pairs(dets, atks, runs)
    cache = json.load(open(os.path.join(OUT, "pairs.json"), encoding="utf-8"))
    miss = [Runner.key(*p) for p in pairs if Runner.key(*p) not in cache]
    if miss:
        raise SystemExit(f"尚有 {len(miss)} 組未評估（先跑 --stage eval）")
    key = lambda d, a: f"{d}|{a or 'CLEAN'}|"
    base_ids = ["D0"] + [f"B2_L{L}" for L in B2_LS] + [i for i in dets if i.startswith("B3_")]
    scripted = [a for a in A if atks[a]["kind"] == "scripted"]
    out = {"spec": SPEC, "meta": meta(), "runs": {}, "baselines": {}}

    def clean_m(sD):
        return mix(cache, sD, None, key)

    def worst(sD, aset):
        ms = {a: mix(cache, sD, {a: 1.0}, key) for a in aset}
        a_t = min(aset, key=lambda a: (ms[a]["TPR_rejected"], a))
        a_d = max(aset, key=lambda a: (ms[a]["d_rejected"]["median"], a))
        return {"by_TPR": {"attacker": a_t, **ms[a_t]}, "by_delay": {"attacker": a_d, **ms[a_d]}}

    def sets_for(r):
        s = {"A-script": ("worst", scripted), "A-pool": ("worst", A_pool)}
        s["A-eq"] = ("mix", runs[r]["sigma_A"])
        if f"{r}:ABR" in atks:
            s["A-BR"] = ("mix", {f"{r}:ABR": 1.0})
        return s

    A_pool = [a for a in A if not a.endswith(":ABR")]
    for b in base_ids:
        ent = {"clean": clean_m({b: 1.0}), "A-script": worst({b: 1.0}, scripted), "A-pool": worst({b: 1.0}, A_pool),
               "per_attacker_script": {a: mix(cache, {b: 1.0}, {a: 1.0}, key) for a in scripted}}
        for r in runs:
            ent[f"A-eq@{r}"] = mix(cache, {b: 1.0}, runs[r]["sigma_A"], key)
            if f"{r}:ABR" in atks:
                ent[f"A-BR@{r}"] = mix(cache, {b: 1.0}, {f"{r}:ABR": 1.0}, key)
        ent["E9c"] = {f"{cm[0]}{cm[1]:g}": cache[f"{b}|CLEAN|{cm[0]}{cm[1]:g}"]["post"] for cm in CM_GRID}
        out["baselines"][b] = ent
    for r, info in runs.items():
        sD = info["sigma_D"]
        e = {"sigma_D": sD, "sigma_A": info["sigma_A"], "n_rounds": info["n_rounds"], "stop": info["stop"],
             "clean": clean_m(sD),
             "A-script": worst(sD, scripted), "A-pool": worst(sD, A_pool),
             "A-eq": mix(cache, sD, info["sigma_A"], key),
             "support": {d: {"clean": clean_m({d: 1.0}), "A-pool": worst({d: 1.0}, A_pool)} for d in sD}}
        if f"{r}:ABR" in atks:
            e["A-BR"] = mix(cache, sD, {f"{r}:ABR": 1.0}, key)
        # E9c（混合：期望計數之比）
        e["E9c"] = {}
        for cm in CM_GRID:
            n = sum(p * cache[f"{d}|CLEAN|{cm[0]}{cm[1]:g}"]["post"]["n"] for d, p in sD.items())
            e["E9c"][f"{cm[0]}{cm[1]:g}"] = {k: sum(p * cache[f"{d}|CLEAN|{cm[0]}{cm[1]:g}"]["post"][k] for d, p in sD.items()) / n
                                             for k in ("rej", "nontrust")}
        # §6 判準
        J = {}
        frr = e["clean"]["clean_false_reject"]
        for sname in ["A-script", "A-pool", "A-eq"] + (["A-BR"] if "A-BR" in e else []):
            if sname in ("A-script", "A-pool"):
                drl_t, drl_d = e[sname]["by_TPR"]["TPR_rejected"], e[sname]["by_delay"]["d_rejected"]["median"]
                bp = [(b, out["baselines"][b]["clean"]["clean_false_reject"], out["baselines"][b][sname]["by_TPR"]["TPR_rejected"],
                       out["baselines"][b][sname]["by_delay"]["d_rejected"]["median"]) for b in base_ids]
            else:
                tag = f"{sname}@{r}"
                drl_t, drl_d = e[sname]["TPR_rejected"], e[sname]["d_rejected"]["median"]
                bp = [(b, out["baselines"][b]["clean"]["clean_false_reject"], out["baselines"][b][tag]["TPR_rejected"],
                       out["baselines"][b][tag]["d_rejected"]["median"]) for b in base_ids]
            v, why = frontier_judge((frr, drl_t, drl_d), bp)
            J[sname] = {"verdict": v, "why": why, "DRL": {"FRR": frr, "TPR_rejected": drl_t, "d_rejected_median": drl_d}}
        cm = f"{CM_MAIN[0]}{CM_MAIN[1]:g}"
        J["E9c"] = {"passed": e["E9c"][cm]["rej"] <= out["baselines"]["D0"]["E9c"][cm]["rej"] / out["baselines"]["D0"]["E9c"][cm]["n"],
                    "DRL_rej": e["E9c"][cm]["rej"], "B1_rej": out["baselines"]["D0"]["E9c"][cm]["rej"] / out["baselines"]["D0"]["E9c"][cm]["n"]}
        e["judgement"] = J
        out["runs"][r] = e
    # §6.3 彙整
    summ = {}
    for lv in ("O-full", "O-outcome"):
        rs = [rid(lv, t) for t in (0, 1, 2)]
        for sname in ["A-script", "A-pool", "A-eq", "A-BR"]:
            vs = [out["runs"][r]["judgement"].get(sname, {}).get("verdict") for r in rs]
            if None in vs:
                continue
            n = vs.count("優於")
            summ[f"{lv}|{sname}"] = {"verdicts": vs, "n_better": n,
                                     "conclusion": "優於" if n == 3 else ("多數情形優於" if n == 2 else "未優於")}
        e9 = [out["runs"][r]["judgement"]["E9c"]["passed"] for r in rs]
        summ[f"{lv}|E9c"] = {"passed": e9}
    out["summary"] = summ
    json.dump(out, open(os.path.join(OUT, "eval_final.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    for k, v in summ.items():
        print(k, v)
    print("寫入", os.path.join(OUT, "eval_final.json"))


def meta():
    import importlib.metadata as md
    return {"git_commit": subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
            "packages": {p: md.version(p) for p in ("torch", "gymnasium", "stable-baselines3", "sb3-contrib", "numpy")},
            "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["checks", "abr", "eval", "report"], required=True)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--allow-missing-abr", action="store_true")
    a = ap.parse_args()
    if os.environ.get("ZT_DATASET") != "d30" or os.environ.get("ZT_FUSION_ORDER") != "severity":
        raise SystemExit("須在 ZT_DATASET=d30 與 ZT_FUSION_ORDER=severity 下執行")
    sys.path.insert(0, HERE)
    {"checks": stage_checks, "abr": stage_abr, "eval": stage_eval, "report": stage_report}[a.stage](a)


if __name__ == "__main__":
    main()
