#!/bin/bash
# D-30P phase-2 step 0 acceptance (P-2, P-3, P-5, then P-6). Waits for collect_d30p_r9.sh; read-only on D-30P / D-30 ref.
REPO=$HOME/oran-zt-kpm-verification; P=$REPO/data/ues30_p_r9_seeds; REF=$HOME/d30_ref
OUT=$REPO/data/results/phase2/D30P_phase0; mkdir -p $OUT; S="python3 $REPO/scripts/r9/check_d30p_phase0.py"
log() { echo "$(date -u '+%F %T UTC') $*" | tee -a $OUT/summary.txt; }
while pgrep -f "bash scripts/collect_d30p_r9.sh" >/dev/null; do sleep 120; done
log "D-30P collection finished; starting P-2/P-3/P-5"
for s in 4200 4201 4202 4203 4204 4205 4206 4207; do
  t=D30P_ues30_t300_seed$s; A=$P/${t}_aux
  if [ ! -s $P/$t.txt ]; then log "seed $s: NO MAIN OUTPUT"; continue; fi
  k=$(grep -c . $A/check_r9_outputs.err 2>/dev/null); log "seed $s: K1-K5 json $(test -s $A/check_r9_outputs.json && echo present || echo MISSING), stderr lines ${k:-NA}; tail of collect log: $(tail -2 $P/collect_$s.log | tr '\n' ' ' | cut -c1-200)"
  $S p2 $A $P/$t.txt $REF/ues30_t300_seed${s}_aux $REF/ues30_t300_seed$s.txt > $OUT/P2_$s.json; log "seed $s: P-2 exit $?"
  $S p3 $A > $OUT/P3_$s.json; log "seed $s: P-3 exit $?"
  $S p5 $A > $OUT/P5_$s.json; log "seed $s: P-5 exit $?"
done
log "starting P-6 run (seed 4200, simTime 31)"
cd $REPO && OUT_DIR=$REPO/data/ues30_p_r9_p6check SIMTIME=31 SEEDS=4200 bash scripts/collect_d30p_r9.sh > $OUT/P6_collect.log 2>&1
$S p6 $REPO/data/ues30_p_r9_p6check/D30P_ues30_t300_seed4200_aux $P/D30P_ues30_t300_seed4200_aux > $OUT/P6_4200.json; log "P-6 exit $?"
log "ALL DONE"; touch $OUT/DONE
