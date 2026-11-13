#!/usr/bin/env bash
# R-7 第 1 項（ByteTagList free list 關閉）驗證短跑（2026-11-13）。只寫入 data/r7_validate/<TAG>/。
# 用法：TAG=V1_noauto MODE=d30 SIMTIME=8 setsid nohup bash scripts/run_r7_validate.sh &
#       TAG=V2_fixedttt MODE=memdiag EXTRA="--handoverMode=FixedTtt" SIMTIME=8 setsid nohup bash scripts/run_r7_validate.sh &
# MODE=d30：與 D-30／R-5 相同命令列（對照 D-30 seed 4200 前綴逐位）；MODE=memdiag：與 memdiag M0–M3 相同命令列（對照 M1 逐位）。
set -u
NS3_DIR="${NS3_DIR:-${HOME}/ns-3-mmwave-oran-r7}"; BIN="${NS3_DIR}/build/scratch/ns3.38.rc1-scenario-three-optimized"
TAG="${TAG:?}"; MODE="${MODE:?}"; EXTRA="${EXTRA:-}"; SIMTIME="${SIMTIME:-8}"; SEED="${SEED:-4200}"; GUARD_MB="${GUARD_MB:-2500}"
case "${MODE}" in
  d30) ARGS="--RngRun=${SEED} --simTime=${SIMTIME} --totalUes=30 --e2nrEnabled=true --configuration=1 --minSpeed=3 --maxSpeed=10 --indicationPeriodicity=1.0 --heuristicType=-1 ${EXTRA}";;
  memdiag) ARGS="--RngRun=${SEED} --simTime=${SIMTIME} --totalUes=30 --e2nrEnabled=true --trafficModel=0 --configuration=1 --minSpeed=3 --maxSpeed=10 --indicationPeriodicity=1.0 --heuristicType=-1 ${EXTRA}";;
  *) echo "bad MODE"; exit 2;;
esac
OUT="${HOME}/oran-zt-kpm-verification/data/r7_validate/${TAG}"; mkdir -p "${OUT}"; cd "${OUT}" || exit 1
{ echo "tag=${TAG} mode=${MODE} start=$(date -u '+%F %T') ns3_dir=${NS3_DIR} args=${ARGS}"; md5sum "${BIN}" "${NS3_DIR}/build/lib/libns3.38.rc1-network-optimized.so" "${NS3_DIR}/build/lib/libns3.38.rc1-lte-optimized.so"; } > meta.txt
"${BIN}" ${ARGS} > run.log 2>&1 & npid=$!
echo -e "wall_s\tlast_window\trss_mb\tho_end\tmem_avail_mb" > mem.tsv; t0=$(date +%s)
while kill -0 ${npid} 2>/dev/null; do
  rss=$(awk '/VmRSS/{print int($2/1024)}' /proc/${npid}/status 2>/dev/null); avail=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)
  lw=$(tail -1 DlE2RlcStats.txt 2>/dev/null | cut -f1); ho=$( [ -f UeHandoverEndStats.txt ] && wc -l < UeHandoverEndStats.txt || echo 0)
  [ -n "${rss}" ] && echo -e "$(( $(date +%s)-t0 ))\t${lw}\t${rss}\t${ho}\t${avail}" >> mem.tsv
  if [ "${avail}" -lt "${GUARD_MB}" ]; then echo "guard: MemAvailable ${avail} MB" >> meta.txt; kill ${npid}; fi
  sleep 10
done
wait ${npid}; echo "exit=$? end=$(date -u '+%F %T')" >> meta.txt
