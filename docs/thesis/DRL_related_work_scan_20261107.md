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

---

## F. 全文閱讀結果（2026-11-07，arXiv 7 篇；以 WebFetch 讀 HTML 全文，數字與引句引用前仍須對 PDF）

### F1. Chen et al., arXiv:2411.12130v2 — 對抗式 MARL 偵測 FDIA（電網）
- 威脅：攻擊者已控制**所有**逆變器的控制參數；每步至多改一個；隱匿性只是「被抓到時給負獎勵 p」，無正式約束。
- 防禦者觀測：電壓案例用**原始量測**；頻率案例用「凍結 LSTM 預測值與觀測之殘差」——參照是學出來的模型，不是場域物理參照。
- 防禦者 reward：分類對 +r、錯 −r，**沒有獨立的誤報懲罰**；只報 accuracy，**沒有 FPR、ROC、偵測延遲**。
- 訓練：獨立 PPO **同時**訓練（非交替）；防禦者可由離線監督式模型暖啟動（TF-MARL-D）。
- 結果：電壓案例平均 accuracy MARL-D 78%、TF-MARL-D 88%、Offline-D 86%；**MARL-D 對離線攻擊只有 42%**（攻擊空間覆蓋窄）。
- 作者自承：合成攻擊可逃過 MARL 防禦者；MARL 無法窮盡攻擊空間；防禦者不能變太多以免遺忘。
- **對本研究的意義**：(1) 純對抗訓練的偵測者會過度特化於自己的對手 → 我們的 DRL 偵測端必須同時用腳本式攻擊（E1–E8、漂移、階躍）與學習型攻擊訓練與測試；(2) 他們缺 FPR 與延遲，正是我們 B1–B4 基線與 E9c 可補的地方。

### F2. Eghtesad, Vorobeychik, Laszka, arXiv:2603.11433 — 對抗式 RL 偵測導航假資料
- 威脅：對每條邊觀測行車時間加非負擾動；**無硬性預算**（攻擊者因怕被抓而自我節制）；攻擊者完全可觀測環境，**觀測向量不含偵測器輸出**；一旦告警，之後擾動全部停止。
- 防禦者：PPO 學出的二元告警策略，觀測過去 5 步的（被擾動的）行車時間；**reward = −(仍在路上的車數) − C_f·誤報**，即以後果（總行車時間）定義偵測目標。
- 賽局：非嚴格零和（因誤報成本只屬防禦者）；以 **PSRO／double oracle** 求混合 Nash，最佳回應用 PPO；10 次迭代，**未報 exploitability**。
- 結果：均衡防禦者比最佳基線穩健 4%／34%／14%；均衡攻擊者比最佳攻擊基線強 19%／11%／22%。
- 限制：單一訓練 seed（未報訓練變異）；結論的總結數字與 VI-B 不一致；「偵測器能學會忽略正常壅塞」未直接驗證。
- **對本研究的意義**：(1) 「依後果定義偵測」與「攻防 RL 賽局」**兩者合在一起已有人做**（交通領域）→ 不能宣稱為新；(2) 他們的偵測器只看被竄改的資料本身，沒有攻擊者無法控制的外部參照——這正是我們的差異點；(3) 方法上 PSRO 比單純交替訓練更站得住，Phase 5 可考慮採用；(4) 我們已規定 ≥ 3 個訓練 seed，可直接補他們的弱點。

### F3. Aslami et al., arXiv:2411.10367 — CARL
- RL 產生能逃過資料驅動偵測器的 FDIA，持續加入偵測器訓練；**持續學習有災難性遺忘**，以全部情境聯合訓練解決。摘要無量化結果。
- **意義**：線上 DRL（P1）要同時面對遺忘與校準中毒（Q6）兩個風險。

### F4. Uddin, Lotfi, Seyfi, Afghah, arXiv:2607.06647 — ORAN-DEFEND
- 威脅：惡意 xApp 供應商發布有後門的 DRL policy，部署時在 KPI 串流注入觸發（降 bitrate／MCS、升 BLER）。**未說明觸發如何進入 xApp，未提被攻陷的 E2 節點**（E2 只在結論列為未來工作）。
- 防禦：以乾淨 rollout（2,048 狀態）之 SVD 估計安全子空間（d = 20），把 KPI 視窗投影回去；殘差 99 百分位為門檻。
- 結果：觸發在子空間外時，回報恢復 100%、DSR ≥ 99.5%；**觸發落在子空間內時線性殘差偵測器掉到隨機水準**；校準資料污染 10% 可使 BadRL 之緩解由 99.9% 降到 0%。
- 無自適應攻擊者。
- **意義**：(1) 與我們的 Q6／E17 校準期中毒結論一致，可互相引用；(2) 「落在正常子空間內的觸發偵測不到」= 我們「範圍內偽造」的另一種表述；(3) 我們若改用 DRL 偵測器，DRL 本身成為後門／規避的目標，必須在限制中寫明，規則下限設計正是對此的保險。

### F5. Balakrishnan et al.（Intel Labs），arXiv:2405.03891 — GNN+DRL 連線管理 xApp 之規避攻擊
- 威脅面：被攻陷的 xApp、介面上 MitM 竄改 RSRP、實體干擾；白箱 PGD 與黑箱代理模型；數位擾動上限約 6%。
- 目標：把 UE 推到少數 macro cell 造成過載（與我們「把使用者吸過來」同類後果）。
- 結果：數位攻擊使 coverage 降 48%；實體 9 dB 約 13%；對抗訓練與正則化訓練約恢復 15%。
- **意義**：學習式 RAN 控制器在 ~6% 擾動下就會被帶偏 → 支持「控制面需要先驗證輸入」的動機；也說明學習式偵測器本身同樣可被規避。

### F6. Habler et al.（BGU／Deutsche Telekom），arXiv:2201.06093 — O-RAN 對抗式 ML 威脅分析
- 以存取能力與知識分類攻擊者、六類威脅行為者；於 traffic steering 示範查詢式規避攻擊。抓取內容在結果節前截斷，結果未讀到。
- **意義**：可作為「O-RAN ML 管線本身是攻擊面」之一般引用；與 KPM 真實性驗證無直接重疊。

### F7. Katsis, Karim, Bertino, arXiv:2511.18568v2 — Zero-Trust Strategies for O-RAN（**最重要**）
- §VIII-A：明確寫到實體上未受保護的邊緣節點可產生異常 KPM telemetry 欺騙 ML 偵測器；並建議「**continuously cross-validating telemetry from multiple distributed O-RUs to detect spatial and temporal anomalies**」。Takeaway 3：ZTA 必須包含對抗訓練與 telemetry 的持續交叉驗證。
- §VIII-B：最小權限——限制應用可訂閱／控制哪些 RAN 節點（對象是 xApp，不是 E2 節點）。
- §VIII-C（引 Eiza et al.）：「A1/O2 use TLS, mTLS, and OAuth, while **E2 is mandated to use IPsec** for all listed protections」。
- 文中 RL 信任引擎只出現在對 i-ZTA 的回顧；作者本身未提出 RL 信任引擎。
- **意義**：
  1. **好消息**：一篇 Bertino 的零信任 O-RAN 綜述把「跨節點交叉驗證 telemetry」列為**建議方向而未實作**——這正是 S_i 的做法，可直接當成動機引用（「本研究實作並評估此方向」）。
  2. **風險**：審稿人可能說「跨節點交叉驗證」已被提出 → 須強調我們的貢獻是具體化（同窗中位數、凍結尺度、場域守恆、移動規則）、量化盲點與攻擊者上界、以及准入代價，而非概念本身。
  3. E2 授權：本文支持「E2 只靠 IPsec」，與正文 ZTA-TR §7.3.4 NOTE 3 一致；D 節之 O-RAN 部落格表格很可能是抓取錯位。仍以 SRCS v15 原文為準。

## G. 讀完全文後的定位修正

| 主張 | 狀態 |
|---|---|
| 攻防雙方 RL 賽局 | **已有**（F1 電網、F2 交通，F2 並以後果定義偵測）。只能當評估方法 |
| 跨節點交叉驗證 telemetry | **已被提出為方向**（F7），未見實作與量化 → 我們是實作與評估 |
| 學習式偵測器可被規避／植入後門 | **已有**（F4、F5）→ 必須寫成我們 DRL 偵測端的限制，並以規則下限緩解 |
| 偵測端參照不交給學習、場域守恆＋同窗 peer＋移動規則 | 未見 |
| 學習元件受規則下限約束、輸出接准入政策並量測可用率代價 | 未見 |
| 同時報 FPR、偵測延遲、共模擾動誤報與 steering 後果 | F1／F2 皆缺 FPR 或訓練變異，我們可補 |
