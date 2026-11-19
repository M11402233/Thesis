#!/bin/bash
# D-30P re-collection with r9 built by g++-13 (user decision 2026-11-19, option B; docs/thesis/D30P_phase0_results.md).
# Chain: wait build -> 2 s gate (seed 4202) -> 8 seeds in parallel -> phase-0 checks (P-2/P-3/P-5/P-6). Stops on any gate failure.
set -u
REPO=$HOME/oran-zt-kpm-verification; NS=$HOME/ns-3-mmwave-oran-r9-g13; G=$HOME/g13gate
P=$REPO/data/ues30_p_r9g13_seeds; P6D=$REPO/data/ues30_p_r9g13_p6check; REF=$HOME/d30_ref
OUT=$REPO/data/results/phase2/D30P_g13_phase0; mkdir -p $OUT $G
S="python3 $REPO/scripts/r9/check_d30p_phase0.py"
log() { echo "$(date -u '+%F %T UTC') $*" | tee -a $OUT/summary.txt; }
# 1. build
while [ ! -e $HOME/build_r9g13.status ]; do sleep 60; done
st=$(cat $HOME/build_r9g13.status); log "build status: $st; $(grep -E '^(SOURCE IDENTICAL|build rc|GCC|KEY)' $HOME/build_r9g13.log | tr '\n' ' ' | cut -c1-1500)"
[ "$st" = OK ] || { log "STOP: build failed"; touch $OUT/STOPPED; exit 1; }
BIN=$NS/build/scratch/ns3.38.rc1-scenario-three-optimized
readelf -p .comment $NS/build/lib/libns3.38.rc1-mmwave-optimized.so | grep -q 'GCC: (Ubuntu 13.4' || { log "STOP: lib not built by GCC 13.4"; touch $OUT/STOPPED; exit 1; }
# 2. gate (2 s, seed 4202; first gcc11 difference was at line 28,096 / t=0.48 s)
rm -rf $G/probe_g13; mkdir -p $G/probe_g13; cd $G/probe_g13
ZT_R7_S2=1 timeout 3000 $BIN --RngRun=4202 --simTime=2 --totalUes=30 --e2nrEnabled=true --configuration=1 --minSpeed=3 --maxSpeed=10 --indicationPeriodicity=1.0 --heuristicType=-1 > run.log 2>&1; rc=$?
log "gate probe exit $rc"
python3 $G/dir_equal.py $G/probe_g13 $G/probe_r9_old > $OUT/G1_probe_vs_r9old.json; g1=$(python3 -c "import json;print(json.load(open('$OUT/G1_probe_vs_r9old.json'))['pass'])")
cmp <(head -n 112374 $G/probe_g13/RxPacketTrace.txt) <(zcat $REF/ues30_t300_seed4202_aux/RxPacketTrace.txt.gz | head -n 112374) > $OUT/G2.txt 2>&1 && g2=True || g2=False
log "G1 (all files == old-machine r9 gcc13 probe): $g1 ; G2 (RxPacketTrace == D-30 to line 112374): $g2"
[ $rc -eq 0 ] && [ "$g1" = True ] && [ "$g2" = True ] || { log "STOP: gate failed"; touch $OUT/STOPPED; exit 1; }
# 3. collect 8 seeds in parallel
mkdir -p $P; cd $REPO
for s in 4200 4201 4202 4203 4204 4205 4206 4207; do NS3_DIR=$NS OUT_DIR=$P SEEDS="$s" setsid nohup bash scripts/collect_d30p_r9.sh >> $P/collect_$s.log 2>&1 < /dev/null & done
log "launched 8 seeds -> $P"; sleep 120
while pgrep -f "bash scripts/collect_d30p_r9.sh" >/dev/null; do sleep 300; done
log "collection finished; starting P-2/P-3/P-5"
for s in 4200 4201 4202 4203 4204 4205 4206 4207; do
  t=D30P_ues30_t300_seed$s; A=$P/${t}_aux
  if [ ! -s $P/$t.txt ]; then log "seed $s: NO MAIN OUTPUT"; continue; fi
  k=$(grep -c . $A/check_r9_outputs.err 2>/dev/null); log "seed $s: K1-K5 json $(test -s $A/check_r9_outputs.json && echo present || echo MISSING), stderr lines ${k:-NA}; $(tail -2 $P/collect_$s.log | tr '\n' ' ' | cut -c1-200)"
  $S p2 $A $P/$t.txt $REF/ues30_t300_seed${s}_aux $REF/ues30_t300_seed$s.txt > $OUT/P2_$s.json; log "seed $s: P-2 exit $?"
  $S p3 $A > $OUT/P3_$s.json; log "seed $s: P-3 exit $?"
  $S p5 $A > $OUT/P5_$s.json; log "seed $s: P-5 exit $?"
done
log "starting P-6 run (seed 4200, simTime 31)"
NS3_DIR=$NS OUT_DIR=$P6D SIMTIME=31 SEEDS=4200 bash scripts/collect_d30p_r9.sh > $OUT/P6_collect.log 2>&1
$S p6 $P6D/D30P_ues30_t300_seed4200_aux $P/D30P_ues30_t300_seed4200_aux > $OUT/P6_4200.json; log "P-6 (auto checker, known EOF mis-flag) exit $?"
python3 $REPO/scripts/r9/p6_prefix.py $P6D/D30P_ues30_t300_seed4200_aux $P/D30P_ues30_t300_seed4200_aux > $OUT/P6_prefix_4200.json; log "P-6 prefix check written"
log "ALL DONE"; touch $OUT/DONE
