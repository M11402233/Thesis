#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_B4_used_resources.py — B4：准入節點所承載的既有排程資源量比例（補充分析；不取代容量版 ρ）

規格：docs/thesis/E11_E12_B4_spec.md（v2）之 B4 段。

  r_used = Σ_{t,j} m_j(t) R_j(t) ／ Σ_{t,j∈A(t)} R_j(t)

  m_j(t)：4.12 之准入遮罩，直接讀 RQ3_eligibility_mask.jsonl.gz（不重跑決策）
  A(t)  ：同 4.12（當窗有上報之 mmWave 節點）
  R_j(t)：乾淨 PHY trace（D-SH aux 之 RxPacketTrace，DL）中 cell j 於第 t 秒之**排程符號量**
          （symbol# 加總，含重傳與解碼失敗之 TB）；敏感度版本以 TB 位元組量為 R。
          trace 未含頻率配置，故稱排程符號量，不稱 PRB 容量。

【內建檢查】
  1. PHY trace 無重複紀錄（同 cell、frame、subframe、slot、起始符號、RNTI）
  2. R_j(t) 全設為 1 時，r_used 須重現 RQ3_decision_replay.json 之 ρ（逐組、容許 1e-12）
  3. 四個 seed 之 aux RLC 須與 si_lstm_seeds 逐位元組相同
【解讀（正文必寫）】排除 KPM 並未使已排程之資源消失；r_used 描述被准入節點原本承載多少排程量，
  不代表實際容量損失。分母為 0 者記為 n/a。
"""
import os
import sys
import gzip
import json
import filecmp
import argparse
import collections

ROOT = os.path.expanduser("~/oran-zt-kpm-verification/data")
OUT_DIR = os.path.join(ROOT, "results")


def load_phy(seed):
    sym = collections.defaultdict(float)
    tb = collections.defaultdict(float)
    keys = set()
    dup = 0
    path = os.path.join(ROOT, "si_lstm_aux", f"ues1_t300_seed{seed}_aux", "RxPacketTrace.txt.gz")
    with gzip.open(path, "rt") as fh:
        fh.readline()
        for line in fh:
            p = line.rstrip("\n").split("\t")
            if p[0] != "DL":
                continue
            key = (p[7], p[2], p[3], p[4], p[5], p[8])
            if key in keys:
                dup += 1
                continue
            keys.add(key)
            c, w = int(p[7]), int(float(p[1]))
            sym[(c, w)] += int(p[6])
            tb[(c, w)] += int(p[10])
    return sym, tb, dup


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=OUT_DIR)
    args = ap.parse_args()
    seeds = ["4200", "4201", "4202", "4203"]
    for s in seeds:
        a = os.path.join(ROOT, "si_lstm_aux", f"ues1_t300_seed{s}_aux", "DlE2RlcStats.txt")
        b = os.path.join(ROOT, "si_lstm_seeds", f"ues1_t300_seed{s}.txt")
        if not filecmp.cmp(a, b, shallow=False):
            raise SystemExit(f"✗ 檢查 3：seed {s} aux 與 D-SH 不一致")
    W = {}
    for s in seeds:
        sym, tb, dup = load_phy(s)
        if dup:
            raise SystemExit(f"✗ 檢查 1：seed {s} PHY trace 有 {dup} 筆重複紀錄")
        W[s] = {"symbols": sym, "tb_bytes": tb}
    print("── 檢查 1：PHY trace 無重複紀錄 ✓；檢查 3：aux RLC = D-SH ✓")

    acc = collections.defaultdict(lambda: collections.defaultdict(float))
    zero_den = collections.Counter()
    with gzip.open(os.path.join(OUT_DIR, "RQ3_eligibility_mask.jsonl.gz"), "rt", encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            seed = r["seed"].split("seed")[-1].replace(".txt", "")
            k, A = r["k"], r["A"]
            for cons, adm in r["admitted"].items():
                key = f"{r['ann_policy']}|{r['attack']}|{cons}"
                acc[key]["one_num"] += len(adm); acc[key]["one_den"] += len(A)
                for wname in ("symbols", "tb_bytes"):
                    w = W[seed][wname]
                    den = sum(w.get((j, k), 0.0) for j in A)
                    acc[key][f"{wname}_num"] += sum(w.get((j, k), 0.0) for j in adm)
                    acc[key][f"{wname}_den"] += den
                    if den == 0:
                        zero_den[f"{key}|{wname}"] += 1

    rq3 = json.load(open(os.path.join(OUT_DIR, "RQ3_decision_replay.json"), encoding="utf-8"))
    bad = []
    res = {}
    for key, a in acc.items():
        one = a["one_num"] / a["one_den"] if a["one_den"] else None
        if rq3.get(key) is None or one is None or abs(one - rq3[key]["rho"]) > 1e-12:
            bad.append((key, one, rq3.get(key, {}).get("rho")))
        res[key] = {"rho_capacity": rq3.get(key, {}).get("rho"),
                    "r_used_symbols": a["symbols_num"] / a["symbols_den"] if a["symbols_den"] else "n/a",
                    "r_used_tb_bytes": a["tb_bytes_num"] / a["tb_bytes_den"] if a["tb_bytes_den"] else "n/a",
                    "zero_denominator_windows": {w: zero_den.get(f"{key}|{w}", 0) for w in ("symbols", "tb_bytes")}}
    if bad:
        raise SystemExit(f"✗ 檢查 2：R=1 未重現 ρ：{bad[:4]}")
    print(f"── 檢查 2：R ≡ 1 時重現 RQ3 之 ρ（{len(acc)} 組，逐組相同）✓\n")

    path = os.path.join(args.out_dir, "B4_used_resources.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"spec": "docs/thesis/E11_E12_B4_spec.md v2 (B4)",
                   "definition": "r_used = sum m_j(t) R_j(t) / sum_{j in A(t)} R_j(t); R from clean PHY trace",
                   "interpretation": "share of already-scheduled resources carried by admitted nodes; not a capacity loss",
                   "results": res}, fh, indent=2, ensure_ascii=False)
    print(f"{'註記政策|攻擊|准入政策':<38} {'ρ（容量）':>9} {'r_used 符號':>11} {'r_used TB':>10} 分母0窗")
    for key in sorted(res):
        v = res[key]
        f = lambda x: f"{x * 100:.1f}%" if isinstance(x, float) else x
        print(f"{key:<38} {f(v['rho_capacity']):>9} {f(v['r_used_symbols']):>11} {f(v['r_used_tb_bytes']):>10} "
              f"{v['zero_denominator_windows']['symbols']}")
    print(f"\n寫入 {path}")


if __name__ == "__main__":
    main()
