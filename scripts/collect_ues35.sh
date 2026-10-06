#!/usr/bin/env bash
# collect_ues35.sh — 35 UE（ues=5 × 7 cell）資料收集，輸出至 data/ues35_seeds/
#
# 與 D-SH（collect_DSH_aux.sh）相同之場景參數，僅 ues=1 → 5。
# 不寫入 data/si_lstm_seeds/ 或 data/batchFinal_seeds/。
#
# 2026-10-06 校準（simTime=5、seed 4200、兩次執行）：
#   - 跑完 5 秒（舊 N=35 紀錄止於 4.2 秒，本次無此問題）
#   - IMSI 1–35 齊全，每窗 N_total = 35
#   - RLC／PHY／CellId／MAC 兩次逐位相同（cu-up 僅第一欄實際時間戳不同）
#   - 約 520 秒實際時間／模擬秒；5 秒時記憶體峰值 1.73 GB；長時間之記憶體趨勢未知
#
# 本腳本額外功能：
#   - 記憶體監控：每 60 秒記錄 ns-3 RSS、系統 MemAvailable、已模擬時間 → <out>/mem_trace.tsv
#   - 防護：MemAvailable < MEM_GUARD_MB 時停止「本腳本啟動之」模擬並記錄（避免整機 OOM）
#   - 完成後檢查：每窗 N_total = 35、IMSI 1–35 齊全
#
# 跑法：
#   cd ~/ns-3-mmwave-oran
#   SEEDS="4200" nohup setsid bash ~/oran-zt-kpm-verification/scripts/collect_ues35.sh > /tmp/collect_ues35.log 2>&1 &

set -uo pipefail

NS3_DIR="${HOME}/ns-3-mmwave-oran"
OUT_DIR="${OUT_DIR:-${HOME}/oran-zt-kpm-verification/data/ues35_seeds}"
mkdir -p "${OUT_DIR}"

CONFIG=1
MINSPEED=3
MAXSPEED=10
PERIOD=1.0
HEURISTIC=-1
UES=5
N_KNOWN=35
SIMTIME=${SIMTIME:-300}
SEEDS=(${SEEDS:-4200})
MEM_GUARD_MB=${MEM_GUARD_MB:-600}
MON_S=${MON_S:-60}

RATE=520                                    # 秒(真實)/秒(模擬)，2026-10-06 校準
RUN_TIMEOUT=$(awk -v r=${RATE} -v t=${SIMTIME} 'BEGIN{printf "%d", r*t*1.5+600}')

KEEP_PLAIN=(DlE2RlcStats.txt cu-cp-cell-1.txt cu-up-cell-1.txt ues.txt enbs.txt CellIdStats.txt UeFailures.txt)
KEEP_GZ=(RxPacketTrace.txt DlMacStats.txt)

fmt_hms() { local s=$1; printf '%dh%02dm' $((s/3600)) $(((s%3600)/60)); }

cd "${NS3_DIR}" || { echo "找不到 ${NS3_DIR}"; exit 1; }
BIN="${NS3_DIR}/build/scratch/ns3.38.rc1-scenario-three-optimized"
[ -x "${BIN}" ] || { echo "找不到 ${BIN}"; exit 1; }

echo "############################################################"
echo "# 35 UE 收集 — seed: ${SEEDS[*]}  simTime=${SIMTIME}s"
echo "# timeout/seed=$(fmt_hms ${RUN_TIMEOUT})  記憶體防護 < ${MEM_GUARD_MB} MB  開始 $(date '+%F %T')"
echo "############################################################"

for SEED in "${SEEDS[@]}"; do
  tag="ues${UES}_t${SIMTIME}_seed${SEED}"
  wd="/tmp/nsU35_${tag}"
  aux="${OUT_DIR}/${tag}_aux"
  main_out="${OUT_DIR}/${tag}.txt"

  if [ -s "${main_out}" ]; then
    echo "-- [${tag}] 已存在，略過 --"; continue
  fi
  rm -rf "${wd}"; mkdir -p "${wd}" "${aux}"
  t0=$(date +%s)
  echo "-- [${tag}] 開始 $(date '+%F %T') --"

  ( cd "${wd}" && exec timeout "${RUN_TIMEOUT}" "${BIN}" \
      --RngRun=${SEED} --simTime=${SIMTIME} --ues=${UES} \
      --configuration=${CONFIG} --minSpeed=${MINSPEED} --maxSpeed=${MAXSPEED} \
      --indicationPeriodicity=${PERIOD} --heuristicType=${HEURISTIC} ) > "${wd}/run.log" 2>&1 &
  tpid=$!

  # ---- 記憶體監控與防護 ----
  printf 'wall_s\tsim_t\trss_mb\tmem_avail_mb\n' > "${aux}/mem_trace.tsv"
  guard_hit=0
  while kill -0 ${tpid} 2>/dev/null; do
    sleep ${MON_S}
    npid=$(pgrep -f "^${BIN} --RngRun=${SEED} --simTime=${SIMTIME} --ues=${UES} " | head -1)
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
  for f in "${KEEP_GZ[@]}"; do [ -e "${wd}/${f}" ] && gzip -c "${wd}/${f}" > "${aux}/${f}.gz"; done
  cp "${wd}/run.log" "${aux}/run.log" 2>/dev/null
  echo "  完成 [${tag}]（耗時 $(fmt_hms ${el})，exit=${ec}）RLC $(wc -l < "${main_out}") 行"

  # ---- C_i 守恆與 IMSI 完整性檢查 ----
  python3 - "${main_out}" "${N_KNOWN}" <<'EOF'
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
print(f"  檢查：{len(win)} 窗；IMSI {len(allim)} 個（應 {n}）；N_total ≠ {n} 之窗 {len(bad)} 個" + (f"：{bad[:10]}" if bad else ""))
print("  ✓ 通過" if not bad and allim == set(range(1, n + 1)) else "  ✗ 未通過——先查原因，勿直接使用")
EOF
  rm -rf "${wd}"
done
echo "# 結束 $(date '+%F %T')"
