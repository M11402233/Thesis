#!/usr/bin/env bash
# R-5／R-6 驗收 run（語意規格 v0.1 §5.2–5.3、§8.1 Q4）：R-5 旁路輸出版 ns-3（~/ns-3-mmwave-oran-r5，patch 見 scripts/ns3_patches/r5_side_channel.diff），
# 命令列與 D-30（scripts/collect_ues30.sh）完全相同。只寫入 data/r5_runs/<TAG>/。前 30 窗兼作功能檢查。
# 用法：SEED=4200 TAG=seed4200_noauto_t301 setsid nohup bash scripts/run_r5_noauto.sh > /dev/null 2>&1 < /dev/null &
set -u
SEED="${SEED:-4200}"; SIMTIME="${SIMTIME:-301}"; TAG="${TAG:-seed${SEED}_noauto_t${SIMTIME}}"; GUARD_MB="${GUARD_MB:-600}"
NS3_DIR="${HOME}/ns-3-mmwave-oran-r5"; BIN="${NS3_DIR}/build/scratch/ns3.38.rc1-scenario-three-optimized"
OUT="${HOME}/oran-zt-kpm-verification/data/r5_runs/${TAG}"; mkdir -p "${OUT}"; cd "${OUT}" || exit 1
ARGS="--RngRun=${SEED} --simTime=${SIMTIME} --totalUes=30 --e2nrEnabled=true --configuration=1 --minSpeed=3 --maxSpeed=10 --indicationPeriodicity=1.0 --heuristicType=-1"
{ echo "tag=${TAG} start=$(date -u '+%F %T') args=${ARGS}"; md5sum "${BIN}"; md5sum "${NS3_DIR}/build/lib/libns3.38.rc1-lte-optimized.so"; } > meta.txt
"${BIN}" ${ARGS} > run.log 2>&1 & npid=$!
echo -e "wall_s\tlast_window\trss_mb\tmem_avail_mb" > mem.tsv; t0=$(date +%s)
while kill -0 ${npid} 2>/dev/null; do
  rss=$(awk '/VmRSS/{print int($2/1024)}' /proc/${npid}/status 2>/dev/null); avail=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)
  lw=$(tail -1 DlE2RlcStats.txt 2>/dev/null | cut -f1)
  echo -e "$(( $(date +%s)-t0 ))\t${lw}\t${rss}\t${avail}" >> mem.tsv
  if [ "${avail}" -lt "${GUARD_MB}" ]; then echo "guard: MemAvailable ${avail} MB at $(date -u '+%F %T')" >> meta.txt; kill ${npid}; fi
  sleep 60
done
wait ${npid}; echo "exit=$? end=$(date -u '+%F %T')" >> meta.txt
