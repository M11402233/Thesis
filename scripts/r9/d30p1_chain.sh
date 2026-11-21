#!/bin/bash
# D-30P1 re-collection (docs/thesis/D30P1_r10_recollection_spec.md §6.1). r11 (= r10 + effective delay samples) mode 1 + S2, 8 seeds in parallel, then acceptance.
# Stops on any failure (no parameter tuning). Do NOT launch before the user has accepted the checks (6 s trace, 21 s validation, this chain's dry-run).
set -u
REPO=$HOME/oran-zt-kpm-verification; NS=$HOME/ns-3-mmwave-oran-r11
P=$REPO/data/ues30_p_r10_seeds; P6D=$REPO/data/ues30_p_r10_p6check; REFP=$REPO/data/ues30_p_r9g13_seeds
D30A=$REPO/data/ues30_seeds/analysis; [ -d "$D30A" ] || D30A=$HOME/d30_ref
OUT=$REPO/data/results/phase2/D30P1_phase0; mkdir -p $OUT
C1="python3 $REPO/scripts/r9/check_d30p1_phase0.py"; C0="python3 $REPO/scripts/r9/check_d30p_phase0.py"
PY=$HOME/venvs/drl/bin/python; RES=$HOME/zt_dev/p2/xapps/verification/residuals
log() { echo "$(date -u '+%F %T UTC') $*" | tee -a $OUT/summary.txt; }
stop() { log "STOP: $*"; touch $OUT/STOPPED; exit 1; }
# 0. gate: the binary / libraries / sources of the r11 build used by the 6 s trace check (data/r11_trace) and the 21 s validation
#    (data/r11_validation: no real diff vs r10 mode 1; binary.md5 = bed17a3a...)
want="bed17a3a19ccb01ceed45618126f54df build/scratch/ns3.38.rc1-scenario-three-optimized
df97e0b626cd31b4135c9b4d6af70122 build/lib/libns3.38.rc1-lte-optimized.so
37b7dde72a807ab162c423bc74024d6e build/lib/libns3.38.rc1-network-optimized.so
dc7458cac41d1d64c63c3ae14197a9a9 build/lib/libns3.38.rc1-mmwave-optimized.so
18288ceacec84539737ac20716a7087b src/lte/model/lte-rlc-am.cc
52dff17b24670b5abfb8e017d54189e3 src/lte/model/lte-rlc-am.h
1852945c417bc55ace87888ff2c02b29 src/lte/helper/mmwave-bearer-stats-calculator.cc
b7f8667b28d83750f86e1e2873c70b32 src/lte/helper/mmwave-bearer-stats-calculator.h"
while read -r h f; do [ "$(md5sum $NS/$f | cut -d' ' -f1)" = "$h" ] || stop "md5 $f differs from the validated build"; done <<< "$want"
log "gate: r11 build md5 == validated build"
# RESUME_FROM=4（2026-11-21）：收集與逐 seed 驗收已完成且全過（summary 須有 "prepare + Q-2c 8/8"），只續跑第 4 步以後；不重收。
if [ "${RESUME_FROM:-0}" = 4 ]; then
  grep -q "prepare + Q-2c 8/8" $OUT/summary.txt || stop "RESUME_FROM=4 但 summary 無 prepare + Q-2c 8/8"
  [ -e $P6D ] && stop "$P6D exists"
  rm -f $OUT/STOPPED; fail=0; log "RESUME from step 4 (code mirror md5 ${ZT_CODE_MD5:-unset})"
else
[ -e $P ] && [ -n "$(ls -A $P 2>/dev/null)" ] && stop "$P not empty"
[ -e $P6D ] && stop "$P6D exists"
# 1. collect
mkdir -p $P; cd $REPO
for s in 4200 4201 4202 4203 4204 4205 4206 4207; do
  VARIANT=D30P1 ZT_R10_RETX_TAG=1 NS3_DIR=$NS OUT_DIR=$P SEEDS="$s" setsid nohup bash scripts/collect_d30p_r9.sh >> $P/collect_$s.log 2>&1 < /dev/null &
done
log "launched 8 seeds -> $P"; sleep 120
while pgrep -f "[b]ash scripts/collect_d30p_r9.sh" >/dev/null; do sleep 300; done
log "collection finished"
# 2. per-seed acceptance
fail=0
for s in 4200 4201 4202 4203 4204 4205 4206 4207; do
  t=D30P1_ues30_t300_seed$s; A=$P/${t}_aux; R=$REFP/D30P_ues30_t300_seed${s}_aux
  [ -s $P/$t.txt ] || { log "seed $s: NO MAIN OUTPUT; $(tail -3 $P/collect_$s.log | tr '\n' ' ' | cut -c1-300)"; fail=1; continue; }
  grep -q "✓ 通過" $P/collect_$s.log || { log "seed $s: N_total/IMSI check not passed"; fail=1; }
  $C1 q0 $A $NS 1 > $OUT/Q0_$s.json; r0=$?
  $C1 q2 $A $R > $OUT/Q2_$s.json; r2=$?
  $C1 q4 $A > $OUT/Q4_$s.json; r4=$?
  $C0 p3 $A > $OUT/P3_$s.json; r3=$?
  $C0 p5 $A > $OUT/P5_$s.json
  log "seed $s: Q-0 exit $r0, Q-2 exit $r2, Q-4 exit $r4, P-3 exit $r3"
  [ $r0 -eq 0 ] && [ $r2 -eq 0 ] && [ $r4 -eq 0 ] && [ $r3 -eq 0 ] || fail=1
done
[ $fail -eq 0 ] || stop "per-seed acceptance failed (see JSON in $OUT)"
# 3. analysis main (0-299) + Q-2c vs D-30 analysis main
(cd $RES && ZT_DATASET=d30p1 $PY prepare_d30.py) > $OUT/prepare.log 2>&1 || stop "prepare_d30 (d30p1) failed"
for s in 4200 4201 4202 4203 4204 4205 4206 4207; do
  $C1 q2c $P/analysis/D30P1_ues30_t300_seed$s.txt $D30A/ues30_t300_seed$s.txt > $OUT/Q2C_$s.json || fail=1
done
[ $fail -eq 0 ] || stop "Q-2c failed"
log "prepare + Q-2c 8/8"
fi   # end of RESUME_FROM guard
# 4. new-input layer X1-X3 + aux_matches_main
(cd $RES && ZT_DATASET=d30p1 $PY - ) > $OUT/X123.log 2>&1 <<'PY' || stop "X1-X3 / aux_matches_main failed"
import os, datasets as DS, percell_source as PS
ok = True
for f in DS.files():
    s = DS.seed_of(f); aux = os.path.dirname(DS.aux_path(s, "x")); r = PS.check(aux); m = DS.aux_matches_main(s)
    e = PS.check_eff(aux, 299)
    ok &= m and r["PASS"] and e["PASS"]; print(s, "aux==main", m, "PASS", r["PASS"], "X4", e)
raise SystemExit(0 if ok and len(DS.files()) == 8 else 1)
PY
log "X1-X3 + X4 + aux==main 8/8"
# 5. P-6 (31 s short run, seed 4200)
VARIANT=D30P1 ZT_R10_RETX_TAG=1 NS3_DIR=$NS OUT_DIR=$P6D SIMTIME=31 SEEDS=4200 bash scripts/collect_d30p_r9.sh > $OUT/P6_collect.log 2>&1
[ -d $P6D/D30P1_ues30_t300_seed4200_aux ] || stop "P-6 short run produced no aux (see $OUT/P6_collect.log)"
python3 $REPO/scripts/r9/p6_prefix.py $P6D/D30P1_ues30_t300_seed4200_aux $P/D30P1_ues30_t300_seed4200_aux > $OUT/P6_prefix_4200.json; r6=$?
log "P-6 prefix exit $r6"; [ $r6 -eq 0 ] || stop "P-6 failed"
log "ALL DONE"; touch $OUT/DONE
