# RQ3 資源取捨改用原生 PRB — 規格草稿（v0，2026-10-07，待使用者定案）

> 狀態：**草稿**。標【待決】者須使用者決定後方定案為 v1；定案前不得以 D-30 資料跑出結果再回頭調整。

## 1. 動機

- 原 RQ3（4.12）之資源量為 ρ（准入節點之容量參考 K_j 佔比；各 cell 同為 20 MHz，故 ρ 等於准入註記之佔比），B4 以 RxPacketTrace 之排程符號量為補充。
- Reviewer 可能要求「模擬器原生之 PRB」。D-30 以 `--e2nrEnabled=true` 收集，cell 2–8 輸出 `du-cell-*.txt`，含 E2SM-KPM 之 `RRU.PrbUsedDl`。
- 本規格定義：RQ3 之資源量改以原生 PRB 計算，並保留可回推之對照。

## 2. 原生 PRB 之性質（已查證，見 `data/ues30_seeds/calibration_20261006/README.md`、`prb_reader.py`）

| 項目 | 事實 | 依據 |
|---|---|---|
| 計算式 | `RRU.PrbUsedDl.UEID` = 排程 OFDM 符號數 ÷（slot 數 × 14）× 139 | ns-3 `mmwave-enb-net-device.cc` 第 1193–1216 行 |
| MAC 型態 | 分時排程（TDMA），每次配置佔滿整個頻寬；無頻域 PRB 配置 | 同上註解；`SetBandwidth` 註解 |
| 139 | 原始碼寫死，= ceil(100 MHz ÷ 720 kHz)，即 configuration 2 之載波 | `mmwave-phy-mac-common.cc` |
| configuration 1 實際 RB 數 | 28 = ceil(20 MHz ÷ 720 kHz)（numerology 2，RB 寬 720 kHz，未扣保護頻帶） | `SetNrNumerology`、`SetBandwidth` |
| cell 層級 `RRU.PrbUsedDl` | 以 uint32 逐 UE 累加，每次截斷小數，系統性偏低 0.75–4.49 | 原始碼；校準實測 |
| 交叉驗證 | Σ_UE `RRU.PrbUsedDl.UEID` 與 RxPacketTrace 符號換算最大差 0.089 | 校準 28 筆 |

**推論**：原生 PRB 用量 = 符號占用率 × 139。占用率（0–1）與常數無關；絕對 PRB 數以 139 為尺度，須換算為 28 方符合 configuration 1。

## 3. 定義

令 A(t) 為第 t 秒有上報之 mmWave 節點，m_j(t) ∈ {0, 1} 為 Policy Enforcement 之准入遮罩（不變，取自 xApp）。

| 代號 | 定義 | 解讀 |
|---|---|---|
| **U_j(t)** | Σ_UE `RRU.PrbUsedDl.UEID`（cell j、第 t 秒）÷ 139 | cell j 之 PRB 時間占用率（原生 KPM） |
| **ρ_cap**（沿用） | Σ m_j K_j ／ Σ_{j∈A} K_j，K_j = 28 RB | 准入節點之容量佔比；數值與原 ρ 相同（K_j 相同） |
| **ρ_PRB**（新主指標） | Σ_t Σ_j m_j(t) U_j(t) ／ Σ_t Σ_{j∈A(t)} U_j(t) | 已使用之 PRB 中，其 KPM 仍被准入決策之比例 |
| **V_PRB** = 1 − ρ_PRB | | **PRB 能見度損失**：其 KPM 被排除、決策時看不到之 PRB 負載比例；**不是容量損失**（被排除之節點仍在排程） |
| 決策品質（沿用） | regret、wrong_rate、lured_rate、availability | 不變 |

**資源取捨曲線**：對每個准入政策（C_none、C_strict、C_restrict_annot、C_notrej）與攻擊強度，畫「保護效果（lured_rate、regret）」對「V_PRB」。此為 RQ3 之「以多少 PRB 能見度換取多少決策保護」。

**乾淨資料上之 V_PRB** 即驗證層之可用性成本（對應原 1 − ρ）。

## 4. 不變之處

- 准入遮罩、註記政策（uebound 主結果；window 對照）、代理決策（以延遲選 cell）、分母（注入區間、真值 ≥ 2 候選之窗）。
- 原 ρ 之數值以 ρ_cap 保留，供與前版對照。

## 5. 界定（正文必寫）

1. **開迴路重放**：U_j(t) 取自乾淨模擬；攻擊誘導之流量轉移**不會**改變 PRB（未建模負載回饋）。故 ρ_PRB 描述「決策時可見之 PRB 負載」，不描述攻擊後之實際 PRB 分配。
2. **PRB 未被驗證**：`RRU.PrbUsedDl` 本身亦可被受攻陷之 O-DU 竄改。本規格以**乾淨**之 PRB 為權重，不以上報值為權重；攻擊者竄改 PRB 之情境屬 P_i（路線 B）範圍，此處不評估。
3. 139 之常數問題：主表報占用率（%）或 ρ_PRB（比值，與常數無關）；如報絕對 PRB 數，同時列 139 尺度與 28 尺度。

## 6. 內建檢查

1. 每個 seed：`prb_reader.cross_check` 通過（Σ_UE 與符號換算差 ≤ 0.5 PRB）。
2. 僅使用 0–299 窗（`datasets` d30 之 `max_window`）。
3. U_j ≡ 1 時，ρ_PRB 須逐位重現 ρ_cap（同 B4 之檢查 2）。
4. 以符號換算之 U_j 重算 ρ_PRB，與原生 PRB 版本之差 ≤ 1e-3（兩種來源一致）。
5. 每個 (j, t) ∈ A(t) 皆須有 PRB 報表；缺者計數並列出，不得補值。

## 7. 【待決】請使用者決定

| # | 問題 | 選項 | 草稿建議 |
|---|---|---|---|
| D1 | 主指標 | (a) ρ_PRB 為主、ρ_cap 為輔；(b) 兩者並列 | (a)：回應「為何不是原生 PRB」 |
| D2 | 下行之外是否納入上行 PRB（`ulPrbUsage`） | (a) 僅 DL；(b) DL + UL | (a)：代理決策為下行延遲；UL 欄位未經交叉驗證 |
| D3 | 是否新增「以 PRB 占用率為準則」之第二種代理決策（選占用率最低之 cell） | (a) 不新增；(b) 新增，但 PRB 未經驗證，須明示驗證層不保護此決策 | (a)：避免宣稱驗證層保護未驗證之量；若要做，屬 P_i 整合後 |
| D4 | 絕對 PRB 數之尺度 | (a) 只報占用率；(b) 占用率 + 28 尺度；(c) 占用率 + 139 + 28 | (b) |
| D5 | B4（排程符號量）之去留 | (a) 由 ρ_PRB 取代並刪除；(b) 移至附錄作交叉驗證 | (b) |

## 8. 實作（定案後）

- 讀取：`prb_reader.load_du_prb(aux_dir, max_window=300)`。
- 修改：`run_RQ3_decision_replay.py`（新增 ρ_PRB、V_PRB、取捨曲線；保留 ρ_cap）、`run_B4_used_resources.py`（依 D5）。
- 回歸：`ZT_DATASET=dsh` 時（無 PRB 報表）RQ3 須逐位重現既有輸出，ρ_PRB 標 n/a。
