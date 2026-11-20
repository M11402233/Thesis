#!/bin/bash
# r11 21 s 驗證：seed 4200、simTime=21、D-30P 命令列、ZT_R7_S2=1、ZT_R10_RETX_TAG=1（r11 正式二進位，無追蹤）。
# 輸出 data/r11_validation/mode1（僅驗證用）；與 data/r10_validation/mode1 逐檔比對（移除掛鐘欄，同 P-2），僅准多出 _r11eff 檔。
set -u
BIN=$HOME/ns-3-mmwave-oran-r11/build/scratch/ns3.38.rc1-scenario-three-optimized
OUT=$HOME/oran-zt-kpm-verification/data/r11_validation; REF=$HOME/oran-zt-kpm-verification/data/r10_validation/mode1
[ -x "$BIN" ] || { echo "no binary"; exit 1; }
[ -e "$OUT" ] && { echo "$OUT exists"; exit 1; }
mkdir -p "$OUT/mode1"; echo "VALIDATION_ONLY (r11 21 s, 2026-11-20); not thesis data" > "$OUT/README_VALIDATION_ONLY.txt"
md5sum "$BIN" > "$OUT/binary.md5"
( cd "$OUT/mode1" && ZT_R7_S2=1 ZT_R10_RETX_TAG=1 nice -n 10 /usr/bin/time -f "maxrss_kb=%M wall_s=%e" \
   "$BIN" --RngRun=4200 --simTime=21 --totalUes=30 --e2nrEnabled=true --configuration=1 --minSpeed=3 --maxSpeed=10 \
   --indicationPeriodicity=1.0 --heuristicType=-1 ) > "$OUT/mode1/run.log" 2>&1
cd "$OUT/mode1"; n=0
for f in $(ls | grep -v "^run.log$" | grep -v r11eff); do
  case $f in bsState.txt) ca='awk {$2="";print}';; cu-*|du-cell-*) ca='cut -d, -f2-';; *) ca=cat;; esac
  cmp -s <($ca "$f") <($ca "$REF/$f") || { echo "REAL_DIFF_VS_R10_MODE1 $f"; n=$((n+1)); }
done > "$OUT/cmp_vs_r10_mode1.txt"
echo "real diffs vs r10 mode1: $n; files $(ls | grep -vc '^run.log$') (r11eff $(ls | grep -c r11eff)) vs ref $(ls $REF | grep -vc '^run.log$'); r11 $(tail -n1 run.log) | r10 $(tail -n1 $REF/run.log)" >> "$OUT/cmp_vs_r10_mode1.txt"
echo "ALLDONE $(date '+%F %T')" > "$OUT/DONE"
