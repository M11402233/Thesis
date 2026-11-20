#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_RQ3_decision_replay.py — RQ3：排除偽造量測後，還剩多少「可用」？

【「資源」之定義（對齊 4.12.1）】
本研究無排程器、無閉迴路，不量測頻譜使用量。「可用資源」定義為兩個可量測的量：

  (1) 保留可用容量比 ρ（retained eligible capacity / baseline capacity）
      ρ = Σ_t Σ_{j∈A(t)} m_j(t)·K_j ／ Σ_t Σ_{j∈A(t)} K_j
      m_j(t)：Policy Enforcement 輸出之資源准入遮罩（eligibility mask）
      K_j   ：容量參考，取自 resource inventory（場域組態），非上報之 KPM
      A(t)  ：當窗有上報之 mmWave 節點。LTE 錨點為驗證用輔助輸入，不在准入範圍內
      configuration 1 之 7 個 mmWave cell 同為 3.5 GHz／20 MHz（scenario-three.cc 之
      Config::SetDefault，無逐 cell 覆寫），故 K_j 相同，ρ 於數值上等於准入註記之佔比。
      ρ 不是頻譜使用量，亦不能驗證吞吐量上報（4.5.2）。
  (2) 決策品質（decision quality）
      以一個明確定義的消費端決策（流量導向：選延遲最低的 cell）為代理，
      比較三種輸入下之決策結果，並以「真值」計算其實際代價。

第 (2) 點是關鍵：攻擊者謊報延遲以吸引流量，但被導向的流量**實際承受的是該 cell 的真實延遲**。
故「攻擊造成的損失」= 依偽造值所做之選擇，其真值代價與最佳選擇之差距。
此評估方式與電力系統中評估偽資料注入之影響一致：攻擊影響決策，代價以真實狀態計算。

【三種輸入】
  GT       乾淨資料（真值）——決策之最佳上界
  RAW      受攻擊、未驗證——攻擊造成之損失
  VERIFIED 受攻擊、依信任註記過濾——驗證所挽回之損失，以及其代價（可用性下降）

【指標】
  rho            保留可用容量比（乾淨資料上 1−ρ 為政策引致之可用性成本）
  yield          准入之 (節點,窗) 註記比例（K_j 相同時等於 rho）
  availability   該窗仍有 ≥1 個可用候選之比例（過濾過嚴會使決策無從作成）
  regret         realized_true_delay − optimal_true_delay（ms，僅計有決策之窗）
  wrong_rate     所選 cell ≠ 真值最佳 cell 之比例
  lured_rate     攻擊者之 cell 被選中、但其實非最佳之比例（攻擊達成率）

【准入政策】
  C_none             不執行准入（對照）
  C_strict           Policy Enforcement admission=strict 之 admitted view（僅 allow）
  C_restrict_annot   Policy Enforcement admission=restrict_annotated（allow + restrict 附註記；
                     defer／exclude 不准入）。新增之政策，結果另列，不沿用任何既有數字
  C_notrej           僅排除 rejected——**包含 abstain（defer）**，不符合 defer 不准入原則；
                     保留為消費端之寬鬆對照組，非 Policy Enforcement 之准入政策

【註記政策】uebound（定案，主結果）；window（對照）

【範圍與分母】
  只評估注入區間內、真值有 ≥2 個 mmWave 候選之窗；無活躍 mmWave 節點之窗（status=n/a）
  不產生節點註記，自然不在分母內。

【內建一致性檢查】
  乾淨資料上，xApp（run_xapp）之逐 (節點, 窗) 決策須與 E10 之 run_policy 逐筆相同
  （兩種註記政策皆檢查）。RQ3 先前之結果由 run_policy 產生，此檢查確保改用 xApp 後
  C_none／C_strict／C_notrej 之數字不因實作替換而改變。不符即停止、不寫檔。

【重要界定（務必寫進論文）】
  - 導向策略為本研究定義之代理決策（單一新流、以延遲為唯一準則），非真實 RIC 之排程器
  - 未建模 PRB、容量、負載回饋與換手成本
  - 若消費端之目標函數依賴未被驗證之量（如吞吐量，見 4.5.2 B2），驗證層無法提供保護——
    本實驗以延遲為準則，正因其為 S_i 所驗證之維度

跑法：
  python3 run_RQ3_decision_replay.py
  python3 run_RQ3_decision_replay.py --data-dir ./seeds/si_lstm_seeds --out-dir ./results
"""
import os
import sys
import copy
import glob
import json
import argparse
import collections
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gzip
import zt_kpm_xapp as X
from run_E10_D1_policy_ablation import run_policy, load_windows
import datasets as DS
import prb_reader as PRB

X.FUSION_MODE = "bound"

# resource inventory：容量參考 K_j 取自場域組態（configuration 1：各 mmWave cell 3.5 GHz／20 MHz）
RESOURCE_INVENTORY = {c: 20e6 for c in range(2, 9)}
INVENTORY_SOURCE = ("scenario-three.cc configuration 1: Config::SetDefault "
                    "MmWavePhyMacCommon::Bandwidth=20e6, CenterFreq=3.5e9; cells 2-8")

DATA_DIR = DS.DATA_DIR
OUT_DIR = DS.results_dir()

# 攻擊：攻擊者壓低自身回報延遲以吸引流量
ATTACKS = [
    ("clean",      None,   None),
    ("step_x0.8",  "step", 0.80),
    ("step_x0.6",  "step", 0.60),
    ("drift_1pct", "drift", 0.01),
    ("drift_2pct", "drift", 0.02),
]
ANN_POLICIES = [("uebound", "uebound", 1), ("window", "window", 1)]   # 主結果在前
CONSUMERS = ["C_none", "C_strict", "C_restrict_annot", "C_notrej"]


class ListSource(X.IndicationSource):
    """以已載入（或已注入攻擊）之窗序列作為 xApp 之 indication 來源"""

    def __init__(self, windows):
        self._w = windows

    def windows(self):
        return iter(self._w)


def annotate(windows, anchor, binding):
    """經 xApp P1–P3 產出註記；回傳 {k: {node: annotation}}（k 為窗索引）"""
    ann = X.run_xapp(ListSource(windows), anchor, "all", binding=binding, admission="strict")[0]
    idx = {w: k for k, (w, _) in enumerate(windows)}
    by_win = collections.defaultdict(dict)
    for a in ann:
        by_win[idx[a["window"]]][a["node"]] = a
    return by_win


def admitted(consumer, anns, reported):
    """資源准入遮罩：回傳准入之 mmWave 節點集合"""
    if consumer == "C_none":
        return set(reported)
    if consumer == "C_strict":                        # P3 admission=strict 之 admitted view
        return {j for j, a in anns.items() if a["admitted"]}
    if consumer == "C_restrict_annot":                # P3 admission=restrict_annotated
        ok = X.ADMISSION["restrict_annotated"]
        return {j for j, a in anns.items() if a["action"] in ok and not a.get("evidence_gate", False)}
    return {j for j, a in anns.items() if a["decision"] != "rejected"}   # C_notrej（含 abstain）


def true_delays(windows):
    """每窗每 cell 之真實平均延遲（ms）"""
    out = []
    for w, cells in windows:
        import interval_source as _IS
        out.append({c: float(np.mean(_IS.valid_vals(v)))
                    for c, v in cells.items() if c != X.LTE_CELL and _IS.valid_vals(v)})
    return out


def apply_attack(windows, atk_cell, kind, param, t0):
    """攻擊者壓低自身 delay：step 乘以 param；drift 每窗遞減 param×原值"""
    if kind is None:
        return windows
    out = copy.deepcopy(windows)
    for k in range(t0, len(out)):
        cells = out[k][1]
        if atk_cell not in cells:
            continue
        f = param if kind == "step" else max(0.05, 1.0 - param * (k - t0))
        for i in list(cells[atk_cell]):
            if cells[atk_cell][i] is not None:               # 第二階段：缺值不可竄改
                cells[atk_cell][i] *= f
    return out


def decide(reported, admissible):
    """導向：於可用候選中選回報延遲最低者"""
    cand = [c for c in admissible if c in reported]
    if not cand:
        return None
    return min(cand, key=lambda c: reported[c])


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
        files = sorted(glob.glob(os.path.join(d, DS.PATTERN)))
        if len(files) >= 2:
            break
    if len(files) < 2:
        print("資料不足，用 --data-dir 指定。"); return
    print(f"載入 {len(files)} seed\n")

    # ---- 原生 PRB（RQ3_PRB_spec.md v1）：僅於有 du-cell 報表之資料集（D-30）啟用；
    #      無報表時（D-SH 等）輸出與修訂前逐位相同 ----
    prb_on, U, U_sym = False, {}, {}
    if DS.CFG.get("aux_dir"):
        seeds_ = [DS.seed_of(f) for f in files]
        aux_ = {s: os.path.dirname(DS.aux_path(s, "x")) for s in seeds_}
        prb_on = all(any(os.path.exists(os.path.join(aux_[s], f"du-cell-2.txt{z}")) for z in ("", ".gz"))
                     for s in seeds_)
    if prb_on:
        mw = DS.CFG.get("max_window")
        for s in seeds_:
            n, mx, _, bad = PRB.cross_check(aux_[s], mw)                       # 檢查 1
            if bad or n == 0:
                print(f"  ✗ PRB 交叉驗證未通過：seed {s} {bad[:3]}"); sys.exit(2)
            U[s] = {k: e["prb"] / PRB.PRB_CONST for k, e in PRB.load_du_prb(aux_[s], mw).items()}
            den = PRB.SLOTS_PER_S * PRB.SYMS_PER_SLOT
            U_sym[s] = {k: v / den for k, v in PRB.symbols_from_phy(aux_[s], mw).items()}
            print(f"── PRB seed {s}：交叉驗證 ✓（{n} 筆，最大差 {mx:.3f} PRB）")

    # acc[(ann_pol, atk_name, consumer)] = counters
    acc = collections.defaultdict(lambda: {
        "win": 0, "avail": 0, "regret": [], "regret_rel": [], "wrong": 0,
        "lured": 0, "lure_opportunity": 0, "ann": 0, "usable_ann": 0,
        "cap_base": 0.0, "cap_kept": 0.0, "opt_excluded": 0,
        "prb_base": 0.0, "prb_kept": 0.0, "sym_base": 0.0, "sym_kept": 0.0,
        "one_base": 0, "one_kept": 0, "prb_missing": 0})

    # ---- 內建一致性檢查：xApp 與 run_policy 於乾淨資料逐筆相同 ----
    n_diff = 0
    for test in files:
        anchor = X.TrustAnchor([f for f in files if f != test])
        base = load_windows(test)
        for _, binding, L_H in ANN_POLICIES:
            ref, _ = run_policy(base, anchor, binding, L_H)
            ref = {(a["k"], a["node"]): a["decision"] for a in ref}
            got = {(k, j): a["decision"]
                   for k, d in annotate(base, anchor, binding).items() for j, a in d.items()}
            n_diff += len(set(ref.items()) ^ set(got.items()))
    print(f"── 一致性檢查（xApp vs run_policy，乾淨資料）── 差異 {n_diff}")
    if n_diff:
        print("  ✗ 不吻合。停止：不寫入任何輸出。請回報，勿調參數。")
        sys.exit(2)
    print("  ✓ 吻合\n")

    mask_path = os.path.join(out_dir, "RQ3_eligibility_mask.jsonl.gz")
    mask_fh = gzip.open(mask_path, "wt", encoding="utf-8")

    for test in files:
        anchor = X.TrustAnchor([f for f in files if f != test])
        base = load_windows(test)
        sd = DS.seed_of(test)
        td_base = true_delays(base)
        t0 = len(base) // 2
        cells_all = sorted({c for d in td_base for c in d})

        for atk_name, kind, param in ATTACKS:
            atk_cells = cells_all if kind else [None]
            for atk_cell in atk_cells:
                mod = apply_attack(base, atk_cell, kind, param, t0)
                rep = true_delays(mod)                    # 回報值（受攻擊後）
                for ann_name, binding, L_H in ANN_POLICIES:
                    by_win = annotate(mod, anchor, binding)

                    for k in range(t0, len(base)):         # 僅評估注入區間
                        truth = td_base[k]
                        if len(truth) < 2:                 # 無選擇餘地之窗不計
                            continue
                        opt_cell = min(truth, key=lambda c: truth[c])
                        anns = by_win.get(k, {})
                        masks = {}
                        for consumer in CONSUMERS:
                            key = (ann_name, atk_name, consumer)
                            a = acc[key]
                            a["win"] += 1
                            a["ann"] += len(anns)
                            adm = admitted(consumer, anns, rep[k])
                            masks[consumer] = sorted(adm)
                            a["usable_ann"] += len(adm)
                            a["cap_base"] += sum(RESOURCE_INVENTORY[j] for j in rep[k])
                            a["cap_kept"] += sum(RESOURCE_INVENTORY[j] for j in adm)
                            if prb_on:                       # U 取自乾淨模擬（開迴路，見規格 §5）
                                for j in rep[k]:
                                    if (j, k) not in U[sd]:
                                        a["prb_missing"] += 1                    # 檢查 5：不補值
                                    u, us = U[sd].get((j, k), 0.0), U_sym[sd].get((j, k), 0.0)
                                    a["prb_base"] += u; a["sym_base"] += us; a["one_base"] += 1
                                    if j in adm:
                                        a["prb_kept"] += u; a["sym_kept"] += us; a["one_kept"] += 1
                            if opt_cell not in adm:          # 真值最佳者被過濾掉
                                a["opt_excluded"] += 1
                            ch = decide(rep[k], adm)
                            if ch is None:
                                continue
                            a["avail"] += 1
                            g = truth.get(ch, np.nan) - truth[opt_cell]
                            a["regret"].append(g)
                            if truth[opt_cell] > 0:
                                a["regret_rel"].append(g / truth[opt_cell])
                            if ch != opt_cell:
                                a["wrong"] += 1
                            if atk_cell is not None and atk_cell in truth and atk_cell != opt_cell:
                                a["lure_opportunity"] += 1
                                if ch == atk_cell:
                                    a["lured"] += 1
                        mask_fh.write(json.dumps({
                            "seed": os.path.basename(test), "ann_policy": ann_name,
                            "attack": atk_name, "atk_cell": atk_cell, "k": k,
                            "A": sorted(rep[k]),
                            "action": {str(j): x["action"] for j, x in anns.items()},
                            "admitted": masks}) + "\n")
        print(f"完成 {os.path.basename(test)}")
    mask_fh.close()

    res = {}
    for (ann_name, atk_name, consumer), a in acc.items():
        reg = [r for r in a["regret"] if not np.isnan(r)]
        res[f"{ann_name}|{atk_name}|{consumer}"] = {
            "windows": a["win"],
            "rho": a["cap_kept"] / a["cap_base"] if a["cap_base"] else None,
            "usable_yield": a["usable_ann"] / a["ann"] if a["ann"] else None,
            "availability": a["avail"] / a["win"] if a["win"] else None,
            "regret_mean_ms": float(np.mean(reg)) if reg else None,
            "regret_p95_ms": float(np.percentile(reg, 95)) if reg else None,
            "regret_rel_mean": (float(np.mean([r for r in a["regret_rel"]
                                               if not np.isnan(r)]))
                                if a["regret_rel"] else None),
            "optimal_excluded_rate": a["opt_excluded"] / a["win"] if a["win"] else None,
            "wrong_rate": a["wrong"] / a["avail"] if a["avail"] else None,
            "lured_rate": (a["lured"] / a["lure_opportunity"]
                           if a["lure_opportunity"] else None),
        }
        if prb_on:
            r = res[f"{ann_name}|{atk_name}|{consumer}"]
            rp = a["prb_kept"] / a["prb_base"] if a["prb_base"] else None
            r.update({"rho_prb": rp, "prb_visibility_loss": (1 - rp) if rp is not None else None,
                      "rho_prb_from_symbols": a["sym_kept"] / a["sym_base"] if a["sym_base"] else None,
                      "used_rb28_per_window_base": a["prb_base"] * PRB.N_RB_CFG1 / a["win"] if a["win"] else None,
                      "used_rb28_per_window_kept": a["prb_kept"] * PRB.N_RB_CFG1 / a["win"] if a["win"] else None,
                      "_u1_rho": a["one_kept"] / a["one_base"] if a["one_base"] else None,
                      "prb_missing_cell_windows": a["prb_missing"]})
    if prb_on:
        bad = []
        for key, r in res.items():
            if r.get("rho") is not None and abs(r["_u1_rho"] - r["rho"]) > 1e-12:          # 檢查 3
                bad.append(("U≡1 未重現 ρ_cap", key))
            if r["rho_prb"] is not None and abs(r["rho_prb"] - r["rho_prb_from_symbols"]) > 1e-3:  # 檢查 4
                bad.append(("原生 PRB 與符號換算之 ρ_PRB 差 > 1e-3", key, r["rho_prb"], r["rho_prb_from_symbols"]))
            if r["prb_missing_cell_windows"]:                                              # 檢查 5
                bad.append(("缺 PRB 報表", key, r["prb_missing_cell_windows"]))
        print("── PRB 檢查 3（U≡1 重現 ρ_cap）、4（兩種來源一致）、5（無缺報）──", "✗ " + str(bad[:4]) if bad else "✓")
        if bad:
            print("  停止：不寫入任何輸出。請回報，勿調參數。"); sys.exit(2)
        for r in res.values():
            r.pop("_u1_rho")
    res["_meta"] = {"resource_inventory_hz": RESOURCE_INVENTORY,
                    "inventory_source": INVENTORY_SOURCE,
                    "A_t": "mmWave nodes reporting in window t; LTE anchor out of scope",
                    "C_notrej_note": "includes abstain (defer); lenient consumer-side baseline, "
                                     "violates defer-not-admitted",
                    "consistency_xapp_vs_run_policy": "ok"}
    if prb_on:
        res["_meta"]["prb"] = {"spec": "docs/thesis/RQ3_PRB_spec.md v1",
                               "U": "sum_UE RRU.PrbUsedDl.UEID / 139 (clean run, DL only)",
                               "rb_scale": f"absolute RB on configuration-1 scale = U x {PRB.N_RB_CFG1}",
                               "open_loop": "PRB from clean simulation; attack-induced traffic shift not modelled"}
    with open(os.path.join(out_dir, "RQ3_decision_replay.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, ensure_ascii=False)

    for ann_name, *_ in ANN_POLICIES:
        print(f"\n═══ 註記政策：{ann_name} ═══")
        print(f"{'攻擊':<12}{'准入政策':<18}{'ρ':>7}{'可用產出':>9}{'決策可用':>9}"
              f"{'regret(ms)':>11}{'regret%':>9}{'誤選率':>8}{'誘導率':>8}{'最佳被濾':>9}")
        for atk_name, *_ in ATTACKS:
            for consumer in CONSUMERS:
                r = res[f"{ann_name}|{atk_name}|{consumer}"]
                f2 = lambda v, s="": f"{v:{s}}" if v is not None else "   -  "
                print(f"{atk_name:<12}{consumer:<18}{f2(r['rho'],'>7.1%')}"
                      f"{f2(r['usable_yield'],'>9.1%')}{f2(r['availability'],'>9.1%')}"
                      f"{f2(r['regret_mean_ms'],'>11.4f')}{f2(r['regret_rel_mean'],'>9.1%')}"
                      f"{f2(r['wrong_rate'],'>8.1%')}{f2(r['lured_rate'],'>8.1%')}"
                      f"{f2(r['optimal_excluded_rate'],'>9.1%')}")
    if prb_on:
        print("\n═══ 原生 PRB（uebound）：ρ_PRB／PRB 能見度損失 V_PRB ═══")
        for atk_name, *_ in ATTACKS:
            print(f"{atk_name:<12}" + "".join(
                f"{c}: {res[f'uebound|{atk_name}|{c}']['rho_prb']:.1%}／{res[f'uebound|{atk_name}|{c}']['prb_visibility_loss']:.1%}  "
                for c in CONSUMERS))
    print(f"\n寫入 {os.path.join(out_dir, 'RQ3_decision_replay.json')}")
    print(f"寫入 {mask_path}")

    if not args.no_fig:
        draw(res, os.path.join(out_dir, "fig_RQ3_decision_replay.png"))
        if prb_on:
            draw_prb_tradeoff(res, os.path.join(out_dir, "fig_RQ3_prb_tradeoff.png"))


def draw_prb_tradeoff(res, path):
    """保護效果（誘導率）對 PRB 能見度損失；每點 = (攻擊, 准入政策)，uebound"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7.5, 5))
    marks = ["o", "s", "^", "D", "v", "P", "X", "*"]
    for (atk_name, *_), mk in zip(ATTACKS, marks):
        for consumer, col in zip(CONSUMERS, ["#adb5bd", "#2b8a3e", "#e8590c", "#1971c2"]):
            r = res[f"uebound|{atk_name}|{consumer}"]
            if r["lured_rate"] is None or r["prb_visibility_loss"] is None:
                continue
            # C_restrict_annot 與 C_notrej 之數值可能完全相同：前者以空心大標記繪於外圈，避免互相遮蔽
            hollow = consumer == "C_restrict_annot"
            ax.scatter(100 * r["prb_visibility_loss"], 100 * r["lured_rate"], marker=mk, s=150 if hollow else 45,
                       facecolors="none" if hollow else col, edgecolors=col, linewidths=1.6 if hollow else 0.5,
                       zorder=2 if hollow else 3)
    for consumer, col in zip(CONSUMERS, ["#adb5bd", "#2b8a3e", "#e8590c", "#1971c2"]):
        hollow = consumer == "C_restrict_annot"
        ax.scatter([], [], facecolors="none" if hollow else col, edgecolors=col, linewidths=1.6 if hollow else 0.5,
                   s=90 if hollow else 45, label=consumer + (" (hollow)" if hollow else ""))
    for (atk_name, *_), mk in zip(ATTACKS, marks):
        ax.scatter([], [], marker=mk, color="k", label=atk_name)
    ax.set_xlabel("PRB visibility loss V_PRB (% of used PRB excluded from decisions)")
    ax.set_ylabel("lure rate (%)")
    ax.set_title("RQ3: protection vs native-PRB visibility (uebound, open-loop replay)")
    ax.grid(alpha=0.3); ax.legend(fontsize=7, ncol=2)
    fig.tight_layout(); fig.savefig(path, dpi=180); plt.close(fig)


def draw(res, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    atks = [a for a, *_ in ATTACKS]
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.2), sharey=True)
    for ax, ann_name in zip(axes, [p[0] for p in ANN_POLICIES]):
        xs = np.arange(len(atks)); w = 0.2
        for i, (consumer, col) in enumerate(zip(
                CONSUMERS, ["#adb5bd", "#2b8a3e", "#e8590c", "#1971c2"])):
            # 相對 regret（真值最佳延遲之百分比），與 4.12.4 表格同一口徑
            reg = [100 * (res[f"{ann_name}|{a}|{consumer}"]["regret_rel_mean"] or 0) for a in atks]
            ax.bar(xs + (i - 1.5) * w, reg, w, color=col, label=consumer, zorder=3)
        ax2 = ax.twinx()
        av = [res[f"{ann_name}|{a}|C_strict"]["availability"] or 0 for a in atks]
        ax2.plot(xs, av, "o--", color="#c92a2a", lw=1.6, ms=5,
                 label="availability (C_strict)", zorder=4)
        ax2.set_ylim(0, 1.05); ax2.set_ylabel("decision availability", color="#c92a2a")
        ax.set_xticks(xs); ax.set_xticklabels(atks, rotation=15, fontsize=8.5)
        ax.set_ylabel("relative regret on true delay (%)")
        ax.set_title(f"annotation policy: {ann_name}", fontsize=10.5)
        ax.grid(alpha=0.3, axis="y", zorder=0)
        if ann_name == ANN_POLICIES[0][0]:
            h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
            fig.legend(h1 + h2, l1 + l2, fontsize=8.5, loc="lower center", ncol=5, frameon=False)
    fig.suptitle("RQ3: what remains usable after excluding untrusted measurements\n"
                 "(bars = decision cost evaluated on true delays; line = fraction of "
                 "windows where a decision can still be made)", fontsize=11)
    fig.tight_layout(rect=[0, 0.07, 1, 0.9])
    fig.savefig(path, dpi=180)
    print(f"圖已存: {path}")


if __name__ == "__main__":
    main()
