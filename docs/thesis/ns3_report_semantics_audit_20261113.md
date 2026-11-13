# ns-3 報表輸出語意稽核（2026-11-13；起因：D-30H 診斷 §7.5(b)）

> 本檔只記錄原始碼與資料之事實及一次探索性檢查；**未修改任何程式、未重算任何結果**。是否影響第四章與 E19 之主結果，待使用者決定。

## 1. 原始碼事實（ns-3：`~/ns-3-mmwave-oran/src`）

| # | 位置 | 事實 |
|---|---|---|
| F1 | `lte/helper/mmwave-bearer-stats-calculator.cc:212–218, 297–312` | 統計鍵 = (IMSI, LCID)；每筆 Tx／Rx PDU 都以 `m_dlCellId[p] = cellId` 覆寫 cell，計數與 delay（`MinMaxAvgTotalCalculator`）跨 cell 合併累計 |
| F2 | 同檔 `EndEpoch()`（約 586–597 行） | `m_protocolType` 以 "E2" 開頭時**不呼叫** `ResetResults()`，註解：「E2 traces 之重置由 enb net devices 處理」 |
| F3 | `mmwave/helper/mmwave-helper.cc:3218` | `DlE2RlcStats.txt` 之計算器 protocol type = "E2RLC"（LTE 為 "E2RLCLTE"） |
| F4 | `grep ResetResultsForImsiLcid`（全 src） | 只有 `mmwave-enb-net-device.cc:831` 與 `lte-enb-net-device.cc:1229` 呼叫，**皆為 PDCP 計算器**；**E2 RLC 計算器從未被重置** |
| F5 | `mmwave/model/mmwave-enb-net-device.cc:946, 1132`（CU-CP、DU 報表）、`:699`（CU-UP） | 各 cell 之 E2 報表以報表時點 `m_rrc->GetUeMap()` 決定 UE 名單（時點快照）；數值自共用計算器依 IMSI 取 |
| F6 | `mmwave-enb-net-device.cc:811` | DU 報表之 RLC 延遲取自同一個未重置之 E2 RLC 計算器 |

## 2. 資料驗證（D-30 seed 4200，`data/ues30_seeds/analysis/ues30_t300_seed4200.txt`）

- 8,970 組相鄰 (UE, 窗)：TxBytes 下降 **0** 次（IMSI 1：窗 0／50／150／299 = 0.31／21.8／70.1／167.6 MB；nTxPDUs 449 → 288,387）⇒ **計數為自 t = 0 起之累計值**。
- delay 欄（`zt_kpm_xapp.py:198` 讀 `p[10]` 作為該窗之延遲）為**自 t = 0 起之累計平均**：IMSI 1 窗 290–299 為 0.746 → 0.744 ms；逐窗變動中位數，前 30 窗 0.0078 ms，後 30 窗 0.0007 ms。
- 因從未重置，每個 UE 自第一筆 PDU 起**每窗都有一列**，cell 欄為「至今最後一筆 PDU 所在之 cell」（含 cell 1 = 最後一筆經 LTE）。

## 3. 探索性檢查（事後、僅 seed 4200；不得當結果引用）

以累計平均與累計 nRxPDUs 反推每窗平均：d_w = (D_w·N_w − D_{w−1}·N_{w−1}) / (N_w − N_{w−1})。
- 8,970 組皆有新 Rx PDU；反推值負數 0。
- 中位數：累計 0.818 ms、反推 0.874 ms。
- 同 UE 逐窗變動中位數：累計 0.0008 ms、反推 0.134 ms（約 170 倍）。
- 與每窗重置之 PDCP 延遲（`DlE2PdcpStats`）之 R²：累計 0.004、反推 0.014 ⇒ **E23 Ref-P 之低 R² 不能以累計解釋**。
- 印出精度（約 6 位有效數字）對反推之誤差未評估。

## 4. 各輸出之語意（依 F1–F6）

| 輸出 | 實際語意 | 本研究之用法 |
|---|---|---|
| `DlE2RlcStats`（主檔）之計數、delay | (IMSI, LCID) 自 t = 0 累計；cell = 最後一筆 PDU 所在 cell | 當作「每窗、每 cell」之量測（S_i、H_i、C_i 成員、E19 環境） |
| `DlE2PdcpStats`、CU-UP 報表 | 每窗（由第一個報該 UE 之 cell 重置） | E23 Ref-P |
| CU-CP／DU 報表之 UE 名單 | 報表時點之 RRC 快照 | E25／E26 之 D4 |
| DU 報表之 RLC 延遲 | 同主檔，累計平均 | 未使用 |

## 5. 影響範圍（待逐條確認，尚未評估）

- **S_i**：τ_S、凍結尺度 0.0565–0.0619 ms、乾淨誤報、E9 之階躍／漂移結論、E13、E21、E23、E24-pre 皆建立在累計平均上。
- **H_i**：「LTE-only」= 最後一筆 PDU 經 LTE（與 v11 之「報表層級歸屬」措辭一致，但「每窗」須改寫）。
- **C_i**：每窗名單 = 累計至今出現過之 UE；N_total = 30 與「0 反例」可能部分由構造造成。
- **E19／E20／E26 與學習型攻擊者**：環境之觀測與攻擊注入作用在累計平均上。
- **D4（E25）**：用 CU-CP 時點快照，不受累計影響；與主檔之比對語意須重寫。
- D-30H 之 cell 歸屬問題（D30H 規格 §7.5(b)）為 F1 之直接結果。
