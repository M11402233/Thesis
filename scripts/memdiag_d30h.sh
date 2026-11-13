#!/usr/bin/env bash
# D-30H 記憶體診斷短跑（2026-11-13）：同 seed、同 D-30 參數，一次只改一個因素；記錄 RSS 與換手數。
# 用法：TAG=M1 EXTRA="--handoverMode=FixedTtt" SIMTIME=8 setsid nohup bash scripts/memdiag_d30h.sh &
# 只寫入 data/d30h_memdiag/<TAG>/；不碰任何正式資料目錄。
set -u
NS3_DIR="${HOME}/ns-3-mmwave-oran"; BIN="${NS3_DIR}/build/scratch/ns3.38.rc1-scenario-three-optimized"
TAG="${TAG:?}"; EXTRA="${EXTRA:-}"; SIMTIME="${SIMTIME:-8}"; SEED="${SEED:-4200}"; GUARD_MB="${GUARD_MB:-2500}"
OUT="${HOME}/oran-zt-kpm-verification/data/d30h_memdiag/${TAG}"; mkdir -p "${OUT}"; cd "${OUT}" || exit 1
ARGS="--RngRun=${SEED} --simTime=${SIMTIME} --totalUes=30 --e2nrEnabled=true --trafficModel=0 --configuration=1 --minSpeed=3 --maxSpeed=10 --indicationPeriodicity=1.0 --heuristicType=-1 ${EXTRA}"
echo "tag=${TAG} start=$(date -u '+%F %T') ns3_commit=$(git -C ${NS3_DIR} rev-parse --short HEAD) args=${ARGS}" > meta.txt
md5sum "${BIN}" >> meta.txt
"${BIN}" ${ARGS} > run.log 2>&1 & npid=$!
echo -e "wall_s\tlast_window\trss_mb\tho_end\tmem_avail_mb" > mem.tsv; t0=$(date +%s)
while kill -0 ${npid} 2>/dev/null; do
  rss=$(awk '/VmRSS/{print int($2/1024)}' /proc/${npid}/status 2>/dev/null); avail=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)
  lw=$(tail -1 DlE2RlcStats.txt 2>/dev/null | cut -f1); ho=$( [ -f UeHandoverEndStats.txt ] && wc -l < UeHandoverEndStats.txt || echo 0)
  echo -e "$(( $(date +%s)-t0 ))\t${lw}\t${rss}\t${ho}\t${avail}" >> mem.tsv
  if [ "${avail}" -lt "${GUARD_MB}" ]; then echo "guard: MemAvailable ${avail} MB" >> meta.txt; kill ${npid}; fi
  sleep 20
done
wait ${npid}; echo "exit=$? end=$(date -u '+%F %T')" >> meta.txt
