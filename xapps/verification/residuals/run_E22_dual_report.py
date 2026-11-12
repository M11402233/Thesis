#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_E22_dual_report.py — 規格 E22 v1（docs/thesis/E22_dual_report_rule_spec.md）：同窗雙掛規則 H_i-D3。

同一行程內切換 zt_kpm_xapp.D3_ENABLED（off／on）重放，比較：
  4.1 乾淨誤拒（D-30 完整管線；另報 Stage 3 TM3、D-SH、D-C 之觸發次數）
  4.2 對 A3（E21-S0 之注入）之偵測率、MF_strict／MF_restrict_annotated、偵測延遲；B-off 變體
  副作用：A1、A2、A4、三種延遲攻擊下規則不觸發、註記逐筆相同
內建檢查 E22-0～E22-3（任一失敗即停，不寫輸出）。

跑法（舊機器）：
  ZT_DATASET=d30 ZT_FUSION_ORDER=severity python3 xapps/verification/residuals/run_E22_dual_report.py
"""
import os
import sys
import glob
import json
import time
import collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run_E21_S0_membership as S0                                # noqa: E402  (含環境檢查)
from run_E21_S0_membership import X, DS, load_windows, inject, stop, T0S, L, KS, LTE  # noqa: E402
from run_E21_S1_boff import relaxed                               # noqa: E402
from run_RQ3_decision_replay import ListSource, apply_attack, true_delays  # noqa: E402

SEV_DIR = S0.SEV_DIR
OUT_DIR = os.path.join(SEV_DIR, "E22")
REF_ANN = S0.REF_ANN
S1_JSON = os.path.join(SEV_DIR, "E21_S1", "E21_S1_boff.json")
REPO = S0.REPO
DELAY = [("A0_step_0.6", "step", 0.60), ("A0_step_0.8", "step", 0.80), ("A0_drift_0.01", "drift", 0.01)]
MEMB_ALL = ["A1_delete", "A2_swap", "A3_claim_anchor", "A4_claim_peer"]
EXTRA = {"S3-TM3": "data/game_stage3/S3-TM3/S3-TM3_ues30_t300_seed42*.txt",
         "D-SH": "data/si_lstm_seeds/ues1_t300_seed42*.txt",
         "D-C": "data/batchFinal_seeds/seed42*.txt"}


def run(wins, anchor, d3):
    X.D3_ENABLED = d3
    return X.run_xapp(ListSource(wins), anchor, "all", binding="uebound", admission="strict")[0]


def strip(a):
    """移除 D3 新增之欄位（E22-3 比較用）"""
    b = {k: v for k, v in a.items() if k != "H_i_D3"}
    b["evidence"] = {k: v for k, v in a["evidence"].items() if k != "D3"}
    return b


def adm(dec, policy):
    return X.ACTION[dec] in X.ADMISSION[policy]


def main():
    t_start = time.time()
    files = DS.files()
    ref = [json.loads(l) for l in open(REF_ANN, encoding="utf-8")]
    s1 = json.load(open(S1_JSON, encoding="utf-8"))["results"]

    # ---- 4.1 乾淨 ----
    print("── 4.1 乾淨（D-30）──")
    seeds, pos, n_trig, clean_on = [], 0, 0, collections.Counter()
    for f in files:
        anchor = X.TrustAnchor([g for g in files if g != f])
        wins = load_windows(f)
        off = run(wins, anchor, False)
        seg = ref[pos:pos + len(off)]
        pos += len(off)
        if len(seg) != len(off) or any(json.loads(json.dumps(a, ensure_ascii=False)) != r for a, r in zip(off, seg)):
            stop(f"E22-0 seed {DS.seed_of(f)}：ZT_D3 關閉時與註記檔不同")
        on = run(wins, anchor, True)
        n_trig += sum(a["H_i_D3"] == "violated" for a in on)
        if [strip(a) for a in on] != off and n_trig == 0:
            stop(f"E22-3 seed {DS.seed_of(f)}：乾淨資料規則未觸發但註記不同")
        clean_on.update(a["decision"] for a in on)
        seeds.append((DS.seed_of(f), anchor, wins, off))
    if pos != len(ref):
        stop(f"E22-0 總筆數 {pos} ≠ {len(ref)}")
    print(f"  E22-0 ✓ 關閉時 15,534 筆逐筆重現註記檔")
    if n_trig:
        stop(f"4.1 乾淨 D-30 之 R1_D3_VETO 觸發 {n_trig} 次（預期 0）——依規格停止回報，不調整規則")
    print(f"  乾淨 D-30：R1_D3_VETO 觸發 0 次；E22-3 ✓ 判定與關閉時逐筆相同 {dict(clean_on)}")
    extra = {}
    for name, pat in EXTRA.items():
        fs = sorted(glob.glob(os.path.join(REPO, pat)))
        n_nodewin = trig = 0
        for f in fs:
            for w, cells in X.TraceReplaySource(f).windows():
                for c in cells:
                    if c == LTE:
                        continue
                    n_nodewin += 1
                    trig += X.verify_hi_d3(cells, c)[0] == "violated"
        extra[name] = {"files": len(fs), "node_windows": n_nodewin, "d3_violated": trig}
        print(f"  {name}：{len(fs)} 檔、(節點, 窗) {n_nodewin}、D3 觸發 {trig}")

    # ---- 4.2 成員關係攻擊 ----
    print("── 4.2 成員關係攻擊（E21-S0 之注入）──")
    res = {}
    for atk in MEMB_ALL:
        for k in KS:
            c = collections.Counter()
            delays = []
            for sd, anchor, wins, _ in seeds:
                widx = {w: t for t, (w, _) in enumerate(wins)}
                for j in sorted({cc for _, cl in wins for cc in cl if cc != LTE}):
                    for t0 in T0S:
                        hi = min(t0 + L + S0.POST, len(wins))
                        iw, nmod = inject(wins, j, t0, k, atk)
                        if sum(nmod) == 0:
                            continue
                        off = run(iw[:hi], anchor, False)
                        on = run(iw[:hi], anchor, True)
                        c["episodes"] += 1
                        first_tam, first_rej = None, None
                        for a_off, a_on in zip(off, on):
                            t = widx[a_on["window"]]
                            is_tam = a_on["node"] == j and t0 <= t < t0 + L and nmod[t - t0] > 0
                            if a_on.get("H_i_D3") == "violated":
                                c["d3_trig"] += 1
                                if not is_tam:
                                    stop(f"E22-2 {atk} k={k} seed {sd} j={j} t0={t0}：D3 觸發於非竄改之 (節點 {a_on['node']}, 窗 {t})")
                            elif strip(a_on) != a_off:
                                stop(f"E22-3 {atk} k={k}：D3 未觸發之 (節點, 窗) 判定改變")
                            if a_on["node"] != j and a_on["decision"] != a_off["decision"]:
                                stop(f"E22-3 {atk} k={k}：非 j 節點之判定改變")
                            if not is_tam:
                                continue
                            c["tam"] += 1
                            c["det"] += a_on.get("H_i_D3") == "violated"
                            c["off_strict"] += adm(a_off["decision"], "strict")
                            c["on_strict"] += adm(a_on["decision"], "strict")
                            c["off_restrict"] += adm(a_off["decision"], "restrict_annotated")
                            c["on_restrict"] += adm(a_on["decision"], "restrict_annotated")
                            c["off_boff_strict"] += adm("trusted" if relaxed(a_off) else a_off["decision"], "strict")
                            c["on_boff_strict"] += adm("trusted" if relaxed(a_on) else a_on["decision"], "strict")
                            if first_tam is None:
                                first_tam = t
                            if first_rej is None and a_on["decision"] == "rejected":
                                first_rej = t
                        if first_tam is not None:
                            delays.append(None if first_rej is None else first_rej - first_tam)
            key = f"{atk}|k={k}"
            n = c["tam"]
            r = {"episodes": c["episodes"], "tampered": n, "d3_triggered": c["d3_trig"],
                 "detection_rate": c["det"] / n,
                 "MF_strict_off": c["off_strict"] / n, "MF_strict_on": c["on_strict"] / n,
                 "MF_restrict_off": c["off_restrict"] / n, "MF_restrict_on": c["on_restrict"] / n,
                 "MF_strict_boff_off": c["off_boff_strict"] / n, "MF_strict_boff_on": c["on_boff_strict"] / n,
                 "delay_windows": {"n": len(delays), "n_never": sum(d is None for d in delays),
                                   "max": max((d for d in delays if d is not None), default=None),
                                   "mean": (sum(d for d in delays if d is not None) / max(1, sum(d is not None for d in delays)))}}
            if r["MF_strict_off"] != s1["membership"][key]["MF_strict_rule"] or n != s1["membership"][key]["tampered"]:
                stop(f"E22-1 {key}：關閉時 MF {r['MF_strict_off']}／竄改 {n} ≠ E21-S1 {s1['membership'][key]['MF_strict_rule']}／{s1['membership'][key]['tampered']}")
            res[key] = r
            print(f"  {key:22s} 竄改 {n:5d}  D3 偵測 {r['detection_rate']:.3f}  MF_strict {r['MF_strict_off']:.3f}→{r['MF_strict_on']:.3f}  "
                  f"MF_restrict {r['MF_restrict_off']:.3f}→{r['MF_restrict_on']:.3f}  B-off strict {r['MF_strict_boff_off']:.3f}→{r['MF_strict_boff_on']:.3f}  "
                  f"延遲 max {r['delay_windows']['max']}  未拒 {r['delay_windows']['n_never']}", flush=True)
    print("  E22-1 ✓ 關閉時 MF_strict 重現 E21-S1；E22-2 ✓ D3 只出現在竄改之 (j, 窗)")

    # ---- 延遲攻擊（副作用）----
    print("── 延遲攻擊（副作用檢查）──")
    for name, kind, param in DELAY:
        trig = 0
        for sd, anchor, base, _ in seeds:
            t0 = len(base) // 2
            for cell in sorted({cc for d in true_delays(base) for cc in d}):
                mod = apply_attack(base, cell, kind, param, t0)
                off, on = run(mod, anchor, False), run(mod, anchor, True)
                trig += sum(a.get("H_i_D3") == "violated" for a in on)
                if [strip(a) for a in on] != off:
                    stop(f"E22-3 {name}：註記改變")
        if trig:
            stop(f"E22-3 {name}：D3 觸發 {trig} 次（預期 0）")
        res[name] = {"d3_triggered": 0, "annotations_identical": True}
        print(f"  {name}：D3 觸發 0；註記逐筆相同")
    print("  E22-3 ✓")
    X.D3_ENABLED = False
    os.makedirs(OUT_DIR, exist_ok=True)
    out = {"spec": "docs/thesis/E22_dual_report_rule_spec.md v1",
           "checks": {"E22-0": "pass", "E22-1": "pass", "E22-2": "pass", "E22-3": "pass"},
           "clean_D30": {"node_windows": len(ref), "d3_triggered": 0, "decisions_on": dict(clean_on)},
           "clean_other": extra, "attacks": res, "elapsed_s": round(time.time() - t_start, 1)}
    p = os.path.join(OUT_DIR, "E22_dual_report.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"寫入 {p}（{time.time() - t_start:.0f} s）")


if __name__ == "__main__":
    main()
