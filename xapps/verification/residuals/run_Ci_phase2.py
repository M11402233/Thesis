#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_Ci_phase2.py — 第二階段步 1：C_i E0–E8 於新輸入層（規格 docs/thesis/Ci_phase2_spec_v0.md）

輸入：D-30P 各 seed 之 aux 目錄（r9 輸出），經 percell_source：
  (A) 主：enb_lists → 每窗各 cell 之 RRC 連線名單；cell 1（LTE 錨點）名單為參照集合
  (B) 對照：traffic_lists → 每窗各 cell 窗內有流量之 UE（ΔnTx > 0）；只判灌水（名單外 IMSI），不判虛減
規則：zt_kpm_xapp.verify_ci_ref（set＝主；card＝對照）＋ fuse（L_C → R1_CI_VETO／R1_CI_PENDING）
攻擊者：控制一個 mmWave cell 之名單（預設 cell 2）；錨點不可控制。E2a 全域壓制保留為與第一階段對照。

【內建檢查】（任一不符即停止、不寫結果）
  K1 percell_source.check(aux) PASS（X1–X3）
  K2 每 seed 窗 0–299 全在（enb 與 traffic 名單）
  K3 判定經 verify_ci_ref／fuse；獨立重算（集合相等／基數相等）逐窗相同
  K4 偽造 IMSI 不與真 IMSI 重疊（真 IMSI < 9000）
用法：python3 run_Ci_phase2.py --aux "<…/D30P_ues30_t300_seed42??_aux>" --out <dir> [--tag diag]
"""
import os, sys, glob, json, argparse, collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("ZT_DATASET", "d30")
import zt_kpm_xapp as X
import percell_source as PS

FAKE0 = 9001
LTE = 1
NET_CASES = [(2, 2), (3, 3), (1, 1), (4, 4), (2, 1), (3, 2), (1, 2), (2, 3), (1, 0), (0, 1)]
DURATIONS = [1, 2, 3, 5]
W = 300


def U(cells):
    u = set()
    for c, s in cells.items():
        if c != LTE:
            u |= s
    return u


def verdict(cells, run, mode):
    """cells 含 cell 1（錨點）；回傳 (violated, run, rule_id)"""
    mm = {c: s for c, s in cells.items() if c != LTE}
    ref = cells.get(LTE, set())
    ci, run, _ = X.verify_ci_ref(mm, ref, run, mode)
    u = U(cells)
    ind = (len(u) != len(ref)) if mode == "card" else (u != ref)                  # K3
    if (ci == "violated") != ind:
        raise SystemExit("✗ K3：verify_ci_ref 與獨立重算不一致")
    rid = X.fuse(ci, run, "normal", "normal", "normal")[1] if ci == "violated" else None
    return ci == "violated", run, rid


def judge(seq, mode):
    out, run = [], 0
    for cells in seq:
        v, run, rid = verdict(cells, run, mode)
        out.append((v, rid))
    return out


def fab(cells, k, a):
    c = {x: set(s) for x, s in cells.items()}
    c.setdefault(a, set()).update(range(FAKE0, FAKE0 + k))
    return c


def drop_own(cells, k, a):
    """攻擊者自其名單移除編號最小之 k 個 UE；不足 k 個 → None"""
    own = sorted(i for i in cells.get(a, set()) if i < 9000)
    if len(own) < k:
        return None
    c = {x: set(s) for x, s in cells.items()}
    c[a] = c[a] - set(own[:k])
    return c


def drop_global(cells, k):
    """第一階段之全域壓制：自所有 mmWave cell 移除 mmWave 聯集中編號最小之 k 個 UE（錨點不動）"""
    real = sorted(i for i in U(cells) if i < 9000)[:k]
    if len(real) < k:
        return None
    return {x: (s if x == LTE else s - set(real)) for x, s in cells.items()}


def replace(cells, add, rem, a):
    c = drop_own(cells, rem, a) if rem else {x: set(s) for x, s in cells.items()}
    return None if c is None else fab(c, add, a)


def experiments(data, mode, a, mm_cells):
    seeds = sorted(data); R = {}
    mid = {s: len(data[s]) // 2 for s in seeds}
    late = {s: list(range(mid[s], len(data[s]))) for s in seeds}
    allw = {s: list(range(len(data[s]))) for s in seeds}

    def per_window(tf, idxs):
        det = tot = skip = 0; ps = {}
        for s in seeds:
            d = t = 0
            for i in idxs[s]:
                new = tf(data[s][i])
                if new is None:
                    skip += 1; continue
                t += 1; d += int(verdict(new, 0, mode)[0])
            det += d; tot += t; ps[s] = d / t if t else None
        return {"detected": det, "total": tot, "skipped": skip, "rate": det / tot if tot else None, "per_seed": ps}

    clean = {s: judge(data[s], mode) for s in seeds}
    R["E0"] = {"windows": sum(len(data[s]) for s in seeds),
               "violations": sum(v for s in seeds for v, _ in clean[s]),
               "clean_rejected": sum(r == "R1_CI_VETO" for s in seeds for _, r in clean[s]),
               "n_anchor_dist": dict(collections.Counter(len(c.get(LTE, ())) for s in seeds for c in data[s])),
               "n_mm_union_dist": dict(collections.Counter(len(U(c)) for s in seeds for c in data[s])),
               "missing_from_mm_dist": dict(collections.Counter(len(c.get(LTE, set()) - U(c)) for s in seeds for c in data[s])),
               "extra_in_mm_dist": dict(collections.Counter(len(U(c) - c.get(LTE, set())) for s in seeds for c in data[s]))}
    R["E1"] = {}
    for k in range(1, 7):
        r = per_window(lambda c, k=k: fab(c, k, a), late); dv, dr = [], []
        for s in seeds:
            j = judge([c if i < mid[s] else fab(c, k, a) for i, c in enumerate(data[s])], mode)
            dv.append(next((i - mid[s] for i in late[s] if j[i][0]), None))
            dr.append(next((i - mid[s] for i in late[s] if j[i][1] == "R1_CI_VETO"), None))
        r["delay_to_violation_s"], r["delay_to_rejected_s"] = dv, dr; R["E1"][k] = r
    R["E2a_global"] = {k: per_window(lambda c, k=k: drop_global(c, k), late) for k in range(1, 5)}
    R["E2b_own"] = {k: per_window(lambda c, k=k: drop_own(c, k, a), late) for k in range(1, 5)}
    R["E3"] = per_window(lambda c: replace(c, 2, 2, a), late)
    R["E4"] = {}
    for name, lo, hi in (("early", 0, 1), ("mid", 1, 2), ("late", 2, 3)):
        R["E4"][name] = per_window(lambda c: fab(c, 3, a), {s: list(range(lo * len(data[s]) // 3, hi * len(data[s]) // 3)) for s in seeds})
    R["E5"] = {"clean": per_window(lambda c: c, allw), "fab+1": per_window(lambda c: fab(c, 1, a), allw),
               "own-1": per_window(lambda c: drop_own(c, 1, a), allw), "global-1": per_window(lambda c: drop_global(c, 1), allw),
               "replace": per_window(lambda c: replace(c, 2, 2, a), allw)}
    R["E6"] = {}
    for D in DURATIONS:
        esc = tot = 0
        for s in seeds:
            starts = [t for t in late[s] if t + D <= len(data[s]) and not clean[s][t - 1][0]]
            for t0 in starts:
                j = judge([fab(c, 1, a) if t0 <= i < t0 + D else c for i, c in enumerate(data[s])], mode)
                esc += int(not any(j[i][1] == "R1_CI_VETO" for i in range(t0, len(data[s]))))
            tot += len(starts)
        R["E6"][D] = {"escaped": esc, "trials": tot, "escape_rate": esc / tot if tot else None, "unit": "(seed, start second)"}
    R["E7"] = []
    for ad, rm in NET_CASES:
        r = per_window(lambda c, x=ad, y=rm: replace(c, x, y, a), allw)
        R["E7"].append({"add": ad, "remove": rm, "net": ad - rm, **{k: r[k] for k in ("detected", "total", "skipped", "rate")}})
    # E8 攻擊面：各 mmWave cell 名單規模、單點抹除（自 cell c 移除 UE i）之條件偵測
    per_cell = collections.defaultdict(list); cd = ct = 0; multi = 0; npairs = 0
    for s in seeds:
        for c0 in data[s]:
            where = collections.Counter(i for c, us in c0.items() if c != LTE for i in us)
            npairs += len(where); multi += sum(v > 1 for v in where.values())
            for c in mm_cells:
                us = c0.get(c, set()); per_cell[c].append(len(us))
                for i in us:
                    new = {x: (y - {i} if x == c else y) for x, y in c0.items()}
                    ct += 1; cd += int(verdict(new, 0, mode)[0])
    R["E8"] = {"window_ue_pairs_mm": npairs, "listed_by_>1_mm_cell": multi,
               "per_cell": {c: {"mean": sum(v) / len(v), "max": max(v), "idle_ratio": sum(x == 0 for x in v) / len(v)} for c, v in sorted(per_cell.items())},
               "single_cell_erasure_conditional_detection": {"detected": cd, "total": ct}}
    return R


def control_B(dataA, dataB, a):
    """(B)：流量名單只判灌水（mmWave 流量名單中出現錨點名單外之 IMSI）；報與 (A) 之差異"""
    seeds = sorted(dataA); R = {"clean_inflation_flags": 0, "windows": 0, "fab+1_detected": 0, "fab+1_total": 0,
                                "B_mm_union_dist": collections.Counter(), "B_minus_A_dist": collections.Counter(),
                                "A_minus_B_dist": collections.Counter()}
    for s in seeds:
        for cA, cB in zip(dataA[s], dataB[s]):
            ref = cA.get(LTE, set()); uB, uA = U(cB), U(cA)
            R["windows"] += 1; R["clean_inflation_flags"] += int(bool(uB - ref))
            R["B_mm_union_dist"][len(uB)] += 1; R["B_minus_A_dist"][len(uB - uA)] += 1; R["A_minus_B_dist"][len(uA - uB)] += 1
            f = fab(cB, 1, a); R["fab+1_total"] += 1; R["fab+1_detected"] += int(bool(U(f) - ref))
    for k in ("B_mm_union_dist", "B_minus_A_dist", "A_minus_B_dist"):
        R[k] = dict(sorted(R[k].items()))
    return R


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--aux", required=True, help="aux 目錄之 glob")
    ap.add_argument("--out", required=True)
    ap.add_argument("--tag", default="d30p")
    ap.add_argument("--attacker", type=int, default=2)
    args = ap.parse_args()
    auxes = sorted(glob.glob(os.path.expanduser(args.aux)))
    if not auxes:
        raise SystemExit(f"找不到 aux：{args.aux}")
    dataA, dataB, k1 = {}, {}, {}
    for aux in auxes:
        s = os.path.basename(aux.rstrip("/")).split("seed")[-1].split("_")[0]
        rep = PS.check(aux); k1[s] = rep
        if not rep["PASS"]:
            raise SystemExit(f"✗ K1：seed {s} 輸入層檢查未通過：{rep}")
        el, tl = PS.enb_lists(aux), PS.traffic_lists(aux)
        if sorted(el) != list(range(W)) or not set(range(W)) <= set(tl):                 # K2
            raise SystemExit(f"✗ K2：seed {s} 窗不完整（enb {len(el)}、traffic {len(tl)}）")
        dataA[s] = [{c: set(u) for c, u in el[k].items()} for k in range(W)]
        dataB[s] = [{c: set(u) for c, u in tl.get(k, {}).items()} for k in range(W)]
        if any(i >= FAKE0 for c in dataA[s] for us in c.values() for i in us):                # K4
            raise SystemExit(f"✗ K4：seed {s} 真 IMSI ≥ {FAKE0}")
    mm_cells = sorted({c for s in dataA for w in dataA[s] for c in w if c != LTE})
    print(f"載入 {len(auxes)} seed；mmWave cell {mm_cells}；攻擊者 cell {args.attacker}；L_C = {X.L_C}")
    print("── K1 輸入層檢查 PASS、K2 窗完整、K4 偽造 IMSI 不重疊 ✓")
    out = {"meta": {"spec": "docs/thesis/Ci_phase2_spec_v0.md", "tag": args.tag, "aux": [os.path.basename(a) for a in auxes],
                    "attacker_cell": args.attacker, "L_C": X.L_C, "mm_cells": mm_cells, "K1": k1}}
    for mode in ("set", "card"):
        out[f"A_{mode}"] = experiments(dataA, mode, args.attacker, mm_cells)
    print("── K3 判定經 verify_ci_ref／fuse，與獨立重算逐窗相同 ✓")
    out["B_control"] = control_B(dataA, dataB, args.attacker)
    os.makedirs(args.out, exist_ok=True)
    p = os.path.join(args.out, f"Ci_phase2_{args.tag}.json")
    json.dump(out, open(p, "w"), indent=1, ensure_ascii=False, default=str)
    f_ = lambda r: f"{r['detected']}/{r['total']}"
    for mode in ("set", "card"):
        R = out[f"A_{mode}"]
        print(f"\n[(A) {mode}] E0 {R['E0']['windows']} 窗：違反 {R['E0']['violations']}、rejected {R['E0']['clean_rejected']}；"
              f"|錨點| {R['E0']['n_anchor_dist']}；錨點有而 mmWave 無 {R['E0']['missing_from_mm_dist']}")
        print("  E1 " + "；".join(f"+{k} {f_(v)}" for k, v in R["E1"].items()))
        print("  E2a 全域 " + "；".join(f"−{k} {f_(v)}" for k, v in R["E2a_global"].items()))
        print("  E2b 自身 " + "；".join(f"−{k} {f_(v)}（略 {v['skipped']}）" for k, v in R["E2b_own"].items()))
        print(f"  E3 替換 {f_(R['E3'])}；E6 " + "；".join(f"D={D} 未升級 {v['escaped']}/{v['trials']}" for D, v in R["E6"].items()))
        print(f"  E8 單點抹除條件偵測 {R['E8']['single_cell_erasure_conditional_detection']}；多 cell 列名 {R['E8']['listed_by_>1_mm_cell']}/{R['E8']['window_ue_pairs_mm']}")
    B = out["B_control"]
    print(f"\n[(B) 對照] 乾淨灌水旗標 {B['clean_inflation_flags']}/{B['windows']}；+1 灌水偵測 {B['fab+1_detected']}/{B['fab+1_total']}；"
          f"|B 聯集| {B['B_mm_union_dist']}")
    print(f"\n寫入 {p}")


if __name__ == "__main__":
    main()
