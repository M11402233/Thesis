#!/usr/bin/env bash
# 依序執行多個「VARIANT:SEED」項目（每項呼叫一次 collect_stage3.sh）。規格 docs/thesis/E19_stage3_data_spec.md §6。
# 用法：ITEMS="S3-TM3:4200 S3-U20:4201" setsid nohup bash scripts/run_stage3_instance.sh >> data/game_stage3/collect_A.log 2>&1 < /dev/null &
# 3 實例平行（使用者 2026-11-07 同意）。順序：先 S3-TM3，後 S3-U20。
cd "$(dirname "$0")/.." || exit 1
for it in ${ITEMS:?}; do
  v=${it%%:*}; s=${it##*:}
  echo "## $(date -u '+%F %T') UTC  開始 ${v} seed ${s}"
  VARIANT=$v SEEDS=$s bash scripts/collect_stage3.sh
  echo "## $(date -u '+%F %T') UTC  結束 ${v} seed ${s}"
done
echo "## INSTANCE DONE $(date -u '+%F %T') UTC"
