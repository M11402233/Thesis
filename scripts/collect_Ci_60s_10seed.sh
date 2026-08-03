#!/usr/bin/env bash
# =============================================================================
# collect_Ci_60s_10seed.sh  (v2)
#   C_i 基數守恆(cardinality conservation)資料集收集 — 10 seed × 60 s
# =============================================================================
#
# 【C_i 的 scope 定義】
#   觀測粒度:E2SM-KPM indication 週期與分析窗均為 1 秒,二者對齊,
#             每一模擬秒產生一個聚合窗。本腳本所稱「窗」一律指此 1 秒聚合窗。
#   資料規模:C_i 使用 60 秒模擬 → 60 窗 × 10 seed = 600 窗,
#             供論文 4.6 節「600 窗 0 反例」證偽測試使用。
#             (對照:S_i / H_i 使用 300 秒模擬,300 窗 × 4 seed。)
#   斷言性質:C_i 為單窗即決之布林斷言(safety property),重「隨機覆蓋廣度」
#             而非單一軌跡長度,故採多 seed 短模擬而非少 seed 長模擬。
#
#   ★ 完整性要求:600 窗此一分母只有在「10 個 seed 全部跑滿 60 s」時才成立。
#     任一 seed 逾時或中斷都會使分母失真,因此本腳本強制:
#       (a) 逾時(rc=124)與真實錯誤(rc≠0)分開記錄,絕不混為「失敗」;
#       (b) 每個 seed 產出寫入 manifest.csv,含 rc / wall time / sha256 / 觀測數;
#       (c) 收尾檢查 10/10 完成,未達標則以非零退出碼結束並明列缺口。
#
# 【可重現性聲明】
#   本腳本為「事後固化」版本:原始 C_i 黃金資料(data/batchFinal_seeds/seed42*.txt)
#   最初由終端機互動式指令產生(見論文 4.0.3 資料生成史)。組態經資料反推驗證:
#   C_i 資料之 delay 分布(median ≈ 0.000955 s)與已知 configuration=1 之 S_i
#   資料一致,確認為同一物理場景。
#
# 【命名說明】
#   ns-O-RAN 場景將節點命名為 mmWave gNB,此為沿用其 MC 雙連結架構之命名慣例。
#   本研究之 S_i 建立於 delay 的跨節點場域一致性,與實體載波頻段無關,
#   因此命名不影響方法有效性。
#   ※ 待確認:本腳本 CONFIG=1 註記為 3.5 GHz(屬 sub-6),而外部註記述及
#     「configuration=2 下實體載波實際為 sub-6 GHz」。兩者若指涉同一參數表,
#     論文與腳本註解宜統一;請以 scenario-three 原始碼的 configuration 分支為準
#     核對後再定稿。此為文件一致性問題,不影響本次資料收集的參數本身。
#
# 【與 v1 的差異(僅執行機制,參數完全未動)】
#   1. 直接執行編譯產物,不再經 ./ns3 run 的 python wrapper
#      → timeout 的訊號可正確傳達到模擬行程(v1 殺 wrapper 會留下孤兒行程)。
#   2. 退出碼分流:124 記為「逾時」,其餘非零記為「錯誤」。
#   3. 平行執行(預設依核心數與記憶體推算),10 個 seed 彼此獨立。
#   4. 先集中編譯一次再平行跑,避免多行程同時觸發 ninja。
#   5. 新增 --probe 校準模式:先量測單位 wall time,再決定 timeout 與平行度。
#   6. 產出 manifest.csv 與 SHA-256,供論文附錄提供資料出處稽核。
#
# 【用法】
#   校準(強烈建議先跑):
#     bash collect_Ci_60s_10seed.sh --probe
#   正式收集:
#     bash collect_Ci_60s_10seed.sh --jobs 5 --timeout 21600
#   其他選項:
#     --out DIR      輸出目錄(預設為 VERIFY 目錄,不覆蓋黃金資料)
#     --seeds "a b"  覆寫 seed 清單(僅供除錯,正式收集請勿使用)
#     --force        允許覆寫既有輸出檔
#     --dry-run      只印出將執行的指令
# =============================================================================

set -uo pipefail

# ---------------------------------------------------------------------------
# 定案參數 — 與 S_i / H_i 資料集(collect_Si_LSTM_ues1_final.sh)一致,
#            僅 simTime 與 seed 數不同。★ 請勿修改,修改即非同一資料集。★
# ---------------------------------------------------------------------------
CONFIG=1          # 3.5 GHz / 20 MHz / isd=1000 m(經 delay 分布反推驗證)
UES=1             # 每 cell 1 UE × 7 cell = N_known = 7
SIMTIME=60        # 布林斷言重廣度,60 s → 60 窗
PERIOD=1.0        # 1 秒觀測窗(= E2SM-KPM indication 週期,二者對齊)
MINSPEED=3
MAXSPEED=10
HEURISTIC=-1
SEEDS=(4200 4201 4202 4203 4204 4205 4206 4207 4208 4209)   # 10 獨立隨機種子

EXPECT_UE=7                 # N_known
EXPECT_WINDOWS=${SIMTIME}   # 60 窗/seed
SCENARIO="scenario-three"

# ---------------------------------------------------------------------------
# 路徑與預設值
# ---------------------------------------------------------------------------
NS3_DIR="${NS3_DIR:-${HOME}/ns-3-mmwave-oran}"
PROJ_DIR="${PROJ_DIR:-${HOME}/oran-zt-kpm-verification}"
# 絕不寫入 batchFinal_seeds(現有論文黃金資料)。先寫入獨立目錄,
# 比對 delay 分布 / N_total 一致後,再由人工決定是否正式取代。
OUT_DIR="${PROJ_DIR}/data/batchFinal_seeds_VERIFY"

JOBS=""                     # 空 = 自動推算
TIMEOUT_S=21600             # 6 小時/seed(v1 的 3600 s 已證實不足)
PROBE=0
FORCE=0
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --probe)   PROBE=1; shift ;;
    --jobs)    JOBS="$2"; shift 2 ;;
    --timeout) TIMEOUT_S="$2"; shift 2 ;;
    --out)     OUT_DIR="$2"; shift 2 ;;
    --seeds)   read -r -a SEEDS <<< "$2"; shift 2 ;;
    --force)   FORCE=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) sed -n '1,60p' "$0"; exit 0 ;;
    *) echo "未知選項:$1(用 --help 看說明)" >&2; exit 2 ;;
  esac
done

RUN_ID="$(date +%Y%m%d_%H%M%S)"
LOG_DIR="${OUT_DIR}/_logs_${RUN_ID}"
MANIFEST="${OUT_DIR}/manifest_${RUN_ID}.csv"

# ---------------------------------------------------------------------------
# 前置檢查
# ---------------------------------------------------------------------------
die() { echo "✗ $*" >&2; exit 1; }

[[ -d "${NS3_DIR}" ]] || die "找不到 ns-3 目錄:${NS3_DIR}(可用 NS3_DIR=... 覆寫)"
cd "${NS3_DIR}" || die "無法進入 ${NS3_DIR}"
[[ -x ./ns3 ]] || die "${NS3_DIR}/ns3 不存在或不可執行"

# 集中編譯一次。平行跑時若讓每個行程各自觸發 ninja,會互相搶鎖或重複編譯。
echo "▶ 編譯(集中一次,避免平行時重複觸發 ninja)…"
if [[ ${DRY_RUN} -eq 0 ]]; then
  ./ns3 build > "/tmp/ns3_build_${RUN_ID}.log" 2>&1 \
    || die "編譯失敗,見 /tmp/ns3_build_${RUN_ID}.log"
fi
echo "  ✓ 編譯完成"

# 定位編譯產物(不同 ns-3 版本命名不同:scenario-three / ns3.xx-scenario-three-default)
BIN="$(find build/scratch -type f -perm -u+x -name "*${SCENARIO}*" 2>/dev/null \
        | grep -v '\.so$' | head -1)"
[[ -n "${BIN}" ]] || die "找不到 ${SCENARIO} 的編譯產物,請確認 scratch/${SCENARIO}.cc 存在"
BIN="${NS3_DIR}/${BIN}"
echo "  ✓ 執行檔:${BIN}"

# 直跑 binary 時必須自行設定共享函式庫路徑(平時由 ./ns3 wrapper 代勞)
export LD_LIBRARY_PATH="${NS3_DIR}/build/lib:${LD_LIBRARY_PATH:-}"

mkdir -p "${OUT_DIR}" "${LOG_DIR}" || die "無法建立輸出目錄"

# ---------------------------------------------------------------------------
# --probe:校準模式。用短 simTime 量測單位 wall time,外推 60 s 所需時間。
# ---------------------------------------------------------------------------
if [[ ${PROBE} -eq 1 ]]; then
  PT=5
  pwd_probe="/tmp/nsCi_probe_${RUN_ID}"
  rm -rf "${pwd_probe}"; mkdir -p "${pwd_probe}"
  echo "▶ 校準:simTime=${PT}s, seed=${SEEDS[0]}(其餘參數與正式收集相同)"
  t0=$(date +%s)
  ( cd "${pwd_probe}" && timeout -k 30 --foreground 1800 "${BIN}" \
      --RngRun="${SEEDS[0]}" --simTime="${PT}" --ues="${UES}" \
      --configuration="${CONFIG}" --minSpeed="${MINSPEED}" --maxSpeed="${MAXSPEED}" \
      --indicationPeriodicity="${PERIOD}" --heuristicType="${HEURISTIC}" ) \
      > "${pwd_probe}/run.log" 2>&1
  prc=$?
  t1=$(date +%s); dt=$((t1 - t0))

  echo "  退出碼=${prc}, wall=${dt}s"
  if [[ ${prc} -eq 124 ]]; then
    echo "  ⚠ 連 ${PT}s 都跑不完 → 高機率卡在啟動階段(E2 termination 等待 RIC 連線是常見原因)。"
    echo "    建議:${BIN} --PrintHelp | grep -i e2   查看 e2 相關參數後再排查。"
    exit 1
  fi
  ls -la "${pwd_probe}"
  if [[ ${dt} -gt 0 ]]; then
    est=$(( dt * SIMTIME / PT ))
    echo ""
    echo "  單位耗時 ≈ $(awk -v a=$dt -v b=$PT 'BEGIN{printf "%.1f", a/b}') s(wall)/ s(sim)"
    echo "  外推 60 s 模擬 ≈ ${est}s ≈ $(awk -v e=$est 'BEGIN{printf "%.1f", e/3600}') 小時/seed"
    echo "  → 建議 --timeout 設為此值的 3 倍以上:$(( est * 3 ))"
    echo "  (mmWave 通道模型的 wall time 對 simTime 大致線性,但非嚴格,故留餘裕。)"
  fi
  echo ""
  echo "校準完成,未產生正式資料。確認數字後再跑正式收集。"
  exit 0
fi

# ---------------------------------------------------------------------------
# 平行度推算:每個 ns-3 行程為單執行緒,10 個 seed 完全獨立,
#             但 mmWave 場景單行程記憶體可達數 GB,故同時受核心與記憶體限制。
# ---------------------------------------------------------------------------
if [[ -z "${JOBS}" ]]; then
  ncpu=$(nproc 2>/dev/null || echo 2)
  memg=$(free -g 2>/dev/null | awk '/^Mem:/{print $7}')
  [[ -z "${memg}" || "${memg}" -lt 1 ]] && memg=4
  by_cpu=$(( ncpu > 2 ? ncpu - 1 : 1 ))     # 留 1 核給系統
  by_mem=$(( memg / 3 ))                     # 每行程保守估 3 GB
  [[ ${by_mem} -lt 1 ]] && by_mem=1
  JOBS=$(( by_cpu < by_mem ? by_cpu : by_mem ))
  [[ ${JOBS} -gt ${#SEEDS[@]} ]] && JOBS=${#SEEDS[@]}
  echo "▶ 自動平行度:${JOBS}(核心 ${ncpu} → ${by_cpu};可用記憶體 ${memg}G → ${by_mem})"
fi

cat <<EOF

===== C_i 資料收集 =====
  seed 數       : ${#SEEDS[@]}  (${SEEDS[*]})
  simTime       : ${SIMTIME}s  → 每 seed ${EXPECT_WINDOWS} 窗
  預期總窗數    : $(( ${#SEEDS[@]} * EXPECT_WINDOWS ))
  組態          : configuration=${CONFIG}, ues=${UES} (N_known=${EXPECT_UE}),
                  indicationPeriodicity=${PERIOD}, speed=${MINSPEED}-${MAXSPEED}
  輸出目錄      : ${OUT_DIR}
  平行度        : ${JOBS}   逾時上限: ${TIMEOUT_S}s/seed
  manifest      : ${MANIFEST}
⚠ 輸出為驗證用目錄,不會覆蓋 data/batchFinal_seeds 正式黃金資料。
========================

EOF

[[ ${DRY_RUN} -eq 1 ]] && { echo "(--dry-run:到此為止,未實際執行)"; exit 0; }

echo "seed,status,rc,wall_s,n_windows,n_ue,sha256,out_file" > "${MANIFEST}"

# ---------------------------------------------------------------------------
# 單一 seed 的執行單元
# ---------------------------------------------------------------------------
run_one() {
  local SEED="$1"
  local tag="seed${SEED}"
  local wd="/tmp/nsCi_${RUN_ID}_${tag}"
  local out="${OUT_DIR}/${tag}.txt"
  local log="${LOG_DIR}/${tag}.log"

  if [[ -e "${out}" && ${FORCE} -eq 0 ]]; then
    echo "  ⏭ ${tag} 輸出已存在,跳過(要重跑請加 --force)"
    echo "${SEED},skipped,,,,,,${out}" >> "${MANIFEST}"
    return 0
  fi

  rm -rf "${wd}"; mkdir -p "${wd}"
  echo "  ▷ ${tag} 開始 $(date +%T)"
  local t0 t1 dt rc
  t0=$(date +%s)
  ( cd "${wd}" && timeout -k 30 --foreground "${TIMEOUT_S}" "${BIN}" \
      --RngRun="${SEED}" --simTime="${SIMTIME}" --ues="${UES}" \
      --configuration="${CONFIG}" --minSpeed="${MINSPEED}" --maxSpeed="${MAXSPEED}" \
      --indicationPeriodicity="${PERIOD}" --heuristicType="${HEURISTIC}" ) \
      > "${log}" 2>&1
  rc=$?
  t1=$(date +%s); dt=$((t1 - t0))

  # 退出碼分流 —— 逾時與錯誤的後續處理完全不同,不可混為一談
  if [[ ${rc} -eq 124 || ${rc} -eq 137 ]]; then
    echo "  ⏱ ${tag} 逾時(${dt}s,未完成)— 資料不完整,不採計"
    echo "${SEED},timeout,${rc},${dt},,,," >> "${MANIFEST}"
    return 1
  fi
  if [[ ${rc} -ne 0 ]]; then
    echo "  ✗ ${tag} 錯誤 rc=${rc}(${dt}s),見 ${log}"
    echo "${SEED},error,${rc},${dt},,,," >> "${MANIFEST}"
    return 1
  fi

  local src="${wd}/DlE2RlcStats.txt"
  if [[ ! -s "${src}" ]]; then
    echo "  ✗ ${tag} 正常結束但無 DlE2RlcStats.txt 輸出,見 ${log}"
    echo "${SEED},no_output,${rc},${dt},,,," >> "${MANIFEST}"
    return 1
  fi

  # 基本完整性檢查:觀測窗數與 UE 數
  local nwin nue
  nwin=$(awk '!/^%/ && NF>3 {print $1}' "${src}" | sort -u | wc -l)
  nue=$(awk  '!/^%/ && NF>3 {print $4}' "${src}" | sort -u | wc -l)

  cp "${src}" "${out}"
  # 一併保留其他統計檔,便於日後交叉比對(不進入正式資料流)
  mkdir -p "${LOG_DIR}/${tag}_aux"
  cp "${wd}"/*.txt "${LOG_DIR}/${tag}_aux/" 2>/dev/null

  local sha
  sha=$(sha256sum "${out}" | awk '{print $1}')
  echo "${SEED},ok,0,${dt},${nwin},${nue},${sha},${out}" >> "${MANIFEST}"

  local flag=""
  [[ "${nue}" -ne "${EXPECT_UE}" ]] && flag=" ⚠UE=${nue}(預期 ${EXPECT_UE})"
  echo "  ✓ ${tag} 完成(${dt}s,觀測時點 ${nwin},UE ${nue})${flag}"
  return 0
}

export -f run_one
export RUN_ID OUT_DIR LOG_DIR MANIFEST BIN TIMEOUT_S FORCE \
       SIMTIME UES CONFIG MINSPEED MAXSPEED PERIOD HEURISTIC EXPECT_UE LD_LIBRARY_PATH

# ---------------------------------------------------------------------------
# 平行執行
# ---------------------------------------------------------------------------
START_TS=$(date +%s)
printf '%s\n' "${SEEDS[@]}" \
  | xargs -P "${JOBS}" -I{} bash -c 'run_one "$@"' _ {}
END_TS=$(date +%s)

# ---------------------------------------------------------------------------
# 收尾稽核 —— 600 窗這個分母必須站得住腳
# ---------------------------------------------------------------------------
echo ""
echo "===== 收尾稽核 ====="
ok=$(awk -F, 'NR>1 && $2=="ok"' "${MANIFEST}" | wc -l)
sk=$(awk -F, 'NR>1 && $2=="skipped"' "${MANIFEST}" | wc -l)
to=$(awk -F, 'NR>1 && $2=="timeout"' "${MANIFEST}" | wc -l)
er=$(awk -F, 'NR>1 && ($2=="error"||$2=="no_output")' "${MANIFEST}" | wc -l)

echo "  完成 ${ok} / 跳過(已存在) ${sk} / 逾時 ${to} / 錯誤 ${er}   總 wall $(( END_TS - START_TS ))s"
echo "  manifest: ${MANIFEST}"

have=$(ls -1 "${OUT_DIR}"/seed*.txt 2>/dev/null | wc -l)
echo "  ${OUT_DIR} 現有 seed 檔:${have} / ${#SEEDS[@]}"

if [[ "${have}" -ne "${#SEEDS[@]}" ]]; then
  echo ""
  echo "  ✗ seed 數不足 ${#SEEDS[@]},C_i 的「$(( ${#SEEDS[@]} * EXPECT_WINDOWS )) 窗」分母不成立。"
  echo "    缺少的 seed:"
  for s in "${SEEDS[@]}"; do
    [[ -e "${OUT_DIR}/seed${s}.txt" ]] || echo "      - seed${s}"
  done
  echo "    請補齊後再進行 4.6 節證偽測試,或在論文中明確改寫實際窗數。"
  exit 1
fi

echo ""
echo "  ✓ ${#SEEDS[@]} 個 seed 齊備。"
echo "  下一步(兩者都做完再決定是否取代黃金資料):"
echo "    1) 分布比對:確認 delay median 與 N_total 與 data/batchFinal_seeds 一致"
echo "    2) 正式驗證:python3 ${PROJ_DIR}/xapps/verification/residuals/run_Ci_experiments.py"
echo ""
echo "  註:每 seed 的 1 秒聚合窗數由分析層(run_Ci_experiments.py)依 "
echo "      indicationPeriodicity=${PERIOD} 切分認定;上表的「觀測時點」為 RLC "
echo "      統計檔的取樣時點數,兩者未必相等,請以分析層輸出為準。"
echo "===================="
