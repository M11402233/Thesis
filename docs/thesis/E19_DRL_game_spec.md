# 規格 E19：DRL 偵測端 × 學習型攻擊者 × OAuth 授權層（總規格）

> 狀態：**v1（2026-11-07）**：§10 之 Q-a～Q-g 已由使用者確認採建議值（原標【待確認】處，以下以〔已確認〕標示）。§0 之前置條件仍須完成才產生結果。
> 依據：`WUT_feedback_DRL_ZT_plan.md`（含 1.2a 之 P1–P11 決定）、`fusion_severity_order_spec.md`。
> 投稿：合併一篇、IEEE OJCOMS、DRL 為主體（P4、P5）；規則版（git tag `rulebased-v1`）為同篇之基線。

## 0. 前置條件（未完成不得開始 Phase 3）

1. 融合順序修正（severity）通過 C1–C4 並採用（`fusion_severity_order_spec.md` §4）。
2. 打 git tag `rulebased-v1`（含 severity 修正後之規則版）。
3. ~~本規格之【待確認】項目經使用者確認~~（2026-11-07 完成）。

## 1. 資料與切分

| 階段 | 資料 | 切分 |
|---|---|---|
| Stage 1（穩定）／Stage 2（學習型攻擊者） | D-30（`data/ues30_seeds/analysis/`，唯讀），7 gNB、1 個被攻陷（P8） | LOSO：7 seed 訓練、1 seed 測試，輪 8 次 |
| Stage 3（提高變異） | `data/game_stage3/`（S3-TM3、S3-U20、S3-U40，見 `E19_stage3_data_spec.md`） | 訓練於 D-30 → 測試於 Stage 3（分布外）；另報 Stage 3 內 LOSO |

被攻陷節點：每個測試 seed 輪流指定 cell 2–8 之一〔已確認：全輪 7 個；若訓練時間 > 1 週改抽 3 個，須標事後修正〕。

## 2. 環境（Phase 1）

- 檔案：`xapps/verification/adversarial/env_kpm_game.py`（gymnasium API）。
- 環境**直接呼叫**既有函式，不得複製改寫：`zt_kpm_xapp` 之 `verify_ci`／`verify_si`／`verify_hi_d2`／`d1_ue_levels`／`verify_hi_d1_uebound`／`fuse`（severity）；`planB_rt` 之時間軸與共同集合；`run_RQ3_decision_replay` 之代理決策與 regret。
- 時間單位：(節點, 秒)；一個 episode = 一個 seed 之 0–299 窗。
- **一致性檢查（內建，失敗即停）**：
  - G1：無攻擊、規則版 L2（不經 DRL）→ 逐筆重現 `xapp_trust_annotations_bound_all_uebound_strict_severity.jsonl`（15,534 筆）。
  - G2：既有注入（E11 之轉移、RQ3 之 ×0.6／×0.8／漂移）→ 重現 E11 轉移統計與 RQ3 誘導率。
  - G3：決定性：同一 seed、同一 policy 重跑逐位相同。

## 3. DRL 偵測端（Phase 3；P1、P11）

| 元素 | 定義 |
|---|---|
| 決策單位 | (節點 j, 秒 t)；L1 rejected 規則（`R1_AUTHZ`、`R1_CI_VETO`、`R1_D2_VETO`）觸發時不交給 DRL |
| floor | V-escalate（主）：severity 版 `fuse()` 之完整判定。V-replace（對照）：僅 L1（含 `R1_CI_PENDING` → ≥ low-trust）＋ L3 |
| action | {trusted, low-trust, rejected}，以 action mask 限於 severity(a) ≥ severity(floor)；abstain 只由 L3 產生 |
| state | $z_j(t)$、peer 數、歸屬 j 之 D1 $z_d$ 最大值與證據強度、C_i pending 旗標；過去 k 秒之上述值與本 agent 過去 action。k = 5〔已確認〕。**不含** peer 中位數與尺度 s 本身 |
| reward | 竄改且判 rejected：+1；竄改且判 low-trust：+λ；竄改且判 trusted：−α·(該秒 steering 錯誤成本，RQ3 regret 正規化)；未竄改且判 rejected：−β；未竄改且判 low-trust：−μ；未竄改且判 trusted：+μ。λ=0.3、α=1、β=5、μ=0.05〔已確認〕 |
| 演算法 | MaskablePPO（sb3-contrib 2.6.0）〔已確認〕；訓練 seed 0、1、2（≥3），報平均與範圍 |
| 部署 | 凍結（frozen）與線上（online，Phase 5）兩者皆做（P1） |

標籤：(節點, 秒) 之報告是否被竄改；被攻陷節點於注入起點前標為未竄改。

## 4. 學習型攻擊者（Phase 4；P3、P9）

| 元素 | 定義 |
|---|---|
| 控制對象 | 被攻陷 DU 之 cell 上報 delay（第一步）；UE ID 集合為第二步（另訂規格） |
| action | 乘數 $a_t\in[0.5,1.5]$，每秒變化 $|a_t-a_{t-1}|\le\delta$，δ=0.05〔已確認〕 |
| 觀測 O-full | 自身過去上報、**偵測端對自己過去之判定**、上一已評估秒之 peer 中位數（lag1） |
| 觀測 O-outcome | 自身過去上報、steering 結果（是否被選中）、lag1 peer 中位數；**不含判定** |
| 觀測 O-outcome+token | O-outcome ＋ token 續發／撤銷事件（僅 P10 連動版，見 §5） |
| 禁止 | 同秒 peer 中位數（Q4 oracle，僅作對照點） |
| reward | 被 steering 選中且非最佳：+1；判 low-trust：−c_l；判 rejected：−c_rc_l=0.1、c_r=1〔已確認〕 |
| 演算法 | PPO（連續 action）；訓練 seed 0、1、2 |

## 5. OAuth 授權層（Phase 2；P10 = B）

- 模組：`xapps/verification/authz/`；RFC 6749 client credentials 之邏輯層模擬（不實作 HTTP）。
- scope：DU 身分、可上報之 cell ID、量測類型、請求種類。新規則 `R1_AUTHZ`（token 無效／過期／scope 不符 → rejected）。
- **P10 = B（連動，使用者 2026-11-07 決定）**：token scope／續發隨信任狀態變動。條件：
  - 連續 rejected ≥ N 窗才撤銷或縮小 scope，N=3〔已確認〕；
  - 撤銷生效加隨機延遲 U[0, D] 窗，D=5〔已確認〕；
  - 撤銷後重新申請之冷卻 T 窗，T=30〔已確認〕。
- **必報之資訊洩漏量測**：(i) 攻擊者於 O-outcome+token 下對「自身是否被判 rejected」之推斷準確度；(ii) 連動版與不連動版（對照）之攻擊者可維持偏差差值；(iii) token 事件與判定之互資訊估計。
- 測試：越權上報全數被擋；持合法 token 之數值竄改**不會**被 OAuth 擋（證明分工）；額外延遲併入 4.9.5。

## 6. 指標（同 plan §6）

主：TPR、乾淨誤拒率（(節點, 秒)，與 4.9.6.3 同口徑）。另：離開 trusted／到達 rejected 之延遲（E11 方法）、偵測前已灌入偏差（Q2）、攻擊者可維持偏差（(a) 未被 S_i 偵測，可與 Q4 23.6% 比；(b) 未被 rejected）、steering 誘導率／regret／ρ_PRB（RQ3）、E9c 共模下誤報、乾淨 trusted 比例。

## 7. 基線

1 規則版 L2（severity）；2 E12 `R2_SI_PERSIST`（L_S 格點）；3 E14 D1 門檻格點；4 E9b 監督式分類器。每個 DRL 結果與 1–4 並列。

## 8. 成功判準（事先登錄）

- 偵測端：同一乾淨誤拒率下，DRL 之「TPR 對偵測延遲」優於基線 1–3 之前緣；E9c 下誤報不高於規則版。
- V-escalate 之 TPR 依構造不低於基線 1；若 V-replace 比規則寬鬆（乾淨誤拒相同下 TPR 較低），如實報告。
- 做不到即報負面結果，不調整 reward 讓它通過；任何 reward／超參數之事後調整須標「事後修正」並保留原結果。

## 9. 輸出

`data/results/d30/drl/<phase>/`；每個結果檔記錄訓練 seed、超參數、步數、環境版本（git commit）、套件版本（torch 2.5.1+cpu、gymnasium 1.1.1、stable-baselines3 2.6.0、numpy 2.2.6；venv `~/venvs/drl`）。

## 10. 參數彙整（2026-11-07 全部依建議值確認）

| # | 項目 | 建議值 |
|---|---|---|
| Q-a | 被攻陷 cell：全輪 7 個或抽 3 個 | 全輪 7 個（若訓練時間 > 1 週改抽 3 個） |
| Q-b | 歷史長度 k | 5 |
| Q-c | 偵測端 reward λ、α、β、μ | 0.3、1、5、0.05 |
| Q-d | 偵測端演算法 | MaskablePPO |
| Q-e | 攻擊者每秒變化上限 δ | 0.05 |
| Q-f | 攻擊者 reward c_l、c_r | 0.1、1 |
| Q-g | token 撤銷 N、延遲 D、冷卻 T | 3、5、30 |
