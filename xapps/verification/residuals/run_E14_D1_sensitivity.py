#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_E14_D1_sensitivity.py — E14：H_i-D1 門檻與持續性之敏感度（規格 docs/thesis/E14_D1_sensitivity_spec.md v1）

【性質】事後新增之敏感度分析：主結果維持凍結值（τ_H = 2／3、L_H = 1），本實驗不用於選擇操作點。
【實作】判定一律經 run_E10_D1_policy_ablation.run_policy（→ zt_kpm_xapp.fuse），僅於呼叫期間覆寫
        X.TAU_H_WARN／X.TAU_H_REJECT；不複製判定邏輯。綁定固定為 uebound。
【內建檢查】見規格第六節；任一失敗即停止、不寫檔。

跑法：ZT_DATASET=d30 python3 run_E14_D1_sensitivity.py [--workers 3]
"""
import os
import sys
import json
import math
import argparse
import collections
import multiprocessing as mp
import numpy as np
import datasets as DS
import zt_kpm_xapp as X
import run_E10_D1_policy_ablation as E

FROZEN = (2.0, 3.0)
THRESHOLDS = [(2.0, 3.0), (3.0, 4.0), (4.0, 5.0), (6.0, 7.0)]
L_HS = [1, 2, 3]
TARGET_Z = [3.0, 4.0, 6.0, 8.0]
BINDING = "uebound"


def key(tw, tr, L_H):
    return f"tau{tw:g}_{tr:g}|L{L_H}"


def eval_config(job):
    files, tw, tr, L_H = job
    if (X.TAU_H_WARN, X.TAU_H_REJECT) != FROZEN:
        raise SystemExit("✗ 檢查 1：模組門檻非凍結值")
    X.TAU_H_WARN, X.TAU_H_REJECT = tw, tr
    try:
        dec, rule = collections.Counter(), collections.Counter()
        per_seed = {}
        n_ann = ue_windows = ue_alert_windows = 0
        inj = {tz: {"n": 0, "det": 0, "delay": [], "delay_strong": []} for tz in TARGET_Z}
        for test in files:
            anchor = X.TrustAnchor([f for f in files if f != test])
            wins = E.load_windows(test)
            ann, alerts = E.run_policy(wins, anchor, BINDING, L_H)
            c = collections.Counter(a["decision"] for a in ann)
            dec.update(c); rule.update(a["rule_id"] for a in ann); n_ann += len(ann)
            per_seed[DS.seed_of(test)] = {"n": len(ann), "trusted": c.get("trusted", 0), "rejected": c.get("rejected", 0)}
            for k, (w, cells) in enumerate(wins):
                ue_windows += sum(len(u) for u in cells.values())
                ue_alert_windows += len(alerts[k])
            # 注入超時消失：與 E10 相同之注入點規則與停留長度
            for imsi in anchor.dwell:
                med, sig = anchor.dwell[imsi]
                for tz in TARGET_Z:
                    L = max(2, int(math.ceil(med + tz * sig)))

                    def on_mmw(kk):
                        cc = wins[kk][1]
                        return [c_ for c_ in cc if c_ != X.LTE_CELL and imsi in cc[c_]]
                    t_idx = None
                    for k in range(max(1, len(wins) // 2), len(wins) - L):
                        if on_mmw(k) and on_mmw(k - 1):
                            t_idx = k; break
                    if t_idx is None:
                        continue
                    iw = E.inject_overtime(wins, imsi, t_idx, L)
                    _, alerts_i = E.run_policy(iw, anchor, BINDING, L_H)
                    inj[tz]["n"] += 1
                    hit = next((k for k in range(t_idx, t_idx + L) if imsi in alerts_i.get(k, {})), None)
                    if hit is None:
                        continue
                    inj[tz]["det"] += 1
                    inj[tz]["delay"].append(hit - t_idx)
                    for k in range(hit, t_idx + L):
                        if alerts_i.get(k, {}).get(imsi, (0,))[0] == 2:
                            inj[tz]["delay_strong"].append(k - t_idx); break
    finally:
        X.TAU_H_WARN, X.TAU_H_REJECT = FROZEN
    return key(tw, tr, L_H), {
        "tau_H_warn": tw, "tau_H_reject": tr, "L_H": L_H, "n_annotations": n_ann,
        "clean_decisions": dict(dec), "clean_share": {k: v / n_ann for k, v in dec.items()},
        "clean_rules": dict(rule), "clean_ue_alert_rate": ue_alert_windows / max(ue_windows, 1),
        "per_seed": per_seed,
        "injection": {str(tz): {"n": v["n"], "tpr": v["det"] / v["n"] if v["n"] else None,
                                "mean_delay": float(np.mean(v["delay"])) if v["delay"] else None,
                                "mean_delay_to_strong": float(np.mean(v["delay_strong"])) if v["delay_strong"] else None}
                      for tz, v in inj.items()}}


def checks(res, out_dir):
    ok = True
    e10 = json.load(open(os.path.join(out_dir, "E10_D1_policy_ablation.json"), encoding="utf-8"))
    print("── 檢查 2／3：凍結門檻兩組須重現同資料集 E10（乾淨計數；z ∈ {3,4,6} 之注入）──")
    for L_H, pname in ((1, "P3_uebound_L1"), (2, "P4_uebound_L2")):
        r, p = res[key(*FROZEN, L_H)], e10[pname]
        c_ok = r["clean_decisions"] == p["clean_decisions"] and r["n_annotations"] == p["n_annotations"]
        i_ok = all(r["injection"][z][f] == p["injection"][z][f]
                   for z in ("3.0", "4.0", "6.0") for f in ("n", "tpr", "mean_delay", "mean_delay_to_strong"))
        print(f"  L_H={L_H} vs {pname}：乾淨 {'✓' if c_ok else '✗'}　注入 {'✓' if i_ok else '✗'}")
        ok = ok and c_ok and i_ok
    tr = lambda tw, t, L: res[key(tw, t, L)]["clean_decisions"].get("trusted", 0)
    mono = all(tr(*THRESHOLDS[i], L) <= tr(*THRESHOLDS[i + 1], L) for L in L_HS for i in range(len(THRESHOLDS) - 1)) and \
        all(tr(*t, L_HS[i]) <= tr(*t, L_HS[i + 1]) for t in THRESHOLDS for i in range(len(L_HS) - 1))
    same_n = len({r["n_annotations"] for r in res.values()}) == 1
    print(f"── 檢查 4：trusted 單調性 {'✓' if mono else '✗'}；檢查 5：註記總數一致 {'✓' if same_n else '✗'}")
    restored = (X.TAU_H_WARN, X.TAU_H_REJECT) == FROZEN
    print(f"── 檢查 1：模組門檻已還原 {'✓' if restored else '✗'}")
    return ok and mono and same_n and restored


def draw(res, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(15, 4.4))
    xs = np.arange(len(THRESHOLDS)); cols = {1: "#1971c2", 2: "#e8590c", 3: "#c92a2a"}
    for L in L_HS:
        rs = [res[key(*t, L)] for t in THRESHOLDS]
        a1.plot(xs, [100 * r["clean_share"].get("trusted", 0) for r in rs], "o-", color=cols[L], label=f"L_H = {L}")
        a2.plot(xs, [100 * r["clean_share"].get("rejected", 0) for r in rs], "s-", color=cols[L], label=f"L_H = {L}")
        for z, ls in (("6.0", "-"), ("8.0", "--")):
            a3.plot(xs, [r["injection"][z]["mean_delay"] if r["injection"][z]["mean_delay"] is not None else np.nan
                         for r in rs], ls, marker="^", color=cols[L], label=f"L_H = {L}, z = {float(z):g}")
    for ax, yl, tt in ((a1, "trusted (%)", "Clean data: usable share"), (a2, "rejected (%)", "Clean data: false rejects"),
                       (a3, "mean detection delay (windows)", "Injected overtime: delay (detected cases)")):
        ax.set_xticks(xs); ax.set_xticklabels([f"{a:g}/{b:g}" for a, b in THRESHOLDS])
        ax.set_xlabel("τ_H warn / reject"); ax.set_ylabel(yl); ax.set_title(tt, fontsize=10)
        ax.axvline(0, color="k", lw=0.6, ls=":"); ax.grid(alpha=0.3); ax.legend(fontsize=7)
    n = next(iter(res.values()))["n_annotations"]
    fig.suptitle(f"E14 (post-hoc sensitivity, {DS.NAME}, uebound, n = {n:,} node annotations); "
                 "dotted line = frozen thresholds 2/3", fontsize=10)
    fig.tight_layout(); fig.savefig(path, dpi=180); plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()
    out_dir = args.out_dir or DS.results_dir()
    files = DS.files()
    if len(files) < 2:
        raise SystemExit("資料不足")
    print(f"載入 {len(files)} seed；資料集 {DS.NAME}；綁定 {BINDING}；格點 {len(THRESHOLDS)}×{len(L_HS)}；z = {TARGET_Z}\n")
    jobs = [(files, tw, tr, L) for tw, tr in THRESHOLDS for L in L_HS]
    with mp.Pool(args.workers) as pool:
        res = dict(pool.imap_unordered(eval_config, jobs))
    res = {key(tw, tr, L): res[key(tw, tr, L)] for tw, tr in THRESHOLDS for L in L_HS}
    if not checks(res, out_dir):
        print("  ✗ 檢查未通過。停止：不寫入任何輸出。請回報，勿調參數。")
        sys.exit(2)

    n = res[key(*FROZEN, 1)]["n_annotations"]
    print(f"\n── 表一：乾淨資料（分母 = 有效節點註記 {n}）；★ = 凍結值 ──")
    print(f"{'τ_H':<8}{'L_H':>4}{'trusted':>10}{'low-trust':>11}{'rejected':>10}{'(筆)':>7}{'UE告警率':>9}  各 seed trusted 範圍")
    for tw, tr in THRESHOLDS:
        for L in L_HS:
            r = res[key(tw, tr, L)]; s = r["clean_share"]
            ps = [v["trusted"] / v["n"] for v in r["per_seed"].values()]
            star = "★" if (tw, tr) == FROZEN and L == 1 else " "
            print(f"{tw:g}/{tr:g}{star:<5}{L:>4}{s.get('trusted', 0):>10.1%}{s.get('low-trust', 0):>11.1%}"
                  f"{s.get('rejected', 0):>10.2%}{r['clean_decisions'].get('rejected', 0):>7}"
                  f"{r['clean_ue_alert_rate']:>9.1%}  {min(ps):.1%}–{max(ps):.1%}")
    print("\n── 表二：注入超時消失 TPR／平均延遲（窗）／達 strong 之平均延遲 ──")
    print(f"{'τ_H':<8}{'L_H':>4}" + "".join(f"{'z=' + format(z, 'g'):>18}" for z in TARGET_Z))
    for tw, tr in THRESHOLDS:
        for L in L_HS:
            row = f"{tw:g}/{tr:g}{'':<5}{L:>4}"
            for z in TARGET_Z:
                v = res[key(tw, tr, L)]["injection"][str(z)]
                f = lambda x: "-" if x is None else f"{x:.1f}"
                row += f"{(v['tpr'] or 0):>8.2f}/{f(v['mean_delay'])}/{f(v['mean_delay_to_strong'])}".rjust(18)
            print(row)
    out = {"spec": "docs/thesis/E14_D1_sensitivity_spec.md v1", "post_hoc": True, "dataset": DS.NAME,
           "binding": BINDING, "frozen": {"tau_H_warn": FROZEN[0], "tau_H_reject": FROZEN[1], "L_H": 1},
           "target_z": TARGET_Z, "checks": "ok", "results": res}
    p = os.path.join(out_dir, "E14_D1_sensitivity.json")
    json.dump(out, open(p, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"\n寫入 {p}")
    draw(res, os.path.join(out_dir, "fig_E14_D1_sensitivity.png"))
    print("圖已存:", os.path.join(out_dir, "fig_E14_D1_sensitivity.png"))


if __name__ == "__main__":
    main()
