#!/bin/bash
# r11t: seed 4200, simTime=6, D-30P command line, mode 1. Two runs of the SAME binary and length: on (ZT_R10_TRACE=1) / off.
set -u
BIN=$HOME/ns-3-mmwave-oran-r11t/build/scratch/ns3.38.rc1-scenario-three-optimized
OUT=$HOME/oran-zt-kpm-verification/data/r11_trace
[ -x "$BIN" ] || { echo no binary; exit 1; }
[ -e "$OUT" ] && { echo "$OUT exists"; exit 1; }
mkdir -p "$OUT/on" "$OUT/off"; echo "VALIDATION_ONLY r11t trace on/off (2026-11-20)" > "$OUT/README_VALIDATION_ONLY.txt"
for v in on off; do
  tr=0; [ $v = on ] && tr=1
  ( cd "$OUT/$v" && if [ $tr = 1 ]; then export ZT_R10_TRACE=1; fi; ZT_R7_S2=1 ZT_R10_RETX_TAG=1 nice -n 10 /usr/bin/time -f "maxrss_kb=%M wall_s=%e" \
    "$BIN" --RngRun=4200 --simTime=6 --totalUes=30 --e2nrEnabled=true --configuration=1 --minSpeed=3 --maxSpeed=10 \
    --indicationPeriodicity=1.0 --heuristicType=-1 > run.log 2>&1 ) &
done
wait
echo "ALLDONE $(date '+%F %T')" > "$OUT/DONE"
# 對照：r11t 關閉追蹤之輸出須與 r10t 關閉追蹤（同長度、模式 1）逐位相同（移除掛鐘欄，同 P-2），僅多 _r11eff 檔
REF=$HOME/oran-zt-kpm-verification/data/r10_trace_v4_dec/off
cd "$OUT/off"; n=0
for f in $(ls | grep -v "^run.log$" | grep -v r11eff); do
  case $f in bsState.txt) ca='awk {$2="";print}';; cu-*|du-cell-*) ca='cut -d, -f2-';; *) ca=cat;; esac
  cmp -s <($ca "$f") <($ca "$REF/$f") || { echo "REAL_DIFF_VS_R10T $f"; n=$((n+1)); }
done > "$OUT/cmp_vs_r10t.txt"
echo "real diffs vs r10t: $n; files $(ls | grep -vc '^run.log$') (r11eff $(ls | grep -c r11eff)) vs ref $(ls $REF | grep -vc '^run.log$')" >> "$OUT/cmp_vs_r10t.txt"
