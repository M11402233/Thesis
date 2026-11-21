#!/usr/bin/env python3
"""延遲修正之分解（2026-11-22；D30P1_r10_recollection_spec.md 之後續）。
三個設定只差延遲之定義，其餘（模擬、舊輸出、門檻、尺度公式）相同（Q-2：D-30P1 之舊輸出與 D-30P 逐位相同）：
  A  D-30P  percell_zero ：舊式 Δdelay 總和 ÷ ΔnRx（含零延遲〔無時間戳〕與重複接收）
  B  D-30P  percell      ：排除零延遲，仍含重複／未被接收端接受之接收
  C  D-30P1 percell（eff）：有效延遲樣本（帶新位元組 ∩ 接收端接受 AN/AS ∩ 有時間戳）
A→B = 排除零值之效果；B→C = 去重（及排除未被接受之接收）之效果。
一致性檢查 K-A：D-30P1 percell_zero（舊式）須與 A 逐位相同（同一份舊輸出、同一公式）。不符即停（exit 1）。
指標皆取自各設定既有之腳本輸出（不另算）：E9_rt 共同集合之乾淨誤報／漂移／階躍偵測率、cv_interval、E9b 校準。
用法：delay_decomposition.py <results_root> <out_dir>
"""
import json, os, sys
R, OUT = sys.argv[1], sys.argv[2]
CFG = {"A": "d30p_delay_percell_zero", "B": "d30p_delay_percell", "C": "d30p1_delay_percell", "A'": "d30p1_delay_percell_zero"}
def load(d, f): return json.load(open(os.path.join(R, d, f), encoding="utf-8"))
def metrics(d):
    m = {}
    e = load(d, "E9_operating_regime_rt.json")["common"]
    for ref in ("spatial", "temporal"):
        m[f"{ref} 乾淨誤報"] = e[ref]["clean_fpr"]["mean"]
        for r in ("0.005", "0.01", "0.02"): m[f"{ref} 漂移 {float(r)*100:g} %/秒"] = e[ref]["drift"][r]["mean"]
        for a in ("1.2", "1.3", "1.5"): m[f"{ref} 階躍 ×{a}"] = e[ref]["step"][a]["mean"]
    cv = load(d, "cv_interval.json")["delay_cv"]
    m["延遲 CV 中位數"] = (eval(cv) if isinstance(cv, str) else cv)["median"]
    b = load(d, "E9b_supervised_baseline_rt.json")
    m["E9b 校準目標 FPR"] = b["calibration_target_fpr"]; m["E9b 校準後乾淨誤報"] = b["thr_cal"]["own"]["clean_fpr"]["mean"]
    return m
M = {k: metrics(v) for k, v in CFG.items()}
bad = [k for k in M["A"] if M["A"][k] != M["A'"][k]]
os.makedirs(OUT, exist_ok=True)
rows = ["| 指標 | A 舊式 | B 排除零值 | C 有效樣本 | A→B | B→C |", "|---|---|---|---|---|---|"]
for k in M["A"]:
    a, b, c = M["A"][k], M["B"][k], M["C"][k]
    rows.append(f"| {k} | {a:.4f} | {b:.4f} | {c:.4f} | {b-a:+.4f} | {c-b:+.4f} |")
md = "\n".join(["# 延遲修正之分解（腳本輸出）", "", f"來源：{json.dumps(CFG, ensure_ascii=False)}", "",
                f"K-A（D-30P1 舊式 = D-30P 舊式，逐位）：{'通過' if not bad else '未通過：' + ', '.join(bad)}", ""] + rows)
open(os.path.join(OUT, "delay_decomposition.md"), "w", encoding="utf-8").write(md + "\n")
json.dump({"configs": CFG, "metrics": M, "K-A_pass": not bad, "K-A_mismatch": bad}, open(os.path.join(OUT, "delay_decomposition.json"), "w"), ensure_ascii=False, indent=1)
print(md); sys.exit(1 if bad else 0)
