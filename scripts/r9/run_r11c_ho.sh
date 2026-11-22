#!/bin/bash
# D-30P1 有換手之小型驗證（docs/thesis/D30P1_ho_pilot_spec.md；結果出來前寫定）。只寫 data/r11c_ho（僅診斷，不得併入正式資料）。
set -u
BC=$HOME/ns-3-mmwave-oran-r11c/build/scratch/ns3.38.rc1-scenario-three-optimized
BF=$HOME/ns-3-mmwave-oran-r11/build/scratch/ns3.38.rc1-scenario-three-optimized
REPO=$HOME/oran-zt-kpm-verification; OUT=$REPO/data/r11c_ho; OFF=$REPO/data/ues30_ho_r8d_seeds
[ -x "$BC" ] && [ -x "$BF" ] || { echo "no binary"; exit 1; }
[ -e "$OUT" ] && { echo "$OUT exists"; exit 1; }
mkdir -p "$OUT"; echo "DIAGNOSTIC_ONLY r11c handover pilot (2026-11-22); not thesis data; spec D30P1_ho_pilot_spec.md" > "$OUT/README_DIAGNOSTIC_ONLY.txt"
md5sum "$BC" "$BF" > "$OUT/binary.md5"
CMD="--totalUes=30 --e2nrEnabled=true --configuration=1 --minSpeed=3 --maxSpeed=10 --indicationPeriodicity=1.0 --heuristicType=-1 --handoverMode=FixedTtt"
run() { # dir binary trace simtime seed
  mkdir -p "$OUT/$1"
  ( cd "$OUT/$1" && if [ "$3" = 1 ]; then export ZT_R10_TRACE=1; fi; ZT_R7_S2=1 ZT_R10_RETX_TAG=1 nice -n 10 /usr/bin/time -f "maxrss_kb=%M wall_s=%e" \
     "$2" --RngRun=$5 --simTime=$4 $CMD > run.log 2>&1 ) &
}
echo "start $(date -u '+%F %T') UTC" > "$OUT/status.txt"
run g0f_formal6 "$BF" 0 6 4200; run g0c_off6 "$BC" 0 6 4200; run g1_on6 "$BC" 1 6 4200
for s in 4200 4201 4202 4203; do run main_$s "$BC" 1 31 $s; done
wait
echo "runs done $(date -u '+%F %T') UTC" >> "$OUT/status.txt"
ca() { case $1 in bsState.txt) awk '{$2="";print}' "$2";; cu-*|du-cell-*) cut -d, -f2- "$2";; *) cat "$2";; esac; }
TR='^(R10_trace\.txt|R10_trace_calc\.txt|R11C_rrc\.txt|R11C_rlf\.txt|run\.log)$'
# G0′
n=0; for f in $(ls "$OUT/g0f_formal6" | grep -vE "$TR"); do cmp -s <(ca $f "$OUT/g0c_off6/$f") <(ca $f "$OUT/g0f_formal6/$f") || { echo "G0_DIFF $f"; n=$((n+1)); }; done > "$OUT/G0.txt"
extra=$(ls "$OUT/g0c_off6" | grep -cE '^(R10_trace|R11C_)'); nf=$(ls "$OUT/g0c_off6" | grep -vcE "$TR"); nr=$(ls "$OUT/g0f_formal6" | grep -vcE "$TR")
echo "G0 diffs=$n files=$nf ref=$nr trace_files_when_off=$extra" >> "$OUT/G0.txt"
[ $n = 0 ] && [ $nf = $nr ] && [ $extra = 0 ] && echo "G0 PASS" >> "$OUT/status.txt" || echo "G0 FAIL" >> "$OUT/status.txt"
# G1′
n=0; for f in $(ls "$OUT/g0c_off6" | grep -vE "$TR"); do cmp -s <(ca $f "$OUT/g1_on6/$f") <(ca $f "$OUT/g0c_off6/$f") || { echo "G1_DIFF $f"; n=$((n+1)); }; done > "$OUT/G1.txt"
nf=$(ls "$OUT/g1_on6" | grep -vcE "$TR"); echo "G1 diffs=$n files=$nf" >> "$OUT/G1.txt"
[ $n = 0 ] && [ $nf = $(ls "$OUT/g0c_off6" | grep -vcE "$TR") ] && echo "G1 PASS" >> "$OUT/status.txt" || echo "G1 FAIL" >> "$OUT/status.txt"
# G2′：追蹤檔移出；只比對規格 §3 之範圍（排除 Q-2 允許清單、r11 新增檔、D-30H 正式輸出所無之檔）
EXCL='^(DlE2RlcStats(Lte)?(_exact|_percell|_r9rx)?\.txt|DlRlcStats\.txt|R7b_rlc_rx_tag_hist\.txt|du-cell-[0-9]+\.txt|.*_r11eff\.txt)(\.gz)?$'
for s in 4200 4201 4202 4203; do
  mkdir -p "$OUT/trace_$s" "$OUT/stage_$s"; for f in R10_trace.txt R10_trace_calc.txt R11C_rrc.txt R11C_rlf.txt; do [ -e "$OUT/main_$s/$f" ] && mv "$OUT/main_$s/$f" "$OUT/trace_$s/"; done
  A=$OFF/D30H_ues30_t300_seed${s}_aux; : > "$OUT/G2_excluded_$s.txt"
  for f in $(ls "$OUT/main_$s"); do
    b=${f%.gz}
    if [ "$f" = run.log ]; then continue; fi
    if echo "$f" | grep -qE "$EXCL"; then echo "$f (allowlist/r11)" >> "$OUT/G2_excluded_$s.txt"; continue; fi
    if [ ! -e "$A/$f" ] && [ ! -e "$A/$b" ] && [ ! -e "$A/$b.gz" ]; then echo "$f (absent in D-30H)" >> "$OUT/G2_excluded_$s.txt"; continue; fi
    ln -s "$OUT/main_$s/$f" "$OUT/stage_$s/$f"
  done
  python3 $REPO/scripts/r9/p6_prefix.py "$OUT/stage_$s" "$A" 31 > "$OUT/G2_$s.json"; rc=$?
  [ $rc = 0 ] && echo "G2 $s PASS" >> "$OUT/status.txt" || echo "G2 $s FAIL" >> "$OUT/status.txt"
done
echo "ALLDONE $(date -u '+%F %T') UTC" >> "$OUT/status.txt"
