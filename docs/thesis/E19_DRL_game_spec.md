# 規格 E19：DRL 偵測端 × 學習型攻擊者 × OAuth 授權層（總規格）

> 狀態：**v2 定案（2026-11-08；R-a～R-f 由使用者依建議值確認）**：訓練流程由「分階段單次訓練」改為 **PSRO**（依使用者之簡報 v1.5 第 42 頁）；新增之 §3a 與 §10b 之 R-a～R-f 已於 2026-11-08 依建議值確認。v1（2026-11-07）之 Q-a～Q-g 已確認，於 v2 不變（以〔已確認〕標示）。v1 全文見 git 歷史（commit 34a6c26 之前）。
> 依據：`WUT_feedback_DRL_ZT_plan.md`（含 1.2a 之 P1–P11 決定）、`fusion_severity_order_spec.md`。
> 投稿：合併一篇、IEEE OJCOMS、DRL 為主體（P4、P5）；規則版（git tag `rulebased-v1`）為同篇之基線。

## 0. 前置條件（未完成不得開始 Phase 3）

1. ~~融合順序修正（severity）通過 C1–C4 並採用~~（2026-11-08 完成，`fusion_severity_order_spec.md` §7）。
2. ~~打 git tag `rulebased-v1`~~（2026-11-08 完成，本機）。
4. ~~v2 之【待確認】項目（§10b）經使用者確認~~（2026-11-08 完成，全部依建議值）。
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

## 2a. 環境之實作定義（2026-11-08，先於任何訓練；規格未明定處）

實作：`xapps/verification/adversarial/game_core.py`（核心）、`env_kpm_game.py`（`DetectorEnv`、`AttackerEnv`）、`check_env.py`（G1–G3）。

1. **成員關係證據預先計算**：攻擊者第一步只改 delay，不改 UE 之出現與歸屬，故 C_i、H_i-D2、H_i-D1 取自乾淨資料之 `run_xapp` 輸出；每步只以 `verify_si` 重算 S_i，再以 `fuse_detail`（severity）求下限。此不變性由 G2a 以完整 `run_xapp` 於注入後資料逐筆驗證。
2. **竄改標籤**：該 (節點, 秒) 之任一 UE 上報值與真值不同（漂移於 t0 當秒乘數為 1，不算竄改）。
3. **注入起點**：t0 = 窗數 // 2（與 RQ3 相同）；學習型攻擊者自 t0 起行動，$a_{t_0-1}=1$；被攻陷 cell 無上報之秒不構成攻擊者之一步，乘數保持。
4. **偵測端之一步**：僅限下限為 trusted 或 low-trust 之 (節點, 秒)；下限為 rejected（含 `R2_SI_D1_BOUND`）或 abstain 者由規則決定（呼應 §3 決策單位）。同窗節點依 cell 編號順序。
5. **偵測端 reward 之 steering 成本**（竄改且判 trusted）：其他節點取其規則下限，依 C_strict（僅 trusted 准入）以 `decide` 選 cell，取 RQ3 之相對 regret；真值候選 < 2 時為 0。評估指標（誘導率等）則以當窗實際之全部判定計算，與 RQ3 同口徑。
6. **攻擊者 reward**：「被選中且非最佳」以當窗實際判定、C_strict 計；真值候選 < 2 時不可能誘導。
7. **觀測之正規化**：偵測端 z 除以 τ_S 並截於 4、peer 數除以 6、D1 z 除以 10 並截於 1（僅 level ≥ weak 之 UE；否則 0）；歷史以實際秒對齊，缺報之秒為全 0 並有存在旗標。攻擊者之延遲以自身 t0 前乾淨平均延遲正規化（DU 知道自身真值）；含自身過去乘數。
8. **信任根（anchor）**：評估（測試 seed）用其餘 7 seed，重現第四章；訓練 episode 之 anchor 另排除該 fold 之測試 seed，避免測試資料進入信任根。
9. **PSRO 之混合**：每個 episode 開始時依混合機率抽一個純策略。每個池成員為 8 個 fold 各一之模型（R-b），報酬取 8 fold 測試 seed × 7 cell 之平均；3 個訓練 seed 為 3 次獨立之 PSRO，報平均與範圍。
10. **G2 之範圍**：E11 之 C_i／D1／D2 類注入改變成員關係，不在攻擊者第一步之動作空間內，故 G2 只重現其 S_i 類 224 列（另與 E11 之獨立實作逐筆比對）。

**G1–G3 結果（2026-11-08，`data/results/d30/drl/env_checks/env_checks.json`）**：G1 15,534 筆逐筆相同；G2a 434,952 筆相同；G2b RQ3 之 4 攻擊 × 4 准入政策 × 8 指標最大差 0；G2c E11 之 S_i 類 224 列逐列相同；G3 重跑逐位相同。G4 於 PSRO 驅動程式完成後執行。

## 2b. 學習曲線（R-f）之判定規則（2026-11-09，先於執行）

- **偵測端**：Round 1 之偵測端最佳回應（對 Round 0 之 σ_A），fold 0（測試 seed 4200）、訓練 seed 0，共 2,000,000 步，每 100,000 步存檔。
- **攻擊者**（R-f 原文只寫偵測端；攻擊者之步數同樣須事先決定，故依同一規則補定〔2026-11-09 補定，先於執行〕）：Round 1 之攻擊者最佳回應（對 σ_D = D0）、O-full、fold 0、訓練 seed 0，共 1,000,000 步，每 50,000 步存檔。
- **驗證分數**：每個存檔以決定性策略於該 fold 之**訓練 seed**（7 seed × 全部 cell，訓練用 anchor）評估每步平均 reward；**不使用測試 seed**。
- **平穩點**：令 $\bar s$ = 最後 3 個存檔之平均、$s_0$ = 未訓練策略（step 0）之分數；容差 $\tau=\max(0.05\,|\bar s-s_0|,\ 10^{-4})$（即達到總進步量之 95 %）。$S^*$ = 最小之存檔步數 c，使 c 及其後每個存檔之分數與 $\bar s$ 相差 ≤ τ。（原擬以 ε = 0.01 為絕對容差，但 Round 0 顯示偵測端每步報酬之量級僅約 0.01，絕對容差無鑑別力，故於執行前改為相對容差。）$S^*$ 即凍結為該角色之訓練步數，用於所有輪、兩種觀測層級與 3 個訓練 seed。
- 若最後一個存檔才符合（未見平穩），不自行延長，回報使用者。
- 超參數：SB3 預設（n_epochs 10、γ 0.99、GAE λ 0.95、clip 0.2、lr 3e-4、MLP 64×64），n_steps 2048、batch 256；torch 單執行緒。

**R-f 結果與事後修正（2026-11-09，使用者決定）**：學習曲線（`data/results/d30/drl/lcurve/`）：偵測端分數由 −4.04（未訓練）於第一個存檔（100,352 步）升至 0.0167，其後於 0.0165–0.0179 間波動，依上述規則 $S^*$ = 100,352；攻擊者於第一個存檔（51,200 步）即達 0.345，其後隨訓練下降（1,024,000 步時 0.290），依上述規則 $S^*$ = 972,800——恰落於退化之後，規則所假設之「單調進步」不成立。**事後修正**：每個最佳回應改為「上限＋驗證選最佳」——訓練至多 300,000 步、每 50,000 步存檔一次，以決定性策略於該 fold 之**訓練 seed**（全部 cell）對對手混合之**期望**每步 reward（依混合機率加權，不抽樣）評分，保留分數最高之存檔（同分取較早者）；不使用測試 seed。原規則與其結果保留於上，不刪除。

**Round 0 與 G4（2026-11-09，`psro.py --g4-only`）**：G4 通過——D0 × A0 之誘導率（C_strict）2.2363%／46.2092%／8.2922% 與 RQ3 逐位相同；乾淨 D0 誤拒 159／15,534 與第四章相同。meta-solver：Lemke–Howson 於 1×3 之退化賽局未得合法解，依 R-c 改用 support enumeration（已記錄）；σ_A = ×0.8 階躍（純策略）。

## 3. DRL 偵測端（Phase 3；P1、P11）

| 元素 | 定義 |
|---|---|
| 決策單位 | (節點 j, 秒 t)；L1 rejected 規則（`R1_AUTHZ`、`R1_CI_VETO`、`R1_D2_VETO`）觸發時不交給 DRL |
| floor | V-escalate（主）：severity 版 `fuse()` 之完整判定。V-replace（對照）：僅 L1（含 `R1_CI_PENDING` → ≥ low-trust）＋ L3 |
| action | {trusted, low-trust, rejected}，以 action mask 限於 severity(a) ≥ severity(floor)；abstain 只由 L3 產生 |
| state | $z_j(t)$、peer 數、歸屬 j 之 D1 $z_d$ 最大值與證據強度、C_i pending 旗標；過去 k 秒之上述值與本 agent 過去 action。k = 5〔已確認〕。**不含** peer 中位數與尺度 s 本身 |
| reward | 竄改且判 rejected：+1；竄改且判 low-trust：+λ；竄改且判 trusted：−α·(該秒 steering 錯誤成本，RQ3 regret 正規化)；未竄改且判 rejected：−β；未竄改且判 low-trust：−μ；未竄改且判 trusted：+μ。λ=0.3、α=1、β=5、μ=0.05〔已確認〕 |
| 演算法 | MaskablePPO（sb3-contrib 2.6.0）〔已確認〕；於 PSRO 中作為偵測端之最佳回應訓練器（§3a）；訓練 seed 0、1、2（≥3），報平均與範圍 |
| 部署 | 凍結（frozen）與線上（online，Phase 5）兩者皆做（P1） |

標籤：(節點, 秒) 之報告是否被竄改；被攻陷節點於注入起點前標為未竄改。

## 3a. 訓練流程：PSRO（v2 新增；參數見 §10b，已確認）

**理由**：兩個學習者若只輪流訓練一次，可能互相追逐（偵測端學會新攻擊、忘記舊攻擊）。改採 PSRO（policy-space response oracles；Lanctot et al., NeurIPS 2017, arXiv:1711.00832）；以 DRL 作最佳回應之 double oracle 於安全賽局之先例見 Eghtesad, Vorobeychik, Laszka, GameSec 2020（LNCS 12513, pp. 58–79）。

**策略池**：
- 偵測端池 $\mathcal{D}$：$D_0$ = 規則版 L2（基線 B1；即 V-escalate 恆選下限）。
- 攻擊者池 $\mathcal{A}$：$A_0$ = 第四章之腳本攻擊（R-a）。

**每一輪**：
1. **報酬表**：池中每對 $(D_i, A_j)$ 於評估 seed 上對戰，填入雙方之平均每步報酬（偵測端：§3 之 reward；攻擊者：§4 之 reward）（R-b）。
2. **meta-solver**：一般和雙矩陣賽局，以 Lemke–Howson 求一個 Nash 均衡（初始 label 固定以確保決定性；R-c），得雙方之混合 $\sigma_D, \sigma_A$。
3. **最佳回應**：偵測端以 MaskablePPO 對 $\sigma_A$ 訓練新策略；攻擊者以 PPO 對 $\sigma_D$ 訓練新策略。
4. 新策略加入各自之池，回到 1。

**停止**：NashConv（各方最佳回應相對目前混合之報酬增益之和；即 exploitability）≤ 0.05 × 第 1 輪之 NashConv，或達最大輪數（R-d，2026-11-09 改為相對門檻）。

**主張**：僅為**受限賽局（目前之策略池）之近似均衡**，以 NashConv 衡量並報告其隨輪數之曲線；**不是**全域均衡保證。每輪之 $D_i$ 皆受規則下限約束（只能更嚴），故任何混合仍為 fail-closed。

**與 v1 之階段對應**：Round 0 = 第四章（$D_0$ vs $A_0$）；Round 1 之偵測端最佳回應 = Stage 1（v1 之 Phase 3）；其後輪次 = Stage 2（Phase 4）；凍結 vs 線上（Phase 5）：以最終混合 $\sigma_D$ 為凍結版，另以線上更新版對最終 $\sigma_A$ 比較；Stage 3（Phase 6）：最終池於 Stage 3 資料上評估，不再訓練。

**觀測層級與 token**（R-e）：PSRO 分別於 O-full 與 O-outcome 各跑一次（P9）；token 洩漏（P10）於最終輪以 O-outcome+token 訓練攻擊者最佳回應，對最終 $\sigma_D$，連動 vs 不連動比較（§5 之 (i)–(iii)），不另跑完整 PSRO。

**新增一致性檢查**：G4——Round 0 之 $(D_0, A_0)$ 報酬表所對應之 TPR／乾淨誤拒／誘導率，須重現第四章（4.9.6、4.12）之數字；失敗即停。

**正式 PSRO 結果與決定（2026-11-10～11，新機器 i7-14700；`data/results/d30/drl/psro/<level>/t<seed>/state.json`）**：
- 新機器 G1–G4、S1–S2 全數通過（`data/results/d30/drl/machine.txt`、`env_checks/`）；舊機器之 O-full t0 試跑不引用。
- NashConv（第 1→6 輪）：O-full t0 0.0220／0.2337／0.0927／0.0574／0.0215／0.0366；t1 0.0239／0.3103／0.0220／0.0105／0.0069／0.0196；t2 0.0260／0.3042／0.0094／0.0326／0.0507／0.0308；O-outcome t0 0.0208／0.2674／0.0097／0.0413／0.0356／0.0215；t1 0.0184／0.2561／0.0373／0.0369／0.0236／0.0110；t2 0.0212／0.2510／0.0110／0.0038／0（第 5 輪達門檻停止）。
- **5／6 組於 6 輪內未達停止門檻（達最大輪數）**；唯一達門檻者（O-outcome t2）之 NashConv = 0 係雙方增益經 max(0,·) 截斷（新最佳回應未優於現行混合），非精確均衡。第 1 輪 NashConv 偏小（攻擊者尚未學會），第 2 輪普遍跳升約 10 倍。
- **使用者決定（2026-11-12）：方案 A——照現況接受，不增加輪數、不改門檻**；正文報告逐輪 NashConv 曲線並明寫 5／6 組未達門檻，主張維持「受限賽局之近似均衡」。最終混合（`state.json` 之 `sigma`）即為後續評估、凍結 vs 線上、token 洩漏、Stage 3 所用之「最終 σ」。
- 最終評估之規格：`E19_eval_final_spec.md`。

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
| 演算法 | PPO（連續 action）；於 PSRO 中作為攻擊者之最佳回應訓練器（§3a）；訓練 seed 0、1、2 |

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

## 10b. v2 參數（2026-11-08 全部依建議值確認）

| # | 項目 | 建議值 | 理由 |
|---|---|---|---|
| R-a | $A_0$ 之內容 | ×0.6 階躍、×0.8 階躍、漂移 1 %/秒（3 個池成員，各自為純策略） | 皆為第四章／RQ3 已有之腳本，G4 可直接對帳 |
| R-b | 報酬表之評估資料 | 每對於 LOSO 之測試 seed（8 fold）上評估，取平均；被攻陷 cell 依 Q-a 輪替 | 與第四章同口徑，避免以訓練 seed 評估 |
| R-c | meta-solver | Lemke–Howson（`nashpy` 0.0.43，2026-11-08 安裝於 `~/venvs/drl`；numpy 2.2.6、scipy 1.15.3），初始 label 0；若退化則改 support enumeration 並記錄 | 一般和雙矩陣；固定 label 以確保 G3 決定性 |
| R-d | ε 與最大輪數 | ~~ε = 0.01（每步報酬單位）~~ → **相對門檻（2026-11-09 使用者決定，先於任何 PSRO 訓練）**：NashConv ≤ 0.05 × 第 1 輪之 NashConv（即完成總下降量之 95 %）即停；第 1 輪 NashConv 為 0 時直接停止；最多 6 輪。理由：Round 0 顯示偵測端每步報酬之量級僅約 0.01，絕對 ε = 0.01 無鑑別力 | 偵測端每步報酬範圍 [−5, +1]，0.01 約為其 0.2 %；輪數上限依運算預算（每輪 2 個最佳回應 × 3 訓練 seed） |
| R-e | 觀測層級與 token 之安排 | 見 §3a（O-full、O-outcome 各一次 PSRO；token 洩漏只於最終輪量測） | 控制運算量；P9、P10 之要求仍滿足 |
| R-f | 每個最佳回應之訓練步數 | ~~先以 Round 1 之偵測端做學習曲線，取報酬平穩處~~ → **事後修正（2026-11-09）**：至多 300,000 步、每 50,000 步存檔，以訓練 seed 驗證保留最佳存檔（§2b） | 事先無可靠數值；以「先量測、再凍結」代替猜測，並標記於結果 |

## 11. v1 → v2 變更紀錄

- 訓練流程：分階段單次訓練 → PSRO（§3a）；主張由「不宣稱均衡」改為「受限賽局之近似均衡，以 NashConv 衡量，非全域保證」。
- 新增 G4（Round 0 重現第四章）。
- §0 前置條件 1、2 已完成；新增 4。
- 參考：Lanctot et al. (2017)；Eghtesad et al. (2020)；規則下限之安全性與 shielding 之關係：Alshiekh et al., AAAI 2018, pp. 2669–2678。
