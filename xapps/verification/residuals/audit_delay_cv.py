#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""audit_delay_cv.py — 4.7.1 之描述統計：同窗跨 mmWave cell 之延遲離散度與 S_i 證據可用性。

定義（與 zt_kpm_xapp.verify_si 相同之 cell 層級延遲 = 該 cell 當窗各 UE delay 之平均）：
  CV(t) = std(cell 延遲) / mean(cell 延遲)，僅計同窗活躍 mmWave cell ≥ 2 之窗；報告全體窗之中位數與四分位。
轉移：逐 (seed, UE) 統計 serving mmWave cell 是否改變，及改變時中間是否有 LTE-only 窗（4.8.4）。
可用性：以 (節點, 窗) 為單位，peer = 同窗其他活躍 mmWave cell 數；≥ MIN_PEER 為 full consensus。
"""
import os
import json
import collections
import numpy as np
import datasets as DS
import zt_kpm_xapp as X


def main():
    cvs, act, peer = [], collections.Counter(), collections.Counter()
    n_win = 0
    ue_runs = multi = via_lte = direct = 0          # 4.8.4：UE 於單次執行內之 serving mmWave cell 是否改變
    for f in DS.files():
        serving, last_mm, last_was_lte = collections.defaultdict(set), {}, {}
        for w, cells in X.TraceReplaySource(f).windows():
            n_win += 1
            for c, ues in cells.items():
                for i in ues:
                    if c == X.LTE_CELL:
                        last_was_lte[i] = True
                        continue
                    serving[i].add(c)
                    if i in last_mm and last_mm[i] != c:
                        if last_was_lte.get(i):
                            via_lte += 1
                        else:
                            direct += 1
                    last_mm[i] = c; last_was_lte[i] = False
        all_ues = set(serving) | set(last_was_lte)
        ue_runs += len(all_ues); multi += sum(1 for i in serving if len(serving[i]) > 1)
    n_win2 = 0
    for f in DS.files():
        for w, cells in X.TraceReplaySource(f).windows():
            n_win2 += 1
            mm = [c for c in cells if c != X.LTE_CELL]
            act[len(mm)] += 1
            for _ in mm:
                peer[len(mm) - 1] += 1
            if len(mm) >= 2:
                d = np.array([np.mean(list(cells[c].values())) for c in mm])
                if d.mean() > 0:
                    cvs.append(float(d.std() / d.mean()))
    n_node = sum(peer.values())
    full = sum(v for k, v in peer.items() if k >= X.MIN_PEER)
    out = {"dataset": DS.NAME, "windows": n_win, "cv_windows": len(cvs),
           "delay_cv_median": float(np.median(cvs)), "delay_cv_q25": float(np.percentile(cvs, 25)),
           "delay_cv_q75": float(np.percentile(cvs, 75)),
           "windows_by_active_mmwave_cells": {str(k): v for k, v in sorted(act.items())},
           "node_windows": n_node, "node_windows_by_peer": {str(k): v for k, v in sorted(peer.items())},
           "full_consensus_node_windows": full, "full_consensus_share": full / n_node,
           "ue_runs": ue_runs, "ue_runs_with_multiple_serving_mmwave_cells": multi,
           "mmwave_cell_changes_via_lte_window": via_lte, "mmwave_cell_changes_without_lte_window": direct}
    p = os.path.join(DS.results_dir(), "audit_delay_cv.json")
    json.dump(out, open(p, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(json.dumps(out, ensure_ascii=False, indent=1)); print("寫入", p)


if __name__ == "__main__":
    main()
