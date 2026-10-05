#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
zt_kpm_xapp.py — 零信任 KPM 驗證 xApp(骨架 + runtime benchmark + 融合規則稽核)

【定位】
本模組依 O-RAN xApp 之架構契約實作驗證邏輯:訂閱 → 逐 indication 聚合 →
窗邊界觸發驗證 → 階層式融合 → 發布信任註記。資料來源目前為 trace replay
(IndicationSource 抽象層),E2 binding 尚未完成——將 TraceReplaySource 換成
E2SubscriptionSource 即可接上 live RIC,驗證邏輯不需改動。

【設計特點:唯讀信任根】
與一般會持續 retrain 的 ML xApp 相反,本 xApp 之基線(per-UE-index 停留分布、
global MAD)於啟動時載入後**永不線上更新**,避免攻擊者以緩慢注入養高基線。

【動作模式:註記型(annotation)】
本 xApp 不攔截 KPM 流、亦不下 E2SM-RC control,而是將逐 (node, window) 之
信任狀態寫入共享資料層,由消費端 xApp 自行過濾。

--------------------------------------------------------------------------
【v2 新增:融合規則稽核儀器(階段 0)】
1. RULE 代碼表——每個決策都對應一個可枚舉的 rule_id,取代自由字串,
   使「決策 × 觸發規則」breakdown 可直接對帳第 4.4.3 節的三層規則。
2. 節點綁定檢查——第二層「S_i + H_i-D1 交叉佐證」現在會檢查兩項證據是否
   指向同一節點(D1 證據 UE 當窗是否掛在 S_i 受測 cell 上)。
   實測發現:D1 量的是 LTE-only 停留,觸發 D1 的 UE 必然在 LTE 錨點上,
   故與 mmWave 受測節點在結構上永不重疊——原規則等同把兩個關於不同對象
   的無關告警當成互相印證。
3. 逐節點評估——原實作每窗僅取編號最小的活躍 mmWave cell 為 target
   (cell 2 佔 780/1200 窗),與「逐 (node, window) 註記」之宣稱不符。
   --eval-mode all(預設)改為對每個活躍 mmWave cell 各產一筆註記。
4. si_raw / peer 欄位——記錄 S_i 原始可用性,不受融合順序遮蔽
   (原本 abstain 只有 45 筆,但 S_i unavailable 實際 538 筆,
    其餘被 D1 的 low-trust 搶先)。
5. runtime 環境擷取——CPU、Python 版本、warm-up、重複次數、gc 狀態,
   回應「runtime 量測缺控制條件」之意見。

--------------------------------------------------------------------------
【v3 新增:三階段管線與定案政策(A1,2026-10-05)】
1. 主迴圈依 4.9.2 拆為 P1 證據偵測 → P2 信任評估 → P3 政策執行。
2. D1 節點歸屬預設改為 uebound(4.9.6.5 定案);window 保留為對照組,
   window/bound/all 須重現 742/2335/83/0,否則不寫檔並以 exit 2 結束。
3. P3 依准入政策將信任狀態轉為 allow/restrict/exclude/defer,產出 policy-admitted
   view 與 execution record。defer 與 exclude 於任何准入政策下皆不准入;
   defer 之 fallback 僅記錄,不使該筆 KPM 回到 admitted view。
4. 計時範圍擴為 P1–P3(含 admitted view 之建構)。

【消融開關】
  --fusion legacy   原始規則(d1 in {strong,weak}、不檢查綁定)→ 復現 27 筆 rejected
  --fusion bound    修正規則(僅 strong、且須同節點綁定)
  --eval-mode single  每窗僅評估一個節點(復現原始 1200 筆註記與 runtime)
  --eval-mode all     每窗逐活躍節點評估(對齊 (node,window) 宣稱)
  --d1-binding uebound|window   D1 證據節點歸屬(預設 uebound)
  --admission strict|restrict_annotated   P3 准入政策(預設 strict)

【輸出】
  tag = {fusion}_{eval}_{binding}_{admission}
  <out>/xapp_trust_annotations_<tag>.jsonl   逐 (node,window) 信任註記 + action/admitted
  <out>/xapp_execution_records_<tag>.jsonl   逐窗 execution record(P3)
  <out>/xapp_rule_breakdown_<tag>.json       決策 × 規則 breakdown + 動作分布 + runtime + 環境
  <out>/fig_xapp_runtime_<tag>.png           延遲分布圖

跑法(Windows 上用 python,不是 python3):
  python zt_kpm_xapp.py                                  # 預設 D-SH, bound, all
  python zt_kpm_xapp.py --fusion legacy --eval-mode single   # 復現舊結果
  python zt_kpm_xapp.py --dataset dc                     # replay D-C(60s)
  python zt_kpm_xapp.py --data-dir ./seeds/si_lstm_seeds --out-dir ./results
"""
import os
import sys
import gc
import glob
import json
import time
import platform
import argparse
import collections
import numpy as np

# ---- 預設路徑(可用 --data-dir / --out-dir 覆寫)----
SI_LSTM_DIR = os.path.expanduser("~/oran-zt-kpm-verification/data/si_lstm_seeds")
BATCH_DIR = os.path.expanduser("~/oran-zt-kpm-verification/data/batchFinal_seeds")
OUT_DIR = os.path.expanduser("~/oran-zt-kpm-verification/data/results")

# ---- 定案參數(對齊第四章)----
N_KNOWN = 7
LTE_CELL = 1
TAU_S = 4.0           # S_i 共識殘差門檻
TAU_H_WARN = 2.0      # H_i-D1 low-trust
TAU_H_REJECT = 3.0    # H_i-D1 strong evidence
L_C = 2               # C_i 持續窗
MIN_PEER = 2          # S_i full consensus 下限(peer<2 → unavailable)
NEAR_RT_BUDGET_MS = 10.0   # 保守比較基準,非本系統已證明之 deadline

# ---- 融合規則代碼表:(decision, layer, 說明)----
# layer 對應 4.4.3 的三層:1=硬否決 2=統計證據 3=證據不可得 0=無反例
RULE = {
    "R1_CI_VETO":       ("rejected",  1, "C_i hard veto (run>=L_C)"),
    "R1_CI_PENDING":    ("low-trust", 1, "C_i violated, run<L_C (pending)"),
    "R1_D2_VETO":       ("rejected",  1, "H_i-D2 hard veto (teleport)"),
    "R2_SI_D1_BOUND":   ("rejected",  2, "S_i + D1 cross-corroboration (same node)"),
    "R2_SI_D1_LEGACY":  ("rejected",  2, "S_i + D1 co-occurrence, NO binding check (legacy)"),
    "R2_SI_D1_UNBOUND": ("low-trust", 2, "S_i + D1 co-occurrence (different objects)"),
    "R2_SI_ALONE":      ("low-trust", 2, "S_i alone (escalate on persistence)"),
    "R2_D1_STRONG":     ("low-trust", 2, "H_i-D1 strong evidence -> investigation"),
    "R2_D1_WEAK":       ("low-trust", 2, "H_i-D1 weak evidence"),
    "R3_ABSTAIN":       ("abstain",   3, "S_i unavailable (peer<MIN_PEER)"),
    "R0_CLEAN":         ("trusted",   0, "no counterexample"),
}

# 融合模式(由 --fusion 設定)
#   legacy : d1 in {strong, weak} 即交叉佐證,且不檢查節點綁定(原始實作)
#   bound  : 僅 d1 == strong,且 D1 證據 UE 須掛在 S_i 受測節點上
FUSION_MODE = "bound"

# D1 證據之節點歸屬政策(由 --d1-binding 設定,對齊 4.9.6.5)
#   uebound : 定案。D1 證據僅歸屬於該 UE「消失前之 serving mmWave cell」
#   window  : 對照組。場域內任一 UE 之 D1 證據及於該窗全部節點(須重現 742/2335/83/0)
D1_BINDING = "uebound"
# 舊版相容性驗證:舊版於無活躍 mmWave 節點之窗產生一筆 node=None 之窗級註記(D-SH 共 10 窗)。
# 以 legacy_none=True 重現舊版時,bound/all 須等於下列計數;新版之有效節點註記須與其逐筆一致。
EXPECTED_COMPAT_BOUND_ALL = {
    "window":  {"trusted": 742,  "low-trust": 2335, "abstain": 83,  "rejected": 0},
    "uebound": {"trusted": 1813, "low-trust": 575,  "abstain": 766, "rejected": 6},
}
NA_REASON_NO_NODE = "no_active_mmwave_node"

# ---- P3 Policy Enforcement(對齊 4.4.0 表、4.9.3)----
ACTION = {"trusted": "allow", "low-trust": "restrict",
          "rejected": "exclude", "abstain": "defer"}
# 准入政策:哪些動作之 KPM 進入 policy-admitted view。
# defer 於任何准入政策下皆不准入(fail-closed);exclude 亦然。
#   strict             : 僅 allow 准入(restrict 自決策輸入排除)
#   restrict_annotated : allow 與 restrict 准入,restrict 附限制註記
# 註:RQ3 之 C_notrej(僅排除 rejected、含 abstain)違反 defer 不准入原則,
#     屬消費端之寬鬆對照組,不在本准入政策集合內。
ADMISSION = {"strict": {"allow"}, "restrict_annotated": {"allow", "restrict"}}
ADMISSION_POLICY = "strict"
# defer 之 fallback:僅記錄於 execution record,永不使該筆 KPM 回到 admitted view。
#   none : 消費端當窗不取得該節點之任何輸入(本章評估所用)
DEFER_FALLBACK = "none"

# 窗層級決策彙總用的嚴重度序
SEVERITY = {"trusted": 0, "abstain": 1, "low-trust": 2, "rejected": 3}


# ==========================================================================
# 1. Indication Source 抽象層 —— 換掉這一層即可接 live E2
# ==========================================================================
class IndicationSource:
    """xApp 的資料入口。E2 版本應實作 subscribe() 並於 on_indication 回呼。"""

    def windows(self):
        raise NotImplementedError


class TraceReplaySource(IndicationSource):
    """由 RLC trace 重放 KPM indication(等價於 E2SM-KPM report style)。"""

    def __init__(self, path, preload=True):
        self.path = path
        self._cache = None
        if preload:
            self._cache = self._parse()   # 預載:使 runtime 量測不含檔案 I/O

    def _parse(self):
        buf = collections.defaultdict(lambda: collections.defaultdict(dict))
        with open(self.path) as fh:
            fh.readline()
            for line in fh:
                p = line.split("\t")
                if len(p) < 11:
                    continue
                try:
                    w = int(float(p[0]))
                    cell = int(p[2])
                    imsi = int(p[3])
                    d = float(p[10]) * 1000.0
                except ValueError:
                    continue
                buf[w][cell][imsi] = d
        return [(w, buf[w]) for w in sorted(buf)]

    def windows(self):
        """yield (window_id, {cell: {imsi: delay_ms}})——一個 granularity period 的聚合。"""
        for item in (self._cache if self._cache is not None else self._parse()):
            yield item


# class E2SubscriptionSource(IndicationSource):
#     """TODO: RAN Function ID 2 訂閱,granularity 1s,on_indication 解碼後聚合。
#        驗證邏輯不需改動——僅需在此填入 E2AP/E2SM-KPM binding。"""


# ==========================================================================
# 2. 唯讀信任根 —— 啟動時載入,永不線上更新
# ==========================================================================
class TrustAnchor:
    """per-UE-index 停留基線 + 全域尺度 s。

    註:dwell 以 IMSI 編號為 key 跨 run 彙整,不同 seed 的同號 IMSI 位置不同,
    故為 per-UE-index 基線而非 deployment 意義上的 device-specific 基線。
    """

    def __init__(self, train_files):
        vals, dwell = [], collections.defaultdict(list)
        for f in train_files:
            src = TraceReplaySource(f)
            seq = collections.defaultdict(list)     # imsi -> 狀態序列
            for w, cells in src.windows():
                for c, ues in cells.items():
                    if c != LTE_CELL:
                        vals += list(ues.values())
                present = {i: ("mmw" if any(c != LTE_CELL for c in cells if i in cells[c])
                               else "lte")
                           for c in cells for i in cells[c]}
                for i, st in present.items():
                    seq[i].append(st)
            for i, s in seq.items():
                run = 0
                for st in s:
                    if st == "lte":
                        run += 1
                    else:
                        if run:
                            dwell[i].append(run)
                        run = 0
        med = np.median(vals) if vals else 0.0
        self.scale = (1.4826 * (float(np.median(np.abs(np.array(vals) - med))) + 1e-9)
                      if vals else 1.0)
        self.dwell = {}
        for i, d in dwell.items():
            if len(d) >= 8:
                m = np.median(d)
                mad = np.median(np.abs(np.array(d) - m))
                self.dwell[i] = (float(m), float(1.4826 * mad if mad > 0 else 1.0))
        self.n_dwell_ue = len(self.dwell)
        self.frozen = True                          # 明示:載入後不再更新


# ==========================================================================
# 3. 三殘差驗證器
# ==========================================================================
def verify_ci(cells, prev_violated_run):
    """C_i:全域 IMSI 聯集基數守恆(含 LTE 錨點)。回傳 (verdict, run, evidence)"""
    union = set()
    for c in cells:
        union |= set(cells[c].keys())
    violated = (len(union) != N_KNOWN)
    run = prev_violated_run + 1 if violated else 0
    ev = {"n_total": len(union)}
    if violated:
        # 第一層歸因:未登記成員可鎖定嫌疑 cell
        new = {i for i in union if i > 9000}
        ev["candidate_cells"] = sorted({c for c in cells if set(cells[c]) & new}) if new else []
    return ("violated" if violated else "conserved"), run, ev


def verify_si(cells, target, scale):
    """S_i:跨節點共識殘差。peer<MIN_PEER → unavailable(abstain)

    註:MIN_PEER=2 表示本 xApp 僅在 full-consensus 窗判定 S_i,
    第 4.7.2 節定義的 weak evidence(peer=1)在此併入 unavailable。
    """
    mmw = [c for c in cells if c != LTE_CELL]
    if target is None or target not in cells or target == LTE_CELL:
        return "n/a", None, None
    peers = [c for c in mmw if c != target]
    if len(peers) < MIN_PEER:
        return "unavailable", None, len(peers)
    tgt = float(np.mean(list(cells[target].values())))
    ref = float(np.median([np.mean(list(cells[c].values())) for c in peers]))
    z = abs(tgt - ref) / scale
    return ("violated" if z > TAU_S else "normal"), round(z, 2), len(peers)


def verify_hi_d2(prev_map, cur_map):
    """H_i-D2:觀測層級瞬移斷言(mmWave A → mmWave B 無 LTE 過渡)"""
    for imsi, cur in cur_map.items():
        prev = prev_map.get(imsi, set())
        pm, cm = prev - {LTE_CELL}, cur - {LTE_CELL}
        if pm and cm and not (pm & cm) and LTE_CELL not in cur:
            return "violated", {"imsi": imsi, "from": sorted(pm), "to": sorted(cm)}
    return "normal", None


def verify_hi_d1(dwell_runs, anchor, cur_map):
    """H_i-D1:LTE-only 停留 robust z(per-UE-index 唯讀基線)

    evidence 含 cells:該 UE 當窗實際掛載之 cell 集合,供第二層節點綁定判定。
    註:D1 依定義量測 LTE-only 停留,故觸發 D1 之 UE 必然掛於 LTE 錨點。
    """
    worst, worst_imsi = 0.0, None
    for imsi, run in dwell_runs.items():
        if run <= 0 or imsi not in anchor.dwell:
            continue
        med, sig = anchor.dwell[imsi]
        z = abs(run - med) / sig if sig > 0 else 0.0
        if z > worst:
            worst, worst_imsi = z, imsi
    if worst_imsi is None:
        return "normal", None
    ev = {"z": round(worst, 2), "imsi": worst_imsi,
          "cells": sorted(cur_map.get(worst_imsi, set()))}
    if worst >= TAU_H_REJECT:
        return "strong", ev
    if worst >= TAU_H_WARN:
        return "weak", ev
    return "normal", None


def d1_ue_levels(dwell_runs, anchor):
    """逐 UE 之 D1 證據強度(與 verify_hi_d1 同一公式)。回傳 {imsi: (level, z)},level 0/1/2"""
    out = {}
    for imsi, run in dwell_runs.items():
        if run <= 0 or imsi not in anchor.dwell:
            continue
        med, sig = anchor.dwell[imsi]
        z = abs(run - med) / sig if sig > 0 else 0.0
        lv = 2 if z >= TAU_H_REJECT else (1 if z >= TAU_H_WARN else 0)
        if lv:
            out[imsi] = (lv, z)
    return out


def verify_hi_d1_uebound(levels, dwell_runs, last_serving, target):
    """H_i-D1(uebound):僅取消失前 serving cell == target 之 UE 證據。

    evidence 之 cells 為歸屬節點(消失前 serving cell),非當窗掛載之 cell。
    最差 UE 之挑選與 run_E10_D1_policy_ablation.run_policy 相同:(level, 停留長度)。
    """
    mine = [i for i in levels if target is not None and last_serving.get(i) == target]
    if not mine:
        return "normal", None
    worst = max(mine, key=lambda i: (levels[i][0], dwell_runs[i]))
    lv, z = levels[worst]
    ev = {"z": round(z, 2), "imsi": worst, "cells": [target], "bound_by": "last_serving"}
    return ("strong" if lv == 2 else "weak"), ev


# ==========================================================================
# 4. 階層式融合(對齊 4.4.3)—— 回傳 (decision, rule_id)
# ==========================================================================
def _r(rule_id):
    return RULE[rule_id][0], rule_id


def fuse(ci, ci_run, si, d2, d1, d1_ev=None, target=None):
    """階層式規則融合。decision 一律由 RULE 表反查,確保 code 與 4.4.3 對齊。"""
    # ---- 第一層:硬否決 ----
    if ci == "violated":
        return _r("R1_CI_VETO" if ci_run >= L_C else "R1_CI_PENDING")
    if d2 == "violated":
        return _r("R1_D2_VETO")

    # ---- 第二層:統計證據 ----
    if si == "violated":
        if FUSION_MODE == "legacy":
            # 原始實作:weak 亦視為佐證,且不檢查兩項證據是否指向同一對象
            if d1 in ("strong", "weak"):
                return _r("R2_SI_D1_LEGACY")
        else:
            # 修正:僅 strong(對齊 4.8.5 的 z_d >= tau_H_reject),且須同節點
            if d1 == "strong":
                bound = (target is not None and d1_ev is not None
                         and target in d1_ev.get("cells", []))
                return _r("R2_SI_D1_BOUND" if bound else "R2_SI_D1_UNBOUND")
        return _r("R2_SI_ALONE")
    if d1 == "strong":
        return _r("R2_D1_STRONG")
    if d1 == "weak":
        return _r("R2_D1_WEAK")

    # ---- 第三層:證據不可得 ----
    if si == "unavailable":
        return _r("R3_ABSTAIN")
    return _r("R0_CLEAN")


# ==========================================================================
# 5. P3 Policy Enforcement —— 信任狀態 → 准入動作 → policy-admitted KPM
# ==========================================================================
def enforce(win_ann, cells, w, admission=None):
    """依准入政策將該窗之信任註記轉為動作,並產出 policy-admitted view 與 execution record。

    admitted view 只含被准入節點之 KPM(淺複製,消費端不得回寫);
    defer / exclude 於任何准入政策下皆不進入 admitted view(fail-closed)。

    execution record 之窗層級欄位:
      status       : "processed",或 "n/a"(無判定對象;n/a 為窗之處理狀態,非信任狀態)
      out_of_scope : LTE 錨點——驗證用輔助輸入,不在本次准入政策之作用範圍(非 rejected/defer)
      unannotated  : 應受判定之 mmWave 節點卻缺少註記者(供發現實作缺漏;eval-mode single 下會出現)
    """
    allowed = ADMISSION[admission or ADMISSION_POLICY]
    view = {}
    rec = {"window": w, "allow": [], "restrict": [], "exclude": [], "defer": []}
    for a in win_ann:
        act = ACTION[a["decision"]]
        adm = (act in allowed) and a["node"] is not None
        a["action"], a["admitted"] = act, adm
        if a["node"] is not None:
            rec[act].append(a["node"])
        if adm:
            view[a["node"]] = {"kpm": dict(cells[a["node"]]),
                               "restricted": act == "restrict",
                               "rule_id": a["rule_id"]}
    rec["admitted"] = sorted(view)
    rec["defer_fallback"] = DEFER_FALLBACK if rec["defer"] else None
    annotated = {a["node"] for a in win_ann}
    rec["out_of_scope"] = [LTE_CELL] if LTE_CELL in cells else []
    rec["unannotated"] = sorted(c for c in cells if c != LTE_CELL and c not in annotated)
    if annotated - {None}:
        rec["status"] = "processed"
    else:
        rec["status"], rec["reason"] = "n/a", NA_REASON_NO_NODE
    return view, rec


# ==========================================================================
# 6. xApp 主迴圈:P1 證據偵測 → P2 信任評估 → P3 政策執行
# ==========================================================================
def run_xapp(source, anchor, eval_mode="all", node_of_interest=None, collect=True,
             binding=None, admission=None, legacy_none=False):
    """回傳 (annotations, per-window latency array, per-window record 數, execution records)。

    latency 量測範圍:自窗聚合完成起,至該窗 policy-admitted view 與 execution record
    產出止(P1–P3)。不含檔案 I/O(trace 已預載)、註記序列化與發布。

    無活躍 mmWave 節點之窗不產生節點註記,僅於 execution record 記為 status=n/a。
    legacy_none=True 僅供舊版相容性驗證:重現舊版之 node=None 窗級註記。
    """
    binding = binding or D1_BINDING
    annotations, latencies, recs, exec_recs = [], [], [], []
    prev_map, ci_run = {}, 0
    dwell_runs = collections.defaultdict(int)
    last_serving = {}

    for w, cells in source.windows():
        t0 = time.perf_counter_ns()                   # ← 計時起點

        # ---- P1 證據偵測 ----
        cur_map = collections.defaultdict(set)
        n_rec = 0
        for c, ues in cells.items():
            for i in ues:
                cur_map[i].add(c)
                n_rec += 1
        for i, cs in cur_map.items():
            dwell_runs[i] = dwell_runs[i] + 1 if cs == {LTE_CELL} else 0
            mm = [c for c in cs if c != LTE_CELL]
            if mm:
                last_serving[i] = min(mm)

        mmw_active = [c for c in sorted(cells) if c != LTE_CELL]
        if node_of_interest is not None:
            targets = [node_of_interest]
        elif eval_mode == "single":
            targets = mmw_active[:1]
        else:
            targets = list(mmw_active)
        if not targets and legacy_none:
            targets = [None]

        ci, ci_run, ci_ev = verify_ci(cells, ci_run)
        d2, d2_ev = verify_hi_d2(prev_map, cur_map)
        if binding == "window":
            d1_win, d1_ev_win = verify_hi_d1(dwell_runs, anchor, cur_map)
        else:
            levels = d1_ue_levels(dwell_runs, anchor)

        # ---- P2 信任評估(逐節點)----
        win_ann = []
        for target in targets:
            si, z, peer = verify_si(cells, target, anchor.scale)
            if binding == "window":
                d1, d1_ev = d1_win, d1_ev_win
            else:
                d1, d1_ev = verify_hi_d1_uebound(levels, dwell_runs, last_serving, target)
            decision, rule_id = fuse(ci, ci_run, si, d2, d1, d1_ev, target)
            win_ann.append({
                "window": w, "node": target,
                "decision": decision, "rule_id": rule_id,
                "layer": RULE[rule_id][1], "rule": RULE[rule_id][2],
                "C_i": ci, "S_i": si, "z_S": z,
                "H_i_D2": d2, "H_i_D1": d1,
                "si_raw": si,                    # 不受融合順序遮蔽的原始可用性
                "peer": peer,
                "n_mmw_active": len(mmw_active),
                "d1_binding": ((target in d1_ev["cells"])
                               if (d1_ev is not None and target is not None) else None),
                "evidence": {k: v for k, v in
                             (("C_i", ci_ev), ("D2", d2_ev), ("D1", d1_ev)) if v},
            })

        # ---- P3 政策執行 ----
        view, rec = enforce(win_ann, cells, w, admission)

        latencies.append((time.perf_counter_ns() - t0) / 1e6)   # ms
        recs.append(n_rec)
        if collect:
            annotations += win_ann
            exec_recs.append(rec)
        prev_map = cur_map
    return annotations, np.array(latencies), np.array(recs), exec_recs


# ==========================================================================
# 7. 環境擷取(回應 runtime 量測缺控制條件)
# ==========================================================================
def runtime_environment(warmup, repeat, gc_disabled, global_warmup=0):
    cpu = platform.processor() or platform.machine()
    try:
        with open("/proc/cpuinfo") as fh:
            for line in fh:
                if line.lower().startswith("model name"):
                    cpu = line.split(":", 1)[1].strip()
                    break
    except OSError:
        pass
    return {
        "cpu": cpu,
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "numpy": np.__version__,
        "logical_cores": os.cpu_count(),
        "timer": "time.perf_counter_ns",
        "warmup_passes_per_seed": warmup,
        "global_warmup_passes": global_warmup,
        "repeat_passes": repeat,
        "gc_disabled_during_measurement": gc_disabled,
        "file_io_excluded": True,
        "note": "verification-layer compute only; excludes E2SM-KPM decode, SCTP transport, "
                "and shared-data-layer write; single-machine offline, no RIC concurrency",
    }


# ==========================================================================
# 8. main
# ==========================================================================
def main():
    global FUSION_MODE, OUT_DIR, D1_BINDING, ADMISSION_POLICY
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=["dsh", "dc"], default="dsh")
    ap.add_argument("--data-dir", default=None, help="覆寫 seed 目錄")
    ap.add_argument("--out-dir", default=None, help="覆寫輸出目錄")
    ap.add_argument("--fusion", choices=["legacy", "bound"], default="bound",
                    help="legacy=原始規則(復現 27 筆 rejected);bound=須同節點綁定且僅 strong")
    ap.add_argument("--eval-mode", choices=["single", "all"], default="all",
                    help="single=每窗僅評估編號最小之活躍節點(復現舊 runtime);all=逐節點")
    ap.add_argument("--d1-binding", choices=["uebound", "window"], default="uebound",
                    help="uebound=定案(D1 證據歸屬消失前 serving cell);"
                         "window=對照組(須重現 742/2335/83/0)")
    ap.add_argument("--admission", choices=sorted(ADMISSION), default="strict",
                    help="strict=僅 allow 准入;restrict_annotated=allow+restrict 准入。"
                         "defer/exclude 一律不准入")
    ap.add_argument("--warmup", type=int, default=3, help="每 seed 量測前暖身回合數")
    ap.add_argument("--repeat", type=int, default=5, help="量測回合數,取逐窗中位數")
    ap.add_argument("--global-warmup", type=int, default=2,
                    help="seed 迴圈前之 process 層級暖身回合數(消除首個 seed 偏慢)")
    ap.add_argument("--keep-gc", action="store_true", help="量測期間不停用 gc")
    ap.add_argument("--no-fig", action="store_true")
    args = ap.parse_args()

    FUSION_MODE = args.fusion
    D1_BINDING = args.d1_binding
    ADMISSION_POLICY = args.admission
    if args.out_dir:
        OUT_DIR = args.out_dir
    os.makedirs(OUT_DIR, exist_ok=True)

    pattern = "ues1_t300_seed*.txt" if args.dataset == "dsh" else "seed42*.txt"
    search = [args.data_dir] if args.data_dir else [
        SI_LSTM_DIR if args.dataset == "dsh" else BATCH_DIR,
        os.path.join("seeds", "si_lstm_seeds" if args.dataset == "dsh" else "batchFinal_seeds"),
        ".",
    ]
    files = []
    for d in search:
        files = sorted(glob.glob(os.path.join(d, pattern)))
        if len(files) >= 2:
            break
    if len(files) < 2:
        print(f"資料不足(找到 {len(files)} 檔)。用 --data-dir 指定 seed 目錄。")
        return

    print(f"=== 零信任 KPM 驗證 xApp(trace replay,{len(files)} seed)===")
    print(f"    fusion={FUSION_MODE}  eval-mode={args.eval_mode}  "
          f"d1-binding={D1_BINDING}  admission={ADMISSION_POLICY}  "
          f"warmup={args.warmup}  repeat={args.repeat}")

    gc_disabled = not args.keep_gc
    all_ann, all_lat, all_recs, all_exec = [], [], [], []
    per_seed = []
    replays = []          # (src, anchor),供計時外之相容性驗證重用

    # ---- process 層級暖身:打熱 numpy 呼叫路徑與 allocator ----
    # 未做此步時,seed 迴圈的第一個檔案會系統性偏慢(實測達 3 倍),
    # 該偏差大於任何配置間之真實差異,會污染 runtime 比較。
    if args.global_warmup > 0:
        _a = TrustAnchor(files[1:])
        _s = TraceReplaySource(files[0])
        for _ in range(args.global_warmup):
            run_xapp(_s, _a, args.eval_mode, collect=False)
        del _a, _s

    for test in files:
        anchor = TrustAnchor([f for f in files if f != test])   # LOSO:基線不含受測 seed
        src = TraceReplaySource(test)                            # 預載,排除 I/O
        replays.append((src, anchor))

        for _ in range(args.warmup):
            run_xapp(src, anchor, args.eval_mode, collect=False)

        if gc_disabled:
            gc.disable()
        runs, seed_ann = [], []
        for r in range(args.repeat):
            ann, lat, recs, ex = run_xapp(src, anchor, args.eval_mode,
                                          collect=(r == 0))
            runs.append(lat)
            if r == 0:
                seed_ann = ann
                all_ann += ann
                all_recs.append(recs)
                all_exec += [dict(e, seed=os.path.basename(test)) for e in ex]
        if gc_disabled:
            gc.enable()

        lat = np.median(np.vstack(runs), axis=0)   # 逐窗取各回合中位數
        all_lat.append(lat)
        n_ann = len(seed_ann)
        n_full = sum(1 for a in seed_ann if a["si_raw"] in ("normal", "violated"))
        per_seed.append({
            "seed": os.path.basename(test), "windows": int(lat.size),
            "annotations": n_ann,
            "targets_per_window": n_ann / max(lat.size, 1),
            "full_consensus_evals": n_full,
            "mean_ms": float(lat.mean()),
            "p95_ms": float(np.percentile(lat, 95)),
            "p99_ms": float(np.percentile(lat, 99)),
            # 工作量正規化:每次完整共識計算之攤提成本,跨 seed 應近似常數
            "us_per_full_eval": float(lat.sum() * 1000.0 / n_full) if n_full else None,
        })
        print(f"  [{os.path.basename(test)}] {len(lat)} 窗, "
              f"每窗 {lat.mean():.3f} ms (P95 {np.percentile(lat, 95):.3f})")

    lat = np.concatenate(all_lat)
    recs = np.concatenate(all_recs)

    # ---------------- 決策分布 ----------------
    dist = collections.Counter(a["decision"] for a in all_ann)
    n = len(all_ann)
    print(f"\n--- 信任決策分布(逐 (node,window) 註記,n={n})---")
    for k, v in sorted(dist.items(), key=lambda x: -x[1]):
        print(f"  {k:<10} {v:>6} ({v/n:.1%})")

    n_na = sum(1 for e in all_exec if e["status"] == "n/a")
    print(f"  無活躍 mmWave 節點之窗(status=n/a,不產生節點註記):{n_na}")

    # ---------------- 舊版相容性驗證(計時外)----------------
    # 以 legacy_none=True 重現舊版之 node=None 窗級註記:
    #   (a) 計數須等於舊版 bound/all;(b) 其餘有效節點註記須與新版逐筆一致。
    consistency = None
    if (FUSION_MODE == "bound" and args.eval_mode == "all" and args.dataset == "dsh"
            and not args.data_dir):
        exp = EXPECTED_COMPAT_BOUND_ALL[D1_BINDING]
        old = []
        for src, anchor in replays:
            old += run_xapp(src, anchor, args.eval_mode, legacy_none=True)[0]
        old_dist = collections.Counter(a["decision"] for a in old)
        got = {k: old_dist.get(k, 0) for k in exp}
        keys = ("window", "node", "decision", "rule_id", "evidence")
        old_valid = [a for a in old if a["node"] is not None]
        n_row_diff = (sum(1 for a, b in zip(old_valid, all_ann)
                          if any(a[k] != b[k] for k in keys))
                      + abs(len(old_valid) - len(all_ann)))
        ok_count = got == exp and len(old) == sum(exp.values())
        ok_rows = n_row_diff == 0
        consistency = {"compat_expected": exp, "compat_got": got,
                       "compat_n": len(old), "compat_none_rows": len(old) - len(old_valid),
                       "valid_row_diff": n_row_diff,
                       "status": "ok" if (ok_count and ok_rows) else "FAIL"}
        print(f"\n--- 舊版相容性驗證({D1_BINDING}/bound/all,含 node=None 窗級註記)---")
        print(f"  計數 {'✓' if ok_count else '✗'}  期望 {exp},得到 {got}(n={len(old)})")
        print(f"  有效節點逐筆 {'✓' if ok_rows else '✗'}  差異 {n_row_diff} / {len(all_ann)}")
        if not (ok_count and ok_rows):
            print("  停止:不寫入任何輸出。請回報,勿調參數。")
            sys.exit(2)

    # ---------------- P3 動作與准入 ----------------
    acts = collections.Counter(a["action"] for a in all_ann)
    n_adm = sum(1 for a in all_ann if a["admitted"])
    print(f"\n--- P3 准入動作(admission={ADMISSION_POLICY},defer fallback={DEFER_FALLBACK},"
          f"分母 n={n})---")
    for k in ("allow", "restrict", "exclude", "defer"):
        print(f"  {k:<9} {acts.get(k, 0):>6} ({acts.get(k, 0)/n:.1%})")
    print(f"  admitted {n_adm:>6} ({n_adm/n:.1%})")
    # 准入不變式:依政策分別檢查
    never = {"strict": {"restrict", "exclude", "defer"},
             "restrict_annotated": {"exclude", "defer"}}[ADMISSION_POLICY]
    n_bad = sum(1 for a in all_ann if a["admitted"] and a["action"] in never)
    n_scope = sum(1 for e in all_exec if LTE_CELL in e["admitted"])
    n_unann = sum(1 for e in all_exec if e["unannotated"])
    admission_check = {"forbidden_actions": sorted(never), "forbidden_admitted": n_bad,
                       "out_of_scope_admitted": n_scope,
                       "windows_with_unannotated": n_unann}
    print(f"  不變式:{'/'.join(sorted(never))} 准入 {n_bad} 筆;"
          f"LTE 錨點准入 {n_scope} 窗;缺註記之窗 {n_unann}")
    if n_bad or n_scope:
        print("  ✗ 准入不變式失敗。停止:不寫入任何輸出。")
        sys.exit(2)

    # ---------------- 規則 breakdown(核心)----------------
    bd = collections.Counter((a["decision"], a["rule_id"]) for a in all_ann)
    print(f"\n--- 決策 × 觸發規則 breakdown ---")
    for (dec, rid), v in sorted(bd.items(), key=lambda x: -x[1]):
        print(f"  L{RULE[rid][1]}  {dec:<10} {rid:<20} {v:>6} ({v/n:5.1%})  {RULE[rid][2]}")

    # ---------------- S_i 原始可用性 ----------------
    raw = collections.Counter(a["si_raw"] for a in all_ann)
    print(f"\n--- S_i 原始可用性(不受融合順序遮蔽)---")
    for k, v in raw.most_common():
        print(f"  {k:<12} {v:>6} ({v/n:.1%})")
    print(f"  (對照:abstain 決策僅 {dist.get('abstain', 0)} 筆——"
          f"其餘 unavailable 窗被上層規則搶先)")

    # ---------------- D1 節點綁定 ----------------
    bind = collections.Counter(a["d1_binding"] for a in all_ann
                               if a["d1_binding"] is not None)
    tot_bind = sum(bind.values())
    print(f"\n--- D1 證據與 S_i 受測節點之綁定 ---")
    print(f"  同節點 {bind.get(True, 0)} / 不同節點 {bind.get(False, 0)}  (共 {tot_bind})")
    d1_cells = collections.Counter(
        tuple(a["evidence"]["D1"]["cells"]) for a in all_ann if "D1" in a["evidence"])
    print(f"  D1 證據 UE 所在 cell 分布: {dict(d1_cells)}")

    # ---------------- runtime ----------------
    p99 = float(np.percentile(lat, 99))
    bench = {
        "windows": int(lat.size), "annotations": n, "n_seeds": len(files),
        "mean_ms": float(lat.mean()), "median_ms": float(np.median(lat)),
        "p95_ms": float(np.percentile(lat, 95)), "p99_ms": p99,
        "max_ms": float(lat.max()),
        "per_seed": per_seed,
        "seed_mean_spread_ratio": (max(d["mean_ms"] for d in per_seed) /
                                   min(d["mean_ms"] for d in per_seed)) if per_seed else None,
        "seed_normalised_spread_ratio": (
            max(d["us_per_full_eval"] for d in per_seed) /
            min(d["us_per_full_eval"] for d in per_seed)) if per_seed else None,
        "records_per_window_mean": float(recs.mean()),
        "records_per_window_max": int(recs.max()),
        "comparison_budget_ms": NEAR_RT_BUDGET_MS,
        "budget_utilisation_p99": p99 / NEAR_RT_BUDGET_MS,
        "kpm_granularity_ms": 1000.0,
        "granularity_utilisation_p99": p99 / 1000.0,
        "budget_note": "10 ms 僅作為保守比較基準,非本系統已證明須符合之 deadline;"
                       "本研究實際 KPM granularity 為 1 秒",
    }
    print(f"\n--- Runtime benchmark({lat.size} 窗)---")
    print(f"  mean={bench['mean_ms']:.3f} ms  P95={bench['p95_ms']:.3f}  "
          f"P99={bench['p99_ms']:.3f}  max={bench['max_ms']:.3f}")
    print(f"  每窗記錄數 mean={bench['records_per_window_mean']:.2f} "
          f"max={bench['records_per_window_max']}")
    print(f"  佔 1 秒 KPM granularity @P99 = {100*p99/1000.0:.3f}%")
    print(f"  以 {NEAR_RT_BUDGET_MS} ms 為保守比較基準 @P99 = "
          f"{100*bench['budget_utilisation_p99']:.2f}%")
    sp, spn = bench["seed_mean_spread_ratio"], bench["seed_normalised_spread_ratio"]
    print(f"\n--- 跨 seed 工作量與正規化成本 ---")
    print(f"  {'seed':<26}{'targets/win':>12}{'full-eval':>11}{'mean ms':>10}{'us/eval':>10}")
    for d in per_seed:
        print(f"  {d['seed']:<26}{d['targets_per_window']:>12.2f}"
              f"{d['full_consensus_evals']:>11}{d['mean_ms']:>10.3f}"
              f"{d['us_per_full_eval']:>10.1f}")
    print(f"  原始 mean 離散 = {sp:.2f}x;工作量正規化後 = {spn:.2f}x")
    if spn and spn > 1.5:
        print(f"  [警告] 正規化後仍離散 {spn:.2f}x,暖身可能不足或機器負載不穩;"
              f"請提高 --global-warmup / --repeat")
    else:
        print(f"  正規化後離散 <1.5x —— 原始 mean 之差異可由每窗評估節點數與"
              f"S_i 提早返回比例解釋,非量測不穩。")

    env = runtime_environment(args.warmup, args.repeat, gc_disabled, args.global_warmup)
    print(f"\n--- 量測環境 ---")
    for k in ("cpu", "python", "numpy", "logical_cores", "timer"):
        print(f"  {k:<16} {env[k]}")

    # ---------------- 寫檔 ----------------
    # tag 含 binding 與 admission,不覆蓋前版 xapp_*_{fusion}_{eval} 之輸出
    tag = f"{args.fusion}_{args.eval_mode}_{D1_BINDING}_{ADMISSION_POLICY}"
    out_bd = os.path.join(OUT_DIR, f"xapp_rule_breakdown_{tag}.json")
    with open(out_bd, "w", encoding="utf-8") as fh:
        json.dump({
            "config": {"fusion_mode": args.fusion, "eval_mode": args.eval_mode,
                       "d1_binding": D1_BINDING, "admission": ADMISSION_POLICY,
                       "admitted_actions": sorted(ADMISSION[ADMISSION_POLICY]),
                       "defer_fallback": DEFER_FALLBACK,
                       "timing_scope": "P1-P3",
                       "dataset": args.dataset, "N_KNOWN": N_KNOWN, "TAU_S": TAU_S,
                       "TAU_H_WARN": TAU_H_WARN, "TAU_H_REJECT": TAU_H_REJECT,
                       "L_C": L_C, "MIN_PEER": MIN_PEER,
                       "seeds": [os.path.basename(f) for f in files]},
            "decision_distribution": dict(dist),
            "na_windows": {"count": n_na, "reason": NA_REASON_NO_NODE},
            "compat_check": consistency,
            "admission_check": admission_check,
            "action_distribution": dict(acts),
            "admitted": n_adm,
            "rule_breakdown": [{"decision": d, "rule_id": r, "layer": RULE[r][1],
                                "description": RULE[r][2], "count": v,
                                "share": v / n}
                               for (d, r), v in sorted(bd.items(), key=lambda x: -x[1])],
            "si_raw_availability": dict(raw),
            "d1_node_binding": {"same_node": bind.get(True, 0),
                                "different_node": bind.get(False, 0),
                                "d1_evidence_ue_cells": {str(k): v
                                                         for k, v in d1_cells.items()}},
            "benchmark": bench,
            "environment": env,
        }, fh, indent=2, ensure_ascii=False)

    out_ann = os.path.join(OUT_DIR, f"xapp_trust_annotations_{tag}.jsonl")
    with open(out_ann, "w", encoding="utf-8") as fh:
        for a in all_ann:
            fh.write(json.dumps(a, ensure_ascii=False) + "\n")
    out_ex = os.path.join(OUT_DIR, f"xapp_execution_records_{tag}.jsonl")
    with open(out_ex, "w", encoding="utf-8") as fh:
        for e in all_exec:
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")
    print(f"\n寫入 {out_bd}")
    print(f"寫入 {out_ann}")
    print(f"寫入 {out_ex}")

    if args.no_fig:
        return
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(8, 4.6))
        ax.hist(lat, bins=60, color="#1971c2", alpha=0.85)
        for v, c, l in [(bench["mean_ms"], "#2b8a3e", "mean"),
                        (bench["p95_ms"], "#e8590c", "P95"),
                        (p99, "#c92a2a", "P99")]:
            ax.axvline(v, ls="--", color=c, lw=1.6, label=f"{l} = {v:.3f} ms")
        ax.set_xlabel("per-window verification latency (ms)")
        ax.set_ylabel("count")
        ax.set_title("Zero-trust KPM verification xApp: per-window compute overhead\n"
                     f"({lat.size} windows, {args.eval_mode} eval, {D1_BINDING}, P1-P3; "
                     f"P99 = {p99:.3f} ms)", fontsize=10.5)
        ax.legend(fontsize=9)
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fp = os.path.join(OUT_DIR, f"fig_xapp_runtime_{tag}.png")
        fig.savefig(fp, dpi=150)
        print(f"圖已存: {fp}")
    except ImportError:
        print("未安裝 matplotlib,略過畫圖")


if __name__ == "__main__":
    main()
