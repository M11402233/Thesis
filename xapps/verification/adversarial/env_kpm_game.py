# -*- coding: utf-8 -*-
"""env_kpm_game.py — E19 之兩個 gymnasium 環境（規格 E19 v2 §2–§4、§3a）。

DetectorEnv：學習者為偵測端（MaskablePPO）；一步 = 一個 (節點, 秒) 且其規則下限為 trusted／low-trust
             （下限為 rejected 或 abstain 者由規則直接決定，不交給學習者）；攻擊者取自攻擊者池之混合。
AttackerEnv：學習者為攻擊者（PPO，連續動作）；一步 = 被攻陷 cell 有上報之一秒（注入起點 t0 之後）；
             偵測端取自偵測端池之混合。

PSRO 之混合：每個 episode 開始時依混合機率抽一個純策略（Lanctot et al., 2017 之標準作法）。
"""
import numpy as np
import gymnasium as gym
from gymnasium import spaces
from gymnasium.utils import seeding

import game_core as G

OBS_LEVELS = ("O-full", "O-outcome")


# ----------------------------------------------------------------------------
# 攻擊者之觀測（§4）：自身過去上報、O-full 之判定／O-outcome 之是否被選中、lag1 peer 中位數
# 一律以自身注入前之乾淨平均延遲正規化；不含同秒 peer 中位數（Q4 oracle）。
ATK_SLOT = {"O-full": 4 + 4, "O-outcome": 4 + 1}


def attacker_obs(ep, level):
    ref = ep.atk_ref
    v = [ep.a_prev - 1.0]
    log = {r["k"]: r for r in ep.atk_log}
    for i in range(1, G.K_HIST + 1):
        r = log.get(ep.k - i)
        if r is None or not r["present"]:
            v += [0.0] * ATK_SLOT[level]
            continue
        a_used = ep.a_hist.get(ep.k - i, 1.0)
        v += [1.0, r["reported"] / ref - 1.0, a_used - 1.0,
              (r["peer_med"] / ref - 1.0) if r["peer_med"] is not None else 0.0]
        if level == "O-full":
            oh = [0.0] * 4
            if r["decision"] is not None:
                oh[G.DI[r["decision"]]] = 1.0
            v += oh
        else:
            v += [float(r["selected"])]
    return np.clip(np.asarray(v, dtype=np.float32), -10, 10)


def attacker_obs_dim(level):
    return 1 + G.K_HIST * ATK_SLOT[level]


def new_episode(sd, cell):
    ep = G.Episode(sd, cell)
    pre = [sd.truth[k][cell] for k in range(sd.t0) if cell in sd.truth[k]]
    ep.atk_ref = float(np.mean(pre)) if pre else 1.0
    ep.a_prev, ep.a_hist = 1.0, {}
    return ep


class LearnedAttacker:
    """把訓練好之攻擊者模型包成 run_episode／DetectorEnv 可用之攻擊者（決定性 predict）。"""

    def __init__(self, model, level, name):
        self.model, self.level, self.name = model, level, name

    def t0(self, ep):
        return ep.sd.t0

    def multiplier(self, ep):
        if ep.k < ep.sd.t0 or ep.atk not in ep.sd.windows[ep.k][1]:
            return None
        act, _ = self.model.predict(attacker_obs(ep, self.level), deterministic=True)
        a = float(np.clip(ep.a_prev + G.DELTA * float(np.clip(act[0], -1, 1)), G.A_MIN, G.A_MAX))
        ep.a_prev = a
        ep.a_hist[ep.k] = a
        return a


class LearnedDetector:
    """訓練好之偵測端模型 → det_policy(ep, j)（決定性；以 action mask 保證只能更嚴）。
    det_mode：F＝E19 之 V-escalate（Discrete(3)）；T／TL＝E30 動態門檻（Discrete(9)／Discrete(27)）。"""

    def __init__(self, model, name, det_mode="F"):
        self.model, self.name, self.det_mode = model, name, det_mode

    def __call__(self, ep, j):
        if self.det_mode != "F":
            return int(self.batch(ep.det_obs_th(j)[None, :], ep.mask_th(j)[None, :])[0])
        return int(self.batch(ep.det_obs(j)[None, :], ep.mask(j)[None, :])[0])

    def batch(self, obs, masks):
        act, _ = self.model.predict(obs, action_masks=masks, deterministic=True)
        return np.asarray(act).reshape(-1)


class FloorDetector:
    name = "D0_rules"

    def __call__(self, ep, j):
        return G.det_floor_policy(ep, j)


# ----------------------------------------------------------------------------
class _Base(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, ds, seed_paths, test_path, pool, probs, seed):
        super().__init__()
        self.ds, self.paths, self.test = ds, list(seed_paths), test_path
        assert len(pool) == len(probs) and abs(sum(probs) - 1) < 1e-9
        self.pool, self.probs = pool, np.asarray(probs, dtype=float)
        self._np_random, _ = seeding.np_random(seed)     # 未給 reset seed 時仍決定性

    def _pick(self):
        rng = self.np_random
        f = self.paths[rng.integers(len(self.paths))]
        sd = self.ds.get(f, None if f == self.test else self.test)
        cell = sd.cells_all[rng.integers(len(sd.cells_all))]
        opp = self.pool[rng.choice(len(self.pool), p=self.probs)]
        return sd, cell, opp


class DetectorEnv(_Base):
    """pool = 攻擊者池（ScriptedAttack／LearnedAttacker），probs = σ_A。det_mode：F（E19）｜T｜TL（E30 §2）。"""

    def __init__(self, ds, seed_paths, test_path, attacker_pool, probs, seed=0, det_mode="F"):
        super().__init__(ds, seed_paths, test_path, attacker_pool, probs, seed)
        assert det_mode in G.DET_MODES
        self.det_mode = det_mode
        self.obs_dim = G.Episode.OBS_DIM if det_mode == "F" else G.Episode.OBS_DIM_TH
        self.observation_space = spaces.Box(-10, 10, (self.obs_dim,), np.float32)
        self.action_space = spaces.Discrete({"F": 3, "T": len(G.MOVES), "TL": 3 * len(G.MOVES)}[det_mode])

    def _obs(self):
        return self.ep.det_obs(self.j) if self.det_mode == "F" else self.ep.det_obs_th(self.j)

    def _advance(self):
        """推進至下一個需要偵測端決定之 (節點, 秒)；回傳 False 表示 episode 結束"""
        ep = self.ep
        while not self.queue:
            if self.in_window:
                ep.end()
                self.in_window = False
            if ep.k >= ep.sd.n:
                return False
            self.queue = list(ep.begin(multiplier=self.atk.multiplier(ep)))
            self.in_window = True
        return True

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        sd, cell, self.atk = self._pick()
        self.ep = new_episode(sd, cell)
        self.ep.det_mode = self.det_mode
        self.queue, self.in_window = [], False
        self._advance()
        self.j = self.queue[0]
        return self._obs(), {"seed": sd.seed, "cell": cell, "attacker": self.atk.name}

    def action_masks(self):
        return self.ep.mask(self.j) if self.det_mode == "F" else self.ep.mask_th(self.j)

    def step(self, action):
        ep, j = self.ep, self.j
        dec = ep.decide_node(j, int(action)) if self.det_mode == "F" else ep.decide_node_th(j, int(action))
        r = ep.det_reward(j, dec)
        info = {"tampered": ep.is_tampered(j), "decision": dec, "floor": ep.floor[j][0]}
        self.queue.pop(0)
        done = not self._advance()
        if done:
            return np.zeros(self.obs_dim, np.float32), r, True, False, info
        self.j = self.queue[0]
        return self._obs(), r, False, False, info


class AttackerEnv(_Base):
    """pool = 偵測端池（FloorDetector／LearnedDetector），probs = σ_D；level ∈ OBS_LEVELS。"""

    def __init__(self, ds, seed_paths, test_path, detector_pool, probs, level, seed=0):
        super().__init__(ds, seed_paths, test_path, detector_pool, probs, seed)
        assert level in OBS_LEVELS
        self.level = level
        self.observation_space = spaces.Box(-10, 10, (attacker_obs_dim(level),), np.float32)
        self.action_space = spaces.Box(-1.0, 1.0, (1,), np.float32)

    t0_cache = None                                       # 由外部指定 G.T0Cache() 以加速（等價已驗證）

    def _run_window(self, a):
        G.step_window(self.ep, self.det, a)

    def _to_next_present(self):
        ep = self.ep
        while ep.k < ep.sd.n and (ep.k < ep.sd.t0 or ep.atk not in ep.sd.windows[ep.k][1]):
            self._run_window(None)
        return ep.k < ep.sd.n

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        while True:
            sd, cell, self.det = self._pick()
            self.ep = (self.t0_cache.get(sd, cell, self.det, new_episode) if self.t0_cache is not None
                       else new_episode(sd, cell))
            if self._to_next_present():
                break
        return attacker_obs(self.ep, self.level), {"seed": sd.seed, "cell": cell, "detector": self.det.name}

    def step(self, action):
        ep = self.ep
        a = float(np.clip(ep.a_prev + G.DELTA * float(np.clip(action[0], -1, 1)), G.A_MIN, G.A_MAX))
        ep.a_prev = a
        ep.a_hist[ep.k] = a
        self._run_window(a)
        r_log = ep.atk_log[-1]
        r = (1.0 if r_log["lured"] else 0.0) - {"low-trust": G.C_L, "rejected": G.C_R}.get(r_log["decision"], 0.0)
        info = {"a": a, "decision": r_log["decision"], "lured": r_log["lured"]}
        done = not self._to_next_present()
        obs = np.zeros(attacker_obs_dim(self.level), np.float32) if done else attacker_obs(ep, self.level)
        return obs, r, done, False, info
