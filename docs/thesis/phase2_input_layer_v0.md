# 第二階段新輸入層 v0（2026-11-19）：實作、檢查與 C_i 待決事項

> 使用者 11-19：新輸入層先以 GCC 11 之 D-30P（`data/ues30_p_r9_seeds/`，**僅供診斷**）於新機器開發。本檔之數字全部來自診斷資料，**不得引用**；只用於設計決定。

## 1. 參照

| # | 項目 | 出處 | 內容 |
|---|---|---|---|
| R1 | 新輸入定義 | `phase2_percell_spec_v0.md` §4、§9.1 | S_i 用事件發生於該 cell 之 Rx PDU、主結果排除零延遲；C_i (A) RRC 名單／(B) 窗內有流量，兩者皆報；聯集須含 LTE 錨點 |
| R2 | 語意 | `report_semantics_spec_v0.md` §2 | D-a～D-f；D-f 無封包 → 延遲缺值 |
| R3 | 報表名單來源 | 同上 F5 | CU-UP／CU-CP／DU 報表名單 = 報表時點 `GetUeMap()` |
| R4 | r9 輸出格式 | D-30P aux 檔頭 | `_percell`：start end EventCellId IMSI LCID nTx TxB nRx RxB delaySumNs（累計）；`_r9rx`：…nRx nRxZeroDelay nRxNoRlcTag nRxTagUnknown（累計）；`R9_enb_uemap`：timeNs cellId rnti IMSI ueManagerState；`R9_ue_rrc`：timeNs IMSI lteCell lteRnti lteState mmCell mmRnti mmState |
| R5 | K1–K5 | `scripts/r9/check_r9_outputs.py` | mmState 9 = CONNECTED_NORMALLY；O-1 與 CU-CP 名單一致 |

## 2. 實作：`xapps/verification/residuals/percell_source.py`

- 累計檔逐 (cell, IMSI, LCID) 差分；累計值下降即報錯。
- `si_windows`：每 (cell, UE) 區間平均 = ΔdelaySumNs ÷ (ΔnRx − ΔnZero)；分母 0 → 缺值。
- `traffic_lists`（C_i (B)）、`enb_lists`（C_i (A)）、`serving`（D-c）。
- 時點對應：eNB 名單於 (k+1)·1e9 + 0.5 ms（LTE cell 1）與 + 0.8 ms（mmWave cell 2–8）各一次，依 cell 合併為窗 k；UE RRC 於 + 0.8 ms。

## 3. 檢查（8 seed 全部通過）

| 檢查 | 內容 | 結果 |
|---|---|---|
| X1 | 每 (IMSI, LCID, 窗)：Σ_cell `_percell` Δ = `_exact` Δ（5 欄整數） | 0 不符 × 8 seed |
| X2 | 每窗各報表時點中每個 cell 只出現一次 | 0 不符（每窗 2 個時點） |
| X3 | mmState = 9 之 UE，其 serving mmCell 名單含該 UE | 9,000／9,000 × 8 seed |

## 4. 描述性觀察（seed 4200／4203，診斷資料）

| 量 | 4200 | 4203 |
|---|---|---|
| Rx PDU 中延遲 = 0 之比例（全部／mmWave） | 0.132／0.135 | 0.141／0.145 |
| 每窗 LTE cell 1 有流量之 UE 數 = 30 之窗數 | 300／300 | 300／300 |
| (A) mmWave 名單聯集（每窗最小–最大） | 30–30 | 30–30 |
| (B) mmWave 有流量 UE 聯集 | 21–30 | 17–30 |
| 已連線但當窗無 mmWave Rx 之 (UE, 窗) | 1,010 | 1,598 |
| 於非 serving mmWave cell 有流量 | 0 | 0 |
| S_i 每窗可用之 mmWave (UE) 筆數 | 20–30 | 14–28 |

## 5. 待使用者決定：C_i 之守恆式（步 1 開始前）

**問題**：§9.1 定「聯集須含 LTE 錨點」。但在新輸入下，LTE 錨點（cell 1）之 RRC 名單與流量名單**每窗都是全部 30 個 UE**（§4）。若照舊把錨點併入聯集，聯集恆為 30：mmWave 節點**刪除自己的 UE（虛減）永遠偵測不到**，只剩灌水（多出不存在之 IMSI）可偵測。舊資料中錨點只含「最後事件在 LTE」之 UE，故舊版無此問題。

| 選項 | 守恆式 | 效果 |
|---|---|---|
| **Q-C1-a（建議）** | 錨點名單作為**參照集合**：mmWave 名單之聯集須**等於**錨點名單（多 → 灌水；少 → 虛減） | 灌水、虛減皆可偵測；仍以錨點為信任根（與原設計精神相同） |
| Q-C1-b | 照字面：聯集含錨點，判 \|聯集\| = N_known | 只能偵測灌水；虛減成為新盲點，須於正文揭露 |
| Q-C1-c | 只用 mmWave 名單聯集 = N_known，不用錨點 | 失去錨點之信任根角色 |

**Q-C2**：(B) 流量名單之 mmWave 聯集每窗只有 17–30（約一成 UE 當窗無 mmWave 流量）。(B) 無法用「等於錨點」之守恆式（無流量不代表不在）。建議 (B) 只作對照：報告其與 (A) 之差異與灌水偵測，不判虛減。

**Q-C3**：D-30P 無換手，D2 與新 D3 於乾淨資料必為 0（非 vacuous 之基線須用 D-30H）。照規格，不另處理。
