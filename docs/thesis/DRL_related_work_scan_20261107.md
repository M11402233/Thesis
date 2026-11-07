# DRL／對抗賽局方向之相關研究初掃（2026-11-07）

> 方法：網路搜尋＋摘要頁（未讀全文）。**下列內容皆僅依摘要或搜尋摘錄，引用前必須讀全文核對**；標 ★ 者為須取得 PDF 的。

## A. 攻擊者與偵測者都會學習的 RL 賽局（方法本身不新）

| 文獻 | 領域 | 與本研究的關係 |
|---|---|---|
| Chen, Nguyen, Sahu, Hassanaly, "Adversarial Multi-Agent RL for Proactive False Data Injection Detection," arXiv:2411.12130（v2 2026-01） | 電網、智慧逆變器 | 對抗者 agent 產生 FDIA、防禦者 agent 偵測與定位；優於離線監督式防禦者。**與教授的 GAN 式迴圈同構** |
| Eghtesad, Vorobeychik, Laszka, "Adversarial RL for Detecting FDI Attacks in Vehicular Routing," arXiv:2603.11433（2026-03） | 交通導航 | 零和賽局、MARL 求近似 Nash；目標是把假資料造成的路由損害壓在最壞上界內。**以「後果」定義偵測目標，與教授的 impact 觀點相同** |
| Aslami et al., continual adversarial RL（CARL），arXiv:2411.10367 | 智慧逆變器 | 交替更新攻擊者／偵測者、處理遺忘 |

結論：「攻防雙方都用 RL」**不能當貢獻**，只能當評估方法，且須引用上列。

## B. O-RAN 中 KPM／KPI 被竄改

| 文獻 | 重點 | 已在論文中？ |
|---|---|---|
| Alimohammadi et al., KPI Poisoning, FNWF 2024 | LSTM 自身歷史 | 是 |
| Alimohammadi et al., Multi-Layer Defence, IEEE OJCOMS 2026 | 執行期三層防禦 | 是 |
| Aizikovich et al., Rogue Cell（APATE 攻擊、MARRS 防禦），arXiv:2505.01816 | 竄改 KPI 誤導 traffic steering；防禦含 peer 聚合嵌入 | 是 |
| ORAN-DEFEND, arXiv:2607.06647 | KPI telemetry 中的後門觸發 DRL xApp；以安全子空間淨化 | 否，**鄰近威脅**（攻擊對象是 DRL xApp 本身）。若偵測端改用 DRL，審稿人會問「你的 DRL 偵測器會不會被同樣的方式攻擊」 |
| arXiv:2405.03891（evasion attacks on DRL/GNN connection-management xApp） | 對 RSRP 加小擾動繞過學習式 xApp | 否，可作為「學習式偵測器本身可被規避」之引用 |
| arXiv:2201.06093（AML threat analysis in O-RAN） | 代理模型＋對抗輸入，含 AD xApp 與 TS xApp | 否 |

## C. 以 RL 做信任評估的零信任 O-RAN（概念不新）

| 文獻 | 重點 |
|---|---|
| Ramezanpour & Jagannath, i-ZTA, arXiv:2105.01478 | RL 信任引擎，輸入含 E2 資料；概念性，不驗證 KPM 數值（論文已引） |
| ★ "Secure and Trustworthy O-RAN Optimization: A Zero-Trust and Federated Learning Framework for 6G"（ResearchGate 392091195） | 動態信任分數＋Q-learning（依調查文獻之摘錄，未核對原文） |
| ★ "Integrating Zero Trust Architecture in O-RAN: A Comprehensive Survey and Analysis," IEEE（document 11299597） | 調查；須查是否有 RL 信任評估之整理 |
| Katsis, Karim, Bertino, "Zero-Trust Strategies for O-RAN Cellular Networks," arXiv:2511.18568 | 摘要未提 RL、未提 KPM 真實性、未提 E2／F1 上的 OAuth |
| ★ Moudoud & Cherkaoui, IEEE OJCOMS 2023（DRL IDS for 5G IoT） | DRL 偵測之 reward 設計可參考 |
| ★ Ahmad, Yau, Keoh 2020（hybrid RL trust model for 5G） | 指出惡意實體也會用 AI 規避偵測 |

## D. OAuth 與 E2（⚠ 可能與正文說法衝突）

- O-RAN ALLIANCE 部落格「Security update 2025」之 Table 1（Interface Security）的 Authorization 列，依欄位位置 E2 似對應「OAuth」，但抓取到的列只有 5 個值、對應 6 個介面，**可能錯位**。同文 Table 2 要求 API security "least privileged authorization using OAuth 2.0"。
- 正文第 609 行引 ZTA-TR §7.3.4 NOTE 3「E2 上認證即授權」。**須以 SRCS v15 原文確認 E2 是否已有 OAuth 授權要求**；若有，「E2 沒有授權」的動機要改寫，OAuth 層的定位要改成「依既有要求實作並加上 scope 與逐請求檢查」。
- ZTRAN（arXiv:2403.04113）：零信任 xApp 原型，須查其授權做法。

## E. 初步定位（待讀全文後修正）

搜尋中**未發現**同時具備以下各點的工作：
1. 威脅為通過認證、遭攻陷之 E2 節點，竄改仍在合法範圍內的 KPM；
2. 偵測依據為攻擊者無法設定的場域參照（登記母體、同窗 peer、移動規則），且參照**不交給學習**；
3. 學習型攻擊者同時對抗規則版與學習版偵測端，並以 steering 後果（誘導率、regret）評估；
4. 學習元件受規則下限約束（只能更嚴），輸出接到准入政策。

可宣稱的差異在「偵測端能從什麼學、不能學什麼」與「在自適應攻擊下的可驗證邊界」，不在賽局方法本身。
