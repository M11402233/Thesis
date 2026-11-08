# -*- coding: utf-8 -*-
"""check_env.py — E19 §2 環境一致性檢查（先於任何訓練；任一失敗即停，不寫結果檔）。

  G1  無攻擊、規則版（D0）→ 逐筆重現 severity 之 15,534 筆註記（decision、rule_id）
  G2a 不變性：延遲竄改下，環境之判定 = 完整 run_xapp 於注入後資料之判定（全部 seed × cell × 攻擊）
  G2b RQ3：A0（×0.6、×0.8、漂移 1%）及漂移 2% 之誘導率等指標逐位重現 RQ3_decision_replay.json（uebound）
  G2c E11：S_i 類注入（漂移、階躍 ×1.5）之轉移統計逐列重現 E11_transitions.json；
      並與 E11 之獨立實作（trace，不呼叫 xApp 函式）逐筆相同
      （E11 之 C_i／D1／D2 類注入改變成員關係，不在攻擊者第一步之動作空間內，故不適用）
  G3  決定性：同一 seed、同一策略（含隨機策略固定 rng）重跑，判定與觀測逐位相同

用法（~/venvs/drl）：ZT_DATASET=d30 ZT_FUSION_ORDER=severity python check_env.py
"""
import os
import sys
import json
import time
import hashlib
import subprocess
import collections
import numpy as np

import game_core as G
X = G.X
sys.path.insert(0, os.path.join(G.HERE, "..", "residuals"))
import run_E11_transitions as E11            # noqa: E402
import planB_rt as P                         # noqa: E402

ROOT = os.path.abspath(os.path.join(G.HERE, "..", "..", ".."))
SEV = os.path.join(ROOT, "data", "results", "d30_fusion_order", "severity")
OUT = os.path.join(ROOT, "data", "results", "d30", "drl", "env_checks")


def fail(msg):
    print("  ✗", msg)
    print("停止：不寫入結果檔。請回報，勿調參數。")
    sys.exit(2)


def split_by_seed(path, n):
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]
    by, cur, last = [], [], -1
    for r in rows:
        if r["window"] < last:
            by.append(cur); cur = []
        cur.append(r); last = r["window"]
    by.append(cur)
    assert len(by) == n, len(by)
    return by


def env_decisions(ep):
    return {key: (d, r) for key, (d, r, _) in ep.final.items()}


def main():
    t_start = time.time()
    ds = G.DataStore()
    files = ds.files
    res = {}

    # ---------------- G1 ----------------
    ref = split_by_seed(os.path.join(SEV, "xapp_trust_annotations_bound_all_uebound_strict_severity.jsonl"), 8)
    n_tot = 0
    for f, rows in zip(files, ref):
        sd = ds.get(f)
        ep = G.run_episode(G.Episode(sd, atk_cell=None), G.det_floor_policy)
        got = [(k, j, *env_decisions(ep)[(k, j)]) for (k, j) in sorted(ep.final)]
        exp = [(r["window"], r["node"], r["decision"], r["rule_id"]) for r in rows]
        if got != exp:
            bad = [(a, b) for a, b in zip(got, exp) if a != b][:3]
            fail(f"G1 seed {sd.seed}：{len(got)} vs {len(exp)} 筆，例 {bad}")
        n_tot += len(got)
    if n_tot != 15534:
        fail(f"G1 合計 {n_tot} ≠ 15,534")
    print(f"G1 ✓ 無攻擊、規則版逐筆重現 {n_tot:,} 筆（decision、rule_id）")
    res["G1"] = {"records": n_tot}

    # ---------------- G2a + G2b ----------------
    rq3 = json.load(open(os.path.join(SEV, "RQ3_decision_replay.json"), encoding="utf-8"))
    attacks = [("step_x0.8", G.ScriptedAttack("step", 0.80)), ("step_x0.6", G.ScriptedAttack("step", 0.60)),
               ("drift_1pct", G.ScriptedAttack("drift", 0.01)), ("drift_2pct", G.ScriptedAttack("drift", 0.02))]
    consumers = ["C_none", "C_strict", "C_restrict_annot", "C_notrej"]
    acc = collections.defaultdict(lambda: collections.Counter())
    regs = collections.defaultdict(list)
    n_g2a = 0
    for f in files:
        sd = ds.get(f)
        for name, atk in attacks:
            for cell in sd.cells_all:
                ep = G.run_episode(G.Episode(sd, cell), G.det_floor_policy, atk)
                # G2a：完整 run_xapp 於注入後資料
                mod = [(w, dict(c)) for w, c in sd.windows]
                for k in range(sd.n):
                    m = atk.multiplier(type("E", (), {"k": k, "sd": sd})())
                    if m is not None and cell in mod[k][1]:
                        mod[k][1][cell] = {i: v * m for i, v in mod[k][1][cell].items()}
                full = X.run_xapp(G.ListSource(mod), sd.anchor, "all", binding="uebound", admission="strict")[0]
                fullmap = {(a["window"], a["node"]): (a["decision"], a["rule_id"]) for a in full}
                if fullmap != env_decisions(ep):
                    d = [x for x in fullmap if fullmap[x] != env_decisions(ep).get(x)][:3]
                    fail(f"G2a seed {sd.seed} {name} cell {cell}：例 {d}")
                n_g2a += len(fullmap)
                # G2b：RQ3 指標（只計注入區間、真值候選 ≥ 2）
                for k in range(sd.t0, sd.n):
                    truth = sd.truth[k]
                    if len(truth) < 2:
                        continue
                    rep = {c: float(np.mean(list(v.values()))) for c, v in mod[k][1].items() if c != G.LTE and v}
                    opt = min(truth, key=lambda c: truth[c])
                    decs = {j: env_decisions(ep)[(k, j)][0] for j in sd.nodes[k]}
                    for cons in consumers:
                        a = acc[(name, cons)]
                        adm = {"C_none": set(rep), "C_strict": {j for j, d in decs.items() if d == "trusted"},
                               "C_restrict_annot": {j for j, d in decs.items() if d in ("trusted", "low-trust")},
                               "C_notrej": {j for j, d in decs.items() if d != "rejected"}}[cons]
                        a["win"] += 1; a["ann"] += len(decs); a["usable"] += len(adm)
                        a["cap_base"] += len(rep); a["cap_kept"] += len(adm)
                        a["opt_ex"] += opt not in adm
                        ch = G.decide(rep, adm)
                        if ch is None:
                            continue
                        a["avail"] += 1
                        g = truth.get(ch, np.nan) - truth[opt]
                        regs[(name, cons)].append(g / truth[opt] if truth[opt] > 0 else np.nan)
                        a["wrong"] += ch != opt
                        if cell in truth and cell != opt:
                            a["opp"] += 1; a["lured"] += ch == cell
    print(f"G2a ✓ 延遲竄改下環境判定 = 完整 run_xapp（{n_g2a:,} 筆，8 seed × 7 cell × 4 攻擊）")
    worst = 0.0
    for (name, cons), a in acc.items():
        r = rq3[f"uebound|{name}|{cons}"]
        rr = [x for x in regs[(name, cons)] if not np.isnan(x)]
        mine = {"windows": a["win"], "rho": a["cap_kept"] / a["cap_base"], "usable_yield": a["usable"] / a["ann"],
                "availability": a["avail"] / a["win"], "regret_rel_mean": float(np.mean(rr)) if rr else None,
                "optimal_excluded_rate": a["opt_ex"] / a["win"], "wrong_rate": a["wrong"] / a["avail"] if a["avail"] else None,
                "lured_rate": a["lured"] / a["opp"] if a["opp"] else None}
        for key, v in mine.items():
            if (v is None) != (r[key] is None) or (v is not None and abs(v - r[key]) > 1e-12):
                fail(f"G2b {name}|{cons}|{key}：環境 {v} vs RQ3 {r[key]}")
            if v is not None:
                worst = max(worst, abs(v - r[key]))
    print(f"G2b ✓ RQ3 指標逐項重現（4 攻擊 × 4 准入政策 × 8 指標，最大差 {worst:.1e}）；"
          f"誘導率 C_strict：×0.6 {acc[('step_x0.6','C_strict')]['lured']/acc[('step_x0.6','C_strict')]['opp']:.1%}、"
          f"×0.8 {acc[('step_x0.8','C_strict')]['lured']/acc[('step_x0.8','C_strict')]['opp']:.1%}、"
          f"漂移 1% {acc[('drift_1pct','C_strict')]['lured']/acc[('drift_1pct','C_strict')]['opp']:.1%}")
    res["G2a"] = {"records": n_g2a}
    res["G2b"] = {"max_abs_diff": worst}

    # ---------------- G2c：E11 之 S_i 類 ----------------
    e11 = json.load(open(os.path.join(SEV, "E11_transitions.json"), encoding="utf-8"))["rows"]
    e11 = {(r["seed"], r["target"], r["kind"], r["T"]): r for r in e11 if r["kind"] in ("Si_drift", "Si_step")}
    n_rows = n_rec = 0
    lv = {"normal": "none", "weak": "weak", "strong": "strong"}

    def as_trace(ep):
        tr = {}
        for (k, j), (dec, rid, _) in ep.final.items():
            ci, run, d2, d1, _ = ep.sd.ev[(k, j)]
            si = ep_si[(k, j)]
            tr[(k, j)] = {"decision": dec, "rule_id": rid, "admitted": dec == "trusted",
                          "ev": {"C_i": ci == "violated", "ci_run": run, "D2": d2 == "violated", "S_i": si,
                                 "S_i_avail": si != "unavailable", "D1": lv[d1]}}
        return tr

    for f in files:
        sd = ds.get(f)
        n_known = len({i for _, c in sd.windows for u in c.values() for i in u})
        ep_si = {}
        cl = G.Episode(sd, None)
        while cl.k < sd.n:
            cl.begin()
            ep_si.update({(cl.k, j): cl.info[j]["si"] for j in cl.info})
            for j in list(cl.pending):
                cl.decide_node(j, G.det_floor_policy(cl, j))
            cl.end()
        clean_tr = as_trace(cl)
        for sm in P.samples_of(sd.seed, P.load_cell_delay(f)):
            for kind in ("Si_drift", "Si_step"):
                for T in E11.T_LIST:
                    att, info, allowed = E11.inject(sd.windows, kind, sm.cell, sm.w_on, T, sm.mean)
                    ep = G.Episode(sd, sm.cell)
                    ep_si = {}

                    def modifier(k, w, ues, att=att, cell=sm.cell):
                        ues.update(att[k][1][cell])
                    while ep.k < sd.n:
                        ep.begin(modifier=modifier)
                        ep_si.update({(ep.k, j): ep.info[j]["si"] for j in ep.info})
                        for j in list(ep.pending):
                            ep.decide_node(j, G.det_floor_policy(ep, j))
                        ep.end()
                    att_tr = as_trace(ep)
                    ind = E11.trace(att, sd.anchor, n_known)
                    if {k: (v["decision"], v["rule_id"]) for k, v in ind.items()} != \
                            {k: (v["decision"], v["rule_id"]) for k, v in att_tr.items()}:
                        fail(f"G2c 與 E11 獨立實作不符：seed {sd.seed} cell {sm.cell} {kind} T={T}")
                    n_rec += len(att_tr)
                    r, unexpl = E11.analyse(kind, clean_tr, att_tr, sm.cell, sm.w_on, T, sd.n)
                    key = (sd.seed, sm.cell, kind, T)
                    exp = e11.get(key)
                    if exp is None or unexpl or any(exp.get(x) != v for x, v in r.items()):
                        diff = {x: (v, (exp or {}).get(x)) for x, v in r.items() if (exp or {}).get(x) != v}
                        fail(f"G2c E11 列不符：{key}；{list(diff.items())[:2]}")
                    n_rows += 1
    if n_rows != len(e11):
        fail(f"G2c 只比對 {n_rows} 列，E11 有 {len(e11)} 列 S_i 類")
    print(f"G2c ✓ E11 之 S_i 類 {n_rows} 列逐列重現；與獨立實作逐筆相同（{n_rec:,} 筆）")
    res["G2c"] = {"rows": n_rows, "records": n_rec}

    # ---------------- G3 ----------------
    def digest(seed_path, atk, rng_seed):
        sd = G.DataStore().get(seed_path)
        rng = np.random.default_rng(rng_seed)
        h = hashlib.sha256()

        def pol(ep, j):
            h.update(ep.det_obs(j).tobytes())
            return int(rng.choice(np.flatnonzero(ep.mask(j))))
        ep = G.run_episode(G.Episode(sd, 4), pol, atk)
        h.update(repr(sorted(ep.final.items())).encode())
        h.update(repr(ep.atk_log).encode())
        return h.hexdigest()
    d1 = digest(files[0], G.A0[2], 123)
    d2 = digest(files[0], G.A0[2], 123)
    d3 = digest(files[0], G.A0[2], 124)
    if d1 != d2:
        fail("G3 同一 seed、同一策略重跑結果不同")
    if d1 == d3:
        fail("G3 對照失效：不同 rng 卻相同（檢查無鑑別力）")
    print(f"G3 ✓ 重跑逐位相同（sha256 {d1[:12]}…；不同 rng 之對照確實不同）")
    res["G3"] = {"sha256": d1}

    commit = subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", ROOT, "status", "--porcelain", "xapps/verification/adversarial"],
                           capture_output=True, text=True).stdout.strip()
    import gymnasium
    res["_meta"] = {"spec": "docs/thesis/E19_DRL_game_spec.md v2 §2", "git_commit": commit,
                    "adversarial_dir_uncommitted": bool(dirty), "numpy": np.__version__,
                    "gymnasium": gymnasium.__version__, "python": sys.version.split()[0],
                    "elapsed_s": round(time.time() - t_start, 1)}
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "env_checks.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, ensure_ascii=False)
    print(f"全部通過（{res['_meta']['elapsed_s']} s）。寫入 {os.path.join(OUT, 'env_checks.json')}")


if __name__ == "__main__":
    main()
