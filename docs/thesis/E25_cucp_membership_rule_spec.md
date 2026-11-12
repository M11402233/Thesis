# E25 規格 v1：成員身分之外部參照——CU-CP 成員對帳（H_i-D4，`R1_D4_VETO`）

> 2026-11-13，使用者指示「1 ok 直接做」。本檔先於腳本執行 commit。事後新增之規則（已看過 E21-S0／S1、E22）；主結果凍結，規則預設關閉，只在本實驗以疊加方式評估。

## 1. 參照

| # | 項目 | 出處 | 內容 |
|---|---|---|---|
| R1 | 缺口 | `E22_run.log`；`E21_S1_boff.json` | A2（k-for-k 替換）：D3 偵測 0.000，MF_strict 0.497、MF_restrict 0.989、B-off 0.977；A4（宣稱 peer 之 UE）：MF_strict 0.490／0.465、MF_restrict 0.989；A1（刪除）MF_restrict 0.113／0.102；A3 由 D3 全數偵測 |
| R2 | 注入 | `run_E21_S0_membership.py:73–107` `inject` | A1 刪 k 個自身 UE；A2 以假 ID 9001… 取代 k 個自身 UE；A3 宣稱 anchor-only UE；A4 宣稱出現於其他 mmWave 節點報表之 UE；T0S = [50,100,150,200,250]、L = 10、k ∈ {1, 3} |
| R3 | C_i 只看基數 | `zt_kpm_xapp.py:270–283` | `violated = (len(union) != N_KNOWN)`；故等量替換不違反 |
| R4 | **CU-CP 報表之逐 cell UE 清單** | `data/ues30_seeds/ues30_t300_seed42??_aux/cu-cp-cell-{2..8}.txt.gz` | 表頭第 2 欄 `ueImsiComplete`、第 7 欄 `L3 serving Id(m_cellId)`；seed 4200 之 cell 2：300 份報表、每份 9 列（＝該 cell 之 RRC 連線 UE） |
| R5 | 報表與窗之對應 | `data/ues30_seeds/calibration_20261006/README.md` 第 25 行 | 「timestamp 欄為實際時間（ms），報表依序對應模擬第 k 秒」 |
| R6 | D-30 無 NR 間換手 | `scratch/scenario-three.cc:249–253`；`scripts/collect_ues30.sh`（未設 handoverMode）；各 seed `CellIdStats.txt` | `handoverMode` 預設 `"NoAuto"`；CellIdStats 30 列（僅初始連線）⇒ **D-30 中 UE→cell 之對應全程不變** |
| R7 | KPM 成員與 RRC 連線不同 | E20-5（thesis v11 之 H_i 措辭） | UE 之 mmWave 鏈路劣化時，其 RLC 列改出現於 anchor（CellId 1）；故乾淨時「節點 j 報表之成員 ⊆ CU-CP 之 cell j 清單」，非相等 |
| R8 | 既有同類規則之作法 | `E22_dual_report_rule_spec.md` | L1、rejected、預設關閉、乾淨觸發為 0 才啟用 |

## 2. 假設（新增，須於威脅模型明寫）

CU-CP 之報表（逐 cell 之 RRC 連線 UE 清單）不經被攻陷之 DU 之 KPM 組裝點，視為可信。於 ns-O-RAN 中 `cu-cp-cell-c` 由同一 gNB 物件產生；本研究將 CU-CP 與 DU 視為不同信任域（O-RAN 之 CU／DU 分離）。CU-CP 被攻陷時本規則不成立。

## 3. 規則

令 R_w(c) = 窗 w 中 cell c 之 KPM 報表成員，A_w(j) = CU-CP 於第 w 份報表所列 cell j 之 UE。對 mmWave 節點 j：

- **D4a（外來成員）**：R_w(j) − A_w(j) ≠ ∅。
- **D4b（失蹤成員）**：A_w(j) − (R_w(j) ∪ R_w(anchor)) ≠ ∅（連線於 j 之 UE 既不在 j 之報表、也不在 anchor 之報表）。
- H_i-D4 = violated ⇔ D4a 或 D4b。規則 `R1_D4_VETO`：L1、rejected，歸因於節點 j。
- 實作：**疊加於既有註記之上**（D4 violated ⇒ 該 (節點, 窗) 之判定改為 rejected）。嚴重度序下 rejected 為最嚴重，疊加與寫入 `fuse()` 之判定相同；`zt_kpm_xapp.py` 本體不改（需另增外部參照之輸入介面，列為後續實作）。

## 4. 量測

- 4.1 乾淨：D-30（8 seed）與 S3-TM3（舊機器現有 6 seed，bursty 流量）之 D4a、D4b 觸發次數。**D-30 乾淨觸發 ≠ 0 即停止回報**（不調整規則）。D-SH／D-C 無 E2 NR 報表，不適用。
- 4.2 成員關係攻擊（R2 之全部 episode）：D4 偵測率（分 D4a／D4b）、MF_strict、MF_restrict_annotated、B-off 下之 MF_strict，分「D4」與「D3＋D4」；rejected 之偵測延遲。
- 4.3 副作用：D4 只觸發於竄改之 (j, 窗)；三種延遲攻擊（×0.6、×0.8、漂移 0.01）下觸發 0。

## 5. 檢查（失敗即停）

- E25-0：每個 seed、每窗，CU-CP 清單為 30 個 UE、每個 UE 恰屬一個 cell、每個 cell 300 份報表。
- E25-1：關閉時 15,534 筆逐筆重現註記檔；關閉時各攻擊之 MF_strict 與竄改筆數重現 E21-S1。
- E25-2：D4 觸發只出現在竄改之 (j, 窗)。
- E25-3：延遲攻擊下 D4 觸發 0。

## 6. 事先揭露之限制

1. D-30 無 NR 間換手（R6），A_w 全程不變；換手瞬間 CU-CP 報表與 RLC 窗之時序差可能造成乾淨誤觸，**未評估**（待含換手之資料）。
2. A3 中被宣稱之 anchor-only UE 若本來就連線於 j，D4a 不觸發（預期由 D3 偵測）；故報「D4」與「D3＋D4」兩者。
3. 只有腳本注入；成員關係之適應性攻擊另案（使用者 2026-11-13：本項完成後再寫規格）。
4. 攻擊者若同時能改寫 CU-CP 報表則無效（§2）。
5. 輸出：`data/results/d30_fusion_order/severity/E25/E25_cucp_membership.json`；腳本 `xapps/verification/residuals/run_E25_cucp_membership.py`。
