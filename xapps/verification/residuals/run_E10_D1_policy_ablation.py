#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_E10_D1_policy_ablation.py — E10：H_i-D1 證據綁定與持續性政策消融（第四章 4.9.6.5）

【要解決的問題】
乾淨資料上 low-trust 達 73.9%、可直接採信僅 23.5%，其中 92.9% 由 H_i-D1 觸發。
4.9.6 診斷為「證據綁定粒度錯配」：現行實作以場域內任一 UE 之 D1 證據降級該窗全部節點。
本實驗在不重跑 ns-3 的前提下，比較五種政策之 trade-off：

  P0 window-L1   現行（任一 UE 之 D1 證據 → 該窗全部節點）          ← 必須重現 bound/all 數字
  P1 window-L2   window + D1 證據須連續 2 窗成立
  P2 window-L3   window + D1 證據須連續 3 窗成立
  P3 uebound-L1  D1 證據只綁定到該 UE「消失前之 serving mmWave cell」
  P4 uebound-L2  uebound + 連續 2 窗

P3/P4 同時實作了 4.4.0／4.8.5 提出的綁定修正方向：以「UE 消失前之 serving cell」
取代「當窗掛載之 cell」，使 R2_SI_D1_BOUND 首次有合法觸發路徑。

【三組指標，缺一不可】
  1. 乾淨資料之決策分布（可操作性）：trusted／low-trust／abstain／rejected
  2. 注入超時消失之偵測（安全性）：TPR（依注入強度）、偵測延遲
  3. 歸因（UE-bound 專屬）：告警是否綁到正確節點、是否落在有註記的節點上
只報 1 會讓 L_H 越大看起來越好；必須和 2 一起看才是 trade-off。

【內建一致性檢查】
無活躍 mmWave 節點之窗（D-SH 共 10 窗）不產生節點註記（與 zt_kpm_xapp v3 之 status=n/a 一致），
主結果之分母為有效 (節點, 窗) 註記（3,150）。
舊版相容性驗證：以 legacy_none=True 重現舊版之 node=None 窗級註記，
  P0 須等於 742／2335／83／0（n=3160），P3 須等於 1813／575／766／6（n=3160）；
  且新版之有效節點註記須與舊版逐筆一致。任一不符即停止、不寫檔。

【依賴】
同目錄需有「新版」zt_kpm_xapp.py（含 RULE 表、fuse(... d1_ev, target)、FUSION_MODE）。
repo 內舊版不相容——請用你跑出 bound/all 結果的那一版。

跑法：
  python3 run_E10_D1_policy_ablation.py
  python3 run_E10_D1_policy_ablation.py --data-dir ./seeds/si_lstm_seeds --out-dir ./results
"""
import os
import sys
import copy
import glob
import json
import math
import argparse
import collections
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import zt_kpm_xapp as X
except ImportError:
    print("找不到 zt_kpm_xapp.py，請放在同一目錄。")
    raise
if not hasattr(X, "RULE") or "R2_SI_D1_UNBOUND" not in X.RULE:
    raise SystemExit("zt_kpm_xapp.py 為舊版（缺 RULE 綁定規則），請換成新版。")

X.FUSION_MODE = "bound"

DATA_DIR = os.path.expanduser("~/oran-zt-kpm-verification/data/si_lstm_seeds")
OUT_DIR = os.path.expanduser("~/oran-zt-kpm-verification/data/results")

POLICIES = [
    ("P0_window_L1", "window", 1),
    ("P1_window_L2", "window", 2),
    ("P2_window_L3", "window", 3),
    ("P3_uebound_L1", "uebound", 1),
    ("P4_uebound_L2", "uebound", 2),
]
TARGET_Z = [2.0, 2.5, 3.0, 4.0, 6.0]      # 注入強度：停留長度 = median + z·σ
EXPECTED_COMPAT = {   # 舊版（含 node=None 窗級註記）之乾淨決策分布
    "P0_window_L1":  {"trusted": 742,  "low-trust": 2335, "abstain": 83,  "rejected": 0},
    "P3_uebound_L1": {"trusted": 1813, "low-trust": 575,  "abstain": 766, "rejected": 6},
}
LEVEL = {"none": 0, "weak": 1, "strong": 2}
INV_LEVEL = {0: "normal", 1: "weak", 2: "strong"}


# ==========================================================================
# 資料
# ==========================================================================
def load_windows(path):
    """[(w, {cell: {imsi: delay_ms}})]，與 TraceReplaySource 相同之解析"""
    return list(X.TraceReplaySource(path).windows())


def inject_overtime(windows, imsi, t_idx, L):
    """自索引 t_idx 起 L 窗，將 imsi 由其 mmWave cell 移到 LTE 錨點（超時消失）"""
    out = copy.deepcopy(windows)
    for k in range(t_idx, min(t_idx + L, len(out))):
        w, cells = out[k]
        moved = None
        for c in list(cells):
            if c != X.LTE_CELL and imsi in cells[c]:
                moved = cells[c].pop(imsi)
                if not cells[c]:
                    del cells[c]
        if moved is not None:
            cells.setdefault(X.LTE_CELL, {})[imsi] = moved
    return out


# ==========================================================================
# 政策化之 xApp 主迴圈
# ==========================================================================
def run_policy(windows, anchor, binding, L_H, track=None, legacy_none=False):
    """
    回傳 (annotations, ue_alerts)
      annotations: 逐 (node, window) 之決策（與 zt_kpm_xapp 同格式之精簡版）
      ue_alerts:   {window_index: {imsi: (level, bound_cell)}}  僅記錄合格（過持續門檻）之 D1 證據
    track: 若指定 imsi，額外回傳該 UE 之逐窗合格紀錄（用於注入偵測）
    legacy_none: 僅供舊版相容性驗證——無活躍 mmWave 節點之窗產生 node=None 之窗級註記
    """
    ann, alerts = [], {}
    prev_map, ci_run = {}, 0
    dwell = collections.defaultdict(int)
    persist = collections.defaultdict(int)
    last_serving = {}

    for k, (w, cells) in enumerate(windows):
        cur = collections.defaultdict(set)
        for c, ues in cells.items():
            for i in ues:
                cur[i].add(c)
        for i, cs in cur.items():
            dwell[i] = dwell[i] + 1 if cs == {X.LTE_CELL} else 0
            mm = sorted(c for c in cs if c != X.LTE_CELL)
            if mm:
                last_serving[i] = mm[0]

        # 逐 UE 之 D1 證據強度（與 verify_hi_d1 同一公式）
        levels = {}
        for i, run in dwell.items():
            lv = 0
            if run > 0 and i in anchor.dwell:
                med, sig = anchor.dwell[i]
                z = abs(run - med) / sig if sig > 0 else 0.0
                lv = 2 if z >= X.TAU_H_REJECT else (1 if z >= X.TAU_H_WARN else 0)
            levels[i] = lv
            persist[i] = persist[i] + 1 if lv > 0 else 0

        eligible = {i: lv for i, lv in levels.items() if lv > 0 and persist[i] >= L_H}
        alerts[k] = {i: (lv, last_serving.get(i)) for i, lv in eligible.items()}

        ci, ci_run, _ = X.verify_ci(cells, ci_run)
        d2, _ = X.verify_hi_d2(prev_map, cur)

        mmw = [c for c in sorted(cells) if c != X.LTE_CELL]
        for target in (mmw or ([None] if legacy_none else [])):
            si, z, peer = X.verify_si(cells, target, anchor.scale)
            if binding == "window":
                if eligible:
                    worst = max(eligible, key=lambda i: (eligible[i], dwell[i]))
                    d1 = INV_LEVEL[eligible[worst]]
                    d1_ev = {"imsi": worst, "cells": sorted(cur.get(worst, set()))}
                else:
                    d1, d1_ev = "normal", None
            else:  # uebound：只看消失前 serving cell == target 之 UE
                mine = {i: lv for i, lv in eligible.items()
                        if target is not None and last_serving.get(i) == target}
                if mine:
                    worst = max(mine, key=lambda i: (mine[i], dwell[i]))
                    d1 = INV_LEVEL[mine[worst]]
                    d1_ev = {"imsi": worst, "cells": [target]}   # 綁定依據：消失前 serving cell
                else:
                    d1, d1_ev = "normal", None
            dec, rid = X.fuse(ci, ci_run, si, d2, d1, d1_ev, target)
            ann.append({"k": k, "node": target, "decision": dec, "rule_id": rid})
        prev_map = cur
    return ann, alerts


# ==========================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=None)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--no-fig", action="store_true")
    args = ap.parse_args()
    out_dir = args.out_dir or OUT_DIR
    os.makedirs(out_dir, exist_ok=True)

    search = [args.data_dir] if args.data_dir else [
        DATA_DIR, os.path.join("seeds", "si_lstm_seeds"), "."]
    files = []
    for d in search:
        files = sorted(glob.glob(os.path.join(d, "ues1_t300_seed*.txt")))
        if len(files) >= 2:
            break
    if len(files) < 2:
        print("資料不足，用 --data-dir 指定。"); return
    print(f"載入 {len(files)} seed\n")

    res = {}
    for name, binding, L_H in POLICIES:
        clean_dec = collections.Counter()
        clean_rule = collections.Counter()
        n_ann = 0
        compat_dec = collections.Counter()
        compat_row_diff = 0
        ue_windows, ue_alert_windows = 0, 0
        inj = {tz: {"n": 0, "det": 0, "delay": [], "delay_strong": [],
                    "attr_ok": 0, "landed": 0} for tz in TARGET_Z}

        for test in files:
            anchor = X.TrustAnchor([f for f in files if f != test])
            wins = load_windows(test)

            # ---- 1. 乾淨資料 ----
            ann, alerts = run_policy(wins, anchor, binding, L_H)
            for a in ann:
                clean_dec[a["decision"]] += 1
                clean_rule[a["rule_id"]] += 1
            n_ann += len(ann)
            if name in EXPECTED_COMPAT:
                old, _ = run_policy(wins, anchor, binding, L_H, legacy_none=True)
                compat_dec.update(a["decision"] for a in old)
                old_valid = [a for a in old if a["node"] is not None]
                compat_row_diff += (sum(1 for a, b in zip(old_valid, ann) if a != b)
                                    + abs(len(old_valid) - len(ann)))
            for k, (w, cells) in enumerate(wins):
                ue_windows += sum(len(u) for u in cells.values())
                ue_alert_windows += len(alerts[k])

            # ---- 2. 注入超時消失 ----
            orig_cell = {}
            for imsi in anchor.dwell:
                med, sig = anchor.dwell[imsi]
                for tz in TARGET_Z:
                    L = max(2, int(math.ceil(med + tz * sig)))
                    t_idx = None
                    # 注入點：該 UE 於 k−1 與 k 皆掛 mmWave，確保停留計數由 0 起算，
                    # 避免把既有 LTE 停留延長而使延遲被低估
                    def on_mmw(kk):
                        cc = wins[kk][1]
                        return [c for c in cc if c != X.LTE_CELL and imsi in cc[c]]
                    for k in range(max(1, len(wins) // 2), len(wins) - L):
                        mm = on_mmw(k)
                        if mm and on_mmw(k - 1):
                            t_idx = k; orig_cell[imsi] = min(mm); break
                    if t_idx is None:
                        continue
                    iw = inject_overtime(wins, imsi, t_idx, L)
                    ann_i, alerts_i = run_policy(iw, anchor, binding, L_H)
                    inj[tz]["n"] += 1
                    hit = None
                    for k in range(t_idx, t_idx + L):
                        if imsi in alerts_i.get(k, {}):
                            hit = k; break
                    if hit is None:
                        continue
                    inj[tz]["det"] += 1
                    inj[tz]["delay"].append(hit - t_idx)
                    for k in range(hit, t_idx + L):          # 首次達 strong（對齊 4.8.6 之 τ_reject）
                        if alerts_i.get(k, {}).get(imsi, (0,))[0] == 2:
                            inj[tz]["delay_strong"].append(k - t_idx); break
                    bound_cell = alerts_i[hit][imsi][1]
                    if bound_cell == orig_cell[imsi]:
                        inj[tz]["attr_ok"] += 1
                    nodes_now = {a["node"] for a in ann_i if a["k"] == hit}
                    if binding == "uebound":
                        if bound_cell in nodes_now:
                            inj[tz]["landed"] += 1
                    else:
                        if nodes_now - {None}:
                            inj[tz]["landed"] += 1

        res[name] = {
            "binding": binding, "L_H": L_H, "n_annotations": n_ann,
            "clean_decisions": dict(clean_dec),
            "clean_share": {k: v / n_ann for k, v in clean_dec.items()},
            "clean_rules": dict(clean_rule),
            "clean_ue_alert_rate": ue_alert_windows / max(ue_windows, 1),
            "compat": ({"decisions_with_none_rows": dict(compat_dec),
                        "valid_row_diff": compat_row_diff}
                       if name in EXPECTED_COMPAT else None),
            "injection": {
                str(tz): {
                    "n": v["n"],
                    "tpr": v["det"] / v["n"] if v["n"] else None,
                    "mean_delay": float(np.mean(v["delay"])) if v["delay"] else None,
                    "mean_delay_to_strong": (float(np.mean(v["delay_strong"]))
                                             if v["delay_strong"] else None),
                    "attribution_ok": v["attr_ok"] / v["det"] if v["det"] else None,
                    "landed_on_annotation": v["landed"] / v["det"] if v["det"] else None,
                } for tz, v in inj.items()},
        }
        print(f"完成 {name}")

    # ---- 舊版相容性驗證 ----
    ok = True
    print("\n── 舊版相容性驗證（含 node=None 窗級註記）──")
    for name, exp in EXPECTED_COMPAT.items():
        c = res[name]["compat"]
        got = {k: c["decisions_with_none_rows"].get(k, 0) for k in exp}
        ok_n = got == exp and sum(c["decisions_with_none_rows"].values()) == sum(exp.values())
        ok_r = c["valid_row_diff"] == 0
        ok = ok and ok_n and ok_r
        print(f"  {name:<15} 計數 {'✓' if ok_n else '✗'} {got}　有效節點逐筆 "
              f"{'✓' if ok_r else '✗'}（差異 {c['valid_row_diff']}）")
    res["consistency_with_bound_all"] = "ok" if ok else "FAIL"
    if not ok:
        print("  ✗ 不吻合。停止：不寫入任何輸出。請回報，勿調參數。")
        sys.exit(2)
    n_na = 0
    for test in files:
        n_na += sum(1 for _, cells in load_windows(test)
                    if not any(c != X.LTE_CELL for c in cells))
    res["na_windows"] = {"count": n_na, "reason": "no_active_mmwave_node"}

    with open(os.path.join(out_dir, "E10_D1_policy_ablation.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, ensure_ascii=False)

    # ---- 輸出 ----
    print(f"\n無活躍 mmWave 節點之窗（status=n/a，不產生節點註記）：{n_na}")

    print(f"\n── 表一：乾淨資料之決策分布（可操作性；分母 = 有效節點註記 "
          f"{res['P0_window_L1']['n_annotations']}）──")
    print(f"{'政策':<15}{'trusted':>9}{'low-trust':>11}{'abstain':>9}{'rejected':>10}{'UE告警率':>10}")
    for name, *_ in POLICIES:
        s = res[name]["clean_share"]
        print(f"{name:<15}{s.get('trusted',0):>9.1%}{s.get('low-trust',0):>11.1%}"
              f"{s.get('abstain',0):>9.1%}{s.get('rejected',0):>10.1%}"
              f"{res[name]['clean_ue_alert_rate']:>10.1%}")

    print("\n── 表二：注入超時消失之偵測（安全性）── TPR / 平均延遲(窗)")
    print(f"{'政策':<15}" + "".join(f"{'z='+str(tz):>14}" for tz in TARGET_Z))
    for name, *_ in POLICIES:
        row = f"{name:<15}"
        for tz in TARGET_Z:
            v = res[name]["injection"][str(tz)]
            row += (f"{v['tpr']:>7.2f}/{v['mean_delay']:<5.1f} " if v["tpr"] and v["mean_delay"] is not None
                    else f"{(v['tpr'] or 0):>7.2f}/  -   ")
        print(row)

    print("\n── 表二b：達 strong 證據之平均延遲（窗，對齊 4.8.6 之 τ_reject）──")
    print(f"{'政策':<15}" + "".join(f"{'z='+str(tz):>9}" for tz in TARGET_Z))
    for name, *_ in POLICIES:
        row = f"{name:<15}"
        for tz in TARGET_Z:
            v = res[name]["injection"][str(tz)]["mean_delay_to_strong"]
            row += f"{v:>9.1f}" if v is not None else f"{'-':>9}"
        print(row)

    print("\n── 表三：歸因（UE-bound）── 綁到正確節點 / 落在有註記之節點")
    for name, binding, _ in POLICIES:
        if binding != "uebound":
            continue
        row = f"{name:<15}"
        for tz in TARGET_Z:
            v = res[name]["injection"][str(tz)]
            a = v["attribution_ok"]; l = v["landed_on_annotation"]
            row += f"  z={tz}: {a if a is None else f'{a:.2f}'}/{l if l is None else f'{l:.2f}'}"
        print(row)

    print("\n── 乾淨資料 rejected 之來源（UE-bound 使 R2_SI_D1_BOUND 可觸發）──")
    for name, *_ in POLICIES:
        r = res[name]["clean_rules"]
        print(f"  {name:<15} R2_SI_D1_BOUND={r.get('R2_SI_D1_BOUND',0)}  "
              f"R2_SI_D1_UNBOUND={r.get('R2_SI_D1_UNBOUND',0)}")
    print(f"\n寫入 {os.path.join(out_dir, 'E10_D1_policy_ablation.json')}")

    if not args.no_fig:
        draw(res, os.path.join(out_dir, "fig_E10_D1_policy_tradeoff.png"))


def draw(res, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 5))
    tz_ref = "3.0"
    for name, binding, L_H in POLICIES:
        tr = res[name]["clean_share"].get("trusted", 0)
        v = res[name]["injection"][tz_ref]
        d = v["mean_delay"] if v["mean_delay"] is not None else np.nan
        mk = "o" if binding == "window" else "s"
        col = {1: "#1971c2", 2: "#e8590c", 3: "#c92a2a"}[L_H]
        ax.scatter(d, tr, s=120, marker=mk, color=col, zorder=3)
        ax.annotate(f"{name}\nTPR={v['tpr']:.2f}" if v["tpr"] is not None else name,
                    (d, tr), textcoords="offset points", xytext=(8, 4), fontsize=8.5)
    ax.set_xlabel(f"mean detection delay (windows), injected overtime z = {tz_ref}")
    ax.set_ylabel("trusted share on clean data")
    ax.set_title("D1 policy trade-off: usability vs detection latency\n"
                 "(circle = window-level, square = UE-bound; colour = persistence L_H)",
                 fontsize=10.5)
    ax.grid(alpha=0.3)
    ax.margins(x=0.15, y=0.15)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    print(f"圖已存: {path}")


if __name__ == "__main__":
    main()
