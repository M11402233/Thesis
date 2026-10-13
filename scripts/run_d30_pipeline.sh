#!/bin/bash
# D-30 完整實驗流程（ZT_DATASET=d30，輸出至 data/results/d30/）。
# 順序依 CLAUDE.md；任何實驗步驟失敗即停止（硬性規則 5：不調參數讓檢查通過）。圖檔步驟失敗只記錄、不中止。
# 用法：setsid nohup scripts/run_d30_pipeline.sh > /dev/null 2>&1 &
REPO=~/oran-zt-kpm-verification
cd $REPO/xapps/verification/residuals || exit 1
export ZT_DATASET=d30 MPLBACKEND=Agg
L=$REPO/data/results/d30/_pipeline_logs
mkdir -p $L; ST=$L/status.txt
echo "# 開始 $(date -u '+%F %T') UTC  commit $(git -C $REPO rev-parse --short HEAD)" > $ST
run() { n=$1; shift; s=$(date +%s); nice -n 10 python3 "$@" > $L/$n.log 2>&1; rc=$?
        echo "$n exit=$rc $(( $(date +%s)-s ))s" >> $ST
        if [ $rc -ne 0 ]; then echo "STOPPED at $n $(date -u '+%F %T') UTC" >> $ST; exit 1; fi; }
fig() { n=$1; shift; s=$(date +%s); nice -n 10 python3 "$@" > $L/$n.log 2>&1
        echo "$n exit=$? $(( $(date +%s)-s ))s (fig, non-fatal)" >> $ST; }
run 00_audit        audit_Si_data.py
run 01_Si_ablation  run_Si_reference_ablation.py      # E9 之檢查依賴其輸出
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
run 25_resource_eval        resource_eval_xapp.py --admission strict              # 須在 RQ3 與 xApp 之後（內建檢查讀其輸出）
run 26_resource_eval_annot  resource_eval_xapp.py --admission restrict_annotated
# 補充實驗（規格 docs/thesis/E15_E18_supplementary_spec.md）：皆有「重現既有輸出」之內建檢查
run 40_E14          run_E14_D1_sensitivity.py
run 41_E15_E16      run_E15_E16_D1_robustness.py
run 42_E17          run_slow_poisoning_rt.py --q6-k 1,2,3,4,5
run 43_E18          resource_eval_xapp.py --attacks
fig 30_fig_Hi_grading make_fig_Hi_D1_grading.py
fig 31_fig_Hi_H1_H4   make_fig_Hi_H1_H4.py
fig 32_fig_Ci         make_fig_Ci_unified.py --tag unified
fig 33_fig_E13_rt     make_fig_E13_rt.py
fig 34_fig_lstm_rt    make_fig_lstm_rt.py
echo "ALLDONE $(date -u '+%F %T') UTC" >> $ST
