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
Observed DL volume (~324 kb/s) was about 2× the nominal ping payload (20 × 1008 B × 8 ≈ 161 kb/s). **Resolved by T3**: in that run two ping streams overlapped (the ping started for the aborted first xApp attempt was still running). With one stream and one subscription, T3 gives 156–164 kb/s.

## Report semantics in OAI — **this build and configuration only** (OAI `1d479b2aa9`, FlexRIC KPM v02.03; not generalised to other OAI versions) (source: `openair2/E2AP/RAN_FUNCTION/O-RAN/ran_func_kpm_subs.c`, `LAYER2/nr_rlc/nr_rlc_entity.c`)
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

## Decision (user, 2026-11-13)
- Current positioning: report-semantics contrast + feasibility evidence (limitations / appendix), not a second dataset.
- Whether to scale up (multi-gNB / multi-UE OAI to strengthen validation, e.g. S_i cross-node) is decided **after phase 1 (S_i interval correction) results**; the user is open to scaling up.

## Follow-up tests (2026-11-13, same setup; logs `data/results/multisim_oai/t*.log`)
| Test | Setup | Observation |
|---|---|---|
| T1 idle UE | no traffic, 1 subscription, 5 indications | The UE is **still listed** (`ran_ue_id = 1`). Volume 0, throughput 0, and `RlcSduDelayDl = 0.00` (**0, not missing**: a window with no samples cannot be told apart from zero delay). First indication = 6,949 kb (increment since the agent's previous "last" value, which carried over from the earlier subscription) |
| T2 two concurrent subscriptions | 1 ping stream (≈161 kb/s nominal), two `xapp_kpm_moni` | xApp A ≈ 123–131 kb/s, xApp B ≈ 32–41 kb/s; **sum ≈ 161** → the shared per-UE "last" counter **splits the increments between subscribers** (uneven). Each subscriber's per-period volume is wrong |
| T3 single subscription | 1 ping stream | 156–164 kb/s per period; delay 338–2,308 μs (last 100 ms) |

Subscription filter in `xapp_kpm_moni` (report style 4): UEs **matching S-NSSAI SST = 1** only (`xapp_kpm_moni.c:300–305`), so UEs on other slices are excluded by design.

## What this check supports and what it does not (wording adopted 2026-11-13)
- **Supported**: a connected UE's identifiers (`amf_ue_ngap_id`, `ran_ue_id`) and its measurements reach an xApp over live E2 every 1 s. "The information C_i needs can be produced by an implementation" — yes.
- **Not supported**: "OAI verifies C_i". Still open:
  - **Idle connected UEs.** Listed in T1, but only on 1 UE and 1 slice.
  - **Partial UE lists.** Subscription conditions can return only some UEs (S-NSSAI filter).
  - **Identity mapping.** How UE identities map across nodes after re-attach or handover is untested.
  - **Missing vs absent.** Whether a missing report can be told apart from a UE that does not exist is untested.
- **Delay start/end points must be compared, not just the window length.** Matching 100 ms vs 1 s does not make two "RLC delay" fields the same quantity. Comparison table (fill before any cross-simulator claim):

| Item | 3GPP `DRB.RlcSduDelayDl` (TS 28.552 §5.1.3.3.3, third-party mirror; official version to check) | OAI (this build) | ns-O-RAN `DlE2RlcStats` delay |
|---|---|---|---|
| SDU or PDU | SDU | SDU (`txsdu_avg_time_to_tx`) | 【待查】 (see `report_semantics_spec_v0.md` §1 F-delay) |
| Start event | SDU arrives at the RLC entry | SDU enters the RLC tx buffer | 【待查】 |
| End event | Last part of the SDU handed to MAC for first transmission | First transmission (time-to-tx) | 【待查】 (Rx event at the UE) |
| Sample weighting | Mean over SDUs | `time_average` over a 100 ms sliding window | Per-PDU running mean |
| Window / report period | Granularity period | Last 100 ms, sampled at a 1 s report | Since t=0, 1 s report |
| Reset / missing / multiple subscriptions | — | No samples → 0.00; volume split across subscribers | Never reset; no new samples → previous mean repeated |
