#!/usr/bin/env bash
# 換手記憶體增長之配置來源追蹤（2026-11-13）：在 ubuntu:22.04 + heaptrack 容器中執行既有 optimized 二進位檔。
# 用法：TAG=H1 EXTRA="--handoverMode=FixedTtt" SIMTIME=4 bash scripts/heaptrack_d30h.sh
# 只寫入 data/d30h_memdiag/HT/<TAG>/。容器以 -d 啟動（不受工作階段結束影響）。
set -eu
TAG="${TAG:?}"; EXTRA="${EXTRA:-}"; SIMTIME="${SIMTIME:-4}"; SEED="${SEED:-4200}"
NS3="${HOME}/ns-3-mmwave-oran"; BIN="${NS3}/build/scratch/ns3.38.rc1-scenario-three-optimized"
OUT="${HOME}/oran-zt-kpm-verification/data/d30h_memdiag/HT/${TAG}"; mkdir -p "${OUT}/hostlib"
cp -L /lib/x86_64-linux-gnu/libstdc++.so.6 /lib/x86_64-linux-gnu/libgcc_s.so.1 "${OUT}/hostlib/"
ARGS="--RngRun=${SEED} --simTime=${SIMTIME} --totalUes=30 --e2nrEnabled=true --trafficModel=0 --configuration=1 --minSpeed=3 --maxSpeed=10 --indicationPeriodicity=1.0 --heuristicType=-1 ${EXTRA}"
echo "tag=${TAG} start=$(date -u '+%F %T') ns3_commit=$(git -C ${NS3} rev-parse --short HEAD) args=${ARGS}" > "${OUT}/meta.txt"; md5sum "${BIN}" >> "${OUT}/meta.txt"
sg docker -c "docker run -d --name zt-ht-${TAG} --user $(id -u):$(id -g) -v ${HOME}:${HOME} -w ${OUT} \
  -e LD_LIBRARY_PATH=${OUT}/hostlib:${NS3}/build/lib zt-heaptrack:22.04 \
  bash -c 'heaptrack -o ${OUT}/ht ${BIN} ${ARGS} > run.log 2>&1; echo exit=\$? end=\$(date -u \"+%F %T\") >> meta.txt'"
