#!/bin/bash
# r10 small validation: seed 4200, simTime=21, D-30P command line, ZT_R7_S2=1; modes 0/1/2 of ZT_R10_RETX_TAG in parallel (niced).
# Output: data/r10_validation/mode{0,1,2}/ (PROBE/validation only - not thesis data)
set -u
NS3=$HOME/ns-3-mmwave-oran-r10; BIN=$NS3/build/scratch/ns3.38.rc1-scenario-three-optimized
OUT=$HOME/oran-zt-kpm-verification/data/r10_validation
[ -x "$BIN" ] || { echo "no binary"; exit 1; }
mkdir -p "$OUT"; echo "VALIDATION_ONLY (r10 small check, 2026-11-20); not thesis data" > "$OUT/README_VALIDATION_ONLY.txt"
for m in 0 1 2; do
  wd=$OUT/mode$m; [ -e "$wd" ] && { echo "mode$m exists, skip"; continue; }
  mkdir -p "$wd"
  ( cd "$wd" && ZT_R7_S2=1 ZT_R10_RETX_TAG=$m exec nice -n 10 /usr/bin/time -f "maxrss_kb=%M wall_s=%e" \
      "$BIN" --RngRun=4200 --simTime=21 --totalUes=30 --e2nrEnabled=true --configuration=1 --minSpeed=3 --maxSpeed=10 \
      --indicationPeriodicity=1.0 --heuristicType=-1 ) > "$wd/run.log" 2>&1 &
done
wait
echo "ALLDONE $(date '+%F %T')" > "$OUT/DONE"
