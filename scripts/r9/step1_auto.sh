#!/bin/bash
# 第二階段步 1 自動化（使用者 2026-11-19 授權）：等 D-30P（GCC 13）chain 結束 → step1_gate.py → 全部通過才跑 C_i（run_Ci_phase2.py）。
# 任一不符即停止、寫 STEP1_NOT_STARTED，不重試、不調參數。只跑步 1；步 2 起須使用者看過結果。
set -u
REPO=$HOME/oran-zt-kpm-verification; DEV=$HOME/zt_dev
OUT=$REPO/data/results/phase2/D30P_g13_phase0; P=$REPO/data/ues30_p_r9g13_seeds
S1=$REPO/data/results/phase2/step1_Ci; mkdir -p $S1
log() { echo "$(date -u '+%F %T UTC') $*" | tee -a $S1/auto.log; }
log "waiting for D-30P chain (DONE/STOPPED in $OUT)"
while [ ! -e $OUT/DONE ] && [ ! -e $OUT/STOPPED ]; do
  pgrep -f d30p_g13_chain.sh >/dev/null || { sleep 60; [ -e $OUT/DONE ] || [ -e $OUT/STOPPED ] || { log "STOP: chain died without DONE/STOPPED"; touch $S1/STEP1_NOT_STARTED; exit 1; }; }
  sleep 300
done
python3 $DEV/step1_gate.py $OUT $P > $S1/gate.json; g=$?
log "gate exit $g: $(tr -d '\n' < $S1/gate.json | cut -c1-600)"
[ $g -eq 0 ] || { log "STOP: gate failed — step 1 not started"; touch $S1/STEP1_NOT_STARTED; exit 1; }
cd $DEV/residuals
ZT_FUSION_ORDER=severity nice -n 10 ~/venvs/drl/bin/python run_Ci_phase2.py --aux "$P/D30P_ues30_t300_seed42??_aux" --out $S1 --tag d30p > $S1/run.log 2>&1; r=$?
log "run_Ci_phase2 exit $r; $(tail -3 $S1/run.log | tr '\n' ' ' | cut -c1-300)"
[ $r -eq 0 ] && { touch $S1/STEP1_DONE; log "STEP 1 DONE — waiting for user review before step 2"; } || { touch $S1/STEP1_FAILED; log "STOP: step 1 check failed"; }
