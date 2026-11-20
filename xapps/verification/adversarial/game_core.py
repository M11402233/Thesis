# -*- coding: utf-8 -*-
"""game_core.py — E19 賽局之共用核心（規格 docs/thesis/E19_DRL_game_spec.md v2 §2）。

只呼叫既有函式，不複製改寫判定邏輯：
  - 成員關係證據（C_i、H_i-D2、H_i-D1 uebound）取自 zt_kpm_xapp.run_xapp 於乾淨資料之輸出；
  - S_i 每步以 zt_kpm_xapp.verify_si 於（被竄改後之）上報重算；
  - 判定下限以 zt_kpm_xapp.fuse_detail（severity）求得；
  - 導向決策以 run_RQ3_decision_replay.decide（選回報延遲最低者），真值代價同 RQ3。

【為何成員關係證據可預先計算】攻擊者第一步只控制被攻陷 cell 之 delay（§4），不改 UE 之出現與歸屬；
C_i、D2、D1 只依成員關係，故與乾淨資料相同。此不變性由 check_env.py 之 G2a 以完整 run_xapp
於注入後資料逐筆驗證（任何差異即停）。

【實作上之定義（規格未明定處，2026-11-08 記錄於 E19 §2a）】
  - 竄改標籤：該 (節點, 秒) 之任一 UE 上報值與真值不同。
  - 偵測端 reward 之 steering 成本（竄改且判 trusted）：其他節點取其規則下限之判定，
    依 C_strict 准入（僅 trusted），以 RQ3 之相對 regret（(真值[所選]−真值[最佳])/真值[最佳]）計；
    真值候選 < 2 或無可選時為 0。
  - 評估指標（誘導率等）則以當窗實際之全部判定計算，與 RQ3 同口徑。
"""
import os
import sys
import collections
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "residuals"))
_DSN = os.environ.get("ZT_DATASET")
PHASE2 = ("d30p", "d30p1")                                    # 第二階段資料集（與 datasets.PHASE2 相同）
if _DSN not in ("d30",) + PHASE2 or os.environ.get("ZT_FUSION_ORDER") != "severity" or \
        (_DSN in PHASE2) != os.environ.get("ZT_DELAY_SOURCE", "cumulative").startswith("percell"):
    raise SystemExit("E19／E30 環境須在 ZT_FUSION_ORDER=severity 且 ZT_DATASET=d30（累計）或 d30p（ZT_DELAY_SOURCE=percell*）下執行")
import zt_kpm_xapp as X                                   # noqa: E402
import datasets as DS                                     # noqa: E402
from run_E10_D1_policy_ablation import load_windows       # noqa: E402
from run_RQ3_decision_replay import ListSource, decide    # noqa: E402

X.FUSION_MODE = "bound"
assert X.FUSION_ORDER == "severity" and X.D1_BINDING == "uebound"

LTE = X.LTE_CELL
DEC = ["trusted", "low-trust", "rejected", "abstain"]
DI = {d: i for i, d in enumerate(DEC)}
K_HIST = 5                                                # Q-b
# 偵測端 reward（Q-c）
LAM, ALPHA, BETA, MU = 0.3, 1.0, 5.0, 0.05
# 攻擊者（Q-e、Q-f）
A_MIN, A_MAX, DELTA = 0.5, 1.5, 0.05
C_L, C_R = 0.1, 1.0
# E21-S4（規格 E21 §8.9）：可選之下限變體掛鉤。FLOOR_FN(dec, rid, also, si, z) → (dec, rid)。
# 預設 None：行為與 E19 逐位相同（檢查 S4-0）。
FLOOR_FN = None

# E30 §2（docs/thesis/E30_coevolution_spec.md）：動態門檻。格點事先登錄；凍結值 (τ_S, τ_H^reject) = (4.0, 3.0)。
TS_GRID = [2.0 + 0.5 * i for i in range(9)]               # τ_S ∈ [2, 6]，步 0.5
TH_GRID = [2.0 + 0.5 * i for i in range(5)]               # τ_H^reject ∈ [2, 4]，步 0.5；τ_H^warn = τ_H^reject − 1
TAU_S0, TAU_HW0, TAU_HR0 = X.TAU_S, X.TAU_H_WARN, X.TAU_H_REJECT
FROZEN = (TS_GRID.index(TAU_S0), TH_GRID.index(TAU_HR0))
assert TAU_HW0 == TAU_HR0 - 1.0
DET_MODES = ("F", "T", "TL")                              # F = 規則／舊 V-escalate（門檻凍結）；T、TL 見 E30 §2
MOVES = [(ds, dh) for ds in (-1, 0, 1) for dh in (-1, 0, 1)]   # 每秒至多一格；索引 4 = 不動


def _vals(v):
    """第二階段延遲缺值為 None（percell_source.xapp_windows）；D-30 無 None，與 list(v.values()) 相同"""
    return [x for x in v.values() if x is not None]


def _mean(v):
    xs = _vals(v)
    return float(np.mean(xs)) if xs else None


def seed_files():
    f = DS.files()
    assert len(f) == 8, f
    return f


# ----------------------------------------------------------------------------
class SeedData:
    """一個 seed 於一個信任根（anchor）下之乾淨資料與預先計算之成員關係證據。"""

    def __init__(self, path, anchor_files):
        self.path = path
        self.seed = DS.seed_of(path)
        self.anchor = X.TrustAnchor(list(anchor_files))
        self.windows = load_windows(path)
        assert [w for w, _ in self.windows] == list(range(len(self.windows)))
        self.n = len(self.windows)
        self.ci_lists = None
        if _DSN in PHASE2:                               # 第二階段 C_i (A)：RRC 名單（與 TraceReplaySource 相同來源）
            import interval_source as _IS
            self.ci_lists = _IS.ci_lists(path)
        ann = X.run_xapp(self._src(), self.anchor, "all", binding="uebound", admission="strict")[0]
        # ci_run 不在註記中：依序重算（與 run_xapp 同一函式），並核對 C_i 與註記一致
        ci_run, ci_of = 0, {}
        for k, (w, cells) in enumerate(self.windows):
            if self.ci_lists is not None:
                mm, anc = self.ci_lists.get(w, ({}, set()))
                ci, ci_run, _ = X.verify_ci_ref(mm, anc, ci_run, X.CI_REF_MODE)
            else:
                ci, ci_run, _ = X.verify_ci(cells, ci_run)
            ci_of[k] = (ci, ci_run)
        self.ev = {}                                      # (k, node) → (ci, ci_run, d2, d1, d1_ev)
        self.clean_ann = {}
        for a in ann:
            k, j = a["window"], a["node"]
            ci, run = ci_of[k]
            assert a["C_i"] == ci
            self.ev[(k, j)] = (ci, run, a["H_i_D2"], a["H_i_D1"], a["evidence"].get("D1"))
            self.clean_ann[(k, j)] = (a["decision"], a["rule_id"])
        self.nodes = {k: sorted(c for c in cells if c != LTE) for k, (w, cells) in enumerate(self.windows)}
        self.truth = [{c: _mean(v) for c, v in cells.items() if c != LTE and _vals(v)}
                      for _, cells in self.windows]
        self.cells_all = sorted({c for d in self.truth for c in d})
        self.t0 = self.n // 2                             # 與 RQ3 相同之注入起點
        self._ev_h = None

    def _src(self):
        src = ListSource(self.windows)
        src.ci_lists = self.ci_lists                      # None 時 run_xapp 行為不變
        return src

    @property
    def ev_h(self):
        """E30：各 τ_H^reject 格點下之 D1 證據 {(k, node): [(d1, d1_ev) × len(TH_GRID)]}。
        D1 只依成員關係（攻擊者只改 delay），故於乾淨資料以 run_xapp 各跑一次即得；凍結格點須與 self.ev 相同。"""
        if self._ev_h is None:
            out = collections.defaultdict(list)
            try:
                for th in TH_GRID:
                    X.TAU_H_REJECT, X.TAU_H_WARN = th, th - 1.0
                    ann = X.run_xapp(self._src(), self.anchor, "all", binding="uebound", admission="strict")[0]
                    for a in ann:
                        out[(a["window"], a["node"])].append((a["H_i_D1"], a["evidence"].get("D1")))
            finally:
                X.TAU_H_REJECT, X.TAU_H_WARN = TAU_HR0, TAU_HW0
            for key, (ci, run, d2, d1, d1_ev) in self.ev.items():
                assert out[key][FROZEN[1]] == (d1, d1_ev), ("E30 C-1：凍結 τ_H 之 D1 與 E19 不同", key)
            self._ev_h = dict(out)
        return self._ev_h


class DataStore:
    """依 (seed, anchor 排除集合) 快取 SeedData。
    評估：anchor = 其餘 7 seed（重現第四章）；訓練：anchor 另排除該 fold 之測試 seed（避免測試資料進入信任根）。"""

    def __init__(self):
        self.files = seed_files()
        self._c = {}

    def get(self, seed_path, test_path=None):
        excl = frozenset({seed_path} | ({test_path} if test_path else set()))
        if excl not in self._c:
            self._c[excl] = SeedData(seed_path, [f for f in self.files if f not in excl])
        return self._c[excl]


# ----------------------------------------------------------------------------
class Episode:
    """一個 episode：一個 seed、一個被攻陷 cell、0–299 窗。
    攻擊以 modifier(k, cells_of_atk_cell) 表示：就地修改受攻擊 cell 之 {imsi: delay}；None 表示不修改。"""

    def __init__(self, sd, atk_cell, det_mode="F"):
        self.sd, self.atk = sd, atk_cell
        self.det_mode = det_mode                          # E30：F（預設，E19 行為）｜T｜TL
        self.th = {}                                      # E30：node → (τ_S 索引, τ_H 索引)；缺 = FROZEN
        self.k = 0
        self.hist = collections.defaultdict(dict)        # node → {k: feature tuple}
        self.final = {}                                   # (k, node) → (decision, rule_id, source)
        self.atk_log = []                                 # 攻擊者觀測所需之逐窗紀錄
        self.stats = collections.Counter()                # 評估用之累計（end() 更新；見 STATS_DOC）

    # ---- 一窗之開始：套用竄改、求每個節點之規則下限 ----
    def begin(self, multiplier=None, modifier=None):
        sd, k = self.sd, self.k
        w, cells = sd.windows[k]
        mod = dict(cells)
        tampered = False
        self.cur_mult = multiplier if modifier is None else None   # E30 §4：本窗實際乘數（modifier 型攻擊無單一乘數 → 不計特徵）
        if self.atk in cells and (multiplier is not None or modifier is not None):
            ues = dict(cells[self.atk])
            if modifier is not None:
                modifier(k, w, ues)
            else:
                for i in list(ues):
                    if ues[i] is not None:                # 缺值（None）不可竄改、亦非上報值
                        ues[i] *= multiplier
            tampered = any(ues[i] != cells[self.atk][i] for i in ues)
            mod[self.atk] = ues
        self.cells = mod
        self.tampered = tampered
        self.reported = {c: _mean(v) for c, v in mod.items() if c != LTE and _vals(v)}
        self.floor, self.info, self.pending = {}, {}, []
        self._fc = {}
        for j in sd.nodes[k]:
            dec, rid, inf = self.floor_at(j, *self.th.get(j, FROZEN))
            self.floor[j] = (dec, rid)
            self.info[j] = inf
            if self.det_mode != "F" or dec in ("trusted", "low-trust"):   # T／TL：每個節點每秒皆為決策點（選門檻）
                self.pending.append(j)
            else:
                self.final[(k, j)] = (dec, rid, "rule")
        return self.pending

    def floor_at(self, j, si_idx, hi_idx):
        """節點 j 於門檻格點 (si_idx, hi_idx) 下之規則下限 (dec, rid, info)。只呼叫既有函式（verify_si、fuse_detail）；
        門檻以暫時設定 zt_kpm_xapp 之模組常數實現，結束即還原。FROZEN 格點與 E19 逐位相同。"""
        key = (j, si_idx, hi_idx)
        if key in self._fc:
            return self._fc[key]
        sd, k = self.sd, self.k
        ci, run, d2, d1, d1_ev = sd.ev[(k, j)]
        if hi_idx != FROZEN[1]:
            d1, d1_ev = sd.ev_h[(k, j)][hi_idx]
        try:
            X.TAU_S = TS_GRID[si_idx]
            si, z, peer = X.verify_si(self.cells, j, sd.anchor.scale)
        finally:
            X.TAU_S = TAU_S0
        dec, rid, also = X.fuse_detail(ci, run, si, d2, d1, d1_ev, j)
        if FLOOR_FN is not None:
            dec, rid = FLOOR_FN(dec, rid, also, si, z)
        inf = {"si": si, "z": z, "peer": peer, "ci_pending": ci == "violated" and run < X.L_C,
               "d1": d1, "d1_z": (d1_ev or {}).get("z", 0.0) if d1 in ("weak", "strong") else 0.0,
               "rid": rid, "also": also}
        self._fc[key] = (dec, rid, inf)
        return self._fc[key]

    # ---- E30 T／TL：動作 = 門檻移動（9）［× 標籤（3）：0 = 依下限、1 = low-trust、2 = rejected］----
    def _moved(self, j, m):
        s0, h0 = self.th.get(j, FROZEN)
        ds, dh = MOVES[m]
        s1, h1 = s0 + ds, h0 + dh
        return (s1, h1) if 0 <= s1 < len(TS_GRID) and 0 <= h1 < len(TH_GRID) else None

    def mask_th(self, j):
        out = []
        for m in range(len(MOVES)):
            nh = self._moved(j, m)
            if self.det_mode == "T":
                out.append(nh is not None)
                continue
            f = self.floor_at(j, *nh)[0] if nh is not None else None
            out += [nh is not None, f == "trusted", f in ("trusted", "low-trust")]
        return np.array(out, dtype=bool)

    def decide_node_th(self, j, action):
        m, lab = (action, 0) if self.det_mode == "T" else divmod(action, 3)
        nh = self._moved(j, m)
        assert nh is not None and self.mask_th(j)[action], (j, action)
        self.th[j] = nh
        dec, rid, inf = self.floor_at(j, *nh)
        self.floor[j], self.info[j] = (dec, rid), inf
        s = self.stats
        s["th_changes"] += m != 4; s["th_n"] += 1
        s[f"th_s{nh[0]}"] += 1; s[f"th_h{nh[1]}"] += 1
        if lab:
            dec, rid = ("low-trust", "rejected")[lab - 1], "DRL_ESCALATE"
        self.final[(self.k, j)] = (dec, rid, "rule" if rid != "DRL_ESCALATE" else "drl")
        return dec

    def is_tampered(self, j):
        return j == self.atk and self.tampered

    def mask(self, j):
        f = self.floor[j][0]
        return np.array([f == "trusted", True, True], dtype=bool)  # trusted／low-trust／rejected

    def decide_node(self, j, action):
        """action ∈ {0,1,2} = trusted／low-trust／rejected；須滿足下限（只能更嚴）"""
        assert self.mask(j)[action], (j, action, self.floor[j])
        dec = DEC[action]
        rid = self.floor[j][1] if dec == self.floor[j][0] else "DRL_ESCALATE"
        self.final[(self.k, j)] = (dec, rid, "rule" if rid != "DRL_ESCALATE" else "drl")
        return dec

    # ---- steering ----
    def steer(self, decisions):
        """decisions: {node: decision}；C_strict 准入（僅 trusted）。回傳 (所選, 最佳, 相對 regret, 候選數)"""
        truth = self.sd.truth[self.k]
        if len(truth) < 2:
            return None, None, 0.0, len(truth)
        opt = min(truth, key=lambda c: truth[c])
        adm = {j for j, d in decisions.items() if d == "trusted"}
        ch = decide(self.reported, adm)
        if ch is None:
            return None, opt, 0.0, len(truth)
        reg = (truth.get(ch, np.nan) - truth[opt]) / truth[opt] if truth[opt] > 0 else 0.0
        return ch, opt, float(reg), len(truth)

    def det_reward(self, j, dec):
        # E30（D-30P）：abstain（S_i 不可得，fail-closed）在 C_strict 下與 low-trust 同為「不准入」，reward 同 low-trust。
        # E19／D-30 之學習者步從不含 abstain（abstain = 0 或由規則決定），故此對應不影響既有數字。
        if dec == "abstain":
            dec = "low-trust"
        if self.is_tampered(j):
            if dec == "rejected":
                return 1.0
            if dec == "low-trust":
                return LAM
            others = {i: self.floor[i][0] for i in self.floor}
            others[j] = "trusted"
            _, _, reg, _ = self.steer(others)
            return -ALPHA * (0.0 if np.isnan(reg) else reg)
        return {"rejected": -BETA, "low-trust": -MU, "trusted": MU}[dec]

    # ---- 一窗之結束：記錄歷史 ----
    def end(self):
        k = self.k
        decs = {}
        for j in self.sd.nodes[k]:
            dec = self.final[(k, j)][0]
            decs[j] = dec
            inf = self.info[j]
            self.hist[j][k] = (inf["si"] != "unavailable", min(inf["z"] or 0.0, 4 * TAU_S0) / TAU_S0,
                               (inf["peer"] or 0) / 6.0, min(inf["d1_z"], 10.0) / 10.0,
                               {"weak": 0.5, "strong": 1.0}.get(inf["d1"], 0.0), float(inf["ci_pending"]), DI[dec])
        ch, opt, reg, ncand = self.steer(decs)
        self.last_steer = (ch, opt, reg, ncand, decs)
        # ---- 評估累計 ----
        s = self.stats
        for j in self.sd.nodes[k]:
            dec = decs[j]
            if j in self.pending:                         # 偵測端之一步（下限為 trusted／low-trust）
                s["det_R"] += self.det_reward(j, dec); s["det_n"] += 1
            # E30 T／TL 之 u_det：全部 (節點, 秒)（規則決定者亦計，使 F 與 T／TL 同分母可比）；F 之 det_R／det_n 不變
            r_all = self.det_reward(j, dec)
            s["det_R_all"] += r_all; s["det_n_all"] += 1
            # 審查意見（2026-11-20）：決策類別計數與 reward 分項，使 abstain 之 reward 假設可離線重算、並檢查「少做事」
            grp = "tam" if self.is_tampered(j) else "clean"
            s[f"dc_{grp}_{dec}"] += 1
            if grp == "tam" and dec == "trusted":
                s["R_tam_trusted"] += r_all                    # 竄改且判 trusted：steering 成本項（不可由計數推得）
            s["si_unavail"] += self.info[j]["si"] == "unavailable"
            s["floor_" + self.floor[j][0].replace("-", "_")] += 1
            if self.is_tampered(j):
                s["tam_n"] += 1; s["tam_rej"] += dec == "rejected"; s["tam_nontrust"] += dec != "trusted"
            else:
                s["clean_n"] += 1; s["clean_rej"] += dec == "rejected"; s["clean_nontrust"] += dec != "trusted"
        a = self.atk
        if a is not None and k >= self.sd.t0 and a in self.reported and self.cur_mult is not None:
            # E30 §4 行為特徵之可加總累計（被攻陷窗 = t ≥ t0 且被攻陷 cell 有上報；乘數 = 本窗 multiplier）
            am = self.cur_mult
            act = abs(am - 1.0) > DELTA
            s["f_n"] += 1; s["f_sum"] += am - 1.0; s["f_abs"] += abs(am - 1.0); s["f_act"] += act
            prev = getattr(self, "_f_prev", None)
            if prev is not None and prev[0] == k - 1:         # 連續窗才計變化度與作用段（缺報窗截斷段落）
                s["f_dn"] += 1; s["f_dv"] += abs(am - prev[1])
                s["f_seg"] += act and not prev[2]
            else:
                s["f_seg"] += act
            self._f_prev = (k, am, act)
        if a is not None and k >= self.sd.t0 and a in self.reported:   # 攻擊者之一步
            truth = self.sd.truth[k]
            lured = ch is not None and ch == a and ch != opt
            s["atk_R"] += (1.0 if lured else 0.0) - {"low-trust": C_L, "rejected": C_R}.get(decs.get(a), 0.0)
            s["atk_n"] += 1
            # RQ3 口徑之誘導率（C_strict；真值候選 ≥ 2、可作決策、攻擊者 cell 非真值最佳）
            if ncand >= 2 and ch is not None and a in truth and a != opt:
                s["lure_opp"] += 1; s["lure"] += ch == a
        peers = [v for c, v in self.reported.items() if c != a]
        self.atk_log.append({"k": k, "present": a in self.reported, "reported": self.reported.get(a),
                             "true": self.sd.truth[k].get(a), "decision": decs.get(a),
                             "selected": ch == a and ch is not None, "lured": ch == a and ch != opt and ch is not None,
                             "peer_med": float(np.median(peers)) if peers else None, "ncand": ncand})
        self.k += 1
        return decs

    # ---- 偵測端之觀測（不含 peer 中位數與尺度 s）----
    OBS_DIM = (K_HIST + 1) * (1 + 6 + 4)

    def det_obs(self, j):
        k, h, v = self.k, self.hist[j], []
        inf = self.info[j]
        cur = (inf["si"] != "unavailable", min(inf["z"] or 0.0, 4 * TAU_S0) / TAU_S0, (inf["peer"] or 0) / 6.0,
               min(inf["d1_z"], 10.0) / 10.0, {"weak": 0.5, "strong": 1.0}.get(inf["d1"], 0.0),
               float(inf["ci_pending"]), None)
        for t, rec in [(k, cur)] + [(k - i, h.get(k - i)) for i in range(1, K_HIST + 1)]:
            if rec is None:
                v += [0.0] * 11
                continue
            onehot = [0.0] * 4
            if rec[6] is not None:
                onehot[rec[6]] = 1.0
            v += [1.0, float(rec[0]), rec[1], rec[2], rec[3], rec[4], rec[5]] + onehot
        return np.asarray(v, dtype=np.float32)

    OBS_DIM_TH = OBS_DIM + 2

    def det_obs_th(self, j):
        """E30 T／TL：det_obs ＋ 目前門檻（正規化至 [0, 1]）。注意 det_obs 之 z 為凍結 τ_S 尺度，不隨所選門檻變。"""
        s0, h0 = self.th.get(j, FROZEN)
        return np.concatenate([self.det_obs(j), np.asarray([s0 / (len(TS_GRID) - 1), h0 / (len(TH_GRID) - 1)],
                                                           dtype=np.float32)])


# ----------------------------------------------------------------------------
# 偵測端策略：D0 = 規則版（恆選下限）
def det_floor_policy(ep, j):
    return 0 if ep.floor[j][0] == "trusted" else 1


def decide_pending(ep, det_policy):
    """決定當窗全部待決節點。偵測端若提供 batch(obs, masks)，同窗節點以一次前向推論決定
    （同窗各節點之觀測只依過去窗與本窗證據，不依同窗其他節點之判定，故與逐一決定等價；
    此等價由 check_speedup.py 逐位驗證）。"""
    pend = list(ep.pending)
    if not pend:
        return
    if ep.det_mode != "F":                                # E30 T／TL
        if hasattr(det_policy, "batch"):
            acts = det_policy.batch(np.stack([ep.det_obs_th(j) for j in pend]),
                                    np.stack([ep.mask_th(j) for j in pend]))
        else:
            acts = [det_policy(ep, j) for j in pend]
        for j, a in zip(pend, acts):
            ep.decide_node_th(j, int(a))
        return
    if hasattr(det_policy, "batch"):
        acts = det_policy.batch(np.stack([ep.det_obs(j) for j in pend]), np.stack([ep.mask(j) for j in pend]))
        for j, a in zip(pend, acts):
            ep.decide_node(j, int(a))
    else:
        for j in pend:
            ep.decide_node(j, det_policy(ep, j))


def step_window(ep, det_policy, multiplier=None):
    ep.begin(multiplier=multiplier)
    decide_pending(ep, det_policy)
    ep.end()


def run_episode(ep, det_policy, attacker=None):
    """以給定之偵測端策略與攻擊者跑完整個 episode。
    det_policy(ep, j) → action（可另有 batch）；attacker：具 .multiplier(ep) 或 .modifier 之物件，或 None。"""
    if ep.k == 0:
        ep.det_mode = getattr(det_policy, "det_mode", "F")
    assert ep.det_mode == getattr(det_policy, "det_mode", "F"), "episode 與偵測端之 det_mode 不同"
    while ep.k < ep.sd.n:
        if attacker is None:
            ep.begin()
        elif getattr(attacker, "modifier", None) is not None:
            ep.begin(modifier=attacker.modifier if ep.k >= attacker.t0(ep) else None)
        else:
            ep.begin(multiplier=attacker.multiplier(ep))
        decide_pending(ep, det_policy)
        ep.end()
    return ep


class T0Cache:
    """注入起點前之窗與攻擊者無關：依 (seed 資料, 被攻陷 cell, 偵測端) 快取 k = t0 時之 episode 狀態。
    取用時深複製（共用唯讀之 SeedData）。等價由 check_speedup.py 驗證。"""

    def __init__(self, maxsize=4096):
        self._c, self.maxsize = {}, maxsize

    def get(self, sd, cell, det, make):
        key = (id(sd), cell, det.name, getattr(det, "det_mode", "F"))
        if key not in self._c:
            ep = make(sd, cell)
            ep.det_mode = getattr(det, "det_mode", "F")
            while ep.k < sd.t0:
                step_window(ep, det)
            if len(self._c) < self.maxsize:
                self._c[key] = ep
            else:
                return ep
        import copy
        src = self._c[key]
        return copy.deepcopy(src, memo={id(sd): sd})


# ----------------------------------------------------------------------------
# A0：第四章之腳本攻擊（RQ3 之 apply_attack，逐 UE 相乘）
class ScriptedAttack:
    def __init__(self, kind, param):
        self.kind, self.param = kind, param
        self.name = f"{kind}_{param}"

    def t0(self, ep):
        return ep.sd.t0

    def multiplier(self, ep):
        k, t0 = ep.k, ep.sd.t0
        if k < t0:
            return None
        return self.param if self.kind == "step" else max(0.05, 1.0 - self.param * (k - t0))


A0 = [ScriptedAttack("step", 0.60), ScriptedAttack("step", 0.80), ScriptedAttack("drift", 0.01)]   # R-a
