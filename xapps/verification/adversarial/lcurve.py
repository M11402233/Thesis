# -*- coding: utf-8 -*-
"""lcurve.py — R-f 學習曲線（規格 E19 §2b）。只用訓練 seed 評估；不使用測試 seed。

用法：ZT_DATASET=d30 ZT_FUSION_ORDER=severity python lcurve.py --role det|atk
輸出：data/results/d30/drl/lcurve/<role>.json（含每個存檔之分數與 S*）
"""
import os
import sys
import json
import time
import argparse
import numpy as np
import torch

torch.set_num_threads(1)
import game_core as G                      # noqa: E402
import env_kpm_game as E                   # noqa: E402
import psro as PS                          # noqa: E402

OUT = os.path.join(PS.ROOT, "data", "results", "d30", "drl", "lcurve")
CFG = {"det": {"total": 2_000_000, "every": 100_000}, "atk": {"total": 1_000_000, "every": 50_000}}
FOLD, TRAIN_SEED, LEVEL = 0, 0, "O-full"


def score(role, model, ds, test, train, cache, opp):
    """訓練 seed × 全部 cell，決定性策略之每步平均 reward（訓練用 anchor）"""
    R = n = 0.0
    for f in train:
        sd = ds.get(f, test)
        for cell in sd.cells_all:
            if role == "det":
                det = E.LearnedDetector(model, "lc")
                ep = G.run_episode(E.new_episode(sd, cell), det, opp)
                R += ep.stats["det_R"]; n += ep.stats["det_n"]
            else:
                atk = E.LearnedAttacker(model, LEVEL, "lc")
                ep = cache.get(sd, cell, opp, E.new_episode)
                G.run_episode(ep, opp, atk)
                R += ep.stats["atk_R"]; n += ep.stats["atk_n"]
    return R / n if n else float("nan")


def plateau(steps, scores):
    sbar = float(np.mean(scores[-3:]))
    tau = max(0.05 * abs(sbar - scores[0]), 1e-4)
    for i in range(1, len(steps)):
        if all(abs(s - sbar) <= tau for s in scores[i:]):
            return steps[i], sbar, tau, i == len(steps) - 1
    return steps[-1], sbar, tau, True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", choices=["det", "atk"], required=True)
    role = ap.parse_args().role
    from sb3_contrib import MaskablePPO
    from stable_baselines3 import PPO
    ds = G.DataStore(); test = ds.files[FOLD]; train = [f for f in ds.files if f != test]
    cache = G.T0Cache(maxsize=1024)
    st = json.load(open(os.path.join(PS.OUT_BASE, "O-full", "t0", "state.json"), encoding="utf-8"))
    hp = {k: v for k, v in PS.HP.items() if k != "policy"}
    seed = 100000 * TRAIN_SEED + 1000 * 1 + 10 * FOLD + (0 if role == "det" else 1)   # 與 psro.py Round 1 相同
    if role == "det":
        sig = st["sigma"]["A"]
        opps = [G.ScriptedAttack(a["attack"], a["param"]) for a in st["A"]]
        keep = [i for i, p in enumerate(sig) if p > 0]
        env = E.DetectorEnv(ds, train, test, [opps[i] for i in keep], [sig[i] for i in keep], seed=seed)
        model = MaskablePPO("MlpPolicy", env, seed=seed, verbose=0, device="cpu", **hp)
        assert len(keep) == 1
        eval_opp = opps[keep[0]]
    else:
        env = E.AttackerEnv(ds, train, test, [E.FloorDetector()], [1.0], LEVEL, seed=seed)
        env.t0_cache = cache
        model = PPO("MlpPolicy", env, seed=seed, verbose=0, device="cpu", **hp)
        eval_opp = E.FloorDetector()
    c = CFG[role]
    os.makedirs(OUT, exist_ok=True)
    steps, scores, t0 = [0], [score(role, model, ds, test, train, cache, eval_opp)], time.time()   # step 0 = 未訓練之策略
    print(f"{role} step 0：{scores[0]:.5f}", flush=True)
    while steps[-1] < c["total"]:
        model.learn(c["every"], reset_num_timesteps=False)
        steps.append(int(model.num_timesteps))
        scores.append(score(role, model, ds, test, train, cache, eval_opp))
        model.save(os.path.join(OUT, f"{role}_{steps[-1]}"))
        print(f"{role} step {steps[-1]:,}：{scores[-1]:.5f}（{time.time() - t0:.0f} s）", flush=True)
        json.dump({"role": role, "steps": steps, "scores": scores, "fold": FOLD, "train_seed": TRAIN_SEED,
                   "level": LEVEL, "hp": PS.HP, "seed": seed}, open(os.path.join(OUT, f"{role}.json"), "w"), indent=1)
    s_star, sbar, tau, at_end = plateau(steps, scores)
    res = {"role": role, "steps": steps, "scores": scores, "S_star": s_star, "s_bar": sbar, "tau": tau,
           "plateau_only_at_end": at_end, "fold": FOLD, "train_seed": TRAIN_SEED, "level": LEVEL,
           "hp": PS.HP, "seed": seed, "elapsed_s": round(time.time() - t0)}
    json.dump(res, open(os.path.join(OUT, f"{role}.json"), "w"), indent=1)
    print(f"S* = {s_star:,}（s̄ = {sbar:.5f}，τ = {tau:.5f}）" + ("　⚠ 只在最後才平穩：回報使用者" if at_end else ""))


if __name__ == "__main__":
    main()
