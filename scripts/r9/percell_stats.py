import sys, collections, numpy as np
sys.path.insert(0, '.')
import percell_source as PS
for aux in sys.argv[1:]:
    pc = PS.percell_delta(aux); z = PS.zero_delta(aux)
    tl = PS.traffic_lists(aux, _pc=pc); el = PS.enb_lists(aux); sv = PS.serving(aux)
    si0 = PS.si_windows(aux, zero=False, _pc=pc, _z=z); si1 = PS.si_windows(aux, zero=True, _pc=pc, _z=z)
    nrx = sum(d[2] for k in pc for d in pc[k].values()); nz = sum(d[1] for k in z for d in z[k].values())
    mm_rx = sum(d[2] for k in pc for (c,i,l), d in pc[k].items() if c != 1)
    nz_mm = sum(d[1] for k in z for (c,i,l), d in z[k].items() if c != 1)
    lte_all = sum(1 for k in tl if len(tl[k].get(1, ())) == 30)
    # (B) union over mmWave cells vs (A) union over mmWave cells
    a_mm = [len(set().union(*[v for c, v in el[k].items() if c != 1])) for k in sorted(el)]
    b_mm = [len(set().union(*[v for c, v in tl[k].items() if c != 1] or [set()])) for k in sorted(tl)]
    # UEs with mmWave serving but no mmWave Rx in window
    gap = sum(1 for k in sv for i, (mc, ms) in sv[k].items() if ms == 9 and not any(i in v for c, v in dict(si1[k][1]).items() if c != 1))
    # UE's traffic at a cell other than its serving mmCell
    other = sum(1 for k in tl for c, v in tl[k].items() if c != 1 for i in v if sv.get(k, {}).get(i, (None,))[0] != c)
    cnt_mm = [sum(len(v) for c, v in d.items() if c != 1) for _, d in si0]
    print(aux.split('/')[-1], {
      "zero_delay_share_all": round(nz / nrx, 4), "zero_delay_share_mmWave": round(nz_mm / mm_rx, 4),
      "windows_LTE_traffic_all30": lte_all, "A_mmWave_union_minmax": [min(a_mm), max(a_mm)],
      "B_mmWave_union_minmax": [min(b_mm), max(b_mm)], "connected_but_no_mmWave_Rx_UEwin": gap,
      "mmWave_tx_at_non_serving_cell": other, "Si_UE_entries_mmWave_per_window_minmax": [min(cnt_mm), max(cnt_mm)]})
