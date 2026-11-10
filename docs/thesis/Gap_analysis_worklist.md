# 完整缺口盤點與工作清單

> 觸發事件：Alimohammadi et al. (2026), *Towards a Multi-Layer Defence Framework for Securing
> Near-Real-Time Operations in Open RAN*, arXiv 2512.01596v2。
> 這是你的**直接競爭者**，本檔以它為基準重新盤點。

---

# 一、先認清處境：這篇跟你是同一個題目

## 1.1 它跟你重疊到什麼程度

| 面向 | Alimohammadi 2026 | 你 |
|---|---|---|
| 威脅模型 | 中毒發生在遙測被 RIC 取用之前，兩個向量：E2 介面 MitM、**被攻陷的 E2 節點直接控制資料來源** | 被攻陷 O-DU 在編碼前竄改 |
| 介面 | E2 / E2SM-KPM | 同 |
| 平台 | FlexRIC + 商用 RAN emulator | ns-O-RAN（FlexRIC 整合未完成） |
| 部署形式 | 獨立 xApp + 平台內 mitigation unit | 獨立 xApp（trace replay） |
| 判定粒度 | per (UE, timestamp) KPM record | per (node, window) |
| 方法 | LSTM/GRU/1D-CNN/Transformer 時序異常 | 三不變量 + 階層式融合 |
| 成果 | ADR ≥97.9%、FPR ≤0.07%、推論 0.15 ms、端到端 <80 ms @500 UE | — |

**威脅模型幾乎相同。** 你不能再用「這個威脅沒人做過」當貢獻，必須改成「這個威脅的既有解法有什麼結構性限制」。

## 1.2 但它自己寫下了三個你可以站的位置

**(a) 它承認可能漏掉慢速中毒。** 討論章明說：若訓練集未涵蓋完整的正常運作多樣性，模型可能產生誤報，或**漏掉緩慢、隱蔽的中毒模式**。

**(b) 它的攻擊模型只有階梯，沒有漂移。** 中毒是以放大因子 AF = 1.2 / 1.3 / 1.4 / 1.5 放大目標 UE 之 KPM 分布的平均與共變異數，發生於隨機選定的時間區段。**這是 20–50% 的瞬間階躍**。而你 4.7.4 的消融顯示，時間自我參照在 ≤2%/窗 的慢速漂移下偵測率僅 0.01。**它的 97.9% 完全沒有在你的操作區被測試過。**

**(c) 它把可解釋性列為限制。** 明說 LSTM 判定不透明，難以提供人類可理解的理由，可能影響操作者信任與事件處理，並建議探索 XAI 或統計門檻與學習模型的混合。**你的不變量判定天生帶證據**（哪個 IMSI、偏離多少、哪個 cell），這正是它缺的。

## 1.3 你的貢獻主張必須重寫成這樣

> 既有的 KPM 中毒偵測採學習式時序建模，於階躍型中毒（幅度 20–50%）達成高偵測率；本研究以受控消融顯示，該類參照機制在低速漸進漂移（≤2%/窗）區間存在結構性盲區，並提出以架構不變量與跨節點同時態共識為參照的互補驗證層，其判定帶可追溯證據且不需標註訓練資料。

三個可辯護的差異點：**操作區不同**（慢速 vs 階躍）、**參照不同**（空間 vs 時間）、**證據性質不同**（可追溯 vs 黑箱）。

---

# 二、你的機制缺口（依嚴重度）

| # | 缺口 | 嚴重度 | 為什麼是問題 | 方向 |
|---|---|---|---|---|
| G1 | **乾淨資料 trusted 僅 23.5%** | 極高 | 對方 FPR 0.07%。這個對比會直接被拿來打。根因是 D1 證據綁定粒度錯配（已診斷） | 做 UE-bound / L_H persistence 政策消融，把 trusted rate 拉上來並報 trade-off |
| G2 | **沒有 mitigation / 動作層** | 高 | 對方有三層嚴重度（small/moderate/significant）對應三種動作（丟棄、封鎖來源節點、上報）。你只有註記，沒有政策層 | 補一節「處置政策」，定義分級與動作，即使只在離線層實作 |
| G3 | **沒有 runtime 整合** | 高 | 對方在 FlexRIC 上跑起來了 | 你已誠實聲明（4.0.6）。至少補「介面契約」說明替換 IndicationSource 後需要什麼 |
| G4 | **規模差 70 倍** | 中高 | 你 7 UE，對方 50 / 500 UE | 用你的成本模型外推（已有 F+S·N），並誠實標註外推限制 |
| G5 | **無 PRB / CQI** | 中高 | 對方的特徵含 PrbUsedUl / PrbUsedDl | 你已聲明（4.3.2 / 4.5.2）。但現在有具體對照，要在限制節指名：「既有工作可取得 PRB 相關量測，本研究之 RLC trace 不含」 |
| G6 | **D1 與 S_i 證據天生無法綁定** | 中高 | 4.4.3 第二層在你資料上從未合法觸發 | 已識別。改用「消失前 serving cell」為綁定依據，列後續工作或實作 |
| G7 | **L_C 脈衝逃脫** | 中 | E6 已量化：D=1 逃脫率 100% | 做振盪政策實驗（E11），給 trade-off 曲線 |
| G8 | **無 benign evidence-loss 驗證** | 中 | 你主張「證據不可得 ≠ 可信」，但沒用資料驗證過 | 四種擾動注入 |
| G9 | **無合法 handover** | 中 | D2 的必經錨點規則從未被合法換手測試 | 已誠實聲明。可考慮改場景參數製造換手 |
| G10 | **τ_S 門檻選擇洩漏** | 中低 | 已揭露 | 報 τ_S ∈ {3,4,5} 的 seed-level 結果 |
| G11 | **S_i 誤報率非穩態** | 中低 | 前半 0.111 / 後半 0.025 | 已量化，寫成 startup exclusion window 的設計依據 |

---

# 三、可補的實驗（依 CP 值排序）

| 編號 | 實驗 | 解決 | 需重跑 ns-3 | 工時 | 價值 |
|---|---|---|---|---|---|
| **E9** | **對抗既有方法的操作區對照**：在你資料上實作 AF=1.2–1.5 階躍注入，比較「你的方法 vs 時間自我參照」在階躍與漂移兩個區間的偵測率 | 1.3 主張 | 否 | 1.5 天 | **最高**。這是你唯一能直接回應對方 97.9% 的實驗 |
| E10 | D1 政策消融（UE-bound / L_H=2,3） | G1 | 否 | 1 天 | 極高 |
| E11 | 振盪／脈衝政策掃描（on/off 週期 × L_C 變體 × 累計計分） | G7 | 否 | 1 天 | 高 |
| E12 | benign evidence-loss 四情境 | G8 | 否 | 1 天 | 高 |
| E13 | τ_S ∈ {3,4,5} 敏感度 + S_i per-seed 曲線 | G10 | 否 | 0.5 天 | 中高 |
| E14 | 信任狀態時間軸 + 復原延遲 | 敘事完整性 | 否 | 1 天 | 中高 |
| E15 | H_i 基線消融（global / group / UE-index） | per-UE-index 質疑 | 否 | 1 天 | 中 |
| E16 | 處置政策模擬（三級嚴重度 → 三種動作，離線重放） | G2 | 否 | 1 天 | 中 |
| E17 | 決策重放（ground truth / raw attacked / verified 三組輸入的決策分歧度） | RQ3 保護效果 | 否 | 2 天 | 中 |
| E18 | 合法 handover 場景（調 isd / 速度製造跨 cell 換手） | G9 | **是** | 2–3 天 | 中低 |
| E19 | 補 D-SH seed 至 8–10 | 統計強度 | **是** | 2 天 | 低 |

**E9 是這次新增的最重要實驗。** 沒有它，你的「慢速漂移盲區」主張只是對自己實作的消融，不是對既有方法的挑戰。有了它，你可以畫一張「偵測率 vs 攻擊幅度」的雙曲線圖，顯示兩種方法的操作區互補——**這張圖會是你全篇最有說服力的單一結果**。

---

# 四、資料蒐集需求

| 需要 | 目的 | 取得方式 | 必要性 |
|---|---|---|---|
| 階躍注入資料（AF 1.2–1.5） | E9 | 現有 trace 離線注入 | 必要 |
| 週期脈衝注入 | E11 | 現有 trace 離線注入 | 必要 |
| 擾動注入（缺報／延遲／錯位） | E12 | 現有 trace 離線注入 | 必要 |
| 合法跨 cell handover 軌跡 | D2 的 FPR 驗證 | ns-3 重跑，調高 UE 速度或縮小 isd | 建議 |
| PRB / CQI | B2 涵蓋 | ns-O-RAN 的 KPM 清單未接出；需改 parser 或換 trace 來源 | 選用 |
| 更多 UE（≥50） | 規模對照 | ns-3 重跑，但 4.6.1 已說明 MC 候選 cell 評估在高密度下無法穩定長跑 | 不建議 |

**不要為了追對方的 500 UE 而重跑。** 你的成本模型（F≈53 μs + S≈135 μs/node）可以外推，而且 4.6.1 已經說明規模限制的技術成因。硬追反而會暴露模擬器限制。

---

# 五、架構完整性

## 5.1 對方有而你沒有的架構元件

| 元件 | 對方的做法 | 你該怎麼辦 |
|---|---|---|
| Mitigation unit | 平台內，policy + decision maker，三動作 | **補一節設計**（不必實作）：分級 → 動作對應表 |
| 驗證後的遙測路徑 | 偵測 xApp 把驗證過的 KPM 存入共享 DB，其他 xApp 從 DB 取用而非直接訂閱 | **這是一個你該討論的替代方案**。它等於用 DB 中介繞過「無法攔截」的限制 |
| 多層次防護 | 訊息層 + 資料層 + 控制邏輯層 | 你只做資料層。**明確定位為資料層的深化，而非與多層框架競爭** |
| 操作者可配置政策 | 可調整、可擴充 | 你的 τ_S / L_C / τ_H 已是可配置參數，包裝成「政策參數」即可 |

## 5.2 一個重要的架構觀察

對方用「驗證 xApp 寫入共享 DB，消費端讀 DB」解決了攔截權限問題——**這是註記型之外的第三種動作模式**，你 4.9.3 的三選一表格（註記／攔截／告警）漏了它。

建議把 4.9.3 的表格擴成四列，加上「中介型（mediated）：驗證元件成為遙測的唯一供應者，消費端改讀驗證後的資料存放區」，並討論其代價：增加一跳延遲、驗證元件成為單點故障與新的攻擊目標、時間敏感 xApp 需要 bypass 機制（對方自己也提到要保留直接存取路徑給超時間敏感的 xApp）。

**這一改會讓你的架構討論比對方更完整**，因為你把它的設計納入比較框架並指出代價。

---

# 六、評估機制的優化

| 現況 | 問題 | 改法 |
|---|---|---|
| 只有 clean FPR 與 injected TPR | 對方報 ADR / FPR / Latency 三項並掃描攻擊幅度 | 補「偵測率 vs 攻擊幅度」曲線（E9），這是領域標準呈現方式 |
| runtime 只報 P99 | 對方報 min/max/avg 並分 50 / 500 UE | 你已有 per-seed 與成本模型，補 min/max 即可 |
| 無 baseline 對照 | 對方明說「因無同類可部署方案，只能與未防護系統比較」 | **你有更好的對照**：時間自我參照消融。要強調這一點 |
| 無端到端影響 | 對方報 data availability time shift | 你可報「驗證層開銷佔 1 秒週期的比例」（0.084%），並說明為何不報 time shift（無閉迴路） |
| 誤報率呈現 | 你的 73.9% low-trust 看起來很糟 | **拆開報**：「low-trust ≠ 誤報」。應報 (a) 硬否決誤觸率（0%）、(b) 需佐證率、(c) 可直接採信率。三個數字分開，不要讓 73.9% 單獨出現 |

**最後一條很重要。** 對方的 FPR 0.07% 是「良性記錄被錯誤標記的比例」，你的 73.9% 是「需要佐證的窗比例」——**兩者不是同一個量**。如果不拆開講，讀者會直接相減。你的等價量是「硬否決誤觸率」，修正綁定後是 0%。

---

# 七、文獻缺口與三殘差的參照關鍵字

## 7.1 必須補的三支（上一輪已說，這裡加優先序）

| 支線 | 為什麼現在更急 | 關鍵字 |
|---|---|---|
| **KPM 中毒（O-RAN）** | 已有直接競爭者，必須完整處理 Alimohammadi 系列三篇 | 見 7.2 |
| **FDIA / bad data detection** | 你的 E3 盲點與 FDIA 的 unobservable attack 是同一結構 | 見 7.3 |
| **蜂巢網路量測造假** | cell outage detection 是 S_i 的先例 | 見 7.4 |

## 7.2 Alimohammadi 團隊的完整系列（全部要引）

```
KPI Poisoning: An Attack in Open RAN Near Real-Time Control Loop, FNWF 2024   ← 攻擊模型原始出處
Towards a Multi-Layer Defence Framework..., arXiv 2512.01596, 2026            ← 防禦框架（本篇）
A New Sub-Use Case for Signaling Storm Attack in Open RAN..., CSCN 2024
Contrastive Learning for Distortion Tolerable Network Slice Prediction, WCNC 2025
```

同時從這篇的參考文獻直接抓這幾篇（都是你第二章該有的）：

```
Hung et al., Security Threats to xApps Access Control and E2 Interface in O-RAN, OJCOMS 2024
Hung et al., Anomaly Detection for Mitigating xApp and E2 Interface Threats, OJCOMS 2025
Baguer et al., Attacking O-RAN Interfaces: Threat Modeling, Analysis and Practical Experimentation, OJCOMS 2024
Thimmaraju et al., Security Testing The O-RAN Near-RT RIC & A1 Interface, WiSec 2024
Abdalla et al., ZTRAN: Prototyping Zero Trust Security xApps, IEEE Wireless Comm 2024
Lin et al., ZT-RIC: A Zero Trust RIC Framework..., CCNC 2025
Polese et al., Understanding O-RAN, COMST 2023                                ← 架構必引
```

## 7.3 C_i（基數守恆）的跨領域參照 ★ 你目前最缺

你的 C_i 在其他領域有大量同構工作。**最接近的是電表竊電偵測**——它的原理就是「分支總和必須等於幹線量測」，跟你的「各 cell 聯集必須等於登記母體」是同一個守恆式。

```
energy theft detection non-technical loss energy balance
meter data consistency feeder level balance check
conservation law based anomaly detection cyber physical
RFID missing tag detection / inventory consistency verification
Sybil attack detection identity fabrication wireless network
count-distinct integrity verification data streaming
flow conservation violation detection network traffic
safety property runtime verification monitor
```

**Sybil detection 特別重要**——你的灌水攻擊（捏造 IMSI）在文獻上就叫 Sybil attack。不引會被問。

**RFID missing-tag detection** 是虛減的同構問題：已知母體、部分讀取器回報、判斷是否有標籤消失。方法論可以直接對照。

## 7.4 S_i（跨節點共識）的跨領域參照

```
cell outage detection sleeping cell neighbour correlation        ← 最近的同場域先例
spatial correlation based outlier detection sensor network
neighbour-based anomaly detection WSN trust
analytical redundancy fault detection
co-located sensor cross-validation air quality low-cost sensor   ← 方法幾乎相同
bad data detection state estimation power system
robust consensus estimation median adversarial
spatial outlier detection geostatistics
```

**低成本空氣品質感測器網路**那一支值得看：多個鄰近感測器互相交叉驗證、用穩健統計排除單一故障或造假節點，連統計工具（median / MAD / robust z）都跟你一樣。

## 7.5 H_i（成員轉移）的跨領域參照

```
impossible travel detection identity security                    ← D2 的標準名稱！
position verification VANET plausibility check
acceptance range threshold movement plausibility VANET
sudden appearance warning misbehaviour detection VANET
GPS spoofing detection kinematic constraint
location spoofing detection mobility pattern
trajectory plausibility checking
dwell time distribution anomaly detection
handover sequence anomaly detection mobility
```

**兩個必引**：

1. **impossible travel** — 這是身分安全領域的標準術語，指「同一帳號在時間上不可能的地理移動」。你的 D2 teleport assertion 就是它。用同一個名詞可以讓審稿人立刻理解，也表示你知道這不是新發明。

2. **VANET position verification** — Leinmüller 等人的 plausibility checks（acceptance range threshold、movement plausibility、sudden appearance warning）與你的三個判準幾乎一一對應。VANET 那一支處理的正是「節點身分合法但回報位置造假」，**跟你的威脅模型完全同構，只是換了場域**。

## 7.6 融合層的參照

```
evidence fusion Dempster-Shafer intrusion detection
hierarchical rule based alert correlation
multi-sensor data fusion trust
criteria-based vs score-based access control（已有 NIST）
```

---

# 八、比較表的方向

建議在第二章末放一張**能力對照表**，格式仿 Alimohammadi 那篇的 Table I（審稿人熟悉這個格式）。

| 工作 | 參照機制 | 需訓練資料 | 攻擊幅度涵蓋 | 判定可追溯性 | 宣告盲點 | 場域基數 | 成員轉移 | Runtime |
|---|---|---|---|---|---|---|---|---|
| Alimohammadi 2024/2026 | 時間（per-UE 序列） | 是 | 階躍 AF 1.2–1.5 | 低（黑箱） | 部分（承認可能漏慢速） | ✗ | ✗ | ✓ |
| RADAR (2025) | 模型輸入淨化 | 是 | 對抗擾動 | 低 | ✗ | ✗ | ✗ | ✓ |
| ZT-RIC (2025) | 加密（機密性） | — | 不適用 | — | — | ✗ | ✗ | ✓ |
| XAI-LLM (2025) | 語意詮釋 | 是 | — | 中 | ✗ | ✗ | ✗ | ✓ |
| i-ZTA (2022) | AI 信任分數 | 是 | 概念 | 低 | ✗ | ✗ | ✗ | ✗ |
| **本研究** | **空間（跨節點同時態）+ 架構不變量** | **否** | **漸進 0.1–15%/窗** | **高（帶證據欄位）** | **✓（E3/E6/E8 已量化）** | **✓** | **✓** | **✗** |

**兩個欄位是你贏面最大的**：「需訓練資料」與「宣告盲點」。前者是方法性質差異，後者是研究誠實度——**沒有任何一篇競爭者量化了自己的盲點**，而你有 E3（守恆式繞過 0/600）、E6（脈衝逃脫 100%）、E7（配平容錯空間 0）、E8（攻擊面 96.2%）。

「Runtime」那欄你是 ✗，不要藏。表格誠實會讓其他欄位的 ✓ 更可信。

---

# 九、完整工作清單

## 第一梯：必做，決定論文能不能站住（5–6 天）

| 順序 | 工作 | 產出 | 工時 |
|---|---|---|---|
| 1 | **E9 操作區對照實驗** | 偵測率 vs 攻擊幅度雙曲線圖 | 1.5 天 |
| 2 | 第二章重寫：加入 Alimohammadi 系列 + 能力對照表 | 2.3 / 2.4 節 | 1 天 |
| 3 | E10 D1 政策消融 | trusted rate 提升 + trade-off 表 | 1 天 |
| 4 | 誤報率呈現拆解（硬否決誤觸率 / 需佐證率 / 可採信率） | 4.9.6 改寫 | 0.5 天 |
| 5 | 4.9.3 加入「中介型」第四種動作模式並比較 | 架構節 | 0.5 天 |
| 6 | 補 mitigation 政策設計節（分級 → 動作） | 新增小節 | 0.5 天 |
| 7 | 全章 RQ 與交叉引用一致性掃描 | — | 0.5 天 |

## 第二梯：顯著提升完整性（4–5 天）

| 順序 | 工作 | 工時 |
|---|---|---|
| 8 | E11 振盪政策掃描 | 1 天 |
| 9 | E12 benign evidence-loss | 1 天 |
| 10 | E13 τ_S 敏感度 + per-seed 曲線 | 0.5 天 |
| 11 | E14 信任狀態時間軸 + 復原延遲 | 1 天 |
| 12 | 補 FDIA / Sybil / VANET / cell outage 四支文獻 | 1 天 |
| 13 | 圖表修正（D1 grading、D2 分母、dwell CCDF、ROC 改 severity） | 0.5 天 |

## 第三梯：有時間再做

| 順序 | 工作 | 工時 |
|---|---|---|
| 14 | E15 H_i 基線消融 | 1 天 |
| 15 | E16 處置政策模擬 | 1 天 |
| 16 | E17 決策重放（RQ3 保護效果） | 2 天 |
| 17 | E18 合法 handover 場景（需重跑 ns-3） | 2–3 天 |

## 不建議做

- 追 500 UE 規模（模擬器限制已知，用成本模型外推即可）
- 補 D-SH seed 到 8–10（邊際效益低，時間成本高）
- 實作 runtime E2 整合（已停損，且對方已做過，重複投入不會產生差異化）

---

# 十、三句話總結

1. **這篇的出現不是壞事**——它證明了題目的重要性，而且它的攻擊模型（階躍 AF 1.2–1.5）與它自承的限制（可能漏掉慢速中毒、判定不可解釋）剛好留下了你的位置。

2. **最關鍵的單一工作是 E9**：在同一份資料上比較「你的方法 vs 時間自我參照」在階躍與慢速兩個區間的表現。這張圖把你的貢獻從「另一種偵測器」變成「涵蓋既有方法盲區的互補層」。

3. **最該改的敘事是誤報率的呈現方式**：73.9% low-trust 與對方的 0.07% FPR 不是同一個量，不拆開講就會被直接相減。
