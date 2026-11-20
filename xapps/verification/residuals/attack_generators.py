#!/usr/bin/env python3
"""
attack_generators.py — E29 不規則攻擊產生器（規格 docs/thesis/E29_irregular_attack_spec.md）

只產生「每秒乘數排程」，不讀資料、不做判定：
    schedule[cell] = np.ndarray(T)，未攻擊之秒 = 1.0；攻擊之秒 = 該段之倍數 f。
套用方式與 run_RQ3_decision_replay.py:146–158 之 apply_attack 相同（受攻擊 cell 之每個 UE delay × f）。

規則（使用者 2026-11-19 決定 Q1–Q7）：
  時間  IRR：第一段起點 t0 ~ U{T0_LO..T0_HI}；之後 ON／OFF 交替，
        ON  = MIN_ON  + Geom(平均 MEAN_ON  − MIN_ON)   （離散化之指數分布，最小 3 s）
        OFF = MIN_OFF + Geom(平均 MEAN_OFF − MIN_OFF)
        ⇒ 攻擊段之起點為（位移後之）Poisson 過程；最後一段截於 T。
  幅度  每段獨立抽 f：down ~ U[0.6, 0.9]、up ~ U[1.2, 1.5]；段內固定。
  方向  down、up 兩族分開（不混合）。
  節點  single：1 個（cell 2–8 輪流，由呼叫端指定）；
        multi ：首個在 t0，之後到達間隔 = Geom(平均 MEAN_ARRIVAL)（Poisson 到達；主設定 60 s，
                敏感度 30／60／120 s），
                至多 MAX_NODES 個，cell 自 2–8 不放回均勻抽；被攻陷後不復原，
                各節點有獨立之 ON／OFF 與倍數，方向相同。
  知識  IRR 不知道 τ_S、不看判定（一般攻擊者）。
  重複  亂數 seed r = 0..9；排程由 (資料 seed, 起始 cell, r, 族) 決定性產生。

自我檢查（python attack_generators.py --selftest）：決定性、最短段長、t0 範圍、
倍數範圍、multi 之節點數上限與不重複、單段統計與設定之平均相符（僅報告，不調參數）。
"""
import argparse, hashlib, json, sys
import numpy as np

T = 300                     # 分析窗 0–299
CELLS = list(range(2, 9))   # mmWave cell 2–8
T0_LO, T0_HI = 30, 150
MIN_ON, MEAN_ON = 3, 10
MIN_OFF, MEAN_OFF = 3, 20
MEAN_ARRIVAL = 60           # 主設定；敏感度掃 MEAN_ARRIVALS
MEAN_ARRIVALS = [30, 60, 120]
MAX_NODES = 4               # 與 run_adversarial_msweep.py:32 之 MS 上限一致
F_RANGE = {"down": (0.6, 0.9), "up": (1.2, 1.5)}
N_RNG = 10


def rng_for(data_seed, cell, r, family, mode):
    key = f"E29|{data_seed}|{cell}|{r}|{family}|{mode}".encode()
    return np.random.default_rng(int.from_bytes(hashlib.sha256(key).digest()[:8], "little"))


def _geom_extra(rng, mean_extra):
    """非負整數、平均 = mean_extra 之幾何分布（指數分布之離散版本）"""
    if mean_extra <= 0:
        return 0
    p = 1.0 / (mean_extra + 1.0)
    return int(rng.geometric(p)) - 1


def onoff_schedule(rng, family, start, T=T):
    """回傳 (mult[T], bursts)；bursts = [(s, e, f)]，e 不含"""
    lo, hi = F_RANGE[family]
    mult = np.ones(T)
    bursts = []
    t = start
    while t < T:
        on = MIN_ON + _geom_extra(rng, MEAN_ON - MIN_ON)
        f = float(rng.uniform(lo, hi))
        e = min(T, t + on)
        mult[t:e] = f
        bursts.append((t, e, f))
        t = e + MIN_OFF + _geom_extra(rng, MEAN_OFF - MIN_OFF)
    return mult, bursts


def irregular(data_seed, cell, r, family, mode="single", T=T, mean_arrival=MEAN_ARRIVAL):
    """single：只攻擊 cell；multi：cell 為第一個被攻陷者，其餘依 Poisson 到達。
    回傳 {"schedule": {cell: mult}, "events": [...]}"""
    assert family in F_RANGE and mode in ("single", "multi") and cell in CELLS
    rng = rng_for(data_seed, cell, r, family, mode if mode == "single" else f"multi{mean_arrival}")
    t0 = int(rng.integers(T0_LO, T0_HI + 1))
    nodes = [(cell, t0)]
    if mode == "multi":
        pool = [c for c in CELLS if c != cell]
        t = t0
        while len(nodes) < MAX_NODES:
            t += 1 + _geom_extra(rng, mean_arrival - 1)
            if t >= T:
                break
            c = pool.pop(int(rng.integers(len(pool))))
            nodes.append((c, t))
    sched, events = {}, []
    for c, tc in nodes:
        m, b = onoff_schedule(rng, family, tc, T)
        sched[c] = m
        events.append({"cell": c, "compromised_at": tc, "bursts": b})
    return {"schedule": sched, "events": events, "t0": t0}


# 既有之規律攻擊，以相同介面表示（只供總表與對照；數值定義引自原腳本）
def step(cell, f, T=T):                       # run_E9_operating_regime.py:109；RQ3 :155
    m = np.ones(T); m[T // 2:] = f
    return {"schedule": {cell: m}, "t0": T // 2}


def drift_down(cell, rate, T=T):              # run_RQ3_decision_replay.py:155（乘法、下限 0.05）
    m = np.ones(T); k = np.arange(T // 2, T)
    m[T // 2:] = np.maximum(0.05, 1.0 - rate * (k - T // 2))
    return {"schedule": {cell: m}, "t0": T // 2}


def drift_up(cell, rate, T=T):                # E29 調高之漂移：乘法 1 + rate·(k−t0)（與 drift_down 對稱；E9 為加法，見規格 §2）
    m = np.ones(T); k = np.arange(T // 2, T)
    m[T // 2:] = 1.0 + rate * (k - T // 2)
    return {"schedule": {cell: m}, "t0": T // 2}


def apply(windows, gen):
    """windows 之格式同 run_RQ3_decision_replay.py：windows[k] = (時間, {cell: {ue: delay}})"""
    import copy
    out = copy.deepcopy(windows)
    for c, m in gen["schedule"].items():
        for k in range(min(len(out), len(m))):
            if m[k] != 1.0 and c in out[k][1]:
                for i in list(out[k][1][c]):
                    if out[k][1][c][i] is not None:             # 第二階段：缺值不可竄改
                        out[k][1][c][i] *= m[k]
    return out


def selftest():
    ok = True
    def chk(name, cond):
        nonlocal ok
        print(("PASS " if cond else "FAIL ") + name)
        ok &= bool(cond)
    a = irregular(4200, 3, 0, "down"); b = irregular(4200, 3, 0, "down")
    chk("決定性（同參數逐位相同）", all(np.array_equal(a["schedule"][c], b["schedule"][c]) for c in a["schedule"]))
    c = irregular(4200, 3, 1, "down")
    chk("不同 r 產生不同排程", not np.array_equal(a["schedule"][3], c["schedule"][3]))
    on_l, off_l, t0s, fs, nn, duty = [], [], [], {"down": [], "up": []}, {}, []
    for fam in ("down", "up"):
        for ds in range(4200, 4208):
            for cell in CELLS:
                for r in range(N_RNG):
                    g = irregular(ds, cell, r, fam)
                    ev = g["events"][0]; bs = ev["bursts"]
                    t0s.append(g["t0"])
                    for j, (s, e, f) in enumerate(bs):
                        fs[fam].append(f)
                        if e < T: on_l.append(e - s)
                        if j + 1 < len(bs): off_l.append(bs[j + 1][0] - e)
                    duty.append(float((g["schedule"][cell][g["t0"]:] != 1).mean()))
                    for ma in MEAN_ARRIVALS:
                        gm = irregular(ds, cell, r, fam, "multi", mean_arrival=ma)
                        cs = [e["cell"] for e in gm["events"]]
                        nn.setdefault(ma, []).append(len(cs))
                    if len(set(cs)) != len(cs) or len(cs) > MAX_NODES or cs[0] != cell:
                        chk(f"multi 節點 {ds}/{cell}/{r}", False)
    chk(f"t0 ∈ [{T0_LO},{T0_HI}]", min(t0s) >= T0_LO and max(t0s) <= T0_HI)
    chk(f"ON ≥ {MIN_ON}（未截斷段）", min(on_l) >= MIN_ON)
    chk(f"OFF ≥ {MIN_OFF}", min(off_l) >= MIN_OFF)
    chk("down 倍數 ∈ [0.6,0.9]", 0.6 <= min(fs["down"]) and max(fs["down"]) <= 0.9)
    chk("up 倍數 ∈ [1.2,1.5]", 1.2 <= min(fs["up"]) and max(fs["up"]) <= 1.5)
    rep = {"episodes_single": len(t0s), "mean_on_s": float(np.mean(on_l)), "mean_off_s": float(np.mean(off_l)),
           "mean_t0": float(np.mean(t0s)), "duty_after_t0_mean": float(np.mean(duty)),
           "duty_after_t0_range": [float(np.min(duty)), float(np.max(duty))],
           "multi_nodes_hist": {ma: {k: v.count(k) for k in range(1, MAX_NODES + 1)} for ma, v in nn.items()}}
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    print("SELFTEST", "OK" if ok else "FAILED")
    return ok


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--show", nargs=4, metavar=("SEED", "CELL", "R", "FAMILY"))
    ap.add_argument("--mode", default="single")
    ap.add_argument("--mean-arrival", type=int, default=MEAN_ARRIVAL)
    a = ap.parse_args()
    if a.show:
        g = irregular(int(a.show[0]), int(a.show[1]), int(a.show[2]), a.show[3], a.mode, mean_arrival=a.mean_arrival)
        for e in g["events"]:
            print(f"cell {e['cell']} compromised at {e['compromised_at']} s")
            for s, e2, f in e["bursts"]:
                print(f"   ON {s:3d}–{e2 - 1:3d} s ({e2 - s:2d} s)  ×{f:.3f}")
    else:
        sys.exit(0 if selftest() else 1)
