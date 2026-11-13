# 規格 v1：D-30H（含合法 NR 間換手之資料收集）

> 2026-11-13。使用者決定：收集含換手之資料，換手模式 **FixedTtt**（「使用固定的換手觸發等待時間」）。本規格只規定資料收集；使用該資料之實驗（D2／D3／D4 之乾淨誤觸等）另寫規格。

## 1. 參照

| 項 | 出處 | 內容 |
|---|---|---|
| D-30 無換手 | `scratch/scenario-three.cc:249–253`；`scripts/collect_ues30.sh`；各 seed `CellIdStats.txt` 30 列 | `handoverMode` 預設 `"NoAuto"`，D-30 未設定 ⇒ 僅初始連線 |
| 換手模式 | `src/lte/model/lte-enb-rrc.cc:3279–3295` | `SecondaryCellHandoverMode` ∈ {FixedTtt, DynamicTtt, Threshold, NoAuto}；`FixedTttValue` 預設 **110 ms** |
| 模擬器會產生換手 | 2026-11-13 試跑（7 UE、`DynamicTtt`、seed 4200、暫存目錄） | 39 秒內 `UeHandoverEndStats.txt` 100 筆（乒乓明顯）。FixedTtt 之換手率未知 ⇒ 先 probe |
| split bearer | `src/lte/model/mc-enb-pdcp.cc:275–290`（`m_useMmWaveConnection`） | PDCP 為二選一切換，非同時雙路徑（程式碼判讀，未實測）⇒ 本資料**不含** split bearer |
| 需求來源 | `E25_cucp_membership_rule_spec.md` §6(1)、`E22_dual_report_rule_spec.md`、`chapter6_draft.md` 6.4(2) | D2／D3／D4 於換手下之乾淨誤觸未評估 |

## 2. 參數

與 D-30 完全相同（configuration 1、`--totalUes=30`、`--e2nrEnabled=true`、`--indicationPeriodicity=1.0`、`--heuristicType=-1`、速度 3–10 m/s、`--simTime=301`、trafficModel 預設值），**僅新增 `--handoverMode=FixedTtt`**（`FixedTttValue` 用預設 110 ms，不調整）。seed 4200–4207。

- 輸出：`data/ues30_ho_seeds/D30H_ues30_t300_seed<s>.txt` 與 `_aux/`（另保留 `CellIdStatsHandover.txt`、`Ue／EnbHandover{Start,End}Stats.txt`）。
- 腳本：`scripts/collect_d30h.sh`（由 `collect_stage3.sh` 複製；拒絕寫入 `ues30_seeds`、`game_stage3`、`si_lstm_seeds`、`batchFinal_seeds`）。一律 `setsid nohup`。
- 亂數流與 D-30 相同 seed，但換手改變事件序列 ⇒ **不是** D-30 之配對樣本。

## 3. Probe（先於正式收集；seed 4200、`--simTime=6`，輸出 `data/ues30_ho_seeds/_probe/`）

記錄：耗時／模擬秒、最大 RSS、每窗 N_total、換手筆數與每 UE 分布（乒乓程度）、同窗出現於兩個報表之 UE 筆數。**只記錄，不據以調整 TTT**；若換手率極端（例如多數 UE 每秒換手 ≥ 1 次）則停下回報使用者，不自行改參數。

## 4. 每 seed 之內建檢查（同 Stage 3）

0–299 窗不缺窗；IMSI 集合 = {1..30}；每窗 N_total 之分布（**只記錄**——換手瞬間可能不恆為 30，C_i 於本資料之用法另訂）；`prb_reader.py <aux>`。

## 5. 排程

舊機器 2 實例平行（31 GB、4 核心；第 3 個實例須問使用者）。新機器於 Stage 3 收齊後可分擔（G-S3 已驗證兩機輸出逐位相同）。

## 6. Probe 結果（2026-11-12 18:24–19:11 UTC；seed 4200、`--simTime=6`；`data/ues30_ho_seeds/_probe/`；與 FlexRIC 編譯及另一個 7 UE 測試同時執行，速度偏慢）

| 項 | 值 |
|---|---|
| 耗時 | 47 分鐘／6 模擬秒（約 470 s/s；D-30 正式收集為 146,624 s／301 s ≈ 487 s/s，2 實例平行）⇒ 推估每 seed 約 40 小時 |
| 最大 RSS | 2,085 MB（5.98 s 時；早期斜率約 350 MB／模擬秒，與 D-30 早期（1.7 s 時 550 MB）同量級；D-30 於 301 s 為 5,543 MB） |
| 內建檢查 | 5 窗、不缺窗、IMSI 30 個、每窗 N_total 皆 = 30 ⇒ 通過 |
| 換手 | `UeHandoverEndStats.txt` 90 筆／6 秒；發生於 20 個 UE，每 UE 1–8 次（≥ 6 次者 6 個 UE）；10 個 UE 無換手。平均 0.5 次／UE／秒 |
| 同窗雙掛 | 5 窗中「出現於 ≥ 2 個 mmWave 報表之 UE」0、「同時出現於 anchor 與 mmWave 之 UE」0 |

判斷：未達 §3 之停止條件（多數 UE 每秒 ≥ 1 次）；換手偏頻繁（乒乓），如實記錄，TTT 不調整。依使用者之決定啟動正式收集（舊機器 2 實例）。

### 6.1 使用者審查（2026-11-13）

「只有 6／30 個 UE 超過每秒一次，所以繼續」之停止條件太寬鬆：最多是粗略警報，不能當資料合理性之驗收標準；少數邊緣 UE 持續往返即可能嚴重影響 D1、D2 與乾淨誤報率。§3 之停止條件因此**降為警報**，驗收改依 §7 之診斷。TTT 110 ms 暫不改。

## 7. 診斷（2026-11-13；`scripts/diag_d30h_handover.py`，輸出 `data/results/d30h_diag/diag_seed420{0,1}.json`）

**資料來源**：正式收集之 seed 4200／4201 均於模擬約 46 秒被記憶體防護中止（RSS 15.0／15.3 GB，MemAvailable 580 MB；見 7.5），其 `_work_*` 目錄保留 0–46 秒之完整輸出。同 seed、同設定，即使用者要求之「延長到 30–60 秒」診斷，不另開實例。

### 7.1 計數來源核對（一次換手 = 一筆 UE 端 HandoverEndOk，來源取自同 UE 最近一筆 start）

| 項 | 4200 | 4201 |
|---|---|---|
| UE start／UE end／eNB start／eNB end | 749／749／749／749 | 652／652／652／652 |
| 配對成功（start→end，目標相同） | 749 | 652 |
| 有 start 無 end（未完成）／UeFailures | 0／0 | 0／0 |
| MmWaveSwitchStats 行數 → 去重後 cell 變更 | 13,181 → 749 | 10,910 → 652 |
| SwitchToLte（LTE fallback／回切） | 0 | 0 |
| 涉及 cell 1（LTE）之換手 | 0 | 0 |
| 初次接入（不計入換手） | 30 | 30 |

- 四個檔案記錄同一事件（UE 端與 eNB 端各一筆 start、一筆 end），probe 之 90 次只取 `UeHandoverEndStats`，**無重複計入**。
- `MmWaveSwitchStats`／`CellIdStats` 每次換手寫 2–4 行（start 與 end 各觸發，含逐 DRB 重寫），**不可直接計數**；去重後與換手數逐筆相同。
- 全部換手皆為 mmWave↔mmWave 之 secondary-cell 換手（ns-3 經 X2 `SendMcHandoverRequest`）；無 LTE fallback、無失敗。
- 觸發規則（`lte-enb-rrc.cc`）：目標 SINR − 目前 SINR > `HoSinrDifference`（預設 3 dB）且維持 `FixedTttValue`（110 ms）。

### 7.2 分段換手率（每 5 秒，次／UE／秒）

| 段 (s) | 0–5 | 5–10 | 10–15 | 15–20 | 20–25 | 25–30 | 30–35 | 35–40 | 40–45 |
|---|---|---|---|---|---|---|---|---|---|
| 4200 | 0.48 | 0.54 | 0.62 | 0.46 | 0.65 | 0.57 | 0.51 | 0.48 | 0.56 |
| 4201（次數） | 52 | 62 | 72 | 58 | 75 | 71 | 69 | 93 | 90 |

⇒ **不集中於開頭**，全程穩定在約 0.5 次／UE／秒；不是暖機暫態，不能靠刪前段處理。

### 7.3 停留時間、乒乓、每 UE

| 項 | 4200 | 4201 |
|---|---|---|
| 停留時間中位數（s） | 0.77 | 0.81 |
| p10／p25／p75／p90（s） | 0.21／0.38／1.70／3.48 | 0.20／0.38／1.80／3.77 |
| 停留 < 0.5 s／< 1 s | 35.5 %／61.0 % | 36.0 %／57.1 % |
| 1 秒內 A→B→A（占全部換手） | 255／749 = **34.0 %** | 223／652 = **34.2 %** |
| 無換手之 UE | 2 | 1 |
| ≥ 0.5 次／秒之 UE | 17 | 17 |
| ≥ 1 次／秒之 UE | 1 | 1 |
| 前 5 名 UE 占換手比例 | 28.6 % | 30.2 % |

- probe（6 秒）之「6 個 UE ≥ 1 次／秒」為短樣本現象；46 秒下只剩 1 個，但 **17／30 個 UE ≥ 0.5 次／秒**，乒乓是**普遍**現象，不是少數邊緣 UE。

### 7.4 SINR 與位置（換手開始時，各 cell 於 `MmWaveSinrTime` 最近一筆）

- 全部換手：目標 − 來源 SINR 中位數 6.4 dB（4200）／6.0 dB（4201）；p10 1.6／1.4 dB；< 3 dB 者 17.6 %／21.0 %（快照時點在 TTT 之後，SINR 已再變動）。
- 4200 最頻繁 5 個 UE（IMSI 12／28／27／18／29，各 56／41／40／40／37 次）：來源 SINR 中位數 −9.2 至 −5.6 dB、目標 −0.8 至 +1.1 dB；主要往返對為 2↔8、2↔5／2↔6、3↔4、2↔5、2↔3。
- 初始位置（`ues.txt`，僅 t = 0 一次）：五者距最近兩個 mmWave cell 之距離差 0–90 m（例如 IMSI 12 距 cell 2 485 m、cell 8 527 m），即位於 cell 邊界附近；46 秒內至多移動約 460 m，**位置僅供參考**（scenario 未輸出軌跡）。
- 解讀（未驗證之推測）：configuration 1（3.5 GHz、isd 1000 m）下 UE 多在 −10 至 +1 dB 之低 SINR 區，SINR 快速起伏使 3 dB 遲滯＋110 ms TTT 不足以抑制往返。

### 7.5 兩個新發現（影響 D-30H 是否可用）

**(a) 記憶體：D-30H 照原規格無法跑完。** RSS 約以 330 MB／模擬秒線性成長（4200：10 s 3.7 GB、20 s 6.1 GB、30 s 9.0 GB、40 s 13.5 GB；`mem_trace.tsv`），D-30（無換手）於 301 s 才 5.5 GB。外推至 301 s 約需 100 GB；兩台機器皆 31 GB。成長原因未查（推測與每次換手建立之 RLC／UeManager 物件有關，未驗證）。seed 4202／4203 已於 02:38 UTC 自動接續，預期同樣於約 46 秒（約 10:00 UTC）中止。

**(b) 報表之 cell 歸屬：窗內換手之 UE 只出現在一個 cell。** 46 個窗、1,380 個 (UE, 窗) 中「同窗出現在 ≥ 2 個 mmWave 報表」為 0，但同期間 507／1,350（37.6 %，窗 1–45）之 (UE, 窗) 於窗內換過 cell。原因（`lte/helper/mmwave-bearer-stats-calculator.cc` 第 215、300 行）：統計以 (IMSI, LCID) 為鍵累計，`m_dlCellId[p] = cellId` 每筆 PDU 覆寫，故整窗之位元組全歸到「該窗最後一筆 PDU 所在之 cell」（與窗末服務 cell 相符者 985／1,350 = 73 %）。⇒ probe 之「同窗雙掛 0」是**報表機制造成，不是證據**；D-30H 之 RLC 報表對換手 UE 不具逐 cell 意義（真實 O-DU 只會報自己 cell 之流量），直接用於 C_i／D2／D4 會得出錯誤結論。（D-30 無換手，不受影響。）

### 7.6 待使用者決定

1. 是否停止 D-30H 之佇列（4202／4203 跑到約 46 秒後，4204–4207 會重複同樣的中止，約 7.5 小時／對）。CLAUDE.md 規定不得終止，須使用者同意。
2. 是否修改 ns-3：統計鍵改為 (cellId, IMSI, LCID)，使窗內換手之 UE 在兩個 cell 各有一列（NoAuto 下輸出應不變，須以 D-30 seed 逐位比對驗證）；記憶體成長另查。
3. 乒乓 34 % 是否可接受，或調整 `HoSinrDifference`／TTT（使用者已表示不急著改 110 ms）。1 秒內返回之乒乓定義與 3GPP 之對照【待查證】。
