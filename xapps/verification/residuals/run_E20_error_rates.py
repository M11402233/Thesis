#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_E20_error_rates.py — 規格 E20（docs/thesis/E20_error_rate_spec.md v1）：兩類誤判率之量測。

FB（誤擋）＝未被竄改之 (節點, 窗) 中未進入准入視圖者之比例；
MF（漏放）＝被竄改之 (節點, 窗) 中進入准入視圖者之比例。
兩種准入政策（strict／restrict_annotated）× 兩套方法（一：端到端計數；二：由各證據比率依規則表組合）。

只呼叫既有函式，不複製判定邏輯：
  - 註記：zt_kpm_xapp.run_xapp（uebound、severity）；LOSO 信任根（其餘 7 seed）；
  - 逐 UE 之 D1 證據：以包裝函式紀錄 zt_kpm_xapp.verify_hi_d1_uebound 之輸入（綁定於該節點之全部 UE），
    再呼叫原函式；反事實（移除單一 UE）亦呼叫原函式與 zt_kpm_xapp.fuse_detail；
  - 注入：run_RQ3_decision_replay.apply_attack（t0 = n//2，與 RQ3、E19 game_core 相同）；
  - 成員序列：run_Hi_D1_performance.load／state_seq／dwell_events／ue_lte_fraction。

內建檢查 E20-0～E20-4（任一失敗即停，不寫輸出，不調參數）；另有 E20-5（PHY 交叉驗證，只報告，不作判準）。

跑法（舊機器）：
  ZT_DATASET=d30 ZT_FUSION_ORDER=severity python3 xapps/verification/residuals/run_E20_error_rates.py
"""
import os
import sys
import gzip
import json
import time
import argparse
import collections
import numpy as np

if os.environ.get("ZT_DATASET") not in ("d30", "d30p") or os.environ.get("ZT_FUSION_ORDER") != "severity":
    raise SystemExit("E20 須在 ZT_DATASET=d30 與 ZT_FUSION_ORDER=severity 下執行")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import zt_kpm_xapp as X                                                      # noqa: E402
import datasets as DS                                                         # noqa: E402
from run_E10_D1_policy_ablation import load_windows                           # noqa: E402
from run_RQ3_decision_replay import ListSource, apply_attack, true_delays     # noqa: E402
from run_Hi_D1_performance import load as load_membership, state_seq, dwell_events, ue_lte_fraction, EDGE_SPLIT  # noqa: E402

X.FUSION_MODE = "bound"
assert X.FUSION_ORDER == "severity" and X.D1_BINDING == "uebound"

REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SEV_DIR = os.path.join(REPO, "data", "results", "d30_fusion_order", "severity")
REF_ANN = os.path.join(SEV_DIR, "xapp_trust_annotations_bound_all_uebound_strict_severity.jsonl")
RQ3_JSON = os.path.join(SEV_DIR, "RQ3_decision_replay.json")
EVAL_FINAL = os.path.join(REPO, "data", "results", "d30", "drl", "psro_newmachine_20261111", "eval_final", "eval_final.json")
OUT_DIR = os.path.join(SEV_DIR, "E20")

POLICIES = ["strict", "restrict_annotated"]
ATTACKS = [("A0_step_0.6", "step", 0.60), ("A0_step_0.8", "step", 0.80), ("A0_drift_0.01", "drift", 0.01)]

# ---- E20-0／E20-3／E20-4 之期望值（論文 4.4.0、4.9.6.6；規格 §6）----
EXP_COUNTS = {"total": 15534, "trusted": 7810, "low-trust": 7565, "rejected": 159, "abstain": 0, "R2_SI_D1_BOUND": 159}
EXP_SEG = [1985, 2026, 1866, 1869, 2055, 1730, 2046, 1957]
EXP_SI_VIOL, EXP_D1_ANY, EXP_INDEP = 408, 7502, 197


def admitted(decision, policy):
    return X.ACTION[decision] in X.ADMISSION[policy]


# ---- 包裝 verify_hi_d1_uebound：紀錄輸入後呼叫原函式（不改判定）----
_ORIG_D1 = X.verify_hi_d1_uebound
LOG = []


def _recording_d1(levels, dwell_runs, last_serving, target):
    bound = sorted(i for i, c in last_serving.items() if target is not None and c == target)
    mine = {i: (levels[i][0], float(levels[i][1]), int(dwell_runs[i])) for i in levels
            if target is not None and last_serving.get(i) == target}
    LOG.append({"target": target, "bound": bound, "mine": mine, "levels_id": id(levels),
                "levels_all": {i: v[0] for i, v in levels.items()}})
    return _ORIG_D1(levels, dwell_runs, last_serving, target)


X.verify_hi_d1_uebound = _recording_d1


def run_annotate(windows, anchor):
    LOG.clear()
    ann = X.run_xapp(ListSource(windows), anchor, "all", binding="uebound", admission="strict")[0]
    if len(LOG) != len(ann):
        stop(f"包裝紀錄數 {len(LOG)} ≠ 註記數 {len(ann)}")
    return ann, list(LOG)


def counterfactual_without(a, log, u):
    """移除 UE u 之 D1 證據後之判定（以原函式重算 D1，再以 fuse_detail 融合）"""
    mine = {i: v for i, v in log["mine"].items() if i != u}
    levels = {i: (v[0], v[1]) for i, v in mine.items()}
    dwell = {i: v[2] for i, v in mine.items()}
    last = {i: log["target"] for i in mine}
    d1, d1_ev = _ORIG_D1(levels, dwell, last, log["target"])
    if a["C_i"] != "conserved":
        stop("乾淨資料出現 C_i 違反，反事實需 ci_run，未定義")
    dec, rid, _ = X.fuse_detail(a["C_i"], 0, a["si_raw"], a["H_i_D2"], d1, d1_ev, log["target"])
    return dec


def stop(msg):
    print(f"\n✗ 檢查未通過：{msg}\n停止：不寫入任何輸出。請回報，勿調參數。")
    sys.exit(2)


def spearman(x, y):
    def rank(v):
        v = np.asarray(v, float); o = np.argsort(v, kind="mergesort"); r = np.empty(len(v))
        r[o] = np.arange(len(v)); s = v[o]; i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and s[j + 1] == s[i]:
                j += 1
            r[o[i:j + 1]] = (i + j) / 2.0; i = j + 1
        return r
    rx, ry = rank(x), rank(y)
    return float(np.corrcoef(rx, ry)[0, 1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phy-seeds", default="all", help="all 或逗號分隔之 seed（Q6 原為一個 seed；v1.1 擴為全部 8 個）")
    ap.add_argument("--no-fig", action="store_true")
    args = ap.parse_args()
    t_start = time.time()
    files = DS.files()
    if len(files) != 8:
        stop(f"seed 數 {len(files)} ≠ 8")
    ref = [json.loads(l) for l in open(REF_ANN, encoding="utf-8")]

    # =====================================================================
    # A. 乾淨重放：FB-1、逐 UE 歸因、方法二之輸入
    # =====================================================================
    print("── A. 乾淨重放（8 seed，LOSO 信任根）──")
    clean = []                   # (seed, ann, log)
    seg = []
    for f in files:
        anchor = X.TrustAnchor([g for g in files if g != f])
        ann, log = run_annotate(load_windows(f), anchor)
        sd = DS.seed_of(f)
        clean += [(sd, a, l) for a, l in zip(ann, log)]
        seg.append(len(ann))
        print(f"  seed {sd}: {len(ann)} 筆")

    # E20-4：seed 切段
    if seg != EXP_SEG:
        stop(f"E20-4 seed 段筆數 {seg} ≠ {EXP_SEG}")
    # E20-0：與註記檔逐筆相同（包含 E20-2 之最嚴重 UE）＋論文計數
    if len(ref) != len(clean):
        stop(f"E20-0 筆數 {len(clean)} ≠ 註記檔 {len(ref)}")
    n_mis = sum(json.loads(json.dumps(a, ensure_ascii=False)) != r for (_, a, _), r in zip(clean, ref))
    if n_mis:
        stop(f"E20-0 重算註記與註記檔不同 {n_mis} 筆")
    dist = collections.Counter(a["decision"] for _, a, _ in clean)
    rules = collections.Counter(a["rule_id"] for _, a, _ in clean)
    got = {"total": len(clean), **{k: dist.get(k, 0) for k in ("trusted", "low-trust", "rejected", "abstain")},
           "R2_SI_D1_BOUND": rules.get("R2_SI_D1_BOUND", 0)}
    if got != EXP_COUNTS:
        stop(f"E20-0 計數 {got} ≠ {EXP_COUNTS}")
    print(f"  E20-4 ✓ seed 段 {seg}")
    print(f"  E20-0 ✓ 15,534 筆與註記檔逐筆相同；{got}")
    # E20-2：由紀錄之全部綁定 UE 重新挑出最嚴重 UE，須與註記檔之 D1 證據 imsi 逐筆相同
    n2 = n2_bad = 0
    for (_, a, l), r in zip(clean, ref):
        ev = r["evidence"].get("D1")
        mine = l["mine"]
        worst = max(mine, key=lambda i: (mine[i][0], mine[i][2])) if mine else None
        if (ev or {}).get("imsi") != worst:
            n2_bad += 1
        n2 += 1
    if n2_bad:
        stop(f"E20-2 最嚴重 UE 與註記檔不同 {n2_bad}／{n2}")
    print(f"  E20-2 ✓ 最嚴重 UE 逐筆相同（{n2} 筆）")

    # ---- FB-1 ----
    N = len(clean)
    fb1 = {}
    for pol in POLICIES:
        blk = [(sd, a) for sd, a, _ in clean if not admitted(a["decision"], pol)]
        by_rule = collections.Counter(a["rule_id"] for _, a in blk)
        per_seed = {}
        for sd in sorted({s for s, _, _ in clean}):
            n_s = sum(1 for s, _, _ in clean if s == sd)
            per_seed[str(sd)] = sum(1 for s, _ in blk if s == sd) / n_s
        fb1[pol] = {"blocked": len(blk), "n": N, "FB": len(blk) / N, "by_rule": dict(by_rule.most_common()),
                    "per_seed": per_seed, "seed_min": min(per_seed.values()), "seed_max": max(per_seed.values())}
        print(f"  FB-1 {pol:<19} {len(blk):>5}／{N} = {len(blk)/N:.4f}（seed {fb1[pol]['seed_min']:.4f}–{fb1[pol]['seed_max']:.4f}）{dict(by_rule.most_common())}")

    # ---- 方法二之輸入（乾淨）----
    si_v = sum(a["si_raw"] == "violated" for _, a, _ in clean)
    d1_any = sum(a["H_i_D1"] in ("weak", "strong") for _, a, _ in clean)
    d1_s = sum(a["H_i_D1"] == "strong" for _, a, _ in clean)
    p_S, q_any, q_s = si_v / N, d1_any / N, d1_s / N
    indep = si_v * d1_any / N
    print(f"  p_S = {si_v}／{N} = {p_S:.4f}；q_any = {d1_any}／{N} = {q_any:.4f}；q_strong = {d1_s}／{N} = {q_s:.4f}")
    if si_v != EXP_SI_VIOL or d1_any != EXP_D1_ANY or round(indep) != EXP_INDEP:
        stop(f"E20-3 S_i 違反 {si_v}（應 {EXP_SI_VIOL}）、D1 證據 {d1_any}（應 {EXP_D1_ANY}）、預期 {indep:.1f}（應 ≈{EXP_INDEP}）")
    print(f"  E20-3 ✓ 論文獨立假設預期 {si_v} × {d1_any}/{N} = {indep:.1f} ≈ {EXP_INDEP}（論文口徑：D1 任一等級）")

    # 方法二 2a：節點窗邊際比率（只假設 S_i ⟂ D1）
    fb2a = {"restrict_annotated": p_S * q_s, "strict": 1 - (1 - p_S) * (1 - q_any)}
    # 方法二 2b：逐 UE 窗比率 × 每節點每窗之綁定 UE（另假設 UE 之間獨立）
    win_lv = collections.defaultdict(dict)            # (seed) → {levels_id 序: {imsi: lv}}
    per_seed_wins = collections.defaultdict(list)
    seen = set()
    for sd, a, l in clean:
        key = (sd, a["window"])
        if key not in seen:
            seen.add(key); per_seed_wins[sd].append(l["levels_all"])
    f_any, f_s = {}, {}
    for sd, wl in per_seed_wins.items():
        cnt_a, cnt_s = collections.Counter(), collections.Counter()
        for lv in wl:
            for i, v in lv.items():
                cnt_a[i] += 1; cnt_s[i] += v == 2
        for i in range(1, X.N_KNOWN + 1):
            f_any[(sd, i)] = cnt_a[i] / len(wl); f_s[(sd, i)] = cnt_s[i] / len(wl)
    qa_pred, qs_pred, fb2b_s, fb2b_r = [], [], [], []
    for sd, a, l in clean:
        qa = 1 - np.prod([1 - f_any[(sd, i)] for i in l["bound"]]) if l["bound"] else 0.0
        qs = 1 - np.prod([1 - f_s[(sd, i)] for i in l["bound"]]) if l["bound"] else 0.0
        qa_pred.append(qa); qs_pred.append(qs)
        fb2b_r.append(p_S * qs); fb2b_s.append(1 - (1 - p_S) * (1 - qa))
    fb2b = {"restrict_annotated": float(np.mean(fb2b_r)), "strict": float(np.mean(fb2b_s))}
    print(f"  方法二 2a：FB strict {fb2a['strict']:.4f}、restrict_annotated {fb2a['restrict_annotated']:.4f}")
    print(f"  方法二 2b：q_any 預測 {np.mean(qa_pred):.4f}（實際 {q_any:.4f}）、q_strong 預測 {np.mean(qs_pred):.4f}（實際 {q_s:.4f}）；"
          f"FB strict {fb2b['strict']:.4f}、restrict_annotated {fb2b['restrict_annotated']:.4f}")

    # ---- 逐 UE 歸因與移動性 ----
    print("── 逐 UE 歸因 ──")
    ue = collections.defaultdict(lambda: collections.Counter())
    for sd, a, l in clean:
        mine = l["mine"]
        if not mine:
            continue
        for pol in POLICIES:
            if admitted(a["decision"], pol):
                continue
            for u in mine:
                ue[(sd, u)][f"involved_{pol}"] += 1
                if admitted(counterfactual_without(a, l, u), pol):
                    ue[(sd, u)][f"pivotal_{pol}"] += 1
    mob = {}
    for f in files:
        sd = DS.seed_of(f)
        rec = load_membership(f)
        all_w = sorted(set(w for im, wm in rec.items() for w in wm))
        for i in range(1, X.N_KNOWN + 1):
            seq = state_seq(rec.get(i, {}), all_w)
            mob[(sd, i)] = {"M_frac": ue_lte_fraction(seq), "M_count": len(dwell_events(seq)), "n_windows": len(all_w)}
    rows = []
    for (sd, i), m in sorted(mob.items()):
        c = ue[(sd, i)]
        nw = m["n_windows"]
        rows.append({"seed": sd, "imsi": i, **m, "group": "edge" if m["M_frac"] >= EDGE_SPLIT else "resident",
                     **{k: c.get(k, 0) for k in ("involved_strict", "pivotal_strict", "involved_restrict_annotated",
                                                  "pivotal_restrict_annotated")},
                     "f_D1_any_window": f_any[(sd, i)], "f_D1_strong_window": f_s[(sd, i)],
                     "block_share_strict": c.get("involved_strict", 0) / nw,
                     "pivotal_share_strict": c.get("pivotal_strict", 0) / nw})
    tot_piv = sum(r["pivotal_strict"] for r in rows)
    mc = np.array([r["M_count"] for r in rows]); mf = np.array([r["M_frac"] for r in rows])
    bs = np.array([r["block_share_strict"] for r in rows]); ps = np.array([r["pivotal_share_strict"] for r in rows])
    q75 = np.percentile(mc, 75)
    top = mc >= q75
    edge = mf >= EDGE_SPLIT
    mobility = {
        "n_ue_runs": len(rows), "edge": int(edge.sum()), "resident": int((~edge).sum()),
        "spearman_Mcount_vs_block_share_strict": spearman(mc, bs),
        "spearman_Mfrac_vs_block_share_strict": spearman(mf, bs),
        "spearman_Mcount_vs_pivotal_share_strict": spearman(mc, ps),
        "spearman_Mcount_vs_Mfrac": spearman(mc, mf),
        "Mcount_q75": float(q75),
        "pivotal_strict_total": int(tot_piv),
        "pivotal_strict_share_from_top_quartile_Mcount": float(sum(r["pivotal_strict"] for r, t in zip(rows, top) if t) / tot_piv) if tot_piv else None,
        "top_quartile_Mcount_ue_runs": int(top.sum()),
        "pivotal_strict_share_from_edge": float(sum(r["pivotal_strict"] for r, e in zip(rows, edge) if e) / tot_piv) if tot_piv else None,
        "block_share_strict_mean": {"edge": float(bs[edge].mean()), "resident": float(bs[~edge].mean()),
                                    "top_quartile_Mcount": float(bs[top].mean()), "rest": float(bs[~top].mean())},
        "Mcount_bins": [],
    }
    # M-count 分箱：五分位數（資料驅動之分箱，僅供描述；非事前登記）
    edges = [int(e) for e in np.unique(np.percentile(mc, [0, 20, 40, 60, 80]).astype(int))] + [10**9]
    mobility["Mcount_bins_rule"] = "quintile edges of M-count (descriptive, data-driven)"
    for lo, hi in zip(edges[:-1], edges[1:]):
        sel = (mc >= lo) & (mc < hi)
        if sel.any():
            mobility["Mcount_bins"].append({"lo": lo, "hi": hi if hi < 10**9 else None, "n": int(sel.sum()),
                                            "block_share_strict_mean": float(bs[sel].mean()),
                                            "pivotal_share_strict_mean": float(ps[sel].mean())})
    print(f"  UE-run {len(rows)}（edge {int(edge.sum())}／resident {int((~edge).sum())}）；"
          f"Spearman(M-count, 擋下佔比 strict) = {mobility['spearman_Mcount_vs_block_share_strict']:.3f}；"
          f"Spearman(M-frac, 同) = {mobility['spearman_Mfrac_vs_block_share_strict']:.3f}")
    print(f"  pivotal（strict）共 {tot_piv} 筆；M-count 前 25 %（{int(top.sum())} 個 UE-run）佔 "
          f"{mobility['pivotal_strict_share_from_top_quartile_Mcount']:.1%}；edge 佔 {mobility['pivotal_strict_share_from_edge']:.1%}")
    for b in mobility["Mcount_bins"]:
        print(f"    M-count [{b['lo']},{b['hi']}) n={b['n']:>3}  擋下佔比 {b['block_share_strict_mean']:.3f}  pivotal {b['pivotal_share_strict_mean']:.3f}")

    # =====================================================================
    # B. 注入：MF-1（第四章管線）、MF-2 之 r_S、§3.3 偏差
    # =====================================================================
    print("── B. 注入（3 種腳本攻擊 × 8 seed × 每個 mmWave cell）──")
    acc = {a: collections.Counter() for a, *_ in ATTACKS}
    bias = {a: {p: [] for p in POLICIES} for a, *_ in ATTACKS}
    for f in files:
        anchor = X.TrustAnchor([g for g in files if g != f])
        base = load_windows(f)
        t0 = len(base) // 2
        cells_all = sorted({c for d in true_delays(base) for c in d})
        for name, kind, param in ATTACKS:
            s = acc[name]
            for cell in cells_all:
                mod = apply_attack(base, cell, kind, param, t0)
                ann, _ = run_annotate(mod, anchor)
                s["episodes"] += 1
                for a in ann:
                    k, j = a["window"], a["node"]
                    tam = (j == cell and k >= t0 and cell in mod[k][1]
                           and any(mod[k][1][cell][i] != base[k][1][cell][i] for i in mod[k][1][cell]))
                    if not tam:
                        s["clean_n"] += 1; s["clean_rej"] += a["decision"] == "rejected"
                        s["clean_nontrust"] += a["decision"] != "trusted"
                        continue
                    s["tam_n"] += 1
                    s["tam_rej"] += a["decision"] == "rejected"
                    s["tam_nontrust"] += a["decision"] != "trusted"
                    s["tam_abstain"] += a["decision"] == "abstain"
                    s["tam_si_viol"] += a["si_raw"] == "violated"
                    s["tam_d1_any"] += a["H_i_D1"] in ("weak", "strong")
                    s["tam_d1_strong"] += a["H_i_D1"] == "strong"
                    rep = float(np.mean(list(mod[k][1][cell].values())))
                    tru = float(np.mean(list(base[k][1][cell].values())))
                    for p in POLICIES:
                        if admitted(a["decision"], p):
                            s[f"tam_adm_{p}"] += 1
                            bias[name][p].append(abs(rep / tru - 1) if tru > 0 else float("nan"))
        print(f"  seed {DS.seed_of(f)} 完成")

    # E20-1：與 eval_final.json（E19 game_core 之實作）比對
    ef = json.load(open(EVAL_FINAL, encoding="utf-8"))
    d0 = ef["baselines"]["D0"]["per_attacker_script"]
    e1 = {}
    bad = []
    for name, *_ in ATTACKS:
        s = acc[name]
        mine = {"TPR_rejected": s["tam_rej"] / s["tam_n"], "TPR_nontrusted": s["tam_nontrust"] / s["tam_n"],
                "clean_false_reject": s["clean_rej"] / s["clean_n"], "clean_nontrusted": s["clean_nontrust"] / s["clean_n"]}
        e1[name] = {"chapter4_pipeline": mine, "eval_final": {k: d0[name][k] for k in mine}, "episodes": s["episodes"]}
        for k in mine:
            if mine[k] != d0[name][k]:
                bad.append((name, k, mine[k], d0[name][k]))
    if bad:
        stop(f"E20-1 兩份實作不一致：{bad}")
    print("  E20-1 ✓ 第四章管線與 eval_final.json 之 TPR_rej、TPR_nt、乾淨誤拒、乾淨非 trusted 逐位相同（3 攻擊）")

    mf = {}
    for name, *_ in ATTACKS:
        s = acc[name]
        r_S = s["tam_si_viol"] / s["tam_n"]
        mf[name] = {
            "tampered": s["tam_n"], "episodes": s["episodes"],
            "MF1": {p: s[f"tam_adm_{p}"] / s["tam_n"] for p in POLICIES},
            "abstain_share": s["tam_abstain"] / s["tam_n"],
            "r_S": r_S,
            "q_on_tampered": {"any": s["tam_d1_any"] / s["tam_n"], "strong": s["tam_d1_strong"] / s["tam_n"]},
            "MF2": {"restrict_annotated": 1 - r_S * q_s, "strict": (1 - r_S) * (1 - q_any)},
            "bias_admitted": {p: ({"n": len(v), "ge_1pct": float(np.mean([x >= 0.01 for x in v])),
                                   "ge_5pct": float(np.mean([x >= 0.05 for x in v])),
                                   "ge_10pct": float(np.mean([x >= 0.10 for x in v])),
                                   "median": float(np.median(v))} if v else {"n": 0}) for p, v in bias[name].items()},
        }
        print(f"  {name:<14} 竄改 {s['tam_n']:>6}  MF-1 strict {mf[name]['MF1']['strict']:.4f}  restrict {mf[name]['MF1']['restrict_annotated']:.4f}  "
              f"｜ r_S {r_S:.4f} → MF-2 strict {mf[name]['MF2']['strict']:.4f}  restrict {mf[name]['MF2']['restrict_annotated']:.4f}")

    # DRL（方法一，既有數字；不重跑）與學習型攻擊者
    drl = {}
    for rid, run in ef["runs"].items():
        drl[rid] = {"FB1": {"strict": run["clean"]["clean_nontrusted"], "restrict_annotated": run["clean"]["clean_false_reject"]},
                    "A-script_worst_by_TPR": {"attacker": run["A-script"]["by_TPR"]["attacker"],
                                              "MF1_strict": 1 - run["A-script"]["by_TPR"]["TPR_nontrusted"],
                                              "MF1_restrict_annotated": 1 - run["A-script"]["by_TPR"]["TPR_rejected"]},
                    "A-pool_worst_by_TPR": {"attacker": run["A-pool"]["by_TPR"]["attacker"],
                                            "MF1_strict": 1 - run["A-pool"]["by_TPR"]["TPR_nontrusted"],
                                            "MF1_restrict_annotated": 1 - run["A-pool"]["by_TPR"]["TPR_rejected"]},
                    "A-BR": {"MF1_strict": 1 - run["A-BR"]["TPR_nontrusted"], "MF1_restrict_annotated": 1 - run["A-BR"]["TPR_rejected"]}}
    d0_learned = {"A-pool_worst_by_TPR": {"attacker": ef["baselines"]["D0"]["A-pool"]["by_TPR"]["attacker"],
                                          "MF1_strict": 1 - ef["baselines"]["D0"]["A-pool"]["by_TPR"]["TPR_nontrusted"],
                                          "MF1_restrict_annotated": 1 - ef["baselines"]["D0"]["A-pool"]["by_TPR"]["TPR_rejected"]},
                  "A-BR": {k: {"MF1_strict": 1 - v["TPR_nontrusted"], "MF1_restrict_annotated": 1 - v["TPR_rejected"]}
                           for k, v in ef["baselines"]["D0"].items() if k.startswith("A-BR@")}}
    rq3 = json.load(open(RQ3_JSON, encoding="utf-8"))
    lure = {k: rq3[f"uebound|{k}|C_strict"]["lured_rate"] for k in ("step_x0.6", "step_x0.8", "drift_1pct")}

    # =====================================================================
    # C. E20-5：PHY 交叉驗證（一個 seed，只報告）
    # =====================================================================
    phy_seeds = ([DS.seed_of(f) for f in files] if args.phy_seeds == "all"
                 else [int(x) for x in args.phy_seeds.split(",")])
    phy = {"per_seed": {str(sd): phy_check(sd, files, mob) for sd in phy_seeds}}
    ok = [v for v in phy["per_seed"].values() if v.get("status") == "ok"]
    for st in ("mmw", "lte"):
        phy[f"range_{st}"] = {k: [min(v["per_rlc_state_phy"][st][k] for v in ok), max(v["per_rlc_state_phy"][st][k] for v in ok)]
                              for k in ("bytes_per_s_median", "corrupt_share_mean", "sinr_db_mean_of_window_means_median")}
    phy["rlc_lte_but_phy_mmw_share"] = [v["rlc_lte_but_phy_mmw"] / v["per_rlc_state_phy"]["lte"]["ue_windows"] for v in ok]
    print(f"── E20-5 PHY（{len(ok)} seed）── LTE-only 窗：SINR {phy['range_lte']['sinr_db_mean_of_window_means_median']} dB、"
          f"損壞 {phy['range_lte']['corrupt_share_mean']}；mmWave 窗：SINR {phy['range_mmw']['sinr_db_mean_of_window_means_median']} dB、"
          f"損壞 {phy['range_mmw']['corrupt_share_mean']}")

    out = {
        "spec": "docs/thesis/E20_error_rate_spec.md v1",
        "checks": {"E20-0": "ok", "E20-1": "ok", "E20-2": "ok", "E20-3": "ok", "E20-4": "ok"},
        "units": {"FB": "clean (node, window) not admitted / all clean (node, window)",
                  "MF": "tampered (node, window) admitted / all tampered (node, window); tampered = attacked cell, k >= t0, any UE value changed",
                  "admission": {p: sorted(X.ADMISSION[p]) for p in POLICIES}},
        "FB1": fb1,
        "FB2": {"inputs": {"S_i_violated": si_v, "D1_any": d1_any, "D1_strong": d1_s, "N": N,
                           "p_S": p_S, "q_any": q_any, "q_strong": q_s, "paper_indep_expectation": indep},
                "2a_marginal": fb2a,
                "2b_per_UE": {**fb2b, "q_any_pred": float(np.mean(qa_pred)), "q_strong_pred": float(np.mean(qs_pred)),
                              "note": "per-UE window-level D1 rates (in-sample, same seed), UEs bound by last serving cell, independence across UEs and between S_i and D1"}},
        "MF": mf, "E20-1": e1,
        "DRL_method1": drl, "D0_learned_attackers_method1": d0_learned,
        "lure_rate_C_strict_RQ3": lure,
        "mobility": mobility, "per_ue_run": rows,
        "phy_check": phy,
        "elapsed_s": round(time.time() - t_start, 1),
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    p = os.path.join(OUT_DIR, "E20_error_rates.json")
    json.dump(out, open(p, "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=lambda o: o.item() if hasattr(o, "item") else str(o))
    print(f"\n寫入 {p}（{out['elapsed_s']} s）")
    if not args.no_fig:
        import make_fig_E20
        make_fig_E20.draw_all(out, OUT_DIR)


def phy_check(seed, files, mob):
    """以 PHY 層 RxPacketTrace（DL，mmWave）之 (cellId, rnti) 反查 IMSI（MmWaveSwitchStats 開機 attach；
    D-30 無合法 mmWave 換手），逐秒判定 UE 是否有 mmWave 下行傳輸，與 RLC 之 mmw 狀態比較。"""
    aux = os.path.dirname(DS.aux_path(seed, "x"))
    m = {}
    for line in open(os.path.join(aux, "MmWaveSwitchStats.txt")):
        p = line.split()
        if len(p) >= 5:
            m[(int(p[3]), int(p[4]))] = int(p[2])     # (cell, rnti) → imsi
    if len(m) != X.N_KNOWN:
        return {"status": "skipped", "reason": f"attach map {len(m)} != {X.N_KNOWN}"}
    pres = collections.defaultdict(set)
    tb, byt, cor, snr = collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter()
    unk = 0
    with gzip.open(os.path.join(aux, "RxPacketTrace.txt.gz"), "rt") as fh:
        fh.readline()
        for line in fh:
            if not line.startswith("DL"):
                continue
            p = line.split("\t")
            sec = int(float(p[1]))
            if sec >= 300:
                continue
            key = (int(p[7]), int(p[8]))
            if key not in m:
                unk += 1; continue
            i_ = m[key]
            pres[i_].add(sec)
            tb[(i_, sec)] += 1; byt[(i_, sec)] += int(p[10]); cor[(i_, sec)] += int(p[14]); snr[(i_, sec)] += float(p[13])
    f = [g for g in files if str(DS.seed_of(g)) == str(seed)][0]
    rec = load_membership(f)
    all_w = sorted(set(w for im, wm in rec.items() for w in wm))
    agree = n = rlc_mmw_phy_no = rlc_lte_phy_yes = 0
    mc_rlc, mc_phy = [], []
    per_state = collections.defaultdict(lambda: collections.defaultdict(list))
    for i in range(1, X.N_KNOWN + 1):
        seq = state_seq(rec.get(i, {}), all_w)
        phy_seq = [("mmw" if w in pres[i] else ("lte" if s != "absent" else "absent")) for w, s in zip(all_w, seq)]
        for s, q in zip(seq, phy_seq):
            if s == "absent":
                continue
            n += 1; agree += (s == "mmw") == (q == "mmw")
            rlc_mmw_phy_no += s == "mmw" and q != "mmw"; rlc_lte_phy_yes += s == "lte" and q == "mmw"
        mc_rlc.append(len(dwell_events(seq))); mc_phy.append(len(dwell_events(phy_seq)))
        for w, s in zip(all_w, seq):
            if s != "absent":
                n_ = tb[(i, w)]
                per_state[s]["tb"].append(n_); per_state[s]["bytes"].append(byt[(i, w)])
                per_state[s]["corrupt"].append(cor[(i, w)] / n_ if n_ else np.nan)
                per_state[s]["sinr_mean"].append(snr[(i, w)] / n_ if n_ else np.nan)
    return {"status": "ok", "seed": seed, "unmapped_phy_rows": unk, "ue_windows": n,
            "agreement_mmw_state": agree / n, "rlc_mmw_but_no_phy": rlc_mmw_phy_no, "rlc_lte_but_phy_mmw": rlc_lte_phy_yes,
            "Mcount_rlc": mc_rlc, "Mcount_phy": mc_phy,
            "spearman_Mcount_rlc_phy": (spearman(mc_rlc, mc_phy) if len(set(mc_phy)) > 1 else None),
            "phy_any_tb_is_valid_state_indicator": len(set(mc_phy)) > 1,
            "per_rlc_state_phy": {st: {"ue_windows": len(v["tb"]),
                                       "tb_per_s_median": float(np.median(v["tb"])),
                                       "bytes_per_s_median": float(np.median(v["bytes"])),
                                       "corrupt_share_mean": float(np.nanmean(v["corrupt"])),
                                       "sinr_db_mean_of_window_means_median": float(np.nanmedian(v["sinr_mean"]))}
                                  for st, v in per_state.items()},
            "note": "check only; not a primary metric (spec Q6)"}


if __name__ == "__main__":
    main()
