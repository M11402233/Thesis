#!/bin/bash
# D-S12（12 UE）小型試跑（docs/thesis/DS12_pilot_spec.md）。只寫 data/pilot_s12（診斷，不併入正式資料）。
# 舊機器（cindy1，Xeon 4110，4 核）：3 個模擬同時（ho 4200、ho 4201、det 4200），留 1 核給系統。
set -u
REPO=$HOME/oran-zt-kpm-verification; NS=$HOME/ns-3-mmwave-oran-r11; OUT=$REPO/data/pilot_s12
log() { echo "$(date -u '+%F %T UTC') $*" | tee -a $OUT/summary.txt; }
[ -e $OUT ] && { echo "$OUT exists"; exit 1; }; mkdir -p $OUT/ho $OUT/det
echo "DIAGNOSTIC_ONLY D-S12 pilot (2026-11-26); not thesis data; spec DS12_pilot_spec.md" > $OUT/README_DIAGNOSTIC_ONLY.txt
# 閘門：與新機器 r11（D-50PH 所用）之二進位、函式庫、原始碼 md5 完全相同（複製所得，非重新建置）
want="bed17a3a19ccb01ceed45618126f54df build/scratch/ns3.38.rc1-scenario-three-optimized
df97e0b626cd31b4135c9b4d6af70122 build/lib/libns3.38.rc1-lte-optimized.so
37b7dde72a807ab162c423bc74024d6e build/lib/libns3.38.rc1-network-optimized.so
dc7458cac41d1d64c63c3ae14197a9a9 build/lib/libns3.38.rc1-mmwave-optimized.so
18288ceacec84539737ac20716a7087b src/lte/model/lte-rlc-am.cc
52dff17b24670b5abfb8e017d54189e3 src/lte/model/lte-rlc-am.h
1852945c417bc55ace87888ff2c02b29 src/lte/helper/mmwave-bearer-stats-calculator.cc
b7f8667b28d83750f86e1e2873c70b32 src/lte/helper/mmwave-bearer-stats-calculator.h"
while read -r h f; do [ "$(md5sum $NS/$f | cut -d' ' -f1)" = "$h" ] || { log "STOP: md5 $f differs"; exit 1; }; done <<< "$want"
log "gate: r11 build md5 == validated build (copied from new machine)"; unset ZT_R10_TRACE; cd $REPO
job() { # arm seed
  ( VARIANT=DS12 HO_MODE=FixedTtt ZT_R10_RETX_TAG=1 NS3_DIR=$NS OUT_DIR=$OUT/$1 SIMTIME=31 SEEDS=$2 RATE=3000 bash scripts/collect_ds12_r11.sh > $OUT/$1/collect_$2.log 2>&1 ) &
}
job ho 4200; job ho 4201; job det 4200
log "launched 3 runs (ho 4200, ho 4201, det 4200), 31 s, 12 UE"; wait; log "runs finished"
python3 scripts/r9/ds12_pilot_report.py $OUT $NS > $OUT/report.log 2>&1; rc=$?
log "report exit $rc (0 = all acceptance checks passed, 1 = invalid); see $OUT/decision.json"
touch $OUT/DONE
