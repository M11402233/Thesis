#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_E25_cucp_membership.py — 規格 docs/thesis/E25_cucp_membership_rule_spec.md v1。
CU-CP 成員對帳（H_i-D4，R1_D4_VETO；疊加於註記之上，zt_kpm_xapp 本體不改）。
內建檢查 E25-0～E25-3（任一失敗即停，不寫輸出）。

跑法（舊機器）：
  ZT_DATASET=d30 ZT_FUSION_ORDER=severity python3 xapps/verification/residuals/run_E25_cucp_membership.py
"""
import os
import sys
import gzip
import glob
import json
import time
import collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run_E21_S0_membership as S0                                # noqa: E402
from run_E21_S0_membership import X, DS, load_windows, inject, stop, T0S, L, KS, LTE  # noqa: E402
from run_E21_S1_boff import relaxed                               # noqa: E402
from run_RQ3_decision_replay import ListSource, apply_attack, true_delays  # noqa: E402

OUT_DIR = os.path.join(S0.SEV_DIR, "E25")
S1_JSON = os.path.join(S0.SEV_DIR, "E21_S1", "E21_S1_boff.json")
DELAY = [("A0_step_0.6", "step", 0.60), ("A0_step_0.8", "step", 0.80), ("A0_drift_0.01", "drift", 0.01)]
MEMB_ALL = ["A1_delete", "A2_swap", "A3_claim_anchor", "A4_claim_peer"]
TM3 = "data/game_stage3/S3-TM3/S3-TM3_ues30_t300_seed42*.txt"
N_UE = 30


def load_cucp(aux_dir, n_win):
    """回傳 [第 k 份報表之 {cell: set(imsi)}]；E25-0"""
    maps = [collections.defaultdict(set) for _ in range(n_win)]
    for c in range(2, 9):
        rows = collections.OrderedDict()
        with gzip.open(os.path.join(aux_dir, f"cu-cp-cell-{c}.txt.gz"), "rt") as fh:
            fh.readline()
            for line in fh:
                p = line.split(",")
                if len(p) < 2 or not p[0]:
                    continue
                rows.setdefault(int(p[0]), set()).add(int(p[1]))
        ts = sorted(rows)
        if len(ts) < n_win:
            stop(f"E25-0 {aux_dir} cell {c}：報表 {len(ts)} 份 < {n_win}")
        for k in range(n_win):
            maps[k][c] = rows[ts[k]]
    for k, m in enumerate(maps):
        allu = [i for c in m for i in m[c]]
        if len(allu) != N_UE or len(set(allu)) != N_UE:
            stop(f"E25-0 {aux_dir} 第 {k} 份：UE {len(allu)}／相異 {len(set(allu))}（應為 {N_UE}）")
    return maps


def d4(cells, amap, j):
    """回傳 (D4a 外來成員, D4b 失蹤成員)"""
    rep = set(cells.get(j, {}))
    att = amap.get(j, set())
    return sorted(rep - att), sorted(att - rep - set(cells.get(LTE, {})))


def run(wins, anchor, d3):
    X.D3_ENABLED = d3
    return X.run_xapp(ListSource(wins), anchor, "all", binding="uebound", admission="strict")[0]


def adm(dec, policy):
    return X.ACTION[dec] in X.ADMISSION[policy]


def clean_count(wins, maps):
    n = a = b = 0
    for t, (w, cells) in enumerate(wins):
        for j in cells:
            if j == LTE:
                continue
            fa, fb = d4(cells, maps[t], j)
            n += 1
            a += bool(fa)
            b += bool(fb)
    return n, a, b


def main():
    t_start = time.time()
    files = DS.files()
    ref = [json.loads(l) for l in open(S0.REF_ANN, encoding="utf-8")]
    s1 = json.load(open(S1_JSON, encoding="utf-8"))["results"]

    print("── 4.1 乾淨 ──")
    seeds, pos, tot = [], 0, [0, 0, 0]
    for f in files:
        sd = DS.seed_of(f)
        anchor = X.TrustAnchor([g for g in files if g != f])
        wins = load_windows(f)
        if [w for w, _ in wins] != list(range(len(wins))):
            stop(f"seed {sd}：窗編號非 0…{len(wins) - 1}")
        maps = load_cucp(os.path.dirname(DS.aux_path(sd, "x")), len(wins))
        off = run(wins, anchor, False)
        seg = ref[pos:pos + len(off)]
        pos += len(off)
        if len(seg) != len(off) or any(json.loads(json.dumps(x, ensure_ascii=False)) != r for x, r in zip(off, seg)):
            stop(f"E25-1 seed {sd}：乾淨回放與註記檔不同")
        n, a, b = clean_count(wins, maps)
        tot = [tot[0] + n, tot[1] + a, tot[2] + b]
        static = all(maps[k] == maps[0] for k in range(len(maps)))
        print(f"  seed {sd}：(節點, 窗) {n}  D4a {a}  D4b {b}  CU-CP 對應全程不變：{static}")
        seeds.append((sd, anchor, wins, maps))
    if pos != len(ref):
        stop(f"E25-1 總筆數 {pos} ≠ {len(ref)}")
    print(f"  E25-0 ✓  E25-1（乾淨 15,534 筆）✓   D-30 乾淨：(節點, 窗) {tot[0]}，D4a {tot[1]}，D4b {tot[2]}")
    if tot[1] or tot[2]:
        stop(f"4.1 乾淨 D-30 之 D4 觸發（D4a {tot[1]}、D4b {tot[2]}；預期 0）——依規格停止回報，不調整規則")
    tm3 = {"files": 0, "node_windows": 0, "D4a": 0, "D4b": 0}
    for f in sorted(glob.glob(os.path.join(S0.REPO, TM3))):
        wins = list(X.TraceReplaySource(f).windows())
        wins = [(w, c) for w, c in wins if w < 300]
        if [w for w, _ in wins] != list(range(len(wins))):
            print(f"  S3-TM3 {os.path.basename(f)}：窗編號不連續，略過（只記錄）")
            continue
        maps = load_cucp(f[:-4] + "_aux", len(wins))
        n, a, b = clean_count(wins, maps)
        tm3 = {"files": tm3["files"] + 1, "node_windows": tm3["node_windows"] + n, "D4a": tm3["D4a"] + a, "D4b": tm3["D4b"] + b}
    print(f"  S3-TM3（只記錄）：{tm3}")

    print("── 4.2 成員關係攻擊 ──")
    res = {}
    for atk in MEMB_ALL:
        for k in KS:
            c = collections.Counter()
            delays = {"D4": [], "D3+D4": []}
            for sd, anchor, wins, maps in seeds:
                for j in sorted({cc for _, cl in wins for cc in cl if cc != LTE}):
                    for t0 in T0S:
                        hi = min(t0 + L + S0.POST, len(wins))
                        iw, nmod = inject(wins, j, t0, k, atk)
                        if sum(nmod) == 0:
                            continue
                        off, on = run(iw[:hi], anchor, False), run(iw[:hi], anchor, True)
                        cellmap = {w: cl for w, cl in iw[:hi]}
                        c["episodes"] += 1
                        first_tam, first_rej = None, {"D4": None, "D3+D4": None}
                        for a_off, a_on in zip(off, on):
                            t, node = a_off["window"], a_off["node"]
                            fa, fb = d4(cellmap[t], maps[t], node)
                            v = bool(fa or fb)
                            is_tam = node == j and t0 <= t < t0 + L and nmod[t - t0] > 0
                            if v and not is_tam:
                                stop(f"E25-2 {atk} k={k} seed {sd} j={j} t0={t0}：D4 觸發於非竄改之 (節點 {node}, 窗 {t})：{fa} {fb}")
                            if not is_tam:
                                continue
                            c["tam"] += 1
                            c["d4"] += v
                            c["d4a"] += bool(fa)
                            c["d4b"] += bool(fb)
                            c["d3"] += a_on.get("H_i_D3") == "violated"
                            for tag, a in (("off", a_off), ("D4", a_off), ("D3+D4", a_on)):
                                dec = "rejected" if (v and tag != "off") else a["decision"]
                                rel = relaxed(a) and not (v and tag != "off")
                                c[f"{tag}_strict"] += adm(dec, "strict")
                                c[f"{tag}_restrict"] += adm(dec, "restrict_annotated")
                                c[f"{tag}_boff"] += adm("trusted" if rel else dec, "strict")
                                if tag != "off" and first_rej[tag] is None and dec == "rejected":
                                    first_rej[tag] = t
                            if first_tam is None:
                                first_tam = t
                        if first_tam is not None:
                            for tag in delays:
                                delays[tag].append(None if first_rej[tag] is None else first_rej[tag] - first_tam)
            key = f"{atk}|k={k}"
            n = c["tam"]
            if c["off_strict"] / n != s1["membership"][key]["MF_strict_rule"] or n != s1["membership"][key]["tampered"]:
                stop(f"E25-1 {key}：關閉時 MF {c['off_strict'] / n}／竄改 {n} 未重現 E21-S1")
            r = {"episodes": c["episodes"], "tampered": n,
                 "det_D4": c["d4"] / n, "det_D4a": c["d4a"] / n, "det_D4b": c["d4b"] / n, "det_D3": c["d3"] / n}
            for tag in ("off", "D4", "D3+D4"):
                r[tag] = {"MF_strict": c[f"{tag}_strict"] / n, "MF_restrict": c[f"{tag}_restrict"] / n,
                          "MF_strict_boff": c[f"{tag}_boff"] / n}
            for tag, d in delays.items():
                ok = [x for x in d if x is not None]
                r[tag]["delay"] = {"n": len(d), "never": len(d) - len(ok), "max": max(ok, default=None)}
            res[key] = r
            print(f"  {key:22s} 竄改 {n:5d}  D4 {r['det_D4']:.3f}（a {r['det_D4a']:.3f}／b {r['det_D4b']:.3f}） D3 {r['det_D3']:.3f} | "
                  f"MF_strict {r['off']['MF_strict']:.3f}→{r['D4']['MF_strict']:.3f}→{r['D3+D4']['MF_strict']:.3f}  "
                  f"restrict {r['off']['MF_restrict']:.3f}→{r['D4']['MF_restrict']:.3f}→{r['D3+D4']['MF_restrict']:.3f}  "
                  f"B-off {r['off']['MF_strict_boff']:.3f}→{r['D4']['MF_strict_boff']:.3f}→{r['D3+D4']['MF_strict_boff']:.3f}  "
                  f"延遲 max {r['D3+D4']['delay']['max']} 未拒 {r['D3+D4']['delay']['never']}", flush=True)
    print("  E25-1 ✓（關閉時重現 E21-S1）  E25-2 ✓（D4 只出現在竄改之 (j, 窗)）")

    print("── 4.3 延遲攻擊（副作用）──")
    for name, kind, param in DELAY:
        trig = 0
        for sd, anchor, base, maps in seeds:
            t0 = len(base) // 2
            for cell in sorted({cc for d in true_delays(base) for cc in d}):
                mod = apply_attack(base, cell, kind, param, t0)
                trig += sum(a + b for _, a, b in [clean_count(mod, maps)])
        if trig:
            stop(f"E25-3 {name}：D4 觸發 {trig} 次（預期 0）")
        res[name] = {"d4_triggered": 0}
        print(f"  {name}：D4 觸發 0")
    print("  E25-3 ✓")
    X.D3_ENABLED = False
    os.makedirs(OUT_DIR, exist_ok=True)
    p = os.path.join(OUT_DIR, "E25_cucp_membership.json")
    json.dump({"spec": "docs/thesis/E25_cucp_membership_rule_spec.md v1",
               "checks": {"E25-0": "pass", "E25-1": "pass", "E25-2": "pass", "E25-3": "pass"},
               "clean_D30": {"node_windows": tot[0], "D4a": tot[1], "D4b": tot[2]}, "clean_S3_TM3": tm3,
               "attacks": res, "elapsed_s": round(time.time() - t_start, 1)},
              open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"寫入 {p}（{time.time() - t_start:.0f} s）")


if __name__ == "__main__":
    main()
