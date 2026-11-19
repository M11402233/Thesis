#import "@preview/mitex:0.2.7": mi, mitex
= 架構與核心機制
#heading(level: 2, numbering: none)[3.1 系統架構]
見附圖：

- #strong[系統架構圖]（KPM Verification Layer 於 Near\-RT RIC 內的位置）
- #strong[架構時序圖]（#raw("01_architecture_sequence.drawio")）：真實場域狀態 → 受攻擊 O\-DU \/ 合法鄰居 O\-DU → Near\-RT RIC 內 C\-ZT 之驗證（P1 Detection → P2 Trust Assessment → P3 Policy Enforcement）→ 准入之 KPM 供 RC xApp 與可用資源評估 xApp 使用的完整訊息流（4.9）
- #strong[攻擊流程圖]（#raw("02_attack_flow.drawio")）：攻擊者取得節點控制權後，如何選擇注入點（O\-DU 為攻擊面；O\-RU\/PHY 與 UPF\/核網為範圍外）、注入攻擊型態 A–E、編碼為合法 E2SM\-KPM、上報、C\-ZT 驗證、四狀態分流（allow／restrict／defer／exclude）的完整路徑

#figure(image("/thesis_typst/figures/hackmd_S1NP2wItzx.jpg", width: 90%), caption: [論文總系統架構圖(多圖)\-System Architecture])
#heading(level: 2, numbering: none)[3.2 身分與授權前提]
取用平台既有之節點身分結果：節點身分由 IKEv2 憑證認證與 IPsec 建立（E2GAP §7.3），E2 Setup 則宣告其 RAN Function（E2GAP §5.5.2）；本前提僅檢查上報來源與已認證之節點身分及其宣告之 RAN Function ID 一致。既有機制成熟，本研究不重複造輪子，僅作前置門檻；通過後進入三類一致性驗證（3.3）。第五章之賽局另於此層加入 OAuth 2.0 之逐請求授權（#raw("R1_AUTHZ")，邏輯層模擬，5.5）；授權限制的是節點#strong[能要求什麼]，不判斷其上報之數值是否為真。

#heading(level: 2, numbering: none)[3.3 物理一致性三類驗證證據（核心貢獻，對齊實測 RLC 欄位）]
#heading(level: 3, numbering: none)[3.3.0 方法論定調：三種驗證證據，而非三個異常偵測器]
本研究不將三殘差視為三個獨立的異常偵測器，而是零信任「持續驗證」框架中，對一份 KPM 量測 的三種#strong[互補（complementary）的驗證證據]。三者取自不同觀測維度，但#strong[並非統計獨立]——皆依賴 IMSI／cell 之上報，LTE 錨點缺報會同時影響 C\_i 與 H\_i（4.4.2）。其共同邏輯是#strong[證偽（falsification）而非證明]（即 runtime verification 之監控觀點：於執行期以觀測到之軌跡檢查性質；Leucker & Schallhart, 2009；Bartocci et al., 2018）：不試圖證明 一份量測為真，而是尋找它與封閉 NPN 物理／架構約束不一致的反證；找不到反證則「尚未被否證」、 於當前窗暫可採信，任一證據找到反證即降權或拒絕。這對應零信任的核心信條——#strong[信任不是預設， 而是每個 granularity window 重新贏得、可被任一類證據推翻的暫時狀態]。

三種證據取自不同觀測維度，故單點攻擊者難以同時滿足：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 4, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([殘差], [驗證的問題], [證偽的不變量], [判定型態]),
  [#strong[C\_i] 場域守恆], [量測是否仍描述同一封閉母體？], [N\_total \= N\_known], [近確定性斷言])]
#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 4, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([#strong[S\_i] 跨節點佐證], [其他節點是否支持此節點觀測？], [delay 符合場域即時共識], [robust 統計殘差]),
  [#strong[H\_i] 成員轉移], [UE 之報表歸屬序列是否符合場域約束？], [成員轉移時空連續], [非參數檢定 \+ 確定性斷言])]
#strong[概念先例與本研究之界定]：三類證據之概念皆非本研究首創。以守恆律檢驗節點之自我回報見於偵測惡意路由器之 WATCHERS（Bradley et al., 1998），其可被繞過之性質亦已被指出（Hughes et al., 2000）；以鄰近節點之空間相關偵測持合法金鑰之內部攻擊者見於無線感測網路（Liu et al., 2007），跨 cell 之 KPI 比較亦用於 sleeping cell 偵測（Asghar et al., 2017）；以移動之物理可能性檢驗回報見於 VANET 之位置驗證（Leinmüller et al., 2006；van der Heijden et al., 2018）。本研究之貢獻因此界定為：(1) 將三者用於 O\-RAN E2 KPM 之#strong[界內]偽造，並以「受測節點無法單方面設定」為共同之設計原則；(2) 以 NPN 之已登記母體使守恆檢驗可用；(3) 以階層式融合產生四種信任狀態並接到准入政策與可用資源評估（RQ3），此為上述先例所無；(4) 量化各證據之盲點（守恆式替換、串謀節點數、D1 規模效應）。

#heading(level: 3, numbering: none)[3.3.1 觀測基礎：實測 RLC 欄位（取代 PDCP 假設）]
先前版本假設 KPM 建立於 PDCP 層四項欄位（#raw("DRB.PdcpSduVolumeDl") 等）。實測發現此假設在 MC （Multi\-Connectivity）雙連結架構下不成立——ns\-O\-RAN 的 PDCP 錨點固定聚在 LTE eNB （#raw("DlE2PdcpStats.txt") 的 CellId 全部 \= 1），無 per\-gNB 資料，S\_i／H\_i 需要的跨節點比對因而 失去意義。改用 #strong[RLC 層 trace（#raw("DlE2RlcStats.txt")）]——主檔提供 CellId 欄位（1–8），可依每個 UE 在該窗 最後一筆事件之 cell 分組，方能支撐跨節點驗證。此欄#strong[不代表各 cell 之獨立統計]：計數依 UE／LCID 累積、 delay 混合 LTE 與 mmWave 兩路（本節下文、4.6.5）；第一階段結果以此歸屬語意為條件，獨立之 per\-cell 統計屬第二階段（D\-30P）。#strong[此為本研究方法論最重要的實測修正。]

#strong[實測可得欄位]（前 11 欄；第 12 欄後有黏欄 bug，parse 時忽略）：

#block(width: 100%, fill: luma(245), inset: 6pt)[#set text(size: 8.5pt)
#raw("start, end, CellId, IMSI, RNTI, LCID, nTxPDUs, TxBytes, nRxPDUs, RxBytes, delay", block: true)]
#raw("IMSI") 對應 UE 識別（跨 cell 一致、可追蹤；其角色類比於 E2SM\-KPM UE ID 中可跨節點對應之識別，如 #raw("amf_ue_ngap_id")，此為類比，非等同）。

#strong[delay 欄之語意（v12 補充，#raw("ns3_report_semantics_audit_20261113.md")）]：ns\-3 E2 RLC 計算器自 t \= 0 起從未重置，故主檔之計數為#strong[累計值]、delay 為#strong[累計平均延遲]；cell 欄為該 (IMSI, LCID) #strong[最後一筆事件]所在之 cell。delay 之起訖點為 RLC PDU 交給 MAC 時打時間戳、至 UE 端 RLC 收到為止；重傳之 PDU 無時間戳，記為 0 但計入樣本。此量與 3GPP #raw("DRB.RlcSduDelayDl")（RLC SDU 之佇列延遲）及 OAI 之 SDU 滯留時間#strong[不是同一個量]，本文不宣稱二者同義。v12 之 S\_i 以相鄰窗累計值差分重建#strong[區間平均延遲]：#mi("\\bar d(t) = (D_t N_t - D_{t-1} N_{t-1})/(N_t - N_{t-1})")，其精度經 R\-5 精確值對帳（4.7.1）。

#strong[觀測粒度（全章一致）]：E2SM\-KPM indication 週期與分析窗均為 1 秒，二者對齊，每模擬秒 一個聚合窗。由 per\-UE 量測聚合出 cell 級觀測量（per window, per cell j）：

#block(width: 100%, fill: luma(245), inset: 6pt)[#set text(size: 8.5pt)
#raw("U_j   = | { 該 cell 該窗上報的相異 IMSI } |          （Active UEs）
DLY_j = mean_UE delay                               （cell 平均延遲；delay 欄之語意見上方說明）
TP_j  = (8/Δt) · Σ_UE ΔRxBytes                      （cell DL 吞吐量）", block: true)]
#block(width: 100%, fill: luma(240), inset: 8pt, radius: 2pt)[#set text(size: 10pt)
#strong[吞吐量前處理注意]：#raw("RxBytes")／#raw("TxBytes") 為累積 counter，非每窗流量，故 TP\_j 須以視窗差分 ΔRxBytes 計算。#raw("delay") 同樣不是每窗獨立之量測值，而是自 t \= 0 起之累計平均（見上方「delay 欄之語意」）；v12 之 S\_i 以相鄰窗累計值差分重建區間平均延遲後使用。

]
#heading(level: 3, numbering: none)[3.3.2 (A) S\_i：跨節點空間一致性殘差（延遲場域共識）]
S\_i 驗證「此節點的觀測是否被同一時刻的其他節點支持」。經對實測資料的訊號探勘，選定#strong[延遲] 為偵測維度：同窗跨 cell 之區間平均延遲變異係數中位數為 0.275（4.7.1），低於吞吐量（每窗增量之跨 cell 變異係數 0.63），但並非「極小」； 舊版以累計平均算得之 0.058 因累計平均隨時間趨於平滑而被構造性壓低，不再採用。吞吐量自然 變異大且無 PRB／CQI 硬約束（見 3.3.5），UE 數則屬 C\_i 的守備範圍。#strong[此維度選擇由資料的 經驗可觀測性決定，而非預設攻擊落於延遲。]

對受測 cell j 於窗 t：

#block(width: 100%, fill: luma(245), inset: 6pt)[#set text(size: 8.5pt)
#raw("中心   c_j(t) = median{ DLY_k(t) : k 為同窗其他活躍 mmWave cell }     （同一時刻跨節點共識）
尺度   s      = 1.4826 · MAD_global                                  （乾淨訓練資料，全域穩定）
殘差   z_j(t) = | DLY_j(t) − c_j(t) | / s
判定   S_i violated  ⟺  z_j(t) > τ_S                 （τ_S = 4；操作點之敏感度見 4.7.7）", block: true)]
- #strong[（空間性）] 中心取自同一時刻其他 cell，故 z\_j(t) 度量節點 j 對場域即時共識的偏離—— 此為跨節點空間一致性，非節點自身的時間基準。
- #strong[（尺度穩定）] 因同窗活躍 cell 數少（N ≤ 7），即時 MAD 有小樣本高變異問題， 故尺度改由乾淨資料全域估計（pooled\/shrinkage scale）。1.4826 使 MAD 成為 常態下標準差的漸近一致估計量。
- #strong[（每窗獨立）] 每窗獨立對照固定尺度與同窗中心，不累積歷史殘差。
- #strong[（S\_i unavailable）] 當受測 cell 之同窗 peer 數 \< MIN\_PEER \= 2（即同窗活躍 mmWave cell \< 3） 時，S\_i 判 #strong[unavailable → abstain，不得視為可信]。證據可用率取決於 UE 密度：D\-30（30 UE）之全部節點註記皆具備 full consensus （4.7.1）；前版之 7 UE 資料則僅 54.8% 之窗具備，unavailable 佔 29.8%（4.9.6.4）。abstain 之#strong[決策] 比例另受融合順序影響，不等於證據不可得率（4.4.0）。 此確保「證據不足」不等於「證據支持」——零信任的體現。

#strong[尚待實作]：#raw("config/topology.yaml") 鄰接矩陣（依場景座標計算）用於 S\_i 的 拓樸加權強化與 H\_i D2 的次要佐證，非 S\_i 主判據前提。

#heading(level: 3, numbering: none)[3.3.3 (B) H\_i：跨小區 UE 成員轉移一致性殘差（消失 \+ 瞬移）]
H\_i 驗證「UE 在各 cell 報表中之出現、缺席與歸屬變化是否符合封閉 NPN 的場域與架構約束」，設計上用以補 C\_i 的涵蓋邊界 （C\_i 只驗基數守恆、不驗成員組成）。經探勘確立兩個性質不同的維度：

#block(width: 100%, fill: luma(240), inset: 8pt, radius: 2pt)[#set text(size: 10pt)
#strong[術語界定（v12 修訂）]：本文之「最後事件歸屬 LTE」「消失」「成員轉移」皆指 #strong[E2 報表層級之歸屬]。主檔每個 (UE, LCID, 窗) 只有一個 cell 欄，記錄該窗#strong[最後一筆 RLC 事件]屬於哪一路；「最後事件歸屬 LTE」即該欄為 cell 1。R\-5 旁路檔顯示每個 UE 每窗都有 LTE 路徑之 PDU（MC 架構下 PDCP SDU 以機率 #raw("perPckToLTE") \= 0.5 分流至 LTE），故此狀態#strong[不代表] UE 只有 LTE 連線，亦不等於 mmWave 鏈路劣化。PHY 層交叉驗證（4.8.1）顯示此狀態與 mmWave 鏈路劣化相關，屬支持性觀察，非機制證明。D1 所量測之「停留」為#strong[連續最後事件歸屬 LTE 之窗數]。（舊版稱「LTE\-only」。）

]
#strong[D1 成員消失（非參數統計檢定）]

實測顯示 UE「最後事件歸屬 LTE」之連續窗數呈#strong[雙峰重長尾]分布，且所測之幾何分布 擬合不佳（卡方適合度 χ² ≫ 臨界值；同一 UE 之多個停留事件彼此相依，p 值僅供參考），故採不依賴該分布假設的非參數方法。對每個 UE x，由 乾淨資料建 Hampel identifier 與經驗分布：

#block(width: 100%, fill: luma(245), inset: 6pt)[#set text(size: 8.5pt)
#raw("z_d(x,t) = ( d(x,t) − median_x ) / ( 1.4826 · MAD_x )       （Hampel robust z；d = 連續 最後事件歸屬 LTE 停留窗數）
p_emp(x,t) = P( 乾淨停留(x) ≥ d(x,t) )                       （經驗 p 值，非參數）
D1 strong  ⟺ z_d ≥ τ_H^reject；D1 warning ⟺ τ_H^warn ≤ z_d < τ_H^reject   （τ_H^warn = 2、τ_H^reject = 3；p_emp 僅作解釋性佐證）", block: true)]
per\-UE 基線的必要性：UE 分「常駐 mmWave」與「結構性訊號差的 edge UE」兩群，全域單一門檻會 系統性誤判 edge UE。#strong[基線由乾淨資料一次估計、永不線上更新]——否則攻擊者可緩慢養高某 UE 停留以撐大門檻（即以自身近期觀測為參照者之同一弱點，4.7.3）。

#strong[D2 成員瞬移（情境特定之斷言）]

#block(width: 100%, fill: luma(240), inset: 8pt, radius: 2pt)[#set text(size: 10pt)
概念先例：以移動之物理可能性（最大速度、突然出現）檢驗回報，見於 VANET 之位置驗證（Leinmüller et al., 2006；van der Heijden et al., 2018）。D2 之差異在於檢驗對象為 UE 於 cell 間之成員轉移，且由 RIC 以多節點之報告交叉檢查，而非單一節點自報之位置。

]
本研究假設：於本場景之 MC 雙連結架構下，UE 換 mmWave cell #strong[須經 LTE 錨點過渡]（此假設未經合法換手檢驗，見下）。實測（D\-30 之 8 seed、240 個 UE\-run）「不經 LTE 的直接 mmWave→mmWave 跳轉」出現 #strong[0 次]（惟經 LTE 之合法換手亦未發生，4.8.4），故：

#block(width: 100%, fill: luma(245), inset: 6pt)[#set text(size: 8.5pt)
#raw("teleport(x,t) := (x 於 t−1 掛 mmWave A) ∧ (x 於 t 掛 mmWave B≠A) ∧ (中間無 最後事件歸屬 LTE 過渡窗)
D2 violated ⟺ ∃x: teleport(x,t)", block: true)]
此規則係由本 ns\-O\-RAN 場景所觀察到之移動行為導出，為#strong[情境特定之斷言（scenario\-specific assertion）]， 並非一般 O\-RAN 部署中必然成立之架構定律。其判定不依賴可調門檻；惟須注意兩點限制：（一）乾淨資料中 合法之跨 cell 換手本身從未發生，故「乾淨基線為 0」屬 vacuous，規則未經合法換手檢驗；（二）注入瞬移之 偵測屬設計必然，且該注入須同時改動多個來源之上報，檢驗的是#strong[規則之行為]，不代表單一受攻陷節點可 發動之攻擊（4.8.4）。此對應攻擊表 type C（謊報位置\/瞬移）。

#strong[（移除流量守恆）] 早期版本的 H\_i 含「跨小區流量守恆 Σ ΔU\_j ≈ 0」。因吞吐量為累積 counter 且缺 PRB 硬約束（3.3.5），此守恆在 RLC\-only 資料上無法穩健成立，故自 H\_i 移除；H\_i 聚焦 成員轉移（消失 \+ 瞬移）兩維度。

#heading(level: 3, numbering: none)[3.3.4 \\(C) C\_i：場域 UE 基數守恆驗證（已實作；於 D\-30 評估）]
C\_i 驗證「量測是否仍描述同一封閉裝置母體」。依 Lamport（1977）提出、Alpern & Schneider（1985）形式化之分類，此為 safety property，其違反可由單一窗即刻觀察，故為布林斷言而非連續分數：

#block(width: 100%, fill: luma(245), inset: 6pt)[#set text(size: 8.5pt)
#raw("N_total(t) = | ∪_all-cells { IMSI }(t) |          （全場域相異 UE 總數，含 LTE 錨點）
conserved(t) := ( N_total(t) = N_known )          （D-30：N_known = 30）
C_i violated ⟺ N_total(t) ≠ N_known", block: true)]
#strong[（布林斷言，非容忍帶）] 採嚴格相等而非 \[N\_lo, N\_hi\] 容忍帶：N\=30 時 5% 帶之下界為 28.5， 將容忍缺漏 1 個 UE（N\_total\=29 仍在帶內），使單一 UE 之虛減無法被偵測，故不設容忍帶；若需吸收重連瞬態，改採多窗持續條件（連續 2 窗 N\_total≠N\_known 才升級 rejected）。

#strong[（虛減偵測的條件性）] C\_i 對單一 O\-DU 虛減的偵測是條件性的：其前提為被刪除之 UE 未同窗 出現於其他 cell。本研究之主檔每個 UE 每窗只列於一個 cell（最後事件之 cell；此為報表結構，不是 UE 未雙掛之證據，4.6.5），於此語意下單點刪除必使 全域聯集淨減、於可攻擊之窗被 C\_i 偵測（100%）；R\-5 旁路檔顯示 UE 每窗實際上同時有 LTE 與 mmWave 兩路事件；若報表逐路列出，錨點仍 上報該 UE、C\_i 即無法察覺（此時須其他證據補，本研究未驗證）。此與守恆式串謀盲點共同構成 C\_i「必要非充分」 的能力邊界。

#heading(level: 3, numbering: none)[3.3.5 涵蓋範圍與 PRB 定位]
三殘差涵蓋基數（C\_i）、跨節點延遲一致（S\_i）、成員轉移（H\_i）。#strong[純吞吐量竄改不在涵蓋範圍]： RLC\-only 資料無 PRB\/CQI，吞吐量缺乏物理硬約束，本研究實測多種途徑均無法穩健偵測。純吞吐量 竄改若伴隨延遲異常則落入 S\_i、伴隨 UE 數異常則落入 C\_i，其未涵蓋角落限縮於「純數值、無 副作用」之攻擊；其影響不推定為低（4.5.2）。#strong[PRB 之定位（對齊 D\-30）]：RLC trace 本身不含 PRB 與 CQI，故三殘差之驗證不使用 PRB。D\-30 另開啟 ns\-O\-RAN 之 E2 NR 報表（#raw("--e2nrEnabled=true")），由 cell 2–8 之 DU 報表取得原生 #raw("RRU.PrbUsedDl")； 該量#strong[僅用於 4.12 之資源評估]（准入政策下已用 PRB 之保留比例與能見度損失），不作為驗證證據， 且其本身亦可被受攻陷之節點竄改。 CQI 仍未取得。

