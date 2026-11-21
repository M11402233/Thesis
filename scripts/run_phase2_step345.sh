#!/bin/bash
# 第二階段步 3–5（phase2_percell_spec_v0.md §5）：H_i、融合與 xApp、准入／可用資源評估／RQ3／E18。
# 順序沿用 run_d30_pipeline.sh 已驗證之依賴順序（RQ3 讀 E10 之輸出；resource_eval 讀 RQ3 與 xApp 之輸出）。
# 尚待使用者決定之項目（E21／E22／E25／E26 之新輸入注入設計；D2 於 D-30H；E20-5）不執行，於狀態檔明列 PENDING。
# 任一步失敗即停（硬性規則 5），不調參數。
# 用法：DATASET=d30p1 VARIANT=percell setsid nohup bash scripts/run_phase2_step345.sh > /dev/null 2>&1 < /dev/null &
set -u
DATASET="${DATASET:?DATASET=d30p|d30p1}"; VARIANT="${VARIANT:?VARIANT=percell|percell_zero|percell_uemed}"
case "$DATASET" in d30p|d30p1) ;; *) echo "DATASET 不合法"; exit 2 ;; esac
case "$VARIANT" in percell|percell_zero|percell_uemed) ;; *) echo "VARIANT 不合法"; exit 2 ;; esac
REPO=~/oran-zt-kpm-verification; CODE="${CODE:-$HOME/zt_dev/p2/xapps/verification/residuals}"; PY="${PY:-$HOME/venvs/drl/bin/python}"
export ZT_DATASET=$DATASET ZT_DELAY_SOURCE=$VARIANT ZT_FUSION_ORDER=severity MPLBACKEND=Agg OMP_NUM_THREADS=4
unset ZT_RESULTS_DIR
OUT=$REPO/data/results/${DATASET}_delay_$VARIANT;
# 乾跑：TESTOUT=<dir> 時寫入 <dir>_delay_<VARIANT>（須先複製步 2 之輸出），不碰正式結果目錄
if [ -n "${TESTOUT:-}" ]; then export ZT_RESULTS_DIR=$TESTOUT; OUT=${TESTOUT}_delay_$VARIANT; fi
L=$OUT/_pipeline_logs_step345; mkdir -p $L; ST=$L/status.txt
echo "# step3-5 DATASET=$DATASET VARIANT=$VARIANT 開始 $(date -u '+%F %T') UTC host=$(hostname) code=$CODE code_md5=$(cd $CODE && find . -name '*.py' -not -path '*/__pycache__/*' | sort | xargs md5sum | md5sum | cut -c1-12)" > $ST
[ -n "${ZT_CODE_COMMIT:-}" ] && echo "# code = repo commit $ZT_CODE_COMMIT（鏡像）" >> $ST
stop() { echo "STOPPED: $1 $(date -u '+%F %T') UTC" >> $ST; exit 1; }
run() { n=$1; shift; s=$(date +%s); (cd $CODE && nice -n 10 $PY "$@") > $L/$n.log 2>&1; rc=$?
        echo "$n exit=$rc $(( $(date +%s)-s ))s" >> $ST; [ $rc -eq 0 ] || stop "$n"; }
# 閘門：步 2 已完成（同資料集、同版本）
grep -q "^ALLDONE" $OUT/_pipeline_logs/status.txt 2>/dev/null || stop "步 2 未完成（$OUT/_pipeline_logs/status.txt）"
echo "GATE step2 ALLDONE ok" >> $ST
run 4a_xapp            zt_kpm_xapp.py --fusion bound --eval-mode all
run 2x_E13             run_E13_tauS_sensitivity.py
SB=""; [ "${SETBASE:-0}" = 1 ] && SB="--set-baseline"   # 同步 2：新資料集之回歸基準（須設 ZT_BASELINE_NOTE）
run 2x_E13_rt          run_E13_rt.py $SB
run 3a_E10             run_E10_D1_policy_ablation.py
run 5a_RQ3             run_RQ3_decision_replay.py
run 4b_E11             run_E11_transitions.py
run 4c_E11b            run_E11b_pulses.py
run 4d_E12             run_E12_persist.py
run 5b_B4              run_B4_used_resources.py
run 4e_fusion          run_fusion_replay.py
run 3b_Hi              run_Hi_experiments.py
run 3c_Hi_D1           run_Hi_D1_performance.py
run 5c_res_strict      resource_eval_xapp.py --admission strict
run 5d_res_annot       resource_eval_xapp.py --admission restrict_annotated
run 3d_E14             run_E14_D1_sensitivity.py
run 3e_E15_E16         run_E15_E16_D1_robustness.py
run 5e_E18             resource_eval_xapp.py --attacks
echo "PENDING (使用者決定)：E21／E22／E25／E26（C_i 改讀 RRC 名單後之注入設計）；D2 於 D-30H；E20-5 PHY 交叉驗證（新 D1）；E20（待步 7 之 E30 eval）" >> $ST
echo "ALLDONE $(date -u '+%F %T') UTC" >> $ST
