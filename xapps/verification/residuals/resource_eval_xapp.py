#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
resource_eval_xapp.py — 可用資源評估 xApp（Available-resource evaluation xApp；第四章 4.9.2、4.12）

【架構定位】（簡報 v0.6 第 27–28 頁之架構）
  Policy Enforcement xApp（P3）將 policy-admitted KPM 與 execution record 寫入共享資料層（DB）；
  合作消費端（RC xApp）與本 xApp 皆自 DB 讀取。本 xApp 另經 Resource Termination 取得各 cell 當窗之
  PRB 用量，**逐窗**計算並回報：
    admitted-input availability  當窗被准入之 mmWave 節點數 ÷ 當窗有上報之 mmWave 節點數
    ρ_PRB、V_PRB                 當窗已用 PRB 中其 KPM 被准入之比例，及其補數（PRB 能見度損失）
  本 xApp 與 P1–P3 於 Near-RT RIC 內同時運作，於每窗 P3 發布後執行；它**不做驗證、不改變信任狀態**。

【實作層級（須如實陳述）】
  本檔為整合原型：DB 與 Resource Termination 為行程內之抽象層（SharedDB、ResourceTermination），
  資料入口為 trace replay（與 zt_kpm_xapp.py 相同）；PRB 取自同一模擬之 E2 NR DU 報表
  （RRU.PrbUsedDl.UEID 加總，prb_reader.py）。未經 live RIC 之 SDL 與訊息匯流排。

【內建檢查】（任一失敗即停止、不寫檔）
  1. 本 xApp 自 DB 讀到之准入節點 = P3 之 execution record 之 admitted。
  2. 於 run_RQ3_decision_replay.py 之評估窗（序列後半段、至少 2 個 mmWave cell 有上報）上彙總之
     ρ_cap 與 ρ_PRB，須等於該腳本乾淨資料之 C_strict（admission=strict）或 C_restrict_annot
     （admission=restrict_annotated）之值（容許 1e-12）。
  3. 有上報之 (cell, 窗) 皆有 PRB 值（不補值）。
  4. 全序列之准入註記數 = zt_kpm_xapp 之 rule breakdown 之 admitted（僅 strict）。

跑法：ZT_DATASET=d30 python3 resource_eval_xapp.py [--admission strict|restrict_annotated]
"""
import os
import sys
import json
import time
import argparse
import numpy as np
import datasets as DS
import zt_kpm_xapp as X
import prb_reader as PRB


class SharedDB:
    """共享資料層之行程內抽象：P3 寫入當窗之 admitted view 與 execution record，其他 xApp 讀取。"""

    def __init__(self):
        self._view, self._rec = {}, {}

    def publish(self, w, view, rec):
        self._view[w], self._rec[w] = view, rec

    def admitted_view(self, w):
        return self._view[w]

    def execution_record(self, w):
        return self._rec[w]


class ResourceTermination:
    """Resource Termination 之抽象：提供各 cell 於第 w 窗之 PRB 時間占用率（原生 PRB ÷ 139）。"""

    def __init__(self, aux_dir, max_window=None):
        self._u = {k: e["prb"] / PRB.PRB_CONST for k, e in PRB.load_du_prb(aux_dir, max_window).items()}

    def prb_occupancy(self, cell, w):
        return self._u.get((cell, w))


class AvailableResourceEvaluationXApp:
    """逐窗讀取 DB 之准入結果與 Resource Termination 之 PRB，回報可用性與 PRB 能見度損失。"""

    def __init__(self, db, rt):
        self.db, self.rt = db, rt
        self.records, self.latency_ms, self.missing = [], [], 0

    def on_window(self, w, k):
        t0 = time.perf_counter_ns()
        rec = self.db.execution_record(w)
        admitted = set(self.db.admitted_view(w))
        active = set(rec["allow"]) | set(rec["restrict"]) | set(rec["exclude"]) | set(rec["defer"]) | set(rec["unannotated"])
        used = kept = 0.0
        for j in active:
            u = self.rt.prb_occupancy(j, k)
            if u is None:
                self.missing += 1
                continue
            used += u
            if j in admitted:
                kept += u
        out = {"window": w, "k": k, "active": len(active), "admitted": len(admitted),
               "admitted_input_availability": (len(admitted) / len(active)) if active else None,
               "prb_used": used, "prb_admitted": kept,
               "rho_prb": (kept / used) if used > 0 else None,
               "v_prb": (1 - kept / used) if used > 0 else None,
               "db_admitted_matches_p3": sorted(admitted) == rec["admitted"]}
        self.latency_ms.append((time.perf_counter_ns() - t0) / 1e6)
        self.records.append(out)
        return out


def aggregate(recs):
    a = sum(r["active"] for r in recs); m = sum(r["admitted"] for r in recs)
    u = sum(r["prb_used"] for r in recs); kp = sum(r["prb_admitted"] for r in recs)
    return {"windows": len(recs), "node_windows": a, "admitted_node_windows": m,
            "admitted_input_availability": m / a if a else None,
            "rho_prb": kp / u if u else None, "v_prb": (1 - kp / u) if u else None,
            "used_rb28_per_window": u * PRB.N_RB_CFG1 / len(recs) if recs else None,
            "admitted_rb28_per_window": kp * PRB.N_RB_CFG1 / len(recs) if recs else None,
            "windows_with_no_admitted_input": sum(1 for r in recs if r["active"] and not r["admitted"])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--admission", choices=sorted(X.ADMISSION), default="strict")
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()
    out_dir = args.out_dir or DS.results_dir()
    files = DS.files()
    if len(files) < 2:
        raise SystemExit("資料不足")
    mw = DS.CFG.get("max_window")
    print(f"=== 可用資源評估 xApp（trace replay，{len(files)} seed，資料集 {DS.NAME}，admission={args.admission}）===")
    all_recs, eval_recs, per_seed, lat, missing, mismatch = [], [], {}, [], 0, 0
    for test in files:
        sd = DS.seed_of(test)
        aux = os.path.dirname(DS.aux_path(sd, "x"))
        anchor = X.TrustAnchor([f for f in files if f != test])
        src = X.TraceReplaySource(test)
        wins = list(src.windows())
        idx = {w: k for k, (w, _) in enumerate(wins)}
        db, rt = SharedDB(), ResourceTermination(aux, mw)
        app = AvailableResourceEvaluationXApp(db, rt)

        def on_published(w, cells, view, rec, db=db, app=app, idx=idx):
            db.publish(w, view, rec)              # P3 → DB
            app.on_window(w, idx[w])              # 可用資源評估 xApp 於同一窗讀取並回報

        X.run_xapp(src, anchor, "all", collect=False, admission=args.admission, on_published=on_published)
        recs = app.records
        mismatch += sum(1 for r in recs if not r["db_admitted_matches_p3"])
        missing += app.missing
        half = len(wins) // 2
        ev = [r for r in recs if r["k"] >= half and r["active"] >= 2]      # 與 RQ3 之評估窗相同
        per_seed[sd] = {"all": aggregate(recs), "rq3_windows": aggregate(ev)}
        all_recs += [dict(r, seed=sd) for r in recs]; eval_recs += ev; lat += app.latency_ms
        print(f"  [seed {sd}] {len(recs)} 窗：准入輸入可用率 {per_seed[sd]['all']['admitted_input_availability']:.1%}、"
              f"ρ_PRB {per_seed[sd]['all']['rho_prb']:.1%}、V_PRB {per_seed[sd]['all']['v_prb']:.1%}")

    tot, ev = aggregate(all_recs), aggregate(eval_recs)
    ok = True
    print(f"── 檢查 1：DB 之准入節點 = P3 execution record {'✓' if mismatch == 0 else '✗'}（不符 {mismatch}）")
    ok &= mismatch == 0
    print(f"── 檢查 3：有上報之 (cell, 窗) 皆有 PRB 值 {'✓' if missing == 0 else '✗'}（缺 {missing}）")
    ok &= missing == 0
    rq3_p = os.path.join(out_dir, "RQ3_decision_replay.json")
    cons = {"strict": "C_strict", "restrict_annotated": "C_restrict_annot"}[args.admission]
    if os.path.exists(rq3_p):
        r = json.load(open(rq3_p, encoding="utf-8"))[f"uebound|clean|{cons}"]
        d_cap = abs(ev["admitted_input_availability"] - r["rho"]); d_prb = abs(ev["rho_prb"] - r["rho_prb"])
        c2 = d_cap <= 1e-12 and d_prb <= 1e-12 and ev["windows"] == r["windows"]
        print(f"── 檢查 2：RQ3 評估窗上之 ρ_cap／ρ_PRB = RQ3 乾淨 {cons} {'✓' if c2 else '✗'}"
              f"（窗 {ev['windows']}／{r['windows']}；差 {d_cap:.1e}／{d_prb:.1e}）")
        ok &= c2
    else:
        print("── 檢查 2：未找到 RQ3_decision_replay.json，未核對"); ok = False
    bd_p = os.path.join(out_dir, "xapp_rule_breakdown_bound_all_uebound_strict.json")
    if args.admission == "strict" and os.path.exists(bd_p):
        adm = json.load(open(bd_p, encoding="utf-8"))["admitted"]
        n_adm = adm.get("count", adm.get("n")) if isinstance(adm, dict) else adm
        c4 = n_adm == tot["admitted_node_windows"]
        print(f"── 檢查 4：全序列准入註記數 = xApp rule breakdown {'✓' if c4 else '✗'}（{tot['admitted_node_windows']}／{n_adm}）")
        ok &= c4
    if not ok:
        print("  ✗ 檢查未通過。停止：不寫入任何輸出。請回報，勿調參數。"); sys.exit(2)

    lat = np.array(lat)
    print(f"\n--- 全序列（{tot['windows']} 窗、{tot['node_windows']} 筆節點註記）---")
    print(f"  准入輸入可用率 {tot['admitted_input_availability']:.1%}；ρ_PRB {tot['rho_prb']:.1%}；V_PRB {tot['v_prb']:.1%}；"
          f"無任何准入輸入之窗 {tot['windows_with_no_admitted_input']}")
    print(f"  每窗已用 PRB（28 RB 尺度，各 cell 合計）{tot['used_rb28_per_window']:.1f}，其中 KPM 被准入者 {tot['admitted_rb28_per_window']:.1f}")
    print(f"--- RQ3 評估窗（後半段，{ev['windows']} 窗）---")
    print(f"  ρ_cap {ev['admitted_input_availability']:.1%}；ρ_PRB {ev['rho_prb']:.1%}；V_PRB {ev['v_prb']:.1%}")
    print(f"--- 本 xApp 之每窗處理時間（不含 P1–P3）--- mean={lat.mean():.4f} ms  P99={np.percentile(lat, 99):.4f}  max={lat.max():.4f}")
    out = {"admission": args.admission, "dataset": DS.NAME, "implementation": "integrated prototype, trace replay; "
           "DB and Resource Termination are in-process abstractions", "checks": "ok",
           "all_windows": tot, "rq3_windows": ev, "per_seed": per_seed,
           "latency_ms": {"mean": float(lat.mean()), "p95": float(np.percentile(lat, 95)),
                          "p99": float(np.percentile(lat, 99)), "max": float(lat.max())}}
    p = os.path.join(out_dir, f"resource_eval_xapp_{args.admission}.json")
    json.dump(out, open(p, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    pw = os.path.join(out_dir, f"resource_eval_xapp_{args.admission}_per_window.jsonl")
    with open(pw, "w", encoding="utf-8") as fh:
        for r in all_recs:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\n寫入 {p}\n寫入 {pw}")


if __name__ == "__main__":
    main()
