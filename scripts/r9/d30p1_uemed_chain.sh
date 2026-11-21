#!/bin/bash
# D-30P1 S_i UE 層級（中位數）版之步 2 → 步 3–5（docs/thesis/D30P1_si_uemed_spec.md；使用者 2026-11-22 決定）。
# 程式鏡像 CODE（預設 ~/zt_dev/p4，= ZT_CODE_COMMIT）；啟動時與結束前各核對一次 md5。任一步失敗即停，不調參數。
# 回歸基準：新目錄首次建立（SETBASE=1；註記「未經作者審閱」）。
set -u
REPO=$HOME/oran-zt-kpm-verification; PY=$HOME/venvs/drl/bin/python
export CODE="${CODE:-$HOME/zt_dev/p4/xapps/verification/residuals}" PY
LOG=$REPO/data/results/phase2/D30P1_uemed_chain.log; V=percell_uemed; O=$REPO/data/results/d30p1_delay_$V
log() { echo "$(date -u '+%F %T UTC') $*" >> $LOG; }
stop() { log "STOP: $*"; exit 1; }
COMMIT="${ZT_CODE_COMMIT:?須設定 ZT_CODE_COMMIT}"
md5now() { (cd $CODE && find . -name '*.py' -not -path '*/__pycache__/*' | LC_ALL=C sort | xargs md5sum | md5sum | cut -c1-32); }
[ "$(md5now)" = "${ZT_CODE_MD5:?須設定 ZT_CODE_MD5}" ] || stop "程式鏡像 md5 不符"
[ -e $O ] && stop "輸出目錄已存在（$O），不覆寫"
export ZT_CODE_COMMIT=$COMMIT ZT_BASELINE_NOTE="D-30P1 percell_uemed（S_i UE 中位數）於 $(date -u '+%F') 建立，結果未經作者審閱"
log "start V=$V code=$CODE commit=$COMMIT"
DATASET=d30p1 VARIANT=$V SETBASE=1 bash $REPO/scripts/run_phase2_step2.sh
grep -q "^ALLDONE" $O/_pipeline_logs/status.txt || stop "步 2 未完成（見 $O/_pipeline_logs/status.txt）"
log "步 2 ALLDONE"
DATASET=d30p1 VARIANT=$V SETBASE=1 bash $REPO/scripts/run_phase2_step345.sh
grep -q "^ALLDONE" $O/_pipeline_logs_step345/status.txt || stop "步 3–5 未完成（見 $O/_pipeline_logs_step345/status.txt）"
[ "$(md5now)" = "$ZT_CODE_MD5" ] || stop "程式鏡像於執行中變動"
log "步 3–5 ALLDONE"; touch $REPO/data/results/phase2/D30P1_UEMED_STEPS_2_5_DONE
