#!/usr/bin/env bash
# collect_Si_LSTM_data.sh v2 — 修正版：自動校準真實速度 + 總時間預算控制
#
# 修正的 bug（v1 的根本問題）：
#   v1 的 timeout 是憑空設定的，沒有用機器的真實模擬速度校準。
#   實測：ues=1, 60s 模擬 = 44 分鐘真實時間（比率 44:1）。
#   300s 模擬因此需要 220 分鐘（3.67 小時），v1 卻只給 70 分鐘 → 全部被錯殺。
#
# v2 修正邏輯：
#   1. 用已知 baseline 速度（可調）推算所有 timeout，不再憑空猜測。
#   2. 對 ues=2 做一次「短模擬校準」，用真實測得的速度決定要不要用 ues=2/3。
#   3. 全程追蹤總時間預算（你現在有的 8-9 小時），時間不夠時提前停止並清楚回報，
#      不會像 v1 一樣硬跑到卡死、留下空資料夾。
#   4. 每輪的 timeout 由「實測速度 × 安全係數 + 固定開銷」動態計算，不是寫死的常數。
#
# 跑法：
#   cd ~/ns-3-mmwave-oran
#   nohup bash ~/oran-zt-kpm-verification/scripts/collect_Si_LSTM_data.sh > /tmp/collectSi.log 2>&1 &
#   tail -f /tmp/collectSi.log

set -uo pipefail

NS3_DIR="${HOME}/ns-3-mmwave-oran"
OUT_DIR="${HOME}/oran-zt-kpm-verification/data/si_lstm_seeds"
PROBE_DIR="${HOME}/oran-zt-kpm-verification/data/si_probe"
mkdir -p "${OUT_DIR}" "${PROBE_DIR}"

CONFIG=1
MINSPEED=3
MAXSPEED=10
PERIOD=1.0
HEURISTIC=-1

# ---- 已知的真實速度基準（你昨晚實測：ues=1, 60s 模擬 = 44 分鐘）----
# 若你的機器狀況變了（例如換機器、CPU 負載不同），改這個數字。
KNOWN_RATE_UES1_SEC_PER_SIMSEC=44   # 秒(真實) / 秒(模擬)，ues=1 時

# ---- 總時間預算：你現在有的時間，單位秒。預設 8.5 小時 ----
TOTAL_BUDGET_SEC=$((20*3600))   # 你確認可以跑更久，給 20 小時上限（非硬性，夠用就會提早結束）
SCRIPT_START=$(date +%s)
DEADLINE=$((SCRIPT_START + TOTAL_BUDGET_SEC))

remaining_sec() { echo $((DEADLINE - $(date +%s))); }
fmt_hms() { local s=$1; printf '%dh%02dm' $((s/3600)) $(((s%3600)/60)); }

cd "${NS3_DIR}" || { echo "找不到 ${NS3_DIR}"; exit 1; }

echo "############################################################"
echo "# 總時間預算：$(fmt_hms ${TOTAL_BUDGET_SEC})，開始於 $(date +%T)，"\
     "截止 $(date -d @${DEADLINE} +%T 2>/dev/null || date -r ${DEADLINE} +%T)"
echo "############################################################"

# ---- 通用執行函式：帶動態 timeout + 完成檢查 + 真實耗時量測 ----
# 回傳 0=成功, 1=失敗/timeout；並把「真實耗時秒數」寫到全域變數 LAST_ELAPSED
run_sim() {
  local ues=$1 simtime=$2 seed=$3 dest=$4 timeout_s=$5
  local tag="ues${ues}_t${simtime}_seed${seed}"
  local wd="/tmp/nsSi_${tag}"
  rm -rf "${wd}"; mkdir -p "${wd}"
  local t0 t1
  t0=$(date +%s)
  echo "-- [${tag}] 開始 $(date +%T)（給 $(fmt_hms ${timeout_s})，"\
       "剩餘預算 $(fmt_hms $(remaining_sec))）--"
  timeout "${timeout_s}" ./ns3 run "scratch/scenario-three \
      --RngRun=${seed} --simTime=${simtime} --ues=${ues} \
      --configuration=${CONFIG} --minSpeed=${MINSPEED} --maxSpeed=${MAXSPEED} \
      --indicationPeriodicity=${PERIOD} --heuristicType=${HEURISTIC}" \
      --cwd="${wd}" > "${wd}/run.log" 2>&1
  local ec=$?
  t1=$(date +%s)
  LAST_ELAPSED=$((t1 - t0))
  if [ ${ec} -eq 124 ]; then
    echo "  TIMEOUT [${tag}]（跑了 $(fmt_hms ${LAST_ELAPSED})，超過給定的 $(fmt_hms ${timeout_s})）→ 跳過"
    return 1
  fi
  if [ -s "${wd}/DlE2RlcStats.txt" ]; then
    local lines; lines=$(wc -l < "${wd}/DlE2RlcStats.txt")
    cp "${wd}/DlE2RlcStats.txt" "${dest}/${tag}.txt"
    echo "  完成 [${tag}]（實際耗時 $(fmt_hms ${LAST_ELAPSED})） — ${lines} 行"

    # ---- 即時完整性檢查：立刻確認基數與模擬時長是否符合預期 ----
    # 教訓來源：舊的 sim_300s_baseline 實際只錄到 4.2 秒、N_known=35（廢棄資料），
    # 若不當場檢查，隔天才發現整批白跑。
    python3 - "${dest}/${tag}.txt" "${ues}" "${simtime}" << 'PYEOF'
import sys
sys.path.insert(0, __import__("os").path.expanduser(
    "~/oran-zt-kpm-verification/xapps/verification/residuals"))
import cardinality as C
path, ues, simtime = sys.argv[1], int(sys.argv[2]), float(sys.argv[3])
recs = list(C.load_rlc(path))
if not recs:
    print("  ⚠️  完整性檢查：檔案讀不到任何記錄！")
    sys.exit(1)
windows = sorted({C._window_key(r) for r in recs})
span = windows[-1] - windows[0] if len(windows) > 1 else 0
n_known_expect = ues * 7  # 固定 ues=1 -> 7，與 C_i 章節 N_known 一致（刻意不用 ues=2/3）
series = C.field_cardinality_series(recs, True, 1)
uniq = sorted(set(series.values()))
print(f"  完整性檢查：窗數={len(windows)}, 實錄時長={span:.1f}s（預期~{simtime}s），"
      f"N_total值域={uniq}（預期含{n_known_expect}附近）")
if span < simtime * 0.8:
    print(f"  ⚠️  警告：實錄時長遠低於預期 simTime={simtime}s，模擬可能提早中斷！")
PYEOF
    return 0
  else
    echo "  無有效輸出 [${tag}]（exit=${ec}，耗時 $(fmt_hms ${LAST_ELAPSED})）"
    return 1
  fi
}

# ---- 計算某 ues/simtime 組合的 timeout：用已知或校準到的速度 × 安全係數 + 固定開銷 ----
compute_timeout() {
  local rate=$1 simtime=$2
  local est=$(( rate * simtime ))          # 估計真實秒數
  local safe=$(( est * 3 / 2 ))            # 安全係數 1.5x
  local fixed_overhead=300                 # 固定開銷（啟動、寫檔）
  echo $((safe + fixed_overhead))
}

echo
echo "############################################################"
echo "# 階段 0：鎖定 ues=1（N_known=7）— 與 C_i 章節的封閉場域母體一致"
echo "############################################################"
echo "  決策依據：C_i 已將 N_known=7 定為封閉場域的硬不變量宣稱。若 S_i/LSTM 改用"
echo "  ues=2/3（N_known=14/21），系統模型前後不一致，會被質疑「環境參數以誰為準」。"
echo "  故不做 ues=2 校準，全程固定 ues=1，僅拉長 simTime 以取得 LSTM 所需長序列。"

MAIN_UES=1
RATE=${KNOWN_RATE_UES1_SEC_PER_SIMSEC}

echo
echo "############################################################"
echo "# 階段 1：主力長模擬（ues=${MAIN_UES}, 速度=${RATE}秒/模擬秒）"
echo "############################################################"

# ---- 依剩餘預算決定 simTime：目標優先序 300s > 180s，只要塞得下「至少 1 輪」就採用 ----
# 180s 是有意義的下限（比現有 60s baseline 長 3 倍）；不會為了塞更多輪而退化回 60s，
# 因為 60s 序列你已經有 10 份了，重複收集沒有新資訊。
choose_simtime() {
  local rate=$1 budget=$2
  for st in 300 180; do
    local t; t=$(compute_timeout "${rate}" "${st}")
    # 只要求塞得下 1 輪 + 安全緩衝（不再要求 2 輪，避免無謂降級）
    if [ $(( t + 300 )) -le "${budget}" ]; then
      echo "${st}"; return
    fi
  done
  echo "SKIP"   # 連一輪 180s 都塞不下才真正放棄，回報給使用者自己決定
}

SIMTIME=$(choose_simtime "${RATE}" "$(remaining_sec)")
if [ "${SIMTIME}" = "SKIP" ]; then
  echo "⚠️  剩餘時間 $(fmt_hms $(remaining_sec)) 連一輪 180s 模擬都塞不下"\
       "（單輪估計需要 $(fmt_hms $(compute_timeout "${RATE}" 180))）。"
  echo "    這不是無法解決，是預算不夠：請確認 TOTAL_BUDGET_SEC 是否反映你實際能給的時間，"
  echo "    調大後重跑即可。腳本在此停止，不會用 60s 硬湊資料。"
  exit 1
fi
RUN_TIMEOUT=$(compute_timeout "${RATE}" "${SIMTIME}")
echo "依剩餘預算 $(fmt_hms $(remaining_sec))，選定 simTime=${SIMTIME}s，"\
     "每輪 timeout=$(fmt_hms ${RUN_TIMEOUT})"

SEED_POOL=(4200 4201 4202 4203)   # 3-4 個獨立 seed，驗證 S_i 跨移動軌跡的穩健性
COMPLETED=()
for SEED in "${SEED_POOL[@]}"; do
  rem=$(remaining_sec)
  need=$(( RUN_TIMEOUT + 60 ))   # 留 60 秒緩衝
  if [ "${rem}" -le "${need}" ]; then
    echo "剩餘時間 $(fmt_hms ${rem}) 不足以再跑一輪（需要 $(fmt_hms ${need})）→ 停止排程"
    break
  fi
  if run_sim "${MAIN_UES}" "${SIMTIME}" "${SEED}" "${OUT_DIR}" "${RUN_TIMEOUT}"; then
    COMPLETED+=("${SEED}")
  fi
done

echo
echo "############################################################"
echo "# 完成 $(date +%T)（總耗時 $(fmt_hms $(( $(date +%s) - SCRIPT_START ))))"
echo "############################################################"
echo "已收集 seed：${COMPLETED[*]:-（無）}"
echo "檔案："
ls -la "${OUT_DIR}/" 2>/dev/null
echo
if [ ${#COMPLETED[@]} -eq 0 ]; then
  echo "⚠️  本輪未產出任何完整檔案。可能原因：時間預算從一開始就不夠跑完一輪 ${SIMTIME}s 模擬。"
  echo "    建議：縮短 simTime 目標，或安排更長的預算重跑。"
else
  echo "下一步："
  echo "  python3 ~/oran-zt-kpm-verification/xapps/verification/residuals/audit_Si_data.py \\"
  echo "      ~/oran-zt-kpm-verification/data/si_lstm_seeds/"
fi
