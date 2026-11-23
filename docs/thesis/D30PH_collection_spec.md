# D-30PH：含換手之第二階段資料重收規格（v0，2026-11-23；結果出來前寫定）

> 依據：`D30P1_ho_pilot_spec.md` §9（31 s、4 seed：允許換手使延遲 > 1 s 之樣本由 0.944 % 降至 0.030 %，比值 0.032，有效）與 §7 之啟動規則。
> 使用者 2026-11-23 指示「依規則寫第三步後啟動就好」：本規格即第 3 步規格；該指示視為 §7 所要求之啟動確認。

## 1. 目的與動機

- 動機（§7 之「明顯縮小」情形）：D-30P1（不換手）之延遲長尾（中位數 8.4 ms、p99 25 s、最大 290 s）與「使用者停在訊號極差之 cell 而場景不換手」有關；小型驗證在 31 s 內顯示換手使長尾縮小約 30 倍。
- **本步要回答的問題**：全長（301 s）下，允許換手之資料是否仍維持短尾？> 30 s 之延遲是否消失？（31 s 驗證看不到 > 30 s。）
- 本步**只收集與驗收資料**，不做 S_i 或任何偵測分析，不改論文數字。分析用主檔、ZT_DATASET 登記、成員變動（換手使 cell 成員每窗不同）之處理，另寫規格，不在本步。

## 2. 資料

| 項目 | 值 |
|---|---|
| 名稱 | D-30PH |
| ns-3 | `~/ns-3-mmwave-oran-r11`（凍結 md5：二進位 `bed17a3a19ccb01ceed45618126f54df`，與小型驗證 G0′ 之正式二進位相同；lte／network／mmwave 函式庫、`lte-rlc-am.{cc,h}`、`mmwave-bearer-stats-calculator.{cc,h}` 之 md5 見 `scripts/r9/d30ph_chain.sh` 閘門）；GCC 13.4.0 |
| 環境變數 | `ZT_R7_S2=1`、`ZT_R10_RETX_TAG=1`（模式 1：重傳 PDU 沿用首次傳送時間戳）；**不設** `ZT_R10_TRACE` |
| 命令列 | `--RngRun=<seed> --simTime=301 --totalUes=30 --e2nrEnabled=true --handoverMode=FixedTtt --configuration=1 --minSpeed=3 --maxSpeed=10 --indicationPeriodicity=1.0 --heuristicType=-1`（與小型驗證相同；與 D-30H 相同，另加 r11 之環境變數） |
| seed | 4200–4207，8 個同時（新機器 i7-14700，14 核、31 GB） |
| 輸出 | `data/ues30_ph_r11_seeds/D30PH_ues30_t300_seed<s>_aux/`；主檔 `D30PH_ues30_t300_seed<s>.txt`；各 seed 之 `collect_<s>.log` |
| 驗收輸出 | `data/results/phase2/D30PH_phase0/`（`summary.txt`、各檢查 JSON；通過 `DONE`、失敗 `STOPPED`） |
| 腳本 | 收集 `scripts/collect_d30ph_r11.sh`（由 `collect_d30p_r9.sh` 改：加 `--handoverMode=FixedTtt`；預設 r11；輸出目錄守衛加入 `ues30_p_r10_seeds`、`r11c_*`）；鏈 `scripts/r9/d30ph_chain.sh` |

與其他資料之關係：D-30P1（`ues30_p_r10_seeds`，不換手，r11）＝同二進位、同環境變數、**唯一差別為 `--handoverMode`**；D-30H r8d（`ues30_ho_r8d_seeds`，換手，r8d）＝同 `--handoverMode`，二進位為較舊之 r8d（無 r9 以後之輸出、RLC 延遲為累計平均）。D-30PH 即「兩者之交集」。三者皆唯讀，不併入、不覆寫。

## 3. 資源與防護

- 記憶體：既往峰值 RSS 約 1.0–1.1 GB／seed（D-30P1 1,022 MB、D-30H r8d 1,080 MB；小型驗證 31 s 為 0.6 GB），8 個同時約 9 GB／31 GB。收集腳本之防護：`MemAvailable < 600 MB` 即停止該次模擬並保留工作目錄與 `mem_trace.tsv`；每 60 s 記錄 RSS 與可用記憶體。
- 磁碟：新機器可用 153 GB；既往每 seed 之 aux 約 0.7–0.9 GB（壓縮後），工作目錄為未壓縮暫存，完成後刪除。
- 時間：**預估 20–30 小時**（既往全長實測：D-30P1 不換手 18.7 h、D-30H r8d 換手 28.1 h；本資料為 r11 ＋ 換手，介於兩者之上）。收集期間**不得在新機器同時啟動重負載**（如 PSRO 訓練），否則可能觸發記憶體防護或拖慢全部 seed；須先問使用者。
- 逾時：`RUN_TIMEOUT` ≈ 75 h（腳本公式 600 × 301 × 1.5 + 600 s），為保險而非預期。
- **不得終止**這些行程。

## 4. 驗收（任一失敗即停，不調參數；結果寫入 `D30PH_phase0/`）

| 編號 | 內容 | 判準 |
|---|---|---|
| G | 啟動前：r11 建置 md5 與凍結值相同；8 個 D-30H 參照存在；輸出目錄為空 | 全過 |
| K1–K5 | `check_r9_outputs.py`（收集腳本內建，每 seed） | 全過 |
| N | 每窗 N_total = 30、IMSI 1–30、無缺窗（收集腳本內建；D-30H r8d 於換手下亦通過此檢查） | 全過 |
| Q-0 | meta 記錄 `ZT_R7_S2=1`、`ZT_R10_RETX_TAG=1`，二進位與 `lte-rlc-am.cc` md5 與 r11 樹相同 | 全過 |
| **Q-2H（新）** | 與同 seed 之 D-30H aux（`scripts/r9/check_d30ph_phase0.py q2h`）：排除檔（RLC 延遲相關、R7b、du-cell、`_r11eff`、D-30H 所無之檔）以外，**逐行相同**；唯一容忍為 `RxPacketTrace.txt` 之 SINR 欄末位（GCC 11 vs 13，小型驗證已證實）；D-30H 有而此處無之檔 → 失敗 | 0 不同 |
| Q-4 | `_r11eff` 與 `_percell` 一致性（同 D-30P1 §6.2 之登記） | 全過 |
| P-3 | percell 加總 = exact（RLC） | 全過 |
| P-5 | 只報告 | — |
| P-6 | seed 4200 之 31 s 短跑為全長 run 之前綴（`p6_prefix.py`，同二進位、同命令列） | 通過 |

**檢查本身之事前驗證（皆唯讀，2026-11-23；不引用其數字）**
- Q-2H：正向對照＝小型驗證 `main_4200`（31 s）對 D-30H seed 4200 之 aux，前綴模式 → 通過（55 檔）；反向對照＝同一資料對 seed 4201 之 aux → 失敗（26 檔）。故檢查可通過亦可失敗。
- K1–K5、Q-4、P-3 已在小型驗證輸出（`data/r11c_ho/main_4200`，含 1855 次換手之同批資料）上跑過，皆通過；證明這些檢查在換手下不會因設計假設（不換手）而誤判。

**已預見之失敗點（出現時照實回報，不調參數）**
- Q-2H：D-30H 為 GCC 11、本資料為 GCC 13；31 s 內只有 SINR 末位差異，但 301 s 下浮點末位差異理論上可累積為其他欄位之差異。若出現 SINR 欄以外之差異 → 停止；因此無法分辨「編譯器累積」與「r11 修改所致」。屆時之替代方案（須使用者決定）：以 `~/ns-3-mmwave-oran-r8d-g13`（GCC 13 之 r8d，已建置）對同 seed 跑 301 s 同編譯器參照（單 seed 約 28 h）。
- 記憶體防護觸發、逾時、某 seed 當機（D-30H r8 之 seed 4202 曾於 RLC AM 換手轉送處當機，r8d 已修正，r8d 全長 8/8 完成）：保留工作目錄，回報，不重跑，由使用者決定。
- 全長之延遲長尾**不一定消失**（換手只處理「停在爛 cell」之情形，不處理其他中斷）。若仍有 > 30 s 之延遲，照實回報，不調場景。

## 5. 不做之事

- 不改 ns-3、不改命令列、不改 seed；不併入 `ues30_p_r10_seeds`、`ues30_ho_r8d_seeds` 或任何舊資料；不覆寫任何既有目錄。
- 不執行 S_i／E9／xApp 等分析（無 `ZT_DATASET` 登記）；不產生論文數字。
- 不在收集期間改 `~/zt_dev/*` 程式鏡像（避免與後續分析之 md5 檢查衝突）。

## 6. 報告項（不設門檻，收集完成後之描述性統計，另以腳本輸出）

換手次數／seed、~~延遲 > 1 s 與 > 30 s 之樣本比例（與 D-30P1 同口徑，來自 `_r11eff`）~~（**設計疏漏，見 §6a**）、各 cell 之判定分布、(cell, 窗) 有效 UE 數分布、記憶體峰值與耗時。

## 6a. 長尾判讀（2026-11-23 自查後補登；D-30PH 資料尚未產生，寫定於結果出來前）

**自查發現之疏漏**：§6 原寫「延遲 > 1 s 之樣本比例，來自 `_r11eff`」，但 `_r11eff` 每列只有 (cell, UE, 窗) 之累計樣本數與延遲總和，**算不出逐封包比例**；小型驗證之逐封包比例來自追蹤檔，而 D-30PH 不開追蹤。故改以 (UE, 窗) 層級定義，且本步之主要問題（全長下長尾是否縮小）原本**沒有事前寫定之判準**，一併補上。

- 腳本：`scripts/r9/analyze_d30ph_tail.py`（只讀）。單位 = (UE, 窗)，只用 mmWave cell（cell ≠ 1）：各 (cell, IMSI, LCID) 之累計 (nEff, delaySumEff) 逐窗差分，同 UE 同窗跨 cell 相加；ΔnEff > 0 為有效 (UE, 窗)，區間平均 = ΣΔdelaySumEff ÷ ΣΔnEff。
- 指標：**W1**（主）＝有效 (UE, 窗) 中區間平均 > 1 s 之比例；W2 ＝ > 30 s 之個數；W3 ＝最大值；C ＝覆蓋率。
- **判準**（D-30PH 對 D-30P1，同 8 seed、窗 0–299，合併）：W1 比值 ≤ 0.2 →「明顯縮小」；≥ 1.5 →「變大」；其餘 →「無明顯差異」（與小型驗證 §5 相同門檻）。W2、W3、C 只報告。
- 單位提醒：此為 (UE, 窗) 層級，與小型驗證之逐封包比例（0.030 % vs 0.944 %）不同，不可直接比較。
- 前提檢查（已做）：每個 (cell, UE, LCID) 一旦出現，之後每窗皆有列（換手小型驗證與 D-30P1 皆 0 跳窗）；腳本若遇跳窗會計數並報告。
- **乾跑揭露**（只用已看過之資料，輸出不入 repo）：(1) 小型驗證 31 s，HO 對 NoAuto，4 seed、窗 0–29：W1 0.00167 vs 0.124，比值 0.013，與逐封包結果方向一致；覆蓋率 0.998／0.853 與小型驗證相同。(2) D-30P1 對自身，300 窗：有效 (UE, 窗) 60,556、W1 0.1389、最大 290.77 s，**與 `D30P1_si_uemed_spec.md` §4 已報告之 60,556／13.9 %／290,768 ms 一致**，比值 1.0。門檻未因乾跑調整。

## 6b. 其他自查結果（2026-11-23）

- 命令列：D-30H 明設 `--trafficModel=0`，本資料未設；`scenario-three.cc:188–195` 預設值為 0，故相同（小型驗證 G2′-g13 亦已實證）。
- Q-2H 之全長模式（正式驗收用）原先只測過前綴模式，補測：r11c 31 s 對同編譯器 r8d-g13 31 s → 通過（55 檔）；對 seed 4201 → 失敗（48 檔）；刪去一個檔（X2Stats）→ 判為 `MISSING_IN_PH` 失敗。
- Q-0：檢查 meta 之 `ZT_R7_S2=1`、`ZT_R10_RETX_TAG=1`、`ns3_dir` 與 8 個檔之 md5；收集腳本之 meta 格式與 D-30P1 相同，適用。
- 換手是否真的發生：未設獨立閘門，但 Q-2H 要求 `EnbHandoverStartStats`／`CellIdStatsHandover` 等與 D-30H 逐行相同，已涵蓋。
- Q-2H 逐檔單執行緒、8 seed 依序：預估數小時，屬可接受之耗時，非錯誤。
- 監看程式原本只看 log 警示與 DONE／STOPPED，若鏈本身異常消失（無 DONE 亦無 STOPPED）不會發現；已改為同時檢查鏈行程是否存在。


## 7. 之後

驗收全過 → 另寫分析規格（成員變動、`ZT_DATASET` 登記、S_i 在換手資料上之定義），經使用者確認後才跑分析。驗收失敗 → 依 §4 回報，等待使用者決定。

## 8. 執行紀錄
- 2026-11-23 02:33:17 UTC（台灣 10:33）：`scripts/r9/d30ph_chain.sh` 啟動（`setsid nohup`，log `data/results/phase2/D30PH_chain.log`）。啟動閘門通過（r11 md5 與凍結值相同）；8 個 seed 同時執行；以 `/proc/<pid>/environ` 與 `pgrep` 確認命令列為 `--RngRun=<s> --simTime=301 --totalUes=30 --e2nrEnabled=true --handoverMode=FixedTtt --configuration=1 --minSpeed=3 --maxSpeed=10 --indicationPeriodicity=1.0 --heuristicType=-1`，環境變數僅 `ZT_R7_S2=1`、`ZT_R10_RETX_TAG=1`。預估完成 20–30 h（**11/24 台灣時間約 06:30–16:30**；2026-11-23 更正：原記「11/24 下午至 11/25 上午」為時區換算錯誤），之後鏈自動做逐 seed 驗收（Q-2H 逐行比對，預估數小時）與 P-6（再約 2 h）。
- **2026-11-23 09:35 UTC（台灣 17:35）中斷**：新機器重開機（`last -x`：核心 6.8.0-138 → 6.8.0-149；日誌為乾淨關機 `systemd-reboot`、`Sending SIGTERM to remaining processes`；重開後 tty2 有使用者登入；無 OOM／MCE／過熱紀錄；未啟用自動重開機）。鏈與 8 個模擬被終止，**無完整輸出可用**：耗時 25,270 s、模擬進度 92.6–99.3 s／301 s（約 31 %）；鏈無 `STOPPED`／`DONE` 標記，`summary.txt` 停在啟動紀錄。反向通道由 autossh 自動恢復。部分輸出（`data/ues30_ph_r11_seeds/`，14 GB，含 `_work_*` 與 `mem_trace.tsv`）**保留不刪**，重啟前須改名封存（鏈對非空目錄會拒絕啟動）。收集作業無法續跑（ns-3 無檢查點），須整批重跑。
- **2026-11-23 09:40:15 UTC（台灣 17:40）重啟**（使用者 11-23：「不會（再重開機）直接安全重啟」）：中斷之輸出改名封存為 `data/ues30_ph_r11_seeds_interrupted_20261123/`（含 `README_INTERRUPTED.txt`）、`data/results/phase2/D30PH_phase0_interrupted_20261123/`、`D30PH_chain_interrupted_20261123.log`，均未刪除。以同一 `scripts/r9/d30ph_chain.sh` 重新啟動；閘門通過，8 個 seed 同時執行，命令列與環境變數與首次相同（已以 `/proc/<pid>` 核對：`--handoverMode=FixedTtt`，`ZT_R7_S2=1`、`ZT_R10_RETX_TAG=1`，無 `ZT_R10_TRACE`）。預估完成 20.5–26.7 h → **11/24 台灣時間約 14:10–20:20**，之後鏈自動驗收（Q-2H、Q-4、P-3、P-6）。
