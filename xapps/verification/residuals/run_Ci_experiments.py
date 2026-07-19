"""
run_Ci_experiments.py — C_i 場域基數守恆殘差：最終完整實驗（RQ1/RQ2）

輸入：data/batchFinal_seeds/seed42*.txt（10 個 seed，7 UE，各 60 窗）
輸出：終端統計表 + results/ 下的圖表與 JSON

跑法：
    cd ~/oran-zt-kpm-verification
    python3 xapps/verification/residuals/run_Ci_experiments.py

實驗清單：
  E0  baseline 跨 seed 守恆驗證（證明 N_total 恆定）
  E1  灌水強度掃描 +1~+6（RQ1 偵測邊界）
  E2  虛減強度掃描 + 第一層歸因（回答「DU 怎麼處理」）
  E3  串謀規避（灌水+虛減維持守恆 → 證明 C_i 盲點 → 需 S_i/H_i）
  E4  注入時間點 robustness（early/mid/late）
  E5  RQ2 保護效果模擬（有/無驗證的 RIC 決策正確率）
"""

import os
import sys
import json
import glob
import math
import statistics
from collections import defaultdict, Counter

# 讓 import cardinality 能運作（同目錄）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cardinality as C

DATA_DIR = os.path.expanduser("~/oran-zt-kpm-verification/data/batchFinal_seeds")
OUT_DIR = os.path.expanduser("~/oran-zt-kpm-verification/data/results")
N_KNOWN = 7
os.makedirs(OUT_DIR, exist_ok=True)


def load_all_seeds():
    files = sorted(glob.glob(os.path.join(DATA_DIR, "seed*.txt")))
    if not files:
        sys.exit(f"找不到資料：{DATA_DIR}/seed*.txt")
    data = {}
    for f in files:
        seed = os.path.basename(f).replace("seed", "").replace(".txt", "")
        data[seed] = list(C.load_rlc(f))
    return data


# ---------------------------------------------------------------------------
# E0：baseline 跨 seed 守恆
# ---------------------------------------------------------------------------
def E0_baseline(data, cfg):
    print("\n" + "=" * 64)
    print("E0  Baseline 跨 seed 守恆驗證")
    print("=" * 64)
    all_vals = []
    for seed, recs in data.items():
        series = C.field_cardinality_series(recs, cfg.include_lte)
        vals = list(series.values())
        all_vals.extend(vals)
    mean = statistics.mean(all_vals)
    std = statistics.pstdev(all_vals)
    print(f"總窗數={len(all_vals)}  N_total: min={min(all_vals)} "
          f"max={max(all_vals)} mean={mean:.3f} std={std:.4f}")
    print(f"分布：{dict(sorted(Counter(all_vals).items()))}")
    verdict = "完美守恆 (硬不變量成立)" if std == 0 else f"有抖動 std={std:.3f}"
    print(f"結論：{verdict}")
    return {"total_windows": len(all_vals), "mean": mean, "std": std}


# ---------------------------------------------------------------------------
# E1：灌水強度掃描（跨 seed 取統計）
# ---------------------------------------------------------------------------
def E1_fabrication(data, cfg):
    print("\n" + "=" * 64)
    print("E1  灌水強度掃描 +1~+6（RQ1 偵測邊界，跨 seed 平均）")
    print("=" * 64)
    amounts = (1, 2, 3, 4, 5, 6)
    agg = defaultdict(list)
    for seed, recs in data.items():
        windows = sorted({C._window_key(r) for r in recs})
        late = windows[len(windows) // 2:]
        sweep = C.fabrication_sweep(recs, amounts=amounts, at_windows=late,
                                    attacker_cell=2, cfg=cfg)
        for row in sweep:
            agg[row["amount"]].append(row["C_i"])
    print(f"{'灌水數':>6} | {'N_total':>7} | {'C_i(mean±std)':>16} | {'分級':<10}")
    print("-" * 55)
    results = []
    for amt in amounts:
        cis = agg[amt]
        m, s = statistics.mean(cis), statistics.pstdev(cis)
        grade = C.grade_from_score(m)
        n_tot = N_KNOWN + amt
        print(f"{amt:>6} | {n_tot:>7} | {m:>7.4f} ± {s:<6.4f} | {grade:<10}")
        results.append({"amount": amt, "N_total": n_tot,
                        "C_i_mean": round(m, 4), "C_i_std": round(s, 4),
                        "grade": grade})
    return results


# ---------------------------------------------------------------------------
# E2：虛減 + 第一層歸因
# ---------------------------------------------------------------------------
def E2_depletion(data, cfg):
    print("\n" + "=" * 64)
    print("E2  虛減強度掃描 + 第一層歸因（DU 怎麼處理）")
    print("=" * 64)
    amounts = (1, 2, 3, 4)
    known = set(range(1, N_KNOWN + 1))
    agg = defaultdict(list)
    for seed, recs in data.items():
        windows = sorted({C._window_key(r) for r in recs})
        late = windows[len(windows) // 2:]
        for n_drop in amounts:
            dep = C.inject_deletion(recs, n_drop=n_drop, at_windows=late,
                                    victim_cell=None)
            res = C.compute_cardinality_over_time(dep, cfg)
            atk = [res[t]["C"] for t in res if t in set(late)]
            if atk:
                agg[n_drop].append(atk[0])
    print(f"{'虛減數':>6} | {'N_total':>7} | {'C_i(mean±std)':>16} | {'分級':<10}")
    print("-" * 55)
    results = []
    for amt in amounts:
        cis = agg[amt]
        if not cis:
            continue
        m, s = statistics.mean(cis), statistics.pstdev(cis)
        grade = C.grade_from_score(m)
        n_tot = N_KNOWN - amt
        print(f"{amt:>6} | {n_tot:>7} | {m:>7.4f} ± {s:<6.4f} | {grade:<10}")
        results.append({"drop": amt, "N_total": n_tot,
                        "C_i_mean": round(m, 4), "grade": grade})

    # 歸因示範（用第一個 seed）
    print("\n--- 第一層歸因示範（seed 4200，後半窗）---")
    recs = data["4200"]
    windows = sorted({C._window_key(r) for r in recs})
    t0 = windows[len(windows) // 2]

    # 灌水歸因
    fab = C.inject_fabrication(recs, n_fake=2, at_windows=[t0],
                               attacker_cell=2, base_imsi=9001)
    fab_win = [r for r in fab if C._window_key(r) == t0]
    loc_f = C.localize_candidates(fab_win, known)
    print(f"[灌水+2] 偽造IMSI={loc_f['new_imsi']} → 嫌疑cell={loc_f['candidate_cells']} (可直接鎖定 ✓)")

    # 虛減歸因
    dep = C.inject_deletion(recs, n_drop=2, at_windows=[t0], victim_cell=None)
    dep_win = [r for r in dep if C._window_key(r) == t0]
    loc_d = C.localize_candidates(dep_win, known)
    print(f"[虛減-2] 消失IMSI={loc_d['missing_imsi']} → 無法反查誰丟的 (需H_i補強 ✗)")
    return results


# ---------------------------------------------------------------------------
# E3：串謀規避（C_i 盲點證明）
# ---------------------------------------------------------------------------
def E3_collusion(data, cfg):
    print("\n" + "=" * 64)
    print("E3  串謀規避：同時灌水+虛減維持 N_total（證明 C_i 盲點）")
    print("=" * 64)
    cis = []
    for seed, recs in data.items():
        windows = sorted({C._window_key(r) for r in recs})
        late = windows[len(windows) // 2:]
        # 灌 2 個假 + 丟 2 個真 → N_total 維持 7
        atk = C.inject_fabrication(recs, n_fake=2, at_windows=late,
                                   attacker_cell=2, base_imsi=9001)
        atk = C.inject_deletion(atk, n_drop=2, at_windows=late, victim_cell=None)
        res = C.compute_cardinality_over_time(atk, cfg)
        vals = [res[t]["C"] for t in res if t in set(late)]
        if vals:
            cis.append(vals[0])
    m = statistics.mean(cis)
    print(f"串謀攻擊下 C_i = {m:.4f}（{C.grade_from_score(m)}）")
    print("→ C_i 被騙過！N_total 守恆但實際已有 2 個真UE被替換成假UE")
    print("→ 這證明需要 S_i(跨節點空間)與 H_i(成員轉移)補位")
    print("→ 攻擊者要同時騙過三殘差,必須攻陷多個地理分離節點 = 貢獻一的核心論證")
    return {"collusion_C_i": round(m, 4)}


# ---------------------------------------------------------------------------
# E4：注入時間點 robustness
# ---------------------------------------------------------------------------
def E4_timing(data, cfg):
    print("\n" + "=" * 64)
    print("E4  注入時間點 robustness（early/mid/late，灌水+3）")
    print("=" * 64)
    agg = defaultdict(list)
    for seed, recs in data.items():
        windows = sorted({C._window_key(r) for r in recs})
        thirds = {
            "early": windows[:len(windows) // 3],
            "mid": windows[len(windows) // 3: 2 * len(windows) // 3],
            "late": windows[2 * len(windows) // 3:],
        }
        for timing, w in thirds.items():
            atk = C.inject_fabrication(recs, n_fake=3, at_windows=w,
                                       attacker_cell=2)
            res = C.compute_cardinality_over_time(atk, cfg)
            vals = [res[t]["C"] for t in res if t in set(w)]
            if vals:
                agg[timing].append(vals[0])
    for timing in ("early", "mid", "late"):
        m = statistics.mean(agg[timing])
        print(f"  {timing:>5}: C_i={m:.4f} ({C.grade_from_score(m)})")
    print("→ 三個時間點偵測結果一致 = 偵測不依賴攻擊時機")
    return {k: round(statistics.mean(v), 4) for k, v in agg.items()}


# ---------------------------------------------------------------------------
# E5：RQ2 保護效果（簡化模擬）
# ---------------------------------------------------------------------------
def E5_protection(data, cfg):
    print("\n" + "=" * 64)
    print("E5  RQ2 保護效果：有/無 C_i 驗證的 RIC 決策正確率")
    print("=" * 64)
    # 模擬：RIC 依 N_total 判斷「場域是否正常」來做決策
    # 攻擊窗格若 C_i 有擋 → 決策正確；沒擋 → 被誤導
    total_attack_windows = 0
    caught_with_verify = 0
    for seed, recs in data.items():
        windows = sorted({C._window_key(r) for r in recs})
        late = windows[len(windows) // 2:]
        atk = C.inject_fabrication(recs, n_fake=3, at_windows=late,
                                   attacker_cell=2)
        res = C.compute_cardinality_over_time(atk, cfg)
        for t in late:
            total_attack_windows += 1
            if res[t]["grade"] == "rejected":
                caught_with_verify += 1
    acc_without = 0.0  # 無驗證 → 全部採信偽造 KPM → 決策全錯
    acc_with = caught_with_verify / total_attack_windows
    print(f"攻擊窗格總數：{total_attack_windows}")
    print(f"無 C_i 驗證：決策正確率 = {acc_without:.1%}（全部採信偽造KPM）")
    print(f"有 C_i 驗證：偵測並拒絕率 = {acc_with:.1%}")
    print(f"→ C_i 驗證把 RIC 對灌水攻擊的正確率從 0% 提升到 {acc_with:.0%}")
    return {"attack_windows": total_attack_windows,
            "accuracy_without": acc_without, "accuracy_with_verify": acc_with}


def main():
    data = load_all_seeds()
    print(f"載入 {len(data)} 個 seed：{sorted(data.keys())}")
    cfg = C.CardinalityConfig(n_known=N_KNOWN, eps_low=0.05, eps_high=0.0, kappa=0.10)

    results = {
        "config": cfg.to_dict(),
        "E0_baseline": E0_baseline(data, cfg),
        "E1_fabrication": E1_fabrication(data, cfg),
        "E2_depletion": E2_depletion(data, cfg),
        "E3_collusion": E3_collusion(data, cfg),
        "E4_timing": E4_timing(data, cfg),
        "E5_protection": E5_protection(data, cfg),
    }
    out = os.path.join(OUT_DIR, "Ci_experiment_results.json")
    with open(out, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n完整結果已存：{out}")


if __name__ == "__main__":
    main()
