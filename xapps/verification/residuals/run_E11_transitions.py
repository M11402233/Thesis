#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_E11_transitions.py — E11：狀態轉移與恢復（RQ2 之 2b），規格 v2

規格：docs/thesis/E11_E12_B4_spec.md（v2，2026-10-06；v1 之診斷見 data/results/E11_v1_diagnosis/）。

每個 seed × 受測 mmWave cell × 攻擊類別 × T ∈ {10, 30}：於 [t0, t0+T) 注入，結束後追蹤 60 秒；
與同 seed 之乾淨回放逐窗配對。多窗迴圈：run_E10_D1_policy_ablation.run_policy（uebound、L_H = 1）；
admission = strict（僅 trusted 准入）。D1 採缺報中斷連續計數（v2）。

【內建檢查】
  1. 乾淨回放四 seed 合計 = 1,803／575／766／6（n = 3,150）
  2. 乾淨回放逐筆 = runtime_20261006 之 xApp 註記
  3. 可追溯性（v2）：對乾淨與攻擊回放之**每一筆**註記，以本檔之獨立實作由報告重算 P1 證據、
     依 4.4.0 規則表推得 (決策, rule_id)，須與回放相同；P3：admitted ⇔ trusted；
     注入改動之報告須限於宣告之節點；每筆差異須至少有一項證據或上報存在與否改變。
  任一不符即停止、不寫檔。
"""
import os
import sys
import copy
import json
import argparse
import statistics
import collections
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_E10_D1_policy_ablation as E10
import planB_rt as P
X = E10.X

OUT_DIR = os.path.expanduser("~/oran-zt-kpm-verification/data/results")
RUNTIME_ANN = os.path.join(OUT_DIR, "runtime_20261006", "xapp_trust_annotations_bound_all_uebound_strict.jsonl")
T_LIST = [10, 30]
TRACK = 60
FAKE_IMSI = 9001
DRIFT_RATE = 0.01
STEP_AF = 1.5
LTE = 1
EXPECTED_P3 = {"trusted": 1803, "low-trust": 575, "abstain": 766, "rejected": 6}
KINDS = ["Ci_inflate", "Ci_deflate", "Si_drift", "Si_step", "D1_overtime", "D2_falseassoc"]
PRIMARY = {"Ci_inflate": "C_i", "Ci_deflate": "C_i", "Si_drift": "S_i", "Si_step": "S_i",
           "D1_overtime": "D1", "D2_falseassoc": "D2"}
REPLAY_ONLY = {"D1_overtime", "D2_falseassoc"}
SEV = {"trusted": 0, "abstain": 1, "low-trust": 2, "rejected": 3}


# ======================================================================
# 注入（與 v1 相同）；回傳 (windows, info, 宣告可被改動之 cell 集合)
# ======================================================================
def ue_on(cells, cell):
    return sorted(i for i in cells.get(cell, {}) if i < FAKE_IMSI)


def inject(windows, kind, target, k0, T, mean):
    out = copy.deepcopy(windows)
    info = {}
    ks = range(k0, min(k0 + T, len(out)))
    allowed = {target}
    if kind == "Ci_inflate":
        for k in ks:
            c = out[k][1]
            if target in c:
                c[target][FAKE_IMSI] = float(np.mean(list(c[target].values())))
    elif kind == "Ci_deflate":
        ues = ue_on(out[k0][1], target)
        if not ues:
            return None, {"skip": "受測 cell 於 t0 無 UE"}, allowed
        imsi = ues[0]; info["imsi"] = imsi
        for k in ks:
            c = out[k][1]
            if target in c and imsi in c[target]:
                del c[target][imsi]
                if not c[target]:
                    del c[target]
    elif kind in ("Si_drift", "Si_step"):
        for k in ks:
            c = out[k][1]
            if target in c:
                w = out[k][0]
                for i in c[target]:
                    c[target][i] = (c[target][i] + DRIFT_RATE * (w - out[k0][0]) * mean
                                    if kind == "Si_drift" else c[target][i] * STEP_AF)
    elif kind == "D1_overtime":
        ues = ue_on(out[k0][1], target)
        if not ues:
            return None, {"skip": "受測 cell 於 t0 無 UE"}, allowed
        imsi = ues[0]; info["imsi"] = imsi
        out = E10.inject_overtime(windows, imsi, k0, T)
        allowed = {target, LTE}
    elif kind == "D2_falseassoc":
        ues = ue_on(out[k0][1], target)
        others = sorted(c for c in out[k0][1] if c not in (target, LTE))
        if not ues or not others:
            return None, {"skip": "t0 無 UE 或無其他活躍 mmWave cell"}, allowed
        imsi, B = ues[0], others[0]; info.update(imsi=imsi, to_cell=B)
        allowed = {target, B}
        for k in ks:
            c = out[k][1]
            if target in c and imsi in c[target]:
                v = c[target].pop(imsi)
                if not c[target]:
                    del c[target]
                c.setdefault(B, {})[imsi] = v
    return out, info, allowed


def changed_cells(clean, att):
    s = set()
    for (w1, c1), (w2, c2) in zip(clean, att):
        for c in set(c1) | set(c2):
            if c1.get(c) != c2.get(c):
                s.add(c)
    return s


# ======================================================================
# 獨立實作：由報告重算 P1 證據，依 4.4.0 規則表推得 (決策, rule_id)
# （刻意不呼叫 X.verify_* 與 X.fuse；依論文定義重寫）
# ======================================================================
def trace(windows, anchor, n_known):
    recs = {}
    prev_map, ci_run = {}, 0
    dwell = collections.defaultdict(int)
    last_srv = {}
    for k, (w, cells) in enumerate(windows):
        cur = collections.defaultdict(set)
        for c, ues in cells.items():
            for i in ues:
                cur[i].add(c)
        for i, cs in cur.items():
            dwell[i] = dwell[i] + 1 if cs == {LTE} else 0
            mm = sorted(c for c in cs if c != LTE)
            if mm:
                last_srv[i] = mm[0]
        for i in list(dwell):
            if i not in cur:
                dwell[i] = 0                      # 缺報中斷連續計數
        n_total = len(cur)
        ci_v = n_total != n_known
        ci_run = ci_run + 1 if ci_v else 0
        d2_v = False
        for i, cs in cur.items():
            pm, cm = prev_map.get(i, set()) - {LTE}, cs - {LTE}
            if pm and cm and not (pm & cm) and LTE not in cs:
                d2_v = True
        lev = {}
        for i, run in dwell.items():
            if run > 0 and i in anchor.dwell:
                med, sig = anchor.dwell[i]
                z = abs(run - med) / sig if sig > 0 else 0.0
                lv = 2 if z >= X.TAU_H_REJECT else (1 if z >= X.TAU_H_WARN else 0)
                if lv:
                    lev[i] = lv
        mmw = sorted(c for c in cells if c != LTE)
        for j in mmw:
            peers = [c for c in mmw if c != j]
            if len(peers) < X.MIN_PEER:
                si, z = "unavailable", None
            else:
                tgt = float(np.mean(list(cells[j].values())))
                ref = float(np.median([np.mean(list(cells[c].values())) for c in peers]))
                z = abs(tgt - ref) / anchor.scale
                si = "violated" if z > X.TAU_S else "normal"
            mine = {i: lv for i, lv in lev.items() if last_srv.get(i) == j}
            d1 = {0: "none", 1: "weak", 2: "strong"}[max(mine.values())] if mine else "none"
            # 4.4.0 規則表（依序，先符合者生效）
            if ci_v:
                dec, rid = (("rejected", "R1_CI_VETO") if ci_run >= X.L_C else ("low-trust", "R1_CI_PENDING"))
            elif d2_v:
                dec, rid = "rejected", "R1_D2_VETO"
            elif si == "violated" and d1 == "strong":
                dec, rid = "rejected", "R2_SI_D1_BOUND"      # uebound：D1 證據僅歸屬於本節點
            elif si == "violated":
                dec, rid = "low-trust", "R2_SI_ALONE"
            elif d1 == "strong":
                dec, rid = "low-trust", "R2_D1_STRONG"
            elif d1 == "weak":
                dec, rid = "low-trust", "R2_D1_WEAK"
            elif si == "unavailable":
                dec, rid = "abstain", "R3_ABSTAIN"
            else:
                dec, rid = "trusted", "R0_CLEAN"
            recs[(k, j)] = {"decision": dec, "rule_id": rid, "admitted": dec == "trusted",
                            "ev": {"C_i": ci_v, "ci_run": ci_run, "D2": d2_v, "S_i": si,
                                   "S_i_avail": si != "unavailable", "D1": d1}}
        prev_map = cur
    return recs


def check_trace(ann, recs, tag):
    got = {(a["k"], a["node"]): (a["decision"], a["rule_id"]) for a in ann}
    exp = {key: (r["decision"], r["rule_id"]) for key, r in recs.items()}
    if got != exp:
        bad = [(k, got.get(k), exp.get(k)) for k in set(got) | set(exp) if got.get(k) != exp.get(k)]
        raise SystemExit(f"✗ 可追溯性（P1→P2）不符：{tag}；{len(bad)} 筆，例 {sorted(bad, key=str)[:3]}")


# ======================================================================
# 差異分類與恢復指標
# ======================================================================
def classify(kind, cr, ar):
    """cr／ar：乾淨／攻擊之 trace 紀錄（None = 該窗無註記）"""
    out = {}
    if cr is None or ar is None:
        out["上報"] = "節點出現" if cr is None else "節點消失"
        out["成因"] = ["證據可用性"]
        return out
    cd, ad = cr["decision"], ar["decision"]
    if cd == ad:
        out["判定"] = "同狀態但規則改變" if cr["rule_id"] != ar["rule_id"] else None
    elif cd == "trusted":
        out["判定"] = "新增非 trusted"
    elif ad == "trusted":
        out["判定"] = "轉成 trusted"
    else:
        out["判定"] = "非 trusted 間加重" if SEV[ad] > SEV[cd] else "非 trusted 間減輕"
    if cr["admitted"] != ar["admitted"]:
        out["准入"] = "准入→不准入" if cr["admitted"] else "不准入→准入"
    ce, ae = cr["ev"], ar["ev"]
    changed = {f for f in ("C_i", "ci_run", "D2", "S_i", "D1") if ce[f] != ae[f]}
    causes = []
    fam = {"C_i": {"C_i", "ci_run"}, "S_i": {"S_i"}, "D1": {"D1"}, "D2": {"D2"}}[PRIMARY[kind]]
    if changed & fam:
        causes.append("主殘差")
    if changed - fam - ({"S_i"} if ce["S_i_avail"] != ae["S_i_avail"] else set()):
        causes.append("跨殘差副作用")
    if ce["S_i_avail"] != ae["S_i_avail"]:
        causes.append("證據可用性")
    out["成因"] = causes
    out["_changed"] = sorted(changed)
    return out


def analyse(kind, clean_tr, att_tr, target, k0, T, n_win, B=None):
    kend, ktrack = k0 + T, min(k0 + T + TRACK, n_win)
    dec = lambda tr, k: tr[(k, target)]["decision"] if (k, target) in tr else None
    differs = lambda k: (clean_tr.get((k, target)) or {}).get("decision") != (att_tr.get((k, target)) or {}).get("decision") \
        or ((k, target) in clean_tr) != ((k, target) in att_tr)
    induced = any(differs(k) for k in range(k0, min(kend, n_win)))
    leave = next((k - k0 for k in range(k0, ktrack) if differs(k) and dec(att_tr, k) not in (None, "trusted")), None)
    rej = next((k - k0 for k in range(k0, ktrack) if dec(att_tr, k) == "rejected" and dec(clean_tr, k) != "rejected"), None)
    first_trusted = next((k - kend for k in range(kend, ktrack) if dec(att_tr, k) == "trusted"), None)
    diff_after = [k for k in range(kend, ktrack) if differs(k)]
    back_clean = None if (diff_after and diff_after[-1] == ktrack - 1) else ((diff_after[-1] + 1 - kend) if diff_after else 0)

    def phase(k):
        if k < kend:
            return "開始" if k == k0 else "維持"
        return "還原" if k == kend else "攻擊後"

    tally = collections.Counter()
    unexplained = []
    for k in range(k0, ktrack):
        nodes = {j for (kk, j) in clean_tr if kk == k} | {j for (kk, j) in att_tr if kk == k}
        for j in nodes:
            cr, ar = clean_tr.get((k, j)), att_tr.get((k, j))
            same = cr is not None and ar is not None and cr["decision"] == ar["decision"] and cr["rule_id"] == ar["rule_id"]
            if same:
                continue
            c = classify(kind, cr, ar)
            who = "受測" if j == target else "其他"
            ph = phase(k) if kind == "D2_falseassoc" else ("期間" if k < kend else "攻擊後")
            for face in ("判定", "准入", "上報"):
                if c.get(face):
                    tally[f"{who}|{ph}|{face}|{c[face]}"] += 1
            for cause in c.get("成因", []):
                tally[f"{who}|{ph}|成因|{cause}"] += 1
            if cr is not None and ar is not None and not c.get("_changed") and "證據可用性" not in c["成因"]:
                unexplained.append((k, j, cr, ar))
    trans = {"期間": collections.Counter(), "攻擊後": collections.Counter()}
    prev = dec(att_tr, k0 - 1)
    for k in range(k0, ktrack):
        cur = dec(att_tr, k)
        if cur is not None and prev is not None and cur != prev:
            trans["期間" if k < kend else "攻擊後"][f"{prev}->{cur}|{att_tr[(k, target)]['rule_id']}"] += 1
        if cur is not None:
            prev = cur
    return {"induced": induced, "leave_s": leave, "reject_s": rej,
            "first_trusted_after_end_s": first_trusted if induced else None,
            "back_to_clean_after_end_s": back_clean if induced else None,
            "recovery_status": ("未引發轉移" if not induced else
                                ("未觀測到恢復" if back_clean is None else "已回到乾淨對照")),
            "tracked_s": ktrack - kend, "tally": dict(tally),
            "transitions": {k: dict(v) for k, v in trans.items()}}, unexplained


def load_runtime_ann(n):
    rows = [json.loads(l) for l in open(RUNTIME_ANN, encoding="utf-8")]
    by, cur, last = [], [], -1
    for r in rows:
        if r["window"] < last:
            by.append(cur); cur = []
        cur.append(r); last = r["window"]
    by.append(cur)
    if len(by) != n:
        raise SystemExit(f"runtime 註記切出 {len(by)} 個 seed，應為 {n}")
    return by


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=OUT_DIR)
    args = ap.parse_args()
    files = P.find_files(None)
    seeds = [os.path.basename(f).split("seed")[-1].replace(".txt", "") for f in files]
    rt = load_runtime_ann(len(seeds))
    clean_total = collections.Counter()
    rows = []
    n_checked = 0
    for si, (sd, f) in enumerate(zip(seeds, files)):
        anchor = X.TrustAnchor([g for g in files if g != f])
        wins = E10.load_windows(f)
        assert [w for w, _ in wins] == list(range(len(wins)))
        n_known = len({i for _, c in wins for u in c.values() for i in u})
        clean, _ = E10.run_policy(wins, anchor, "uebound", 1)
        clean_total.update(a["decision"] for a in clean)
        ref = [(r["window"], r["node"], r["decision"], r["rule_id"]) for r in rt[si]]
        if ref != [(a["k"], a["node"], a["decision"], a["rule_id"]) for a in clean]:
            raise SystemExit(f"✗ 檢查 2：seed {sd} 乾淨回放與 runtime 註記不一致")
        clean_tr = trace(wins, anchor, n_known)
        check_trace(clean, clean_tr, f"seed {sd} 乾淨"); n_checked += len(clean)
        for sm in P.samples_of(sd, P.load_cell_delay(f)):
            for kind in KINDS:
                for T in T_LIST:
                    att, info, allowed = inject(wins, kind, sm.cell, sm.w_on, T, sm.mean)
                    base = {"seed": sd, "target": sm.cell, "kind": kind, "T": T, "t0": sm.w_on, **info}
                    if att is None:
                        rows.append(base); continue
                    extra = changed_cells(wins, att) - allowed
                    if extra:
                        raise SystemExit(f"✗ 注入層級：{base} 改動了未宣告之 cell {sorted(extra)}")
                    a_ann, _ = E10.run_policy(att, anchor, "uebound", 1)
                    att_tr = trace(att, anchor, n_known)
                    check_trace(a_ann, att_tr, str(base)); n_checked += len(a_ann)
                    r, unexpl = analyse(kind, clean_tr, att_tr, sm.cell, sm.w_on, T, len(wins))
                    if unexpl:
                        raise SystemExit(f"✗ 無法解釋之差異：{base}；例 {unexpl[:2]}")
                    rows.append({**base, **r})
        print(f"seed {sd} 完成")

    got = {k: clean_total.get(k, 0) for k in EXPECTED_P3}
    print("── 檢查 1：乾淨回放合計", got, "✓" if got == EXPECTED_P3 else "✗")
    if got != EXPECTED_P3:
        raise SystemExit("不一致，停止，不寫檔。")
    print("── 檢查 2：乾淨回放逐筆 = runtime 註記 ✓")
    print(f"── 檢查 3：可追溯性 ✓（獨立重算 {n_checked} 筆註記之 P1→P2 皆相同；注入層級皆合宣告；無無法解釋之差異）")

    path = os.path.join(args.out_dir, "E11_transitions.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"spec": "docs/thesis/E11_E12_B4_spec.md v2", "track_s": TRACK, "T": T_LIST,
                   "replay_only_kinds": sorted(REPLAY_ONLY), "n_records_traced": n_checked, "rows": rows},
                  fh, indent=1, ensure_ascii=False)
    summarize(rows)
    print(f"\n寫入 {path}")


def summarize(rows):
    med = lambda xs: (float(statistics.median(xs)) if xs else None)
    print("\n══ E11 摘要（受測節點；秒；中位數僅含有值者）══")
    for kind in KINDS:
        for T in T_LIST:
            rs = [r for r in rows if r["kind"] == kind and r["T"] == T and "induced" in r]
            sk = sum(1 for r in rows if r["kind"] == kind and r["T"] == T and "skip" in r)
            ind = [r for r in rs if r["induced"]]
            lv = [r["leave_s"] for r in ind if r["leave_s"] is not None]
            rj = [r["reject_s"] for r in ind if r["reject_s"] is not None]
            ft = [r["first_trusted_after_end_s"] for r in ind if r["first_trusted_after_end_s"] is not None]
            st = collections.Counter(r["recovery_status"] for r in rs)
            print(f"{kind:<14} T={T:<2} n={len(rs):>2}（略過 {sk}）| {dict(st)} | 離開 trusted {med(lv)}"
                  f" | 到 rejected {len(rj)}/{len(ind)}，{med(rj)} | 首次回 trusted {len(ft)}/{len(ind)}，{med(ft)}")
    print("\n══ 差異分類（全部情境合計）══")
    tot = collections.Counter()
    for r in rows:
        tot.update(r.get("tally", {}))
    for k, v in sorted(tot.items()):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
