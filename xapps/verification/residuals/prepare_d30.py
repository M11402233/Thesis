#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prepare_d30.py — D-30 分析用主檔：自原始 RLC 主檔截取 0–299 窗（不改動原始檔）

原因：--e2nrEnabled=true 會使模擬結束時之最後一窗遺失，故收集以 --simTime=301 執行；
原始主檔因此含第 300 窗（可能不完整）。分析一律讀本腳本之輸出（datasets.py 之 d30 指向 analysis/）。

輸出：<dst>/ues30_t300_seed<s>.txt（表頭 + 窗 < MAX_WINDOW 之列，逐位元組取自原始檔）
      <dst>/manifest.json（原始／輸出之 sha256、窗數、檢查結果）
【內建檢查】（任一不符即停止，不寫該 seed）
  1. 原始檔含 0 … MAX_WINDOW−1 每一窗
  2. 輸出恰為 0 … MAX_WINDOW−1 窗，且為原始檔之前綴列（逐位元組）
  3. 每窗 N_total = N_known；IMSI = 1 … N_known
  4. aux 之 DlE2RlcStats 截斷後與輸出相同（datasets.aux_matches_main）
用法：python3 prepare_d30.py            # 處理 data/ues30_seeds/ 下所有已完成之 seed
      python3 prepare_d30.py --src DIR --dst DIR --max-window 4 --n-known 30   # 測試用
"""
import os
import sys
import glob
import json
import hashlib
import argparse
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("ZT_DATASET", "d30")
import datasets as DS


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def main():
    cfg = DS.REGISTRY["d30"]
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=cfg["raw_dir"])
    ap.add_argument("--dst", default=cfg["dir"])
    ap.add_argument("--pattern", default=cfg["pattern"])
    ap.add_argument("--max-window", type=int, default=cfg["max_window"])
    ap.add_argument("--n-known", type=int, default=cfg["n_known"])
    ap.add_argument("--skip-aux-check", action="store_true", help="僅測試用（無 aux 目錄時）")
    args = ap.parse_args()
    raws = sorted(glob.glob(os.path.join(args.src, args.pattern)))
    if not raws:
        raise SystemExit(f"找不到原始主檔：{args.src}/{args.pattern}")
    os.makedirs(args.dst, exist_ok=True)
    man_path = os.path.join(args.dst, "manifest.json")
    manifest = json.load(open(man_path, encoding="utf-8")) if os.path.exists(man_path) else {}
    mw, nk = args.max_window, args.n_known
    for raw in raws:
        name = os.path.basename(raw)
        lines = open(raw, encoding="utf-8").read().splitlines(True)
        wins_raw = {DS.window_of(l) for l in lines} - {None}
        missing = [w for w in range(mw) if w not in wins_raw]
        if missing:
            raise SystemExit(f"✗ 檢查 1：{name} 缺窗 {missing[:10]}（共 {len(missing)}）")
        keep = [l for l in lines if DS.window_of(l) is None or DS.window_of(l) < mw]
        if lines[:len(keep)] != keep:
            raise SystemExit(f"✗ 檢查 2：{name} 之 0–{mw - 1} 窗非原始檔之前綴列（窗順序異常）")
        occ = collections.defaultdict(set)
        for l in keep:
            w = DS.window_of(l)
            if w is not None:
                occ[w].add(int(l.split("\t")[3]))
        if sorted(occ) != list(range(mw)):
            raise SystemExit(f"✗ 檢查 2：{name} 輸出之窗不為 0–{mw - 1}")
        bad = [w for w in occ if len(occ[w]) != nk]
        imsi = set().union(*occ.values())
        if bad or imsi != set(range(1, nk + 1)):
            raise SystemExit(f"✗ 檢查 3：{name} N_total ≠ {nk} 之窗 {sorted(bad)[:10]}；IMSI {sorted(imsi)[:3]}…（{len(imsi)} 個）")
        out = os.path.join(args.dst, name)
        with open(out, "w", encoding="utf-8", newline="") as fh:
            fh.write("".join(keep))
        seed = DS.seed_of(raw)
        if not args.skip_aux_check:
            if not DS.aux_matches_main(seed):
                os.remove(out)
                raise SystemExit(f"✗ 檢查 4：seed {seed} 之 aux DlE2RlcStats 截斷後與輸出不同")
        manifest[name] = {"raw_sha256": sha(raw), "analysis_sha256": sha(out), "raw_windows": len(wins_raw),
                          "analysis_windows": mw, "dropped_windows": sorted(wins_raw - set(range(mw))),
                          "n_known": nk, "aux_check": "skipped" if args.skip_aux_check else "ok"}
        print(f"✓ {name}：原始 {len(wins_raw)} 窗 → 分析 {mw} 窗（捨去 {manifest[name]['dropped_windows']}）；"
              f"每窗 N_total = {nk}；aux {'略過' if args.skip_aux_check else '一致'}")
    json.dump(manifest, open(man_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"寫入 {man_path}")


if __name__ == "__main__":
    main()
