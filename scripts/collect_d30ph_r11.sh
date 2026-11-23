#!/usr/bin/env bash
# collect_d30ph_r11.sh — D-30PH（含換手之第二階段資料；規格 docs/thesis/D30PH_collection_spec.md）：r11（= r10 模式 1 ＋ 有效延遲樣本）＋ ZT_R7_S2=1 ＋ ZT_R10_RETX_TAG=1 ＋ --handoverMode=FixedTtt
#   命令列同 D-30H（r8d）之 FixedTtt 版；8 seed 4200–4207、301 s；輸出 data/ues30_ph_r11_seeds/。不得終止。不得設 ZT_R10_TRACE（無追蹤）。
#   啟動由 scripts/r9/d30ph_chain.sh 負責；單 seed：VARIANT=D30PH ZT_R10_RETX_TAG=1 NS3_DIR=~/ns-3-mmwave-oran-r11 OUT_DIR=<dir> SEEDS=<s> bash scripts/collect_d30ph_r11.sh
#   由 collect_d30p_r9.sh 改：EXTRA_ARGS 加 --handoverMode=FixedTtt；預設 NS3_DIR 為 r11；變體 D30PH
set -uo pipefail

NS3_DIR="${NS3_DIR:-${HOME}/ns-3-mmwave-oran-r11}"
unset ZT_R10_TRACE
export ZT_R7_S2=1
# D-30P1（D30P1_r10_recollection_spec.md F1）：r10／r11 必須明設 ZT_R10_RETX_TAG，並寫入 meta
case "$(basename "${NS3_DIR}")" in *r10*|*r11*) [ -n "${ZT_R10_RETX_TAG:-}" ] || { echo "r10 須設定 ZT_R10_RETX_TAG"; exit 2; }; export ZT_R10_RETX_TAG ;; esac
VARIANT=${VARIANT:-D30PH}; N_KNOWN=30                   # D-30PH：D-30 之命令列 ＋ FixedTtt，r11 ＋ S2
OUT_DIR="${OUT_DIR:-${HOME}/oran-zt-kpm-verification/data/ues30_ph_r11_seeds}"
case "$(realpath -m "${OUT_DIR}")" in */data/ues30_seeds|*/data/ues30_seeds/*|*/data/ues30_ho_seeds|*/data/ues30_ho_seeds/*|*/data/ues30_ho_r8*_seeds|*/data/ues30_ho_r8*_seeds/*|*/data/game_stage3*|*/data/si_lstm_seeds*|*/data/batchFinal_seeds*|*/data/ues30_p_r9_seeds|*/data/ues30_p_r9_seeds/*|*/data/ues30_p_r9g13_seeds|*/data/ues30_p_r9g13_seeds/*|*/data/ues30_p_r10_seeds|*/data/ues30_p_r10_seeds/*|*/data/r11c_*) echo "拒絕寫入既有資料目錄"; exit 2 ;; esac
mkdir -p "${OUT_DIR}"

CONFIG=1
MINSPEED=3
MAXSPEED=10
PERIOD=1.0
HEURISTIC=-1
EXTRA_ARGS="--totalUes=${N_KNOWN} --e2nrEnabled=true --handoverMode=FixedTtt"
SIMTIME=${SIMTIME:-301}
TAG_T=300                                   # 檔名沿用 t300（實際模擬 301 s，分析取 0–299）
SEEDS=(${SEEDS:-4200})
MEM_GUARD_MB=${MEM_GUARD_MB:-600}
MON_S=${MON_S:-60}

RATE=600                                    # 秒(真實)/秒(模擬)；校準約 384，35 UE 長跑後段變慢，取保守值
RUN_TIMEOUT=$(awk -v r=${RATE} -v t=${SIMTIME} 'BEGIN{printf "%d", r*t*1.5+600}')

KEEP_PLAIN=(DlE2RlcStats.txt UlE2RlcStats.txt DlE2RlcStats_exact.txt DlE2RlcStats_percell.txt DlE2RlcStats_r11eff.txt DlE2RlcStatsLte_r11eff.txt DlE2RlcStatsLte_exact.txt DlE2RlcStatsLte_percell.txt R9_enb_uemap.txt R9_ue_rrc.txt R9_pdcp_split.txt DlE2RlcStats_r9rx.txt DlE2RlcStats_r9lastset.txt DlE2RlcStatsLte_r9rx.txt DlE2RlcStatsLte_r9lastset.txt ues.txt enbs.txt CellIdStats.txt UeFailures.txt MmWaveSwitchStats.txt CellIdStatsHandover.txt UeHandoverStartStats.txt UeHandoverEndStats.txt EnbHandoverStartStats.txt EnbHandoverEndStats.txt)
KEEP_GZ=(RxPacketTrace.txt DlMacStats.txt DlTxPhyStats.txt DlE2PdcpStats.txt cu-cp-cell-1.txt cu-up-cell-1.txt du-cell-2.txt du-cell-3.txt du-cell-4.txt du-cell-5.txt du-cell-6.txt du-cell-7.txt du-cell-8.txt cu-cp-cell-2.txt cu-cp-cell-3.txt cu-cp-cell-4.txt cu-cp-cell-5.txt cu-cp-cell-6.txt cu-cp-cell-7.txt cu-cp-cell-8.txt cu-up-cell-2.txt cu-up-cell-3.txt cu-up-cell-4.txt cu-up-cell-5.txt cu-up-cell-6.txt cu-up-cell-7.txt cu-up-cell-8.txt)

fmt_hms() { local s=$1; printf '%dh%02dm' $((s/3600)) $(((s%3600)/60)); }

REPO="${REPO:-${HOME}/oran-zt-kpm-verification}"
cd "${NS3_DIR}" || { echo "找不到 ${NS3_DIR}"; exit 1; }
BIN="${NS3_DIR}/build/scratch/ns3.38.rc1-scenario-three-optimized"
[ -x "${BIN}" ] || { echo "找不到 ${BIN}"; exit 1; }

echo "############################################################"
echo "# D-30PH 收集（FixedTtt，r11）（${N_KNOWN} UE） — seed: ${SEEDS[*]}  simTime=${SIMTIME}s"
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

  ( cd "${REPO}" && python3 scripts/r9/check_r9_outputs.py "${wd}" > "${aux}/check_r9_outputs.json" 2> "${aux}/check_r9_outputs.err" ); kec=$?
  if [ ${kec} -ne 0 ]; then echo "  ✗ 未通過（K1–K5，exit=${kec}）[${tag}]；保留 ${wd}，見 ${aux}/check_r9_outputs.json"; continue; fi
  echo "  K1–K5 通過 [${tag}]"
  cp "${wd}/DlE2RlcStats.txt" "${main_out}"
  for f in "${KEEP_PLAIN[@]}"; do [ -e "${wd}/${f}" ] && cp "${wd}/${f}" "${aux}/${f}"; done
  for f in "${wd}"/*.txt; do b=$(basename "$f"); [ -e "${aux}/${b}" ] || gzip -c "$f" > "${aux}/${b}.gz"; done
  { echo "ZT_R7_S2=${ZT_R7_S2} ZT_R10_RETX_TAG=${ZT_R10_RETX_TAG:-unset} ns3_dir=${NS3_DIR} host=$(hostname) end=$(date '+%F %T')"; md5sum "${BIN}" "${NS3_DIR}"/build/lib/libns3.38.rc1-{network,lte,mmwave}-*.so "${NS3_DIR}"/src/lte/model/{lte-rlc-am.cc,lte-rlc-am.h,lte-enb-rrc.cc,lte-enb-rrc.h,lte-enb-net-device.cc,mc-enb-pdcp.cc,mc-enb-pdcp.h} "${NS3_DIR}"/src/lte/helper/mmwave-bearer-stats-calculator.{cc,h} "${NS3_DIR}"/src/mmwave/model/mmwave-enb-net-device.cc "${NS3_DIR}"/scratch/scenario-three.cc; } > "${aux}/meta.txt"
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
