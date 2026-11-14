#!/usr/bin/env bash
# collect_d30h_r8.sh — D-30H 重收（2026-11-14 使用者決定）：修正版 ns-3 r8（R-5 旁路＋ByteTagList free list 關閉＋S2），ZT_R7_S2=1
#   輸出 data/ues30_ho_r8_seeds/；舊 data/ues30_ho_seeds/ 僅供診斷，拒絕寫入。全部 .txt 輸出皆保留（gz），含 _exact／_percell 旁路檔
# 由 collect_d30h.sh 複製：D-30 之參數＋ --handoverMode=FixedTtt（含合法 NR 間換手）
# 由 collect_stage3.sh 複製（2026-11-13）；規格 docs/thesis/D30H_handover_data_spec.md。一律以 setsid nohup 啟動。
#   SEEDS="4200 4202 4204 4206" setsid nohup bash scripts/collect_d30h.sh >> data/ues30_ho_seeds/collect_A.log 2>&1 < /dev/null &
# probe：SIMTIME=6 OUT_DIR=$HOME/oran-zt-kpm-verification/data/ues30_ho_seeds/_probe bash scripts/collect_d30h.sh


set -uo pipefail

NS3_DIR="${NS3_DIR:-${HOME}/ns-3-mmwave-oran-r8}"
export ZT_R7_S2=1
VARIANT=D30H; N_KNOWN=30; TM=0; HO_MODE=FixedTtt     # D-30H：同 D-30，僅加 --handoverMode=FixedTtt（規格 docs/thesis/D30H_handover_data_spec.md）
OUT_DIR="${OUT_DIR:-${HOME}/oran-zt-kpm-verification/data/ues30_ho_r8_seeds}"
case "$(realpath -m "${OUT_DIR}")" in */data/ues30_seeds|*/data/ues30_seeds/*|*/data/ues30_ho_seeds|*/data/ues30_ho_seeds/*|*/data/game_stage3*|*/data/si_lstm_seeds*|*/data/batchFinal_seeds*) echo "拒絕寫入既有資料目錄"; exit 2 ;; esac
mkdir -p "${OUT_DIR}"

CONFIG=1
MINSPEED=3
MAXSPEED=10
PERIOD=1.0
HEURISTIC=-1
EXTRA_ARGS="--totalUes=${N_KNOWN} --e2nrEnabled=true --trafficModel=${TM} --handoverMode=${HO_MODE}"
SIMTIME=${SIMTIME:-301}
TAG_T=300                                   # 檔名沿用 t300（實際模擬 301 s，分析取 0–299）
SEEDS=(${SEEDS:-4200})
MEM_GUARD_MB=${MEM_GUARD_MB:-600}
MON_S=${MON_S:-60}

RATE=600                                    # 秒(真實)/秒(模擬)；校準約 384，35 UE 長跑後段變慢，取保守值
RUN_TIMEOUT=$(awk -v r=${RATE} -v t=${SIMTIME} 'BEGIN{printf "%d", r*t*1.5+600}')

KEEP_PLAIN=(DlE2RlcStats.txt UlE2RlcStats.txt DlE2RlcStats_exact.txt DlE2RlcStats_percell.txt DlE2RlcStatsLte_exact.txt DlE2RlcStatsLte_percell.txt ues.txt enbs.txt CellIdStats.txt UeFailures.txt MmWaveSwitchStats.txt CellIdStatsHandover.txt UeHandoverStartStats.txt UeHandoverEndStats.txt EnbHandoverStartStats.txt EnbHandoverEndStats.txt)
KEEP_GZ=(RxPacketTrace.txt DlMacStats.txt DlTxPhyStats.txt DlE2PdcpStats.txt cu-cp-cell-1.txt cu-up-cell-1.txt du-cell-2.txt du-cell-3.txt du-cell-4.txt du-cell-5.txt du-cell-6.txt du-cell-7.txt du-cell-8.txt cu-cp-cell-2.txt cu-cp-cell-3.txt cu-cp-cell-4.txt cu-cp-cell-5.txt cu-cp-cell-6.txt cu-cp-cell-7.txt cu-cp-cell-8.txt cu-up-cell-2.txt cu-up-cell-3.txt cu-up-cell-4.txt cu-up-cell-5.txt cu-up-cell-6.txt cu-up-cell-7.txt cu-up-cell-8.txt)

fmt_hms() { local s=$1; printf '%dh%02dm' $((s/3600)) $(((s%3600)/60)); }

cd "${NS3_DIR}" || { echo "找不到 ${NS3_DIR}"; exit 1; }
BIN="${NS3_DIR}/build/scratch/ns3.38.rc1-scenario-three-optimized"
[ -x "${BIN}" ] || { echo "找不到 ${BIN}"; exit 1; }

echo "############################################################"
echo "# D-30H 收集（handoverMode=${HO_MODE}）（${N_KNOWN} UE，trafficModel=${TM}） — seed: ${SEEDS[*]}  simTime=${SIMTIME}s"
echo "# timeout/seed=$(fmt_hms ${RUN_TIMEOUT})  記憶體防護 < ${MEM_GUARD_MB} MB  開始 $(date '+%F %T')"
echo "############################################################"

for SEED in "${SEEDS[@]}"; do
  tag="${VARIANT}_ues${N_KNOWN}_t${TAG_T}_seed${SEED}"
  wd="${OUT_DIR}/_work_${tag}"
  aux="${OUT_DIR}/${tag}_aux"
  main_out="${OUT_DIR}/${tag}.txt"

  if [ -s "${main_out}" ]; then
    echo "-- [${tag}] 已存在，略過 --"; continue
  fi
  rm -rf "${wd}"; mkdir -p "${wd}" "${aux}"
  t0=$(date +%s)
  echo "-- [${tag}] 開始 $(date '+%F %T') --"

  ( cd "${wd}" && exec timeout "${RUN_TIMEOUT}" "${BIN}" \
      --RngRun=${SEED} --simTime=${SIMTIME} ${EXTRA_ARGS} \
      --configuration=${CONFIG} --minSpeed=${MINSPEED} --maxSpeed=${MAXSPEED} \
      --indicationPeriodicity=${PERIOD} --heuristicType=${HEURISTIC} ) > "${wd}/run.log" 2>&1 &
  tpid=$!

  # ---- 記憶體監控與防護 ----
  printf 'wall_s\tsim_t\trss_mb\tmem_avail_mb\n' > "${aux}/mem_trace.tsv"
  guard_hit=0
  while kill -0 ${tpid} 2>/dev/null; do
    sleep ${MON_S}
    npid=$(pgrep -f "^${BIN} --RngRun=${SEED} --simTime=${SIMTIME} --totalUes=${N_KNOWN} " | head -1)
    rss=0; [ -n "${npid}" ] && rss=$(( $(awk '/VmRSS/{print $2}' /proc/${npid}/status 2>/dev/null || echo 0) / 1024 ))
    avail=$(( $(awk '/MemAvailable/{print $2}' /proc/meminfo) / 1024 ))
    simt=$(tail -n 1 "${wd}/RxPacketTrace.txt" 2>/dev/null | cut -f2)
    printf '%d\t%s\t%d\t%d\n' $(( $(date +%s) - t0 )) "${simt:-NA}" "${rss}" "${avail}" >> "${aux}/mem_trace.tsv"
    if [ "${avail}" -lt "${MEM_GUARD_MB}" ]; then
      echo "  ⚠ 記憶體防護觸發：MemAvailable ${avail} MB < ${MEM_GUARD_MB} MB（sim_t=${simt}, RSS=${rss} MB）→ 停止本次模擬"
      kill ${tpid} 2>/dev/null; [ -n "${npid}" ] && kill ${npid} 2>/dev/null
      guard_hit=1; break
    fi
  done
  wait ${tpid}; ec=$?
  el=$(( $(date +%s) - t0 ))

  if [ ${guard_hit} -eq 1 ]; then
    echo "  [${tag}] 因記憶體防護中止（耗時 $(fmt_hms ${el})）；保留 ${wd} 與 ${aux}/mem_trace.tsv 供檢查"
    continue
  fi
  if [ ${ec} -eq 124 ]; then
    echo "  TIMEOUT [${tag}]（$(fmt_hms ${el})）；保留 ${wd}"; continue
  fi
  if [ ! -s "${wd}/DlE2RlcStats.txt" ]; then
    echo "  無有效輸出 [${tag}]（exit=${ec}）；保留 ${wd}"; continue
  fi

  cp "${wd}/DlE2RlcStats.txt" "${main_out}"
  for f in "${KEEP_PLAIN[@]}"; do [ -e "${wd}/${f}" ] && cp "${wd}/${f}" "${aux}/${f}"; done
  for f in "${wd}"/*.txt; do b=$(basename "$f"); [ -e "${aux}/${b}" ] || gzip -c "$f" > "${aux}/${b}.gz"; done
  { echo "ZT_R7_S2=${ZT_R7_S2} ns3_dir=${NS3_DIR} host=$(hostname) end=$(date '+%F %T')"; md5sum "${BIN}" "${NS3_DIR}"/build/lib/libns3.38.rc1-{network,lte,mmwave}-*.so; } > "${aux}/meta.txt"
  cp "${wd}/run.log" "${aux}/run.log" 2>/dev/null
  echo "  完成 [${tag}]（耗時 $(fmt_hms ${el})，exit=${ec}）RLC $(wc -l < "${main_out}") 行"

  # ---- C_i 守恆與 IMSI 完整性檢查 ----
  python3 - "${main_out}" "${N_KNOWN}" "$(( SIMTIME > 300 ? 300 : SIMTIME - 1 ))" <<'EOF'
import sys, collections
path, n = sys.argv[1], int(sys.argv[2])
win = collections.defaultdict(set)
for l in open(path):
    if l.startswith("%"): continue
    p = l.split("\t")
    try: win[int(float(p[0]))].add(int(p[3]))
    except (ValueError, IndexError): pass
allim = set().union(*win.values()) if win else set()
bad = [w for w in sorted(win) if len(win[w]) != n]
missing = [w for w in range(int(sys.argv[3])) if w not in win]
print(f"  檢查：{len(win)} 窗（應有窗缺 {len(missing)} 窗）；IMSI {len(allim)} 個（應 {n}）；N_total ≠ {n} 之窗 {len(bad)} 個" + (f"：{bad[:10]}" if bad else ""))
print("  ✓ 通過" if not bad and not missing and allim == set(range(1, n + 1)) else "  ✗ 未通過——先查原因，勿直接使用")
EOF
  rm -rf "${wd}"
done
echo "# 結束 $(date '+%F %T')"
