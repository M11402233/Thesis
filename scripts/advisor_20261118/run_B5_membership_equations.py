#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B5：成員名單三條等式（規格 docs/thesis/B5_membership_equations_spec_v0.md）。
只用報表成員集合與登記名單 R；不用 CU-CP。內建檢查 B5-0～B5-2，失敗即停、不寫輸出。
跑法（於 xapps/verification/residuals）：
  ZT_DATASET=d30 ZT_FUSION_ORDER=severity python3 ../../../scripts/advisor_20261118/run_B5_membership_equations.py
"""
import os, sys, json, time, collections
HERE = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "xapps", "verification", "residuals"))
sys.path.insert(0, HERE)
import run_E21_S0_membership as S0                                     # noqa: E402
from run_E21_S0_membership import X, DS, load_windows, inject, stop, check_s01, T0S, L, KS, LTE  # noqa: E402

N = X.N_KNOWN
REG = set(range(1, N + 1))
OUT = os.path.join(S0.REPO, "data", "results", "advisor_20261118", "B5_membership_equations.json")
ATKS = ["A1_delete", "A2_swap", "A3_claim_anchor", "A4_claim_peer", "A5_swap_peer"]
NFRAME = 5


def sets(cells):
    return {j: set(u) for j, u in cells.items()}


def equations(S):
    allu = [i for j in S for i in S[j]]
    uni = set(allu)
    return {"E1": len(uni) == N, "E2": len(allu) == N, "E3": uni <= REG}


def inject_a5(wins, j, t0, k):
    """A5：刪 k 個自身 UE、加 k 個他人（peer mmWave）UE，延遲取自身均值；Σ 不變"""
    out, nmod, prev = list(wins), [], []
    for t in range(t0, min(t0 + L, len(wins))):
        w, cells = wins[t]
        c2 = {c: dict(u) for c, u in cells.items()}
        if j not in c2 or not c2[j]:
            nmod.append(0); continue
        mine = c2[j]
        peer = sorted({i for c in c2 if c not in (LTE, j) for i in c2[c]} - set(mine))
        own = sorted(mine)
        kk = min(k, len(own), len(peer))
        m = sum(mine.values()) / len(mine)
        sel = [i for i in prev if i in peer][:kk]
        for i in peer:
            if len(sel) >= kk:
                break
            if i not in sel:
                sel.append(i)
        for i in own[:kk]:
            mine.pop(i)
        for i in sel:
            mine[i] = m
        prev = sel
        nmod.append(kk)
        out[t] = (w, c2)
    return out, nmod


class History:
    """依觀測到之報表（含已竄改者）累積：last_unique[u]、last_reporters[u]"""
    def __init__(self):
        self.last_unique, self.last_rep = {}, {}

    def update(self, S):
        rep = collections.defaultdict(set)
        for j in S:
            for i in S[j]:
                rep[i].add(j)
        for i, r in rep.items():
            if len(r) == 1:
                self.last_unique[i] = next(iter(r))
        for i in list(self.last_rep):
            if i not in rep:
                pass                       # 缺失之 u 保留上一次之回報者
        for i, r in rep.items():
            self.last_rep[i] = set(r)


def attribute(S, hist):
    """回傳 {policy: (rejected_nodes, abstain_nodes, revoke_nodes)}"""
    nodes = set(S)
    eq = equations(S)
    if all(eq.values()):
        e = (set(), set(), set())
        return {"field": e, "sound": e, "temporal": e}, eq
    field = (set(nodes), set(), set(nodes))
    rep = collections.defaultdict(set)
    for j in S:
        for i in S[j]:
            rep[i].add(j)
    cand = set(nodes)
    for j in S:
        if S[j] - REG:
            cand &= {j}
    for i, r in rep.items():
        if len(r) >= 2:
            cand &= r
    if not cand:
        sound = field
    elif cand == nodes:
        sound = (set(), set(nodes), set())
    elif len(cand) == 1:
        sound = (set(cand), set(), set(cand))
    else:
        sound = (set(cand), set(), set())
    tcand = set(cand) if cand else set(nodes)
    if len(tcand) > 1:
        blame = set(nodes)
        for i, r in rep.items():
            if len(r) >= 2 and i in hist.last_unique:
                blame &= (r - {hist.last_unique[i]})
        missing = REG - set(rep)
        for i in missing:
            if i in hist.last_rep:
                blame &= hist.last_rep[i]
        b = tcand & blame
        temporal = (set(b), set(), set(b)) if len(b) == 1 else sound
    else:
        temporal = sound
    return {"field": field, "sound": sound, "temporal": temporal}, eq


def main():
    t_start = time.time()
    files = DS.files()
    if len(files) != 8:
        stop(f"B5-0 seed 數 {len(files)} ≠ 8")
    seeds = []
    clean_viol = collections.Counter()
    for f in files:
        sd = DS.seed_of(f)
        wins = load_windows(f)
        if [w for w, _ in wins] != list(range(300)):
            stop(f"B5-0 seed {sd}：窗編號非 0…299")
        for _, cells in wins:
            eq = equations(sets(cells))
            for e, ok in eq.items():
                clean_viol[e] += (not ok)
        seeds.append((sd, wins))
    print(f"── 4.1 乾淨：8 seed × 300 窗，違反 E1 {clean_viol['E1']}  E2 {clean_viol['E2']}  E3 {clean_viol['E3']}")
    if any(clean_viol.values()):
        stop(f"4.1 乾淨違反 {dict(clean_viol)}（H3 或 H4 於 D-30 不成立）——依規格停止回報")

    res = {}
    for atk in ATKS:
        for k in KS:
            c = collections.Counter()
            for sd, wins in seeds:
                for a in sorted({cc for _, cl in wins for cc in cl if cc != LTE}):
                    for t0 in T0S:
                        if atk == "A5_swap_peer":
                            iw, nmod = inject_a5(wins, a, t0, k)
                        else:
                            iw, nmod = inject(wins, a, t0, k, atk)
                        if sum(nmod) == 0:
                            continue
                        err = check_s01(wins, iw, a, t0)
                        if err:
                            stop(f"B5-1 {atk} k={k} seed {sd} a={a} t0={t0}：{err}")
                        c["episodes"] += 1
                        hist = History()
                        for t in range(0, min(t0 + L, len(iw))):
                            S = sets(iw[t][1])
                            if t >= t0 and nmod[t - t0] > 0:
                                pol, eq = attribute(S, hist)
                                same = S.get(a, set()) == set(wins[t][1].get(a, {}))
                                if all(eq.values()) != same:
                                    stop(f"B5-2 命題 1 不成立：{atk} k={k} seed {sd} a={a} t={t} eq={eq} same={same}")
                                c["tam"] += 1
                                det = not all(eq.values())
                                c["det"] += det
                                for e, ok in eq.items():
                                    c[f"viol_{e}"] += (not ok)
                                honest = set(S) - {a}
                                for p, (rej, abst, rev) in pol.items():
                                    c[f"{p}_correct"] += (rej == {a})
                                    c[f"{p}_a_rej"] += (a in rej)
                                    c[f"{p}_honest_rej"] += len(rej & honest)
                                    c[f"{p}_honest_abst"] += len(abst & honest)
                                    c[f"{p}_honest_revoke"] += len(rev & honest)
                                    c[f"{p}_honest_nw"] += len(honest)
                                    c[f"{p}_pair"] += (len(rej) == 2)
                                    c[f"{p}_allabst"] += (bool(abst) and abst == set(S))
                            hist.update(S)
            n = c["tam"]
            r = {"episodes": c["episodes"], "tampered_windows": n, "detected": c["det"] / n,
                 "viol": {e: c[f"viol_{e}"] / n for e in ("E1", "E2", "E3")}}
            for p in ("field", "sound", "temporal"):
                hn = c[f"{p}_honest_nw"]
                r[p] = {"attrib_exact_a": c[f"{p}_correct"] / n, "a_rejected": c[f"{p}_a_rej"] / n,
                        "pair_rejected": c[f"{p}_pair"] / n, "all_abstain": c[f"{p}_allabst"] / n,
                        "honest_rejected_per_tam": c[f"{p}_honest_rej"] / n,
                        "honest_rejected_frac": c[f"{p}_honest_rej"] / hn,
                        "honest_abstain_frac": c[f"{p}_honest_abst"] / hn,
                        "honest_revoke_per_tam": c[f"{p}_honest_revoke"] / n}
            res[f"{atk}|k={k}"] = r
            print(f"  {atk:16s} k={k} 竄改窗 {n:5d} 偵測 {r['detected']:.3f} (E1 {r['viol']['E1']:.2f} E2 {r['viol']['E2']:.2f} E3 {r['viol']['E3']:.2f}) | "
                  + " | ".join(f"{p}: 只指a {r[p]['attrib_exact_a']:.3f} a被拒 {r[p]['a_rejected']:.2f} 誠實拒/窗 {r[p]['honest_rejected_per_tam']:.2f} 誠實撤銷/窗 {r[p]['honest_revoke_per_tam']:.2f} 全abstain {r[p]['all_abstain']:.2f}"
                               for p in ("field", "sound", "temporal")), flush=True)
    print("  B5-1 ✓（注入只改 a、只在攻擊窗）  B5-2 ✓（攻擊窗中三式皆成立 ⇔ U_a 未改）")

    print("── 4.3 誣陷（P-temporal）──")
    frame = {}
    for kind in ("A6_stale_retain", "A7_omit_arrival"):
        c = collections.Counter()
        for sd, wins in seeds:
            ev = collections.defaultdict(list)
            for t in range(1, len(wins)):
                prev = {i: j for j, u in wins[t - 1][1].items() for i in u}
                cur = {i: j for j, u in wins[t][1].items() for i in u}
                for i in cur:
                    if i in prev and prev[i] != cur[i]:
                        x, y = prev[i], cur[i]
                        a = x if kind == "A6_stale_retain" else y
                        if a != LTE and len(ev[a]) < NFRAME:
                            ev[a].append((t, i, x, y))
            for a, lst in ev.items():
                for t, i, x, y in lst:
                    iw = list(wins)
                    c2 = {cc: dict(u) for cc, u in wins[t][1].items()}
                    if kind == "A6_stale_retain":
                        c2.setdefault(a, {})[i] = wins[t - 1][1][a][i]
                    else:
                        c2[a].pop(i)
                        if not c2[a]:
                            del c2[a]
                    iw[t] = (wins[t][0], c2)
                    for cc in set(c2) | set(wins[t][1]):
                        if cc != a and dict(c2.get(cc, {})) != dict(wins[t][1].get(cc, {})):
                            stop(f"B5-1 誣陷注入改到非 a 之節點 {cc}")
                    hist = History()
                    for tt in range(t):
                        hist.update(sets(iw[tt][1]))
                    S = sets(c2)
                    pol, eq = attribute(S, hist)
                    c["n"] += 1
                    c["det"] += not all(eq.values())
                    for p in ("sound", "temporal"):
                        rej = pol[p][0]
                        c[f"{p}_correct"] += (rej == {a})
                        c[f"{p}_framed"] += bool(rej - {a}) and a not in rej
                        c[f"{p}_honest_revoke"] += len(pol[p][2] - {a})
        n = c["n"]
        frame[kind] = {"events": n, "detected": c["det"] / n,
                       **{p: {"attrib_exact_a": c[f"{p}_correct"] / n, "framed_honest_only": c[f"{p}_framed"] / n,
                              "honest_revoke_per_event": c[f"{p}_honest_revoke"] / n} for p in ("sound", "temporal")}}
        print(f"  {kind}: 事件 {n}  偵測 {frame[kind]['detected']:.3f}  " +
              "  ".join(f"{p}: 只指a {frame[kind][p]['attrib_exact_a']:.3f} 只誣陷誠實 {frame[kind][p]['framed_honest_only']:.3f} 誠實撤銷/事件 {frame[kind][p]['honest_revoke_per_event']:.2f}" for p in ("sound", "temporal")))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"spec": "docs/thesis/B5_membership_equations_spec_v0.md", "dataset": "d30 (main file, cumulative semantics membership)",
               "checks": {"B5-0": "pass", "B5-1": "pass", "B5-2": "pass"}, "clean_violations": dict(clean_viol),
               "attacks": res, "framing": frame, "elapsed_s": round(time.time() - t_start, 1)},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"寫入 {OUT}（{time.time() - t_start:.0f} s）")


if __name__ == "__main__":
    main()
