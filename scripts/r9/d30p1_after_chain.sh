#!/bin/bash
# D-30P1 收集鏈完成後之接續（phase2_percell_spec_v0.md §5 步 1–5；D30P1_r10_recollection_spec.md）。
# 步 1 之呼叫方式同 D-30P（step1_auto.sh：不設 ZT_DATASET，程式內預設 d30），以便逐項比對。
# 等 d30p1_chain.sh 之 DONE（STOPPED 即結束）→ 步 1 C_i（須與 D-30P 之 step1_Ci 除 meta 外完全相同：C_i 不用延遲，
# 非延遲檔已由 Q-2 保證逐位相同）→ 步 2（percell、percell_zero）→ 步 3–5（percell、percell_zero）。任一失敗即停，不調參數。
# 回歸基準：新資料集首次建立（SETBASE=1；註記「建立，結果未經作者審閱」；規格 F6）。步 6（閒置機器）、步 7（PSRO）不在此。
set -u
REPO=$HOME/oran-zt-kpm-verification; CODE=$HOME/zt_dev/p2/xapps/verification/residuals; PY=$HOME/venvs/drl/bin/python
P0=$REPO/data/results/phase2/D30P1_phase0; S1=$REPO/data/results/phase2/D30P1_step1_Ci
LOG=$REPO/data/results/phase2/D30P1_after_chain.log
log() { echo "$(date -u '+%F %T UTC') $*" >> $LOG; }
stop() { log "STOP: $*"; exit 1; }
COMMIT="${ZT_CODE_COMMIT:?須設定 ZT_CODE_COMMIT（鏡像對應之 repo commit）}"
log "waiting for D-30P1 chain (DONE/STOPPED in $P0); code mirror $CODE = commit $COMMIT"
while [ ! -e $P0/DONE ] && [ ! -e $P0/STOPPED ]; do
  pgrep -f "[d]30p1_chain.sh" >/dev/null || { sleep 60; [ -e $P0/DONE ] || [ -e $P0/STOPPED ] || stop "chain died without DONE/STOPPED"; }
  sleep 600
done
[ -e $P0/STOPPED ] && stop "chain STOPPED（見 $P0/summary.txt）"
log "chain DONE"
# 鏡像未被改動（與啟動時相同）
NOW=$(cd $CODE && find . -name '*.py' -not -path '*/__pycache__/*' | LC_ALL=C sort | xargs md5sum | md5sum | cut -c1-32)
[ "$NOW" = "${ZT_CODE_MD5:?須設定 ZT_CODE_MD5}" ] || stop "程式鏡像已變動（$NOW ≠ $ZT_CODE_MD5）"
export ZT_CODE_COMMIT=$COMMIT ZT_BASELINE_NOTE="D-30P1（r11）於 $(date -u '+%F') 建立，結果未經作者審閱" CODE PY
# 步 1
mkdir -p $S1
(cd $CODE && env -u ZT_DATASET ZT_FUSION_ORDER=severity $PY run_Ci_phase2.py --aux "$REPO/data/ues30_p_r10_seeds/D30P1_ues30_t300_seed42??_aux" --out $S1 --tag d30p1) > $S1/run.log 2>&1 || stop "步 1 run_Ci_phase2 失敗"
python3 - $S1/Ci_phase2_d30p1.json $REPO/data/results/phase2/step1_Ci/Ci_phase2_d30p.json > $S1/compare_vs_d30p.txt 2>&1 <<'PY' || stop "步 1 與 D-30P 之 C_i 結果不同（C_i 不應受延遲修正影響）"
import json, sys
a, b = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
ka, kb = set(a) - {"meta"}, set(b) - {"meta"}
diff = sorted(k for k in ka | kb if a.get(k) != b.get(k))
print("keys", sorted(ka), "differing", diff); sys.exit(1 if diff or ka != kb else 0)
PY
touch $S1/STEP1_DONE; log "步 1 完成：與 D-30P 除 meta 外相同"
# 步 2
for V in percell percell_zero; do
  DATASET=d30p1 VARIANT=$V SETBASE=1 bash $REPO/scripts/run_phase2_step2.sh
  grep -q "^ALLDONE" $REPO/data/results/d30p1_delay_$V/_pipeline_logs/status.txt || stop "步 2 $V 未完成（見 d30p1_delay_$V/_pipeline_logs/status.txt）"
  log "步 2 $V ALLDONE"
done
# 步 3–5
for V in percell percell_zero; do
  DATASET=d30p1 VARIANT=$V SETBASE=1 bash $REPO/scripts/run_phase2_step345.sh
  grep -q "^ALLDONE" $REPO/data/results/d30p1_delay_$V/_pipeline_logs_step345/status.txt || stop "步 3–5 $V 未完成（見 _pipeline_logs_step345/status.txt）"
  log "步 3–5 $V ALLDONE"
done
log "ALL STEPS 1–5 DONE（步 6、7 待使用者）"; touch $REPO/data/results/phase2/D30P1_STEPS_1_5_DONE
