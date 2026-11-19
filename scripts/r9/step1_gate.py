#!/usr/bin/env python3
"""D-30P（GCC 13）phase-0 結果 → 是否可自動進入第二階段步 1。任一不符 → pass=false（不得進入）。
判準：8 seed 主檔存在、K1–K5 通過、stderr 0；P-2、P-3 pass；P-5 未對應 0；
P-6 前綴核對之非前綴檔 ⊆ GCC 11 批人工核對已接受之 22 檔（D30P_phase0_results.md §P-6）。"""
import json, os, sys
OUT, P = sys.argv[1], sys.argv[2]
ACCEPT = {'DlE2PdcpStatsLte.txt', 'DlE2PdcpStatsLte_exact.txt', 'DlE2PdcpStatsLte_percell.txt', 'DlE2PdcpStatsLte_r9lastset.txt',
          'DlE2PdcpStatsLte_r9rx.txt', 'DlE2RlcStatsLte.txt', 'DlE2RlcStatsLte_exact.txt', 'DlE2RlcStatsLte_percell.txt',
          'DlE2RlcStatsLte_r9lastset.txt', 'DlE2RlcStatsLte_r9rx.txt', 'DlPdcpStats.txt', 'DlPhyTransmissionTrace.txt', 'DlRlcStats.txt',
          'EnbSchedAllocTraces.txt', 'MmWaveSinrTime.txt', 'R7b_rlc_rx_tag_hist.txt', 'RlcAmBufferSize.txt', 'RxPacketTrace.txt',
          'UlE2RlcStatsLte.txt', 'UlRlcStats.txt', 'X2Stats.txt', 'bsState.txt'}
bad = []
def J(p):
    try: return json.load(open(p))
    except Exception as e: bad.append(f"{os.path.basename(p)} unreadable ({e.__class__.__name__})"); return {}
if os.path.exists(os.path.join(OUT, "STOPPED")): bad.append("chain STOPPED")
for s in range(4200, 4208):
    t = f"D30P_ues30_t300_seed{s}"; A = os.path.join(P, t + "_aux")
    if not os.path.getsize(os.path.join(P, t + ".txt")) if os.path.exists(os.path.join(P, t + ".txt")) else True: bad.append(f"{s}: no main output")
    log = open(os.path.join(P, f"collect_{s}.log"), errors="replace").read() if os.path.exists(os.path.join(P, f"collect_{s}.log")) else ""
    if "K1–K5 通過" not in log: bad.append(f"{s}: K1–K5 not passed")
    err = os.path.join(A, "check_r9_outputs.err")
    if os.path.exists(err) and open(err).read().strip(): bad.append(f"{s}: check_r9 stderr not empty")
    if J(os.path.join(OUT, f"P2_{s}.json")).get("pass") is not True: bad.append(f"{s}: P-2 not pass")
    if J(os.path.join(OUT, f"P3_{s}.json")).get("pass") is not True: bad.append(f"{s}: P-3 not pass")
    p5 = J(os.path.join(OUT, f"P5_{s}.json"))
    if p5.get("ue_rrc_unmatched") != 0 or p5.get("uemap_unmatched") != 0: bad.append(f"{s}: P-5 unmatched != 0")
p6 = J(os.path.join(OUT, "P6_prefix_4200.json"))
extra = sorted(set(p6.get("not_prefix", {"<missing>": 1})) - ACCEPT)
if extra: bad.append(f"P-6 non-prefix files outside accepted set: {extra}")
res = {"pass": not bad, "failed": bad}
print(json.dumps(res, ensure_ascii=False, indent=1)); sys.exit(0 if not bad else 1)
