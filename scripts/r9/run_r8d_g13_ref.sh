#!/bin/bash
# D30P1_ho_pilot_spec.md §8a：r8d（g++-13）31 s 參照 → G2′-g13（閘門）與 I-c（資訊）。只寫 data/r11c_ho/ref_g13_* 與 G2g13_*／Ic_*。
set -u
B=$HOME/ns-3-mmwave-oran-r8d-g13/build/scratch/ns3.38.rc1-scenario-three-optimized
REPO=$HOME/oran-zt-kpm-verification; OUT=$REPO/data/r11c_ho; OFF=$REPO/data/ues30_ho_r8d_seeds; ST=$OUT/status_g13.txt
[ -x "$B" ] || { echo "no binary"; exit 1; }
for s in 4200 4201 4202 4203; do [ -e "$OUT/ref_g13_$s" ] && { echo "ref_g13_$s exists"; exit 1; }; done
md5sum "$B" > "$OUT/binary_g13.md5"
echo "start $(date -u '+%F %T') UTC" > "$ST"
for s in 4200 4201 4202 4203; do
  mkdir -p "$OUT/ref_g13_$s"
  ( cd "$OUT/ref_g13_$s" && ZT_R7_S2=1 nice -n 10 /usr/bin/time -f "maxrss_kb=%M wall_s=%e" "$B" --RngRun=$s --simTime=31 \
      --totalUes=30 --e2nrEnabled=true --trafficModel=0 --handoverMode=FixedTtt \
      --configuration=1 --minSpeed=3 --maxSpeed=10 --indicationPeriodicity=1.0 --heuristicType=-1 > run.log 2>&1 ) &
done
wait
echo "runs done $(date -u '+%F %T') UTC" >> "$ST"
EXCL='^(DlE2RlcStats(Lte)?(_exact|_percell|_r9rx)?\.txt|DlRlcStats\.txt|R7b_rlc_rx_tag_hist\.txt|du-cell-[0-9]+\.txt|.*_r11eff\.txt)(\.gz)?$'
for s in 4200 4201 4202 4203; do
  python3 $REPO/scripts/r9/p6_prefix.py "$OUT/stage_$s" "$OUT/ref_g13_$s" 31 > "$OUT/G2g13_$s.json" && echo "G2g13 $s PASS" >> "$ST" || echo "G2g13 $s FAIL" >> "$ST"
  mkdir -p "$OUT/stageref_$s"
  for f in $(ls "$OUT/ref_g13_$s"); do b=${f%.gz}; A=$OFF/D30H_ues30_t300_seed${s}_aux
    [ "$f" = run.log ] && continue; echo "$f" | grep -qE "$EXCL" && continue
    [ ! -e "$A/$f" ] && [ ! -e "$A/$b" ] && [ ! -e "$A/$b.gz" ] && continue
    ln -s "$OUT/ref_g13_$s/$f" "$OUT/stageref_$s/$f"; done
  python3 $REPO/scripts/r9/p6_prefix.py "$OUT/stageref_$s" "$OFF/D30H_ues30_t300_seed${s}_aux" 31 > "$OUT/Ic_$s.json"; echo "Ic $s rc=$?" >> "$ST"
done
echo "ALLDONE $(date -u '+%F %T') UTC" >> "$ST"
