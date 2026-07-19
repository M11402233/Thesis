#!/usr/bin/env bash
# collect_mobility_sweep.sh — 移動性掃描資料收集（證明基數守恆與 UE 速度無關）
#
# 目的：C_i 的 σ=0 若是「物理必然」而非「特定速度巧合」，那不同移動速度下
#       N_total 都應恆為 N_known。此腳本跑三檔速度，供 verify_mobility_invariance.py 分析。
#
# 設計對齊你 C_i_experiment_design_v4.md 的批次 C，但固定用定案參數（ues=1, 7UE, period=1.0）。
#
# 跑法（在你機器上，過夜或分批）：
#     cd ~/ns-3-mmwave-oran
#     bash ~/oran-zt-kpm-verification/scripts/collect_mobility_sweep.sh
#
# 輸出：data/mobility_seeds/ 下，檔名格式 speed{MIN}_{MAX}_seed{SEED}.txt

set -euo pipefail

NS3_DIR="${HOME}/ns-3-mmwave-oran"
OUT_DIR="${HOME}/oran-zt-kpm-verification/data/mobility_seeds"
mkdir -p "${OUT_DIR}"

# 三檔速度（min max），涵蓋慢走 / 正常 / 快速移動
SPEEDS=("1 3" "3 10" "10 20")
# 每檔速度至少 3 個 seed（跨隨機性；要更嚴謹可加到 5）
SEEDS=(4200 4201 4202)

# 定案參數（與 baseline 完全一致，只變速度）
SIMTIME=60
UES=1
CONFIG=1
PERIOD=1.0
HEURISTIC=-1

echo "===== 移動性掃描：3 速度 × ${#SEEDS[@]} seed ====="
echo "定案參數：ues=${UES}(7UE), config=${CONFIG}, simTime=${SIMTIME}, period=${PERIOD}"
echo "輸出目錄：${OUT_DIR}"
echo

cd "${NS3_DIR}"

run_one() {
  local smin=$1 smax=$2 seed=$3
  local tag="speed${smin}_${smax}_seed${seed}"
  local outdir="/tmp/nsmob_${tag}"
  rm -rf "${outdir}"; mkdir -p "${outdir}"
  echo "-- ${tag} 開始 $(date +%T) --"
  timeout 4200 ./ns3 run "scratch/scenario-three --RngRun=${seed} --simTime=${SIMTIME} \
      --ues=${UES} --configuration=${CONFIG} --minSpeed=${smin} --maxSpeed=${smax} \
      --indicationPeriodicity=${PERIOD} --heuristicType=${HEURISTIC}" \
      --cwd="${outdir}" > "${outdir}/run.log" 2>&1 || {
        echo "  ❌ ${tag} 失敗（見 ${outdir}/run.log）"; return 1; }
  if [ -s "${outdir}/DlE2RlcStats.txt" ]; then
    cp "${outdir}/DlE2RlcStats.txt" "${OUT_DIR}/${tag}.txt"
    echo "  ✅ ${tag} 完成 $(date +%T)"
  else
    echo "  ❌ ${tag} 無輸出"; return 1
  fi
}

# 序列跑（穩定；若要平行可改用 & + wait，一次最多 4 個）
for sp in "${SPEEDS[@]}"; do
  read -r SMIN SMAX <<< "${sp}"
  for SEED in "${SEEDS[@]}"; do
    run_one "${SMIN}" "${SMAX}" "${SEED}" || echo "  (略過失敗項，繼續)"
  done
done

echo
echo "===== 全部完成 $(date +%T) ====="
echo "接著跑分析："
echo "  python3 ~/oran-zt-kpm-verification/xapps/verification/residuals/verify_mobility_invariance.py"
