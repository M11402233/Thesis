#!/bin/bash
# D-S12 全長收集（12 UE，8 seed 4200–4207 × 301 s，FixedTtt，r11）。舊機器 cindy1，3 個工作者（留 1 核）。
# 動態佇列：工作者以 mkdir 領取 seed，先完成者接下一個。完成後逐 seed 驗收（collector K1–K5/N、Q-0、Q-4、P-3），寫 summary.txt 與 DONE。
# 規格：docs/thesis/DS12_pilot_spec.md；使用者 2026-11-26 確認啟動。驗收失敗只回報，不調參數。
set -u
REPO=$HOME/oran-zt-kpm-verification; NS=$HOME/ns-3-mmwave-oran-r11; OUT=$REPO/data/ues12_ph_r11_seeds; R9=$REPO/scripts/r9
[ -e $OUT ] && { echo "$OUT exists"; exit 1; }; mkdir -p $OUT/_claims
log() { echo "$(date -u '+%F %T UTC') $*" | tee -a $OUT/summary.txt; }
want="bed17a3a19ccb01ceed45618126f54df build/scratch/ns3.38.rc1-scenario-three-optimized
df97e0b626cd31b4135c9b4d6af70122 build/lib/libns3.38.rc1-lte-optimized.so
37b7dde72a807ab162c423bc74024d6e build/lib/libns3.38.rc1-network-optimized.so
dc7458cac41d1d64c63c3ae14197a9a9 build/lib/libns3.38.rc1-mmwave-optimized.so
18288ceacec84539737ac20716a7087b src/lte/model/lte-rlc-am.cc
52dff17b24670b5abfb8e017d54189e3 src/lte/model/lte-rlc-am.h
1852945c417bc55ace87888ff2c02b29 src/lte/helper/mmwave-bearer-stats-calculator.cc
b7f8667b28d83750f86e1e2873c70b32 src/lte/helper/mmwave-bearer-stats-calculator.h"
while read -r h f; do [ "$(md5sum $NS/$f | cut -d' ' -f1)" = "$h" ] || { log "STOP: md5 $f differs"; exit 1; }; done <<< "$want"
log "gate: r11 build md5 OK"; unset ZT_R10_TRACE; cd $REPO
worker() { # id
  for s in 4200 4201 4202 4203 4204 4205 4206 4207; do
    mkdir $OUT/_claims/$s 2>/dev/null || continue
    log "worker $1 start seed $s"
    VARIANT=DS12 HO_MODE=FixedTtt ZT_R10_RETX_TAG=1 NS3_DIR=$NS OUT_DIR=$OUT SIMTIME=301 SEEDS=$s RATE=300 bash scripts/collect_ds12_r11.sh > $OUT/collect_$s.log 2>&1
    log "worker $1 finished seed $s (exit $?)"
  done
}
worker A & sleep 20; worker B & sleep 20; worker C & wait
log "all collectors finished; per-seed acceptance"
fail=0
for s in 4200 4201 4202 4203 4204 4205 4206 4207; do
  a=$OUT/DS12_ues12_t300_seed${s}_aux
  ok_log=0; grep -q '✓ 通過' $OUT/collect_$s.log 2>/dev/null && ok_log=1
  python3 $R9/check_d30p1_phase0.py q0 $a $NS 1 >/dev/null 2>&1; r0=$?
  python3 $R9/check_d30p1_phase0.py q4 $a >/dev/null 2>&1; r4=$?
  python3 $R9/check_d30p_phase0.py p3 $a >/dev/null 2>&1; r3=$?
  log "seed $s: K1K5_N=$ok_log Q0=$r0 Q4=$r4 P3=$r3 (0=pass)"
  [ $ok_log = 1 ] && [ $r0 = 0 ] && [ $r4 = 0 ] && [ $r3 = 0 ] || fail=1
done
log "acceptance fail=$fail (0 = all pass)"; touch $OUT/DONE
