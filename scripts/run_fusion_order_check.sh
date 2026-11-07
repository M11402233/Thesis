#!/bin/bash
# 融合順序修正之 C1／C2／C4 檢查（規格 docs/thesis/fusion_severity_order_spec.md）。
# 用法：setsid nohup scripts/run_fusion_order_check.sh <first-match|severity> > /dev/null 2>&1 &
# 輸出：data/results/d30_fusion_order/<order>/（先複製 d30/ 之既有輸出作為上游依賴，再重跑所有經 fuse 之步驟）。
# 不寫入 data/results/d30/。任一步驟失敗即停止（硬性規則 5）。
ORDER=$1; [ "$ORDER" = first-match ] || [ "$ORDER" = severity ] || { echo "usage: $0 first-match|severity"; exit 2; }
REPO=~/oran-zt-kpm-verification
cd $REPO/xapps/verification/residuals || exit 1
OUT=$REPO/data/results/d30_fusion_order/$ORDER
[ -e "$OUT" ] && { echo "$OUT 已存在，不覆寫"; exit 2; }
mkdir -p "$OUT"
rsync -a --exclude _pipeline_logs $REPO/data/results/d30/ "$OUT"/
export ZT_DATASET=d30 ZT_RESULTS_DIR="$OUT" ZT_FUSION_ORDER=$ORDER MPLBACKEND=Agg
L=$OUT/_logs; mkdir -p $L; ST=$L/status.txt
echo "# 開始 $(date -u '+%F %T') UTC  commit $(git -C $REPO rev-parse --short HEAD)  order=$ORDER" > $ST
run() { n=$1; shift; s=$(date +%s); nice -n 10 python3 "$@" > $L/$n.log 2>&1; rc=$?
        echo "$n exit=$rc $(( $(date +%s)-s ))s" >> $ST
        if [ $rc -ne 0 ]; then echo "STOPPED at $n $(date -u '+%F %T') UTC" >> $ST; exit 1; fi; }
run 03_xapp         zt_kpm_xapp.py --fusion bound --eval-mode all --fusion-order $ORDER
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
