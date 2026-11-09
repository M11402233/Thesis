#!/bin/bash
# Paper A（第四章，規則版 C-ZT）全部結果之獨立重現（2026-11-09）。
# 以目前 HEAD 之程式，自原始資料重跑 d30 全流程（first-match）與嚴重度序之重跑步驟，
# 輸出至全新目錄 data/results/d30_repro_<tag>/{first-match,severity}，不寫入既有結果目錄。
# 唯一自既有結果複製者：planB_rt_baselines.json（rt 系列之回歸基準，使其逐位比對生效）。
# 任一步驟失敗即停止（硬性規則 5）。結束時（含失敗）恢復被暫停之行程（RESUME_PIDS）。
# 用法：RESUME_PIDS="pid1 pid2" setsid nohup scripts/run_paperA_reproduce.sh <tag> > /dev/null 2>&1 &
TAG=$1; [ -n "$TAG" ] || { echo "usage: $0 <tag>"; exit 2; }
REPO=~/oran-zt-kpm-verification
ROOT=$REPO/data/results/d30_repro_$TAG
[ -e "$ROOT" ] && { echo "$ROOT 已存在，不覆寫"; exit 2; }
trap '[ -n "${RESUME_PIDS:-}" ] && kill -CONT $RESUME_PIDS 2>/dev/null; echo "RESUMED ${RESUME_PIDS:-none} $(date -u "+%F %T") UTC" >> $ROOT/status.txt' EXIT
OUT1=$ROOT/first-match; OUT2=$ROOT/severity
mkdir -p $OUT1/_logs $OUT2/_logs
cp $REPO/data/results/d30/planB_rt_baselines.json $OUT1/
cd $REPO/xapps/verification/residuals || exit 1
ST=$ROOT/status.txt
echo "# 開始 $(date -u '+%F %T') UTC  commit $(git -C $REPO rev-parse --short HEAD)  dirty=$(git -C $REPO status --porcelain -- xapps | wc -l)" > $ST
export ZT_DATASET=d30 MPLBACKEND=Agg PYTHONUNBUFFERED=1
run() { n=$1; shift; s=$(date +%s); nice -n 10 python3 "$@" > $L/$n.log 2>&1; rc=$?
        echo "$PHASE $n exit=$rc $(( $(date +%s)-s ))s" >> $ST
        if [ $rc -ne 0 ]; then echo "STOPPED at $PHASE $n $(date -u '+%F %T') UTC" >> $ST; exit 1; fi; }
# ---- 1. first-match 全流程（同 run_d30_pipeline.sh 之實驗步驟，不含圖）
PHASE=FM; L=$OUT1/_logs; export ZT_RESULTS_DIR=$OUT1; unset ZT_FUSION_ORDER
run 00_audit        audit_Si_data.py
run 01_Si_ablation  run_Si_reference_ablation.py
run 02_Si_exp       run_Si_experiments.py
run 03_xapp         zt_kpm_xapp.py --fusion bound --eval-mode all
run 04_E9           run_E9_operating_regime.py
run 05_E9_rt        run_E9_rt.py
run 06_E9b_rt       run_E9b_rt.py
run 07_E9c_rt       run_E9c_rt.py
run 08_E9d_rt       run_E9d_rt.py
run 09_E13          run_E13_tauS_sensitivity.py
run 10_E13_rt       run_E13_rt.py
run 11_slow         run_slow_poisoning_suite.py
run 12_slow_rt      run_slow_poisoning_rt.py
run 13_E10          run_E10_D1_policy_ablation.py
run 14_RQ3          run_RQ3_decision_replay.py
run 15_E11          run_E11_transitions.py
run 16_E11b         run_E11b_pulses.py
run 17_E12          run_E12_persist.py
run 18_B4           run_B4_used_resources.py
run 19_fusion       run_fusion_replay.py
run 20_msweep       run_adversarial_msweep.py
run 21_Hi           run_Hi_experiments.py
run 22_Hi_D1        run_Hi_D1_performance.py
run 23_Ci           run_Ci_unified.py
run 25_resource_eval        resource_eval_xapp.py --admission strict
run 26_resource_eval_annot  resource_eval_xapp.py --admission restrict_annotated
run 40_E14          run_E14_D1_sensitivity.py
run 41_E15_E16      run_E15_E16_D1_robustness.py
run 42_E17          run_slow_poisoning_rt.py --q6-k 1,2,3,4,5
run 43_E18          resource_eval_xapp.py --attacks
# ---- 2. severity（同 run_fusion_order_check.sh；上游依賴取自本次 first-match 輸出，而非既有結果）
rsync -a --exclude _logs $OUT1/ $OUT2/
PHASE=SEV; L=$OUT2/_logs; export ZT_RESULTS_DIR=$OUT2 ZT_FUSION_ORDER=severity
run 03_xapp         zt_kpm_xapp.py --fusion bound --eval-mode all --fusion-order severity
run 13_E10          run_E10_D1_policy_ablation.py
run 14_RQ3          run_RQ3_decision_replay.py
run 15_E11          run_E11_transitions.py
run 16_E11b         run_E11b_pulses.py
run 17_E12          run_E12_persist.py
run 18_B4           run_B4_used_resources.py
run 19_fusion       run_fusion_replay.py
run 23_Ci           run_Ci_unified.py
run 25_resource_eval        resource_eval_xapp.py --admission strict
run 26_resource_eval_annot  resource_eval_xapp.py --admission restrict_annotated
run 40_E14          run_E14_D1_sensitivity.py
run 41_E15_E16      run_E15_E16_D1_robustness.py
run 43_E18          resource_eval_xapp.py --attacks
echo "ALLDONE $(date -u '+%F %T') UTC" >> $ST
