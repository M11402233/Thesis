#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""jcriteria.py — E30 判準 J1–J4、J7 之計算（docs/thesis/E30_coevolution_spec.md §3、§4、§6；2026-11-22）。

只讀 psro.py 之 state.json（--payoff-split train 產生者），不重新模擬、不訓練。
實作範圍（誠實揭露）：
  已實作：J1（含 §4 行為特徵距離之 d／d_max／d_min 三種）、J2、J3、J4 之 gain_atk 曲線、J7。
  未實作：J5（未知攻擊／E29 攻擊集：須以 σ_D^(k) 另行重放）、J6（基線前緣：須 FRR 掃描）、
          §5 探索不足檢查（須另訓練 600k 步／另 2 seed）。輸出之 `not_implemented` 欄位明列；不得把缺項當成「未成立」。

資料分離（§0a）：
  選擇側（train split；`payoff`）：J1 之 gain_atk（history）、C_strict 誘導率比較、§4 行為特徵。
  評估側（test split；`payoff_test`）：J2、J3、J7。程式中任何「選擇」都不讀 payoff_test。
符號：k = 輪數；A_k、D_k 為第 k 輪新增之最佳回應；σ^(k) 為第 k 輪結束時之混合策略。
  SD[k]、SA[k] = σ_D^(k)、σ_A^(k)（k = 0 為 Round 0 之解）；A_k 為對 SD[k−1] 訓練。
  池：n0 = 初始攻擊者數（名稱以 "A0" 開頭者）；第 k 輪時之既有攻擊者 = A[:n0 + k − 1]，偵測端池 = D[:k]。
混合策略之量 = Σ_d σ[d]·（純策略之比率）（以機率加權之比率平均；計數未重新加權，與 psro.py 之 u_det 作法一致）。

用法：
  python3 jcriteria.py --root <…/psro_e30> --out <dir>     # 讀 <root>/<level>/t<seed>/state.json
  python3 jcriteria.py --selftest
"""
import argparse
import glob
import json
import os
import sys

EPS_A, DELTA, DELTA_REC = 0.01, 0.25, 0.05        # E30 §6 凍結值
RANGE_FLOOR = 0.05                                 # §4：正規化範圍下限
FEATS = ("m", "g", "p", "L", "v")
NOT_IMPL = ["J5（未知攻擊：須以 σ_D^(k) 重放 E29 攻擊集）", "J6（基線前緣：須 FRR 掃描）",
            "§5 探索不足檢查（gain_atk ≤ ε_A 之輪須另訓練）"]


def _g(x, *k):
    for i in k:
        if x is None:
            return None
        x = x.get(i) if isinstance(x, dict) else None
    return x


def mix(P, dnames, sig, aname, key):
    """σ 對純策略 aname 之混合量；任一被加權項缺值（None）→ None"""
    tot = 0.0
    for d, w in zip(dnames, sig):
        if w == 0:
            continue
        v = _g(P, f"{d}|{aname}", key)
        if v is None:
            return None
        tot += w * v
    return tot


def mix_atk(P, dname_or_mix, anames, sa, key, sig_d=None):
    """σ_D 對攻擊者混合 σ_A 之量（用於 J3 基準）"""
    tot = 0.0
    for a, w in zip(anames, sa):
        if w == 0:
            continue
        v = mix(P, dname_or_mix, sig_d, a, key)
        if v is None:
            return None
        tot += w * v
    return tot


def _sigmas(st):
    h = st["history"]
    if not h:
        return [], []
    SD = [h[0]["sigma_prev"]["D"]] + [x["sigma_new"]["D"] for x in h]
    SA = [h[0]["sigma_prev"]["A"]] + [x["sigma_new"]["A"] for x in h]
    return SD, SA


def _dist(P, d, X, Y, norm):
    """同一偵測端 d 下 X、Y 之正規化 L∞ 距離；norm[feat] = 範圍（已套下限）"""
    bx, by = _g(P, f"{d}|{X}", "behaviour"), _g(P, f"{d}|{Y}", "behaviour")
    if bx is None or by is None:
        return None
    return max(abs(bx[f] - by[f]) / norm[f] for f in FEATS)


def analyze(st):
    n0 = sum(1 for a in st["A"] if a["name"].startswith("A0"))
    Dn = [d["name"] for d in st["D"]]
    An = [a["name"] for a in st["A"]]
    Ptr, Pte = st.get("payoff", {}), st.get("payoff_test", {})
    if st.get("payoff_split") != "train" or not Pte:
        raise SystemExit("✗ state 非 --payoff-split train（缺 payoff_test）；J 判準只對 E30 之 state 有定義")
    SD, SA = _sigmas(st)
    rounds = len(st["history"])
    out = {"n0": n0, "rounds": rounds, "stop": st.get("stop"), "eps_A": EPS_A, "delta": DELTA, "delta_rec": DELTA_REC,
           "not_implemented": NOT_IMPL, "per_round": []}
    for k in range(1, rounds + 1):
        h = st["history"][k - 1]
        Ak = An[n0 + k - 1]
        old = An[:n0 + k - 1]                         # 第 k 輪時之既有攻擊者
        dpool = Dn[:k]                                # D_0..D_{k-1}
        r = {"k": k, "A_k": Ak, "gain_atk": h["gain_atk"], "gain_det": h["gain_det"], "nashconv": h["nashconv"]}
        # ---- J1（選擇側：train）----
        lure_new = mix(Ptr, dpool, SD[k - 1], Ak, "lure_rate_C_strict")
        lure_old = [mix(Ptr, dpool, SD[k - 1], y, "lure_rate_C_strict") for y in old]
        eff = (h["gain_atk"] > EPS_A) and lure_new is not None and all(v is not None for v in lure_old) \
            and lure_new > max(lure_old)
        feats_ok = all(_g(Ptr, f"{d}|{x}", "behaviour") is not None for d in dpool for x in old + [Ak])
        j1 = {"effective": bool(eff), "gain_atk_gt_eps": h["gain_atk"] > EPS_A, "lure_new": lure_new, "lure_old_best": max(
            [v for v in lure_old if v is not None], default=None)}
        if not feats_ok:
            j1.update({"new": None, "note": "state 缺 behaviour（舊版 psro.py 之 state）或某偵測端下攻擊者無被攻陷窗；J1 之「新」無法計算"})
        else:
            # 各偵測端 d 下之特徵範圍（A_0 與當時池，含 A_k）
            dd = {}
            for Y in old:
                per_d = []
                for d in dpool:
                    norm = {f: max(RANGE_FLOOR, max(_g(Ptr, f"{d}|{x}", "behaviour")[f] for x in old + [Ak]) -
                                   min(_g(Ptr, f"{d}|{x}", "behaviour")[f] for x in old + [Ak])) for f in FEATS}
                    per_d.append(_dist(Ptr, d, Ak, Y, norm))
                dd[Y] = {"mean": sum(per_d) / len(per_d), "max": max(per_d), "min": min(per_d), "per_d": per_d}
            new_main = all(v["mean"] > DELTA for v in dd.values())
            new_max = all(v["max"] > DELTA for v in dd.values())
            new_min = all(v["min"] > DELTA for v in dd.values())
            j1.update({"new": new_main, "new_dmax": new_max, "new_dmin": new_min, "dist": dd,
                       "three_agree": new_main == new_max == new_min})
            j1["holds"] = bool(eff and new_main)
        r["J1"] = j1
        # ---- J2（評估側：test）----
        row = {}
        for key in ("TPR_nontrusted", "TPR_rejected"):
            a = _g(Pte, f"{Dn[k]}|{Ak}", key)
            b = mix(Pte, Dn[:k], SD[k - 1], Ak, key)
            row[key] = {"D_k": a, "sigma_prev": b, "gain": None if a is None or b is None else a - b}
        g = row["TPR_nontrusted"]["gain"]
        r["J2"] = {**row, "holds": None if g is None else bool(g >= DELTA_REC)}
        # ---- J3（評估側）----
        base = None
        if old:
            base = mix_atk(Pte, Dn[:k], old, SA[k - 1], "TPR_nontrusted", sig_d=SD[k - 1])
        rk, curve = None, []
        for rr in range(1, rounds - (k - 1) + 1):
            idx = k - 1 + rr
            v = mix(Pte, Dn[:idx + 1], SD[idx], Ak, "TPR_nontrusted")
            curve.append(v)
            if rk is None and v is not None and base is not None and v >= base:
                rk = rr
        r["J3"] = {"baseline_TPR_nt": base, "curve": curve, "recovery_rounds": rk,
                   "censored": rk is None, "available_rounds": rounds - (k - 1)}
        # ---- J7（評估側）----
        j7 = []
        for Y in old:
            a = mix(Pte, Dn[:k + 1], SD[k], Y, "TPR_nontrusted")
            b = mix(Pte, Dn[:k], SD[k - 1], Y, "TPR_nontrusted")
            dlt = None if a is None or b is None else a - b
            j7.append({"Y": Y, "delta_old": dlt, "forgot": None if dlt is None else bool(dlt < -DELTA_REC)})
        def _mixc(sig, dn, key):
            vs = [mix(Pte, dn, sig, y, key) for y in old]
            return None if any(v is None for v in vs) else sum(vs) / len(vs)
        r["J7"] = {"pairs": j7, "n_forgot": sum(1 for x in j7 if x["forgot"]),
                   "worst": min([x["delta_old"] for x in j7 if x["delta_old"] is not None], default=None),
                   "clean_FRR_delta": _delta(_mixc(SD[k], Dn[:k + 1], "clean_false_reject"), _mixc(SD[k - 1], Dn[:k], "clean_false_reject")),
                   "clean_nontrusted_delta": _delta(_mixc(SD[k], Dn[:k + 1], "clean_nontrusted"), _mixc(SD[k - 1], Dn[:k], "clean_nontrusted"))}
        out["per_round"].append(r)
    # J4：gain_atk 曲線與 J1 成立之輪數
    out["J4"] = {"gain_atk_curve": [x["gain_atk"] for x in out["per_round"]],
                 "J1_rounds": [x["k"] for x in out["per_round"] if _g(x, "J1", "holds")],
                 "rounds_gain_le_eps": [x["k"] for x in out["per_round"] if x["gain_atk"] <= EPS_A],
                 "note": "gain_atk ≤ ε_A 之輪須做 §5 探索不足檢查（未實作）；在此之前不得解讀為「找不到攻擊」"}
    return out


def _delta(a, b):
    return None if a is None or b is None else a - b


def aggregate(results):
    """results = {(level, seed): analyze(...)}；每項報「幾組成立」（§3：3/3 成立、2/3 多數情形成立）"""
    agg = {}
    for lv in sorted({l for l, _ in results}):
        runs = {s: v for (l, s), v in results.items() if l == lv}
        maxk = max(v["rounds"] for v in runs.values())
        rows = []
        for k in range(1, maxk + 1):
            def cnt(f):
                vals = [f(v["per_round"][k - 1]) for v in runs.values() if v["rounds"] >= k]
                return {"holds": sum(1 for x in vals if x is True), "n": sum(1 for x in vals if x is not None), "groups": len(vals)}
            rows.append({"k": k, "J1": cnt(lambda x: x["J1"].get("holds")), "J2": cnt(lambda x: x["J2"]["holds"]),
                         "J3_recovered": cnt(lambda x: None if x["J3"]["baseline_TPR_nt"] is None else (not x["J3"]["censored"])),
                         "J7_no_forgetting": cnt(lambda x: x["J7"]["n_forgot"] == 0)})
        agg[lv] = {"n_runs": len(runs), "rounds": rows}
    return agg


def _selftest():
    mk = lambda **kw: dict(kw)
    D = [{"name": f"D{i}"} for i in range(3)]
    A = [{"name": "A0x"}, {"name": "A1"}, {"name": "A2"}]
    tpr = {"D0": {"A0x": .2, "A1": .1, "A2": .1}, "D1": {"A0x": .3, "A1": .6, "A2": .2}, "D2": {"A0x": .4, "A1": .1, "A2": .7}}
    lure = {"A0x": .3, "A1": .3, "A2": .6}
    bh = {"A0x": dict(m=-.4, g=.4, p=1.0, L=100.0, v=0.0), "A1": dict(m=-.4, g=.4, p=1.0, L=100.0, v=0.0),
          "A2": dict(m=.2, g=.2, p=.5, L=20.0, v=.1)}
    Pte, Ptr = {}, {}
    for d in tpr:
        for a in tpr[d]:
            Pte[f"{d}|{a}"] = {"TPR_nontrusted": tpr[d][a], "TPR_rejected": tpr[d][a] / 2, "clean_false_reject": .01, "clean_nontrusted": .1}
            Ptr[f"{d}|{a}"] = {"lure_rate_C_strict": lure[a], "behaviour": bh[a]}
    st = {"payoff_split": "train", "D": D, "A": A, "payoff": Ptr, "payoff_test": Pte, "stop": "selftest",
          "history": [{"round": 1, "gain_atk": .05, "gain_det": .1, "nashconv": .2,
                       "sigma_prev": {"D": [1.0], "A": [1.0]}, "sigma_new": {"D": [.5, .5], "A": [.5, .5]}},
                      {"round": 2, "gain_atk": .05, "gain_det": .1, "nashconv": .1,
                       "sigma_prev": {"D": [.5, .5], "A": [.5, .5]}, "sigma_new": {"D": [.2, .3, .5], "A": [.2, .3, .5]}}]}
    o = analyze(st); r1, r2 = o["per_round"]
    ap = lambda a, b: a is not None and abs(a - b) < 1e-12
    chk = [
        ("J2 k=1 gain .5", ap(r1["J2"]["TPR_nontrusted"]["gain"], .5) and r1["J2"]["holds"] is True),
        ("J2 k=2 gain .55", ap(r2["J2"]["TPR_nontrusted"]["gain"], .55)),
        ("J3 k=1 baseline .2, r=1", ap(r1["J3"]["baseline_TPR_nt"], .2) and r1["J3"]["recovery_rounds"] == 1),
        ("J3 k=2 baseline .3, r=1", ap(r2["J3"]["baseline_TPR_nt"], .3) and r2["J3"]["recovery_rounds"] == 1 and ap(r2["J3"]["curve"][0], .43)),
        ("J3 k=1 curve 2 pts (.35, ?)", len(r1["J3"]["curve"]) == 2 and ap(r1["J3"]["curve"][0], .35)),
        ("J7 k=1 no forgetting, Δ=+.05", r1["J7"]["n_forgot"] == 0 and ap(r1["J7"]["pairs"][0]["delta_old"], .05)),
        ("J7 k=2 forgot A1 Δ=-.10", r2["J7"]["n_forgot"] == 1 and ap(r2["J7"]["worst"], -.10)),
        ("J1 k=1 not new (identical behaviour)", r1["J1"]["new"] is False and r1["J1"]["holds"] is False),
        ("J1 k=2 new+effective", r2["J1"]["new"] is True and r2["J1"]["holds"] is True and ap(r2["J1"]["lure_new"], .6)),
        ("J1 k=2 three-way agree", r2["J1"]["three_agree"] is True),
        ("J4 curve/rounds", o["J4"]["J1_rounds"] == [2] and o["J4"]["rounds_gain_le_eps"] == []),
    ]
    # 負向：舊版 state（無 behaviour）→ J1「新」為 None，不得當成 False
    st2 = json.loads(json.dumps(st))
    for v in st2["payoff"].values(): v.pop("behaviour")
    o2 = analyze(st2); chk.append(("無 behaviour → new=None", o2["per_round"][1]["J1"]["new"] is None))
    # 負向：非 train state 須拒絕
    st3 = dict(st, payoff_split="test")
    try:
        analyze(st3); chk.append(("非 train state 須拒絕", False))
    except SystemExit:
        chk.append(("非 train state 須拒絕", True))
    bad = [n for n, ok in chk if not ok]
    for n, ok in chk: print(("✓ " if ok else "✗ ") + n)
    print("selftest", "通過" if not bad else f"失敗 {bad}")
    return 0 if not bad else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root"); ap.add_argument("--out"); ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(_selftest())
    if not (a.root and a.out):
        raise SystemExit("須 --root 與 --out")
    res = {}
    for f in sorted(glob.glob(os.path.join(a.root, "*", "t*", "state.json"))):
        lv, t = f.split(os.sep)[-3], f.split(os.sep)[-2]
        res[(lv, t)] = analyze(json.load(open(f, encoding="utf-8")))
    if not res:
        raise SystemExit(f"✗ 找不到 {a.root}/<level>/t<seed>/state.json")
    os.makedirs(a.out, exist_ok=True)
    json.dump({f"{l}/{t}": v for (l, t), v in res.items()}, open(os.path.join(a.out, "J_per_run.json"), "w"), ensure_ascii=False, indent=1)
    json.dump(aggregate(res), open(os.path.join(a.out, "J_aggregate.json"), "w"), ensure_ascii=False, indent=1)
    print(f"完成：{len(res)} 組 → {a.out}")


if __name__ == "__main__":
    main()
