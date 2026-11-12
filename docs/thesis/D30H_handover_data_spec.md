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
