# 資源分配移至下一篇：影響清單（2026-11-19，供與老師討論；未改任何正文／簡報）

> 使用者 11-19 提議：資源分配（resource allocation）自本篇移除，作為下一篇題目。本檔只列影響與待決事項；**老師同意前不改正文、簡報、程式**。
> 依據：正文 `thesis_v12_2.md`（行號為該檔）、簡報 `~/Downloads/Cindy_Thesis_v1.16.pptx`（頁碼為 v1.16）。

## 1. 建議的切法

| 部分 | 處理 | 理由 |
|---|---|---|
| 可用資源評估 xApp（第 4 個 xApp）、ρ_PRB／V_PRB／ρ_cap、准入輸入可用率、原生 PRB 分析（RQ3_PRB、E18、B4、M1 中之第 4 xApp） | **移至下一篇** | 屬「資源」本身；下一篇以閉迴路 ns-3 做才完整 |
| steering 代理決策（選回報延遲最低之 cell）、誘導率、regret | **保留，但降為「量傷害之工具」，不再是貢獻** | E19 攻擊者報酬 = lured（`game_core.py:221`）、偵測端報酬含 steering regret（正文 2398）；E29 之 Q6-c 指標（攻擊者得利＋regret）亦依賴它。拿掉則 DRL 賽局與兩張比較圖都失去目標 |
| 驗證延遲（P99 1.16–1.42 ms，歷史版本） | 保留 | 與資源分配無關 |
| 准入政策（P3：strict／restrict） | 保留 | 題目中之 “Admission” 依此成立 |

## 2. RQ／貢獻之改法（二選一）

| 方案 | RQ3 | C3 | 優缺點 |
|---|---|---|---|
| **A（建議）** | 「准入之代價與保護：乾淨誤拒之可用性成本、下游決策（steering）之誘導率與 regret、驗證延遲」＝ 原 3b ＋ 3c，刪 3a | 「KPM 准入對下游決策之保護與代價」，不含 PRB／容量 | 維持 4 RQ，改動集中在 4.12；第五章不必動 |
| B | 刪除 RQ3；延遲併入 RQ2，誘導率併入 RQ4 | 刪除，C4 → C3 | 結構較緊，但編號全部重排、第五章與簡報改動大 |

**名稱衝突（任一方案都要處理）**：正文 4.7.5.5 與 11-19 進度報告中的「C3」指「同條件偵測方法比較」，與貢獻 C3 同名。建議 4.7.5.5 改稱「同條件比較（SC）」。

## 3. 正文影響（`thesis_v12_2.md`）

| 位置 | 內容 | 方案 A 之改法 |
|---|---|---|
| 36 | RQ 總述「放行之代價（RQ3）」 | 保留措辭 |
| 75–83 | RQ3 子問題 3a／3b／3c、範圍聲明 | 刪 3a（PRB、ρ_cap）；範圍聲明刪「可用資源評估 xApp」「PRB」句 |
| 121–131 | C3 | 改寫為 steering 保護＋可用性成本＋延遲；刪 ρ_PRB 50.6%、ρ_cap 49.5% |
| 206 | 架構時序圖之「准入…可用資源」 | 刪第 4 xApp |
| 368–377（3.3.5） | PRB「僅用於 4.12 之資源評估」 | 改為「本篇不使用 PRB」；保留「吞吐量竄改不在範圍」 |
| 399、406 | 「四個 xApp」、第 4 xApp 之表列 | 三個 xApp |
| 440 | `du-cell-*.txt` 用途「RQ3 之原生 PRB」 | 改為「本篇未使用」 |
| 445–466（4.0.3） | D-30 開 E2 NR 報表之理由（含 PRB） | 理由改寫；最後一窗遺失之副作用仍須揭露 |
| 1685–1800（4.9） | 標題「四 xApp 架構」、④ 之定義、M1 四 xApp 合計 P99 | 三 xApp；M1 只留 P1–P3 |
| 2084–2266（4.12） | 資源—政策評估全節 | 改為「准入之保護與代價」：留誘導率、regret、決策可用率；刪 ρ_PRB、V_PRB、ρ_cap、Fig 4-16b |
| 2289–2297（4.13 總結 RQ3） | 含 ρ_cap、ρ_PRB、四 xApp 合計 | 同上刪除 |
| 2318 | 實驗總表之輸出欄 | 刪 PRB 類 |
| 2366（5.1） | 偵測對誤拒「可用資源下降（ρ_PRB）」 | 改為「乾淨誤拒率」 |
| 2398、2409、2471（第五章） | steering 誘導、RQ3 regret | **不變**（steering 保留） |
| 2513–2514、2555–2556 | Fig 4-16b、`resource_eval_xapp.py` | 刪 Fig 4-16b 與 `resource_eval_xapp.py` 列；`run_RQ3_decision_replay.py` 保留 |
| 第六章（未寫） | 未來工作 | 新增「閉迴路資源分配，以本篇信任註記為輸入」 |

## 4. 簡報影響（v1.16 頁碼）

| 頁 | 標題 | 改法 |
|---|---|---|
| 15、16 | Research Questions／Contributions | RQ3、C3 依方案 A 改寫，刪 PRB |
| 17 | Validation Status | 刪 PRB／資源列 |
| 26 | Scenario and Use Case | 檢查 PRB 字樣 |
| 28 | C-ZT Framework with Zero-Trust Authorization | 架構圖刪 Available-resource evaluation 與 Resource Termination |
| 29 | C-ZT: Four xApps, Four Verbs | 改為 Three xApps；刪 P4 |
| 36 | P3. Enforce: Policy and Resource Evaluation | 標題改為 Policy Enforcement；刪資源評估步驟 |
| 37 | D. Learn | 「four xApps」改字 |
| 46 | Evaluation Design | 「Fixed: P1 · P3 · P4」改為「P1 · P3」 |
| 48、51、57 | 環境／觀測／資料集 | 刪 PRB、resource evaluation 字樣 |
| 52 | Correction: Running Mean | 檢查 RQ3 敘述 |
| 63 | Resource Evaluation: Protection vs Availability (RQ3) | 改為「Admission: Protection vs Cost」，只留誘導率／regret |
| 67 | Computation Overhead of Four Logical Modules | 改為三個 |

## 5. 程式與資料

- 不刪任何程式或資料：`resource_eval_xapp.py`、`RQ3_PRB_spec.md`、E18 結果保留於 repo，供下一篇使用。
- D-30／D-30P 不需重收（E2 NR 報表照開，只是本篇不讀 PRB）。
- 待重算清單（D-30P 通過後）因此減少：不必重算 ρ_PRB、ρ_cap、E18、B4、M1 第 4 xApp。
- E29 與兩張比較圖不受影響（只用 steering 之誘導率／regret）。

## 6. 要問老師的事

1. 同意移除嗎？採方案 A（RQ3 改為「准入之保護與代價」）還是 B（併掉 RQ3）？
2. steering 保留為量傷害之工具（不當貢獻），可以嗎？
3. 下一篇之範圍：閉迴路 ns-3 之資源分配（以信任註記為輸入），是否也在本碩論之未來工作中寫明？
