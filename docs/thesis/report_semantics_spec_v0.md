# 報表語意與統計修正規格 v0（2026-11-13；草稿，待使用者確認 §8）

> 起因：`docs/thesis/ns3_report_semantics_audit_20261113.md`（E2 RLC 計算器從未重置）與 `D30H_handover_data_spec.md` §7.5(b)（cell 被最後一筆 PDU 覆寫）。
> 本規格**只定義語意與驗證程序**；ns-3 尚未修改。

## 0. 使用者決策（2026-11-13，已定）

| 項 | 決策 |
|---|---|
| 路徑 | 分階段 (c)，技術驗證通過後走 (a)：若論文仍研究每窗量測，所有依賴這些輸入之主要結論（含 E19）都重新評估。**不採** (b)「改寫為累計平均以維持原主張」 |
| 現有結果 | 檔案、程式、數值保留；已標記「量測語意待修正，暫不支持區間量測主張」（`thesis_v11.md`、`chapter6_draft.md` 檔首、`data/results/d30*/STATUS_MEASUREMENT_SEMANTICS.md`、CLAUDE.md） |
| 順序 | 標記 → 本規格 v0 → 驗證反推精度與樣本對應 → 重跑 S_i／E9；記憶體另線短跑；E19 先不重訓 |
| 選 (c) 之理由 | 控制重跑成本，**不是**看新結果好不好再決定是否修正 |
| 換手參數 | 保留 3 dB／110 ms；修好量測後再做小範圍敏感度比較 |
| 乒乓定義 | 3GPP TR 36.839 V11.1.0 §5.2.2（使用者提供）：停留時間 = 兩次成功換手完成之間；MTS = 1 s；分母 = 成功換手總數（排除失敗） |

## 1. 參照（原始碼；ns-3 `~/ns-3-mmwave-oran`，commit `8c42089d`＋本地修改 `scenario-three.cc`、`sta-wifi-mac.h`）

| # | 位置 | 事實 |
|---|---|---|
| F1 | `src/lte/helper/mmwave-bearer-stats-calculator.cc:212–218, 297–312` | 鍵 = (IMSI, LCID)；`m_dlCellId[p] = cellId` 每筆 Tx／Rx 覆寫；`m_dlRxPackets[p]++` 與 `m_dlDelay[p]->Update(delay)` 在**同一分支** |
| F2 | 同檔 `EndEpoch()` 586–597 | protocol type 以 "E2" 開頭不 `ResetResults()` |
| F3 | `src/mmwave/helper/mmwave-helper.cc:3218, 3224` | "E2RLC"（mmWave，寫 `DlE2RlcStats.txt`）、"E2RLCLTE" |
| F4 | `src/mmwave/model/mmwave-enb-net-device.cc:831`、`src/lte/model/lte-enb-net-device.cc:1229` | 唯二 `ResetResultsForImsiLcid` 呼叫，皆 PDCP；由**第一個報該 UE 之 cell** 重置 |
| F5 | `mmwave-enb-net-device.cc:699, 946, 1132` | CU-UP／CU-CP／DU 報表名單 = 報表時點 `m_rrc->GetUeMap()` |
| F6 | `mmwave-enb-net-device.cc:811, 815` | DU 報表之 RLC 延遲、PDU size 取自同一未重置計算器 |
| F7 | 計算器 `WriteDlResults` 438–480 | 列 = `m_dlTxPackets` 之鍵（有 Tx 即有列）；delay 以 `(*it) * 1e-9` 輸出，ofstream 預設精度 6 位有效數字 |
| F8 | 同檔 `GetDlDelayStats` 755–767 | 欄位依序 mean、stddev、min、max；無 Rx 時四欄皆 0.0 |
| F9 | `src/lte/model/lte-enb-net-device.cc:128–224, 374` | `ts_actions_for_ns3.csv`（timestamp, IMSI, targetCellId）每 `e2Periodicity` 讀一次，可下達換手命令（人工換手案例之候選機制；執行時點未驗證） |
| F10 | `zt_kpm_xapp.py:198` | 驗證管線讀 `p[10]`（累計平均）作為該窗延遲 |

## 2. 語意定義（使用者決定之表，為本規格之權威定義）

| 資料 | 定義與處理 |
|---|---|
| D-a 每 cell 之窗內流量 | 依 (cell, IMSI, LCID, 方向) 分開累計；對固定時間區間 [kT, (k+1)T) 做差分 |
| D-b 每 cell 之窗內平均延遲 | 分別保存延遲總和（ns，整數，精確）與樣本數；差分後相除；輸出足夠精度（整數直接輸出） |
| D-c 窗末 serving cell／連線狀態 | 由指定時點之 RRC 狀態取得；**不得**以最後一筆封包之 cell 代替 |
| D-d 窗內曾服務過之 cell | 由服務狀態事件（換手 start／end、RRC context 建立／釋放）建立區間紀錄；與「有封包經過之 cell」分開 |
| D-e 同時刻之服務關係 | 依明確角色（MCG／SCG、source／target context）與時間重疊判斷；**同窗兩列 ≠ 同時雙掛** |
| D-f 無封包之 UE | 可有控制面歸屬紀錄；流量 = 0、平均延遲 = **缺值**（不得填 0、不得沿用舊值） |

合法換手可使同一 UE 於同窗在兩個 cell 各有一列（D-a），**不得**據此判為攻擊。

## 3. 實作方向（建議，待對照共享與呼叫關係後定）

- 底層保留**累計充分統計量**：per (cell, IMSI, LCID, 方向) 之 count、bytes、Σdelay_ns（uint64）、（可選）Σdelay²。
- **各消費端各自保存上次快照並做差分**；任何消費端不得清空共用計算器（避免 F4 之「先報者重置」使區間依報表順序改變）。
- 消費端清單（須逐一對照）：計算器自身之檔案輸出（`EndEpoch`→`ShowResults`）、DU 報表（F6）、CU-UP 報表（PDCP，F4）、LTE eNB 報表（`lte-enb-net-device.cc:1229` 附近）。
- 舊欄位與舊檔名在 NoAuto 下**逐位不變**（回歸要求，§5 R-6）；新輸出另檔（如 `DlE2RlcStatsPerCell.txt`），整數欄位精確輸出。
- **PDCP 不能直接當已驗證參照**：雖不受 RLC 不重置影響，但換手或多消費端下「第一個報者重置」可能改變統計區間，須另驗證。

## 4. 各規則輸入之語意稽核（逐條確認，不只換欄位名）

| 規則 | 須先回答 | 備註 |
|---|---|---|
| S_i | 改用 D-b（窗內平均）；尺度與 τ_S 重新校準（§6） | 原 0.06 ms 尺度不得沿用 |
| C_i | 要數的是：已註冊 UE／此時有連線之 UE（D-c）／窗內有流量之 UE（D-a）？三者不必相等 | 用時點名單時須處理換手中之 source／target context、斷線、閒置；**不得要求各 cell 原始名單加總恆等於 30**；全域唯一 UE 用聯集 |
| H_i-D1（LTE-only） | 「最後一筆經 LTE」可能是過去殘留狀態；能否支持停留時間與鏈路劣化之解釋須重新核對 | 不只是把「每窗」改字 |
| H_i-D2／D3 | 各自吃時點或區間？ | 待查程式 |
| D4 | 暫定不直接受 RLC 累計影響；但與主檔比對或融合之部分、RRC 名單於換手期間之意義須確認 | |
| 融合／准入／可用資源評估／RQ3 | 依上游更新後重跑 | 第一階段之後 |

## 5. 驗證

### 5.1 反推（既有 D-30 可否重建）之前提 —— 已執行（`check_rlc_decumulation.py`，`data/results/semantics_v0/R1_R4_decumulation_precheck_d30.json`）

| 檢查 | 結果（8 seed × 30 UE × 299 窗對 = 71,760） |
|---|---|
| R-1 樣本對應 | 程式層：F1 同分支更新、同鍵；LCID 只有 3（每 seed 30 個 (IMSI, LCID)）；資料層：nRxPDUs 不減、N=0 時 delay=0 違反 0 |
| R-2 邊界 | 缺窗 0、窗不連續 0、計數下降 0（無重置、無重建計算器、無漏輸出） |
| R-3 第一窗 | 計算器於 t = 0 建立（F2、`m_startTime` = 0），窗 0 之累計即窗 0 之值，起點 0 有程式依據 |
| R-4 精度上限 | 每窗新增 Rx PDU 最少 33；誤差上限中位數 1.8–2.3×10⁻⁴ ms、p99 0.006–0.010 ms、最大 0.013–0.024 ms（後段 270–299 窗最大 0.013–0.024 ms）；反推後同 UE 逐窗變動中位數 0.127–0.216 ms |
| 反推值為負 | 0 |

R-4 之上限是最壞情況，且假設印出值為正確捨入；**能否接受須相對於重新校準後之尺度與門檻判斷**（§8 Q2），目前不作結論。只靠累計平均與計數**不能**恢復窗內跨 cell 之延遲分帳，也不能恢復原始延遲分布。

### 5.2 R-5 經驗驗證（待做；需加裝輸出，不改舊欄位）

同一組封包事件同時產生：(i) 依 D-b 直接按窗計算之平均（整數 Σdelay_ns 與 count 差分，精確）；(ii) 舊格式輸出後反推之平均。seed 4200、NoAuto、短跑（建議 30 s）。比較 |(ii) − (i)| 之分布；接受準則見 §8 Q2。

### 5.3 R-6 回歸

NoAuto 下舊檔（`DlE2RlcStats.txt` 等）與 D-30 seed 4200 同長度前綴**逐位相同**。

### 5.4 R-7 小案例（每 cell 統計實作後）

| 案例 | 檢查 |
|---|---|
| T1 窗中 A→B 換手 | 兩 cell 之封包／位元組分帳正確；同層同方向加總守恆（= 舊 per-UE 差分）；窗末歸屬 = B；不判為同時雙掛 |
| T2 窗內無新封包 | 流量 0、延遲缺值；控制面歸屬仍在 |
| T3 窗邊界發生換手 | 換手前後之區間各歸各窗；窗末歸屬取指定時點之 RRC 狀態 |

人工換手之機制候選為 F9；其執行時點（是否只能在讀檔週期）須先驗證，不行則另寫最小測試 scenario。延遲平均按各 cell 實際樣本計算，不得複製整窗平均。

## 6. 第一階段重跑（S_i 乾淨校準／評估與 E9）

兩種用途不同之評估：

| 評估 | 用途 |
|---|---|
| E-i 修正後輸入 ＋ 原凍結門檻／尺度 | 診斷語意錯置對原系統之影響 |
| E-ii 修正後輸入 ＋ 依預定程序重新校準 | 評估區間量測版本之方法 |

- 重新校準不得在同一批評估資料上反覆挑選；當作新版本，事先記錄校準與測試分工（沿用 LOSO 或另定，§8 Q3）。
- 已看過之 seed 不得宣稱為完全未見之測試集；正文須揭露。
- 之後依序：融合、准入、資源評估 → E19。舊 E19 之負面結果保留為**歷史版本結果**，不得外推為「使用真正區間延遲時 DRL 也沒有優勢」。

## 7. 記憶體（另線，已啟動；`scripts/memdiag_d30h.sh`，輸出 `data/d30h_memdiag/`）

固定建置（同 §1 commit、binary md5 記於各 `meta.txt`），seed 4200、8 秒、一次改一個因素：M0 NoAuto；M1 FixedTtt；M2 FixedTtt＋`--enableTraces=false`；M3 FixedTtt＋E2 NR／LTE 報表關閉。記錄 RSS 與換手數。之後依結果檢查換手後是否重複註冊回呼、保留舊物件或累積未清除之統計容器（例如 F1 之 map 以 (IMSI, LCID) 為鍵不會隨換手成長，須另查 RLC／UeManager／X2）。不提高防護上限、不靠換機或 Docker。統計修正後以同一最小案例重跑比較。

## 8. 待使用者決定（附建議）

| # | 問題 | 建議 |
|---|---|---|
| Q1 | §3 實作方向（底層累計、各消費端差分）是否採用 | 採用；先做 R-5 所需之「加裝整數輸出」，每 cell 拆分在 R-5 後 |
| Q2 | R-4／R-5 之接受準則 | 相對於 E-ii 重新校準後之尺度 s′：重建誤差 p99 ≤ 0.05·s′ 且 max ≤ 0.25·s′，且以重建值與精確值跑 S_i 之乾淨判定逐筆相同比例 ≥ 99.9 %；s′ 以精確值（R-5）計算，不以重建值 |
| Q3 | E-ii 之校準／測試分工 | 沿用 LOSO（7 seed 校準、1 seed 測試，輪替 8 次），預定程序寫入新版 S_i 規格後才執行 |
| Q4 | R-5 短跑長度 | 30 s（涵蓋後段累計樣本多之情形不足時，延長到 60 s；不必 301 s） |
