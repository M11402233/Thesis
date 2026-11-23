#!/bin/bash
# D-50PH 全長收集與逐 seed 驗收（docs/thesis/D50PH_collection_spec.md）。r11（凍結 md5）＋ FixedTtt ＋ S2 ＋ 模式 1，50 UE，8 seed 同時，301 s。
# 任一失敗即停（不調參數）。只負責「收集＋接收檢查＋P-6」；分析用主檔與結果分析另議。
set -u
REPO=$HOME/oran-zt-kpm-verification; NS=$HOME/ns-3-mmwave-oran-r11
P=$REPO/data/ues50_ph_r11_seeds; PIL=$REPO/data/pilot_d50/ho
OUT=$REPO/data/results/phase2/D50PH_phase0; mkdir -p $OUT
C1="python3 $REPO/scripts/r9/check_d30p1_phase0.py"; C0="python3 $REPO/scripts/r9/check_d30p_phase0.py"
log() { echo "$(date -u '+%F %T UTC') $*" | tee -a $OUT/summary.txt; }
stop() { log "STOP: $*"; touch $OUT/STOPPED; exit 1; }
unset ZT_R10_TRACE
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
python3 -c "import json,sys;d=json.load(open('$REPO/data/pilot_d50/decision.json'));sys.exit(0 if d['valid'] and d['verdict']=='明顯縮小' else 1)" || stop "pilot decision not valid/shrinks"
for s in 4200 4201 4202 4203; do [ -d $PIL/D50PH_ues50_t300_seed${s}_aux ] || stop "no pilot short run for seed $s (P-6 reference)"; done
[ -e $P ] && [ -n "$(ls -A $P 2>/dev/null)" ] && stop "$P not empty"
mkdir -p $P; cd $REPO
for s in 4200 4201 4202 4203 4204 4205 4206 4207; do
  VARIANT=D50PH HO_MODE=FixedTtt RATE=1000 ZT_R10_RETX_TAG=1 NS3_DIR=$NS OUT_DIR=$P SEEDS="$s" setsid nohup bash scripts/collect_d50ph_r11.sh >> $P/collect_$s.log 2>&1 < /dev/null &
done
log "launched 8 seeds -> $P"; sleep 120
while pgrep -f "[b]ash scripts/collect_d50ph_r11.sh" >/dev/null; do sleep 300; done
log "collection finished"
fail=0
for s in 4200 4201 4202 4203 4204 4205 4206 4207; do
  t=D50PH_ues50_t300_seed$s; A=$P/${t}_aux
  [ -s $P/$t.txt ] || { log "seed $s: NO MAIN OUTPUT; $(tail -3 $P/collect_$s.log | tr '\n' ' ' | cut -c1-300)"; fail=1; continue; }
  grep -q "✓ 通過" $P/collect_$s.log || { log "seed $s: N_total/IMSI check not passed"; fail=1; }
  $C1 q0 $A $NS 1 > $OUT/Q0_$s.json; r0=$?
  $C1 q4 $A > $OUT/Q4_$s.json; r4=$?
  $C0 p3 $A > $OUT/P3_$s.json; r3=$?
  $C0 p5 $A > $OUT/P5_$s.json
  r6=n/a
  if [ -d $PIL/${t}_aux ]; then python3 $REPO/scripts/r9/p6_prefix.py $PIL/${t}_aux $A 31 > $OUT/P6_prefix_$s.json; r6=$?; fi
  log "seed $s: Q-0 exit $r0, Q-4 exit $r4, P-3 exit $r3, P-6 exit $r6"
  [ $r0 -eq 0 ] && [ $r4 -eq 0 ] && [ $r3 -eq 0 ] && { [ "$r6" = n/a ] || [ "$r6" = 0 ]; } || fail=1
done
[ $fail -eq 0 ] || stop "per-seed acceptance failed (see JSON in $OUT)"
log "per-seed acceptance 8/8"; log "ALL DONE"; touch $OUT/DONE
