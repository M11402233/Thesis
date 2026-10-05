#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_Pi_experiments.py — 第四殘差 P_i：吞吐量—資源內部一致性（第四章新增節）

【定位】
C_i／S_i／H_i 屬「外部佐證」——證據來源位於受測節點之外。
P_i 屬「內部一致性」——檢查單一節點之上報在物理上是否自洽。二者為不同類別，
論文中須分類陳述，不可將 P_i 併入「不依賴被懷疑節點配合」之主張。

【兩個子檢查（與 H_i 之 D1／D2 對稱）】
  P_i-C 一致性（統計）
      回報位元組 B 與「回報符號數 × (a·MCS + b)」之相對殘差，以 robust z 判定
      r = (B − B̂) / B̂ ；z = |r − med(r_clean)| / (1.4826·MAD(r_clean))
      P_i-C violated ⟺ z > τ_P
  P_i-B 容量上界（斷言）
      回報符號數 ≤ 載波容量、回報 MCS ≤ MCS 上限；超過即物理上不可能

【可用性】
僅於「成員穩定窗」判定（該 cell 前後窗之 IMSI 集合相同且差分皆有效）。
窗內換手會使位元組之 cell 歸屬錯位，其餘窗判為證據不可得。

【校準（兩種，皆報）】
  deploy  部署內時間切分：前半乾淨窗校準、後半評估——對應 P3 乾淨啟動（主結果）
  loso    跨部署：以其他 seed 校準、套用於受測 seed——換場域直接套用之悲觀情境

【攻擊】
  naive       只灌高／壓低回報吞吐量 κ 倍，符號數與 MCS 不變（B2 之天真型）
  consistent  白箱：同步提高回報符號數與 MCS，使 B̂ 追上灌高後之 B（P_i-C 必然通過）
              → 量化其物理天花板：該窗可無聲灌高之最大倍數 κ_max

【資料】需 *_aux 目錄（RxPacketTrace.txt + DlE2RlcStats.txt）。
  D-C：batchFinal_seeds_VERIFY/_logs_*/seed42??_aux（已有）
  D-SH：須以保留 aux 之方式重跑後方可整合進 xApp

跑法：
  python3 run_Pi_experiments.py --aux "$HOME/oran-zt-kpm-verification/data/batchFinal_seeds_VERIFY/_logs_*/seed42??_aux"
"""
import os
import json
import glob
import gzip
import argparse
import collections
import numpy as np

LTE_CELL = 1
TAU_P = 4.0
MIN_CAL = 15                     # 校準所需之最少穩定窗數
KAPPA_INF = [1.2, 1.5, 2.0, 2.5, 3.0, 5.0]
KAPPA_DEF = [0.8, 0.5, 0.2]
OUT_DIR = os.path.expanduser("~/oran-zt-kpm-verification/data/results")


# ==========================================================================
# 資料載入
# ==========================================================================
def open_trace(path):
    """Read a plain trace, or its .gz counterpart if the plain file is absent."""
    path = os.fspath(path)
    if not os.path.isfile(path) and os.path.isfile(path + ".gz"):
        path += ".gz"
    opener = gzip.open if path.endswith(".gz") else open
    return opener(path, "rt", encoding="utf-8")

def load_phy(path):
    """回傳 per-(cell,win) 聚合，以及估計載波容量所需之 slot 結構"""
    agg = collections.defaultdict(lambda: {"sym": 0, "tb": 0, "mcs_w": 0.0, "n": 0})
    slots_per_sec = collections.defaultdict(set)
    max_sym, max_mcs = 0, 0
    with open_trace(path) as fh:
        header = fh.readline().split()
        col = {n: i for i, n in enumerate(header)}
        for line in fh:
            p = line.split()
            if len(p) < len(header) or p[col["DL/UL"]] != "DL":
                continue
            try:
                t = float(p[col["time"]]); cid = int(p[col["cellId"]])
                sym = int(p[col["symbol#"]]); tb = int(p[col["tbSize"]])
                mcs = int(p[col["mcs"]]); bad = int(p[col["corrupt"]])
                fr = int(p[col["frame"]]); sf = int(p[col["subF"]]); sl = int(p[col["slot"]])
            except (ValueError, KeyError):
                continue
            w = int(t)
            k = agg[(cid, w)]
            k["n"] += 1; k["sym"] += sym; k["mcs_w"] += mcs * sym
            if not bad:
                k["tb"] += tb
            slots_per_sec[(cid, w)].add((fr, sf, sl))
            max_sym = max(max_sym, sym); max_mcs = max(max_mcs, mcs)
    rows = {}
    for key, v in agg.items():
        if v["sym"] > 0:
            rows[key] = {"sym": v["sym"], "tb": v["tb"], "mcs": v["mcs_w"] / v["sym"],
                         "n": v["n"]}
    # 載波容量代理：每秒可用 slot 數之高分位 × 單次配置之最大符號數
    sps = [len(s) for s in slots_per_sec.values()]
    slot_cap = float(np.percentile(sps, 99)) if sps else 0.0
    return rows, {"slots_per_sec_p99": slot_cap, "max_sym_per_tx": max_sym,
                  "sym_cap": slot_cap * max_sym, "mcs_max_observed": max_mcs}


def load_rlc(path):
    series = collections.defaultdict(dict)
    member = collections.defaultdict(set)
    with open_trace(path) as fh:
        fh.readline()
        for line in fh:
            p = line.split("\t")
            if len(p) < 11:
                continue
            try:
                w = int(float(p[0])); c = int(p[2]); i = int(p[3]); rx = float(p[9])
            except ValueError:
                continue
            series[(c, i)][w] = rx
            member[(c, w)].add(i)
    diffs = collections.defaultdict(float)
    contrib = collections.defaultdict(set)
    for (c, i), wm in series.items():
        ws = sorted(wm)
        for a, b in zip(ws, ws[1:]):
            if b - a != 1:
                continue
            d = wm[b] - wm[a]
            if d < 0:
                continue
            diffs[(c, b)] += d; contrib[(c, b)].add(i)
    return diffs, member, contrib


def load_seed(aux):
    phy, cap = load_phy(os.path.join(aux, "RxPacketTrace.txt"))
    rlc, member, contrib = load_rlc(os.path.join(aux, "DlE2RlcStats.txt"))
    rows = []
    for (c, w), v in phy.items():
        if c == LTE_CELL or v["n"] < 5:
            continue
        b = rlc.get((c, w))
        if b is None or b <= 0:
            continue
        prev, cur = member.get((c, w - 1), set()), member.get((c, w), set())
        stable = (prev == cur) and len(cur) > 0 and contrib.get((c, w), set()) == cur
        rows.append({"cell": c, "win": w, "sym": float(v["sym"]), "mcs": v["mcs"],
                     "B": float(b), "stable": stable})
    return rows, cap


# ==========================================================================
# 模型
# ==========================================================================
def fit(rows):
    X = np.array([[r["sym"] * r["mcs"], r["sym"]] for r in rows])
    y = np.array([r["B"] for r in rows])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    return coef


def predict(coef, sym, mcs):
    return sym * (coef[0] * mcs + coef[1])


def rel_resid(coef, rows, B=None, sym=None, mcs=None):
    out = []
    for k, r in enumerate(rows):
        b = r["B"] if B is None else B[k]
        s = r["sym"] if sym is None else sym[k]
        m = r["mcs"] if mcs is None else mcs[k]
        p = predict(coef, s, m)
        out.append((b - p) / p if p > 0 else np.nan)
    return np.array(out)


def calib_stats(coef, rows):
    r = rel_resid(coef, rows); r = r[np.isfinite(r)]
    med = float(np.median(r))
    sig = 1.4826 * float(np.median(np.abs(r - med)))
    return med, max(sig, 1e-6)


def zscore(r, med, sig):
    return np.abs(r - med) / sig


# ==========================================================================
def evaluate(train, test, cap, mcs_max):
    """於 test（穩定窗）上評估；train 用於校準"""
    coef = fit(train)
    med, sig = calib_stats(coef, train)
    out = {"coef": coef.tolist(), "median_r": med, "sigma_r": sig, "n_test": len(test)}

    # 乾淨誤報
    z0 = zscore(rel_resid(coef, test), med, sig)
    out["clean_fpr"] = float(np.nanmean(z0 > TAU_P))
    # 容量斷言於乾淨資料之誤觸（應為 0）
    out["clean_bound_violation"] = float(np.mean(
        [(r["sym"] > cap["sym_cap"]) or (r["mcs"] > mcs_max) for r in test]))

    # naive：只改 B
    det = {}
    for k in KAPPA_INF + KAPPA_DEF:
        z = zscore(rel_resid(coef, test, B=[k * r["B"] for r in test]), med, sig)
        det[str(k)] = float(np.nanmean(z > TAU_P))
    out["naive_detection"] = det

    # consistent：白箱同步提高 sym 與 MCS，使 P_i-C 通過；計算物理天花板
    kmax = []
    for r in test:
        best = predict(coef, cap["sym_cap"], mcs_max)   # 灌滿兩者上限時之可宣稱位元組
        true_pred = predict(coef, r["sym"], r["mcs"])
        if true_pred > 0:
            kmax.append(best / true_pred)
    kmax = np.array(kmax)
    out["consistent_kappa_max"] = {
        "median": float(np.median(kmax)), "p10": float(np.percentile(kmax, 10)),
        "p90": float(np.percentile(kmax, 90))}
    # 各 κ 下，consistent 攻擊被容量上界攔下之比例
    out["consistent_bound_catch"] = {str(k): float(np.mean(kmax < k)) for k in KAPPA_INF}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--aux", required=True)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--no-fig", action="store_true")
    args = ap.parse_args()
    out_dir = args.out_dir or OUT_DIR
    os.makedirs(out_dir, exist_ok=True)

    auxes = sorted(glob.glob(os.path.expanduser(args.aux)))
    if len(auxes) < 2:
        raise SystemExit(f"需要至少 2 個 seed（找到 {len(auxes)}）")
    data = {}
    caps = []
    for a in auxes:
        rows, cap = load_seed(a)
        data[os.path.basename(a)] = rows
        caps.append(cap)
    # 容量取全體之最大（保守：寧可高估容量、少誤攔）
    cap = {"sym_cap": max(c["sym_cap"] for c in caps),
           "slots_per_sec_p99": max(c["slots_per_sec_p99"] for c in caps),
           "max_sym_per_tx": max(c["max_sym_per_tx"] for c in caps)}
    # MCS 上限取 MCS 表之上限（28）與實測最大值之較大者——
    # 若只用實測最大值會低估攻擊者之可宣稱空間，使 κ_max 偏向對防禦方有利
    mcs_obs = max(c["mcs_max_observed"] for c in caps)
    mcs_max = max(mcs_obs, 28)
    print("⚠ 容量為實測代理值：若無 cell 曾滿載，將低估真實容量，使 κ_max 偏向對防禦方有利；")
    print("  部署時容量應取自載波組態（numerology），而非實測。\n")
    print(f"載入 {len(data)} seed；容量代理：{cap['slots_per_sec_p99']:.0f} slot/s × "
          f"{cap['max_sym_per_tx']} sym = {cap['sym_cap']:.0f} sym/s；MCS 上限 {mcs_max}\n")

    res = {"tau_P": TAU_P, "capacity": cap, "mcs_max": mcs_max, "mcs_max_observed": mcs_obs,
           "capacity_note": ("empirical proxy (p99 used slots/s x max symbols/tx); "
                             "underestimates true capacity if no cell is ever fully "
                             "loaded, which makes kappa_max optimistic for the defender"),
           "deploy": {}, "loso": {}}
    for s, rows in data.items():
        st = sorted([r for r in rows if r["stable"]], key=lambda r: r["win"])
        cov = len(st) / len(rows) if rows else 0
        # deploy：前半校準、後半評估
        half = len(st) // 2
        if half >= MIN_CAL and len(st) - half >= 10:
            e = evaluate(st[:half], st[half:], cap, mcs_max)
            e["coverage"] = cov
            res["deploy"][s] = e
        # loso：其他 seed 之穩定窗校準
        train = [r for o, rr in data.items() if o != s for r in rr if r["stable"]]
        if len(train) >= MIN_CAL and len(st) >= 10:
            e = evaluate(train, st, cap, mcs_max)
            e["coverage"] = cov
            res["loso"][s] = e

    def pooled(mode, key, sub=None):
        vals = []
        for e in res[mode].values():
            v = e[key] if sub is None else e[key].get(sub)
            if v is not None and np.isfinite(v):
                vals.append(v)
        return (float(np.mean(vals)), float(min(vals)), float(max(vals))) if vals else None

    for mode, label in (("deploy", "部署內校準（主結果）"), ("loso", "跨部署校準（悲觀）")):
        if not res[mode]:
            continue
        print(f"═══ {label}：{len(res[mode])} seed ═══")
        cv = pooled(mode, "coverage"); fp = pooled(mode, "clean_fpr")
        sg = pooled(mode, "sigma_r"); bv = pooled(mode, "clean_bound_violation")
        print(f"  覆蓋率        {cv[0]:.1%}  [{cv[1]:.1%}–{cv[2]:.1%}]")
        print(f"  σ_r（相對）   {sg[0]:.3f}  [{sg[1]:.3f}–{sg[2]:.3f}]")
        print(f"  乾淨誤報率    {fp[0]:.1%}  [{fp[1]:.1%}–{fp[2]:.1%}]   (τ_P={TAU_P})")
        print(f"  容量斷言誤觸  {bv[0]:.1%}   （應為 0；非 0 代表容量估計過低）")
        print("  天真灌水偵測率：")
        for k in KAPPA_INF:
            d = pooled(mode, "naive_detection", str(k))
            print(f"    κ={k:<4} {d[0]:>6.1%}  [{d[1]:.1%}–{d[2]:.1%}]")
        print("  天真壓低偵測率：")
        for k in KAPPA_DEF:
            d = pooled(mode, "naive_detection", str(k))
            print(f"    κ={k:<4} {d[0]:>6.1%}")
        km = [e["consistent_kappa_max"]["median"] for e in res[mode].values()]
        print(f"  白箱同步偽造之物理天花板 κ_max（中位數）：{np.median(km):.2f}×"
              f"  [seed 範圍 {min(km):.2f}–{max(km):.2f}]")
        print("  白箱同步偽造被容量斷言攔下之比例：")
        for k in KAPPA_INF:
            d = pooled(mode, "consistent_bound_catch", str(k))
            print(f"    κ={k:<4} {d[0]:>6.1%}")
        mind = None
        for k in KAPPA_INF:
            if pooled(mode, "naive_detection", str(k))[0] >= 0.5:
                mind = k; break
        print(f"  → 天真灌水之最小可偵測倍數（偵測率 ≥ 50%）：{mind}×\n")

    with open(os.path.join(out_dir, "Pi_experiments.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, ensure_ascii=False, default=float)
    print(f"寫入 {os.path.join(out_dir, 'Pi_experiments.json')}")
    if not args.no_fig:
        draw(res, os.path.join(out_dir, "fig_Pi_detection.png"))


def draw(res, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.6))
    for mode, col, lab in (("deploy", "#2b8a3e", "in-deployment calibration"),
                           ("loso", "#868e96", "cross-deployment calibration")):
        if not res[mode]:
            continue
        m = [np.mean([e["naive_detection"][str(k)] for e in res[mode].values()])
             for k in KAPPA_INF]
        ax1.plot(KAPPA_INF, m, "o-", color=col, lw=2, label=f"naive inflation ({lab})")
        c = [np.mean([e["consistent_bound_catch"][str(k)] for e in res[mode].values()])
             for k in KAPPA_INF]
        ax1.plot(KAPPA_INF, c, "s--", color=col, lw=1.5, alpha=0.8,
                 label=f"white-box consistent, caught by capacity bound ({lab})")
    ax1.set_xlabel("throughput inflation factor κ")
    ax1.set_ylabel("detection rate")
    ax1.set_ylim(-0.03, 1.03); ax1.grid(alpha=0.3); ax1.legend(fontsize=7.5)
    ax1.set_title("P_i: consistency check vs capacity bound", fontsize=10.5)

    km = [v for mode in ("deploy",) for e in res[mode].values()
          for v in [e["consistent_kappa_max"]["median"]]]
    ax2.bar(range(len(km)), sorted(km), color="#e8590c", alpha=0.8)
    ax2.axhline(1, color="#495057", lw=1)
    ax2.set_xlabel("seed (sorted)"); ax2.set_ylabel("κ_max (median over windows)")
    ax2.set_title("white-box headroom: max silent inflation within physical capacity",
                  fontsize=10.5)
    ax2.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    print(f"圖已存: {path}")


if __name__ == "__main__":
    main()
