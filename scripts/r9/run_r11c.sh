#!/bin/bash
# D-30P1 因果驗證（docs/thesis/D30P1_causal_maxretx_spec.md §5）。只觀測；輸出 data/r11c_causal（僅診斷，不得併入正式資料）。
#  G0：r11c 追蹤關閉 6 s == r11t 追蹤關閉 6 s（data/r11_trace/off）→ patch 關閉時不改行為
#  G1：r11c 追蹤開啟 6 s 之非追蹤檔 == G0 輸出 → 追蹤開啟時不改行為
#  主跑：seed 4200–4203（事先固定，不依結果挑選）、simTime=31、追蹤開啟、D-30P1 命令列
#  G2：主跑之非追蹤檔為 D-30P1 正式 300 s 輸出之前綴（p6_prefix.py，SIMTIME_SHORT=31）→ 主跑重現正式資料
set -u
BIN=$HOME/ns-3-mmwave-oran-r11c/build/scratch/ns3.38.rc1-scenario-three-optimized
REPO=$HOME/oran-zt-kpm-verification; OUT=$REPO/data/r11c_causal; OFF6=$REPO/data/r11_trace/off; FULL=$REPO/data/ues30_p_r10_seeds
[ -x "$BIN" ] || { echo "no binary"; exit 1; }
[ -e "$OUT" ] && { echo "$OUT exists"; exit 1; }
mkdir -p "$OUT"; echo "DIAGNOSTIC_ONLY r11c causal check (2026-11-22); not thesis data; spec D30P1_causal_maxretx_spec.md" > "$OUT/README_DIAGNOSTIC_ONLY.txt"
md5sum "$BIN" $HOME/ns-3-mmwave-oran-r11c/build/lib/libns3.38.rc1-{lte,network,mmwave}-optimized.so > "$OUT/binary.md5"
cp $HOME/ns-3-mmwave-oran-r11c/r11c_*.diff "$OUT/"
CMD="--totalUes=30 --e2nrEnabled=true --configuration=1 --minSpeed=3 --maxSpeed=10 --indicationPeriodicity=1.0 --heuristicType=-1"
run() { # dir trace simtime seed
  mkdir -p "$OUT/$1"
  ( cd "$OUT/$1" && if [ "$2" = 1 ]; then export ZT_R10_TRACE=1; fi; ZT_R7_S2=1 ZT_R10_RETX_TAG=1 nice -n 10 /usr/bin/time -f "maxrss_kb=%M wall_s=%e" \
     "$BIN" --RngRun=$4 --simTime=$3 $CMD > run.log 2>&1 ) &
}
echo "start $(date -u '+%F %T') UTC" > "$OUT/status.txt"
run g0_off6 0 6 4200; run g1_on6 1 6 4200
for s in 4200 4201 4202 4203; do run main_$s 1 31 $s; done
wait
echo "runs done $(date -u '+%F %T') UTC" >> "$OUT/status.txt"
ca() { case $1 in bsState.txt) awk '{$2="";print}' "$2";; cu-*|du-cell-*) cut -d, -f2- "$2";; *) cat "$2";; esac; }
TR='^(R10_trace\.txt|R10_trace_calc\.txt|R11C_rrc\.txt|R11C_rlf\.txt|run\.log)$'
# G0
n=0; for f in $(ls "$OUT/g0_off6" | grep -vE "$TR"); do cmp -s <(ca $f "$OUT/g0_off6/$f") <(ca $f "$OFF6/$f") || { echo "G0_DIFF $f"; n=$((n+1)); }; done > "$OUT/G0.txt"
extra=$(ls "$OUT/g0_off6" | grep -cE '^(R10_trace|R11C_)'); nf=$(ls "$OUT/g0_off6" | grep -vcE "$TR"); nr=$(ls "$OFF6" | grep -vcE "$TR")
echo "G0 diffs=$n files=$nf ref=$nr trace_files_when_off=$extra" >> "$OUT/G0.txt"
[ $n = 0 ] && [ $nf = $nr ] && [ $extra = 0 ] && echo "G0 PASS" >> "$OUT/status.txt" || echo "G0 FAIL" >> "$OUT/status.txt"
# G1
n=0; for f in $(ls "$OUT/g0_off6" | grep -vE "$TR"); do cmp -s <(ca $f "$OUT/g1_on6/$f") <(ca $f "$OUT/g0_off6/$f") || { echo "G1_DIFF $f"; n=$((n+1)); }; done > "$OUT/G1.txt"
nf=$(ls "$OUT/g1_on6" | grep -vcE "$TR")
echo "G1 diffs=$n files=$nf" >> "$OUT/G1.txt"
[ $n = 0 ] && [ $nf = $(ls "$OUT/g0_off6" | grep -vcE "$TR") ] && echo "G1 PASS" >> "$OUT/status.txt" || echo "G1 FAIL" >> "$OUT/status.txt"
# G2（追蹤檔移出後比對前綴）
for s in 4200 4201 4202 4203; do
  mkdir -p "$OUT/trace_$s"; for f in R10_trace.txt R10_trace_calc.txt R11C_rrc.txt R11C_rlf.txt; do [ -e "$OUT/main_$s/$f" ] && mv "$OUT/main_$s/$f" "$OUT/trace_$s/"; done
  python3 $REPO/scripts/r9/p6_prefix.py "$OUT/main_$s" "$FULL/D30P1_ues30_t300_seed${s}_aux" 31 > "$OUT/G2_$s.json"; rc=$?
  [ $rc = 0 ] && echo "G2 $s PASS" >> "$OUT/status.txt" || echo "G2 $s FAIL" >> "$OUT/status.txt"
done
echo "ALLDONE $(date -u '+%F %T') UTC" >> "$OUT/status.txt"
