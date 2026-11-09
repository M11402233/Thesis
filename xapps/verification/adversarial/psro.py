# -*- coding: utf-8 -*-
"""psro.py — E19 v2 §3a 之 PSRO 驅動程式。

策略池：偵測端 D0 = 規則版（下限）；攻擊者 A0 = ×0.6 階躍、×0.8 階躍、漂移 1 %/秒（R-a）。
每個學習出之池成員 = 8 個 fold 各一之模型（R-b；fold f 以其餘 7 seed 訓練、於 seed f 評估）。
每一輪：報酬表（池中每對於 8 fold 測試 seed × 7 cell 評估，每步平均報酬，跨 episode 合併計）
       → Lemke–Howson（nashpy，初始 label 0；不合法則改 support enumeration 並記錄；R-c）
       → 各自對另一方之混合訓練最佳回應（偵測端 MaskablePPO、攻擊者 PPO）→ 加入池。
停止：NashConv < ε（0.01）或達最大輪數（6）（R-d）。主張僅為受限賽局之近似均衡。

  --g4-only        只跑 Round 0 之報酬表與 G4（D0 × A0 重現第四章），不訓練
  --det-steps/--atk-steps  每個最佳回應之訓練步數（R-f 學習曲線定案前不得用於正式結果）

輸出：data/results/d30/drl/psro/<level>/t<訓練 seed>/（state.json、models/），可續跑。
用法：ZT_DATASET=d30 ZT_FUSION_ORDER=severity python psro.py --level O-full --train-seed 0 ...
"""
import os
import sys
import json
import time
import argparse
import subprocess
import multiprocessing as mp
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
OUT_BASE = os.path.join(ROOT, "data", "results", "d30", "drl", "psro")
SEV = os.path.join(ROOT, "data", "results", "d30_fusion_order", "severity")
EPS, MAX_ROUNDS = 0.01, 6                                   # R-d
HP = {"n_steps": 2048, "batch_size": 256, "learning_rate": 3e-4, "n_epochs": 10, "gamma": 0.99,
      "gae_lambda": 0.95, "clip_range": 0.2, "ent_coef": 0.0, "policy": "MlpPolicy (SB3 預設 64×64)"}
A0_SPEC = [("step", 0.60), ("step", 0.80), ("drift", 0.01)]
RQ3_NAME = {("step", 0.60): "step_x0.6", ("step", 0.80): "step_x0.8", ("drift", 0.01): "drift_1pct"}

_W = {}                                                      # 每個工作行程之快取


def _init_worker():
    import torch
    torch.set_num_threads(1)
    import game_core as G
    import env_kpm_game as E
    _W.update(G=G, E=E, ds=G.DataStore(), cache=G.T0Cache(maxsize=1024), models={})


def _load(strat, fold, role):
    """策略描述 → 可用物件（偵測端：det_policy；攻擊者：具 multiplier 之物件）"""
    G, E = _W["G"], _W["E"]
    if strat["kind"] == "floor":
        return E.FloorDetector()
    if strat["kind"] == "scripted":
        return G.ScriptedAttack(strat["attack"], strat["param"])
    path = strat["paths"][str(fold)]
    key = (path, role)
    if key not in _W["models"]:
        if strat["kind"] == "maskppo":
            from sb3_contrib import MaskablePPO
            _W["models"][key] = E.LearnedDetector(MaskablePPO.load(path, device="cpu"), f"{strat['name']}@f{fold}")
        else:
            from stable_baselines3 import PPO
            _W["models"][key] = E.LearnedAttacker(PPO.load(path, device="cpu"), strat["level"], f"{strat['name']}@f{fold}")
    return _W["models"][key]


def _eval_job(args):
    """一個 (偵測端, 攻擊者, fold) 於該 fold 測試 seed 之全部 cell；回傳累計 stats"""
    dstrat, astrat, fold = args
    G, E, ds = _W["G"], _W["E"], _W["ds"]
    sd = ds.get(ds.files[fold])                              # 評估 anchor = 其餘 7 seed（重現第四章）
    det, atk = _load(dstrat, fold, "det"), _load(astrat, fold, "atk")
    tot = {}
    for cell in sd.cells_all:
        ep = _W["cache"].get(sd, cell, det, E.new_episode)
        G.run_episode(ep, det, atk)
        for k, v in ep.stats.items():
            tot[k] = tot.get(k, 0) + v
    return tot


def _train_job(args):
    """一個最佳回應之一個 fold：對另一方之混合訓練並存檔"""
    role, fold, opp_pool, sigma, level, steps, seed, path = args
    if os.path.exists(path + ".zip"):
        return path
    E, ds = _W["E"], _W["ds"]
    test = ds.files[fold]
    train = [f for f in ds.files if f != test]
    opps = [_load(s, fold, "atk" if role == "det" else "det") for s in opp_pool]
    keep = [i for i, p in enumerate(sigma) if p > 0]
    opps, probs = [opps[i] for i in keep], [sigma[i] for i in keep]
    probs = list(np.asarray(probs) / sum(probs))
    if role == "det":
        from sb3_contrib import MaskablePPO
        env = E.DetectorEnv(ds, train, test, opps, probs, seed=seed)
        algo = MaskablePPO
    else:
        from stable_baselines3 import PPO
        env = E.AttackerEnv(ds, train, test, opps, probs, level, seed=seed)
        env.t0_cache = _W["cache"]
        algo = PPO
    hp = {k: v for k, v in HP.items() if k != "policy"}
    m = algo("MlpPolicy", env, seed=seed, verbose=0, device="cpu", **hp)
    m.learn(steps)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    m.save(path)
    return path


# ----------------------------------------------------------------------------
def summarize(tot):
    g = lambda a, b: (tot.get(a, 0) / tot[b]) if tot.get(b) else None
    return {"u_det": g("det_R", "det_n"), "u_atk": g("atk_R", "atk_n"), "TPR_rejected": g("tam_rej", "tam_n"),
            "TPR_nontrusted": g("tam_nontrust", "tam_n"), "clean_false_reject": g("clean_rej", "clean_n"),
            "lure_rate_C_strict": g("lure", "lure_opp"), "counts": tot}


def solve(A, B):
    """一般和雙矩陣：Lemke–Howson（label 0）；不合法則 support enumeration（記錄）"""
    import nashpy as nash
    g = nash.Game(A, B)

    def ok(s, t):
        if s is None or t is None or np.any(np.isnan(s)) or np.any(np.isnan(t)):
            return False
        if np.any(s < -1e-12) or np.any(t < -1e-12) or abs(s.sum() - 1) > 1e-9 or abs(t.sum() - 1) > 1e-9:
            return False
        return (A @ t).max() - s @ A @ t <= 1e-9 and (s @ B).max() - s @ B @ t <= 1e-9
    try:
        s, t = g.lemke_howson(initial_dropped_label=0)
    except Exception:                                        # noqa: BLE001
        s = t = None
    if ok(s, t):
        return s, t, "lemke_howson(label=0)"
    for s, t in g.support_enumeration():
        if ok(s, t):
            return s, t, "support_enumeration(first)"
    raise SystemExit("meta-solver 找不到合法之 Nash 均衡，停止，請回報。")


class PSRO:
    def __init__(self, args):
        self.a = args
        self.dir = os.path.join(OUT_BASE, args.level, f"t{args.train_seed}")
        self.state_path = os.path.join(self.dir, "state.json")
        if os.path.exists(self.state_path):
            self.st = json.load(open(self.state_path, encoding="utf-8"))
            print(f"續跑：{self.state_path}（round {self.st['round']}）")
        else:
            self.st = {"round": 0, "D": [{"name": "D0", "kind": "floor"}],
                       "A": [{"name": f"A0_{k}_{p}", "kind": "scripted", "attack": k, "param": p} for k, p in A0_SPEC],
                       "payoff": {}, "history": []}
        self.pool = mp.Pool(args.workers, initializer=_init_worker)

    def save(self):
        os.makedirs(self.dir, exist_ok=True)
        tmp = self.state_path + ".tmp"
        json.dump(self.st, open(tmp, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        os.replace(tmp, self.state_path)

    def fill_payoff(self):
        todo = [(d, a) for d in self.st["D"] for a in self.st["A"] if f"{d['name']}|{a['name']}" not in self.st["payoff"]]
        jobs = [(d, a, f) for d, a in todo for f in range(8)]
        t = time.time()
        res = self.pool.map(_eval_job, jobs, chunksize=1)
        for i, (d, a) in enumerate(todo):
            tot = {}
            for r in res[i * 8:(i + 1) * 8]:
                for k, v in r.items():
                    tot[k] = tot.get(k, 0) + v
            self.st["payoff"][f"{d['name']}|{a['name']}"] = summarize(tot)
        print(f"  報酬表：新增 {len(todo)} 對（{time.time() - t:.0f} s）")
        self.save()

    def matrices(self):
        P = self.st["payoff"]
        A = np.array([[P[f"{d['name']}|{a['name']}"]["u_det"] for a in self.st["A"]] for d in self.st["D"]])
        B = np.array([[P[f"{d['name']}|{a['name']}"]["u_atk"] for a in self.st["A"]] for d in self.st["D"]])
        return A, B

    def g4(self):
        rq3 = json.load(open(os.path.join(SEV, "RQ3_decision_replay.json"), encoding="utf-8"))
        bad = []
        for a in self.st["A"][:3]:
            got = self.st["payoff"][f"D0|{a['name']}"]["lure_rate_C_strict"]
            exp = rq3[f"uebound|{RQ3_NAME[(a['attack'], a['param'])]}|C_strict"]["lured_rate"]
            print(f"  G4 {a['name']}：誘導率 {got:.4%}（RQ3 {exp:.4%}）")
            if abs(got - exp) > 1e-12:
                bad.append(a["name"])
        # 乾淨（無攻擊）：D0 之誤拒須為 159／15,534（4.9.6）
        tot = {}
        for r in self.pool.map(_clean_job, range(8)):
            for k, v in r.items():
                tot[k] = tot.get(k, 0) + v
        print(f"  G4 乾淨 D0：rejected {tot['clean_rej']}／{tot['clean_n']}（第四章 159／15,534）")
        if (tot["clean_rej"], tot["clean_n"]) != (159, 15534):
            bad.append("clean")
        if bad:
            raise SystemExit(f"G4 ✗ {bad}；停止，請回報，勿調參數。")
        print("G4 ✓ Round 0（D0 × A0）重現第四章之誘導率（RQ3，C_strict）與乾淨誤拒；"
              "TPR 第四章無同口徑之數字，僅記錄")
        self.st["G4"] = {"passed": True, "clean": tot}
        self.save()

    def run(self):
        st, a = self.st, self.a
        if st["round"] == 0:
            self.fill_payoff()
            self.g4()
            A, B = self.matrices()
            s, t, how = solve(A, B)
            st["sigma"] = {"D": s.tolist(), "A": t.tolist(), "solver": how}
            st["round"] = 1
            self.save()
            print(f"Round 0：σ_D={np.round(s, 3).tolist()} σ_A={np.round(t, 3).tolist()}（{how}）")
        if a.g4_only:
            return
        if not (a.det_steps and a.atk_steps):
            raise SystemExit("需指定 --det-steps 與 --atk-steps（R-f 定案之值）")
        while st["round"] <= MAX_ROUNDS:
            r = st["round"]
            sig = st["sigma"]
            mdir = os.path.join(self.dir, "models", f"r{r}")
            dname, aname = f"D{r}", f"A{r}"
            dpaths = {str(f): os.path.join(mdir, f"{dname}_f{f}") for f in range(8)}
            apaths = {str(f): os.path.join(mdir, f"{aname}_f{f}") for f in range(8)}
            seed_of = lambda role, f: 100000 * a.train_seed + 1000 * r + 10 * f + (0 if role == "det" else 1)
            jobs = ([("det", f, st["A"], sig["A"], a.level, a.det_steps, seed_of("det", f), dpaths[str(f)]) for f in range(8)]
                    + [("atk", f, st["D"], sig["D"], a.level, a.atk_steps, seed_of("atk", f), apaths[str(f)]) for f in range(8)])
            t = time.time()
            self.pool.map(_train_job, jobs, chunksize=1)
            print(f"Round {r}：最佳回應訓練完成（{time.time() - t:.0f} s）")
            newD = {"name": dname, "kind": "maskppo", "paths": dpaths, "steps": a.det_steps}
            newA = {"name": aname, "kind": "ppo", "level": a.level, "paths": apaths, "steps": a.atk_steps}
            if not any(d["name"] == dname for d in st["D"]):
                st["D"].append(newD); st["A"].append(newA)
            self.save()
            self.fill_payoff()
            A, B = self.matrices()
            s_old, t_old = np.array(sig["D"]), np.array(sig["A"])
            nD, nA = len(s_old), len(t_old)
            uD = s_old @ A[:nD, :nA] @ t_old
            uA = s_old @ B[:nD, :nA] @ t_old
            gD = max(0.0, float(A[-1, :nA] @ t_old - uD))
            gA = max(0.0, float(s_old @ B[:nD, -1] - uA))
            nashconv = gD + gA
            s, t, how = solve(A, B)
            st["history"].append({"round": r, "gain_det": gD, "gain_atk": gA, "nashconv": nashconv,
                                  "sigma_prev": sig, "sigma_new": {"D": s.tolist(), "A": t.tolist(), "solver": how}})
            st["sigma"] = {"D": s.tolist(), "A": t.tolist(), "solver": how}
            st["round"] = r + 1
            self.save()
            print(f"Round {r}：NashConv = {nashconv:.4f}（偵測端增益 {gD:.4f}、攻擊者增益 {gA:.4f}）；"
                  f"新 σ_D={np.round(s, 3).tolist()} σ_A={np.round(t, 3).tolist()}")
            if nashconv < EPS:
                st["stop"] = f"NashConv {nashconv:.4f} < ε = {EPS}（round {r}）"
                break
        else:
            st["stop"] = f"達最大輪數 {MAX_ROUNDS}"
        self.save()
        print("停止：", st["stop"])


def _clean_job(fold):
    G, E, ds = _W["G"], _W["E"], _W["ds"]
    sd = ds.get(ds.files[fold])
    ep = G.run_episode(G.Episode(sd, None), E.FloorDetector())
    return dict(ep.stats)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", choices=["O-full", "O-outcome"], required=True)
    ap.add_argument("--train-seed", type=int, choices=[0, 1, 2], required=True)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--det-steps", type=int)
    ap.add_argument("--atk-steps", type=int)
    ap.add_argument("--g4-only", action="store_true")
    args = ap.parse_args()
    if os.environ.get("ZT_DATASET") != "d30" or os.environ.get("ZT_FUSION_ORDER") != "severity":
        raise SystemExit("須在 ZT_DATASET=d30 與 ZT_FUSION_ORDER=severity 下執行")
    import importlib.metadata as md
    meta = {"git_commit": subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
            "packages": {p: md.version(p) for p in ("torch", "gymnasium", "stable-baselines3", "sb3-contrib", "numpy", "nashpy")},
            "hyperparameters": HP, "eps": EPS, "max_rounds": MAX_ROUNDS}
    p = PSRO(args)
    p.st.setdefault("meta_runs", []).append(dict(meta, argv=sys.argv[1:], started=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())))
    p.save()
    p.run()
    p.pool.close(); p.pool.join()


if __name__ == "__main__":
    main()
