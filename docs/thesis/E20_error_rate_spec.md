# 規格 E20：兩類誤判率之量測（v1）

> 狀態：**v1（2026-11-12）——使用者核可執行**（「其他結果目前給你執行」）；Q1–Q6 依 §9 之建議值定案。v0 草稿（同日）之參照清單 §8 未改。實作：`xapps/verification/residuals/run_E20_error_rates.py`；輸出：`data/results/d30_fusion_order/severity/E20/`。
>
> **v1 實作上之定義（v0 未明定處，執行前記錄）**：
> - 方法二分兩層：**2a** 只用節點窗之邊際比率 p_S、q（只假設 S_i ⟂ D1）；**2b** 之 q 由**逐 UE 之窗層級** D1 證據率（同 seed、樣本內）與每節點每窗之綁定 UE（消失前 serving cell = 該節點）以 1 − Π(1 − f_u) 組合（另假設 UE 間獨立）。論文 4.8.6 之 0.102 為**逐停留事件**之誤報率，單位不同，不直接代入。
> - E20-3 依論文口徑（D1 任一等級，7,502）重現 197；方法二之 rejected 預測則依規則表用 strong D1（q_strong）。
> - 逐 UE 歸因報兩種：**involved**（節點被擋且該 UE 有綁定之 D1 證據）與 **pivotal**（移除該 UE 之 D1 證據後，同政策下即會准入；以原函式 `verify_hi_d1_uebound` 與 `fuse_detail` 重算）。
> - M-count = `run_Hi_D1_performance.dwell_events` 之事件數（mmWave 後接 ≥ 1 窗 LTE-only）。
> - 竄改標籤與 E19 game_core 相同：受攻陷 cell、k ≥ t0、任一 UE 值與真值不同。
> - E20-5（PHY 交叉驗證，Q6）：seed 4200 之 RxPacketTrace DL 以 MmWaveSwitchStats 之 (cell, rnti) → IMSI 反查，逐秒比較 mmWave 狀態；只報告，不作判準。
> 動機：使用者指出，頻繁進出的 UE 可能被一直判為偽造資料（硬判準之風險）；E19 之 DRL 依 R7「只能更嚴」，結構上無法降低此類誤判（E19_eval_final_spec.md §12）。本規格先量測現況，作為「可放寬之學習元件」（另訂規格 E21）之依據。
> 本規格**不改任何凍結參數、不改主結果**；只讀既有資料與既有輸出，必要時以既有函式重算（不複製判定邏輯）。

## 0. 目的

量測兩類誤判，各以**兩套方法**估計：

| 代號 | 白話 | 定義 |
|---|---|---|
| **FB**（false block，誤擋） | 實際是對的，卻被擋下 | 未被竄改之 (節點, 窗) 中，**未進入准入視圖**者之比例 |
| **MF**（missed falsification，漏放） | 實際是錯的，卻留在系統中 | 被竄改之 (節點, 窗) 中，**進入准入視圖**者之比例 |

並回答：**FB 是否集中於頻繁進出（mmWave ↔ LTE 錨點）之 UE**。

## 1. 「擋下」之定義依准入政策而不同（4.4.0、程序 P3）

| 准入政策 | 擋下（不進准入視圖） | 進入准入視圖 |
|---|---|---|
| `strict` | low-trust、rejected、abstain | trusted |
| `restrict_annotated` | rejected、abstain | trusted、low-trust（加註記） |

兩種政策都報。FB 與 MF 為同一政策下之一對數字，不得跨政策配對。

## 2. 資料、單位與範圍

- 資料：D-30（8 seed × 0–299 窗，唯讀）；單位 (節點, 窗)；融合 severity order（`ZT_FUSION_ORDER=severity`）；uebound 綁定。
- 受評偵測端：**D0（規則版）** 兩套方法皆做；**DRL（E19 六組 σ_D）** 只做方法一（數字已在 `eval_final.json`，不重跑；方法二須在新機器另算，見 Q5）。
- 攻擊者（MF 用）：A-script（×0.6 階躍、×0.8 階躍、漂移 1 %/秒，與 RQ3 同口徑）；學習型攻擊者（A-pool 最壞、A-BR）只用方法一之既有數字。

## 3. 方法

### 3.1 方法一：端到端直接計數（標籤由構造給定）

- **FB-1**：乾淨重放之 15,534 筆註記（無攻擊，每筆皆為真），FB = 擋下筆數 ÷ 15,534。依 rule_id 分解；以 seed 為 cluster 報範圍。
- **MF-1**：注入 episode 中，受攻陷節點注入起點後之 (節點, 秒)：MF = 進入准入視圖之竄改筆數 ÷ 竄改筆數（strict：1 − TPR_nt；restrict_annotated：1 − TPR_rej，abstain 另計）。D0 取自 `eval_final.json` 之 `per_attacker_script`；另以第四章管線（`run_RQ3_decision_replay.py` 之注入方式）重算一次，兩份實作須一致（檢查 E20-1）。

### 3.2 方法二：由各證據之誤報／偵測率自下而上組合（獨立性假設）

不看融合後之端到端結果，只用**各證據分開量得之比率**，依 4.4.0 之規則表組合出預測值，再與方法一比較。

- 4.4.0 規則（乾淨資料上 C_i、D2、AUTHZ 違反皆為 0，故只剩 S_i 與 D1）：
  - rejected ⟺ S_i violated ∧ 同節點有 strong D1（`R2_SI_D1_BOUND`）
  - 非 trusted ⟺ S_i violated ∨ 同節點有 D1 證據（strong 或 warning）
- **FB-2**：令 p_S = 每 (節點, 窗) 之 S_i 乾淨誤報率，q_s／q_w = 每 (節點, 窗) 綁有 strong／任一 D1 證據之機率（由**逐 UE** 之 D1 誤報率與每節點每窗之綁定 UE 數推得，見 §4.2）。
  - FB-2(restrict_annotated) ≈ p_S · q_s
  - FB-2(strict) ≈ 1 − (1 − p_S)(1 − q_w)
- **MF-2**：竄改只改延遲值，D1 證據取自乾淨資料（E19 §2a.1），故 q 不變；令 r_S(a) = 攻擊 a 下竄改 (節點, 秒) 之 S_i 偵測率（取自 S_i／E9 之既有輸出，或以既有函式重算）。
  - MF-2(restrict_annotated) ≈ 1 − r_S(a) · q_s
  - MF-2(strict) ≈ (1 − r_S(a))(1 − q_w)
- **解讀**：方法一與方法二接近 → 融合大致等於各證據之組合；差距大 → 證據間有相關結構（例如同一 seed／cell 之異質性）。**差距本身是結果，不調參數使其一致**；且依論文 4.9.6.6 之限制，不得把「接近」寫成「已證明獨立」。

### 3.3 補充（非判準，見 Q4）：留下來的錯誤有多大

MF 只數「有沒有留下」。補充報告留下之竄改筆之相對偏差 |報告值／真值 − 1| 之分布（ε = 1 %、5 %、10 % 以上之比例），以及誘導率 C_strict（RQ3 口徑）。

## 4. 移動性指標（回答「頻繁進出之 UE」）

D-30 中**合法之 mmWave → mmWave 換手從未發生**（240 個 UE-run 之 serving mmWave cell 皆未改變；論文 4.8.4、454 行）；故「進出」＝ UE 在自己的 mmWave cell 與 LTE 錨點之間來回。

### 4.1 兩個指標

| 指標 | 定義 | 來源 | 狀態 |
|---|---|---|---|
| **M-frac**（停留佔比） | UE-run 之 LTE-only 窗佔比；≥ 0.55 為 edge（沿用值） | DlE2RlcStats（逐窗成員） | 既有（4.8.6、E15） |
| **M-count**（進出次數） | UE-run 中「mmWave → LTE-only」之轉移次數 ÷ 300 s | 同上，逐窗成員序列 | **新增**；使用者所說之「頻繁進出」較接近此指標 |

兩者不同：長時間停在錨點但很少來回者 M-frac 高、M-count 低；常常短暫掉到錨點者相反。

### 4.2 逐 UE 歸因

- 註記檔之 D1 證據只記**最嚴重之一個 UE**（`verify_hi_d1_uebound`：依 (等級, 停留長度) 取最大），其餘有貢獻之 UE 未記錄。
- 故逐 UE 歸因須以**同一函式**（`zt_kpm_xapp` 之 D1 判定，不複製邏輯）重算每窗每節點之**全部**有 D1 證據之 UE；檢查 E20-2：重算後每筆之「最嚴重 UE」須與註記檔逐筆相同。
- 每個 UE-run 報：其 D1 證據導致節點被擋之窗數（strict／restrict_annotated 各一）÷ 300。

## 5. 圖

| 圖 | 內容 |
|---|---|
| **E20-F1** | FB：兩種政策 × 兩套方法（方法一附 8 seed 範圍）；方法一依 rule_id 堆疊 |
| **E20-F2** | 逐 UE-run 散佈圖：x = M-count（每 300 s 進出次數），y = 該 UE 導致之擋下窗比例；顏色 = edge／resident（M-frac 0.55）；另一面板以 M-frac 為 x |
| **E20-F3** | MF：攻擊（×0.6、×0.8、漂移）× 兩種政策 × 兩套方法；D0 為點，DRL（方法一）為範圍 |
| **E20-F4** | 兩類誤判同平面：x = FB，y = MF（各政策、各偵測端、各攻擊一點）——「對的被擋」對「錯的留下」之取捨 |

## 6. 一致性檢查（內建；任一失敗即停，回報，不調參數）

- **E20-0**：註記檔重讀後之計數須等於論文值：15,534 筆；trusted 7,810、low-trust 7,565、rejected 159、abstain 0；`R2_SI_D1_BOUND` 159。
- **E20-1**：MF-1 之兩份實作（`eval_final.json` 與第四章管線）對 D0 × A-script 之 TPR_rej、TPR_nt 須一致（容許：逐位相同；若單位定義有差須先寫明再比）。
- **E20-2**：逐 UE 重算之「最嚴重 UE」與註記檔逐筆相同（15,534 筆）。
- **E20-3**：方法二之 rejected 預測須重現論文之獨立假設預期值（408 × 0.483 ≈ 197，4.9.6.6）——確認方法二之輸入與論文同口徑。
- **E20-4**：seed 對應——註記檔無 seed 欄位，依 window 歸零切成 8 段（各段筆數 1,985／2,026／1,866／1,869／2,055／1,730／2,046／1,957）；須與各 seed 之節點窗數逐一相符才可使用。

## 7. 揭露與不做的事

- 只量測，不提出新規則，不改門檻；E14（τ_H 6／7）等敏感度結果只並列，不據以改主結果。
- D1 基線為 per-UE-index（跨 run 以 IMSI 編號彙整，非部署意義之個別裝置），M-frac／M-count 亦同。
- edge／resident 為探索性分層（4.8.6），不作事前登記之群體定義。
- 方法二依賴獨立性假設；接近不代表獨立已被證明。

## 8. 參照清單（每一項皆已讀過原檔；請逐項確認）

| # | 參照 | 位置 | 原文／數值 | 用途 |
|---|---|---|---|---|
| R1 | 乾淨註記 | `data/results/d30_fusion_order/severity/xapp_trust_annotations_bound_all_uebound_strict.jsonl` | 15,534 筆；trusted 7,810／low-trust 7,565／rejected 159／abstain 0；rule：R0_CLEAN 7,810、R2_D1_STRONG 6,183、R2_D1_WEAK 1,133、R2_SI_ALONE 249、R2_SI_D1_BOUND 159 | FB-1；E20-0 |
| R2 | 准入政策對應 | 論文 4.4.0；簡報程序 P3 | trusted 准入；low-trust：strict 排除、annotated 准入＋註記；rejected 排除；abstain 暫緩不准入 | §1 |
| R3 | 單一統計證據不冒進 | 論文 777 行（三項行為承諾 2） | 「S_i 或 H_i-D1 單獨違反僅得 low-trust，其必要性由 4.8.6 之 edge UE 誤報率實證」 | 動機；E21 之約束 |
| R4 | D1 逐 UE 誤報率 | 論文 4.8.6（1487–1501 行），`run_Hi_D1_performance.py` | 整體 0.102（± 0.022）；resident 0.01–0.04；edge 0.20–0.31 | FB-2 之輸入；F2 對照 |
| R5 | edge／resident 分群 | 論文 1508 行 | LTE-only 窗佔比 ≥ 0.55 為 edge；resident 163／edge 77（240 UE-run）；沿用前版、未於 D-30 重選；探索性分層 | M-frac |
| R6 | E15 分群門檻敏感度 | 論文 1516–1522 行 | 門檻 0.50／0.55／0.60：整體 FPR 皆 0.102；edge FPR 0.236／0.263／0.320；8／8 seed edge > resident | 穩健性對照 |
| R7 | 無合法跨 cell 換手 | 論文 454 行、3.3.3、4.8.4 | 240 個 UE-run 之 serving mmWave cell 皆未改變 | §4 之「進出」定義 |
| R8 | MmWaveSwitchStats 無用 | `data/ues30_seeds/ues30_t300_seed4200_aux/MmWaveSwitchStats.txt` | 只有 30 筆開機 attach（0.054 s），無後續轉移 | 說明 M-count 須自 RLC 序列計算 |
| R9 | D1 證據只記最嚴重 UE | `zt_kpm_xapp.py` 350–362 行 | `worst = max(mine, key=(level, 停留長度))`；ev 只含一個 imsi | §4.2 須重算 |
| R10 | 獨立假設預期 | 論文 1810 行 | S_i 乾淨違反 408（2.6 %）；48.3 % 節點註記綁 D1（7,502）；預期 197，實際 159；不得寫成已證明獨立 | 方法二；E20-3 |
| R11 | D0 對腳本攻擊之 TPR | `psro_newmachine_20261111/eval_final/eval_final.json` → `baselines.D0.per_attacker_script` | ×0.6：TPR_rej 0.394604、TPR_nt 0.980638；×0.8：0.014070、0.519298；漂移：0.341780、0.900325 | MF-1（D0） |
| R12 | DRL 對腳本攻擊（最壞） | 同上 → `runs.*.A-script.by_TPR` | ×0.8：TPR_nt 0.600–0.724、乾淨非 trusted 0.504–0.509 | MF-1（DRL） |
| R13 | 攻擊只改延遲、D1 取自乾淨 | `E19_DRL_game_spec.md` §2a.1（新機器版本為準） | 攻擊者第一步只改 delay，成員關係證據不變 | 方法二之 q 不變 |
| R14 | R7「學習只能更嚴」 | 論文 45 行、2275 行 | 「學習元件只能使規則之判定更嚴，不能更寬鬆」；shielding（Alshiekh et al., 2018） | 動機；E21 必須面對之約束 |
| R15 | 節點層 low-trust 之規模效應 | 論文 1783 行、4.9.6.3 | window 政策下 97.3 % low-trust 由 D1 單獨觸發；證據綁定粒度之錯配 | FB 主因之既有診斷 |

由 R1 直接可讀之現況（**引用既有計數，非新計算**）：strict 下乾淨資料被擋 7,724／15,534（49.7 %），其中 7,316 筆（low-trust 之 96.7 %）由 D1 單獨觸發；restrict_annotated 下被擋 159／15,534（1.0 %）。

## 9. 決定（2026-11-12：依建議值）

| # | 問題 | 建議 |
|---|---|---|
| Q1 | FB／MF 兩套方法是否為「端到端計數」＋「各證據自下而上組合」 | 是；兩者回答同一數字、方法不同，差距本身有資訊 |
| Q2 | 移動性用 M-count（進出次數）為主、M-frac 並列 | 是；M-count 較貼近「頻繁進出」 |
| Q3 | 兩種准入政策都報 | 是；FB 與 MF 之取捨主要由政策決定 |
| Q4 | §3.3（偏差大小、誘導率）是否做 | 做，但只當補充 |
| Q5 | DRL 之方法二（新機器另算）是否做 | 先不做；E21 之對象是「可放寬」元件，DRL（只能更嚴）只需方法一作對照 |
| Q6 | 是否以 PHY 層 `RxPacketTrace` 之 serving cell 交叉驗證 M-count（模擬器層級、獨立於 E2 管線） | 建議做一個 seed 作檢查，不作主指標 |

## 10. 之後（不在本規格）

E21「可放寬之學習元件」：依 E20 結果，先另給一份**參照清單**（論文內之約束 R3、R14、fail-closed、L1 不可放寬等＋外部文獻，每篇先查證原文再列），使用者看過後才開始設計。
