# -*- coding: utf-8 -*-
"""psro.py — E19 v2 §3a 之 PSRO 驅動程式。

策略池：偵測端 D0 = 規則版（下限）；攻擊者 A0 = ×0.6 階躍、×0.8 階躍、漂移 1 %/秒（R-a）。
每個學習出之池成員 = 8 個 fold 各一之模型（R-b；fold f 以其餘 7 seed 訓練、於 seed f 評估）。
每一輪：報酬表（池中每對於 8 fold 測試 seed × 7 cell 評估，每步平均報酬，跨 episode 合併計）
       → Lemke–Howson（nashpy，初始 label 0；不合法則改 support enumeration 並記錄；R-c）
       → 各自對另一方之混合訓練最佳回應（偵測端 MaskablePPO、攻擊者 PPO）→ 加入池。
停止：NashConv ≤ 0.05 × 第 1 輪之 NashConv（完成總下降量 95 %）或達最大輪數（6）（R-d，2026-11-09）。主張僅為受限賽局之近似均衡。

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
_DSN = os.environ.get("ZT_DATASET")
if _DSN == "d30p":                                           # 第二階段（E30 §8）：D-30P，G4 對步 4–5 之輸出
    OUT_BASE = os.path.join(ROOT, "data", "results", "d30p", "drl", "psro")
    SEV = os.path.join(ROOT, "data", "results", "d30p_delay_" + os.environ.get("ZT_DELAY_SOURCE", ""))
else:
    OUT_BASE = os.path.join(ROOT, "data", "results", "d30", "drl", "psro")
    SEV = os.path.join(ROOT, "data", "results", "d30_fusion_order", "severity")
REL_STOP, MAX_ROUNDS = 0.05, 6                              # R-d（2026-11-09）：NashConv ≤ 0.05 × 第 1 輪 NashConv
HP = {"n_steps": 2048, "batch_size": 256, "learning_rate": 3e-4, "n_epochs": 10, "gamma": 0.99,
      "gae_lambda": 0.95, "clip_range": 0.2, "ent_coef": 0.0, "policy": "MlpPolicy (SB3 預設 64×64)"}
A0_SPEC = [("step", 0.60), ("step", 0.80), ("drift", 0.01)]
RQ3_NAME = {("step", 0.60): "step_x0.6", ("step", 0.80): "step_x0.8", ("drift", 0.01): "drift_1pct"}

_W = {}                                                      # 每個工作行程之快取
FOLDS = list(range(8))


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
        if strat["kind"] == "maskppo" and os.path.exists(path + ".floor.json"):
            _W["models"][key] = E.FloorDetector()             # E30 §2：無合格存檔（誤拒上限）→ 該 fold 之最佳回應為 F
        elif strat["kind"] == "maskppo":
            from sb3_contrib import MaskablePPO
            _W["models"][key] = E.LearnedDetector(MaskablePPO.load(path, device="cpu"), f"{strat['name']}@f{fold}",
                                                  strat.get("det_mode", "F"))
        else:
            from stable_baselines3 import PPO
            _W["models"][key] = E.LearnedAttacker(PPO.load(path, device="cpu"), strat["level"], f"{strat['name']}@f{fold}")
    return _W["models"][key]


def _eval_job(args):
    """一個 (偵測端, 攻擊者, fold, split) 之累計 stats。
    split="test"：該 fold 之測試 seed（外層評估；E19 原行為）。
    split="train"：該 fold 之 7 個訓練 seed（anchor 排除測試 seed；內層＝策略選擇用，E30 / 審稿 A2）"""
    dstrat, astrat, fold = args[:3]
    split = args[3] if len(args) > 3 else "test"
    G, E, ds = _W["G"], _W["E"], _W["ds"]
    test = ds.files[fold]
    sds = [ds.get(test)] if split == "test" else [ds.get(f, test) for f in ds.files if f != test]
    det, atk = _load(dstrat, fold, "det"), _load(astrat, fold, "atk")
    tot = {}
    for sd in sds:
        for cell in sd.cells_all:
            ep = _W["cache"].get(sd, cell, det, E.new_episode)
            G.run_episode(ep, det, atk)
            for k, v in ep.stats.items():
                tot[k] = tot.get(k, 0) + v
    return tot


BR_MAX, BR_EVERY = 300_000, 50_000                          # R-f 事後修正（2026-11-09，E19 §2b）


def _val_score(role, model, train, test, opps, probs, det_mode="F", with_frr=False):
    """決定性策略於該 fold 之訓練 seed（全部 cell）對對手混合之期望每步 reward（依機率加權，不抽樣）。
    with_frr（E30 §2 誤拒上限）：另回傳同口徑之乾淨誤拒率（clean_rej／clean_n，依機率加權）。model=None → F（規則版）"""
    G, E, ds = _W["G"], _W["E"], _W["ds"]
    total = frr = 0.0
    for opp, p in zip(opps, probs):
        R = n = cr = cn = 0.0
        for f in train:
            sd = ds.get(f, test)
            for cell in sd.cells_all:
                if role == "det":
                    det = E.FloorDetector() if model is None else E.LearnedDetector(model, "val", det_mode)
                    ep = G.run_episode(E.new_episode(sd, cell), det, opp)
                    R += ep.stats["det_R"]; n += ep.stats["det_n"]
                    cr += ep.stats["clean_rej"]; cn += ep.stats["clean_n"]
                else:
                    ep = _W["cache"].get(sd, cell, opp, E.new_episode)
                    G.run_episode(ep, opp, E.LearnedAttacker(model, model._zt_level, "val"))
                    R += ep.stats["atk_R"]; n += ep.stats["atk_n"]
        total += p * (R / n if n else 0.0)
        frr += p * (cr / cn if cn else 0.0)
    return (total, frr) if with_frr else total


def _train_job(args):
    """一個最佳回應之一個 fold：對另一方之混合訓練至多 BR_MAX 步，每 BR_EVERY 步以訓練 seed 驗證，保留最佳存檔"""
    role, fold, opp_pool, sigma, level, br_max, br_every, seed, path = args[:9]
    det_mode = args[9] if len(args) > 9 else "F"
    if os.path.exists(path + ".zip") or os.path.exists(path + ".floor.json"):
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
        env = E.DetectorEnv(ds, train, test, opps, probs, seed=seed, det_mode=det_mode)
        algo = MaskablePPO
    else:
        from stable_baselines3 import PPO
        env = E.AttackerEnv(ds, train, test, opps, probs, level, seed=seed)
        env.t0_cache = _W["cache"]
        algo = PPO
    hp = {k: v for k, v in HP.items() if k != "policy"}
    m = algo("MlpPolicy", env, seed=seed, verbose=0, device="cpu", **hp)
    m._zt_level = level
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cap = role == "det" and det_mode != "F"                  # E30 §2：只在乾淨誤拒率 ≤ F 之存檔中選
    frr_F = _val_score("det", None, train, test, opps, probs, with_frr=True)[1] if cap else None
    curve, best = [], (-np.inf, None)
    while m.num_timesteps < br_max:
        m.learn(br_every, reset_num_timesteps=False)
        if cap:
            sc, frr = _val_score(role, m, train, test, opps, probs, det_mode, with_frr=True)
            curve.append([int(m.num_timesteps), sc, frr])
            if frr > frr_F:
                continue
        else:
            sc = _val_score(role, m, train, test, opps, probs)
            curve.append([int(m.num_timesteps), sc])
        if sc > best[0]:                                     # 同分取較早者
            best = (sc, int(m.num_timesteps))
            m.save(path + "_best_tmp")
    info = {"role": role, "fold": fold, "seed": seed, "curve": curve, "best_step": best[1], "best_score": best[0],
            "opponents": [s["name"] for s in opp_pool], "sigma": sigma, "det_mode": det_mode if role == "det" else None,
            "frr_cap_F": frr_F}
    if best[1] is None:                                      # 無合格存檔（僅 cap 時可能）→ F
        assert cap
        json.dump(dict(info, fallback="F（無存檔之乾淨誤拒率 ≤ F）"), open(path + ".floor.json", "w"), indent=1)
    else:
        os.replace(path + "_best_tmp.zip", path + ".zip")
    json.dump(info, open(path + "_curve.json", "w"), indent=1)
    return path


# ----------------------------------------------------------------------------
def summarize(tot):
    g = lambda a, b: (tot.get(a, 0) / tot[b]) if tot.get(b) else None
    return {"u_det": g("det_R", "det_n"), "u_atk": g("atk_R", "atk_n"), "TPR_rejected": g("tam_rej", "tam_n"),
            "TPR_nontrusted": g("tam_nontrust", "tam_n"), "clean_false_reject": g("clean_rej", "clean_n"), "clean_nontrusted": g("clean_nontrust", "clean_n"),
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
        base = OUT_BASE + ("_e30" if args.payoff_split == "train" else "") \
            + ("" if args.det_mode == "F" else f"_{args.det_mode}")          # E30 不與 E19 輸出混用；T／TL 各自一目錄
        self.dir = os.path.join(base, args.level, f"t{args.train_seed}")
        self.state_path = os.path.join(self.dir, "state.json")
        if os.path.exists(self.state_path):
            self.st = json.load(open(self.state_path, encoding="utf-8"))
            if self.st.get("payoff_split", "test") != args.payoff_split:
                raise SystemExit(f"✗ 既有 state 之 payoff_split = {self.st.get('payoff_split', 'test')} ≠ {args.payoff_split}；停止")
            if self.st.get("det_mode", "F") != args.det_mode:
                raise SystemExit(f"✗ 既有 state 之 det_mode = {self.st.get('det_mode', 'F')} ≠ {args.det_mode}；停止")
            print(f"續跑：{self.state_path}（round {self.st['round']}）")
        else:
            self.st = {"round": 0, "D": [{"name": "D0", "kind": "floor"}],
                       "A": [{"name": f"A0_{k}_{p}", "kind": "scripted", "attack": k, "param": p} for k, p in A0_SPEC],
                       "payoff": {}, "history": [], "payoff_split": args.payoff_split, "det_mode": args.det_mode}
        self.pool = mp.Pool(args.workers, initializer=_init_worker)

    def save(self):
        os.makedirs(self.dir, exist_ok=True)
        tmp = self.state_path + ".tmp"
        json.dump(self.st, open(tmp, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        os.replace(tmp, self.state_path)

    def _fill(self, key, split):
        tab = self.st.setdefault(key, {})
        todo = [(d, a) for d in self.st["D"] for a in self.st["A"] if f"{d['name']}|{a['name']}" not in tab]
        jobs = [(d, a, f, split) for d, a in todo for f in FOLDS]
        t = time.time()
        res = self.pool.map(_eval_job, jobs, chunksize=1)
        for i, (d, a) in enumerate(todo):
            tot = {}
            for r in res[i * len(FOLDS):(i + 1) * len(FOLDS)]:
                for k, v in r.items():
                    tot[k] = tot.get(k, 0) + v
            tab[f"{d['name']}|{a['name']}"] = summarize(tot)
        print(f"  報酬表[{key}／{split} seed]：新增 {len(todo)} 對（{time.time() - t:.0f} s）")

    def fill_payoff(self):
        """payoff ＝ meta-solver／NashConv／下一輪訓練所用之表（選擇用）。
        payoff_split="test"（E19 原行為）：payoff 取自測試 seed，此時測試 seed 參與策略選擇。
        payoff_split="train"（E30）：payoff 取自訓練 seed；另存 payoff_test（測試 seed）僅供評估，程式中無任何選擇讀取它。"""
        if self.a.payoff_split == "train":
            self._fill("payoff", "train")
            self._fill("payoff_test", "test")
        else:
            self._fill("payoff", "test")
        self.save()

    def matrices(self):
        P = self.st["payoff"]
        A = np.array([[P[f"{d['name']}|{a['name']}"]["u_det"] for a in self.st["A"]] for d in self.st["D"]])
        B = np.array([[P[f"{d['name']}|{a['name']}"]["u_atk"] for a in self.st["A"]] for d in self.st["D"]])
        return A, B

    def g4(self):
        if self.a.smoke:
            print("  （冒煙測試：只有 fold 0，G4 不適用，略過）")
            return
        rq3 = json.load(open(os.path.join(SEV, "RQ3_decision_replay.json"), encoding="utf-8"))
        bad = []
        for a in self.st["A"][:3]:
            got = self.st.get("payoff_test", self.st["payoff"])[f"D0|{a['name']}"]["lure_rate_C_strict"]
            exp = rq3[f"uebound|{RQ3_NAME[(a['attack'], a['param'])]}|C_strict"]["lured_rate"]
            print(f"  G4 {a['name']}：誘導率 {got:.4%}（RQ3 {exp:.4%}）")
            if abs(got - exp) > 1e-12:
                bad.append(a["name"])
        # 乾淨（無攻擊）：D0 之誤拒須為 159／15,534（4.9.6）；D-30P：= 步 4 之 xApp 註記（E30 C-2）
        if _DSN == "d30p":
            ann = [json.loads(l) for l in open(os.path.join(SEV, "xapp_trust_annotations_bound_all_uebound_strict_severity.jsonl"))]
            exp_clean = (sum(x["decision"] == "rejected" for x in ann), len(ann))
        else:
            exp_clean = (159, 15534)
        tot = {}
        for r in self.pool.map(_clean_job, range(8)):
            for k, v in r.items():
                tot[k] = tot.get(k, 0) + v
        print(f"  G4 乾淨 D0：rejected {tot['clean_rej']}／{tot['clean_n']}（期望 {exp_clean[0]}／{exp_clean[1]}）")
        if (tot["clean_rej"], tot["clean_n"]) != exp_clean:
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
        while st["round"] <= self.a.max_rounds:
            r = st["round"]
            sig = st["sigma"]
            mdir = os.path.join(self.dir, "models", f"r{r}")
            dname, aname = f"D{r}", f"A{r}"
            dpaths = {str(f): os.path.join(mdir, f"{dname}_f{f}") for f in FOLDS}
            apaths = {str(f): os.path.join(mdir, f"{aname}_f{f}") for f in FOLDS}
            seed_of = lambda role, f: 100000 * a.train_seed + 1000 * r + 10 * f + (0 if role == "det" else 1)
            jobs = ([("det", f, st["A"], sig["A"], a.level, a.br_max, a.br_every, seed_of("det", f), dpaths[str(f)], a.det_mode)
                     for f in FOLDS]
                    + [("atk", f, st["D"], sig["D"], a.level, a.br_max, a.br_every, seed_of("atk", f), apaths[str(f)]) for f in FOLDS])
            t = time.time()
            self.pool.map(_train_job, jobs, chunksize=1)
            print(f"Round {r}：最佳回應訓練完成（{time.time() - t:.0f} s）")
            newD = {"name": dname, "kind": "maskppo", "paths": dpaths, "br_max": a.br_max, "br_every": a.br_every}
            if a.det_mode != "F":
                newD["det_mode"] = a.det_mode
            newA = {"name": aname, "kind": "ppo", "level": a.level, "paths": apaths, "br_max": a.br_max, "br_every": a.br_every}
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
            st.setdefault("nashconv_round1", nashconv)
            thr = REL_STOP * st["nashconv_round1"]
            if self.a.smoke:                                 # 冒煙測試：固定跑 2 輪以測試學過之對手，不套停止規則
                if r >= 2:
                    st["stop"] = "smoke: 2 rounds"; self.save(); break
                continue
            if st["nashconv_round1"] == 0 or (r > 1 and nashconv <= thr):
                st["stop"] = f"NashConv {nashconv:.4f} ≤ {REL_STOP} × 第 1 輪 {st['nashconv_round1']:.4f}（round {r}）"
                self.save()
                break
        else:
            st["stop"] = f"達最大輪數 {self.a.max_rounds}"
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
    ap.add_argument("--br-max", type=int, default=BR_MAX)
    ap.add_argument("--br-every", type=int, default=BR_EVERY)
    ap.add_argument("--smoke", action="store_true", help="冒煙測試：只用 fold 0、輸出至 psro_smoke/；結果不得引用")
    ap.add_argument("--g4-only", action="store_true")
    ap.add_argument("--payoff-split", choices=["test", "train"], default="test",
                    help="選擇用報酬表之資料：test＝E19 原行為；train＝E30（測試 seed 只作評估，審稿 A2）")
    ap.add_argument("--max-rounds", type=int, default=MAX_ROUNDS, help="E19＝6；E30＝12")
    ap.add_argument("--det-mode", choices=["F", "T", "TL"], default="F",
                    help="偵測端最佳回應之型態：F＝E19 之 V-escalate；T／TL＝E30 §2 動態門檻（須 --payoff-split train）")
    args = ap.parse_args()
    if _DSN not in ("d30", "d30p") or os.environ.get("ZT_FUSION_ORDER") != "severity":
        raise SystemExit("須在 ZT_DATASET=d30／d30p 與 ZT_FUSION_ORDER=severity 下執行")
    if args.det_mode != "F" and args.payoff_split != "train":
        raise SystemExit("--det-mode T／TL 屬 E30，須 --payoff-split train")
    import importlib.metadata as md
    meta = {"git_commit": subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
            "packages": {p: md.version(p) for p in ("torch", "gymnasium", "stable-baselines3", "sb3-contrib", "numpy", "nashpy")},
            "hyperparameters": HP, "br_max": args.br_max, "br_every": args.br_every, "smoke": args.smoke, "stop_rule": f"NashConv <= {REL_STOP} x round-1 NashConv", "max_rounds": args.max_rounds, "payoff_split": args.payoff_split, "det_mode": args.det_mode,
            "dataset": _DSN, "delay_source": os.environ.get("ZT_DELAY_SOURCE", "cumulative")}
    global FOLDS, OUT_BASE
    if args.smoke:
        FOLDS, OUT_BASE = [0], OUT_BASE + "_smoke"
    else:
        assert args.br_max == BR_MAX and args.br_every == BR_EVERY, "正式執行須用定案之 BR_MAX／BR_EVERY"
    p = PSRO(args)
    p.st.setdefault("meta_runs", []).append(dict(meta, argv=sys.argv[1:], started=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())))
    p.save()
    p.run()
    p.pool.close(); p.pool.join()


if __name__ == "__main__":
    main()
