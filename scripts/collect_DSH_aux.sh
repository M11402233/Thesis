#!/usr/bin/env bash
# collect_DSH_aux.sh — 重跑 D-SH（ues=1, 300s, seed 4200–4203），保留 PHY/MAC trace
#
# 為什麼另寫一支，而不是改 collect_Si_LSTM_ues1_final.sh：
#   原腳本不會跳過已存在的 seed，且會覆寫 data/si_lstm_seeds/ues1_t300_seedXXXX.txt——
#   那是整份論文 S_i／H_i／xApp／對抗性分析的基礎資料，不該冒險。
#   本腳本輸出到全新目錄 data/si_lstm_aux/，完全不碰原檔。
#
# 附帶的驗證（重要）：
#   ns-3 以 RngRun 決定隨機性，理論上為確定性。本腳本每跑完一個 seed，就把新產生的
#   DlE2RlcStats.txt 與你既有的 D-SH 檔做逐位元組比對：
#     一致   → 這批 PHY trace 確實屬於 D-SH 那次模擬，可與 D-SH 聯合分析
#     不一致 → 兩次模擬不同（版本／編譯／環境差異），PHY 與 D-SH 不可混用，
#              後續 PRB 分析須改用 aux 內自己的 DlE2RlcStats.txt
#   兩種結果都要寫進論文的可重現性說明，所以務必看比對輸出。
#
# 磁碟：只保留有用的檔案，RxPacketTrace 壓縮。刻意略過 EnbSchedAllocTraces.txt
#   （無 cellId 欄位，無法歸屬節點；60s 就 430 萬行，300s 約 2 千萬行）。
#
# 跑法（單一程序，約 15 小時）：
#   cd ~/ns-3-mmwave-oran
#   nohup bash ~/oran-zt-kpm-verification/scripts/collect_DSH_aux.sh > /tmp/collectAux.log 2>&1 &
#   tail -f /tmp/collectAux.log
#
# 想縮短時間（機器 4 核；ns-3 為單執行緒；先確認記憶體足夠再用）：
#   SEEDS="4200 4201" nohup bash .../collect_DSH_aux.sh > /tmp/collectAux_a.log 2>&1 &
#   SEEDS="4202 4203" nohup bash .../collect_DSH_aux.sh > /tmp/collectAux_b.log 2>&1 &

set -uo pipefail

NS3_DIR="${HOME}/ns-3-mmwave-oran"
EXIST_DIR="${HOME}/oran-zt-kpm-verification/data/si_lstm_seeds"     # 只讀，用於比對
AUX_DIR="${HOME}/oran-zt-kpm-verification/data/si_lstm_aux"         # 新目錄
mkdir -p "${AUX_DIR}"

# ---- 與 collect_Si_LSTM_ues1_final.sh 完全一致的參數（逐項核對過）----
CONFIG=1
MINSPEED=3
MAXSPEED=10
PERIOD=1.0
HEURISTIC=-1
UES=1
SIMTIME=300
SEEDS=(${SEEDS:-4200 4201 4202 4203})

RATE=44                                     # 秒(真實)/秒(模擬)，ues=1，沿用原腳本實測值
RUN_TIMEOUT=$(( RATE * SIMTIME * 3 / 2 + 300 ))

# 需要保留的檔案（其餘丟棄）
KEEP_PLAIN=(DlE2RlcStats.txt cu-cp-cell-1.txt cu-up-cell-1.txt ues.txt enbs.txt CellIdStats.txt)
KEEP_GZ=(RxPacketTrace.txt DlMacStats.txt)

fmt_hms() { local s=$1; printf '%dh%02dm' $((s/3600)) $(((s%3600)/60)); }

# ---- 前置檢查 ----
cd "${NS3_DIR}" || { echo "找不到 ${NS3_DIR}"; exit 1; }

avail_kb=$(df -Pk /tmp | awk 'NR==2{print $4}')
avail_gb=$(( avail_kb / 1024 / 1024 ))
echo "/tmp 可用空間：${avail_gb} GB（單一 seed 之工作目錄約需 2–3 GB）"
if [ "${avail_gb}" -lt 4 ]; then
  echo "⚠️  /tmp 空間不足 4 GB，請先清理（例如 rm -rf /tmp/nsSi_* /tmp/nsAux_*）再重跑。"
  exit 1
fi
avail_h_kb=$(df -Pk "${AUX_DIR}" | awk 'NR==2{print $4}')
echo "輸出目錄可用空間：$(( avail_h_kb / 1024 / 1024 )) GB（預估總需求 < 1 GB）"

if [ ! -x ./ns3 ]; then
  echo "找不到 ./ns3 可執行檔，請確認在 ns-3 目錄內。"; exit 1
fi

echo
echo "############################################################"
echo "# D-SH 重跑（保留 PHY/MAC trace）— seed: ${SEEDS[*]}"
echo "# simTime=${SIMTIME}s  timeout/seed=$(fmt_hms ${RUN_TIMEOUT})  開始 $(date +%T)"
echo "############################################################"

DONE=(); FAIL=(); IDENT=(); DIFFER=()
for SEED in "${SEEDS[@]}"; do
  tag="ues${UES}_t${SIMTIME}_seed${SEED}"
  wd="/tmp/nsAux_${tag}"
  out="${AUX_DIR}/${tag}_aux"

  if [ -s "${out}/DlE2RlcStats.txt" ] && [ -s "${out}/RxPacketTrace.txt.gz" ]; then
    echo "-- [${tag}] 已存在於 ${out}，略過 --"
    DONE+=("${SEED}"); continue
  fi

  rm -rf "${wd}"; mkdir -p "${wd}" "${out}"
  t0=$(date +%s)
  echo "-- [${tag}] 開始 $(date +%T) --"

  timeout "${RUN_TIMEOUT}" ./ns3 run "scratch/scenario-three \
      --RngRun=${SEED} --simTime=${SIMTIME} --ues=${UES} \
      --configuration=${CONFIG} --minSpeed=${MINSPEED} --maxSpeed=${MAXSPEED} \
      --indicationPeriodicity=${PERIOD} --heuristicType=${HEURISTIC}" \
      --cwd="${wd}" > "${wd}/run.log" 2>&1
  ec=$?
  el=$(( $(date +%s) - t0 ))

  if [ ${ec} -eq 124 ]; then
    echo "  TIMEOUT [${tag}]（跑了 $(fmt_hms ${el})）→ 跳過"
    FAIL+=("${SEED}"); rm -rf "${wd}"; continue
  fi
  if [ ! -s "${wd}/DlE2RlcStats.txt" ] || [ ! -s "${wd}/RxPacketTrace.txt" ]; then
    echo "  無有效輸出 [${tag}]（exit=${ec}，耗時 $(fmt_hms ${el})）；保留 ${wd} 供檢查"
    FAIL+=("${SEED}"); continue
  fi

  # ---- 保留有用檔案 ----
  for f in "${KEEP_PLAIN[@]}"; do
    [ -e "${wd}/${f}" ] && cp "${wd}/${f}" "${out}/${f}"
  done
  for f in "${KEEP_GZ[@]}"; do
    [ -e "${wd}/${f}" ] && gzip -c "${wd}/${f}" > "${out}/${f}.gz"
  done
  cp "${wd}/run.log" "${out}/run.log" 2>/dev/null

  rlc_lines=$(wc -l < "${wd}/DlE2RlcStats.txt")
  phy_lines=$(wc -l < "${wd}/RxPacketTrace.txt")
  echo "  完成 [${tag}]（耗時 $(fmt_hms ${el})）RLC ${rlc_lines} 行 / PHY ${phy_lines} 行"

  # ---- 確定性檢查：與既有 D-SH 逐位元組比對 ----
  ref="${EXIST_DIR}/${tag}.txt"
  if [ -s "${ref}" ]; then
    if cmp -s "${ref}" "${out}/DlE2RlcStats.txt"; then
      echo "  ✓ 與既有 D-SH 逐位元組相同 → 本次 PHY trace 屬於 D-SH 該次模擬"
      IDENT+=("${SEED}")
    else
      echo "  ✗ 與既有 D-SH 不同（行數 既有 $(wc -l < "${ref}") / 本次 ${rlc_lines}）"
      echo "    → 兩次模擬並不相同；PHY 與既有 D-SH 不可混用（見檔頭說明）"
      DIFFER+=("${SEED}")
    fi
  else
    echo "  （找不到既有 ${ref}，略過比對）"
  fi

  rm -rf "${wd}"      # 釋放 /tmp 空間
  DONE+=("${SEED}")
done

echo
echo "############################################################"
echo "# 完成 $(date +%T)"
echo "############################################################"
echo "成功：${DONE[*]:-（無）}"
echo "失敗：${FAIL[*]:-（無）}"
echo "與既有 D-SH 相同：${IDENT[*]:-（無）}"
echo "與既有 D-SH 不同：${DIFFER[*]:-（無）}"
echo
ls -la "${AUX_DIR}/" 2>/dev/null
[ ${#FAIL[@]} -eq 0 ] || exit 2
