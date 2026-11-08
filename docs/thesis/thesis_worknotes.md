# 論文工作筆記（自 thesis_v7.md 移出，2026-11-08）

> 以下段落原在正文中，屬工作用或過時之修訂紀錄（例：實作進度表含前版 7 UE 數字 m_S*=2、可用性 11.5／33.7／54.8%，與 D-30 之正文不符），移出正文、保留原文。

## 圖表狀態清單（工作用，定稿前刪除）

> 盤點日期：2026-10-13。全部實驗結果圖已於 D-30 上重新產生，檔案位於 `data/results/d30/`（打包檔 `data/results/d30_figs_20261013.tar.gz`）。**正文中所有結果圖之連結皆為【待填】**：前版（7 UE）之 HackMD 圖已不適用，須上傳新圖後填入。

**狀態代號**：⬆️ 待上傳（本地檔案為最新，正文連結為【待填】）｜✏️ 待繪製（概念圖未完成或需修改）｜❓ 需確認

### 一、概念圖與架構圖

| 位置 | 圖 | 狀態 | 待辦 |
|---|---|---|---|
| 第一章（第 57 行） | 論文總系統架構圖（HackMD jpg） | ❓ | 核對是否已反映四個 xApp（Detection／Trust Assessment／Policy Enforcement／Available-resource evaluation）與四狀態 |
| 4.1 | System Architecture（HackMD png，10-05 版） | ❓ | 同上 |
| 第一章（第 53 行） | `01_architecture_sequence.drawio` | ✏️ | 檔案不在 repo；描述寫「兩階段驗證 → SMO 告警」，與 4.4.0（四 xApp、rejected → exclude + execution record）不一致，需改圖並修正第 53 行 |
| 第一章（第 54 行） | `02_attack_flow.drawio` | ⬆️ | 已於 10-06 依 4.4.0／4.5 更新（repo：`docs/thesis/02_attack_flow.drawio`）；需於 draw.io 匯出 png 後上傳，並決定是否嵌入正文 |
| 4.9.2 | C-ZT 四 xApp 架構圖 | ⬆️ | 採簡報 v0.6 第 27 頁之圖；上傳後填入連結 |

### 二、實驗結果圖

| 圖號 | 檔名（`data/results/d30/`） | 章節 | 產生日期 | 狀態 |
|---|---|---|---|---|
| Fig 4-1 ～ 4-4 | `fig_Ci_1_trajectories_unified`、`fig_Ci_2_boolean_unified`、`fig_Ci_3_persistence_unified`、`fig_Ci_4_attack_surface_unified` | 4.6 | 10-13 | ⬆️ |
| Fig 4-5 | `fig_Si_reference_ablation_rt` | 4.7.4 | 10-13 | ⬆️ |
| Fig 4-6 | `fig_E9_operating_regime_rt` | 4.7.5 | 10-13 | ⬆️ |
| Fig 4-6b | `fig_E9b_supervised_baseline_rt` | 4.7.5.1 | 10-13 | ⬆️ |
| Fig 4-6c | `fig_E9c_common_mode_rt` | 4.7.5.2 | 10-13 | ⬆️ |
| Fig 4-7 | `fig_lstm_drift_evasion_rt` | 4.7.6 | 10-13 | ⬆️ |
| Fig 4-7b | `fig_E13_tauS_sensitivity_rt` | 4.7.7 | 10-13 | ⬆️ |
| Fig 4-7c ～ 4-7e | `fig_slow_Q1_frontier_rt`、`fig_slow_Q2_bias_rt`、`fig_slow_Q4_hugging_rt` | 4.7.8 | 10-13 | ⬆️ |
| Fig 4-8 | `fig_Hi_D1_edge_vs_resident` | 4.8.6 | 10-13 | ⬆️ |
| Fig 4-9 ～ 4-12 | `fig_Hi_H1_dwell_dist`、`fig_Hi_H2_edge_ue`、`fig_Hi_H3_geom_reject`、`fig_Hi_H4_teleport` | 4.8 | 10-13 | ⬆️ |
| Fig 4-13 | `fig_Hi_D1_grading` | 4.8.5 | 10-13 | ⬆️ |
| Fig 4-13b | `fig_E16_D1_severity` | 4.8.6 | 10-13 | ⬆️ |
| Fig 4-14 | `fig_xapp_runtime_bound_all_uebound_strict` | 4.9.5 | 10-13（閒置機器重測） | ⬆️ |
| Fig 4-14b | `fig_E14_D1_sensitivity` | 4.9.6.6 | 10-13 | ⬆️ |
| Fig 4-15 | `fig_adversarial_mstar` | 4.10.3 | 10-13 | ⬆️ |
| Fig 4-16 | `fig_RQ3_decision_replay` | 4.12.4 | 10-13 | ⬆️ |
| Fig 4-16b | `fig_RQ3_prb_tradeoff` | 4.12.4 | 10-13 | ⬆️ |

### 三、已產生但正文未引用之圖

| 檔名 | 說明 |
|---|---|
| `fig_E10_D1_policy_tradeoff` | E10 政策消融之 trade-off，與 4.9.6.5 之數字一致；可考慮納入 |
| `fig_Hi_D1_roc` | D1 門檻之 ROC（4.8.6 以文字引用其數值） |
| `fig_Si_vs_lstm_delay`、`fig_Si_reference_ablation`、`fig_E9_operating_regime`、`fig_E13_tauS_sensitivity`、`fig_slow_Q*`（無 `_rt`）、`fig_xapp_runtime_bound_single_uebound_strict` | 以窗索引為單位之舊實作或輔助量測之輸出，僅供回歸檢查 |

**彙總**：結果圖 26 張皆已於 D-30 產生、皆待上傳；概念圖之狀態見上表。

## 附錄
## 配合簡報須修改或新增之實驗

**A. 既有腳本修改後重跑**

| 代號 | 腳本 | 要改什麼 | 影響之章節 |
|---|---|---|---|
| A1 | `zt_kpm_xapp.py` | ✓ 已完成（2026-10-05）：uebound 為預設；新增 P3（動作、admitted view、execution record）；無節點窗記為 `n/a`；LTE 錨點記為 `out_of_scope`；相容模式重現 742／2,335／83／0 與 1,813／575／766／6 並逐筆比對。**P1–P3 之 runtime 待重測** | 4.9.5、4.9.6.3、4.9.6.5 |
| A2 | `run_RQ3_decision_replay.py` | ✓ 已完成：主結果為 uebound；註記與准入取自 xApp；輸出 eligibility mask 與 $\rho$；新增 `C_restrict_annot`；既有 270 個指標值逐位不變 | 4.12 |
| A3 | `run_fusion_replay.py` | ✓ 已完成：改用 xApp 之判定、融合與 P3；輸出動作與准入；D1 情境帶歸屬節點；新增 `n/a` 窗；8 項檢查通過 | 4.11 |
| A4 | `run_E9_operating_regime.py` | ✓ 已完成（2026-10-05）：未修改；內建檢查重現 4.7.4；逐列輸出已填入 4.7.5 | 4.7.5 |

**B. 新增實驗**

| 代號 | 目的（對應簡報） | 設計要點 | 影響之章節 |
|---|---|---|---|
| B1（E11） | RQ2「能否回到 trusted」 | 對各攻擊類別注入有限長度之攻擊後停止；量測離開 trusted 之延遲、到達 rejected 之延遲、攻擊結束後回到 trusted 之窗數；輸出「轉移 × 觸發規則」矩陣 | 4.4.0（四） |
| B2（E11b） | RQ2「持續性政策對重複短違反之效果」 | 重複之單窗脈衝（間隔 g 窗）× $L_C \in \{1,2,3\}$；量測 rejected 比例。注意：乾淨資料 600 窗無任何違反，故 $L_C$ 之「吸收瞬態」效益於現有資料無法量測，只能量攻擊側 | 4.6.7、4.4.0（四） |
| B3（E12） | 簡報 p.39「low-trust 僅於佐證或**持續**時升級」 | 現行規則中 S_i 持續違反不升級。候選規則 `R2_SI_PERSIST`（連續 $L_S$ 個 full-consensus 窗違反 → rejected）；掃描 $L_S$，量測乾淨誤拒率（注意 4.7.7 之啟動暫態）與到達 rejected 之延遲；其後以 `C_notrej` 重跑 4.12 | 4.4.0（二）（四）、4.12.5 |
| B4 | C3「eligible PRB capacity」之 PHY 版 | 已由 D-30 之原生 PRB（`RRU.PrbUsedDl`）取代：$\rho_{\text{PRB}}$ 為 4.12 之主指標，並以 `RxPacketTrace` 交叉驗證 | 4.12.1 |

**C. 不做實驗、僅於正文標示**：execution-status 回饋（Policy Enforcement → Detection）列為提出之介面，未實作、未評估（4.9.2）。

**待填與待核對**（2026-10-13 更新）：第四章之實驗數字已全部以 D-30 之腳本輸出填入；正文中餘留之【待填】皆為圖片上傳後之連結與概念圖。

═══════════════════════════════════════════════════════════════
---

## 附錄：目前實作進度

| 實驗 / 主題 | 修改重點 |
|---|---|
| 實驗設定（Configuration） | config 2→1，補充 sub-6 說明 |
| 符號與決策規則 | 刪除 τ_T，補充 L_C=2 與 D_i 狀態集 |
| H_i-D2 基線 | seed 由 10 改為 4，改寫 vacuous baseline |
| H_i-D1（p_emp） | p_emp 降級為解釋性佐證 |
| Fusion Replay | H_i-D1 標註為情境設定值（stipulated） |
| S_i 串謀分析 | 更新 m-sweep 實測結果、機制說明與 m_S*=2 |
| S_i 可用性 | 改為 unavailable / weak / full 三層可用性（11.5% / 33.7% / 54.8%） |
| LSTM 比較 | 改為「滑動視窗吸收」機制，非 adaptive |
| 吞吐量分析 | 註明 CV≈0.62 為差分後統計 |
| Resident / Edge 基線 | 補充 per-UE-index 基線限制 |
| Resident / Edge 分群 | 補充 edge_split=0.55 分群定義 |
