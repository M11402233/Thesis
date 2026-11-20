#!/bin/bash
# 第二階段步 2：S_i 於 D-30P 新輸入（規格 docs/thesis/phase2_percell_spec_v0.md §5 步 2、§4、§9.1 Q-P5）。
# 新機器執行（D-30P 在新機器）。程式目錄 CODE（預設 ~/zt_dev/phase2/residuals，與 repo commit 同步之鏡像）。
# VARIANT=percell（主：排除零延遲 PDU）｜percell_zero（對照：含零延遲）。輸出 data/results/d30p_delay_<VARIANT>/。
# 門檻、注入、尺度公式皆不變（Q-P6）；尺度由各腳本依原定義於 D-30P 以 LOSO 重估。
# E13 含融合層（E10.run_policy），移至步 4；E-i 只定義於 D-30（舊凍結尺度），第二階段不跑。
# 任一步失敗即停（硬性規則 5），不調參數。
# 用法：VARIANT=percell setsid nohup bash scripts/run_phase2_step2.sh > /dev/null 2>&1 < /dev/null &
set -u
VARIANT="${VARIANT:?VARIANT=percell|percell_zero}"
case "$VARIANT" in percell|percell_zero) ;; *) echo "VARIANT 不合法"; exit 2 ;; esac
REPO=~/oran-zt-kpm-verification; CODE="${CODE:-$HOME/zt_dev/phase2/residuals}"; PY="${PY:-$HOME/venvs/drl/bin/python}"
# D30P1_r10_recollection_spec.md F5：DATASET=d30p（預設，行為不變）｜d30p1
DATASET="${DATASET:-d30p}"
case "$DATASET" in d30p) P0=$REPO/data/results/phase2/D30P_g13_phase0; GK="P2 P3" ;;
                  d30p1) P0=$REPO/data/results/phase2/D30P1_phase0; GK="Q0 Q2 Q2C Q4 P3" ;; *) echo "DATASET 不合法"; exit 2 ;; esac
export ZT_DATASET=$DATASET ZT_DELAY_SOURCE=$VARIANT ZT_FUSION_ORDER=severity MPLBACKEND=Agg OMP_NUM_THREADS=4
unset ZT_RESULTS_DIR
OUT=$REPO/data/results/${DATASET}_delay_$VARIANT; L=$OUT/_pipeline_logs; mkdir -p $L; ST=$L/status.txt
echo "# step2 DATASET=$DATASET VARIANT=$VARIANT 開始 $(date -u '+%F %T') UTC host=$(hostname) code=$CODE code_md5=$(cd $CODE && find . -name '*.py' -not -path '*/__pycache__/*' | sort | xargs md5sum | md5sum | cut -c1-12)" > $ST
[ -n "${ZT_CODE_COMMIT:-}" ] && echo "# code = repo commit $ZT_CODE_COMMIT（鏡像）" >> $ST
stop() { echo "STOPPED: $1 $(date -u '+%F %T') UTC" >> $ST; exit 1; }
run() { n=$1; shift; s=$(date +%s); (cd $CODE && nice -n 10 $PY "$@") > $L/$n.log 2>&1; rc=$?
        echo "$n exit=$rc $(( $(date +%s)-s ))s" >> $ST; [ $rc -eq 0 ] || stop "$n"; }

# ---- 閘門：第零階段與新輸入層 ----
[ -e $P0/DONE ] || stop "第零階段未完成"
$PY - $P0 $GK >> $ST <<'PY' || stop "第零階段檢查（$GK）未全數通過"
import json, glob, sys
d = sys.argv[1]; r = {}
for p in sys.argv[2:]:
    fs = sorted(glob.glob(f"{d}/{p}_42*.json")); r[p] = [json.load(open(f))["pass"] for f in fs]
print("GATE phase0", {k: f"{sum(v)}/{len(v)}" for k, v in r.items()})
sys.exit(0 if all(len(v) == 8 and all(v) for v in r.values()) else 1)
PY
(cd $CODE && $PY - ) >> $ST <<'PY' || stop "aux 與主檔不一致或新輸入層檢查 X1–X3 未過"
import os, datasets as DS, percell_source as PS
ok = True
for f in DS.files():
    s = DS.seed_of(f); aux = os.path.dirname(DS.aux_path(s, "x")); r = PS.check(aux)
    m = DS.aux_matches_main(s); ok &= m and r["PASS"]
    print(f"GATE seed {s}: aux==main {m}; X1 {r['X1_percell_sum_eq_exact_mismatch']} X2 {r['X2_mismatch']} X3 {r['X3_not_in_enb_list']} PASS {r['PASS']}")
raise SystemExit(0 if ok and len(DS.files()) == 8 else 1)
PY
echo "GATE PASSED $(date -u '+%F %T') UTC" >> $ST

run 01_cv_interval   cv_interval.py
run 02_Si_ablation   run_Si_reference_ablation.py
run 03_E9            run_E9_operating_regime.py
SB=""; [ "${SETBASE:-0}" = 1 ] && SB="--set-baseline"   # 回歸基準：SETBASE=1 時建立（須同時設 ZT_BASELINE_NOTE；結果是否經作者審閱由註記說明）
run 04_E9_rt         run_E9_rt.py $SB
run 05_E9b_rt        run_E9b_rt.py $SB
run 06_E9c_rt        run_E9c_rt.py $SB
run 07_E9d_rt        run_E9d_rt.py $SB
run 08_slow          run_slow_poisoning_suite.py
run 09_slow_rt       run_slow_poisoning_rt.py $SB
run 10_E17           run_slow_poisoning_rt.py --q6-k 1,2,3,4,5
run 11_msweep        run_adversarial_msweep.py
echo "ALLDONE $(date -u '+%F %T') UTC" >> $ST
