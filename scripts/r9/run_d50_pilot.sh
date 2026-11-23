#!/bin/bash
# D-50PH 小型換手試跑（docs/thesis/D50PH_pilot_spec.md）。只寫 data/pilot_d50（診斷，不併入正式資料）。
set -u
REPO=$HOME/oran-zt-kpm-verification; NS=$HOME/ns-3-mmwave-oran-r11; OUT=$REPO/data/pilot_d50
log() { echo "$(date -u '+%F %T UTC') $*" | tee -a $OUT/summary.txt; }
[ -e $OUT ] && { echo "$OUT exists"; exit 1; }; mkdir -p $OUT/ho $OUT/na $OUT/det
echo "DIAGNOSTIC_ONLY D-50PH pilot (2026-11-23); not thesis data; spec D50PH_pilot_spec.md" > $OUT/README_DIAGNOSTIC_ONLY.txt
want="bed17a3a19ccb01ceed45618126f54df build/scratch/ns3.38.rc1-scenario-three-optimized
df97e0b626cd31b4135c9b4d6af70122 build/lib/libns3.38.rc1-lte-optimized.so
37b7dde72a807ab162c423bc74024d6e build/lib/libns3.38.rc1-network-optimized.so
dc7458cac41d1d64c63c3ae14197a9a9 build/lib/libns3.38.rc1-mmwave-optimized.so
18288ceacec84539737ac20716a7087b src/lte/model/lte-rlc-am.cc
52dff17b24670b5abfb8e017d54189e3 src/lte/model/lte-rlc-am.h
1852945c417bc55ace87888ff2c02b29 src/lte/helper/mmwave-bearer-stats-calculator.cc
b7f8667b28d83750f86e1e2873c70b32 src/lte/helper/mmwave-bearer-stats-calculator.h"
while read -r h f; do [ "$(md5sum $NS/$f | cut -d' ' -f1)" = "$h" ] || { log "STOP: md5 $f differs"; exit 1; }; done <<< "$want"
log "gate: r11 build md5 == validated build"; unset ZT_R10_TRACE; cd $REPO
job() { # arm mode seed
  ( VARIANT=D50PH HO_MODE=$2 ZT_R10_RETX_TAG=1 NS3_DIR=$NS OUT_DIR=$OUT/$1 SIMTIME=31 SEEDS=$3 RATE=900 bash scripts/collect_d50ph_r11.sh > $OUT/$1/collect_$3.log 2>&1 ) &
}
for s in 4200 4201 4202 4203; do job ho FixedTtt $s; job na NoAuto $s; done; job det FixedTtt 4200
log "launched 9 runs (ho x4, na x4, det x1), 31 s, 50 UE"; wait; log "runs finished"
~/venvs/drl/bin/python scripts/r9/d50_pilot_report.py $OUT $NS > $OUT/report.log 2>&1; rc=$?
log "report exit $rc (0 = valid & shrinks, 2 = valid but not 'shrinks', 1 = invalid); see $OUT/decision.json"
touch $OUT/DONE
