#!/usr/bin/env python3
"""
zt_kpm_xapp.py — 零信任 KPM 驗證 xApp(骨架 + runtime benchmark)

【定位】
本模組依 O-RAN xApp 之架構契約實作驗證邏輯:訂閱 → 逐 indication 聚合 →
窗邊界觸發驗證 → 階層式融合 → 發布信任註記。資料來源目前為 trace replay
(IndicationSource 抽象層),E2 binding 尚未完成——將 TraceReplaySource 換成
E2SubscriptionSource 即可接上 live RIC,驗證邏輯不需改動。

【設計特點:唯讀信任根】
與一般會持續 retrain 的 ML xApp 相反,本 xApp 之基線(per-UE 停留分布、
global MAD)於啟動時載入後**永不線上更新**,避免攻擊者以緩慢注入養高基線。

【動作模式:註記型(annotation)】
本 xApp 不攔截 KPM 流、亦不下 E2SM-RC control,而是將逐 (node, window) 之
信任狀態寫入共享資料層,由消費端 xApp 自行過濾。此為 O-RAN 標準相容之做法
(驗證 xApp 無權阻斷他人訂閱)。

【輸出】
  data/results/xapp_trust_annotations.jsonl   逐窗信任註記
  data/results/xapp_runtime_benchmark.json    每窗處理延遲 mean/P95/P99
  data/results/fig_xapp_runtime.png           延遲分布圖

跑法:
  python3 zt_kpm_xapp.py                      # 預設 replay D-SH(300s)
  python3 zt_kpm_xapp.py --dataset dc         # replay D-C(60s)
"""
import os, sys, glob, json, time, argparse, collections
import numpy as np

SI_LSTM_DIR = os.path.expanduser("~/oran-zt-kpm-verification/data/si_lstm_seeds")
BATCH_DIR   = os.path.expanduser("~/oran-zt-kpm-verification/data/batchFinal_seeds")
OUT_DIR     = os.path.expanduser("~/oran-zt-kpm-verification/data/results")
os.makedirs(OUT_DIR, exist_ok=True)

# ---- 定案參數(對齊第四章)----
N_KNOWN      = 7
LTE_CELL     = 1
TAU_S        = 4.0     # S_i 共識殘差門檻
TAU_H_WARN   = 2.0     # H_i-D1 low-trust
TAU_H_REJECT = 3.0     # H_i-D1 strong evidence
L_C          = 2       # C_i 持續窗
MIN_PEER     = 2       # S_i full consensus 下限
NEAR_RT_BUDGET_MS = 10.0   # Near-RT RIC 控制迴圈預算


# ==========================================================================
# 1. Indication Source 抽象層 —— 換掉這一層即可接 live E2
# ==========================================================================
class IndicationSource:
    """xApp 的資料入口。E2 版本應實作 subscribe() 並於 on_indication 回呼。"""
    def windows(self):
        raise NotImplementedError


class TraceReplaySource(IndicationSource):
    """由 RLC trace 重放 KPM indication(等價於 E2SM-KPM report style)。"""
    def __init__(self, path):
        self.path = path

    def windows(self):
        """yield (window_id, {cell: {imsi: delay_ms}})——等同一個 granularity period 的聚合。"""
        buf = collections.defaultdict(lambda: collections.defaultdict(dict))
        with open(self.path) as fh:
            fh.readline()
            for line in fh:
                p = line.split("\t")
                if len(p) < 11:
                    continue
                try:
                    w = int(float(p[0])); cell = int(p[2])
                    imsi = int(p[3]); d = float(p[10]) * 1000.0
                except ValueError:
                    continue
                buf[w][cell][imsi] = d
        for w in sorted(buf):
            yield w, buf[w]


# class E2SubscriptionSource(IndicationSource):
#     """TODO: RAN Function ID 2 訂閱,granularity 1s,on_indication 解碼後聚合。
#        驗證邏輯不需改動——僅需在此填入 E2AP/E2SM-KPM binding。"""


# ==========================================================================
# 2. 唯讀信任根 —— 啟動時載入,永不線上更新
# ==========================================================================
class TrustAnchor:
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
                        if run: dwell[i].append(run)
                        run = 0
        med = np.median(vals) if vals else 0.0
        self.scale = 1.4826 * (float(np.median(np.abs(np.array(vals) - med))) + 1e-9) if vals else 1.0
        self.dwell = {}
        for i, d in dwell.items():
            if len(d) >= 8:
                m = np.median(d)
                mad = np.median(np.abs(np.array(d) - m))
                self.dwell[i] = (float(m), float(1.4826 * mad if mad > 0 else 1.0))
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
    """S_i:跨節點共識殘差。peer<MIN_PEER → unavailable(abstain)"""
    mmw = [c for c in cells if c != LTE_CELL]
    if target not in cells or target == LTE_CELL:
        return "n/a", None
    peers = [c for c in mmw if c != target]
    if len(peers) < MIN_PEER:
        return "unavailable", None
    tgt = float(np.mean(list(cells[target].values())))
    ref = float(np.median([np.mean(list(cells[c].values())) for c in peers]))
    z = abs(tgt - ref) / scale
    return ("violated" if z > TAU_S else "normal"), round(z, 2)


def verify_hi_d2(prev_map, cur_map):
    """H_i-D2:觀測層級瞬移斷言(mmWave A → mmWave B 無 LTE 過渡)"""
    for imsi, cur in cur_map.items():
        prev = prev_map.get(imsi, set())
        pm, cm = prev - {LTE_CELL}, cur - {LTE_CELL}
        if pm and cm and not (pm & cm) and LTE_CELL not in cur:
            return "violated", {"imsi": imsi, "from": sorted(pm), "to": sorted(cm)}
    return "normal", None


def verify_hi_d1(dwell_runs, anchor):
    """H_i-D1:LTE-only 停留 robust z(per-UE 唯讀基線)"""
    worst, worst_imsi = 0.0, None
    for imsi, run in dwell_runs.items():
        if run <= 0 or imsi not in anchor.dwell:
            continue
        med, sig = anchor.dwell[imsi]
        z = abs(run - med) / sig if sig > 0 else 0.0
        if z > worst:
            worst, worst_imsi = z, imsi
    if worst >= TAU_H_REJECT: return "strong", {"z": round(worst, 2), "imsi": worst_imsi}
    if worst >= TAU_H_WARN:   return "weak",   {"z": round(worst, 2), "imsi": worst_imsi}
    return "normal", None


# ==========================================================================
# 4. 階層式融合(對齊 4.4.3)
# ==========================================================================
def fuse(ci, ci_run, si, d2, d1):
    # 第一層:硬否決
    if ci == "violated":
        return ("rejected", "C_i hard veto") if ci_run >= L_C else \
               ("low-trust", f"C_i violated (pending, run={ci_run}<L_C)")
    if d2 == "violated":
        return "rejected", "H_i-D2 hard veto (teleport)"
    # 第二層:統計證據
    if si == "violated" and d1 in ("strong", "weak"):
        return "rejected", "S_i + H_i-D1 cross-corroboration"
    if si == "violated":
        return "low-trust", "S_i alone (escalate on persistence)"
    if d1 == "strong":
        return "low-trust", "H_i-D1 strong evidence → investigation"
    if d1 == "weak":
        return "low-trust", "H_i-D1 weak evidence"
    # 第三層:證據不可得
    if si == "unavailable":
        return "abstain", "S_i evidence unavailable (peer<2)"
    return "trusted", "no counterexample"


# ==========================================================================
# 5. xApp 主迴圈
# ==========================================================================
def run_xapp(source, anchor, node_of_interest=None):
    annotations, latencies = [], []
    prev_map, ci_run = {}, 0
    dwell_runs = collections.defaultdict(int)

    for w, cells in source.windows():
        t0 = time.perf_counter()                      # ← 計時起點(驗證處理)

        cur_map = collections.defaultdict(set)
        for c, ues in cells.items():
            for i in ues:
                cur_map[i].add(c)
        for i, cs in cur_map.items():
            dwell_runs[i] = dwell_runs[i] + 1 if cs == {LTE_CELL} else 0

        target = node_of_interest or next(
            (c for c in sorted(cells) if c != LTE_CELL), None)

        ci, ci_run, ci_ev = verify_ci(cells, ci_run)
        si, z            = verify_si(cells, target, anchor.scale) if target else ("n/a", None)
        d2, d2_ev        = verify_hi_d2(prev_map, cur_map)
        d1, d1_ev        = verify_hi_d1(dwell_runs, anchor)
        decision, rule   = fuse(ci, ci_run, si, d2, d1)

        latencies.append((time.perf_counter() - t0) * 1000.0)   # ms
        annotations.append({"window": w, "node": target, "decision": decision,
                            "rule": rule, "C_i": ci, "S_i": si, "z_S": z,
                            "H_i_D2": d2, "H_i_D1": d1,
                            "evidence": {k: v for k, v in
                                         (("C_i", ci_ev), ("D2", d2_ev), ("D1", d1_ev))
                                         if v}})
        prev_map = cur_map
    return annotations, np.array(latencies)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=["dsh", "dc"], default="dsh")
    args = ap.parse_args()

    if args.dataset == "dsh":
        files = sorted(glob.glob(os.path.join(SI_LSTM_DIR, "ues1_t300_seed*.txt"))) or \
                sorted(glob.glob("ues1_t300_seed*.txt"))
    else:
        files = sorted(glob.glob(os.path.join(BATCH_DIR, "seed42*.txt"))) or \
                sorted(glob.glob("seed42*.txt"))
    if len(files) < 2:
        print(f"資料不足(找到 {len(files)} 檔)"); return

    print(f"=== 零信任 KPM 驗證 xApp(trace replay,{len(files)} seed)===")
    all_lat, all_ann, dist = [], [], collections.Counter()
    for i, test in enumerate(files):                       # LOSO:基線不含受測 seed
        anchor = TrustAnchor([f for f in files if f != test])
        ann, lat = run_xapp(TraceReplaySource(test), anchor)
        all_ann += ann; all_lat.append(lat)
        for a in ann: dist[a["decision"]] += 1
        print(f"  [{os.path.basename(test)}] {len(ann)} 窗, "
              f"每窗 {lat.mean():.3f} ms (P95 {np.percentile(lat,95):.3f})")

    lat = np.concatenate(all_lat)
    bench = {"windows": int(lat.size), "n_seeds": len(files),
             "mean_ms": float(lat.mean()), "median_ms": float(np.median(lat)),
             "p95_ms": float(np.percentile(lat, 95)),
             "p99_ms": float(np.percentile(lat, 99)), "max_ms": float(lat.max()),
             "near_rt_budget_ms": NEAR_RT_BUDGET_MS,
             "budget_utilisation_p99": float(np.percentile(lat, 99) / NEAR_RT_BUDGET_MS),
             "note": "verification-layer compute only; excludes E2 decode/transport"}

    print(f"\n--- Runtime benchmark({lat.size} 窗)---")
    print(f"  mean={bench['mean_ms']:.3f} ms  P95={bench['p95_ms']:.3f}  "
          f"P99={bench['p99_ms']:.3f}  max={bench['max_ms']:.3f}")
    print(f"  Near-RT 預算({NEAR_RT_BUDGET_MS} ms)佔比 @P99 = "
          f"{100*bench['budget_utilisation_p99']:.2f}%")
    print(f"\n--- 信任決策分布 ---")
    for k, v in dist.most_common():
        print(f"  {k:<10} {v:>5} ({v/len(all_ann):.1%})")

    with open(os.path.join(OUT_DIR, "xapp_runtime_benchmark.json"), "w") as fh:
        json.dump({"benchmark": bench, "decision_distribution": dict(dist)},
                  fh, indent=2, ensure_ascii=False)
    with open(os.path.join(OUT_DIR, "xapp_trust_annotations.jsonl"), "w") as fh:
        for a in all_ann:
            fh.write(json.dumps(a, ensure_ascii=False) + "\n")
    print(f"\n寫入 {OUT_DIR}/xapp_runtime_benchmark.json, xapp_trust_annotations.jsonl")

    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(8, 4.6))
        ax.hist(lat, bins=60, color="#1971c2", alpha=0.85)
        for v, c, l in [(bench["mean_ms"], "#2b8a3e", "mean"),
                        (bench["p95_ms"], "#e8590c", "P95"),
                        (bench["p99_ms"], "#c92a2a", "P99")]:
            ax.axvline(v, ls="--", color=c, lw=1.6, label=f"{l} = {v:.3f} ms")
        ax.set_xlabel("per-window verification latency (ms)")
        ax.set_ylabel("count")
        ax.set_title(f"Zero-trust KPM verification xApp: compute overhead "
                     f"(P99 = {100*bench['budget_utilisation_p99']:.2f}% of {NEAR_RT_BUDGET_MS} ms budget)",
                     fontsize=10.5)
        ax.legend(fontsize=9); ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(os.path.join(OUT_DIR, "fig_xapp_runtime.png"), dpi=150)
        print("圖已存: fig_xapp_runtime.png")
    except ImportError:
        print("未安裝 matplotlib,略過畫圖")


if __name__ == "__main__":
    main()
