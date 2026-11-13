# Multi-simulator check: OAI SA + FlexRIC live E2 KPM (2026-11-13)

> Status: **functional check only (1 UE, rfsim, 10 indications)**. Not thesis data, no numbers from here enter chapter 4.

## Setup (old machine 10.10.10.136)
- OAI CN5G (docker compose, 10 containers healthy); AMF 192.168.70.132.
- OAI gNB `nr-softmodem` (openairinterface5g `1d479b2aa9`, 2025-03-26), band 78, 106 PRB, numerology 1, `--rfsim`, E2 agent E2AP_V2 / KPM_V2_03.
- FlexRIC nearRT-RIC + `xapp_kpm_moni` (build `~/flexric_build_e2apv2_kpmv203_gcc13`), SM dir = OAI-tree KPM v02.03 `.so` (passing the default v03.00 SM aborts in `kpm_dec_ind_hdr_asn`: version mismatch, fixed with `-p <sm2>`).
- nrUE (host binary in ubuntu:18.04 container, host loader), IMSI 001010000000001; registered, PDU session 10.0.0.2.
- DL traffic: `ping -i 0.05 -s 1000` from `oai-ext-dn` to the UE.
- Raw logs: `data/results/multisim_oai/`.

## Result
Per-UE KPM rows obtained over live E2 every 1 s (`period_ms = 1000`), 10 indications:

| ind | PdcpSduVolumeDL [kb] | RlcSduDelayDl [μs] | UEThpDl [kbps] | PrbTotDl |
|---|---|---|---|---|
| 1 | 2598 | 660.75 | 2614.95 | 12574 |
| 2 | 328 | 513.00 | 330.88 | 530 |
| 3 | 320 | 1578.75 | 322.63 | 508 |
| 4 | 328 | 909.25 | 330.88 | 532 |
| 5 | 320 | 2137.50 | 322.61 | 485 |
| 6–10 | 320–328 | 280.25–679.25 | 322.6–330.9 | 462–508 |

Indication 1 = everything since attach (first difference against zero), then per-period values.
Observed DL volume (~324 kb/s) is about 2× the nominal ping payload (20 × 1008 B × 8 ≈ 161 kb/s); **not explained**, not investigated.

## Report semantics in OAI (source: `openair2/E2AP/RAN_FUNCTION/O-RAN/ran_func_kpm_subs.c`, `LAYER2/nr_rlc/nr_rlc_entity.c`)
| KPM | OAI semantics | vs ns-O-RAN DlE2RlcStats |
|---|---|---|
| `DRB.PdcpSduVolumeDL` | difference of cumulative PDCP bytes against a **static per-UE-index "last" value in the E2 agent** (interval, consumer-side differencing) | counts cumulative since t=0 |
| `DRB.UEThpDl` | RLC tx PDU bytes difference / `gran_period_ms` | — |
| `DRB.RlcSduDelayDl` | `time_average` over the **last 100 ms** of RLC SDU sojourn (`nr_rlc_entity.c:142–145`), sampled at report time | running mean since t=0 |
| `RRU.PrbTotDl` | difference against last total PRBs | (ns-3 `RRU.PrbUsedDl`, per report) |

Implications (to be weighed, not yet decided):
1. Neither simulator gives "per-window mean delay over the 1 s window": ns-3 = since t=0, OAI = last 100 ms. The semantics spec v0.1 D-b definition (interval mean per window) is satisfied by neither out of the box.
2. OAI's "last" counters are global per UE index inside the agent: two subscriptions would split the increments between them (the per-consumer-differencing concern in spec v0.1 §3 applies here too). Not tested.
3. Useful as a cross-check that a real E2 stack produces per-UE rows at 1 s with UE IDs (`amf_ue_ngap_id`, `ran_ue_id`); C_i-style UE-set reconciliation is feasible in principle. Multi-UE and multi-cell not tested (rfsim, 1 gNB, 1 UE).
