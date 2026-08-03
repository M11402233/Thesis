#!/usr/bin/env python3
"""
run_adversarial_msweep.py — S_i 抗協同串謀的 m-sweep 實測(取代舊的 9.2%/84.5% 估計)

攻擊模型:
  攻擊者控制 m 個 mmWave 節點,將其上報 delay 同步設為「場域共識 + 6σ」的偽造值,
  試圖讓偽造值不被 S_i 的跨節點一致性檢查否證。

方法(回應 review 對 bypass 分母的要求):
  - 對每個窗、每個 m-子集(controlled cells)列舉為一次 attack trial;
  - 以受控目標 cell j 的「其他同窗活躍 cell」中位數為 S_i 中心 c_j
    (其他 cell 含被控者=偽造值、誠實者=真值,故 m≥2 會毒化共識本身);
  - z_j = |fake − c_j| / s_global;bypass ⟺ z_j ≤ τ_S;
  - 按目標的 peer 數(= 同窗其他活躍 mmWave cell 數)分三層,分母嚴格分開:
        unavailable(peer=0) / weak(peer=1) / full-consensus(peer≥2)
  - 核心指標 = bypass_full / eligible_full-consensus_trials
    (unavailable 窗屬證據不可得,不計入有效繞過)

輸入: data/si_lstm_seeds/ues1_t300_seed42*.txt
輸出: data/results/adversarial_msweep.json, fig_adversarial_mstar.png
"""
import os, glob, json, collections, itertools
import numpy as np

DATA_DIR = os.path.expanduser("~/oran-zt-kpm-verification/data/si_lstm_seeds")
OUT_DIR  = os.path.expanduser("~/oran-zt-kpm-verification/data/results")
os.makedirs(OUT_DIR, exist_ok=True)

TAU_S      = 4.0     # 與 run_Si_experiments 一致
SIGMA_FAKE = 6.0     # 6σ 偽造偏離
MS         = [1, 2, 3, 4]
DELAY_COL  = 10


def load_cell_delay(path):
    dly = collections.defaultdict(lambda: collections.defaultdict(list))
    with open(path) as fh:
        fh.readline()
        for line in fh:
            p = line.split("\t")
            if len(p) < 11:
                continue
            try:
                w = int(float(p[0])); cell = int(p[2]); d = float(p[DELAY_COL])
            except ValueError:
                continue
            if cell == 1:            # 排除 LTE 錨點,只做 mmWave 跨節點
                continue
            dly[w][cell].append(d)
    return {w: {c: float(np.mean(dly[w][c])) * 1000.0 for c in dly[w]} for w in dly}


def main():
    files = sorted(glob.glob(os.path.join(DATA_DIR, "ues1_t300_seed*.txt"))) or \
            sorted(glob.glob("ues1_t300_seed*.txt"))
    if len(files) < 2:
        print(f"資料不足(找到 {len(files)} 檔)"); return

    data = {f: load_cell_delay(f) for f in files}
    allv = [v for f in files for w in data[f] for v in data[f][w].values()]
    med_g = np.median(allv)
    scale = 1.4826 * (float(np.median(np.abs(np.array(allv) - med_g))) + 1e-9)
    print(f"seeds={len(files)}  global scale s={scale:.4f} ms  tau_S={TAU_S}  fab={SIGMA_FAKE}σ\n")

    out = {"params": {"tau_S": TAU_S, "sigma_fake": SIGMA_FAKE, "scale_ms": scale,
                      "n_seeds": len(files)}, "per_m": []}

    for m in MS:
        tier = {"unavailable": 0, "weak": 0, "full": 0}
        byp  = {"unavailable": 0, "weak": 0, "full": 0}
        for f in files:
            for w, cd in data[f].items():
                cells = sorted(cd); P = len(cells)
                if P < m:
                    continue
                consensus = np.median([cd[c] for c in cells])
                fake = consensus + SIGMA_FAKE * scale
                for S in itertools.combinations(cells, m):
                    j = S[0]                              # 代表性受控目標
                    peer = P - 1
                    t = "unavailable" if peer < 1 else ("weak" if peer == 1 else "full")
                    tier[t] += 1
                    others = [fake if c in S else cd[c] for c in cells if c != j]
                    z = abs(fake - np.median(others)) / scale if others else 0.0
                    if z <= TAU_S:
                        byp[t] += 1

        def rate(a, b): return (a / b) if b else float("nan")
        row = {"m": m,
               "full_trials": tier["full"],   "full_bypass": byp["full"],
               "full_bypass_rate": rate(byp["full"], tier["full"]),
               "weak_trials": tier["weak"],   "weak_bypass": byp["weak"],
               "weak_bypass_rate": rate(byp["weak"], tier["weak"]),
               "unavailable_trials": tier["unavailable"],
               "unavailable_bypass": byp["unavailable"]}
        out["per_m"].append(row)
        print(f"m={m}: full-consensus bypass = {byp['full']}/{tier['full']} "
              f"= {100*rate(byp['full'],tier['full']):.1f}%   "
              f"(weak {byp['weak']}/{tier['weak']}, unavailable {tier['unavailable']})")

    with open(os.path.join(OUT_DIR, "adversarial_msweep.json"), "w") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)
    print(f"\n寫入 {os.path.join(OUT_DIR,'adversarial_msweep.json')}")

    # m_S*: 第一個 full-consensus bypass ≥ 50% 的 m
    m_star = next((r["m"] for r in out["per_m"] if r["full_bypass_rate"] >= 0.5), None)
    print(f"m_S*(拉動 full-consensus 共識所需最小節點數, ≥50%繞過) = {m_star}")

    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        ms   = [r["m"] for r in out["per_m"]]
        full = [100*r["full_bypass_rate"] for r in out["per_m"]]
        fig, ax = plt.subplots(figsize=(7, 5))
        ax.plot(ms, full, "o-", color="#c92a2a", lw=2.2, ms=8,
                label="bypass rate on full-consensus windows (peer≥2)")
        ax.axhline(50, ls=":", color="#868e96", alpha=0.7)
        for r in out["per_m"]:
            ax.annotate(f"{100*r['full_bypass_rate']:.0f}%\n(n={r['full_trials']})",
                        (r["m"], 100*r["full_bypass_rate"]),
                        textcoords="offset points", xytext=(6, -4), fontsize=8)
        ax.set_xlabel("number of colluding mmWave nodes  m")
        ax.set_ylabel("S_i bypass rate on full-consensus windows (%)")
        ax.set_title("Anti-collusion strength of S_i (6σ coordinated delay fabrication)")
        ax.set_xticks(ms); ax.set_ylim(-5, 105); ax.grid(alpha=0.3)
        ax.legend(loc="lower right")
        fig.tight_layout()
        fig.savefig(os.path.join(OUT_DIR, "fig_adversarial_mstar.png"), dpi=150)
        print("圖已存: fig_adversarial_mstar.png")
    except ImportError:
        print("未安裝 matplotlib,略過畫圖(JSON 已完整)")


if __name__ == "__main__":
    main()
