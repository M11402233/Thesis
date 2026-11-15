#!/bin/bash
# 第一階段 S_i 重跑（規格 docs/thesis/Si_interval_correction_spec_v0.md §2、§6；report_semantics_spec_v0.md §6）。
# MODE=dryrun  ：不經 R-5 驗收閘門；輸出 data/results/phase1_dryrun/d30_delay_reconstructed/，一律為「探索性」（P-2 未過）。
# MODE=official：先跑 R-5 驗收閘門（P-1 R-6、R-5、P-2 Q2、Q-1 尺度對照；任一失敗或 Q-1 旗標即停），
#                再輸出 data/results/d30_delay_reconstructed/；若 dryrun 已存在，最後逐位比對兩者之 JSON。
# 所有結果「以現行 cell 歸屬（最後事件）為條件」。任一步失敗即停（硬性規則 5），不調參數。
# 用法：MODE=dryrun setsid nohup bash scripts/run_phase1_Si.sh > /dev/null 2>&1 < /dev/null &
set -u
MODE="${MODE:?MODE=dryrun|official}"
REPO=~/oran-zt-kpm-verification; RES=$REPO/xapps/verification/residuals; SV=$REPO/data/results/semantics_v0
R5=$REPO/data/r5_runs/seed4200_noauto_t301; REF6=$REPO/data/ues30_seeds/ues30_t300_seed4200.txt
export ZT_DATASET=d30 ZT_DELAY_SOURCE=reconstructed ZT_FUSION_ORDER=severity MPLBACKEND=Agg
case "$MODE" in
  dryrun)   export ZT_RESULTS_DIR=$REPO/data/results/phase1_dryrun/d30; OUT=$REPO/data/results/phase1_dryrun/d30_delay_reconstructed ;;
  official) unset ZT_RESULTS_DIR; OUT=$REPO/data/results/d30_delay_reconstructed ;;
  *) echo "MODE 須為 dryrun 或 official"; exit 2 ;;
esac
L=$OUT/_pipeline_logs; mkdir -p $L; ST=$L/status.txt
echo "# MODE=$MODE 開始 $(date -u '+%F %T') UTC commit $(git -C $REPO rev-parse --short HEAD) dirty=$(git -C $REPO status --porcelain --untracked-files=no | wc -l)" > $ST
[ "$MODE" = dryrun ] && echo "# 探索性：R-5 驗收（P-2）未過前之輸出，不得作為正式結果" >> $ST
stop() { echo "STOPPED: $1 $(date -u '+%F %T') UTC" >> $ST; exit 1; }
run() { n=$1; shift; s=$(date +%s); (cd $RES && nice -n 10 python3 "$@") > $L/$n.log 2>&1; rc=$?
        echo "$n exit=$rc $(( $(date +%s)-s ))s" >> $ST; [ $rc -eq 0 ] || stop "$n"; }

if [ "$MODE" = official ]; then
  pgrep -f "ns-3-mmwave-oran-r5/build/scratch" > /dev/null && stop "R-5 仍在執行"
  awk -F'\t' '$1+0>=299{f=1} END{exit !f}' $R5/DlE2RlcStats.txt || stop "R-5 未含窗 299"
  run G1_R5_R6  check_R5_R6.py $R5 --ref $REF6 --json $SV/R5R6_final.json
  run G2_Q2     check_Q2_acceptance.py $R5 --json $SV/Q2_final.json
  run G3_Q1     check_Q1_scales.py $R5 --json $SV/Q1_scales_final.json
  python3 - $SV/Q1_scales_final.json >> $ST <<'PY' || stop "G3_Q1 旗標（>10 %）：人工複核後才可繼續（使用者 Q-1）"
import json, sys
d = json.load(open(sys.argv[1])); f = {k: d["same_seed_4200"][f"{k}_flag"] for k in ("C1", "C2")}
f.update({f"cross_{k}": d["cross_seed_reconstructed"][k]["flag"] for k in ("C1", "C2")})
import os; ack = set(filter(None, os.environ.get("ZT_G3_ACK", "").split(",")))
print("G3_Q1 flags", f, "user-acknowledged", sorted(ack))
sys.exit(1 if any(v and k not in ack for k, v in f.items()) else 0)
PY
  echo "GATE PASSED $(date -u '+%F %T') UTC${ZT_G3_ACK:+ （G3 旗標經使用者複核接受：$ZT_G3_ACK）}" >> $ST
fi

# E-ii（規格 §6 之順序）
run 01_cv_interval   cv_interval.py
run 02_xapp          zt_kpm_xapp.py --fusion bound --eval-mode all
run 03_Si_ablation   run_Si_reference_ablation.py
run 04_E9            run_E9_operating_regime.py
run 05_E9_rt         run_E9_rt.py
run 06_E9b_rt        run_E9b_rt.py
run 07_E9c_rt        run_E9c_rt.py
run 08_E9d_rt        run_E9d_rt.py
# E-i（舊凍結尺度＋區間輸入；內建 K1／K2）
run 09_Ei            run_Ei_diagnostic.py

if [ "$MODE" = official ] && [ -d $REPO/data/results/phase1_dryrun/d30_delay_reconstructed ]; then
  python3 - $REPO/data/results/phase1_dryrun/d30_delay_reconstructed $OUT >> $ST <<'PY' || stop "official 與 dryrun 之 JSON 不同（確定性破壞，先查）"
import json, os, sys, glob
# 2026-11-15 使用者決定：計時欄位（實際執行時間，本質上每次不同）不納入逐位比對；其餘欄位仍須逐位相同
TIMING = {"mean_ms", "median_ms", "p95_ms", "p99_ms", "max_ms", "us_per_full_eval", "seed_mean_spread_ratio",
          "seed_normalised_spread_ratio", "budget_utilisation_p99", "granularity_utilisation_p99"}
def strip(o):
    if isinstance(o, dict): return {k: strip(v) for k, v in o.items() if k not in TIMING}
    if isinstance(o, list): return [strip(x) for x in o]
    return o
a, b = sys.argv[1:]; bad = []; timing_only = []
for p in sorted(glob.glob(os.path.join(a, "**", "*.json"), recursive=True)):
    q = os.path.join(b, os.path.relpath(p, a)); r = os.path.relpath(p, a)
    if not os.path.exists(q): bad.append(r); continue
    x, y = json.load(open(p)), json.load(open(q))
    if x == y: continue
    (timing_only if strip(x) == strip(y) else bad).append(r)
print("dryrun vs official JSON（排除計時欄位 %s）:" % sorted(TIMING), "identical" if not bad else bad,
      "| 僅計時欄位不同:", timing_only or "none"); sys.exit(1 if bad else 0)
PY
fi
echo "ALLDONE $(date -u '+%F %T') UTC" >> $ST
