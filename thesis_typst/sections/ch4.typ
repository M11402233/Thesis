#import "@preview/mitex:0.2.7": mi, mitex
= 基於物理與架構不變量的零信任 KPM 驗證：設計與評估
#block(width: 100%, fill: luma(240), inset: 8pt, radius: 2pt)[#set text(size: 10pt)
#strong[資料集]：本章全部實驗結果（4.6–4.13）皆以主資料集 D\-30（30 UE × 8 seed × 300 窗，4.0.3）產生：主結果於 2026\-10\-13；融合順序修正後之 E11／E11b 於 2026\-11\-08；S\_i 相關者（4.7.1、4.7.4–4.7.5.4）於 2026\-11\-15 以區間平均延遲重跑。門檻於 D\-30 結果產出前凍結；惟以下各項係於看過 D\-30 結果之後所為，各自於該節標明：融合順序之修正（4.4.0（三））、E14–E18 之補充實驗、S\_i 尺度 #mi("s") 於區間輸入下之重估（門檻 τ\_S 不變）。與前版 7 UE 資料之結論差異於各節以「揭露」標示。

]
#strong[本章總覽：三類證據各需要什麼資料]

本章依序回答「以什麼資料、檢查什麼、結果如何」。三類一致性證據皆由#strong[同一份逐窗上報]計算，所需之資料如下；資料集之細節見 4.0。

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 4, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([證據], [逐窗所需之上報資料], [所需之參照（非受測節點所能單方設定）], [不需要]),
  [#strong[C\_i] 母體守恆], [全部 cell（含 LTE 錨點）當窗上報之 UE 識別（IMSI）集合], [已登記之 UE 母體數 N\_known（啟動時載入之唯讀組態）], [訓練資料、門檻],
  [#strong[S\_i] 同窗共識], [各 mmWave cell 當窗之區間平均延遲（由當窗與前一窗之累計延遲與 PDU 數差分重建，4.7.1）], [同窗其他活躍 cell 之延遲中位數（每窗即時計算，至少 2 個 peer）；由乾淨資料估計後凍結之尺度 #mi("s")], [以節點自身之歷史為參照（差分重建僅以前一窗之累計值作換算）],
  [#strong[H\_i] 成員轉移], [相鄰窗之間每個 UE 出現於哪些 cell 之報表（含 LTE 錨點）], [D2：由本場景移動行為導出之轉移規則；D1：由乾淨資料估計後凍結之逐 UE 停留基線], [延遲、吞吐量])]
三者共用之欄位為（窗時間、IMSI、CellId、延遲；區間延遲之重建另需 nRxPDUs），取自各 cell 之 RLC 統計；#strong[皆不使用吞吐量與 PRB]。原生 PRB（E2 NR 報表之 #raw("RRU.PrbUsedDl")）僅用於 4.12 之資源評估。上述參照中，需要乾淨資料者為 S\_i 之尺度與 H\_i\-D1 之停留基線（clean bootstrap 假設，4.9.4）；C\_i 與 H\_i\-D2 不需要。

章節安排：4.0–4.3 為資料集與前處理；4.4 為信任狀態與融合規則；4.5 為攻擊模型；4.6–4.8 為三類證據之個別評估；4.9 為 C\-ZT 架構、運算開銷與融合後之決策分布；4.10–4.11 為對抗性分析與規則回放；4.12 為資源—政策評估；4.13 為總結。

#strong[符號與參數]：S\_i 操作門檻 τ\_S \= 4；H\_i\-D1 門檻 τ\_H^warn \= 2、τ\_H^reject \= 3；C\_i 持續窗門檻 L\_C \= 2；S\_i 最少 peer 數 MIN\_PEER \= 2。信任狀態 #mi("D_i(t) \\in") {trusted, low\-trust, rejected, abstain} 之定義與判定規則見 #strong[4.4.0]，由階層式規則產生，並非由連續信任分數決定。S\_i 與 H\_i\-D1 均採 robust z 統計量，但門檻各自校準，不共用數值。

#strong[本章與 C\-ZT 架構、研究問題之對應]：本研究提出之 C\-ZT 由四個職責分離之 xApp 組成（目標部署架構見 4.9；本原型以離線 trace 回放、同一行程內之邏輯模組實作）：Detection、Trust Assessment、Policy Enforcement 三者依序構成驗證與准入之管線（程序 P1–P3），可用資源評估 xApp（Available\-resource evaluation xApp）則於每窗 P3 發布後評估准入政策下之可用資源。簡報所稱 Population／Peer／Mobility Check 分別即本章之 C\_i／S\_i／H\_i。

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 4, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([模組（程序）], [職責], [對應節], [研究問題]),
  [#strong[Detection xApp]（P1）], [對齊上報；計算 C\_i、S\_i、H\_i 三類一致性證據，並記錄各證據之適用對象與可得性], [4.3、4.6–4.8、4.10], [RQ1],
  [#strong[Trust Assessment xApp]（P2）], [依階層式規則將證據合成信任狀態，並記錄觸發規則與證據], [4.4、4.9.6、4.11], [RQ2],
  [#strong[Policy Enforcement xApp]（P3）], [依信任狀態對合作消費端之 KPM 輸入執行 allow／restrict／exclude／defer], [4.9.3], [RQ2],
  [#strong[Available\-resource evaluation xApp]（可用資源評估；於每窗 P3 發布後執行）], [於每窗 P3 發布後，經 Resource Termination 自共享資料層（DB）讀取 policy\-admitted KPM 與 PRB 用量，回報准入輸入可用率與 PRB 能見度損失；不做驗證、不改變信任狀態], [4.9.2、4.12], [RQ3])]
#heading(level: 2, numbering: none)[4.0 資料集與威脅注入方法論]
#heading(level: 3, numbering: none)[4.0.1 為何獨立說明：乾淨基線與攻擊注入之分離]
本章所有偵測結果之可信度，取決於一個可被檢驗之前提：#strong[乾淨基線與攻擊樣本之界線明確，且注入邏輯獨立於偵測邏輯。] 若攻擊資料係「為被偵測而構造」，高偵測率即淪為循環論證。本節說明三件事：

+ 乾淨基線全部來自 ns\-3 封包級模擬之輸出，未經任何人工修改；原始檔唯讀，並以 sha256 記錄（4.0.3）。
+ 所有攻擊樣本均為於乾淨 trace #strong[副本]上之#strong[離線後處理注入]；一般腳本注入之程式不讀取偵測器之門檻、參數或標籤；白箱規避測試（4.7.8、4.10）與規則行為測試（如 E16 以正常上界倍數定義之注入）則依門檻構造，其攻擊者可知資訊於各節列明，且不作為注入與偵測獨立之證據（4.0.4）。
+ 每種攻擊之注入位置、幅度與對應之偵測依據逐一列明（4.0.4）。

乾淨資料#strong[不含任何攻擊]，為 3.5 GHz 非公眾網路於正常運作下之模擬遙測。攻擊並非另外模擬之異常資料，而是事後於乾淨 trace 之可控欄位上施加之修改，用以模擬受攻陷 O\-DU 於 KPM 組裝點之輸出（4.1；其與 runtime 竄改之等價性未以 E2 hook 驗證，4.0.6）。故偵測率反映「偵測器能否分辨乾淨與被竄改」，而非「模擬器能否產生必然被偵測之資料」。

#heading(level: 3, numbering: none)[4.0.2 底層模擬與資料型別]
底層模擬為 ns\-O\-RAN 之 #raw("scratch/scenario-three.cc")（#raw("configuration=1")：3.5 GHz、20 MHz、isd \= 1,000 m、單天線；平台與參數見 4.2.1–4.2.2）。場景含 1 個 LTE eNB（cell 1，錨點）與 7 個 gNB（cell 2–8）之 MC 雙連結拓樸、30 個 UE；模擬器以封包層級計算 SINR、雙連結之服務 cell 切換與封包延遲，並以 1 秒為觀測窗輸出統計。

#strong[主要 KPM 來源]為 RLC 層統計（#raw("DlE2RlcStats.txt")），經前處理（4.3）解析為每窗、每 cell、每 UE 之觀測量：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 4, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([欄位], [型別], [語意], [使用者]),
  [start／end], [float], [觀測窗起訖（秒）], [全部（窗對齊）],
  [CellId], [int], [節點識別（cell 1 \= LTE 錨點）], [C\_i、H\_i],
  [IMSI], [int], [UE 識別], [C\_i、H\_i],
  [delay], [float], [自 t \= 0 起之#strong[累計平均] RLC PDU 延遲（檔案單位為秒，前處理轉為毫秒；語意見 3.3.1）。v12 之 S\_i 改用相鄰窗差分重建之區間平均（4.7.1）], [#strong[S\_i]],
  [RxBytes／TxBytes], [int], [自 t \= 0 起之累計位元組量（須差分；前處理見 4.3.2）], [未用於殘差（吞吐量竄改未涵蓋，4.5.2）])]
#strong[輔助資料]（同一模擬之其他輸出，用於資源評估與交叉驗證）：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 3, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([檔案], [語意], [使用者]),
  [#raw("du-cell-2…8.txt")（E2 NR 報表）], [E2SM\-KPM DU 報表，含逐 UE 之 #raw("RRU.PrbUsedDl")], [RQ3 之原生 PRB（4.12）],
  [#raw("RxPacketTrace.txt")], [每個傳輸區塊之 cell、排程符號數、TB 大小、MCS、SINR], [原生 PRB 之交叉驗證、E9d])]
#block(width: 100%, fill: luma(240), inset: 8pt, radius: 2pt)[#set text(size: 10pt)
#strong[組態命名註]：#raw("configuration=1") 下實體載波為 sub\-6 GHz；ns\-O\-RAN 將節點命名為「mmWave gNB」，係沿用其 MC 雙連結架構之命名。S\_i 建立於 delay 之跨節點一致性，與載波頻段無關，此命名不影響方法有效性。RLC 統計不含 PRB 與 CQI；PRB 改由 E2 NR 報表取得（4.12.1），CQI 未取得。

]
#heading(level: 3, numbering: none)[4.0.3 乾淨資料集 D\-30]
第四章全部實驗使用#strong[單一資料集 D\-30]：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 2, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([項目], [設定]),
  [規模], [30 UE（#raw("--totalUes=30")）× 8 seed（RngRun 4200–4207）],
  [時長], [每 seed 模擬 301 秒，分析取 0–299 共 300 窗；全資料 2,400 窗],
  [收集腳本], [#raw("scripts/collect_ues30.sh")（逐 seed 輸出至 #raw("data/ues30_seeds/")）],
  [其餘參數], [#raw("indicationPeriodicity=1.0")、#raw("minSpeed=3")／#raw("maxSpeed=10")（m\/s）、#raw("heuristicType=-1")、#raw("--e2nrEnabled=true")（4.2.2）],
  [分析檔], [#raw("prepare_d30.py") 自原始檔截取 0–299 窗至 #raw("data/ues30_seeds/analysis/")，並記錄原始檔與分析檔之 sha256],
  [收集時之完成檢查], [每窗 N\_total \= 30、IMSI 1–30 齊全、0–299 窗無缺])]
#strong[為何以單一資料集]：前版以兩批資料分別評估 C\_i（D\-C：10 seed × 60 s）與其餘檢查（D\-SH：4 seed × 300 s），兩者 UE 數皆為 7。改為單一資料集後，C\_i、S\_i、H\_i、融合與資源評估皆於同一組軌跡上評估，結論可直接對照。代價為 C\_i 之 seed 數由 10 降為 8；窗數則由 600 增為 2,400。前版資料集保留唯讀，僅供附錄對照。

#strong[規模之選擇]：UE 數取 30，與比較文獻常用之 10 之倍數規模一致。35 UE 之試跑推估單一 seed 之記憶體需求約 20 GB，超出實驗機器可平行執行之範圍，故未採用；每個 seed 之模擬約需 36–41 小時。

#strong[校準]：正式收集前以 5 秒模擬驗證四點（#raw("data/ues30_seeds/calibration_20261006/")）：（1）同一 seed 兩次執行之輸出逐位相同，僅實際時間戳欄不同；（2）每窗 N\_total \= 30；（3）新增之 #raw("--totalUes") 參數於原參數下不改變任何輸出；（4）原生 PRB 與排程符號數之換算相符。開啟 E2 NR 報表之副作用見 4.2.3。

#strong[乾淨基線之性質]：收集腳本對每個 seed 檢查每窗 N\_total \= 30。8 個 seed 皆通過：各 300 窗、無缺窗、IMSI 30 個、每窗 N\_total \= 30（#raw("prepare_d30.py")）；原生 PRB 與 #raw("RxPacketTrace") 排程符號數之交叉驗證 8 個 seed 皆通過（各 2,100 筆 (cell, 窗)，最大差 0.149 PRB，容許 0.5）。乾淨資料上之基線：C\_i 反例 0／2,400 窗（4.6.2）；跨 mmWave cell 之轉移 0（240 個 UE\-run 之 serving mmWave cell 皆未改變，4.8.4）；全部 15,534 筆 (節點, 窗) 皆具備 full consensus（4.7.1）。

#strong[參數凍結]：所有門檻與政策沿用於 7 UE 資料上定案之值，於 D\-30 之結果產出前凍結，D\-30 未用於選擇任何門檻（#raw("docs/thesis/D30_parameter_freeze.md")）。惟融合順序之事後修正與區間輸入下尺度 #mi("s") 之重估係於 D\-30 上進行（見本章開頭之說明）。

#heading(level: 3, numbering: none)[4.0.4 攻擊樣本：注入方法與獨立性]
所有攻擊樣本由#strong[離線注入函式]於乾淨 trace 之副本上產生，修改 KPM 之可控欄位（IMSI 集合、CellId 與 IMSI 之對應、delay），用以模擬受攻陷 O\-DU 之輸出。注入原則：

+ #strong[乾淨 trace 永不修改]：原始 RLC 統計為唯一真值來源，所有注入於其副本上進行。
+ #strong[一般腳本注入為獨立程式]：注入程式不讀取偵測器之門檻或內部狀態。例外為刻意依門檻構造之測試——白箱貼門檻規避（4.7.8 Q4）、串謀 m\-sweep（4.10）、以正常上界倍數定義之 D1 注入（E16）——其攻擊者可知資訊於各節列明；這些測試不作為注入與偵測獨立之證據。
+ #strong[偵測器不知情]：偵測器以同一介面、同一組凍結門檻處理乾淨與注入樣本，不接收任何標籤。

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 5, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([攻擊型態], [注入操作（於乾淨 trace 副本上）], [竄改欄位], [對應之偵測依據], [腳本]),
  [A 灌水（\+k）], [加入 k 個未登記 IMSI], [IMSI 集合], [C\_i：N\_total 淨增], [#raw("run_Ci_unified.py")],
  [A 虛減（−k）], [刪除 k 個真實 IMSI], [IMSI 集合], [C\_i：N\_total 淨減], [#raw("run_Ci_unified.py")],
  [E3 守恆式替換], [同窗 \+k 假、−k 真], [IMSI 集合], [C\_i 之盲點（刻意保留，4.6.6）], [#raw("run_Ci_unified.py")],
  [B1 階躍], [受測 cell 之 delay 乘以放大因子], [delay], [S\_i：偏離同窗共識], [#raw("run_E9_rt.py")],
  [D 漸進漂移], [受測 cell 之 delay 每#strong[實際秒]遞增 r × 平均值], [delay], [S\_i：對同窗共識累積偏離], [#raw("run_E9_rt.py")、#raw("run_slow_poisoning_rt.py")],
  [C 瞬移], [竄改 IMSI 與 CellId 之對應，使 UE 不經錨點跨 mmWave cell], [CellId], [H\_i\-D2：無合法過渡], [#raw("run_Hi_experiments.py")],
  [超時消失], [使 UE 自 mmWave cell 消失並滯留錨點], [CellId], [H\_i\-D1：停留超出基線], [#raw("run_E10_D1_policy_ablation.py")],
  [延遲壓低（RQ3）], [受控節點壓低自身回報延遲以吸引流量], [delay], [融合後之准入（4.12）], [#raw("run_RQ3_decision_replay.py")])]
注入之獨立性可由程式結構檢驗：S\_i 之共識中心取自受測節點以外之 cell，偵測器不讀取任何注入標記，只能經由殘差判定。

#strong[注入不偏袒偵測器之證據]：E3 守恆式替換#strong[刻意構造為 C\_i 無法偵測]（N\_total 不變）。若注入係為「保證被偵測」而設計，即不會包含此函式並如實呈現 C\_i 未偵測之結果。E3 之存在為注入邏輯不服務於偵測率之一項佐證，惟不足以證明其餘注入皆無偏袒——注入與偵測程式出自同一作者，其獨立性僅及於一般腳本注入之程式結構（不共享門檻、參數與標籤）。此盲點說明 C\_i 須由其他證據補足（4.6.6）。

#heading(level: 3, numbering: none)[4.0.5 Seeds 明細與可追溯性]
#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 5, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([seed], [時長], [用途], [攻擊注入], [統計單位]),
  [4200–4207], [300 窗], [全部殘差、融合、xApp、對抗性分析、規則回放、RQ3], [依 4.0.4；S\_i 類注入於各 (seed, cell) 序列中點], [seed（cluster）])]
#strong[攻擊實例規模]：S\_i 類注入之樣本單位為 (seed, cell)，同一 seed 內之 cell 共用軌跡與共識參照，非獨立樣本，不確定性以 seed 為 cluster 呈現（S\_i 類之表列 seed 間範圍，未計算信賴區間；D1 之表列跨 seed 之 95% 信賴區間半寬）。D\-30 之 (seed, cell) 樣本數為 56（8 seed × 7 cell；共模實驗 E9c 為 54、慢性中毒題組之準則 2c 為 55，因可評估窗不足而少計）；H\_i\-D2 瞬移注入 239 例；D1 超時消失注入每個強度 233 例；C\_i 逐窗注入視實驗為 800–2,400 窗（4.6）。

#strong[LOSO 無洩漏聲明]：S\_i 之全域尺度 s 與 H\_i 之 per\-UE 基線，於每個 LOSO fold 僅由訓練 seed 估計，held\-out seed 不參與。門檻（τ\_S 等）於前版資料上選定、於 D\-30 結果產出前凍結，未以 D\-30 調整（4.0.3）。

#strong[per\-UE 基線之身分對齊限制]：H\_i 之 per\-UE 基線跨 seed 以 IMSI 編號彙整，然不同 seed 之同號 IMSI 對應不同初始位置與軌跡之 UE；LOSO 下 held\-out seed 之 UE 個體無自身歷史可循，此為架構固有限制（4.8.7）。

#heading(level: 3, numbering: none)[4.0.6 E2 runtime 整合之嘗試與限制]
#strong[資料取得路徑之界定]：本研究之資料#strong[並非經由 E2 介面即時上報、於 near\-RT RIC 落地]，而是由 ns\-O\-RAN 之離線檔案記錄機制（#raw("enableE2FileLogging=true")，原始碼註解明載為「產生離線檔案記錄，而非連接 RIC」）直接輸出之統計檔。數值仍由完整之封包級模擬產生，但驗證層並未實際消費 E2SM\-KPM indication 訊息。

#strong[整合嘗試與受阻點]：本研究曾嘗試以 FlexRIC 作為 near\-RT RIC 建立 E2AP／E2SM runtime 連線。#strong[E2 Setup 已成功]：FlexRIC 於本機迴路（127.0.0.1:36421）收到 E2 節點之 E2 SETUP REQUEST，並接受其宣告之 RAN Function。其後於 RIC Indication 之產生路徑上，依序排除兩專案因獨立版本演進所致之相容性落差，包括：E2AP 訊息型別不相容導致之 RIC 端斷言失敗、ASN.1 標頭安裝路徑缺漏、e2sim 函式庫 callback 註冊 API 之簽名變更（#raw("register_callback") → #raw("register_sm_callback")）、核心裝置類別缺少之存取方法，以及 ns\-3 屬性系統中多項 E2 屬性未於配對版本註冊。最終阻滯於 #strong[RIC Indication Header 之 ASN.1 PER 編碼階段]（#raw("ric-KPM-Node-List")），錯誤發生於編碼函式庫內部，其排除需深入第三方 codec，超出本研究時程之可控範圍，遂停損。

#strong[對本研究之影響]：驗證邏輯之輸入改由離線 trace 提供（4.9.1 之 #raw("IndicationSource") 抽象層），攻擊注入改採於模擬輸出上之等價後處理。兩條路徑承載之數值出自同一封包級模擬，#strong[未經驗證者包含傳輸路徑，以及驗證邏輯於真實 E2 訊息上之行為]（真實 E2 之欄位語意可能與本文 trace 不同，見下方 OAI 之補充檢查）；端到端 E2 訊息處理延遲、runtime 注入 hook 與實際 RIC 決策之影響，均因此無法量測，列為後續工作。

#strong[OAI 之補充檢查（v12）]：另以 OpenAirInterface（rfsim）＋ FlexRIC 進行兩項檢查（#raw("multisim_OAI_check_20261113.md")、#raw("E28_L2a_result_20261115.md")）。L1 只支持「E2SM\-KPM 傳輸可行」；L2a（1 CU、2 DU、1 UE、3 次 F1 換手）只支持「C\_i 所需之資訊（各 DU 之 UE 成員、跨 DU 之 UE 身分）可由未修改之 OAI E2 介面取得」。兩者皆#strong[不驗證 C\_i、S\_i 或 H\_i 本身]，OAI 之延遲欄位與本文 delay 之起訖點亦不同，故不作為交叉驗證。L2a 另觀察到：DU 無 UE 時不送報告（應視為未知，不得視為 0 個 UE）；UE 重新進入曾服務之 DU 時，第一筆吞吐量增量為 uint32 差分下溢之異常值。

#heading(level: 2, numbering: none)[4.1 攻擊架構與注入點定位]
本研究之威脅為一個#strong[身分合法、但資料造假]的內部 O\-DU 節點。攻擊者不破壞 E2 介面之 IPsec、不偽造 E2AP 格式、不碰無線層——竄改發生於#strong[量測收集完成後、E2SM\-KPM indication 編碼前]的資料組裝環節，使上報之數值或 IMSI 偏離物理真實。此威脅已由 O\-RAN WG11 點名為 Key Issue \#14「Malicious E2 Node」：惡意行為者可濫用已正確完成認證之被攻陷 E2 節點，送出變造與誤導性資料（xApp\-TR §5.15）。E2 路徑上之傳輸與身分保護（IPsec ESP 與 IKEv2 憑證認證；E2GAP §7.3）對此無效，現行之單值範圍檢查（SRCS SEC\-CTL\-NEAR\-RT\-17）亦無法偵測落在合法範圍內之偽造值，此即需要跨來源一致性驗證之根本原因（呼應第一章）。

#strong[注入點排除說明]：

- #strong[O\-RU／PHY 無線層]：研究範圍外。本研究驗證 E2 量測資料之可信度，而非真實無線訊號。
- #strong[UPF／核網（N3\/N6）]：研究範圍外。UPF 非 E2 節點、不參與 E2SM\-KPM 通訊。
- #strong[O\-DU（E2 節點）KPM 組裝點]：#strong[本研究攻擊面]。ns\-O\-RAN 單體 gNB 架構下 CU\/DU 未實際物理切分，攻擊點準確描述為「E2 節點內、量測聚合完成至 E2SM\-KPM indication 編碼之間」之資料層。

#block(width: 100%, fill: luma(240), inset: 8pt, radius: 2pt)[#set text(size: 10pt)
威脅模型之#strong[概念注入點]位於 O\-DU KPM 組裝點；#strong[本章實驗以離線後處理修改該點可控欄位、等價模擬其輸出效果，尚未完成 runtime E2SM\-KPM indication hook]（見 4.0.6）。本章所有攻擊實驗均屬此離線注入層級。

]
#strong[完整攻擊流程]：

#block(width: 100%, fill: luma(245), inset: 6pt)[#set text(size: 8.5pt)
#raw("攻擊者取得邊緣節點控制權
  → 通過 IKEv2／IPsec 節點認證，並完成 E2 Setup（宣告 RAN function；E2AP 格式完好）
  → 選擇竄改注入點：O-DU KPM 組裝點（本研究攻擊面）
  → 注入攻擊型態（見 4.5.1）
  → 編碼為合法 E2SM-KPM indication（格式合規、身分合法、數值落於合法範圍）
  → 週期上報 Near-RT RIC
  → ① Detection xApp：計算三類一致性證據（C_i／S_i／H_i）
  → ② Trust Assessment xApp：階層式融合 → trusted / low-trust / rejected / abstain
  → ③ Policy Enforcement xApp：allow / restrict / exclude / defer → policy-admitted KPM
  → 合作之消費端（RC xApp）僅取用 policy-admitted KPM", block: true)]
#figure(image("/thesis_typst/figures/hackmd_HJZ2XzboGx.png", width: 90%), caption: [System Architecture1005 (1)])
#heading(level: 2, numbering: none)[4.2 工具鏈、資料集與實驗方法]
#heading(level: 3, numbering: none)[4.2.1 平台與場景]
#strong[平台]：ns\-O\-RAN（ns\-3.38，#raw("wineslab/ns-o-ran-ns3-mmwave") commit 8c42089d；mmWave module \+ #raw("oran-interface") E2 termination）。場景建立 #strong[7 個 gNB \+ 1 個 LTE eNB] 之 MC 雙連結拓樸，提供跨節點空間驗證所需之多 cell 觀測。ns\-O\-RAN 具備 E2 termination 能力（RAN Function ID 2，ORAN\-E2SM\-KPM），惟#strong[本研究之資料收集採其離線檔案記錄模式（#raw("enableE2FileLogging=true")），未經由 Near\-RT RIC 之 E2 indication 路徑]；E2 runtime 整合之嘗試與受阻點見 4.0.6。

#strong[場景]：#raw("scratch/scenario-three.cc")，#raw("configuration=1")（3.5 GHz／20 MHz／isd \= 1000 m／單天線）。本研究對場景程式僅作一項修改：新增 #raw("--totalUes") 參數，以指定 UE 總數（原程式之 UE 數只能為 #raw("ues") × 7）；參數為 0 時維持原行為。修改後之執行檔於原參數下之全部輸出與修改前逐位相同（校準紀錄，見 4.0.3）。UE 初始位置為以場域中心為圓心之均勻圓盤分布，不逐基地台分配，故 UE 總數不必為 7 之倍數。本場景之 NPN 屬性（固定且已登記之裝置母體、涵蓋全場域之可信錨點）為本研究之情境假設，模擬器本身不含 NPN 特有之機制（第二章「為何限定於非公眾網路」）。

#block(width: 100%, fill: luma(240), inset: 8pt, radius: 2pt)[#set text(size: 10pt)
#strong[註]：ns\-O\-RAN 將節點命名為「mmWave gNB」，係沿用其 MC 雙連結架構之命名慣例；於 #raw("configuration=1") 下實體載波為 sub\-6 GHz。S\_i 建立於 delay 之跨節點一致性，與載波頻段無關，此命名不影響方法有效性。

]
#heading(level: 3, numbering: none)[4.2.2 觀測粒度]
記錄週期與分析窗均為 #strong[1 秒]（#raw("indicationPeriodicity=1.0")），二者對齊，每模擬秒產生一個聚合窗。全章所有「窗」均指此 1 秒聚合窗。

#strong[定案參數]（主資料集 D\-30）：

#block(width: 100%, fill: luma(245), inset: 6pt)[#set text(size: 8.5pt)
#raw("CONFIG=1          # 3.5 GHz / 20 MHz / isd=1000m
TOTAL_UES=30      # --totalUes=30，N_known = 30
SIMTIME=301       # 分析取 0–299 共 300 窗（見 4.2.3）
PERIOD=1.0        # 1 秒觀測窗
MINSPEED=3
MAXSPEED=10
HEURISTIC=-1      # 不啟用節能 heuristic
E2NR=true         # --e2nrEnabled=true：cell 2–8 輸出 E2SM-KPM DU 報表（含 RRU.PrbUsedDl）
SEEDS=4200–4207   # RngRun，8 個獨立 seed", block: true, lang: "bash")]
#heading(level: 3, numbering: none)[4.2.3 資料集與 E2 NR 報表之技術細節]
資料集 D\-30 之規模、收集、校準與參數凍結見 #strong[4.0.3]。以下為分析時須知之技術細節：

- #strong[分析窗]：開啟 E2 NR 報表時，模擬結束之最後一窗不輸出 RLC 統計，故模擬 301 秒、分析取 0–299 窗；分析檔由 #raw("prepare_d30.py") 截取，並內建缺窗、N\_total 與 aux 一致性檢查。
- #strong[E2 NR 報表之副作用]（校準實測）：RLC 統計與 PHY trace 於開啟前後之共同窗逐位相同；PDCP 統計改為每次報表後歸零。本研究之分析不使用 PDCP 統計。
- #strong[確定性]：同一台機器上，同一 seed 重跑之輸出逐位相同（實際時間戳欄除外）。

#heading(level: 2, numbering: none)[4.3 資料前處理]
#heading(level: 3, numbering: none)[4.3.1 資料源與欄位]
資料源為 #strong[RLC 層 trace（#raw("DlE2RlcStats.txt")）]（非原先假設之 PDCP 層——PDCP 錨點在 MC 架構下全聚於 LTE eNB，無 per\-gNB 資料，無法支撐跨節點比對）。可用欄位（前 11 欄）：

#block(width: 100%, fill: luma(245), inset: 6pt)[#set text(size: 8.5pt)
#raw("start, end, CellId, IMSI, RNTI, LCID, nTxPDUs, TxBytes, nRxPDUs, RxBytes, delay", block: true)]
RLC trace #strong[不含 PRB 使用率與 CQI]。D\-30 另開啟 ns\-O\-RAN 之 E2 NR 報表（#raw("--e2nrEnabled=true")），由 cell 2–8 之 DU 報表取得原生 #raw("RRU.PrbUsedDl")（定義與性質見 4.12.1）；#raw("RRU.PrbUsedDl") 之原始定義見 3GPP TS 28.552 V20.4.0 §5.1.1.2.5（Mean DL PRB used for data traffic：量測期間 T 內下行資料傳輸所用 PRB 數之算術平均，為單一整數），E2SM\-KPM 本身並未列舉 #raw("RRU.PrbUsedDl")。CQI 仍未取得。

#heading(level: 3, numbering: none)[4.3.2 吞吐量的差分前處理]
#raw("RxBytes")／#raw("TxBytes") 為累積 counter，非每窗區間流量，故 cell 級吞吐量須先做視窗差分：

#mi("ΔRxBytes(u,t) = RxBytes(u,t) − RxBytes(u,t−1)") #mi("TP_j(t) = (8/Δt) · Σ_{u ∈ cell j} ΔRxBytes(u,t)")

第一窗、缺窗、cell change 或 counter reset 造成之不可比差分標為 missing、不納入計算。#strong[delay 亦非每窗獨立之量測值]，而是累計平均（3.3.1）；S\_i 所用之區間平均延遲另以差分重建（4.7.1）。

#heading(level: 3, numbering: none)[4.3.3 場域基數必含 LTE 錨點]
C\_i 之全域聯集#strong[必須包含 LTE 錨點 cell（CellId\=1）]：含 LTE 時 N\_total(t) 於 D\-30 乾淨資料之每窗皆等於已知母體數；若只計 mmWave，N\_total 會因 UE 正常回落 LTE 而浮動（非攻擊訊號）。

#heading(level: 2, numbering: none)[4.4 驗證哲學與階層式證據融合]
#heading(level: 3, numbering: none)[4.4.0 信任狀態之定義與判定規則]
#heading(level: 4, numbering: none)[（一）信任狀態之語意]
本研究之驗證層對每一個 (節點, 觀測窗) 產出一個信任狀態 #mi("D_i(t) \\in \\{\\text{trusted},\\ \\text{low-trust},\\ \\text{rejected},\\ \\text{abstain}\\}")。四者之語意、對應之 Policy Enforcement 動作，以及#strong[明確排除之誤解]定義如下：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 4, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([狀態], [語意], [Policy Enforcement 動作（4.9.3）], [明確不代表]),
  [#strong[trusted]], [本窗未觀察到任何反例，且驗證所需證據充足], [#strong[allow]：納入 policy\-admitted KPM], [不代表該量測已被證明為真；僅代表未發現反例（4.4.1）],
  [#strong[low\-trust]], [存在至少一項需交叉佐證之證據，未達可直接採信之標準], [#strong[restrict]：依准入政策限制其使用——附註記後納入，或自決策輸入排除（本章評估之兩種設定見 4.12.3）], [#strong[不代表該量測為偽造]；不應解讀為誤報率],
  [#strong[rejected]], [存在確定性違反，或多項統計證據指向同一對象], [#strong[exclude]：該筆量測不進入 policy\-admitted KPM；寫入 execution record], [#strong[不代表該節點被判定為攻擊者]；拒絕對象為該筆 KPM，非該節點之身分],
  [#strong[abstain]], [驗證所需證據不可得，無法作成判定], [#strong[defer]：當窗不進入 policy\-admitted KPM；fallback 政策另行定義，且不使該筆量測回到 admitted view（4.9.3）], [#strong[不代表可信]；證據不足永遠不等於證據支持])]
#strong[嚴重度序]：#mi("\\text{trusted} \\prec \\text{abstain} \\prec \\text{low-trust} \\prec \\text{rejected}")。此序用於同窗多項證據並存時之彙總，以及跨節點之窗層級呈現。

#strong[不繼承原則]：信任狀態並非節點之屬性，而是每個觀測窗針對每個 (節點, 窗) 重新產生之驗證狀態。前一窗之 trusted 不對後一窗構成任何預設；前一窗之 rejected 亦不使該節點於後續窗永久失信。過去狀態僅在明文定義之多窗持續性規則中作為證據（見下表 #raw("R1_CI_VETO") 之持續窗條件）。由此導出之狀態轉移與恢復條件見（四）。

#heading(level: 4, numbering: none)[（二）階層式融合規則]
三項殘差之性質互異——#mi("C_i") 為近確定性斷言、#mi("H_i")\-D2 為情境特定之規則斷言（二者皆不依賴可調門檻），#mi("S_i") 與 #mi("H_i")\-D1 為統計殘差。若以加權分數融合，確定性之違反將被正常之統計讀數稀釋（論證見 4.4.3）。故採#strong[階層式規則融合]，依 NIST SP 800\-207 §3.3.1 之分類屬 criteria\-based 信任演算法。

#strong[判定輸入]：本窗之證據組 #mi("E_i(t) = \\langle\\, C_i,\\ r_C,\\ S_i,\\ \\text{D2},\\ \\text{D1},\\ \\text{ev}_{\\text{D1}},\\ j \\,\\rangle")，其中 #mi("r_C") 為 #mi("C_i") 連續違反窗數，#mi("\\text{ev}_{\\text{D1}}") 為 D1 證據之歸屬節點——於定案之 uebound 政策下為觸發該證據之 UE #strong[消失前之 serving mmWave cell]；於 window 對照政策下為該 UE 當窗掛載之 cell 集合（4.9.6.5），#mi("j") 為受測節點。

#strong[判定對象之範圍]：信任狀態僅對當窗有上報之 mmWave 節點產生。LTE 錨點（CellId 1）為驗證用之輔助輸入（#mi("C_i") 之聯集、#mi("H_i") 之過渡判定），不在本次准入政策之作用範圍內。當窗無任何活躍 mmWave 節點時，該窗之處理狀態記為 #raw("n/a")（reason \= #raw("no_active_mmwave_node")），不產生節點信任註記、准入動作或准入量測；#raw("n/a") 為窗之處理狀態，#strong[不是第五種信任狀態]。

#strong[規則表]（評估全部規則，由#strong[嚴重度最高之符合規則]決定；同嚴重度時依層級 L1 ≺ L2 ≺ L3、再依表內順序決定 #raw("rule_id")；其餘符合之規則記入 #raw("also_matched")。此為#strong[事後修正]，第四章原採「第一條符合即決定」，見（三））：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 4, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([層], [代碼], [條件], [狀態]),
  [L1], [#raw("R1_AUTHZ")], [token 無效、過期或 scope 不符（OAuth 2.0 邏輯層授權；第五章新增，第四章之實驗未啟用，原型 #raw("fuse()") 尚未實作；5.5）], [#strong[rejected]],
  [L1], [#raw("R1_CI_VETO")], [#mi("C_i") violated 且 #mi("r_C \\geq L_C")], [#strong[rejected]],
  [L1], [#raw("R1_CI_PENDING")], [#mi("C_i") violated 且 #mi("r_C < L_C")], [#strong[low\-trust]],
  [L1], [#raw("R1_D2_VETO")], [#mi("H_i")\-D2 violated（觀測層級瞬移斷言）], [#strong[rejected]],
  [L1], [#raw("R1_STAGE1")], [身分前提不成立（節點身分認證由 RIC 平台以 IKEv2／IPsec 完成，E2 Setup 僅宣告 RAN function；本層僅取用其結果；原型 #raw("fuse()") 未實作，身分前提於重放層恆成立）], [#strong[rejected]],
  [L2], [#raw("R2_SI_D1_BOUND")], [#mi("S_i") violated 且 D1 \= strong 且 #mi("j \\in \\text{ev}_{\\text{D1}}.\\text{cells}")], [#strong[rejected]],
  [L2], [#raw("R2_SI_D1_UNBOUND")], [#mi("S_i") violated 且 D1 \= strong 但 #mi("j \\notin \\text{ev}_{\\text{D1}}.\\text{cells}")], [#strong[low\-trust]],
  [L2], [#raw("R2_SI_ALONE")], [#mi("S_i") violated，D1 無 strong 證據], [#strong[low\-trust]],
  [L2], [#raw("R2_D1_STRONG")], [D1 \= strong（#mi("z_d \\geq \\tau_H^{\\text{reject}}")）且歸屬於節點 #mi("j")，#mi("S_i") 未違反], [#strong[low\-trust]],
  [L2], [#raw("R2_D1_WEAK")], [D1 \= warning（#mi("\\tau_H^{\\text{warn}} \\leq z_d < \\tau_H^{\\text{reject}}")）且歸屬於節點 #mi("j")], [#strong[low\-trust]],
  [L3], [#raw("R3_ABSTAIN")], [#mi("S_i") unavailable（同窗 peer 數 \< MIN\_PEER）、LTE 錨點 KPM 遺失、或窗無法對齊], [#strong[abstain]],
  [L0], [#raw("R0_CLEAN")], [以上皆不成立], [#strong[trusted]])]
#heading(level: 4, numbering: none)[（三）三項設計約束之說明]
#strong[約束一：硬違反優先，且不被統計證據稀釋。] L1 之 rejected 規則成立時，判定即為 rejected（嚴重度已為最高），L2 與 L3 不能使其減輕；#raw("R1_CI_PENDING")（low\-trust）則不再阻擋同窗之 rejected 證據（見本節末之事後修正）。#mi("C_i") 違反但持續窗數未達 #mi("L_C") 者降為 low\-trust 而非 trusted——#strong[違反之觀察與拒絕之執行為不同層級]，前者為 property 判定，後者為 enforcement 決策（4.6.1）。

#strong[約束二：單一統計證據不構成硬否決；交叉佐證須指向同一對象。] #mi("S_i") 或 #mi("H_i")\-D1 單獨違反僅得 low\-trust。二者同窗並存時，#strong[須進一步檢查兩項證據是否指向同一節點]方可升級為 rejected（#raw("R2_SI_D1_BOUND")）；若指向不同對象（#raw("R2_SI_D1_UNBOUND")），則視為兩個無關告警同時出現，不構成互相印證。

此綁定要求源自實作稽核（4.9.6）。#mi("H_i")\-D1 依定義量測 UE 之 最後事件歸屬 LTE 停留窗數，觸發 D1 之 UE 必然掛載於 LTE 錨點。#strong[若以「當窗掛載之 cell」為歸屬依據（window 對照政策），D1 證據與 #mi("S_i") 受測之 mmWave 節點在結構上不相交，#raw("R2_SI_D1_BOUND") 不存在合法觸發路徑。] 定案之 uebound 政策改以「該 UE 消失前之 serving mmWave cell」為歸屬依據，使此規則首次具有合法觸發路徑；其於 D\-30 乾淨資料上之觸發為 159 筆（前版 7 UE 資料為 6 筆），均為誤拒事件（4.9.6.5）。

#strong[約束三：證據不可得永不等同於證據支持（fail\-closed）。] L3 成立時，該筆量測判為 abstain，且於任何准入政策下皆不准入（P3 之證據可得性閘，4.9.3；v12.3），避免攻擊者藉由壓制鄰居節點上報、或利用離峰空窗使 #mi("S_i") 無法取得比對對象而「預設通過」。

嚴重度序之一項後果：low\-trust 之嚴重度高於 abstain，故當同窗另有 #mi("H_i")\-D1 證據時判為 low\-trust，該窗雖屬 #mi("S_i") 證據不可得，卻不呈現為 abstain。#strong[因此 abstain 之決策比例並非證據不可得率]，二者須分別陳述（實測見 4.9.6.4）。其理由為：abstain 較 low\-trust 為輕，當已有其他證據足以降級時採較嚴之標籤。惟標籤較嚴不等於准入較嚴：#raw("restrict_annotated") 准入 low\-trust，故若只依標籤准入，「S\_i 不可得＋D1 weak／strong」之量測會被附註記准入（外部審稿以函式反例指出）。故 v12.3 於 P3 加入#strong[證據可得性閘]：只要該筆之 S\_i 證據不可得（#raw("R3_ABSTAIN") 為最終或同時符合之規則），任何准入政策皆不准入；判定標籤不變（4.9.3）。

#strong[融合順序之事後修正（已修正，2026\-11\-08）]：第四章原採「依序評估，第一條符合者即決定」。#raw("R1_CI_PENDING")（low\-trust）排在 #raw("R1_D2_VETO") 與 #raw("R2_SI_D1_BOUND")（皆為 rejected）之前，故當同窗 #mi("C_i") 首次違反（#mi("r_C < L_C")），而 #mi("H_i")\-D2 亦違反、或同節點之交叉佐證成立時，本應產出之 rejected 被遮蔽為 low\-trust。本研究依事先寫定之規格（#raw("docs/thesis/fusion_severity_order_spec.md")）改為上表之嚴重度序，並以四項檢查決定是否採用（腳本 #raw("run_fusion_order_check.sh")、#raw("compare_fusion_order.py")、#raw("test_fusion_order.py")）：（C1）原順序重跑之 16 個輸出與既有結果逐位相同；（C2）乾淨 D\-30 之 15,534 筆註記逐筆不變（乾淨資料之 #mi("C_i") 違反為 0），#raw("R2_SI_D1_BOUND") 仍為 159 筆；（C3）窮舉單元測試：所有不同之組合皆為預期組合，且皆更嚴；（C4）全部注入實驗重跑：僅 E11 與 E11b 改變，共 222 個 (節點, 窗) 由 #raw("R1_CI_PENDING")（low\-trust）改為 #raw("R2_SI_D1_BOUND")（rejected）——E11 26 個（受測 13、其他節點 13）、E11b 196 個（#mi("L_C") \= 2、3 各 98）；#raw("R1_D2_VETO") 之組合未出現；其餘實驗（E10、E12、E14–E16、E18、RQ3、規則回放、#mi("C_i") 統一版、可用資源評估等）逐位相同。四項皆通過，故採用嚴重度序，本章受影響之數字（下文 E11、4.6.7 之 E11b）已依新輸出更新。#strong[此修正揭露原順序之實際後果]：E11 中上述 26 筆於原順序下為「乾淨回放為 rejected、注入 #mi("C_i") 偽造後被首次違反窗降為 low\-trust」——攻擊者可藉 #mi("C_i") 之首次違反減輕原本會被拒絕之報告。揭露：本修正為事後修正；E11 之獨立核對實作原以原順序推得決策，C4 執行時停於該檢查，經使用者同意後同步改為嚴重度序（#raw("run_E11_transitions.py") 標註〔事後修正 2026\-11\-08，使用者同意〕）；程式預設仍為原順序以重現既有回歸基準，主結果以 #raw("ZT_FUSION_ORDER=severity") 產生；嚴重度序之運算開銷未於閒置機器重新量測（4.9.5 之數字為原順序）。

#heading(level: 4, numbering: none)[（四）狀態轉移與恢復條件]
因採不繼承原則，狀態之進入與離開均由當窗證據決定。由（二）之規則表可直接導出各狀態之離開條件：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 3, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([進入之規則], [進入條件], [離開條件（次窗重新判定）]),
  [#raw("R1_CI_PENDING") → #raw("R1_CI_VETO")], [#mi("N_{\\text{total}} \\neq N_{\\text{known}}")；連續達 #mi("L_C") 窗時升級為 rejected], [首個 #mi("N_{\\text{total}} = N_{\\text{known}}") 之窗，#mi("r_C") 歸零],
  [#raw("R1_D2_VETO")], [當窗出現瞬移事件], [瞬移為單窗事件；次窗若無新事件即離開],
  [#raw("R2_SI_ALONE")], [#mi("z_j > \\tau_S")], [首個 #mi("z_j \\leq \\tau_S") 之 full\-consensus 窗],
  [#raw("R2_D1_STRONG")／#raw("R2_D1_WEAK")], [歸屬於節點 #mi("j") 之 UE 其 #mi("z_d \\geq \\tau_H")], [該 UE 之連續 最後事件歸屬 LTE 停留結束（回到 mmWave，或因缺報而中斷計數；#mi("d") 歸零）],
  [#raw("R3_ABSTAIN")], [證據不可得], [證據恢復可得])]
此表為規則之邏輯後果，非實測結果。其兩項意涵須明言：

+ #strong[不永久繼承前窗信任狀態]：信任狀態不跨窗沿用，觸發條件消失後，該節點之判定即依當窗證據重新產生，系統不保留「曾被拒絕」之狀態。惟部分證據本身使用歷史資訊——#mi("C_i") 之連續違反計數 #mi("r_C")、D1 之連續 最後事件歸屬 LTE 停留窗數、D2 之前窗關聯——故離開時點取決於這些證據何時歸零，未必為觸發條件消失之次窗（實測見下文 E11）。此與「拒絕對象為該筆量測而非節點」一致，但亦意謂間歇性攻擊者於每次停手後即可恢復。
+ #strong[持續性升級僅有一條]：唯一之持續性升級為 #mi("C_i") 之 #mi("L_C")。#mi("S_i") 之持續違反恆為 low\-trust（#raw("R2_SI_ALONE")）。統計證據升級為 rejected 之唯一路徑為同窗之交叉佐證（#raw("R2_SI_D1_BOUND")），且僅於 uebound 政策下可觸發（約束二）；window 政策下統計證據不存在升級為 rejected 之路徑。其下游後果見 4.12.5（三）。

RQ2 所問之轉移延遲與恢復延遲之實測見下文 E11，重複短違反之效果見 4.6.7 之 E11b；統計證據之持續性升級規則（候選 #raw("R2_SI_PERSIST")）之評估見下文 E12；該候選規則#strong[不列入]（二）之規範性規則表。

#strong[E11：轉移與恢復之實測]（規格 #raw("docs/thesis/E11_E12_B4_spec.md") v2；腳本 #raw("run_E11_transitions.py")；驗證層級：離線注入與規則回放，D\-30 8 seed）

#block(width: 100%, fill: luma(240), inset: 8pt, radius: 2pt)[#set text(size: 10pt)
#strong[v12 註]：E11、E11b 與 E12 未於第一階段重跑，為累計平均輸入之歷史版本結果。

]
#strong[設計]：每個 seed × 受測 mmWave cell（共 56 組）× 六類攻擊 × 攻擊長度 T ∈ {10, 30} 秒，於 #mi("[t_0, t_0+T)") 注入（#mi("t_0") 為受測 cell full\-consensus 序列中點之窗），攻擊結束後追蹤 60 秒；每個情境皆與同 seed 之乾淨回放逐窗配對，只計攻擊造成之差異。#mi("C_i") 灌水／虛減與 #mi("S_i") 漂移（1 %\/秒）／階躍（×1.5）僅改動受測節點自身之報告；D1 超時消失須改動受信任之 LTE 錨點報告，D2 偽造關聯須同時改動兩個 mmWave 節點之報告，二者皆為#strong[規則回放]，不宣稱符合單點 O\-DU 攻陷模型。

#strong[可追溯性]：以獨立實作（不呼叫 xApp 之判定與融合函式）由注入後之報告重算 P1 證據，並依（二）之規則表推得決策；1,319,703 筆註記與 xApp 回放逐筆相同（嚴重度序下，獨立實作同步改為嚴重度序，筆數與逐筆一致性不變）。乾淨回放合計為 7,810／7,565／0／159（trusted／low\-trust／abstain／rejected），並與 4.9.5 之 runtime 註記逐筆相同。

#strong[規格修訂之揭露]：本實驗首版（v1）之檢查要求攻擊只觸發自身類別之規則，首次執行有 21 個情境不符。檢視後發現同一份上報會影響多個殘差，故改為可追溯性檢查；並發現 D1 於 UE 缺報時凍結停留計數，使缺報前後兩段停留被接成一段，與 4.8.3「連續 最後事件歸屬 LTE 停留窗數」之定義不符，遂改為缺報中斷計數（4.8.3）。此修訂於前版資料上進行，v1 之規格、程式與完整診斷保存於 #raw("data/results/E11_v1_diagnosis/")；D\-30 之全部結果皆以修訂後之定義產生。

#strong[結果]（受測節點；延遲單位為秒，中位數〔範圍〕；「受測 (節點, 窗) 變化」為攻擊期間與追蹤期內與乾淨對照不同之受測節點註記數）：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 7, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([攻擊], [T], [引發轉移], [離開 trusted], [到達 rejected], [回到乾淨對照（自攻擊結束起）], [受測 (節點, 窗) 變化：降級（新增非 trusted 或加重）／判定減輕／同狀態改規則／節點消失]),
  [#mi("C_i") 灌水], [10], [56／56], [0〔0–8〕], [56／56，1], [0〔0–0〕], [495／0／37／0],
  [#mi("C_i") 灌水], [30], [56／56], [0〔0–8〕], [56／56，1], [0〔0–0〕], [1,484／0／68／0],
  [#mi("C_i") 虛減], [10], [55／56], [0〔0–9〕], [46／55，1], [0〔0–0〕], [277／0／42／58],
  [#mi("C_i") 虛減], [30], [55／56], [0〔0–9〕], [48／55，1], [0〔0–0〕], [809／0／97／171],
  [#mi("S_i") 漂移 1 %\/秒], [10], [1／56], [5〔5–5〕], [1／1，5], [0〔0–0〕], [1／0／0／0],
  [#mi("S_i") 漂移 1 %\/秒], [30], [38／56], [23〔5–29〕], [22／38，20], [0〔0–0〕], [173／0／12／0],
  [#mi("S_i") 階躍 ×1.5], [10], [55／56], [0〔0–1〕], [39／55，1], [0〔0–0〕], [474／0／45／0],
  [#mi("S_i") 階躍 ×1.5], [30], [55／56], [0〔0–1〕], [47／55，2], [0〔0–0〕], [1,410／0／120／0],
  [D1 超時（規則回放）], [10], [54／56], [2〔0–7〕], [2／54，5.5], [0〔0–3〕], [220／1／34／58],
  [D1 超時（規則回放）], [30], [56／56], [2〔0–30〕], [5／56，14], [0〔0–2〕], [690／1／100／171],
  [D2 偽造關聯（規則回放）], [10], [49／56], [0〔0–10〕], [39／49，0], [1〔0–23〕], [61／61／4／58],
  [D2 偽造關聯（規則回放）], [30], [51／56], [0〔0–30〕], [42／51，0], [1〔0–7〕], [68／123／6／171])]
（表由 #raw("make_table_E11.py") 自 #raw("data/results/d30_fusion_order/severity/E11_transitions.json") 產生。與 v7 相比：#mi("C_i") 類之「判定減輕」因嚴重度序而歸零（原為 2／7／1／3）；另 v7 之表有 4 格與腳本輸出不符（#mi("C_i") 虛減之同狀態改規則、D2 之降級），為抄錄錯誤，已依腳本輸出更正。）

#strong[發現]（本次 E11 之資料與注入設定下）：

+ #strong[引發轉移之情境於追蹤期內皆回到乾淨對照]：#mi("C_i") 與 #mi("S_i") 類於攻擊結束當窗即回到乾淨對照；D1 類為 0〔0–3〕秒；D2 類為 1〔0–23〕秒（T \= 10）與 1〔0–7〕秒（T \= 30）。
+ #strong[「引發轉移」不等於偵測成功]：受測節點亦出現判定減輕（轉成 trusted，或非 trusted 間減輕），D2 類合計 184 筆、D1 類 2 筆、#mi("C_i") 與 #mi("S_i") 類 0 筆（#mi("C_i") 類於原順序下為 13 筆，皆為（三）所述之遮蔽，嚴重度序下歸零）。D2 回放將 UE 移離受測節點，連帶移除該 UE 原本綁於此節點之 D1 證據，故出現減輕。
+ #strong[慢速漂移於 10 秒內幾乎不引發轉移]：1 %\/秒、T \= 10 之 56 個情境中僅 1 個引發轉移；T \= 30 時為 38／56，離開 trusted 之中位數為 23 秒。此與 4.7.8 之 Q2（1 %\/秒時偵測秒數中位數 28.5 秒）一致。
+ #strong[統計證據於 D\-30 經常升級為 rejected，其路徑為與 D1 之重合]：#mi("S_i") 階躍 ×1.5 到達 rejected 者為 39／55 與 47／55，#mi("S_i") 漂移（T \= 30）為 22／38；D1 超時回放為 2／54 與 5／56。此等升級皆經 #raw("R2_SI_D1_BOUND")——D\-30 有 48.3% 之節點註記綁有 D1 證據（4.9.6.5），故 #mi("S_i") 違反持續數窗時，恰與同節點之 D1 證據同窗之機率甚高。#strong[此升級並非由持續性規則所致]（規則中 #mi("S_i") 無持續性升級），而是交叉佐證於高 UE 密度下之附帶結果（4.9.6.6）；前版之 7 UE 資料上同一攻擊到達 rejected 者僅 4／16 與 6／16。
+ #strong[#mi("C_i") 虛減大多升級]：到達 rejected 者為 46／55 與 48／55。未升級者係被刪除之 UE 於部分窗自然切至 LTE、該窗無可刪除之報告，連續違反計數因而中斷；另有 1 個情境未引發轉移。
+ #strong[全場域斷言之影響範圍]：#mi("C_i") 與 D2 為全場域判定，違反時同窗所有有上報之 mmWave 節點同受影響。以 #mi("C_i") 灌水 T \= 30 為例，56 個情境合計，其他節點之 (節點, 窗) 中有 4,357 個由准入轉為不准入（新增非 trusted），另有 3,911 個於非 trusted 間加重。此為跨情境累計之 (節點, 窗) 比對次數，非獨立事件數，亦非乾淨誤報率。

#strong[E12：統計證據之持續性升級（候選規則，未採用）]（規格 #raw("docs/thesis/E11_E12_B4_spec.md")；腳本 #raw("run_E12_persist.py")；驗證層級：離線合成注入，D\-30 8 seed）

#strong[問題]：現行規則中 #mi("S_i") 之持續違反恆為 low\-trust。若新增候選規則「#mi("S_i") 於同一節點連續違反 #mi("L_S") 個實際秒即升級為 rejected」（#raw("R2_SI_PERSIST")），誤拒與偵測如何取捨？#mi("L_S = \\infty") 即現行規則。三項內建檢查（#mi("L_S = \\infty") 之註記等於 runtime 註記；連續計數之兩份實作逐筆相同，15,534 筆；#mi("L_S = \\infty") 之 RQ3 指標與 4.12 逐位相同）皆通過。

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 6, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([#mi("L_S")], [乾淨資料新增誤拒（分母 15,534）], [漂移 1 %\/秒：到達 rejected／中位延遲（秒）], [階躍 ×1.3], [階躍 ×1.5], [#raw("C_notrej") 誘導率：×0.6／漂移 1%／漂移 2%]),
  [∞（現行）], [0], [52／56，32], [44／56，5], [54／56，4], [58.9%／59.1%／57.2%],
  [2], [81（0.52%）], [56／56，29], [46／56，1], [56／56，1], [8.6%／17.2%／9.3%],
  [3], [39（0.25%）], [56／56，30], [46／56，2], [56／56，2], [10.8%／18.4%／10.4%],
  [5], [7（0.05%）], [55／56，32], [45／56，4], [55／56，4], [14.3%／20.5%／12.6%],
  [10], [0], [55／56，32], [45／56，5], [55／56，4], [20.2%／24.9%／17.3%])]
#strong[發現]：(1) 持續性升級可使「僅排除 rejected」之消費端（#raw("C_notrej")）獲得實質保護——#mi("L_S = 2") 時 ×0.6 階躍之誘導率由 58.9% 降至 8.6%，決策可用率維持 100%——代價為乾淨資料新增 81 筆誤拒（0.52%），其中 64 筆位於序列前半段；#mi("L_S = 10") 時無新增誤拒，誘導率仍降至 17.3%–24.9%。(2) 對 ×0.8 階躍幾無作用（誘導率 94.1%–94.3%，各 #mi("L_S") 皆然）：該幅度下 #mi("S_i") 本身即很少違反。(3) 新增誤拒於 seed 間不均（#mi("L_S = 2") 時 seed 4202 為 21 筆、seed 4201 為 0 筆）。#strong[本研究未採用此候選規則]：其操作點（#mi("L_S")）須另行選定，而 D\-30 依凍結聲明不用於選擇參數；列為未來工作。

#heading(level: 4, numbering: none)[（五）本節與實作之關係]
上表為#strong[規範性定義]。驗證元件於實作中設置規則稽核儀器，逐筆記錄觸發規則代碼、各殘差原始判定與證據綁定對象，使實際判定可與本表直接對帳；稽核結果、前版實作與本表不符之處及修正後之決策分布見 4.9.6。門檻參數之取值與校準方式分別見 4.6.1、4.7.2、4.8.3；本節僅定義規則結構。

#strong[動作層之界定]：信任狀態由 Policy Enforcement xApp 轉為對合作消費端 KPM 輸入之准入動作（allow／restrict／exclude／defer），而非以攔截 E2 資料流實現——驗證元件無權阻斷其他 xApp 之訂閱。各動作之精確語意與動作模式之比較見 4.9.3。

#heading(level: 3, numbering: none)[4.4.1 從認證到持續驗證]
Near\-RT RIC 現況隱含「認證即可信」之假設：E2 上認證即授權，SCTP 無原生授權方法（SRCS SEC\-CTL\-NEAR\-RT\-2 NOTE；ZTA\-TR §7.3.4 NOTE 3），O\-RAN 零信任研究亦將經 E2 傳送之資料判定為無缺口（ZTA\-TR §7.3.4）。NIST SP 800\-207 則明言，不應因主體通過基本認證即假設其後續請求同樣有效；O\-RAN WG11 之研究報告亦指出，即使 E2 被視為具備機密性、完整性與雙向認證，RIC 仍不應假設收到之資料有效且可信（xApp\-TR §6.17）。

傳統：  measurement → authenticated? → trust 本研究：measurement → authenticated? → VERIFY → trust decision

信任不是預設，而是#strong[每個 granularity window 重新產生之驗證狀態]。本研究借用「#strong[未發現反例不等於證明為真]」之共同判斷原則（統計證偽、runtime verification 與零信任共有），不宣稱四者具完全相同之認識論骨架。

#heading(level: 3, numbering: none)[4.4.2 三種驗證證據]
#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 4, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([殘差], [驗證的問題], [證偽的不變量], [判定型態]),
  [#strong[C\_i] 場域守恆], [量測是否仍描述同一封閉母體？], [N\_total \= N\_known], [近確定性斷言],
  [#strong[S\_i] 跨節點佐證], [其他節點是否支持此節點觀測？], [delay 符合場域即時共識], [robust 統計殘差],
  [#strong[H\_i] 成員轉移], [UE 之報表歸屬序列是否符合場域約束？], [成員轉移時空連續], [非參數檢定 \+ 確定性斷言])]
三者取自不同觀測維度（空間聚合／空間並置／時間連續），#strong[互補但非統計獨立]（皆依賴 IMSI\/cell 上報，LTE 錨點缺報會同時影響 C\_i 與 H\_i）。其防禦價值在於：攻擊者要同時不被三者否證，需讓偽造資料同時滿足多種不同約束——此僅就竄改幅度超出各證據偵測邊界之攻擊而言，不構成完整性保證：幅度落在邊界以內之竄改，單一節點即可同時通過三者（4.10.4）。

此跨來源佐證之原則並非全新範式：3GPP 於假基站偵測中已載明，多個 UE 之量測報告可用於過濾單一惡意 UE 之錯誤報告（TS 33.501 Annex E §E.2）。本研究將其移植至 E2 介面與內部威脅方向。

#heading(level: 3, numbering: none)[4.4.3 融合結構之設計理由：為何不採線性加權]
#block(width: 100%, fill: luma(240), inset: 8pt, radius: 2pt)[#set text(size: 10pt)
本節說明 4.4.0 規則結構之設計理由；規則本身見 4.4.0。

]
#heading(level: 4, numbering: none)[（一）加權平均會使確定性證據被稀釋]
三項殘差之性質並不對等。#mi("C_i") 為布林斷言（Alpern & Schneider 意義下之 safety property）；#mi("H_i")\-D2 為由本場景移動行為導出之情境特定斷言（觀測層級）；#mi("S_i") 與 #mi("H_i")\-D1 則為統計殘差，其輸出為連續偏離量。

若以線性加權合成單一信任分數，某窗之 #mi("C_i") 確定違反（分數為 0）而 #mi("S_i") 與 #mi("H_i") 均正常（分數接近 1）時，合成分數仍可能落於可信區——#strong[以最弱之證據稀釋最強之證據]。

此問題不能以調整權重解決。提高 #mi("C_i") 之權重至足以單獨主導判定時，該權重在數學上已等價於一條硬否決規則，惟表達較不明確、門檻與權重之交互作用難以稽核。#strong[既然目標行為是一票否決，直接表達為規則較表達為權重更誠實且可驗證。]

#heading(level: 4, numbering: none)[（二）此選擇對應 criteria\-based 信任演算法]
NIST SP 800\-207 將信任演算法區分為 criteria\-based（一組合格條件全數滿足方予放行）與 score\-based（加權信賴分數比門檻）。本研究屬前者。以 KPM 為輸入之零信任框架多採 score\-based 設計——例如 i\-ZTA 之信任評估引擎輸出 0 至 1 之連續信賴度量（Ramezanpour & Jagannath, 2022）。該架構以 E2 KPM 與 O1 KPI 作為信任評估與網路安全狀態分析之輸入，但未驗證 KPM 數值本身是否為真，亦未討論身分合法而遭攻陷之 E2 節點偽造資料之情形；其持續多因子認證檢查的是元件身分與軟體完整性，而非數值內容。就該文所述之設計而言，未見對 KPM 數值真實性之檢查。（該文為概念性架構，未含實作與量化評估。）該設計適用於證據性質同質之情形；當證據中同時包含確定性斷言與統計殘差時，分數化會抹除二者在認識論上之差異。

#heading(level: 4, numbering: none)[（三）三項行為承諾]
+ #strong[硬違反優先]：確定性證據一旦成立即直接產出判定。
+ #strong[單一統計證據不冒進]：#mi("S_i") 或 #mi("H_i")\-D1 單獨違反僅得 low\-trust，其必要性由 4.8.6 之 edge UE 誤報率支持。
+ #strong[fail\-closed]：證據不可得不得視為證據支持，且於任何准入政策下皆不准入（v12.3 起由 P3 之證據可得性閘保證，4.9.3）。

前兩項於 4.11 之規則回放中檢驗；fail\-closed（#raw("R3_ABSTAIN")）於 D\-30 無對應之窗，4.11 未涵蓋，其規則層級之行為見 4.4.0（三）C3 之窮舉單元測試。

#heading(level: 4, numbering: none)[（四）拒絕採信，而非容錯聚合]
拜占庭容錯框架之目標為在部分節點惡意之情形下#strong[仍產出可用之聚合結果]；零信任之目標為#strong[在採信前逐份驗證，證據不足時拒絕採信]。前者以可用性為優先並容忍受污染輸入，後者以正確性為優先並接受可用資料量之減少。本研究採後者，其代價（可直接採信之比例下降、可用資源減少）於 4.9.6 與 4.12 揭露。

#heading(level: 2, numbering: none)[4.5 攻擊模型與涵蓋範圍]
#heading(level: 3, numbering: none)[4.5.1 涵蓋的攻擊型態]
#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 4, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([類別], [注入方式], [竄改欄位], [對應殘差]),
  [#strong[A. 竄改 UE 數量]], [捏造／刪除 IMSI], [IMSI 集合], [C\_i；H\_i 佐證],
  [#strong[B1. 延遲竄改]], [竄改 per\-cell delay，含階躍放大（E9）], [delay], [S\_i],
  [#strong[C. 謊報位置／瞬移]], [錯誤 CellId↔IMSI], [成員位置], [H\_i\-D2],
  [#strong[D. 連續值緩慢漂移]], [B1 偏移隨時間遞增], [delay], [S\_i])]
（D 限定為連續值漂移，對應 S\_i；離散之基數投毒另屬 A／C\_i，不併入 D。）

#heading(level: 3, numbering: none)[4.5.2 範圍界定：主動聲明不涵蓋]
#strong[（B2）純吞吐量竄改]：RLC\-only 資料不含 PRB\/CQI\/MCS，吞吐量缺乏可獨立佐證之物理約束。本研究實測四種途徑（固定場域帶、同窗跨 cell z\-score、混合空間殘差、RLC bytes\/PDU 內部一致性）均無法在可接受誤報率下穩定偵測；吞吐量與延遲之離散度差異見 4.7.1。B2 是#strong[未涵蓋但可能具實際影響]之攻擊類別——負載平衡、流量導向與 admission 可能直接依賴吞吐量，故#strong[不推定其影響較低]。若消費端之目標函數依賴此類未被驗證之量，本研究之驗證層無法對該決策提供保護（見 4.12.6）。

#strong[（E）模仿時序]：針對時序偵測器統計特性設計，本研究未建立專屬殘差，列未來工作。

#heading(level: 2, numbering: none)[4.6 C\_i：場域基數守恆驗證]
#heading(level: 3, numbering: none)[4.6.1 形式定位與定案參數]
依 Alpern & Schneider，場域基數守恆屬 #strong[safety property]：違反可由單一窗即刻觀察，故為布林斷言。

#block(width: 100%, fill: luma(245), inset: 6pt)[#set text(size: 8.5pt)
#raw("N_total(t) = | ∪_all-cells { IMSI }(t) |          （含 LTE 錨點）
conserved(t) := ( N_total(t) = N_known )          （D-30：N_known = 30）
C_i violated ⟺ N_total(t) ≠ N_known", block: true)]
#strong[布林斷言，非容忍帶]：5% 容忍帶於 N \= 30 時下界為 28.5，將容忍缺漏 1 個 UE（N\_total \= 29 仍在帶內），使單一 UE 之虛減無法被偵測，故採嚴格相等；重連瞬態以持續窗條件吸收（連續 L\_C 窗違反方升級 rejected）。

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 3, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([參數], [值], [理由]),
  [#raw("N_known")], [#strong[30]（#raw("--totalUes=30")）], [與比較文獻之 10 之倍數規模一致；35 UE 之記憶體需求超出實驗機器之平行執行範圍（4.0.3）。此為場域規模之實驗限制，其對運算開銷之意涵見 4.9.5],
  [判定], [嚴格相等], [safety property，零閾值布林斷言],
  [L\_C], [2], [吸收斷線重連瞬態（代價見 4.6.7）])]
#block(width: 100%, fill: luma(240), inset: 8pt, radius: 2pt)[#set text(size: 10pt)
#strong[範式說明]：C\_i 不採 ROC\/AUC\/閾值掃描（布林斷言無閾值可調），改採#strong[證偽測試]——於多條獨立軌跡上尋找 conserved(t) \= False 之正常窗格。

#strong[違反觀察與執行決策之區分]：單窗 N\_total ≠ N\_known 即構成 #emph[invariant violation observed]；是否升級為 rejected 由 L\_C 政策決定（4.4.0 #raw("R1_CI_VETO")／#raw("R1_CI_PENDING")）。

]
#heading(level: 3, numbering: none)[4.6.2 E0：不變量成立性之證偽測試]
#strong[設定]：D\-30 資料集，8 個獨立 seed，各 300 窗，共 2,400 窗。逐窗計算含 LTE 錨點之全 cell 相異 IMSI 聯集；判定一律經 xApp 之 #raw("verify_ci")／#raw("fuse")（#raw("run_Ci_unified.py")，規格 #raw("Ci_unified_spec.md")）。

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 2, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([統計量], [值]),
  [總窗數], [2,400],
  [N\_total 分布], [全部 \= 30],
  [反例數（違反觀察）], [#strong[0]],
  [乾淨資料 rejected], [#strong[0]])]
#strong[論述]：N\_total 於 2,400 窗、8 種獨立隨機性下未觀察到任何反例。此為#strong[本 ns\-O\-RAN MC 組態與觀測條件下之架構不變量，而非一般封閉 NPN 中無條件成立之物理定律]——真實 NPN 仍可能因 UE 關機、睡眠、暫時 detach、KPM 遺失、解碼失敗、窗未對齊、UE 重連換 ID、維護期裝置增減而破壞此恆定（見 4.6.9）。結果為確定性，不宣稱統計顯著性。

#block(width: 100%, fill: luma(240), inset: 8pt, radius: 2pt)[#set text(size: 10pt)
#strong[與前版之差異（揭露）]：前版之 C\_i 實驗使用另一組資料（10 個 seed、各 60 窗，共 600 窗，N\_known \= 7）。為使全部殘差於同一資料集上評估，本版改用 D\-30；獨立 seed 數由 10 降為 8，總窗數由 600 增為 2,400。

]
#heading(level: 3, numbering: none)[4.6.3 E1：灌水偵測邊界與幅度不變性]
#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 4, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([灌水數 k], [N\_total], [斷言], [偵測（注入窗）]),
  [0（baseline）], [30], [conserved], [—],
  [\+1], [31], [#strong[violated]], [1,200 \/ 1,200],
  [\+2 ～ \+6], [32 ～ 36], [violated], [各 1,200 \/ 1,200])]
任何 |k| ≥ 1 → violated。N\_known \= 30 下偵測邊界為 \+1 UE（每筆偽造佔母體 1\/30 ≈ 3.3%）。

#strong[幅度不變性]：於固定注入起點施加 k \= 1…6，8 個 seed 之違反觀察延遲均為 #strong[0 秒]、升級為 rejected 之延遲均為 #strong[1 秒]（L\_C \= 2；圖 4\-1）——k 僅改變偏離量，不影響觸發時機。此為單窗即決斷言之必然結果。與統計型偵測器相對：後者需累積證據方能跨越門檻，偵測延遲隨攻擊幅度遞減。

#strong[規模關係（分析性）]：偵測邊界 |k| ≥ 1 與 N\_known 無關。隨 N\_known 改變者為#strong[相對衝擊比例] k\/N\_known（N \= 30 時 3.3%），不影響斷言判定，但決定下游決策之實質偏誤程度。

#heading(level: 3, numbering: none)[4.6.4 E7：守恆式繞過的精確性要求]
攻擊者欲繞過 C\_i，須使全域聯集之#strong[淨變化恰為零]。此可透過等量替換達成（同窗刪除 k 個既有 IMSI、新增 k 個假 IMSI），#strong[不必然需要知道 N\_known 之絕對值]；但攻擊者須確保被刪之 IMSI 未同窗出現於其他 cell、假 IMSI 不與既有母體重複，且替換須不破壞成員轉移之連續性（H\_i）。以 D\-30（2,400 窗）逐窗注入各種增刪組合：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 3, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([注入組合（假\/真）], [淨變化], [偵測率]),
  [\+2\/−2、\+3\/−3、\+1\/−1、\+4\/−4], [0], [#strong[0 \/ 2,400 \= 0%]],
  [\+2\/−1、\+3\/−2、\+1\/−0], [\+1], [#strong[2,400 \/ 2,400 \= 100%]],
  [\+1\/−2、\+2\/−3、\+0\/−1], [−1], [#strong[2,400 \/ 2,400 \= 100%]])]
#strong[二分（布林斷言之定義後果，非實證發現）]：淨變化為零者全數繞過，任何 |淨變化| ≥ 1 者全數偵測。C\_i 並非提高攻擊成本之統計門檻，而是#strong[不容許任何近似之離散約束]——攻擊者之配平容錯空間為 #strong[0]。

#heading(level: 3, numbering: none)[4.6.5 E8：單一 O\-DU 虛減之攻擊面]
#strong[觀測前提（v12 修訂）]：主檔之每個 (UE, LCID, 窗) 只有一個 cell 欄（最後事件之 cell），故 72,000 個 (窗, UE) 樣本中「同窗同時出現於 LTE 錨點與 mmWave cell」者為 0（最後事件歸屬 mmWave 41,523 筆，57.7%；歸屬 LTE 30,477 筆，42.3%）#strong[是報表結構造成的，不是證據]：R\-5 旁路檔顯示 UE 每窗實際上同時有兩路事件。因此本節只能說「#strong[報表結構上無法呈現雙掛]」，不能據此推論「UE 雙掛使單點刪除不改變全域聯集」之遮蔽情境不存在；以下結論之適用範圍限於此報表語意。

單一受攻擊 O\-DU 之虛減能力因此受兩重結構限制：

+ #strong[僅能抹除當窗掛載於其上之 UE]——未掛載於該 cell 之 UE 不在其上報範圍內。
+ #strong[於現行報表語意下，此類抹除必然造成全域聯集淨減]（主檔中無其他 cell 同時列出該 IMSI）。故#strong[於可發動虛減之窗（該 O\-DU 當窗至少掛載 1 UE）中，C\_i 之條件偵測率為 100%]（41,523 \/ 41,523）；無可攻擊目標之窗代表攻擊無從發動，不納入偵測率分母。

#strong[攻擊面量化]（圖 4\-4）：全場域每窗掛載於 mmWave 之 UE 數 mean \= 17.30（2,400 窗中無任何一窗為 0）；逐 O\-DU 之差異：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 4, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([O\-DU], [每窗可抹除 UE 數 (mean)], [最大值], [無可攻擊目標之窗比例]),
  [#strong[cell 2]], [#strong[4.80]], [9], [0.1%],
  [cell 3], [2.21], [6], [2.5%],
  [cell 4], [1.84], [6], [15.0%],
  [cell 5], [2.56], [6], [1.2%],
  [cell 6], [1.99], [6], [10.2%],
  [cell 7], [2.06], [6], [12.5%],
  [cell 8], [1.85], [6], [11.2%])]
#strong[意涵]：虛減方向之攻擊幅度存在結構性上限（受該 O\-DU 當窗掛載數限制，本資料中單窗最多 9 個 UE），灌水方向則無此限制。於 30 UE 之規模下，各 O\-DU 於 85% 以上之窗皆有可抹除之目標（cell 4 無目標之窗比例最高，為 15.0%），攻擊面較 7 UE 之前版資料大；惟於現行報表語意下，任一此類抹除皆使 N\_total 淨減而被 C\_i 偵測；若報表逐路列出，此結論不成立（見本節開頭之觀測前提）。

#block(width: 100%, fill: luma(240), inset: 8pt, radius: 2pt)[#set text(size: 10pt)
#strong[與 E2a 全域壓制之區分]：若攻擊者能同時竄改 LTE 錨點與所有 mmWave 節點之上報，N\_total 亦淨減、同樣 100% 觸發；惟該能力超出單一 mmWave O\-DU 之威脅模型。

]
#heading(level: 3, numbering: none)[4.6.6 E3：守恆式串謀盲點（核心涵蓋邊界）]
#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 3, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([攻擊], [N\_total], [斷言]),
  [守恆式串謀（\+2 假 \/ −2 真）], [30], [conserved（繞過 C\_i；0 \/ 1,200 窗被偵測）])]
#strong[這不是 C\_i 之缺陷，而是攻擊滿足了被監控之性質。] 完整性 R(t) \= P ⟹ |R(t)| \= |P|，反向不成立，故基數守恆為完整性之#strong[必要非充分條件]。此邏輯地推導出其他殘差之必要性：

- 被替換 UE 憑空增減 → 無合法成員轉移軌跡 → 可能破壞 #strong[H\_i]。須限定：H\_i 於本資料上之實證效力#strong[限於規則行為驗證]——D2 之乾淨基線為 vacuous、注入偵測屬設計必然（4.8.4），D1 之基線語意見 4.8.1；故不稱其為守恆式替換之主要防線。
- #strong[僅當]替換同時造成被攻擊節點之 delay 偏離同窗共識時，才被 #strong[S\_i] 捕捉——S\_i 只看 delay，偽造 IMSI 若使用正常 delay 未必破壞 S\_i，故 S\_i 為條件性佐證（此為 4.11 融合回放中「守恆式替換 S\_i \= normal」之依據）。

此結構與電力系統狀態估計中之不可觀測偽資料注入（unobservable false data injection）性質相近：滿足系統約束之注入可繞過殘差檢測。網路安全中亦有同類先例：以流量守恆偵測惡意路由器之 WATCHERS（Bradley et al., 1998）被指出未充分驗證守恆之前提，可被攻擊者擊敗（Hughes et al., 2000）。近期分析進一步指出，於交流潮流下，落在量測流形上之偽造量測與正常量測於殘差式偵測下根本無法區分（Xiao & Weng, 2026）；守恆式替換即本研究場域約束下之同類情形，故須以不同性質之證據（成員轉移）補足，而非調整 C\_i。圖 4\-2 視覺化此盲點。

#heading(level: 3, numbering: none)[4.6.7 E6：L\_C 持續窗政策之取捨代價]
L\_C \= 2 用於吸收斷線重連瞬態，但同時開啟一個攻擊面：#strong[持續時間短於 L\_C 之脈衝攻擊，雖觸發違反觀察，卻不升級為 rejected]。

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 2, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([注入持續 D], [未升級為 rejected 之比例（單位：(seed, 起始秒)）]),
  [#strong[1 窗]], [#strong[1,200 \/ 1,200 \= 100%]],
  [2 窗], [0 \/ 1,192 \= 0%],
  [3 窗], [0 \/ 1,184 \= 0%],
  [5 窗], [0 \/ 1,168 \= 0%])]
8 個 seed 之逐 seed 比例與上表相同（D \= 1 皆為 100%，其餘皆為 0%）。

#strong[意涵]（圖 4\-3）：所有 D \= 1 之注入均觸發違反觀察（#raw("R1_CI_PENDING") → low\-trust），但因 L\_C \= 2 而不升級。L\_C 越大瞬態容忍度越高，脈衝攻擊之可利用窗口亦越寬。改善方向包含：對「新增未登記 IMSI」採非對稱政策（因有 allowlist 可即刻證偽，可設 L\_C \= 1），或對重複出現之單窗違反累計計分。本研究採統一 L\_C \= 2，此脆弱性列為已知限制；重複出現之單窗違反於現行規則下之效果見下方 E11b。

#strong[E11b：重複單窗脈衝 × #mi("L_C")]（腳本 #raw("run_E11b_pulses.py")；規則行為驗證，D\-30 8 seed）：於受測 cell 注入單窗 #mi("C_i") 灌水脈衝，脈衝間隔 g ∈ {1, 2, 3, 5} 秒（脈衝之間至少一個完整、#mi("C_i") 正常之秒窗），共 10 個脈衝，#mi("L_C") ∈ {1, 2, 3}。在造成 #mi("C_i") 違反之脈衝窗中（分母 515–529，依 g 而異），受測節點由 #raw("R1_CI_VETO") 判為 rejected 之比例：#mi("L_C") \= 1 時為 1.00；#mi("L_C") \= 2、3 時為 0.00，其中 512–524 個為 #raw("R1_CI_PENDING")（low\-trust），另 3–6 個（g \= 1／2／3／5 依序為 6／5／3／5）因同窗另有綁定之交叉佐證，由 #raw("R2_SI_D1_BOUND") 判為 rejected（嚴重度序下方可見；原順序下此 19 筆被遮蔽為 low\-trust，4.4.0（三））。此結果為規則之必然（連續計數於間隔窗歸零），屬#strong[規則行為驗證]，非實證發現；其意涵為：#strong[於現行 #mi("L_C") \= 2 下，間隔至少一秒之重複單窗脈衝永不經由 #mi("C_i") 升級為 rejected（僅於同窗另有交叉佐證時被拒）]。另有 31–45／560 個脈衝時點因受測節點當窗無上報而無法注入，不計入分母；乾淨回放於三個 #mi("L_C") 下皆不變（D\-30 乾淨資料無 #mi("C_i") 違反），故 #mi("L_C") 降低之乾淨代價於現有資料不可量測。所有註記（1,351,458 筆）經獨立實作逐筆核對。

#heading(level: 3, numbering: none)[4.6.8 E4／E5：時機無關性與違反判定]
#strong[E4]：灌水 \+3 於 early\/mid\/late 注入，斷言均 violated（各 800 \/ 800 窗）→ 偵測不依賴攻擊時機（逐窗獨立判定、不累積歷史之後果）。

#strong[E5（輸入層判定效果）]：在#strong[破壞守恆之攻擊類別下]（灌水／全域壓制），對 2,400 個 baseline 窗逐一注入，啟用斷言時全數判為違反，未啟用時全數進入。

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 2, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([測試類型], [觸發數\/測試數]),
  [乾淨窗], [0\/2,400],
  [\+1 灌水], [2,400\/2,400],
  [全域 −1 壓制（E2a）], [2,400\/2,400],
  [守恆式替換（E3）], [0\/2,400])]
#strong[此 100% 不涵蓋守恆式串謀（E3）——對該攻擊 C\_i 單獨判定率為 0%，須由其他證據補（H\_i 於本資料之效力限於規則行為驗證，4.6.6）。] 此為斷言執行結果，非學習所得之泛化性能；判定經 Policy Enforcement 轉為准入動作（4.9.3）；其對下游決策之影響，本研究僅於 4.12 以延遲為準則之代理決策評估，#strong[基數類攻擊對下游決策之影響未評估]。

#heading(level: 3, numbering: none)[4.6.9 歸因、複雜度與有效性威脅]
#strong[第一層歸因]：#raw("new_imsi = 場域聯集 − known_population")；#raw("candidate_cells = {j : reported(j) ∩ new_imsi ≠ ∅}")。灌水可鎖定嫌疑 cell；虛減無法反查（須 H\_i 佐證）。灌水之識別機制與身分偽造（Sybil attack）偵測相近。

#strong[複雜度]：斷言為單次雜湊集合聯集比對，時間 O(M)、空間 O(N\_known)。實測開銷見 4.9.5（驗證層全體，非 C\_i 單項）。

#strong[有效性威脅]：

- #strong[建構有效性]依賴窗對齊（缺對齊緩衝會產生假性違反，屬工程問題非不變量缺陷）。
- #strong[E8 之攻擊面刻畫]受本組態之 MC 連結行為影響——R\-5 旁路檔顯示本模擬中 UE 每窗實際上同時有兩路事件；若報表逐路列出（真實部署之可能情形），錨點仍會列出被刪除之 UE，C\_i 對單點虛減之偵測率將低於 100%；若錨點每窗皆列出全部 UE，則為 0。此項之重評屬第二階段。
- #strong[L\_C 政策脆弱性]（E6、E11b）：間隔至少一秒之重複單窗脈衝於 #mi("L_C") \= 2 下永不經由 #mi("C_i") 升級（E11b，規則行為驗證）；對重複單窗違反之跨窗累計計分政策#strong[尚未評估]。
- #strong[外部有效性]限於封閉、母體固定之 SNPN；2,400 窗不構成全域證明。

#figure(image("/data/results/d30/fig_Ci_1_trajectories_unified.png", width: 90%), caption: [四情境基數軌跡])
#figure(image("/data/results/d30/fig_Ci_2_boolean_unified.png", width: 90%), caption: [布林判定與 E3 盲點])
#figure(image("/data/results/d30/fig_Ci_3_persistence_unified.png", width: 90%), caption: [L\_C 下脈衝注入之非升級比例])
#figure(image("/data/results/d30/fig_Ci_4_attack_surface_unified.png", width: 90%), caption: [單點虛減攻擊面])
#heading(level: 2, numbering: none)[4.7 S\_i：跨節點同時態共識驗證]
#heading(level: 3, numbering: none)[4.7.1 定位與資料可觀測性]
S\_i 驗證「此節點之觀測是否被同一時刻之其他節點支持」。

#strong[v12 之輸入（第一階段）]：主檔之 delay 為自 t \= 0 起之累計平均（3.3.1），本節起之 S\_i 一律改用以相鄰窗累計值差分重建之#strong[區間平均延遲]。重建之精度於 R\-5 旁路 run（seed 4200，窗 0–299）以精確值對帳：R\-5／R\-6 結構檢查通過（8,970 組），以重建值與精確值分別計算 S\_i 判定之一致率檢查（1,979 個節點窗）0 筆翻轉；尺度之同 seed 差異為 C\-1 0.11 %、C\-2 0.21 %。跨 seed 對照中，單一 R\-5 run 之精確 C\-1 尺度較各 fold 之重建值低 17–22 %，超過預先訂定之 10 % 人工複核門檻，經使用者複核後接受（#raw("Si_interval_correction_spec_v0.md") §9.1；輸出 #raw("data/results/semantics_v0/")）。尺度 #mi("s")（C\-2，cell 平均層級）由累計輸入之 0.052–0.056 ms 變為 0.160–0.171 ms（8 個 LOSO fold），約為 3.1 倍。另須註明：主檔 delay 為 mmWave 與 LTE 兩路 PDU 之混合平均，LTE 路徑之 PDU 延遲恆為 3 ms；peer 集合為「當窗最後事件歸屬各 mmWave cell 之 UE」，每窗約三成 UE 因最後事件歸屬 LTE 而不在任何 mmWave cell 平均中（#raw("Si_interval_correction_spec_v0.md") §7）。因此#strong[本節之結果一律以現行 cell 歸屬（最後事件）為條件]，per\-cell 歸屬實作後（第二階段）須重評。

#strong[為何以延遲為偵測維度]：同窗跨 mmWave cell 之區間平均延遲變異係數中位數為 #strong[0.275]（四分位 0.181–0.398；n \= 2,400 窗；#raw("cv_interval.json")）。舊版以累計平均算得之 0.058（四分位 0.043–0.081）因累計平均隨時間趨於平滑而被構造性壓低，#strong[不再採用]。吞吐量之離散度仍較高：轉為每窗增量後，各 cell 之時間變異係數為 0.86–1.48、跨 cell 之變異係數為 0.63（#raw("audit_Si_data.py")，seed 4200；吞吐量本即以增量計算，4.3.2）。區間延遲之跨 cell 離散度低於吞吐量，但差距不到一個數量級，故不再宣稱「延遲於同一時刻之跨 cell 分布緊密」；延遲是否足以作為共識參照，由 4.7.4 之乾淨誤報率直接實測。吞吐量之驗證另需要本研究未取得之資源佐證，不在涵蓋範圍（4.5.2）。UE 數則屬 C\_i 之守備範圍。#strong[此維度選擇由資料之經驗可觀測性決定，而非預設攻擊落於延遲。]

#strong[證據可用性]：跨節點共識需要同窗至少有其他活躍節點可比。D\-30 之 2,400 窗中，每窗活躍之 mmWave cell 數為 4–7 個：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 5, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([同窗活躍 mmWave cell 數], [受測節點之 peer 數], [層級], [窗數], [比例]),
  [4], [3], [full consensus], [10], [0.4%],
  [5], [4], [full consensus], [133], [5.5%],
  [6], [5], [full consensus], [970], [40.4%],
  [7], [6], [full consensus], [1,287], [53.6%])]
即於 30 UE 之規模下，#strong[全部 15,534 筆 (節點, 窗) 皆具備 full consensus]（peer ≥ 2），weak evidence 與 unavailable 皆為 0 筆。此與 7 UE 之前版資料不同（該資料僅 54.8% 之窗具備 full consensus）：證據可用率取決於場域之 UE 密度，低密度或離峰時段仍須依賴下述之 abstain 處置。

#heading(level: 3, numbering: none)[4.7.2 S\_i 定義]
設同窗活躍 mmWave cell 集合為 #mi("\\mathcal{A}(t)")，受測節點為 #mi("j")。

#strong[中心共識估計]（同一時刻其他節點之即時共識，排除受測節點本身）：

#mitex("c_j(t) = \\operatorname{median}_{\\,k \\in \\mathcal{A}(t)\\setminus\\{j\\}} \\big\\{ \\mathrm{delay}_k(t) \\big\\}")
#strong[全域尺度因子]（由訓練 seed 之乾淨軌跡估計，LOSO 下不含 held\-out seed）：

#mitex("s = 1.4826 \\cdot \\mathrm{MAD}_{\\text{global}}")
#strong[共識殘差與判定]：

#mitex("z_j(t) = \\frac{\\big|\\, \\mathrm{delay}_j(t) - c_j(t) \\,\\big|}{s}, \\qquad S_i \\text{ violated} \\iff z_j(t) > \\tau_S \\;\\;(\\tau_S = 4)")
- #strong[（空間性）] 中心取自同一時刻其他 cell，故 #mi("z_j") 度量節點對場域即時共識之偏離，非對自身歷史之偏離。
- #strong[（尺度固定、中心動態）] 尺度與門檻由乾淨資料一次估計後固定；中心每窗即時計算。因中心不含受測節點，單點漂移無法拖動參照。
- #strong[（尺度穩定）] 同窗活躍 cell 數少（N ≤ 7），即時 MAD 有小樣本高變異問題，故尺度由全域乾淨資料估計；1.4826 使 MAD 成為常態標準差之漸近一致估計量。
- #strong[（每窗獨立）] 不累積歷史殘差。

#strong[證據不可得之處置]：本研究以 MIN\_PEER \= 2 為判定門檻，即僅於 full\-consensus 窗判定 S\_i；weak evidence（peer \= 1）與 unavailable（peer \= 0）均視為證據不可得，依 4.4.0 判為 abstain（#raw("R3_ABSTAIN")）；若同窗另有其他殘差之證據，則依規則順序由 L1 或 L2 先行判定。#strong[abstain 為「暫緩採信」而非「預設通過」]，避免攻擊者利用離峰空窗或壓制鄰居 cell 以規避 S\_i；C\_i 之基數守恆為不依賴 peer 之防線，不受此影響。

#block(width: 100%, fill: luma(240), inset: 8pt, radius: 2pt)[#set text(size: 10pt)
#strong[定位收斂]：延遲之離散度低於吞吐量，僅表示各 cell 數值相對較近，不證明受單一共同物理因素約束。S\_i 定位為#strong[場域即時共識殘差（field\-wide contemporaneous consensus residual）]，其偵測效力由實驗支持，不對物理詮釋作過度宣稱。

]
#heading(level: 3, numbering: none)[4.7.3 核心論證：參照機制之轉換]
#block(width: 100%, fill: luma(240), inset: 8pt, radius: 2pt)[#set text(size: 10pt)
時序偵測器問：「此節點是否與#strong[自己的過去]一致？」 S\_i 問：「此節點是否與#strong[此刻其他節點的共識]一致？」

]
S\_i 之貢獻不在 median、MAD 或 τ\_S 之選擇，而在#strong[把異常偵測之參照基準，從節點自身之時間歷史換成同一時刻其他節點之空間共識]。

#strong[此轉換之方向並非本研究首創]：無線感測網路已以鄰近節點之空間相關、配合以 median／MAD 為基礎之穩健估計，偵測持合法金鑰之內部攻擊者（Liu et al., 2007）；行動網路之 sleeping cell 偵測亦指出，與鄰 cell 比較可抓到只看自身歷史抓不到之劣化（Asghar et al., 2017）。惟前者模擬之攻擊者偏離正常值約 20 個標準差且攻擊固定，後者為良性故障，皆未評估界內、緩慢之偽造。本節之主張因此限縮為：#strong[在 O\-RAN E2 KPM 之界內緩慢偽造下，以受控消融量化此轉換之效益]，並標出其界線（串謀節點數 4.10、校準期中毒 4.7.8 Q6）。

#strong[為何滑動更新之自我參照對緩慢漂移失效]：以自身近期觀測為參照、且參照隨新觀測滑動更新時，足夠緩慢之偏移會被逐步納入參照本身——漂移成為新的局部常態，殘差因而可長期落在門檻內。須限定：此論證適用於#strong[隨近期觀測滑動更新之局部自我參照]；採凍結之長期基線、變點偵測（如 CUSUM）或雙時間尺度設計之偵測器不必然受此限，本研究未對其進行評估。

#strong[為何同時態空間參照不受此限]：S\_i 之參照取自同窗其他節點，不隨受測節點之漂移移動。偏移對著一條由誠實鄰居構成之基準累積，若持續擴大即會跨過 τ\_S；停在 τ\_S·s 以內之偏移則不會被偵測（4.7.8 Q4）。舊版稱「漂移速率越低，此對比越明顯」，於區間輸入下不成立：兩種參照之差距只出現於 1 %\/秒以上（4.7.4）。

此主張於 4.7.4 以受控消融檢驗，並於 4.7.5 延伸至既有工作之攻擊模型。#strong[v12 註]：於區間輸入下，時間參照之「吸收」與其自身誤報水準難以分辨（4.7.4 之發現 2），空間參照之優勢亦只出現於 1 %\/秒以上；本節之論證保留為設計理由，其實證強度以 4.7.4 之新數字為準。

#heading(level: 3, numbering: none)[4.7.4 主實驗：參照機制受控消融]
#strong[設計動機]：若以不同模型（如 LSTM）作為時序對照，偵測率差異可能同時源自參照機制、模型能力與資料條件，無法歸因。本實驗採#strong[受控消融]：固定資料、尺度、門檻與攻擊，#strong[僅變動參照中心一個變數]。

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 2, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([控制變數], [設定]),
  [資料], [D\-30 之 mmWave cell #strong[區間平均延遲]（累計值差分重建；4.7.1），LOSO（8 seed）],
  [尺度 #mi("s")], [同一 global MAD（僅由 training seeds 估計）],
  [門檻], [同為 τ\_S \= 4],
  [攻擊], [同一組 delay 線性漂移：偏移 \= r ×（自注入起點經過之實際秒數）× 平均 delay，自序列中點起注入於受測 cell #strong[所有上報窗]],
  [評估範圍], [full\-consensus 窗（peer ≥ 2）之後半段中，兩種參照皆可評估者（共同集合）],
  [#strong[評估區間]], [#strong[序列後半段（注入區間）；乾淨與注入於同一窗子集上比較]],
  [#strong[唯一差異]], [#strong[中心 \= 同窗其他 cell 中位數　vs　自身前 10 秒內有上報之窗之中位數]])]
兩種參照使用#strong[相同之統計量與計算複雜度]（皆為中位數），故偵測率差異不可歸因於模型能力。時間參照於前 10 秒內有上報之窗少於 5 個時不可評估；共同集合佔 full\-consensus 後半段窗之 94.7%（樣本等權；seed 間 82.0%–100%），完整 10 秒皆有上報者為 76.5%（seed 間 67.2%–85.1%）。時間單位之定義見本節末之說明。

#strong[結果]（第一階段正式版；共同集合；56 組 (seed, cell) 樣本之等權平均；差值以未捨入之值計算；以現行 cell 歸屬（最後事件）為條件）：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 5, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([漂移速率（%\/秒）], [空間共識參照], [時間自我參照], [差值], [舊值（累計輸入）空間／時間]),
  [#strong[乾淨序列 FPR（注入區間）]], [#strong[0.098]], [#strong[0.106]], [—], [0.046／0.029],
  [0.1], [0.11], [0.11], [\+0.01], [0.07／0.03],
  [0.2], [0.13], [0.11], [\+0.02], [0.21／0.03],
  [0.5], [0.23], [0.11], [\+0.12], [0.65／0.03],
  [1.0], [0.55], [0.11], [\+0.44], [0.82／0.03],
  [2.0], [0.77], [0.12], [\+0.65], [0.91／0.04],
  [4.0], [0.88], [0.13], [\+0.75], [0.95／0.12],
  [8.0], [0.94], [0.19], [\+0.75], [0.97／0.96],
  [15.0], [0.97], [0.56], [\+0.40], [0.98／0.98])]
空間參照之乾淨誤報率 seed 間為 0.05–0.15，時間參照為 0.05–0.19。舊值為累計平均輸入之結果（v11），僅供對照，不再作為結論依據。

#strong[評估區間之界定]：漂移於序列中點注入，故乾淨與注入之偵測率均於序列後半段評估，以確保二者落在同一窗子集、可直接相減。空間參照於全部 full\-consensus 後半段窗（原始評估集合，樣本等權）之乾淨誤報率為 0.111（舊值 0.051），與以窗索引為單位之實作逐窗相同（腳本內建檢查，15,534 筆；空間參照不依賴時間序列）。第一階段之 xApp 重跑於全序列、以節點註記合併計算，S\_i 違反為 1,755／15,534（11.3%；舊值 408，2.6%），與本節「(seed, cell) 樣本等權、限後半段」之口徑不同，不可直接對照；融合層之其餘結果屬第二階段（4.9 仍為歷史版本）。

#strong[核心發現]：

+ #strong[乾淨誤報率上升]：區間輸入下，兩種參照之乾淨誤報率皆約 0.10（空間 0.098、時間 0.106），為舊值之 2.1 倍與 3.7 倍；尺度 #mi("s") 同時增為約 3.1 倍（4.7.1）。舊版之低誤報有一部分來自累計平均之平滑，而非場域共識本身。
+ #strong[時間自我參照於 ≤ 4 %\/秒時與其誤報水準相當]：0.1–4 %\/秒之偵測率為 0.11–0.13，與其乾淨誤報率 0.106 相當；8 %\/秒時僅 0.19，15 %\/秒時為 0.56（舊值 0.96／0.98）。舊版「≥ 8 %\/秒時兩者收斂」#strong[於區間輸入下不成立]。
+ #strong[空間共識參照之分離縮小、門檻後移]：0.5 %\/秒時為 0.23（舊值 0.65），與其誤報率 0.098 之差距有限；1–2 %\/秒時為 0.55–0.77（舊值 0.82–0.91）；≥ 4 %\/秒時為 0.88 以上。兩種參照之差值於 1–8 %\/秒為 \+0.44 至 \+0.75，0.1–0.2 %\/秒時兩者皆不高於誤報水準。故「空間參照於低速漂移下有效」之主張須收斂為：#strong[於 1–2 %\/秒，空間參照之偵測率高於時間參照，惟乾淨誤報率約 0.10]；0.5 %\/秒以下兩者皆非有效之偵測。
+ #strong[τ\_S 敏感度（E13）未於區間輸入下重跑]：E13 屬第二階段（#raw("Si_interval_correction_spec_v0.md") Q\-3），4.7.7 之 E13 表為累計輸入之歷史結果，#strong[不得用於支持上表]。上表之結論因此限於 τ\_S \= 4。

#strong[攻擊動機]：RIC 依 KPM 進行負載平衡與換手決策，受攻擊 O\-DU 持續灌高自身回報延遲可誘使流量導離，灌低則吸引流量至受控節點。理性攻擊者若採 low\-and\-slow 策略規避時序偵測，於區間輸入下，0.5 %\/秒以下之漂移對兩種參照皆接近不可偵測；空間參照之優勢只出現於 1 %\/秒以上。

#strong[樣本結構]：56 組 (seed, cell) 非獨立樣本（同 seed 內 cell 共用軌跡與共識參照），不確定性以 seed 為 cluster 呈現；本節之表只列 seed 間範圍，未計算信賴區間。（腳本 #raw("run_E9_rt.py")；規格 #raw("docs/thesis/planB_realtime_spec.md")）

#strong[時間單位之說明（2026\-10\-06 修訂）]：本節初版以「被評估之 full\-consensus 窗」為漂移與時間參照之單位；然於前版之 7 UE 資料中，full\-consensus 序列之相鄰索引實際相隔 1 秒者僅 53.4%，同一「%\/窗」於不同章節代表不同速率，且與 4.12 以實際秒計之注入不一致。依事前登記之規格改以實際秒計，並以共同集合比較；空間參照之乾淨判定與階躍判定於原始評估集合上逐窗重現修訂前之值。前版資料上修訂前後之數字對照見附錄 A。

#figure(image("/data/results/d30/fig_Si_reference_ablation_rt.png", width: 90%), caption: [參照機制受控消融（實際秒；共同集合；v12 之圖為 #raw("data/results/d30_delay_reconstructed/") 之對應輸出）])
#heading(level: 3, numbering: none)[4.7.5 E9：既有工作之攻擊模型下的操作區對照]
#strong[動機]：既有之 KPM 中毒偵測以學習式時序建模為主。Alimohammadi 等人提出 KPI 中毒攻擊並以 LSTM 偵測，自報偵測率介於 62% 至 99%，且放大倍數越大越易偵測（FNWF 2024）；其後續多層防禦框架之評估採放大因子 1.2／1.3／1.4／1.5 之階躍注入，報告攻擊偵測率 ≥ 97.9%，並自承可能漏掉緩慢隱蔽之中毒模式（IEEE OJCOMS 2026）。#strong[本實驗檢驗：兩種參照於既有工作所用之階躍幅度下之行為]。（v11 之動機為「既有工作之評估是否恰好落在兩種參照皆有效之高幅度區間」；於區間輸入下此前提不成立，見下方發現。）

#strong[設計]：沿用 4.7.4 之全部控制變數（資料、尺度、門檻、評估範圍、評估區間），僅擴充攻擊族：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 3, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([攻擊族], [注入方式], [參數]),
  [#strong[階躍放大]（既有工作之攻擊模型）], [注入起點後，受測 cell 之 delay 乘以放大因子 AF], [AF ∈ {1.2, 1.3, 1.4, 1.5}],
  [#strong[漸進漂移]（本研究，同 4.7.4）], [注入起點後，偏移每實際秒遞增 r% × 平均 delay], [r ∈ {0.1, 0.2, 0.5, 1, 2, 4, 8, 15}])]
#strong[指標]：注入區間偵測率；階躍族另報 onset 命中率（注入後前 5 秒內之共同可評估窗是否至少觸發一次），用以區分「起始點被捕捉後遭吸收」與「起始點即未被捕捉」。

#strong[須誠實說明之差異]：既有工作係放大目標 UE 之多項 KPM（吞吐量、PRB、封包數）分布之平均與共變異數；本實驗僅放大受測 cell 之 delay，屬#strong[同型攻擊於本研究觀測維度上之對應]，而非對其實驗之重現。本實驗比較之對象為兩種參照機制，#strong[不比較本研究與既有工作之偵測器效能]。

#strong[結果]：

（D\-30，區間平均延遲，LOSO，56 個 seed × cell 樣本，共同集合；偵測率為 56 個樣本之等權平均，括號內為 seed 間範圍——即各 seed 內樣本平均之最小與最大）

（第一階段正式版；以現行 cell 歸屬（最後事件）為條件；差值以未捨入之值計算）

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 8, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([攻擊族], [參數], [空間共識參照], [時間自我參照], [差值], [空間參照 onset 命中率], [時間參照 onset 命中率], [舊值（累計輸入）空間／時間]),
  [階躍], [AF \= 1.2], [0.15（0.09–0.20）], [0.13（0.06–0.22）], [\+0.01], [0.45], [0.41], [0.24／0.03；onset 0.41／0.25],
  [階躍], [AF \= 1.3], [0.18（0.11–0.24）], [0.15（0.07–0.23）], [\+0.03], [0.54], [0.46], [0.61／0.06；onset 0.73／0.93],
  [階躍], [AF \= 1.4], [0.21（0.15–0.26）], [0.16（0.08–0.25）], [\+0.05], [0.59], [0.54], [0.96／0.07；onset 0.96／0.96],
  [階躍], [AF \= 1.5], [0.25（0.18–0.31）], [0.17（0.09–0.25）], [\+0.08], [0.62], [0.61], [1.00／0.07；onset 0.96／0.96],
  [漂移], [0.1 – 15 %\/秒], [同 4.7.4], [同 4.7.4], [同 4.7.4], [—], [—], [—])]
注入區間之乾淨誤報率：空間參照 0.098（seed 間 0.05–0.15）、時間參照 0.106（0.05–0.19）；舊值為 0.046／0.029。#strong[一致性檢查]：空間參照於原始評估集合之乾淨誤報率與四個階躍之偵測率，逐位重現以窗索引為單位之實作（同輸入、同注入時點、同比較窗集合；腳本內建檢查通過）。第一階段正式版與探索性之 dry run 之 11 個輸出檔，除 xApp 之計時欄位外逐位相同。

#strong[發現]（本次 E9 之資料與注入設定下）：

+ #strong[於區間輸入下，AF 1.2–1.5 之階躍對兩種參照之偵測率皆低]：空間參照之注入區間偵測率為 0.15–0.25、時間參照為 0.13–0.17，各自之乾淨誤報率為 0.098／0.106；以表列之捨入值計，高出誤報之幅度約為 0.05–0.15 與 0.02–0.06。舊版於 AF ≥ 1.4 之 0.96–1.00 #strong[未重現]；其原因之一為尺度 #mi("s") 增為約 3.1 倍（4.7.1），同一相對放大量對應之 #mi("z_j") 隨之縮小。
+ #strong[onset 命中率亦下降]：空間參照為 0.45–0.62、時間參照為 0.41–0.61（舊值時間參照 0.93–0.96）。onset 命中率未計算乾淨序列之對應值（輸出檔無此欄），故無法判定其高出誤報之程度；逐窗誤報約 0.10 時，5 秒內至少一次告警本即不罕見。
+ #strong[舊版「起始點被捕捉、其後被吸收」之型態不再清楚]：時間參照之注入區間偵測率與其誤報水準之差距本即很小，無從區分「被吸收」與「未被偵測」。

#strong[意涵之界定（v12 修訂）]：v11 之結論「兩種參照之差異在能否於偏移存續期間持續標記」建立於累計平均輸入，#strong[於區間輸入下不受支持，撤回]。本實驗於區間輸入下只能說：既有工作所用之 AF 1.2–1.5 階躍，於本研究之 delay 維度、凍結尺度與 τ\_S \= 4 下，#strong[兩種參照皆非有效之偵測]；4.7.4 所示之空間參照優勢限於 1 %\/秒以上之漸進漂移。此結論限於#strong[以滾動中位數為參照之時間偵測器]，不外推至既有工作之 LSTM，亦不應解讀為本研究之偵測器優於或劣於既有工作。

#figure(image("/data/results/d30/fig_E9_operating_regime_rt.png", width: 90%), caption: [兩種參照於階躍與漸進攻擊下之偵測率（實際秒；共同集合；區間平均延遲）——x 軸左區為漂移速率（%\/秒）、右區為階躍放大因子，y 軸為注入區間偵測率；腳本 #raw("run_E9_rt.py")])
#heading(level: 4, numbering: none)[4.7.5.1 E9b：監督式時序分類器之對照]
#strong[動機]：4.7.6 之 LSTM 基準與上表之時間參照，皆屬「以自身近期觀測為參照」之自我參照類；既有工作之偵測器（Alimohammadi 等人，FNWF 2024；及其後續 IEEE OJCOMS 2026）則為以帶標籤注入資料訓練之#strong[監督式時序分類器]。自我參照類之盲點不得外推至監督式模型，故以同類方法於本研究觀測維度上實作一組對照，檢驗以階躍標籤訓練之分類器於訓練分布外之漸進漂移下之行為。

#strong[設計]：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 2, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([項目], [設定]),
  [資料], [D\-30（區間平均延遲），與 E9 相同之 56 個 seed × cell 樣本；LOSO（7 seed 訓練、1 seed 測試）],
  [輸入], [受測 cell 自身之 delay，取 w − 9 … w 共 10 個實際秒（含當窗，不用未來資料），不含 peer 資訊。通道一：(delay − 訓練資料中位數) \/ s，缺窗以固定占位值 0 表示；通道二：有無上報之遮罩。10 秒內有上報之窗少於 5 個者不可評估],
  [標籤與訓練資料], [逐窗標籤（注入起點後 \= 1）；每條訓練序列含 1 份乾淨序列，及 AF ∈ {1.2, 1.3, 1.4, 1.5} × 5 個隨機起點之階躍注入（注入於受測 cell 所有上報窗）；以 pos\_weight 平衡],
  [模型], [LSTM（hidden 64、2 層）\+ 線性輸出；25 epoch；CPU 確定性執行，整體重跑逐位相同],
  [門檻], [機率 0.5；及 #strong[校準目標 FPR]（定義凍結為「同資料集 E9 空間參照於原始評估集合之乾淨誤報率」，#raw("D30_parameter_freeze.md")；定義不變，於區間輸入下其值為 0.1107，舊輸入為 0.0515），以#strong[訓練 fold] 乾淨複本後半段之可評估窗合併取分位數，不使用測試資料],
  [測試], [與 E9 相同之注入時點與攻擊族；方法間比較以三種方法之共同集合為準])]
輸入由單通道改為「值 \+ 遮罩」雙通道，#strong[屬處理不規則觀測之模型修改]，不宣稱訓練設計完全未變。

#strong[擬合檢查（執行前訂定）]：訓練資料之 balanced accuracy 須 ≥ 0.80。八個 fold 為 0.996–0.998，通過（舊輸入 0.998–0.999）。時間單位修訂前另有一個僅保留序列形狀之 #raw("relative") 變體，因三個 fold 未通過擬合檢查而不採計；修訂後不再嘗試該變體。

#strong[結果]（共同集合；以訓練資料校準之門檻；括號內為 seed 間範圍）：

（第一階段正式版；以現行 cell 歸屬（最後事件）為條件）

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 6, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([攻擊族], [參數], [監督式分類器], [空間共識參照（E9）], [時間自我參照（E9）], [舊值（累計輸入）監督式]),
  [乾淨誤報率], [—], [#strong[0.423]（0.324–0.485）], [0.098（0.05–0.15）], [0.106（0.05–0.19）], [0.144],
  [階躍], [AF \= 1.2], [0.91（0.81–0.96）], [0.15], [0.13], [0.96],
  [階躍], [AF \= 1.3], [0.97（0.95–0.99）], [0.18], [0.15], [1.00],
  [階躍], [AF \= 1.4], [0.98（0.98–0.99）], [0.21], [0.16], [1.00],
  [階躍], [AF \= 1.5], [0.99（0.98–1.00）], [0.25], [0.17], [1.00],
  [漂移], [0.1 %\/秒], [0.64（0.49–0.70）], [0.11], [0.11], [0.45],
  [漂移], [0.2 %\/秒], [0.78（0.67–0.84）], [0.13], [0.11], [0.69],
  [漂移], [0.5 %\/秒], [0.90（0.84–0.93）], [0.23], [0.11], [0.86],
  [漂移], [1 %\/秒], [0.95（0.92–0.96）], [0.55], [0.11], [0.91],
  [漂移], [2 %\/秒], [0.96（0.94–0.98）], [0.77], [0.12], [0.96],
  [漂移], [4 %\/秒], [0.98（0.97–0.99）], [0.88], [0.13], [0.98],
  [漂移], [8 %\/秒], [0.98（0.98–0.99）], [0.94], [0.19], [0.99],
  [漂移], [15 %\/秒], [0.98（0.98–0.99）], [0.97], [0.56], [0.99])]
階躍之 onset 命中率於四個 AF 為 0.95–0.96。門檻取 0.5 時，各列與上表之差距 ≤ 0.11，乾淨誤報率為 0.276。以「實際連續兩秒告警」為準則時，監督式分類器於乾淨序列之注入區間內出現誤報之樣本比例為 0.96（seed 間 0.86–1.00；舊值 0.41）。

#strong[發現]（本次 E9b 之資料與注入設定下）：

+ #strong[監督式分類器之偵測率仍高]：1 %\/秒時偵測率 0.95、0.5 %\/秒時 0.90，階躍 0.91–0.99。以絕對水準為輸入者，其參照為訓練資料之水準分布，不隨受測節點移動。
+ #strong[但誤報率極高，且校準未能跨 seed 轉移]：校準目標 FPR 為 0.1107，測試 seed 上之實際乾淨誤報率為 #strong[0.423]（0.324–0.485），約為空間參照之 4.3 倍（舊輸入為 0.144，3.1 倍）。監督式分類器與兩種參照#strong[並非於相同誤報水準下比較]：其於乾淨誤報 0.423 下之偵測率（漂移 1 %\/秒為 0.95）仍遠高於其誤報率，具鑑別力；空間參照於乾淨誤報 0.098 下為 0.55。本實驗未提供相同誤報水準下之比較，故既不得解讀為監督式分類器優於兩種參照，亦不得解讀為兩種參照優於監督式分類器。（粗略之對照點：E\-i 中空間參照於乾淨誤報 0.372 下，1 %\/秒之偵測率為 0.83；惟其評估集合與尺度皆不同，不可直接相減，4.7.5.4。）相同誤報水準下之比較已由 C3 補做（v12.2，4.7.5.5）：監督式模型改以未參與訓練之校準 seed 取門檻後，乾淨誤報可降至約 1%，且逐窗偵測力仍高於 peer 檢查。故本段 0.423 之高誤報為 E9b 之校準方式所致，#strong[不是監督式方法之固有代價]。
+ #strong[依賴標註資料]：分類器需帶標籤之注入資料；本實驗之標籤由合成注入產生，實際部署時此類標籤之取得本身即為前提。

#strong[對本研究主張之影響]：E9b 仍不支持「學習式時序方法於慢速漂移下普遍失效」之推論；4.7.4–4.7.6 所示之盲點僅適用於以自身近期觀測為參照之方法（4.7.3）。#strong[（v12.2 修正）] v12.1 寫「相對於監督式方法，本研究可實證之差異為較低之乾淨誤報率（0.098 對 0.423）與無需標註資料」；其中「較低之乾淨誤報率」#strong[撤回]：於相同之誤報校準目標下（同條件偵測方法比較，4.7.5.5），監督式模型之誤報可校準至約 1%，且逐窗偵測力高於 peer 檢查。相對於監督式方法，本研究可實證之差異僅剩#strong[無需標註資料]，以及#strong[對未訓練之攻擊方向不失效]（只學放大之 LSTM 對調低之 lift ≈ 0）。全場域共模變化下之行為檢驗於 4.7.5.2（E9c）：全場域 delay 上升 10 % 時，監督式分類器之告警率由 0.41 升至 0.70，空間參照與時間自我參照皆由 0.09 升至 0.10——此差異只相對於監督式分類器成立，空間參照相對於時間參照並無優勢。

#strong[範圍界定]：此為同類方法於本研究觀測維度上之實作，#strong[非既有工作之重現]——既有工作之輸入為 per\-UE 多項 KPM，本實作僅有 per\-cell delay，模型規模與訓練資料量亦不同。結論限於「以階躍標籤訓練、以自身時序之絕對水準為輸入之監督式分類器」於 D\-30 上之行為，亦不應解讀為本研究之偵測器優於或劣於既有工作。

（腳本 #raw("run_E9b_rt.py")；驗證層級：離線合成注入，D\-30 8 seed；模型存於 #raw("data/results/d30_delay_reconstructed/planB_models/")）

#figure(image("/data/results/d30/fig_E9b_supervised_baseline_rt.png", width: 90%), caption: [監督式分類器（階躍訓練）與兩種參照於漸進漂移與階躍下之偵測率（實際秒；共同集合；區間平均延遲）。監督式分類器之校準目標 FPR 為 0.1107，測試時之實際乾淨誤報率為 0.423，#strong[並非於相同誤報水準下比較]])
#heading(level: 4, numbering: none)[4.7.5.2 E9c：良性共模擾動下之誤報]
#strong[動機]：E9b 顯示以絕對水準為輸入之監督式分類器亦能偵測漸進漂移，其代價為較高之乾淨誤報率。空間共識參照之設計預期為：#strong[全場域共同之變化]（例如負載上升使所有 cell 之 delay 同時上升）#strong[會被同窗共識抵銷]，而以絕對水準或自身歷史為參照者不具此性質。本實驗以合成之良性共模擾動檢驗此預期；結果顯示其於乘法擾動下只部分成立，且時間自我參照之表現與空間參照相當（發現 2）。

#strong[設計]：沿用 E9／E9b 之資料、樣本、尺度與門檻；監督式分類器沿用 E9b 之已訓練模型。自模擬時間第 150 秒起，#strong[所有 mmWave cell] 之 delay 同乘一倍率：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 2, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([擾動], [方式]),
  [共模階躍], [同乘 g，g ∈ {1.1, 1.2, 1.3, 1.5}],
  [共模漂移], [同乘 1 \+ r·(t − 150)，t 為實際秒，r ∈ {0.5, 1, 2} %\/秒],
  [共模下之攻擊], [共模階躍 g \= 1.2 之上，再對受測 cell 注入 E9 之階躍或漂移])]
評估區間為各樣本中第 150 秒以後、三種方法皆可評估之 full\-consensus 窗（54 個 seed × cell 樣本；有 2 個樣本於此區間之共同可評估窗少於 5 個而不計）。前兩類擾動下之告警#strong[全部為誤報]。#strong[口徑]：本節之「基線」為此區間未施加擾動時之告警率（監督式分類器 0.41），與 4.7.5.1 之乾淨誤報率 0.423 不同——後者之評估區間為序列後半段；兩者之彙總方式相同（seed × cell 樣本之告警比例等權平均），差異僅在於所含之窗。腳本內建檢查：三種方法於 E9／E9b 評估區間之乾淨誤報率逐位重現 E9 與 E9b 之輸出。

#strong[結果一：良性共模擾動下之告警率]（括號內為 seed 間範圍）

（第一階段正式版；以現行 cell 歸屬（最後事件）為條件）

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 5, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([擾動], [空間共識參照], [時間自我參照], [監督式分類器], [舊值（累計輸入）空間／時間／監督式]),
  [無（基線）], [0.09（0.04–0.16）], [0.09（0.05–0.16）], [0.41（0.32–0.49）], [0.03／0.02／0.13],
  [共模階躍 ×1.1], [0.10（0.05–0.17）], [0.10（0.05–0.18）], [0.70（0.55–0.78）], [0.03／0.02／0.53],
  [共模階躍 ×1.2], [0.12（0.06–0.18）], [0.12（0.06–0.19）], [0.90（0.81–0.96）], [0.03／0.02／0.96],
  [共模階躍 ×1.3], [0.13（0.07–0.20）], [0.13（0.06–0.21）], [0.97（0.95–0.98）], [0.03／0.04／1.00],
  [共模階躍 ×1.5], [0.16（0.09–0.22）], [0.16（0.09–0.23）], [0.99（0.98–1.00）], [0.05／0.06／1.00],
  [共模漂移 0.5 %\/秒], [0.14（0.07–0.21）], [0.14（0.08–0.20）], [0.89（0.82–0.93）], [0.04／0.02／0.85],
  [共模漂移 1 %\/秒], [0.18（0.11–0.24）], [0.18（0.11–0.24）], [0.94（0.91–0.95）], [0.07／0.03／0.91],
  [共模漂移 2 %\/秒], [0.28（0.17–0.33）], [0.26（0.17–0.30）], [0.96（0.94–0.98）], [0.16／0.07／0.95])]
#strong[結果二：共模階躍 ×1.2 之上注入攻擊之偵測率]（有共模擾動／無共模擾動）

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 5, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([攻擊], [空間共識參照], [時間自我參照], [監督式分類器], [舊值（累計輸入）空間；時間；監督式]),
  [階躍 AF \= 1.3], [0.21／0.17], [0.17／0.13], [0.99／0.97], [0.80／0.60；0.06／0.05；1.00／1.00],
  [階躍 AF \= 1.5], [0.33／0.24], [0.20／0.16], [0.99／0.99], [1.00／1.00；0.07／0.06；1.00／1.00],
  [漂移 1 %\/秒], [0.54／0.54], [0.12／0.10], [0.98／0.94], [0.82／0.82；0.02／0.02；1.00／0.91],
  [漂移 2 %\/秒], [0.77／0.77], [0.13／0.10], [0.99／0.96], [0.91／0.91；0.03／0.02；1.00／0.95])]
#strong[發現]（本次 E9c 之合成共模設定下）：

+ #strong[監督式分類器將良性共模變化判為攻擊]：其基線告警率已達 0.41；全場域 delay 上升 10 % 時升至 0.70，上升 20 % 時為 0.90。其參照為訓練資料之絕對水準分布，無從區分「單一節點偏離」與「全場域共同變化」。
+ #strong[空間共識參照與時間自我參照之告警率皆隨共模階躍緩升]：共模階躍 ×1.1 至 ×1.5 下，空間參照為 0.10–0.16（基線 0.09），時間參照為 0.10–0.16（基線 0.09）。所有 delay 同乘 g 時，同窗中心 #mi("c_j") 亦同乘 g，而尺度 #mi("s") 凍結，故 #mi("z'_j = g\\,z_j")——乘法共模擾動#strong[並未被抵銷]。於區間輸入下，空間參照於此項已無相對時間參照之優勢；兩者皆遠低於監督式分類器。
+ #strong[共模漂移下兩種參照之誤報皆上升]：2 %\/秒時空間參照為 0.28、時間參照為 0.26、監督式分類器為 0.96。凍結尺度 #mi("s") 未隨全場域水準調整為其原因之一。
+ #strong[共模階躍 ×1.2 之上之攻擊]：空間參照於漂移攻擊之偵測率與無共模時相同（1 %\/秒：0.54；2 %\/秒：0.77），於階躍攻擊仍僅 0.17–0.33。監督式分類器之偵測率為 0.94–0.99，惟其於同一共模擾動下、#strong[無攻擊]之窗之告警率即達 0.90，不能單獨作為有效區分攻擊之證據。

#strong[意涵（v12 修訂）]：監督式分類器之高偵測率與其對良性全場域變化之高誤報來自同一原因——參照為固定之絕對水準；此點於區間輸入下仍成立。惟 v11 所稱「空間參照可區分單一節點偏離與全場域共同變化」於區間輸入下#strong[只相對於監督式分類器成立]：時間自我參照於本合成設定下之共模告警率與空間參照相當。

#strong[界定]：

- 共模擾動為#strong[合成之理想情境]：所有 cell 以同一倍率變化。實際之全場域負載變化僅部分相關，本結果不代表真實負載變化下之誤報率；真實 trace 之觀察見 4.7.5.3。
- 空間參照之抵銷性質依賴乘法擾動之幅度與凍結尺度；共模漂移下之誤報上升為其限制，以全場域水準正規化尺度之版本#strong[尚未評估]。
- 監督式分類器之結論限於 E9b 之 #raw("level") 變體，非既有工作之重現。

（腳本 #raw("run_E9c_rt.py")；驗證層級：離線合成注入，D\-30 8 seed，區間平均延遲）

#figure(image("/data/results/d30/fig_E9c_common_mode_rt.png", width: 90%), caption: [良性共模階躍與漂移下三種方法之告警率（全部為誤報；實際秒；共同集合）])
#heading(level: 4, numbering: none)[4.7.5.3 E9d：真實 trace 中之其他 cell 背景與乾淨誤報（補充觀察）]
#strong[問題]：監督式分類器之乾淨誤報，是否集中於「同窗其他 cell 高負載、高延遲背景」之窗？此為觀察性分析，用以檢視 E9c 所揭示之機制於真實 trace 中是否有對應，不證明因果。

#strong[設計（事前固定）]：負載代理為 D\-30 aux 之 PHY trace（#raw("RxPacketTrace")，DL）中各 cell 每秒之排程 TB 位元組量（含重傳與解碼失敗之 TB），#strong[不是] PRB 使用率或流量需求；#raw("DlMacStats") 於本資料中僅含 LTE 錨點之固定值紀錄，不予採用。對每個評估窗，以#strong[同窗其他 cell]（不含受測 cell）之正規化負載與正規化 delay 之中位數為場域指標 F、D；依各 seed 之第 75 百分位分為四組，其中 F、D 皆高者稱「#strong[其他 cell 高負載、高延遲背景]」——百分位分組描述的是同窗其他 cell 之相對水準，#strong[不代表時間上之上升]。分組不使用任何告警結果。評估窗為 E9b 之共同集合；樣本單位為 #strong[(seed, cell, 評估窗)]，同一 seed × cell 內之窗彼此相關，非獨立樣本。八個 seed 之 aux 與主檔之一致性經腳本檢查通過。

#strong[結果]（第一階段正式版；以現行 cell 歸屬（最後事件）為條件；共 7,643 個 (seed, cell, 評估窗)；整體告警率：監督式 0.402、空間參照 0.073、時間參照 0.073；舊值 0.107／0.013／0.009）：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 5, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([組別], [樣本數], [監督式分類器告警], [空間參照告警], [時間參照告警]),
  [其他 cell 高負載、高延遲背景], [369], [151（0.409）], [15（0.041）], [17（0.046）],
  [其他 cell 低負載、低延遲背景], [4,165], [1,688（0.405）], [298（0.072）], [304（0.073）])]
- #strong[未觀察到集中現象]：監督式分類器之告警率於高負載高延遲背景與低負載低延遲背景相當（0.409 對 0.405）。分組樣本數與舊版不同（高背景組 369，舊 486），因區間延遲改變了 D 之分組。
- #strong[各 seed 不一致]：監督式分類器之高背景組高於低背景組者為 4／8。
- 敏感度（監督式分類器，高背景組對低背景組）：第 50 百分位分組 723／1,757（0.411）對 680／1,743（0.390），同方向者 6／8；僅計新傳輸 132／349（0.378）對 1,691／4,146（0.408）；第 90 百分位 10／29（0.345）對 2,484／6,123（0.406）。
- 空間參照於高負載高延遲背景之告警率為 0.041，低於其於低背景組之 0.072；高於低背景組者 1／8 個 seed。

#strong[解讀]：於 D\-30 之真實 trace 上，#strong[未觀察到] E9c 之合成共模機制所預期之「誤報集中於其他 cell 高負載高延遲背景」；此結論與舊輸入相同。前版之 7 UE 資料曾觀察到約 1.8 倍之差異（樣本 41 對 497，且各 seed 不一致），於 D\-30 上未重現。故 E9c 之結論應限於其合成之理想共模情境，不得以本節作為其於真實負載變化下成立之佐證。（腳本 #raw("run_E9d_rt.py")；驗證層級：觀察性關聯，D\-30 8 seed，區間平均延遲）

#heading(level: 4, numbering: none)[4.7.5.4 E\-i：語意錯置對原系統之影響（診斷，v12 新增）]
#strong[問題]：若原系統（v11）之凍結尺度不變、只把輸入換成區間平均延遲，其行為如何？此即「原系統在其校準時所假設之輸入語意被更正後」之表現，用以量化語意錯置之影響，不作為新的操作點。

#strong[設計]（#raw("Si_interval_correction_spec_v0.md") §6、Q\-2）：對受測 seed #mi("k")，尺度沿用其餘七 seed 之#strong[原累計輸入]、原公式算出之 #mi("s_{\\mathrm{old}}^{(-k)}")（0.052–0.056 ms），輸入改為區間平均延遲；τ\_S、注入與其他設定不變。腳本 #raw("run_Ei_diagnostic.py") 之內建檢查 K1（資料 md5 與凍結檔相同）、K2（尺度依受測 seed 取用）於正式版通過；自我檢查 K3（輸入改回累計時逐位重現主結果）於 2026\-11\-14 實作時執行通過，未於正式版重跑。本節採以窗索引為單位之原始評估集合（#raw("Si_reference_ablation.py")／#raw("run_E9_operating_regime.py") 之口徑），與 4.7.4 之共同集合不同；同口徑之 E\-ii（新尺度）乾淨誤報率為 0.111／0.101。

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 3, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([項目], [空間共識參照], [時間自我參照]),
  [乾淨 FPR], [0.372], [0.331],
  [漂移 0.1 %\/秒], [0.38], [0.33],
  [漂移 0.2 %\/秒], [0.45], [0.33],
  [漂移 0.5 %\/秒], [0.69], [0.32],
  [漂移 1 %\/秒], [0.83], [0.32],
  [漂移 2 %\/秒], [0.92], [0.34],
  [漂移 4 %\/秒], [0.95], [0.48],
  [漂移 8 %\/秒], [0.98], [0.81],
  [漂移 15 %\/秒], [0.99], [0.96],
  [階躍 AF \= 1.2（onset）], [0.49（0.88）], [0.38（0.89）],
  [階躍 AF \= 1.3（onset）], [0.61（0.98）], [0.41（0.98）],
  [階躍 AF \= 1.4（onset）], [0.72（0.98）], [0.43（1.00）],
  [階躍 AF \= 1.5（onset）], [0.80（1.00）], [0.46（1.00）])]
#strong[發現]：沿用舊尺度時，兩種參照之乾淨誤報率升至 0.372／0.331，約為 E\-ii 之 3.3 倍；漂移與階躍之偵測率雖高（空間參照 0.5–2 %\/秒為 0.69–0.92），但係於約 0.37 之誤報水準下取得。故#strong[原系統之凍結校準不能直接沿用至區間語意]，v11 之 S\_i 操作點（τ\_S \= 4 配合累計輸入之尺度）於更正語意後不成立；4.7.4–4.7.5.3 之數字皆以新尺度（E\-ii）為準。

（輸出 #raw("data/results/d30_delay_reconstructed/E_i/")；驗證層級：離線診斷）

#heading(level: 4, numbering: none)[4.7.5.5 同條件偵測方法比較：同資料、同攻擊、相同之誤報校準目標（v12.2 新增；事後修正兩次，須揭露）]
（內部代號 C3，見規格檔名；與研究貢獻 C3 無關。）

#strong[動機]：E9b 未於相同誤報水準比較（4.7.5.1）。本實驗以同一資料（D\-30 區間平均延遲，第一階段重建；以現行 cell 歸屬為條件）、同一攻擊、同一誤報校準目標（實際測試誤報見下表），比較九種方法。規格 #raw("docs/thesis/C3_same_condition_comparison_spec_v0.md")（執行前定案），腳本 #raw("scripts/advisor_20261118/run_C3_comparison.py")。

#strong[設計]：56 個 (seed, cell) 序列，8\-fold LOSO（每 fold 留一 seed 測試）。門檻 \= 訓練 seed 乾淨序列後半段之逐窗誤報 1%；CUSUM 以 ARL0 ≈ 1000 校準（k \= 0.5）。攻擊自序列中點起至結束：delay 階躍 ×1.2／1.3／1.5（調高）、×0.9／0.8／0.6（調低）、漂移↓ 1 %\/秒、漂移↑ 1 %\/秒（有上限）。方法：M1 範圍檢查（訓練極值）、M2 時間自我參照、M3 peer 線性雙側（＝4.7.4 空間參照）、M4 peer 對數雙側、M5 peer 對數單側（下）、M6 peer 對數 CUSUM（上／下）、M7 前作類 LSTM（只學 ×1.2–1.5，輸入為 delay 水準）、M8 已知攻擊之監督式 LSTM（學 ×0.6–0.9 與 ×1.2–1.5，輸入為 delay 水準＋peer 對數殘差）。M7、M8：hidden 64、2 層、25 epoch、序列長 10、CPU 確定性。

#strong[檢查]：C3\-1（M3、M5 逐位重現 B1 之 V0e、V3e）通過；C3\-2（LSTM 訓練 balanced accuracy ≥ 0.80，規格 §C3\-2 與程式 #raw("FIT_GATE")；v12.2 誤植為 0.95）通過：M7 0.996–0.998、M8 0.995–0.997。

#strong[事後修正（看過結果後才改）]：

- v0：LSTM 門檻取自已擬合之訓練序列，測試誤報 0.298／0.518，未達同誤報，該版 LSTM 列作廢。
- v1：改由每 fold 固定一個不參與訓練之校準 seed 取門檻；sigmoid 輸出於 float32 飽和為 1.0（校準 seed 乾淨窗中 1.5–14.3%），8 fold 門檻皆為 1.0，從不告警，結果退化。
- v2（本節數字）：門檻與告警改以 logit（sigmoid 前之值）計算。此為單調轉換，不改模型與校準定義。
- M1–M6 無學習成分，三版逐位相同。

#strong[主指標]：lift ＝ 攻擊段逐窗告警率 − 同序列乾淨段逐窗告警率。「攻擊段是否至少告警一次」不作主指標，因乾淨序列後半段至少告警一次之比例（clean\_any）即達 0.02–0.66（例如 M5 為 0.66）。

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 9, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([方法], [測試乾淨誤報], [clean\_any], [×1.2], [×1.5], [×0.9], [×0.8], [×0.6], [漂移↓ 1 %\/秒]),
  [M1 範圍檢查], [0.0001], [0.02], [0.027], [0.045], [0.000], [0.000], [0.000], [0.000],
  [M2 時間自我參照], [0.018], [0.32], [0.005], [0.023], [−0.004], [−0.008], [−0.018], [−0.009],
  [M3 peer 線性雙側], [0.022], [0.29], [0.016], [0.040], [−0.014], [−0.022], [−0.022], [−0.017],
  [M4 peer 對數雙側], [0.019], [0.43], [0.015], [0.035], [−0.008], [−0.013], [−0.004], [0.005],
  [M5 peer 對數單側（下）], [0.012], [0.66], [−0.005], [−0.008], [0.004], [0.016], [0.103], [0.196],
  [M6 peer CUSUM 下（ARL0 914）], [0.0009], [0.11], [−0.001], [−0.001], [0.007], [0.025], [0.097], [0.110],
  [M6 peer CUSUM 上（ARL0 971）], [0.0033], [0.14], [0.005], [0.019], [−0.001], [−0.003], [−0.003], [−0.001],
  [M7 前作類 LSTM（只學放大）], [0.0149], [0.43], [0.319], [0.674], [−0.011], [−0.013], [−0.008], [−0.011],
  [M8 已知攻擊之監督式 LSTM], [0.0078], [0.39], [0.200], [0.498], [0.041], [0.260], [0.790], [0.686])]
（測試乾淨誤報之 seed 範圍：M7 0.0029–0.0356、M8 0.0010–0.0112；完整數字含 ×1.3、漂移↑ 與偵測延遲見 #raw("data/results/advisor_20261118/C3_comparison.json")。）

#strong[發現]：

+ #strong[於相同之誤報校準目標下（實際測試誤報見上表第一欄，各方法不同），學過攻擊方向之監督式 LSTM 之逐窗偵測力高於全部 peer／CUSUM 檢查]：調低 ×0.6 為 0.79 對最佳統計法 0.10；漂移↓（訓練中未出現之形狀）為 0.69 對 0.20；調高 ×1.5 為 0.50–0.67 對 ≤ 0.05。
+ #strong[只學放大之 LSTM 與範圍檢查對 delay 調低無反應]（lift −0.013～0.000）；peer 單側檢查與 CUSUM 下則有（0.10–0.20）。
+ #strong[peer 檢查於單窗、1% 誤報下之偵測力普遍很低]（多數 lift \< 0.05）；4.7.4 之較高偵測率係於約 10% 之誤報下取得。

#strong[比較之性質]：各方法之實際測試誤報（0.0001–0.022）偏離 1% 之校準目標，且範圍檢查不校準至 1%、CUSUM 以 ARL0 校準；故本節為「各方法於其校準設定下之實際操作點」之並列，lift 之差不是已完全控制誤報代價之比較。測試分布不同使實際誤報偏離校準目標，本身不表示實驗設計錯誤。

#strong[對本研究主張之影響]：撤回「相對監督式方法之較低誤報率」（4.7.5.1）；不主張 peer 檢查之偵測力優於監督式方法。peer 檢查可主張者為：（一）不需攻擊樣本；（二）不需事先知道攻擊方向即可設計（雙側檢查）；惟單側檢查本身帶方向，雙側公式亦不保證兩方向之偵測力相同，「對所有未見方向有效」未獲證明。觀察：只學放大之 M7 對調低無反應。

#strong[限制]：

- M8 之訓練攻擊與測試攻擊出自同一產生器（乘法階躍），其數字為「攻擊型態已知」之樂觀上限；面對未知或會學習之攻擊者之表現未評估（第五章）。
- M8 之輸入含 peer 對數殘差，未做「只用 delay 水準、但學雙向」之消融，故無法區分其優勢來自 peer 特徵或來自學過調低；M7 與 M8 另亦改變注入起點設定，二者之差異不能全歸因於是否學過調低。
- M7、M8 未於全場域共模擾動（E9c）下評估。
- 兩個 LSTM 均為本研究自行實作，#strong[非前作之重現]（前作為 per\-UE 多項 KPM）；前作自報之誤報（≤ 0.07%）不與本表比較。
- LSTM 門檻經兩次事後修正（見上）。

（驗證層級：離線合成注入，D\-30 8 seed × 7 cell，區間平均延遲；輸出 #raw("data/results/advisor_20261118/C3_comparison.json")，v0／v1 輸出保留為 #raw("_v0")／#raw("_v1")）

#heading(level: 3, numbering: none)[4.7.6 文獻基準：單節點時序 LSTM]
#strong[定位]：本節之 LSTM 為#strong[本研究自行實作之預測式自我參照基準]，用以代表「以自身近期觀測預測下一窗、殘差超過門檻即判異常」之一類單節點時序偵測，並回答「為何不直接以節點自身之時序為參照」；其#strong[非與 S\_i 並列之效能對照，亦非任何既有工作之重現]。#strong[範圍界定]：Alimohammadi 等人之偵測器（FNWF 2024 及其後續 IEEE OJCOMS 2026）為以帶標籤注入資料訓練之#strong[監督式時序分類器]，與本基準不同類；本節結論不外推至監督式模型，監督式之對應實作見 E9b（4.7.5.1）。

#strong[規格]：單層 LSTM 預測器（hidden \= 32），以前 10 秒（10 個連續窗）之滑動輸入視窗預測下一秒，異常門檻取訓練殘差 mean \+ 3σ，LOSO，#strong[離線一次訓練、測試時凍結]（無線上更新）。

#block(width: 100%, fill: luma(240), inset: 8pt, radius: 2pt)[#set text(size: 10pt)
#strong[v12 註]：本節未於第一階段重跑。其輸入為 cell 1 之每窗吞吐量增量（4.3.2 已差分，不受累計 delay 之影響），但 cell 1 之列由「最後事件歸屬 LTE」決定（3.3.3），故受 cell 歸屬語意影響，屬歷史版本結果。

#strong[觀測對象之範圍聲明]：本基準沿用前版之設計，採 LTE 錨點之連續序列（前版 7 UE 資料中 mmWave 單節點序列稀疏不連續，無法訓練單節點時序模型），#strong[且其輸入為每窗聚合吞吐量（RxBytes），非 delay]——與 S\_i 為不同物理量、不同節點、不同注入攻擊。二者偵測率#strong[不可直接比較]，故本節數據獨立呈現。參照機制之嚴格對照由 4.7.4 與 4.7.5 承擔。

]
#strong[結果]（LTE 錨點吞吐量序列，吞吐量漂移注入）：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 2, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([攻擊], [LSTM 偵測率]),
  [乾淨序列 FPR], [0.02],
  [突發階梯（\+0.5×mean），full\-window], [0.06],
  [突發階梯，onset 命中率（前 1–5 秒）], [0.12（8 個測試 seed 中 1 個命中）],
  [漂移 0.5 %\/秒], [0.07],
  [漂移 1.0 %\/秒], [0.20],
  [漂移 2.0 %\/秒], [0.49],
  [漂移 4.0 %\/秒], [0.71],
  [漂移 8.0 %\/秒], [0.85],
  [漂移 15.0 %\/秒], [0.93])]
#strong[起始點分析]：階梯攻擊之 onset 命中率為 0.12（8 個測試 seed 中僅 seed 4201 命中），full\-window 偵測率為 0.06。於多數 seed，此幅度之偏移#strong[連起始點都未跨越 mean \+ 3σ 門檻]，而非「抓到起始點後被吸收」。本基準之殘差門檻對「相對於序列自身波動不夠劇烈」之偏移遲鈍；此結論限於本節之單一模型與輸入（LTE 錨點吞吐量），不外推至其他單節點預測式偵測器，亦因物理量不同而不與 4.7.4 對照。

#strong[時間單位]：LTE 錨點於 D\-30 八個 seed 皆為實際連續秒、無空窗（#raw("make_fig_lstm_rt.py") 內建檢查），故本節之「每窗」即「每秒」。（腳本 #raw("lstm_baseline_anchor.py")）

#figure(image("/data/results/d30/fig_lstm_drift_evasion_rt.png", width: 90%), caption: [自我參照 LSTM 基準之漂移偵測曲線（LTE 錨點吞吐量；%\/秒）])
#heading(level: 3, numbering: none)[4.7.7 有效性威脅]
- #strong[v12 註]：本小節之 E13 表與十等分表皆為#strong[累計平均輸入之歷史版本結果]，未於第一階段重跑（E13 屬第二階段，#raw("Si_interval_correction_spec_v0.md") Q\-3），不得與 4.7.4 之新值並讀或用於支持其結論。
- #strong[門檻選擇層級之洩漏與敏感度（E13）]：τ\_S \= 4 之操作點於前版之 7 UE 資料上由全體 seed 掃描選定，並於 D\-30 結果產出前凍結（4.0.3），D\-30 未用於選擇門檻；尺度 #mi("s") 已隔離 held\-out seed。為檢驗結論是否依賴此操作點，於 τ\_S ∈ {3, 3.5, 4, 4.5, 5} 重算殘差層（同 4.7.4：實際秒、共同集合、56 組 seed × cell 樣本等權平均）與融合層（定案之 uebound、#mi("L_H = 1")）：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 10, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([τ\_S], [空間乾淨誤報], [時間乾淨誤報], [空間 0.5 %\/秒], [空間 1 %\/秒], [空間 2 %\/秒], [時間 1 %\/秒], [1 %\/秒差距（seed 範圍）], [融合 trusted], [乾淨誤拒]),
  [3], [0.054], [0.034], [0.74], [0.87], [0.93], [0.04], [\+0.83（\+0.78 至 \+0.85）], [49.7%], [198（1.27%）],
  [3.5], [0.049], [0.032], [0.70], [0.85], [0.92], [0.04], [\+0.81（\+0.76 至 \+0.84）], [50.0%], [174（1.12%）],
  [#strong[4]], [#strong[0.046]], [#strong[0.029]], [#strong[0.65]], [#strong[0.82]], [#strong[0.91]], [#strong[0.03]], [#strong[\+0.79（\+0.73 至 \+0.82）]], [#strong[50.3%]], [#strong[159（1.02%）]],
  [4.5], [0.042], [0.027], [0.61], [0.80], [0.90], [0.03], [\+0.77（\+0.72 至 \+0.80）], [50.5%], [146（0.94%）],
  [5], [0.039], [0.026], [0.57], [0.78], [0.89], [0.03], [\+0.76（\+0.71 至 \+0.79）], [50.7%], [137（0.88%）])]
「差距」為空間與時間參照於 1 %\/秒之偵測率差；括號內為逐 seed 差距之範圍。融合層分母為 15,534 筆有效節點註記；abstain 於各 τ\_S 皆為 0%（D\-30 之全部節點註記皆具備 full consensus，4.7.1）。τ\_S \= 4 之列逐位重現 4.7.4（#raw("run_E9_rt.py")）與 4.9.6.5 之 P3（腳本內建檢查）。#strong[發現]：空間參照於 1 %\/秒之優勢於整個區間皆存在，且每個 seed 皆為正（最小 \+0.71，τ\_S \= 5、seed 4202），故#strong[累計輸入下]之結論不依賴 τ\_S \= 4 之選擇（歷史版本；區間輸入下未驗證，見本小節首之 v12 註）。τ\_S 於融合層之影響有限：τ\_S 由 3 升至 5，乾淨誤拒由 198 筆降至 137 筆、trusted 僅由 49.7% 升至 50.7%，空間參照於 1 %\/秒之偵測率則由 0.87 降至 0.78。#strong[於 D\-30，融合層之可用性主要受 D1 證據支配，而非 τ\_S]（4.9.6.6 之 E14）。（腳本 #raw("run_E13_rt.py")；Fig 4\-7b）

- #strong[證據可用率]：D\-30 之全部節點註記皆具備 full consensus（4.7.1），惟此取決於 UE 密度；7 UE 之前版資料僅 54.8% 之窗具備 full consensus。4.7.4 與 4.7.5 之偵測率不代表低密度場域之全時段覆蓋。
- #strong[誤報率之非穩態（啟動暫態）]：S\_i 之乾淨誤報率於序列中並非定值。以 full\-consensus 之節點註記依序列位置分為十等分：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 4, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([序列位置], [FPR], [平均 #mi("z_j")], [平均 peer 數]),
  [0–10%], [0.086], [1.79], [5.59],
  [10–20%], [0.024], [1.09], [5.60],
  [20–30%], [0.028], [0.99], [5.52],
  [30–40%], [0.023], [1.01], [5.53],
  [40–50%], [0.023], [1.05], [5.50],
  [50–60%], [0.020], [1.01], [5.53],
  [60–70%], [0.021], [1.04], [5.53],
  [70–80%], [0.021], [1.08], [5.56],
  [80–90%], [0.021], [1.02], [5.48],
  [90–100%], [0.026], [1.07], [5.48],
  [#strong[前半段]], [#strong[0.037]], [—], [—],
  [#strong[後半段]], [#strong[0.022]], [—], [—])]
誤報集中於序列最前之十分之一（約前 30 秒）：該段誤報率 0.086、平均 #mi("z_j") 1.79，其後各段為 0.020–0.028、平均 #mi("z_j") 約 1.0；同期平均 peer 數維持於 5.5–5.6 無趨勢，故此現象非證據可用性變化所致，而係模擬啟動後跨節點延遲離散度收斂前之暫態。前半段誤報率為後半段之 1.7 倍。意涵有二：4.7.4 之乾淨誤報率#strong[不可外推至場域啟動初期]；並為 4.9.4 之 clean bootstrap 假設提供量化依據——實際部署應設置啟動排除期，於該期間將 S\_i 判定降級為 abstain，其長度校準列為後續工作。

#strong[口徑說明]：上表由 #raw("run_E13_rt.py") 產生（與以窗索引為單位之 #raw("run_E13_tauS_sensitivity.py") 逐列相同，腳本內建檢查；節點註記層級合併，依序列位置 ⌊10·i／n⌋ 分組）。前半段／後半段為十等分誤報率之未加權平均，直接合併計算亦為 0.037／0.022。此口徑與 4.7.4 之 0.046（seed × cell 樣本之等權平均，僅含後半段之共同集合）不同，二數不可互換。另須指出收斂並非各 seed 皆然：合併計算下 seed 4205 之前後半段分別為 0.034 與 0.037，seed 4202 為 0.049 與 0.046。

- #strong[多節點共識操縱]：S\_i 以「多數鄰居誠實」為前提。抗串謀強度見 4.10（D\-30：#mi("m^*_{S,50} = 4")）。
- #strong[樣本規模]：8 個 seed；seed 間之範圍已列於各表括號內。
- #strong[物理詮釋]：延遲之離散度為經驗可觀測性，非物理定律；且區間延遲之離散度（CV 中位數 0.275）遠高於舊版以累計平均算得之值。
- #strong[輸入語意與 cell 歸屬]：4.7.4–4.7.5 之數字使用重建之區間平均延遲，精度僅於單一 R\-5 run 驗收；peer 集合依最後事件之 cell 歸屬，且 delay 混有 LTE 路徑之 PDU（4.7.1）。per\-cell 歸屬之重評屬第二階段。

#figure(image("/data/results/d30/fig_E13_tauS_sensitivity_rt.png", width: 90%), caption: [τ\_S 敏感度：漂移偵測率、乾淨誤報率（實際秒；共同集合）與融合層 trusted 比例、乾淨誤拒數])
#heading(level: 3, numbering: none)[4.7.8 慢性中毒題組：偵測前沿、偵測前偏差、貼門檻攻擊與校準期中毒]
#block(width: 100%, fill: luma(240), inset: 8pt, radius: 2pt)[#set text(size: 10pt)
#strong[v12 註]：本節（Q1、Q2、Q4、Q6 與 E17）#strong[未於第一階段重跑]，全部為累計平均輸入之歷史版本結果，與 4.7.4 之新值不可並讀；區間輸入下之重跑列為第二階段。另，區間輸入下尺度 #mi("s") 增為約 3.1 倍（4.7.1），Q4 中可維持而不被偵測之偏差（約 τ\_S·s）預期隨之增大；此為推論，未量測。

]
#strong[動機]：4.7.4 與 4.7.5 以注入區間偵測率衡量。對慢性中毒而言，更貼近損害之量為#strong[被偵測前已灌入多少偏差]，以及#strong[知道門檻之攻擊者能長期維持多少偏差]。本節以同一資料與實作回答四個問題（Q1、Q2、Q4、Q6）。

#strong[共同設定]：與 4.7.4 相同（D\-30、LOSO 尺度、τ\_S \= 4、注入起點為序列中點、漂移速率與時間參照皆以#strong[實際秒]計、主結果於#strong[共同集合]評估；統計單位為 seed）。偵測準則採 #strong[2c]——注入後首次於#strong[實際連續 2 秒]皆 #mi("z_j > \\tau_S")（兩秒皆須於比較集合中），對應 #mi("L_C = 2") 之持續概念；另以未注入序列計算同一準則之#strong[乾淨底線]（未注入時於同一區間觸發之機率）。所有攻擊僅作用於 delay，為本研究觀測維度上之合成注入。腳本內建檢查：Q4 之 oracle 攻擊（β \< 1）依構造不可偵測、Q6 未中毒之空間乾淨誤報等於 4.7.4，以及人工核對後建立之回歸基準，皆通過。

#heading(level: 4, numbering: none)[Q1 偵測前沿]
#mi("r^*_D") 定義為「於注入後 #mi("D") 秒內偵測之機率 ≥ 0.5，且高於乾淨底線」之最低漂移速率（速率格點 0.1–15 %\/秒，共 13 點）：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 5, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([#mi("D")（秒）], [空間 #mi("r^*_D")], [空間乾淨底線], [時間 #mi("r^*_D")], [時間乾淨底線]),
  [5], [15 %], [0.04], [15 %], [0.02],
  [10], [4 %], [0.04], [6 %], [0.02],
  [20], [2 %], [0.05], [6 %], [0.04],
  [40], [0.75 %], [0.05], [6 %], [0.04])]
#strong[發現]：時間參照之 #mi("r^*_D") 自 #mi("D = 10") 秒起停在 6 %\/秒，延長觀察時間無益——偏移被前 10 秒之滑動參照吸收。空間參照之 #mi("r^*_D") 隨 #mi("D") 延長而下降，40 秒內 0.75 %\/秒即過半偵測。#mi("D = 5") 秒時兩者皆需 15 %\/秒，即於注入後極短時間內，兩種參照皆無法區分慢速漂移與雜訊。乾淨底線於 D\-30 非零（空間 0.04–0.05、時間 0.02–0.04），#mi("r^*_D") 之定義已要求偵測機率高於此底線。

#heading(level: 4, numbering: none)[Q2 偵測前已灌入之偏差]
偏移以受測 cell 平均 delay 之百分比計；偵測秒數與偏移為#strong[已偵測樣本]之中位數（準則 2c）；末欄為時間參照全部樣本之偏移中位數，未偵測者以比較集合中最後一窗之偏移代入（設限）。樣本數 55：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 8, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([速率], [空間：未偵測比例], [空間：偵測秒數], [空間：偵測時偏移], [時間：未偵測比例], [時間：偵測秒數], [時間：偵測時偏移], [時間：全樣本偏移（設限）]),
  [0.1 %\/秒], [0.78（0.57–1.00）], [91], [9.1 %], [0.93（0.71–1.00）], [39], [3.9 %], [14.9 %],
  [0.2 %\/秒], [0.33（0.00–0.43）], [107], [21.4 %], [0.93（0.71–1.00）], [39], [7.8 %], [29.8 %],
  [0.5 %\/秒], [0.02（0.00–0.14）], [53], [26.5 %], [0.93（0.71–1.00）], [39], [19.5 %], [74.5 %],
  [1 %\/秒], [0.02（0.00–0.14）], [28.5], [28.5 %], [0.93（0.71–1.00）], [37.5], [37.5 %], [149.0 %],
  [2 %\/秒], [0.02（0.00–0.14）], [15], [30.0 %], [0.85（0.57–1.00）], [56], [112.0 %], [298.0 %],
  [4 %\/秒], [0.02（0.00–0.14）], [9], [36.0 %], [0.47（0.29–0.71）], [27], [108.0 %], [296.0 %])]
#strong[發現]：

+ #strong[空間參照放行之偏差隨速率變化有限，且高於門檻對應之偏差]：≥ 0.5 %\/秒時，偵測時偏移為 26.5–36.0 %，偵測秒數則由 53 秒縮短至 9 秒（0.5 → 4 %\/秒）。門檻 #mi("\\tau_S \\cdot s") 於各 fold 為 0.208–0.223 ms；偵測時偏移高於 Q4 中 oracle 攻擊者恰低於門檻時之偏差（約 24 %），表示自越過門檻至被準則 2c 判定之間尚有延遲。此延遲之組成#strong[未分解]。
+ #strong[0.1 %\/秒時空間參照亦無有效偵測]：未偵測比例 0.78；0.2 %\/秒時為 0.33（seed 間 0.00–0.43），偵測時偏移 21.4 %。
+ #strong[時間參照於 ≤ 1 %\/秒時實質未偵測]：未偵測比例皆為 0.93，且不隨速率改變；其餘 0.07 之「偵測」於各速率皆落在同一時點（中位數 37.5–39 秒），與其乾淨底線（#mi("D = 40") 秒時 0.04）同量級，應視為誤報而非對漂移之偵測。偏差可持續累積至序列結束（設限之中位數於 1 %\/秒為 149.0 %、2 %\/秒為 298.0 %）。

#heading(level: 4, numbering: none)[Q4 貼門檻之適應型攻擊者]
攻擊者白箱知道 #mi("s") 與 #mi("\\tau_S")，每秒上報「參照值 \+ β·τ\_S·s」（上偏）。三種知識假設：#strong[oracle]——上報前已知同窗 peer 中位數，為上界，實際 O\-DU 無法於上報前取得他節點同窗值；#strong[lag1]——僅知最近一個已評估窗之 peer 中位數；#strong[own]——不知 peer，僅於自身真值上加固定偏移。對時間參照而言，參照即攻擊者自身前 10 秒之上報，故 oracle 與 lag1 等價（輸出逐位相同）。

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 6, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([參照], [知識], [β], [偵測率], [平均誘導偏差], [注入區間末之偏差]),
  [空間], [oracle], [0.5], [0.00], [10.6 %], [9.8 %],
  [空間], [oracle], [0.99], [0.00], [23.6 %], [22.8 %],
  [空間], [lag1], [0.5], [0.00（0.00–0.00）], [10.6 %], [9.8 %],
  [空間], [lag1], [0.9], [0.13（0.07–0.21）], [21.2 %], [20.5 %],
  [空間], [lag1], [0.99], [0.44（0.41–0.48）], [23.6 %], [22.8 %],
  [空間], [own], [0.99], [0.51（0.45–0.54）], [26.3 %], [26.3 %],
  [時間], [oracle／lag1], [0.5], [0.00], [182.6 %], [353.1 %],
  [時間], [oracle／lag1], [0.99], [0.00], [359.8 %], [697.3 %],
  [時間], [own], [0.99], [0.04（0.01–0.10）], [26.3 %], [26.3 %])]
#strong[發現]：

+ #strong[空間參照下可維持之偏差於本資料中有界]：#mi("\\tau_S \\cdot s") 限制的是「上報值與同窗 peer 中心之差」#mi("|v_j - c_j|")，而非「上報值與自身真值之差」；後者另含 peer 中心與自身真值之自然差異 #mi("c_j - x_j")。本資料中 oracle 攻擊者（β \= 0.99）全程未被偵測，其相對自身真值之偏差平均 23.6 %、注入區間末 22.8 %，不隨時間增長。約 24 % 為本次資料之觀察值，非普遍保證。
+ #strong[時間參照下偏差於序列長度內持續累積]：攻擊者以自身歷史上報推移參照，β \= 0.99 時平均偏差 359.8 %、注入區間末達 697.3 %，且全程未被偵測。
+ #strong[較實際之 lag1 攻擊者須於偏差與曝光間取捨]：β \= 0.9 時維持 21.2 % 之偏差，偵測率為 0.13（0.07–0.21）；β \= 0.99 時偵測率升至 0.44。
+ #strong[固定偏移（own）對時間參照近乎不可見]：偵測率 0.04，與時間參照之乾淨誤報（0.029）相當；依構造，固定偏移於注入後 10 秒即完全進入其參照。同一固定偏移於空間參照下之偵測率為 0.51。

#strong[界定]：空間參照所限制者為 #mi("|v_j - c_j| \\le \\tau_S \\cdot s")，其實質大小取決於尺度 #mi("s")（見 Q6）、門檻 τ\_S（4.7.7），以及 peer 中心相對受測節點真值之自然偏離。約 24 % 之放行偏差與 4.12 之 ×0.8 階躍幅度相當，其下游影響見 4.12.4——#strong[有界不等於無害]。

#heading(level: 4, numbering: none)[Q6 校準期中毒]
凍結尺度 #mi("s") 由 training seeds 之資料估計（4.7.2）。若攻擊者於校準期間即已控制 #mi("k") 個 cell（取出現窗數最多者，屬最壞情況），並自 #mi("t = 0") 起竄改（漸進 0.5／1／2 %\/秒，或固定 \+50／100／200 %），#mi("s") 將被灌大，測試期之偵測率隨之下降。下表為空間參照、共同集合；範圍跨六種竄改方式與八個 fold（#mi("k = 4")、5 為補充實驗 E17）：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 6, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([#mi("k")], [校準資料受污染比例 ε], [#mi("s") 放大倍數], [測試期 1 %\/秒偵測率], [測試期 2 %\/秒偵測率], [乾淨誤報率]),
  [0（未中毒）], [0], [1], [0.82（0.81–0.84）], [0.91（0.90–0.92）], [0.046],
  [1], [0.15–0.16], [1.33–1.51], [0.75], [0.87], [0.039],
  [2], [0.30–0.31], [2.03–2.37], [0.61–0.63], [0.80–0.81], [0.022],
  [3], [0.45–0.47], [3.56–6.69], [0.08–0.33], [0.50–0.66], [0.009–0.010],
  [4（E17）], [0.61–0.62], [2.85–26.24], [0.00–0.48], [0.00–0.73], [0.000–0.011],
  [5（E17）], [0.75–0.77], [1.64–40.88], [0.00–0.69], [0.00–0.84], [0.000–0.035])]
#strong[發現]：

+ #strong[單一 cell 即可削弱偵測，但幅度有限]：D\-30 每 seed 有 7 個 mmWave cell 上報，單一 cell 佔校準資料 15–16 %。其於校準期被控制時，#mi("s") 放大 1.33–1.51 倍，1 %\/秒之偵測率由 0.82 降至 0.75。
+ #strong[偵測率隨受控 cell 數快速下降]：#mi("k = 2")（ε 0.30–0.31）時 1 %\/秒之偵測率為 0.61–0.63；#mi("k = 3")（ε 0.45–0.47）時 #mi("s") 放大 3.56–6.69 倍，偵測率降至 0.08–0.33。#mi("k \\le 3") 時 ε 皆未超過 MAD 之崩潰點 0.5。
+ #strong[超過崩潰點後（E17，#mi("k = 4")、5；規格 #raw("E15_E18_supplementary_spec.md") v1；主結果產出後新增之補充實驗，規格先於結果定案）]：ε 為 0.61–0.77。漸進竄改使 #mi("s") 放大 6.5–40.9 倍，1 %\/秒之偵測率降至 0.00–0.03（#mi("k = 4")、2 %\/秒漂移竄改時為 0.00）。固定偏移竄改之放大倍數反而較小，且隨 #mi("k") 增加而下降（\+50 % 時 #mi("k = 4") 為 2.85–3.25 倍、#mi("k = 5") 為 1.64–1.95 倍），偵測率因而回升（#mi("k = 5")、\+50 % 時 1 %\/秒為 0.69）——中位數本身已移入被竄改群，MAD 改為量測被竄改群內部之離散度。#strong[此為崩潰後之非單調行為，不代表較安全]：此時尺度之中心已由攻擊者決定。#mi("k \\le 3") 之結果與回歸基準逐位相同（內建檢查）。
+ #strong[凍結尺度為信任根]：4.9.4 之 clean bootstrap 假設不僅是誤報率之前提（4.7.7），亦為#strong[安全性前提]——校準須於可信條件下完成（例如部署前之受控量測），且校準資料不得與營運期資料混用。以同窗共識殘差而非原始 delay 估計尺度，或逐 cell 估計後取中位數，可能降低單一 cell 之影響，#strong[尚未評估]。

（腳本 #raw("run_slow_poisoning_rt.py")；規格 #raw("docs/thesis/planB_realtime_spec.md")；驗證層級：離線合成注入，D\-30 8 seed）

#figure(image("/data/results/d30/fig_slow_Q1_frontier_rt.png", width: 90%), caption: [Q1：不同觀察秒數下之偵測機率（虛線為乾淨底線；實際秒；共同集合）])
#figure(image("/data/results/d30/fig_slow_Q2_bias_rt.png", width: 90%), caption: [Q2：全部樣本之偏移中位數，未偵測者以比較集合中最後一窗之偏移代入（設限）。#strong[與上表空間欄之口徑不同]：上表為僅含已偵測樣本之中位數])
#figure(image("/data/results/d30/fig_slow_Q4_hugging_rt.png", width: 90%), caption: [Q4：貼門檻攻擊之偵測率與注入區間末之偏差])
#heading(level: 2, numbering: none)[4.8 H\_i：跨小區成員轉移一致性驗證]
#block(width: 100%, fill: luma(240), inset: 8pt, radius: 2pt)[#set text(size: 10pt)
#strong[定位]：H\_i 負責#strong[成員轉移可信度]之驗證，設計上用以補 C\_i 之涵蓋邊界（4.6.6 守恆式串謀）；惟其於本資料之實證效力限於規則行為驗證，不稱其為守恆式替換之主要防線（4.6.6）。D1 以 Hampel identifier 之 robust z 量化證據強度，D2 為情境特定之規則斷言；二者之輸出經 4.4.0 之規則映射為信任狀態。

]
#heading(level: 3, numbering: none)[4.8.1 兩個維度與乾淨基線]
#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 3, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([維度], [乾淨基線（實測）], [判定型態]),
  [#strong[D1 成員消失]], [UE 之最後事件連續歸屬 LTE 之窗數（與 mmWave 鏈路劣化相關）呈重長尾：12,252 個停留事件中 98.0% ≤ 12 窗，最長 160 窗，長尾集中於 edge UE], [非參數（Hampel robust z）],
  [#strong[D2 成員瞬移]（情境特定之斷言）], [UE 之 serving mmWave cell 於單次執行內皆維持固定；任何跨 mmWave cell 轉移（含經 LTE 者）於 D\-30 全部 240 個 UE\-run 中皆未發生（#raw("audit_delay_cv.py")）], [架構斷言])]
#strong[PHY 層交叉驗證（「最後事件歸屬 LTE」與 mmWave 鏈路之關係）]：以 #raw("MmWaveSwitchStats") 之開機 attach 建立 (cell, RNTI) → IMSI 對應（D\-30 無合法 mmWave 換手，且該檔無任何後續切換事件），逐秒比對 mmWave PHY 下行紀錄（#raw("RxPacketTrace")）與 RLC 報表狀態（8 個 seed；#raw("run_E20_error_rates.py")，輸出 #raw("E20_error_rates.json") → #raw("phy_check")）：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 3, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([], [RLC：最後事件歸屬 mmWave 之 UE\-秒（41,523）], [RLC：最後事件歸屬 LTE 之 UE\-秒（30,477）]),
  [該秒仍有 mmWave PHY 下行傳輸之比例], [—], [1.0（8／8 seed）],
  [SINR（UE\-秒平均之中位數，8 seed 範圍）], [7.7 至 10.9 dB], [−11.7 至 −3.2 dB],
  [TB 損壞比例（平均，8 seed 範圍）], [0.25–0.30], [0.59–0.74],
  [mmWave PHY 位元組／秒（中位數，8 seed 範圍）], [440,039–848,349], [28,929–38,779])]
故本文所稱「最後事件歸屬 LTE 之停留」於 D\-30 中#strong[與 mmWave 鏈路劣化相關]，UE 並未離開其 mmWave cell。#strong[v12 修訂]：R\-5 旁路檔顯示每個 UE 每窗皆有 LTE 路徑之 PDU，cell 欄記錄的是「該窗最後一筆事件屬於哪一路」；mmWave 鏈路變差時 mmWave PDU 變少，最後事件落在 LTE 之機率上升，與上表一致（R\-5 窗 0–6 之探索性量化：依 LTE 樣本比例四分位，歸屬 LTE 之比例 0.075 → 0.585 單調遞增），但 LTE 只占約 1 % 之樣本時仍有 7.5 % 被記為 cell 1。故上表為#strong[支持性之相關，不是機制證明]；不得寫成「只有 LTE 連線」或「等於 mmWave 劣化」。最後事件之對帳（記錄窗末最後一次覆寫之時間、方向與 cell）待 R\-7b。#strong[不宣稱]：劣化之成因（遮蔽、距離、干擾）未逐一歸因。H\_i 之判定對象仍為報表層級之歸屬序列與凍結基線是否一致；惟基線之語意由「鏈路劣化之停留」改為「最後事件歸屬」後，D1 所偵測者之意義須於第二階段（per\-cell 歸屬）重評。

#heading(level: 3, numbering: none)[4.8.2 D1：為何非參數]
卡方適合度檢定比對停留時間與幾何分布（參數以最大概似估計，#mi("\\hat p") \= 1／平均停留；分箱 {1, 2, 3, 4, 5, ≥ 6}，自由度 4）：常駐群 χ² \= 236.3、邊緣群 χ² \= 596.1、全體 χ² \= 1,786.8，均遠超 α \= 0.01 之臨界值 13.28——所測之幾何分布擬合不佳（同一 UE 之多個停留事件相依，有效樣本數小於事件數，χ² 之 p 值僅供參考），故採不依賴該分布假設之非參數方法；本檢定不涵蓋其他參數族。

#heading(level: 3, numbering: none)[4.8.3 D1：Hampel identifier]
#strong[（a）Hampel identifier]（Hampel, 1974；Leys et al., 2013）：

z\_d(x,t) \= ( d(x,t) − median\_x ) \/ ( 1.4826 · MAD\_x )

#mi("d(x,t)") 為當前連續 最後事件歸屬 LTE 停留窗數。#strong[缺值語意]：UE 於某窗未出現於任何報告時，無法確認其仍為 最後事件歸屬 LTE，故中斷本段計數，再次觀測到 最後事件歸屬 LTE 時自新段起算；中斷不代表正常或 trusted。基線估計採相同定義，被缺報截斷之停留片段不列為完整停留事件（2026\-10\-06 修訂，見 4.4.0（四）之 E11 揭露）。#mi("z_d") 即 robust z（與 S\_i 同一統計量，門檻各自校準）。MAD \= 0 時尺度取 1 窗之下限。

#strong[基線]：採 #strong[per\-UE\-index 基線]——跨 run 以 IMSI 編號彙整停留事件（同號 UE 於不同 run 之位置不同，故非部署意義下之個別裝置基線）；事件數 \< 8 時退回 resident／edge 群層級經驗分布。基線由乾淨資料一次估計、#strong[永不線上更新]——否則攻擊者可緩慢養高某 UE 之停留以撐大門檻，此即 4.7.3 所述滑動更新參照之同一弱點。此需 clean bootstrap（信任根）假設。

#strong[（b）經驗 p 值]：

p\_emp(x,t) \= ( 1 \+ |{ d' ∈ 乾淨停留(x) : d' ≥ d }| ) \/ ( n \+ 1 )

採 (1\+·)\/(n\+1) 避免有限樣本得 0。#mi("p_{\\text{emp}}") 作為事後解釋性統計（其隨注入強度單調下降），#strong[不參與 4.8.5 之證據分級]；z 與 p 之聯合決策為實作已支援之設定，列為後續敏感度分析。

#heading(level: 3, numbering: none)[4.8.4 D2：觀測層級之瞬移斷言]
#block(width: 100%, fill: luma(245), inset: 6pt)[#set text(size: 8.5pt)
#raw("teleport(x,t) := (x 於 t−1 掛 mmWave A) ∧ (x 於 t 掛 mmWave B≠A) ∧ (中間無 最後事件歸屬 LTE 過渡窗)
D2 violated ⟺ ∃x: teleport(x,t)", block: true)]
此判準類似身分安全領域之 impossible travel detection：同一身分於時間上不可能之位置轉移。#strong[宣稱之範圍]：D2 為由本場景觀察到之移動行為導出之#strong[情境特定斷言]，其「必經 LTE 錨點」之前提於其他移動模型、觀測粒度或不採 MC 雙連結之部署下未必成立；本研究不宣稱其為一般性之架構不變量。

#strong[乾淨基線與其限制]：D\-30（8 seed × 300 s，2,400 窗，240 個 UE\-run）中跨 mmWave cell 之轉移為 0——無論中間是否經過 最後事件歸屬 LTE 窗，沒有任何 UE 於單次執行內更換 serving mmWave cell。#strong[須誠實指出：合法之跨 cell 轉移本身即未發生]（v12 補註：此「轉移」亦以最後事件之 cell 歸屬定義；於此歸屬下每窗約三成 UE 被記為 cell 1 而從 mmWave cell 平均中消失，S\_i 之 cell 母體因此每窗變動，4.7.1），故乾淨基線為 0 屬 vacuous，「必經 LTE 錨點」之規則未曾經合法換手檢驗。注入瞬移（239 例，目標 cell 以確定性公式指定）得 239／239 偵測、乾淨誤報 0，#strong[屬設計必然（by construction）]。該注入須同時改動來源與目的兩個 mmWave 節點之上報，故其檢驗的是規則是否如定義運作，#strong[不是對單一受攻陷節點攻擊之偵測率]；D2 之實證效力因此限於「規則行為驗證」。

#heading(level: 3, numbering: none)[4.8.5 D1 與 D2 於融合規則中之角色]
#block(width: 100%, fill: luma(240), inset: 8pt, radius: 2pt)[#set text(size: 10pt)
信任狀態之定義與判定條件見 4.4.0，此處不重複定義。

]
#heading(level: 4, numbering: none)[（一）證據強度與規則代碼之對應]
#mi("H_i")\-D1 之輸出為#strong[證據強度]，而非信任狀態：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 4, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([#mi("H_i") 輸出], [條件], [於 4.4.0 中觸發之規則], [單獨成立時之狀態]),
  [D2 violated], [存在瞬移事件], [#raw("R1_D2_VETO")（L1）], [rejected],
  [D1 \= strong], [#mi("z_d \\geq \\tau_H^{\\text{reject}}")], [#raw("R2_D1_STRONG")（L2）], [low\-trust],
  [D1 \= strong，且 #mi("S_i") 同窗違反並指向同一節點], [—], [#raw("R2_SI_D1_BOUND")（L2）], [rejected],
  [D1 \= strong，且 #mi("S_i") 同窗違反但指向不同對象], [—], [#raw("R2_SI_D1_UNBOUND")（L2）], [low\-trust],
  [D1 \= warning], [#mi("\\tau_H^{\\text{warn}} \\leq z_d < \\tau_H^{\\text{reject}}")], [#raw("R2_D1_WEAK")（L2）], [low\-trust],
  [D1 \= none], [#mi("z_d < \\tau_H^{\\text{warn}}")], [不觸發], [由其他殘差決定])]
#strong[D1 本身不產出信任狀態]。最右欄為該證據於其他殘差均無異常時經 4.4.0 所得之結果；同窗若另有 #mi("C_i") 違反或 D2 瞬移，則 L1 優先。D1 單獨成立時僅影響其所歸屬之節點（UE 綁定，4.9.6.5）；無節點可歸屬之 D1 證據留存為 UE 層級紀錄，不改變任何節點之信任狀態。

#heading(level: 4, numbering: none)[（二）D2 為硬否決、D1 不為硬否決之理由]
#strong[D2 為情境特定之斷言]：於本場景觀察到之移動行為下，UE 更換 serving mmWave cell 必經 LTE 錨點過渡，「前一窗掛 A、當窗掛 B、中間無錨點過渡」構成結構上不應出現之觀測，其判定不依賴可調門檻，故與 #mi("C_i") 同置於 L1。

#strong[D1 為統計推論]：判定結果依賴 #mi("\\tau_H") 與基線品質。更關鍵者為裝置並非同質——結構性訊號較差之 UE 長時間掛載於錨點屬其正常移動性行為，其誤報率於 8 個 seed 皆高於常駐 UE（4.8.6；未作顯著性檢定）。#strong[若允許 D1 單獨硬否決，此類正常行為將直接導致誤拒。] 4.8.6 之 edge UE 高誤報率並非對本設計之否定，而正是本設計之依據。

#heading(level: 4, numbering: none)[（三）交叉佐證之綁定要求及其限制]
#raw("R2_SI_D1_BOUND") 要求兩項證據指向同一節點。然 D1 量測#strong[連續 最後事件歸屬 LTE 停留窗數]，觸發 D1 之 UE 必然掛載於 LTE 錨點。#strong[若以「當窗掛載之 cell」為歸屬依據（window 對照政策），該規則不存在合法觸發路徑]（實測見 4.9.6.2）。定案之 uebound 政策以「UE 消失前之 serving mmWave cell」為歸屬依據，同時適用於 D1 單獨成立與交叉佐證兩種情形；此修正使交叉佐證可觸發，代價為乾淨資料上出現 159 筆誤拒（1.0%；4.9.6.5）。

#heading(level: 3, numbering: none)[4.8.6 D1 偵測效能（誠實的部分成功）]
LOSO，注入超時消失，per\-seed 明細：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 6, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([seed], [clean FPR], [injection TPR], [detection delay], [resident FPR], [edge FPR]),
  [4200], [0.069], [1.00], [5.3 窗], [0.02], [0.23],
  [4201], [0.085], [1.00], [5.2 窗], [0.04], [0.24],
  [4202], [0.110], [1.00], [5.3 窗], [0.03], [0.25],
  [4203], [0.142], [1.00], [5.2 窗], [0.02], [0.31],
  [4204], [0.063], [1.00], [5.3 窗], [0.01], [0.30],
  [4205], [0.087], [1.00], [5.3 窗], [0.04], [0.20],
  [4206], [0.153], [1.00], [5.3 窗], [0.03], [0.26],
  [4207], [0.106], [1.00], [5.3 窗], [0.04], [0.31],
  [#strong[平均]], [#strong[0.102（± 0.022）]], [#strong[1.00]], [#strong[5.3 窗]], [—], [—])]
（決策規則 z\_only，門檻即 τ\_H^reject \= 3：本 UE 層級效能腳本以 #mi("z_d > 3") 判定，xApp 之 strong 證據以 #mi("z_d \\geq 3") 判定，二者僅於 #mi("z_d") 恰為 3 時不同；± 為跨 seed 之 95% 信賴區間半寬；腳本 #raw("run_Hi_D1_performance.py")）

#strong[分群]：resident UE FPR 0.01–0.04；edge UE FPR 0.20–0.31（偏高，由 low\-trust 與交叉佐證吸收）。

#strong[門檻敏感度]（同一腳本之 ROC）：門檻由 2.0 升至 6.0，乾淨 FPR 由 0.141 降至 0.049，注入 TPR 皆為 1.00。D1 門檻與持續窗對節點層級決策之影響見 4.9.6.6（E14）。

#strong[與規模之關係]：逐 UE 之乾淨誤報率於 30 UE 與前版之 7 UE 資料相當（前版 0.116）；惟節點層級之 low\-trust 比例隨每節點之 UE 數上升而大幅提高（4.9.6.3），此為 D1 證據之規模效應，見 4.9.6.6。

#strong[界定]：

- #strong[分群標準]：以 UE 於序列中 最後事件歸屬 LTE 窗之佔比為依據，門檻取 0.55（多數時間最後事件歸屬 LTE 者判為 edge；此與 mmWave 鏈路長期劣化相關，4.8.1），#strong[沿用前版之值、未於 D\-30 重新選擇]。於 D\-30，該門檻下之分群為 resident 163／edge 77（240 個 UE\-run）；佔比之中位數為 0.388，分布無明顯自然分界（最大間隙 0.040，位於 0.863–0.903），故此分層應理解為#strong[探索性分層（exploratory stratification）]，而非事前登記之群體定義。其結論對分群門檻之穩健性見下方 E15。
- #strong[注入之性質]：超時消失之注入係將 UE 之歸屬序列由 mmWave 改為 LTE，等同改動 LTE 錨點之列（4.4.0（四）E11 之說明）；錨點為信任根，故本節之 TPR 代表「若錨點之報表呈現超時停留」時之偵測能力（規則行為驗證），#strong[不代表單一受攻陷 mmWave O\-DU 可造成之情境之偵測率]。
- #strong[TPR \= 1.0 限定於明顯超時消失]；注入強度依門檻定義，故 TPR \= 1 部分為設計必然。嚴重度–反應曲線見下方 E16。#strong[不宣稱可偵測所有消失攻擊。]
- 8 個 seed；per\-seed 明細如上表。

#strong[E15：分群門檻之敏感度]（規格 #raw("E15_E18_supplementary_spec.md") v1；主結果產出後新增之補充實驗，規格先於結果定案；腳本 #raw("run_E15_E16_D1_robustness.py")）

僅改變 resident／edge 之分群門檻，其餘設定同上表；0.55 之列逐 seed 重現上表（內建檢查）。括號內為 seed 間範圍：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 8, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([分群門檻], [resident／edge（UE\-run）], [整體 FPR], [resident FPR], [edge FPR], [TPR], [延遲（窗）], [edge FPR 高於 resident 之 seed 數]),
  [0.50], [151／89], [0.102（0.063–0.153）], [0.023（0.012–0.036）], [0.236（0.148–0.310）], [1.00], [5.3], [8／8],
  [#strong[0.55（沿用值）]], [#strong[163／77]], [#strong[0.102（0.063–0.153）]], [#strong[0.028（0.012–0.041）]], [#strong[0.263（0.202–0.311）]], [#strong[1.00]], [#strong[5.3]], [#strong[8／8]],
  [0.60], [177／63], [0.102（0.063–0.153）], [0.038（0.018–0.056）], [0.320（0.245–0.423）], [1.00], [5.3], [8／8])]
#strong[發現]：三個門檻下整體 FPR、TPR 與延遲皆相同（0.102／1.00／5.3 窗），edge FPR 於每個 seed 皆高於 resident FPR。故「edge UE 誤報偏高、整體效能不受分群影響」之結論#strong[對分群門檻不敏感]；分群門檻僅改變兩群之人數與各自之 FPR 數值（門檻越高，被劃為 edge 者越少、其 FPR 越高）。

#strong[E16：超時消失之嚴重度–反應曲線]（同一規格與腳本）

注入之 最後事件歸屬 LTE 停留長度 \= max(2, round(倍數 × 正常上界))，正常上界 \= median \+ 3σ；分群門檻 0.55。倍數 1.5／2.0／3.0 合併之結果逐 seed 重現上表（內建檢查）。每個倍數 240 次注入；括號內為 seed 間範圍：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 5, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([倍數], [整體偵測率], [resident], [edge], [已偵測者之平均延遲（窗）]),
  [0.5], [0.175（0.100–0.333）], [0.030（0.000–0.059）], [0.463（0.286–0.692）], [5.2],
  [0.75], [0.233（0.133–0.400）], [0.066（0.000–0.182）], [0.564（0.429–0.769）], [5.3],
  [1.0], [0.467（0.367–0.567）], [0.311（0.188–0.478）], [0.787（0.571–1.000）], [5.2],
  [1.1], [0.546（0.433–0.633）], [0.406（0.273–0.565）], [0.840（0.714–1.000）], [5.5],
  [1.25], [1.000], [1.000], [1.000], [5.3],
  [1.5], [1.000], [1.000], [1.000], [5.3],
  [2.0], [1.000], [1.000], [1.000], [5.3],
  [3.0], [1.000], [1.000], [1.000], [5.3])]
#strong[發現]：(1) #strong[轉折位於 1.1 與 1.25 倍之間]：注入長度達正常上界之 1.25 倍以上時全數偵測；恰為上界（1.0 倍）時僅 0.47，1.1 倍時 0.55。(2) #strong[低於上界之注入對 resident UE 幾乎不被偵測]（0.5 倍時 0.03），符合定義。(3) #strong[低於上界之「偵測」並非偵測到注入本身]：edge UE 於 0.5–0.75 倍時偵測率為 0.46–0.56，高於其乾淨誤報率（0.263）。逐筆分解（E16b）顯示，0.5 倍之 42 筆與 0.75 倍之 56 筆偵測#strong[全數發生於注入段結束之後]——該 UE 於注入段結束後仍連續停留於 LTE 錨點（其自身之自然停留與注入段相連），累計停留方超過門檻；於注入段之內被偵測者為 0 筆。1.0 倍時 112 筆中僅 1 筆於段內、1.1 倍時 131 筆中 33 筆於段內；1.25 倍以上則全數於段內偵測。故低於上界之數值反映的是 edge UE 本來就常駐錨點，#strong[不應解讀為對短暫消失之有效偵測]。(4) 已偵測者之延遲約 5.3 窗，與倍數無關——延遲由該 UE 之門檻（median \+ 3σ）決定。#strong[結論]：D1 可偵測者為「明顯超出該 UE 正常停留上界」之消失；上界以內之消失不在其偵測範圍。

#figure(image("/data/results/d30/fig_E16_D1_severity.png", width: 90%), caption: [E16：D1 偵測率對注入停留長度（以正常上界之倍數計）；虛線為乾淨之逐 UE 誤報率])
#figure(image("/data/results/d30/fig_Hi_D1_edge_vs_resident.png", width: 90%), caption: [resident／edge 分群之誤報率])
#figure(image("/data/results/d30/fig_Hi_H1_dwell_dist.png", width: 90%), caption: [最後事件歸屬 LTE 之停留時間分布（D\-30，12,252 個停留事件；98.0% ≤ 12 窗）])
#figure(image("/data/results/d30/fig_Hi_H2_edge_ue.png", width: 90%), caption: [240 個 UE\-run 之 最後事件歸屬 LTE 佔比與 edge／resident 分群（探索性分層）])
#figure(image("/data/results/d30/fig_Hi_H3_geom_reject.png", width: 90%), caption: [幾何分布適合度檢定（觀測 vs 最大概似幾何分布之期望次數）])
#figure(image("/data/results/d30/fig_Hi_H4_teleport.png", width: 90%), caption: [D2 注入之完整性檢查：D\-30 之乾淨跨 mmWave cell 轉移為 0（無合法換手，屬 vacuous），注入瞬移之偵測屬設計必然])
#figure(image("/data/results/d30/fig_Hi_D1_grading.png", width: 90%), caption: [D1 證據強度分級（乾淨事件 12,252 個：none 81.1%／warning 5.6%／strong 13.4%）；最終信任狀態由 4.4.0 之階層式融合決定])
#heading(level: 3, numbering: none)[4.8.7 有效性威脅]
- #strong[D2 之粒度依賴]：在目前 1 秒報表、無合法 NR\-to\-NR 換手之資料上，未觀察到 D2 反例；這只表示此資料未提供反例，不是在合法換手上驗證了規則。注入直接違反規則而全數被抓，屬規則行為驗證，不是一般換手異常之偵測準確率。不同時間粒度下之誤觸（較細時可能捕捉到過渡、較粗時可能漏掉短暫過渡）未經觀測。
- #strong[D2 之合法過渡規則未經檢驗]：本場景缺乏跨 cell handover，真實移動性下之誤報率未驗證。
- #strong[per\-UE\-index 基線]：LOSO 下無法對齊 held\-out seed 之 UE 個體身分，屬 LOSO 架構之固有限制；部署上宜於冷啟動時採群組基線、累積乾淨歷史後切換為裝置層級基線。
- #strong[clean bootstrap 假設]。
- #strong[edge UE 敏感度]：須交叉佐證；分群門檻之穩健性待敏感度分析。
- #strong[證據綁定粒度]：D1 證據以 UE 為單位，註記以 (節點, 窗) 為單位。本研究定案採 UE 綁定（4.9.6.5），其代價為：注入實驗中，告警雖均歸屬至正確節點，惟約 10% 之事件於首次告警窗時其歸屬節點當窗無有效節點註記（該 cell 當窗無上報），告警因此僅留存為 UE 層級紀錄；以「UE 消失前之 serving cell」為歸屬依據使 D1 與 S\_i 之交叉佐證可觸發，於乾淨資料上產生 1.0% 之誤拒（4.9.6.5）。
- #strong[樣本規模與外部有效性]：8 個 seed；外部有效性限於封閉 NPN、固定拓樸、MC 架構。
- #strong[規模效應]：D1 之逐 UE 誤報率不隨 UE 數下降，故每節點之 UE 越多，節點於任一窗綁有 D1 證據之機率越高（D\-30 為 48.3%），見 4.9.6.6。

#heading(level: 2, numbering: none)[4.9 C\-ZT 四 xApp 架構、動作模式與運算開銷]
#heading(level: 3, numbering: none)[4.9.1 定位與實作層級]
本節將 C\-ZT 組織為四個職責分離之 xApp：Detection、Trust Assessment、Policy Enforcement 三者將三類一致性證據經階層式融合轉為准入動作（程序 P1–P3），可用資源評估 xApp（Available\-resource evaluation xApp）於每窗 P3 發布後評估准入政策下之可用資源（4.12）。此為目標部署架構；本原型以離線 trace 回放、同一行程內之邏輯模組實作四者，逐窗依序執行，未接上 live E2 與 RIC 平台。本節並量測 P1–P3 之運算開銷。E2 Termination、Subscription Management 與 shared data service 為 Near\-RT RIC 平台之既有功能，非本研究之貢獻。

#strong[實作層級之誠實聲明]：

- 四個 xApp 之邏輯皆已實作並於重放 trace 上執行。Detection、Trust Assessment、Policy Enforcement（逐窗對齊、三類證據之計算、階層式融合、依信任狀態產生准入動作）目前於同一行程（#raw("zt_kpm_xapp.py")）內依 P1→P2→P3 依序執行，可用資源評估 xApp（#raw("resource_eval_xapp.py")）於同一行程內、每窗 P3 發布後執行；模組間之 evidence record、trust state 與 admitted view 以行程內資料結構傳遞，未經 RIC 之 shared data service 與訊息匯流排。故本章所驗證者為各模組之邏輯及其介面內容，而非四個獨立部署之 xApp 間之通訊。
- #strong[資料入口為 trace replay，E2 訂閱綁定尚未完成]（見 4.0.6）。程式以 #raw("IndicationSource") 抽象層隔離資料來源，設計上擬以 #raw("E2SubscriptionSource") 替換 #raw("TraceReplaySource") 接上 live RIC；此替換未實作、未測試，且 OAI 之檢查顯示真實 E2 之欄位語意與本文 trace 不同（4.0.6），驗證邏輯是否須改動尚未知。
- Policy Enforcement 將 policy\-admitted KPM 與 execution record 寫入共享資料層（DB）；合作消費端（RC xApp）與可用資源評估 xApp 皆自 DB 讀取。可用資源評估 xApp 於#strong[每窗 P3 發布後即執行]（#raw("resource_eval_xapp.py")），與 P1–P3 於同一回放迴圈中逐窗執行，而非事後之離線統計。於本原型中，DB 與 Resource Termination 為行程內之抽象層，尚未接上 RIC 之 shared data service。
- 攻擊情境下對合作消費端之保護效果，以注入後之 trace 經同一管線重放評估（4.12），未涉及 runtime 控制與閉迴路。
- 運算開銷量測反映驗證層之計算成本，#strong[不含 E2SM\-KPM 解碼與 SCTP 傳輸延遲]。

#heading(level: 3, numbering: none)[4.9.2 模組定義與程序]
#figure(rect(width: 80%, height: 4cm, stroke: (dash: "dashed"))[#align(center + horizon)[【待填：圖檔】 C\-ZT 架構圖]], caption: [C\-ZT 架構圖])
#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 4, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([xApp], [職責], [輸入], [輸出]),
  [#strong[① Detection xApp]], [將各 E2 節點（含 LTE 錨點）之上報對齊至 1 秒窗；計算 C\_i、S\_i、H\_i\-D1、H\_i\-D2；記錄每項證據之適用對象（場域／cell／UE）與可得性], [E2SM\-KPM 上報（REPORT style，granularity period \= 1 s；此為設計，原型之輸入為 trace replay）；已知 UE 母體；凍結基線], [evidence record],
  [#strong[② Trust Assessment xApp]], [套用 4.4.0 之階層式規則、交叉佐證之綁定檢查與持續窗條件], [evidence record], [逐 (節點, 窗) 之信任狀態、觸發規則代碼與佐證證據],
  [#strong[③ Policy Enforcement xApp]], [依設定之准入政策將信任狀態轉為 allow／restrict／exclude／defer，並將 policy\-admitted KPM 寫入共享資料層（DB）], [信任狀態；准入政策設定], [policy\-admitted KPM、註記與 execution record（寫入 DB）],
  [#strong[④ Available\-resource evaluation xApp]], [與 ①–③ 於同一回放迴圈中逐窗執行；每窗於 P3 發布後，經 Resource Termination 自 DB 讀取准入結果與各 cell 之 PRB 用量，計算可用資源指標。#strong[不做驗證、不改變信任狀態]], [DB 中之 policy\-admitted KPM 與 execution record；PRB 用量（#raw("RRU.PrbUsedDl")）], [逐窗之准入輸入可用率、#mi("\\rho_{\\text{PRB}}")、PRB 能見度損失 #mi("V_{\\text{PRB}}")])]
#strong[程序]：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 2, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([程序], [內容]),
  [初始化], [載入已登記之節點身分、已知 UE 母體（N\_known）、凍結基線（S\_i 之全域尺度 #mi("s")、H\_i\-D1 之停留基線）與政策設定（τ\_S、τ\_H、L\_C、MIN\_PEER、准入政策）],
  [#strong[P1] 證據偵測], [對齊上報；計算一致性證據及其適用對象與可得性],
  [#strong[P2] 信任評估], [套用融合規則與狀態轉移條件，產出信任註記],
  [#strong[P3] 政策執行], [套用准入政策，發布 policy\-admitted KPM 並記錄執行結果],
  [逐窗執行（同一回放迴圈）], [Available\-resource evaluation xApp：每窗於 P3 發布後，自 DB 讀取准入結果與 PRB 用量，回報准入輸入可用率與 PRB 能見度損失（4.12）])]
#strong[evidence record 之欄位]：C\_i 之 #raw("n_total") 與嫌疑 cell；S\_i 之 #mi("z") 值與 peer 數；D2 之瞬移 IMSI 與來源／目的 cell；D1 之 #mi("z_d") 值、對應 UE 及其歸屬節點（4.9.6.5）。每筆信任註記含決策、觸發規則代碼與上述證據欄位；證據隨決策一併發布，使消費端與稽核者可追溯判定依據。

#strong[execution record 之欄位]：逐窗記錄 allow／restrict／exclude／defer 之節點、准入之節點（admitted）、defer 之 fallback 設定、#raw("out_of_scope")（LTE 錨點）、#raw("unannotated")（應受判定之 mmWave 節點卻缺少註記者，用於發現實作缺漏），以及窗之處理狀態（#raw("processed") 或 #raw("n/a")）。

#strong[execution\-status 回饋]：架構圖中由 Policy Enforcement 回送 Detection 之 execution status（目前生效之限制）為#strong[提出之介面]，本研究未實作亦未評估；現行之證據計算與判定均不依賴此回饋。

#heading(level: 3, numbering: none)[4.9.3 動作模式：對合作消費端之准入，而非攔截]
#strong[權限邊界]：O\-RAN 架構下各 xApp 獨立向 Near\-RT RIC 訂閱 E2 資料，由平台之 subscription management 管理並執行授權（xApp\-TR v07 §4.2；RICARCH v09.00 §6.2.2：「Managing subscriptions from xApps to E2 Nodes; Enforcing authorization of policies controlling xApp access to messages」）；C\-ZT #strong[無權阻斷其他 xApp 之訂閱或攔截 KPM 資料流]。四種可能之動作模式比較如下：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 5, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([模式], [機制], [標準相容性], [代價], [本研究]),
  [註記型], [發布信任狀態與證據至共享資料層], [相容（需消費端配合）], [保護效果取決於消費端是否採用註記], [#strong[✓]（Trust Assessment 之輸出）],
  [中介型（限合作消費端）], [Policy Enforcement 發布 policy\-admitted KPM，合作之消費端改讀此視圖], [相容（需改變該消費端之資料來源）], [增加一跳延遲；Policy Enforcement 成為該消費端之單點故障與新攻擊目標；未合作之 xApp 不受保護；時間敏感 xApp 需保留直接存取路徑], [#strong[✓ 採用]（離線評估，4.12）],
  [攔截型], [攔在 KPM 流前，僅轉發 trusted 資料], [非標準（O\-RAN 無此角色）], [需平台層權限], [✗],
  [告警型], [僅寫日誌，不介入決策], [完全相容], [保護力最弱], [併入 execution record])]
中介型之一例為 Alimohammadi 等人之框架：其中毒偵測 xApp 將驗證後之 KPM 存入共享資料庫，其他 xApp 改由資料庫取用，並保留超時間敏感 xApp 之直接存取路徑（IEEE OJCOMS 2026）。本研究與之同屬此類，差異在於准入之依據為 4.4.0 之信任狀態及其可追溯之證據。

#strong[信任狀態與動作之對應]：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 3, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([信任狀態], [動作], [於 policy\-admitted KPM 中之處置]),
  [trusted], [#strong[allow]], [原值納入，附註記],
  [low\-trust], [#strong[restrict]], [依准入政策設定：#raw("strict") 自決策輸入排除；#raw("restrict_annotated") 附限制註記後納入；S\_i 證據不可得者兩種設定皆不准入（證據可得性閘）。兩種設定之下游差異見 4.12],
  [rejected], [#strong[exclude]], [該 (節點, 窗) 之量測不納入；寫入 execution record],
  [abstain], [#strong[defer]], [於任何准入政策下皆不進入 policy\-admitted KPM，待後續窗重新判定。fallback 政策（例如消費端改採其他資料來源）另行定義，且#strong[不得使該筆量測回到 admitted view]；本章評估之 fallback 為 #raw("none")，即消費端當窗不取得該節點之輸入])]
#strong[准入政策]：#raw("strict") 僅准入 allow；#raw("restrict_annotated") 准入 allow 與 restrict（restrict 附限制註記）。exclude 與 defer 於兩者下皆不准入。實作以不變式檢查之：strict 下非 allow 之准入為 0 筆，restrict\_annotated 下 defer／exclude 之准入為 0 筆。

#strong[證據可得性閘（v12.3）]：註記之 S\_i 證據不可得（#raw("si_raw") 為 unavailable，或 #raw("R3_ABSTAIN") 為最終或同時符合之規則）者，於任何准入政策下皆不准入；判定標籤不變，execution record 另列 #raw("evidence_gate")（#raw("zt_kpm_xapp.py") 之 #raw("EVIDENCE_GATE")；#raw("ZT_EVIDENCE_GATE=0") 僅供重現 v12.2 前之輸出）。外部審稿以函式反例指出：未加此閘時，#raw("restrict_annotated") 會准入「S\_i 不可得＋D1 weak／strong」而判為 low\-trust 之量測（#raw("R3_ABSTAIN") 仍列於同時符合之規則，但准入只看最終狀態）；加閘後兩種政策皆不准入，D1 normal 之 abstain 則本來即不准入。累計輸入之 D\-30 中 S\_i 證據不可得率為 0（4.9.6.4），故本版之歷史數字不受此閘影響；低密度場域（前版 7 UE 資料之不可得率 29.8%）下則會改變 #raw("restrict_annotated") 之准入。

#strong[LTE 錨點]：LTE 錨點之 KPM 為驗證用之輔助輸入，不在本次准入政策之作用範圍內，於 execution record 記為 #raw("out_of_scope")。其未進入 admitted view 之原因為不在作用範圍，#strong[不代表 rejected 或 defer]。

#strong[作用範圍]：Policy Enforcement 僅作用於合作消費端（本研究以 RC xApp 為例）之 KPM 輸入。C\-ZT 不下達 E2SM\-RC control、不阻斷其他 xApp 之訂閱，亦不對 E2 節點採取任何動作。rejected 之精確語意為#strong[該筆量測不進入 policy\-admitted KPM 並留存執行紀錄]，非判定該節點為攻擊者。驗證服務與政策設定假設位於攻擊者控制之外。向管理面之通報不在本研究之架構範圍內。

#heading(level: 3, numbering: none)[4.9.4 唯讀信任根]
Detection xApp 之基線——per\-UE\-index 停留分布（H\_i\-D1）與全域尺度 #mi("s")（S\_i）——於#strong[啟動時由乾淨資料載入後永不線上更新]。須區分：S\_i 之#strong[尺度與門檻]固定，#strong[中心]則每窗由同窗其他節點即時計算；後者屬同時態參照，非固定參照。

#strong[設計理由]：若基線隨線上資料更新，攻擊者可藉緩慢注入逐步養高門檻，使後續大幅偏移仍落於「正常」範圍——此即 4.7.3 所述滑動更新參照之結構性弱點。凍結基線使此規避路徑失效，代價為需要 #strong[clean bootstrap 假設]，並將風險移至校準期（校準期中毒，4.7.8 Q6）。4.7.7 之非穩態結果顯示，基線與判定均不宜於場域啟動暫態期間取得或投入。

#heading(level: 3, numbering: none)[4.9.5 運算開銷實測]
#strong[設定]：於 D\-30 以 LOSO 重放，逐窗量測「窗聚合完成至該窗全部 (node) 決策與准入動作產出」之處理時間（計時範圍 P1–P3）。定案組態為逐節點評估（對每個同窗活躍 mmWave 節點各產出一筆註記）、uebound、#raw("strict") 准入，共 2,400 窗、15,534 筆註記。量測於機器無其他負載時進行，連續執行三次。

#strong[量測環境與程序]：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 2, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([項目], [設定]),
  [CPU], [Intel Xeon Silver 4110 \@ 2.10 GHz],
  [邏輯核心], [4],
  [作業系統], [Linux 5.15（Ubuntu 22.04）],
  [Python／NumPy], [3.10.12／2.2.6],
  [計時器], [#raw("time.perf_counter_ns")],
  [暖身], [process 層級暖身 \+ 每 seed 3 回合],
  [重複量測], [每 seed 5 回合，#strong[逐窗取各回合中位數]],
  [垃圾回收], [量測期間停用],
  [檔案 I\/O], [trace 預先載入，不計入],
  [每窗記錄數], [mean 30.00、max 30])]
#strong[結果]（三次執行；正文與圖採第三次，即存檔之輸出）。下表之 P99 為「同一窗重複五回合取中位數後、跨窗之第 99 百分位」，為離線重放之計算成本基準，不是原始請求耗時之 P99，亦非 live E2 端到端之尾延遲（不含傳輸、解碼與共享資料層）：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 4, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([指標], [第一次], [第二次], [#strong[第三次（存檔）]]),
  [mean], [0.917 ms], [0.907 ms], [#strong[0.916 ms]],
  [P95], [1.068 ms], [1.076 ms], [#strong[1.111 ms]],
  [P99], [1.177 ms], [1.163 ms], [#strong[1.419 ms]],
  [max], [1.540 ms], [1.509 ms], [#strong[1.922 ms]],
  [#strong[佔 1 秒 KPM granularity（\@P99）]], [0.118%], [0.116%], [#strong[0.142%]],
  [佔 10 ms 保守比較基準（\@P99）], [11.8%], [11.6%], [14.2%])]
#strong[論述]：驗證層之每窗開銷於 P99 為 1.16–1.42 ms（三次執行之範圍），平均約 0.91 ms。本研究實際之 KPM granularity 為 1 秒，故該開銷佔量測週期之 #strong[0.12%–0.14%]；若另以 Near\-RT RIC 常引用之 10 ms 控制迴圈下界作為保守比較基準，則佔 11.6%–14.2%——10 ms 並非本系統已證明須符合之 deadline，僅作量級對照。P99 於各次執行間之變動（1.16–1.42 ms）大於 mean 之變動（0.907–0.917 ms），尾端數值對單機之排程擾動敏感。

#strong[四個 xApp 合計之每窗處理時間（M1）]：上表僅計 P1–P3。另於同一次執行中逐窗量測 P1–P3 與可用資源評估 xApp 之處理時間及其合計（規格 #raw("E15_E18_supplementary_spec.md") v1；主結果產出後新增之補充實驗，規格先於結果定案；程序同上，連續三次）：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 5, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([範圍], [mean], [P95], [P99], [max]),
  [P1–P3], [0.857–0.874 ms], [1.006–1.015 ms], [1.088–1.122 ms], [1.402–2.032 ms],
  [可用資源評估 xApp], [0.013 ms], [0.015 ms], [0.017 ms], [0.024–0.025 ms],
  [#strong[四個 xApp 合計]], [#strong[0.871–0.887 ms]], [#strong[1.021–1.030 ms]], [#strong[1.102–1.139 ms]], [#strong[1.418–2.050 ms]])]
第四個 xApp 使每窗處理時間增加約 0.013 ms（約 1.5%）；四者合計之 P99 為 1.10–1.14 ms，佔 1 秒量測週期之 0.11%。本表與上表為不同次執行，P1–P3 之數值略有差異（P99 1.09–1.12 ms 對 1.16–1.42 ms），二者並列、不互相取代。DB 於本原型為行程內抽象，實際之資料層讀寫開銷未計入。

#strong[跨 seed 差異與工作量正規化]（第三次執行）：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 5, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([seed], [每窗受測節點數], [full\-consensus 判定次數], [mean (ms)], [每次判定攤提 (μs)]),
  [4200], [6.62], [1,985], [0.911], [137.7],
  [4201], [6.75], [2,026], [0.965], [142.8],
  [4202], [6.22], [1,866], [0.917], [147.5],
  [4203], [6.23], [1,869], [0.854], [137.1],
  [4204], [6.85], [2,055], [0.982], [143.4],
  [4205], [5.77], [1,730], [0.765], [132.7],
  [4206], [6.82], [2,046], [0.972], [142.6],
  [4207], [6.52], [1,957], [0.960], [147.2])]
原始 mean 之跨 seed 差異為 1.28 倍；以每次 full\-consensus 判定攤提後降至 #strong[1.11 倍]，故差異主要源自各 seed 之活躍節點數，非量測不穩。

#strong[成本模型與擴展性外推]：以同機器、同程序下兩個操作點（逐節點評估：每窗 0.916 ms／6.47 次 full\-consensus 判定；單節點評估：0.220 ms／1 次）解聯立：

#mitex("t_{\\text{window}} \\approx F + S \\cdot n_{\\text{full}}, \\qquad F \\approx 93\\ \\mu s,\\quad S \\approx 127\\ \\mu s")
#mi("F") 為每窗固定成本（C\_i 聯集比對、H\_i\-D1、H\_i\-D2、聚合；UE 數為 30），#mi("S") 為每受測節點之 S\_i 共識計算與融合成本。此為兩點解，未檢驗線性假設。外推（假設全節點均達 full consensus、UE 數維持 30）：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 3, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([節點數 N], [每窗開銷估計（mean）], [佔 1 秒 granularity]),
  [#strong[7（本研究）]], [#strong[0.98 ms]], [#strong[0.098%]],
  [20], [2.64 ms], [0.264%],
  [50], [6.45 ms], [0.645%],
  [100], [12.8 ms], [1.28%])]
N \= 7 之外推值（0.98 ms）為全部 7 個節點皆上報時之估計；實測 mean 0.916 ms 對應平均 6.47 個節點。

#strong[延遲分布]（圖 4\-14）：D\-30 之全部節點註記皆執行完整之 S\_i 共識計算（無提早返回），每窗開銷主要隨當窗活躍節點數（4–7 個）變動。

#strong[範圍界定]：本節數字為累計輸入、原融合順序下之量測；區間延遲重建與嚴重度序之開銷未於閒置機器重新量測。數值#strong[僅涵蓋驗證層之計算成本]，不含 E2SM\-KPM ASN.1 解碼、SCTP 傳輸與共享資料層寫入。外推另有三項限制：中位數運算為 #mi("O(N \\log N)") 而非嚴格線性，大 N 之估計偏樂觀；C\_i 與 D1 之成本隨 UE 數成長，本外推固定為 30 個 UE（#mi("F") 於前版之 7 UE 資料上約為 53 μs）；單機離線量測未模擬 RIC 之併發負載。

#figure(image("/data/results/d30/fig_xapp_runtime_bound_all_uebound_strict.png", width: 90%), caption: [C\-ZT 驗證層之每窗運算延遲分布（逐節點評估）])
#heading(level: 3, numbering: none)[4.9.6 融合規則稽核與乾淨資料上之決策分布]
#block(width: 100%, fill: luma(240), inset: 8pt, radius: 2pt)[#set text(size: 10pt)
規則定義見 4.4.0，本節報告該定義之實作稽核結果。

]
#heading(level: 4, numbering: none)[4.9.6.1 規則稽核之儀器化]
為檢驗融合實作是否與 4.4.0 一致，xApp 加入規則稽核儀器：每筆註記除決策外，另記錄#strong[觸發規則代碼]、#strong[各殘差之原始判定]與#strong[證據之綁定對象]，使「決策 × 觸發規則」可直接與規則表對帳。

稽核發現前版實作於第二層有兩處與規則陳述不符：其一，交叉佐證收受 H\_i\-D1 之 warning 證據，與「rejected 須 #mi("z_d \\geq \\tau_H^{\\text{reject}}")」矛盾；其二，未檢查兩項證據是否指向同一節點。修正後之規則即 4.4.0 所載版本。

#heading(level: 4, numbering: none)[4.9.6.2 證據綁定之結構性發現]
D1 量測連續 最後事件歸屬 LTE 停留，觸發 D1 之 UE 當窗掛載之 cell 集合恆為 {LTE 錨點}，與 S\_i 受測之 mmWave 節點不可能重合——此為定義使然。於 D\-30 之 window 政策下（15,534 筆有效節點註記），S\_i 違反且同窗有 D1 strong 證據者共 332 筆，全部觸發 #raw("R2_SI_D1_UNBOUND")；#strong[#raw("R2_SI_D1_BOUND") 之觸發為 0 筆]。

其後果為：#strong[以「當窗掛載之 cell」為歸屬依據時，4.4.0 之 #raw("R2_SI_D1_BOUND") 不存在合法觸發路徑]；前版實作因未檢查綁定，曾將此結構上不可能之配對誤判為互相印證（見下節）。定案之 uebound 政策改以「UE 消失前之 serving mmWave cell」為歸屬依據（4.9.6.5）；於該政策下，D1 證據依定義歸屬於受測節點本身（D\-30 之 7,502 筆皆為同節點），故同節點比例不再具診斷意義，應改看 #raw("R2_SI_D1_BOUND") 之觸發與其證據。

#heading(level: 4, numbering: none)[4.9.6.3 乾淨資料上之決策分布（window 政策，E10 之對照基線）]
於#strong[未注入任何攻擊]之資料上，以 window 註記政策執行。分母為有效 (節點, 窗) 註記 #strong[15,534] 筆；D\-30 無「無活躍 mmWave 節點」之窗。定案之 uebound 政策結果見 4.9.6.5：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 5, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([層級], [決策], [觸發規則], [筆數], [比例]),
  [L2], [low\-trust], [#raw("R2_D1_STRONG")], [14,707], [94.7%],
  [L2], [low\-trust], [#raw("R2_SI_D1_UNBOUND")], [332], [2.1%],
  [L2], [low\-trust], [#raw("R2_D1_WEAK")], [237], [1.5%],
  [L0], [trusted], [#raw("R0_CLEAN")], [182], [1.2%],
  [L2], [low\-trust], [#raw("R2_SI_ALONE")], [76], [0.5%])]
決策彙總：trusted 182（1.2%）、low\-trust 15,352（98.8%）、abstain 0、#strong[rejected 0（0%）]。

#strong[window 政策於 30 UE 之規模下實質不可用]：場域內 30 個 UE 中，幾乎每一窗都至少有一個 UE 帶有 D1 證據，window 政策即以之標記該窗全部節點，使 98.8% 之註記落為 low\-trust。前版之 7 UE 資料上此比例為 73.8%（trusted 23.6%）；規模擴大後，此政策之缺陷由「偏高」變為「全面」。此為 4.9.6.5 採 uebound 之主要依據。

#strong[前版實作之稽核紀錄]（7 UE 資料）：前版實作（未檢查綁定、收受 warning 證據）曾於乾淨資料產生 rejected 99 筆（3.1%，分母 3,160），全數來自第二層之無效配對；加入綁定要求後，window 政策下乾淨資料之誤拒歸零。現行實作於前版資料上以相容模式逐位重現前版計數（#raw("ZT_DATASET=dsh") 之回歸檢查，為 #raw("zt_kpm_xapp.py") 與 #raw("run_E10_D1_policy_ablation.py") 之內建條件）。

#strong[誤報之分層呈現]：本研究之 low\-trust 與學習式偵測器之 FPR 並非同一量——前者為「需佐證」，後者為「良性記錄被錯誤標記為攻擊」。與後者對應之量為#strong[乾淨資料上之 rejected 比例]：window 政策下為 #strong[0%]；定案之 uebound 政策下為 #strong[1.0%（159／15,534）]，全數來自交叉佐證（#raw("R2_SI_D1_BOUND")），L1 硬否決之誤觸於兩政策下皆為 0（4.9.6.5）。惟此對應僅及語意：學習式偵測器之 FPR 以 (UE, record) 為單位、於其訓練／測試切分上計算，本研究以 (節點, 窗) 為單位，#strong[二者為對應量而非等價量，不宜以數值直接相比]。其餘註記分別陳述：可直接採信（trusted）、需佐證（low\-trust）、證據不可得（abstain），三者均不計為誤報；惟於 #raw("strict") 准入下，low\-trust 之量測同樣被排除於決策輸入之外，其可用性代價見 4.12。定案政策下之比例見 4.9.6.5。

#heading(level: 4, numbering: none)[4.9.6.4 證據可用率與 abstain 決策率之區分]
S\_i 之#strong[原始判定分布]（不受融合順序遮蔽；兩種註記政策下相同；逐節點評估，n \= 15,534）：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 3, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([S\_i 原始判定], [筆數], [比例]),
  [normal], [15,126], [97.4%],
  [violated], [408], [2.6%],
  [#strong[unavailable]], [#strong[0]], [#strong[0%]])]
D\-30 之全部節點註記皆具備 full consensus（4.7.1），故 S\_i 證據不可得率為 0，abstain #strong[決策]亦為 0 筆。此二量於概念上仍須區分：abstain 決策率為「證據不可得且無其他證據」之比例，受 4.4.0 之評估順序影響（同窗另有 H\_i\-D1 證據時，L2 先行觸發 low\-trust）；證據不可得率則為 S\_i 本身無法判定之比例。於低 UE 密度之場域，二者皆不為 0：前版之 7 UE 資料上，證據不可得率為 29.8%，uebound 政策下 abstain 決策為 24.3%。#strong[D\-30 之 abstain \= 0 反映的是本場域之 UE 密度，不代表 fail\-closed 路徑不需要]。

#strong[跨腳本對帳]：逐節點評估下 S\_i 有效判定為 15,534 筆，與 4.10.3 之 m \= 1 full\-consensus trial 數相同（#raw("run_adversarial_msweep.py") 不 import #raw("zt_kpm_xapp.py")）。兩支獨立腳本於不同計算路徑得到同一分母，可作為資料處理一致性之交叉驗證。

#strong[檢查之性質須區分]：本章各腳本之內建檢查分為兩類。（一）#strong[回歸一致性檢查]：以同一判定函式重算，確認版本間逐位一致——例如 RQ3 與規則回放改經 #raw("zt_kpm_xapp.py") 之判定函式重跑（4.12、4.11），以及 E9b、E9c、E13 對 E9 與 4.9.6.5 之重現。此類檢查可排除版本分歧，但#strong[無法排除共享函式之共同錯誤]。（二）#strong[獨立驗證]：以原始 trace 逐筆回推、人工預期或不共享判定函式之計算路徑檢驗正確性——例如上述跨腳本對帳（#raw("run_adversarial_msweep.py")、#raw("run_Si_experiments.py") 均不 import #raw("zt_kpm_xapp.py")），以及 E11／E11b／E12 對註記之獨立重算。本章引用「一致性檢查通過」時，均指第一類，除非另行註明。

#heading(level: 4, numbering: none)[4.9.6.5 E10：D1 證據之節點歸屬政策——消融與定案]
#strong[診斷]：window 政策下，15,352 筆 low\-trust 中 14,944 筆（97.3%）由 H\_i\-D1 單獨觸發（strong 14,707 \+ warning 237），其 C\_i 判定均為 conserved。此為 4.8.6 所述 edge UE 高誤報率在窗層級之累積——該政策以「場域內任一 UE 之 D1 證據」標記該窗全部節點之註記。#strong[此為證據綁定粒度之錯配，非 D1 判定本身之錯誤]，與 4.9.6.2 同源。

#strong[政策]：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 2, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([政策], [D1 證據之節點歸屬]),
  [window（前版，對照）], [場域內任一 UE 之 D1 證據，標記該窗全部受測節點；交叉佐證之綁定依據為該 UE 當窗掛載之 cell],
  [#strong[uebound（定案）]], [D1 證據僅歸屬於觸發該證據之 UE #strong[消失前之 serving mmWave cell]，即該 UE 進入本次連續 最後事件歸屬 LTE 停留前最後一次掛載之 mmWave cell。D1 單獨成立與交叉佐證均以此為歸屬依據。該 cell 當窗無上報者，證據僅留存為 UE 層級紀錄，不影響任何節點之信任狀態])]
另以持續性門檻 #mi("L_H")（D1 證據須連續 #mi("L_H") 窗成立方計入）組成五組：P0 window\-#mi("L_H")1、P1 window\-#mi("L_H")2、P2 window\-#mi("L_H")3、P3 uebound\-#mi("L_H")1、P4 uebound\-#mi("L_H")2。

#strong[結果]（乾淨資料，分母 15,534 筆有效節點註記；注入為超時消失，每個強度 233 次）：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 8, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([政策], [trusted], [low\-trust], [abstain], [rejected], [UE 告警率], [偵測率 z \= 2.0／≥ 2.5], [平均偵測延遲（窗）]),
  [P0 window\-1], [1.2%], [98.8%], [0%], [0%], [16.9%], [1.00／1.00], [2.2],
  [P1 window\-2], [2.7%], [97.3%], [0%], [0%], [13.7%], [0.00／1.00], [3.2],
  [P2 window\-3], [4.6%], [95.4%], [0%], [0%], [11.4%], [0.00／0.00（z \= 2.5）、0.11（z \= 3.0）、1.00（z ≥ 4）], [4.2–6.0],
  [#strong[P3 uebound\-1（定案）]], [#strong[50.3%]], [48.7%], [0%], [1.0%], [16.9%], [1.00／1.00], [2.2],
  [P4 uebound\-2], [57.3%], [41.6%], [0%], [1.0%], [13.7%], [0.00／1.00], [3.2])]
定案政策（P3）之觸發規則：#raw("R0_CLEAN") 7,810（50.3%）、#raw("R2_D1_STRONG") 6,183（39.8%）、#raw("R2_D1_WEAK") 1,133（7.3%）、#raw("R2_SI_ALONE") 249（1.6%）、#raw("R2_SI_D1_BOUND") 159（1.0%）；L1 硬否決（#raw("R1_CI_VETO")、#raw("R1_D2_VETO")）之誤觸為 0。歸因：偵測到之注入均綁定至正確節點（1.00）；首次告警窗中，歸屬節點當窗有有效節點註記者為 90.1%，即 #strong[約 9.9% 之注入事件，其告警窗之歸屬節點當窗無有效節點註記]（該 cell 當窗無上報）。此比例量測於注入事件，非乾淨資料上之全部 D1 告警。

#strong[定案]：本研究採 #strong[uebound]。理由有三：可直接採信之註記比例由 1.2% 升至 50.3%；偵測率與偵測延遲與 window 相同（P0 與 P3 皆為 1.00／2.2 窗）；且與註記單位之語意一致——(節點, 窗) 之信任狀態不應因無法歸屬於該節點之 UE 證據而降級。uebound 之定案早於 D\-30（於前版資料上決定並凍結，4.0.3）；D\-30 之結果未用於此選擇，惟其支持此選擇之程度高於前版資料。

#strong[乾淨資料上之 159 筆 rejected]：uebound 使 #raw("R2_SI_D1_BOUND") 具有合法觸發路徑，於 D\-30 乾淨資料上觸發 159 筆（1.0%）。其組成：

- #strong[重合次數未高於獨立假設下之預期（探索性檢查）]：S\_i 於乾淨資料上違反 408 筆（2.6%），而 48.3% 之節點註記綁有 D1 證據（7,502／15,534）。若二者獨立，預期重合 408 × 0.483 ≈ 197 筆；實際 159 筆，未高於此值。惟此比較不足以證明兩項證據統計獨立（例如未考慮 seed 與 cell 之異質性），誤拒之相關結構仍須進一步檢驗。
- #strong[集中於少數 seed 與 cell]：seed 4203（69 筆）與 4202（47 筆）合佔 73%；seed 4200 為 0 筆。依 cell：cell 4（50）、cell 6（46）、cell 8（38）較多。
- #strong[並非集中於啟動暫態]：159 筆中 81 筆位於序列前半段，14 筆位於前 30 秒。
- 其 S\_i 判定之 peer 數為 4–6（非最低共識門檻），z 值介於 τ\_S 與 32.7 之間。

#strong[此 159 筆應報為乾淨資料上之誤拒事件（1.0%），不得解讀為攻擊偵測成功。] 前版之 7 UE 資料上同一規則僅觸發 6 筆（0.19%）；誤拒率隨規模上升之原因與限制見 4.9.6.6。

#strong[v12 揭露（區間輸入下之誤拒）]：上述數字為累計平均輸入之歷史版本。第一階段以區間平均延遲（新尺度）重跑同一 xApp 組態（uebound、strict、嚴重度序）時，乾淨資料之決策分布為 trusted 7,230（46.5%）／low\-trust 7,460（48.0%）／abstain 0／rejected 844（5.4%），844 筆全為 #raw("R2_SI_D1_BOUND")；S\_i 違反由 408 筆增為 1,755 筆（4.7.4）。即乾淨誤拒由 1.0% 升至 5.4%。此為第一階段之 xApp 重跑輸出（#raw("data/results/d30_delay_reconstructed/xapp_rule_breakdown_bound_all_uebound_strict_severity.json")），以現行 cell 歸屬為條件，#strong[非第二階段之正式融合結果]；惟其方向顯示本節之 1.0% 於更正輸入語意後不成立，4.12 之准入代價亦將隨之改變。

#strong[代價與限制]：

- 注入實驗中，約 9.9% 之事件於首次告警窗時，其（正確之）歸屬節點當窗無有效節點註記，告警僅留存為 UE 層級紀錄。
- UE 綁定使同窗之候選集由「全有全無」變為部分候選，於乾淨資料上引入新的誤排除成本（見 4.12.5（四））。
- 交叉佐證之觸發使乾淨資料出現 1.0% 之誤拒（上段）；window 政策下為 0，惟 window 政策之 trusted 僅 1.2%。

#strong[持續性政策（消融結果）]：本研究保留 #mi("L_H = 1")（凍結值）。於 D\-30（8 seed）與本注入設定（超時消失，每個強度 233 次）下，#mi("L_H = 2") 使 trusted 比例於 uebound 下增加 7.0 個百分點（50.3% → 57.3%），於 window 下僅增加 1.5 個百分點（1.2% → 2.7%），乾淨誤拒不變（159 筆），卻使 z \= 2.0 之注入完全漏偵（偵測率 1.00 → 0.00），且平均偵測延遲增加 1 窗（2.2 → 3.2）；#mi("L_H = 3")（window）之漏偵延伸至 z \= 2.5（0.00）與 z \= 3.0（0.11）。此取捨僅就上述資料與注入設定成立，不外推至其他移動模型或攻擊型態；門檻與持續窗之完整格點見 4.9.6.6。

#strong[一致性檢查]：E10 之相容模式計數檢查（742／2,335／83／0 與 1,813／575／766／6）屬前版資料之期望值，於 D\-30 明示略過；「有效節點註記與現行 xApp 逐筆一致」之檢查於 D\-30 仍執行並通過（P0、P3 差異皆為 0）。

#strong[界定]：low\-trust 應解讀為「存在至少一項需交叉佐證之證據」，而非「資料不可信」。於定案政策下，50.3% 之註記可直接採信；其餘註記之下游影響取決於 Policy Enforcement 對 low\-trust 之 restrict 設定（4.12）。

（腳本 #raw("run_E10_D1_policy_ablation.py")；定案組態為 #raw("zt_kpm_xapp.py --fusion bound --eval-mode all --d1-binding uebound")，window 對照組為 #raw("--d1-binding window")，前版對照為 #raw("--fusion legacy --eval-mode single")）

#heading(level: 4, numbering: none)[4.9.6.6 E14：D1 證據之規模效應與門檻敏感度（事後新增）]
#block(width: 100%, fill: luma(240), inset: 8pt, radius: 2pt)[#set text(size: 10pt)
#strong[揭露]：本小節為#strong[事後新增（post\-hoc）之敏感度分析]。其規格（#raw("E14_D1_sensitivity_spec.md") v1）撰寫於看過 D\-30 主結果之後、E14 任何結果產出之前。第四章之主結果一律維持凍結值（τ\_H \= 2／3、#mi("L_H = 1")）；#strong[本實驗不用於選擇操作點]。

]
#strong[動機]：D\-30 之乾淨資料上，low\-trust 為 48.7%、乾淨誤拒為 1.0%，分別高於前版 7 UE 資料之 18.3% 與 0.19%。然 D1 之#strong[逐 UE] 乾淨誤報率於兩組資料相當（0.102 對 0.116，4.8.6）。差異來自規模：D1 之逐 UE 誤報率不隨 UE 數下降，每節點之 UE 越多，節點於任一窗至少綁有一筆 D1 證據之機率越高（D\-30 為 48.3%）。本實驗量化：提高 D1 門檻或持續窗，能以多少偵測延遲換回多少可用性，以及誤拒能否因此消除。

#strong[設計]：D\-30、LOSO、uebound；格點為 (τ\_H^warn, τ\_H^reject) ∈ {(2, 3)★、(3, 4)、(4, 5)、(6, 7)} × #mi("L_H") ∈ {1★、2、3}（★ 為凍結值）。判定直接呼叫 E10 之 #raw("run_policy")，僅覆寫門檻，不複製判定邏輯。注入與 E10 相同（超時消失，停留長度 \= ⌈median \+ z·σ⌉），z ∈ {3, 4, 6, 8}；加入 z \= 8 係因 τ\_H^warn \= 6 時 z ≤ 6 之注入依定義不可偵測。內建檢查五項（凍結門檻之兩組須逐位重現 E10 之 P3／P4；trusted 之單調性；註記總數一致；門檻還原）全數通過。

#strong[結果一：乾淨資料]（分母 15,534）

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 5, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([τ\_H warn／reject], [#mi("L_H")], [trusted（seed 範圍）], [low\-trust], [rejected]),
  [#strong[2／3 ★]], [#strong[1]], [#strong[50.3%（40.5%–60.5%）]], [#strong[48.7%]], [#strong[159（1.02%）]],
  [2／3], [2], [57.3%（46.9%–68.9%）], [41.6%], [159（1.02%）],
  [2／3], [3], [62.9%（51.0%–75.2%）], [36.2%], [141（0.91%）],
  [3／4], [1], [57.6%（47.4%–69.3%）], [41.5%], [141（0.91%）],
  [3／4], [2], [63.2%（51.4%–75.6%）], [35.9%], [141（0.91%）],
  [3／4], [3], [67.7%（55.2%–81.0%）], [31.4%], [131（0.84%）],
  [4／5], [1], [63.2%（51.4%–75.6%）], [36.0%], [129（0.83%）],
  [4／5], [2], [67.7%（55.2%–81.0%）], [31.4%], [129（0.83%）],
  [4／5], [3], [71.0%（57.8%–84.6%）], [28.2%], [123（0.79%）],
  [6／7], [1], [71.2%（58.0%–84.9%）], [28.1%], [110（0.71%）],
  [6／7], [2], [74.2%（60.6%–87.9%）], [25.1%], [110（0.71%）],
  [6／7], [3], [76.7%（62.8%–90.3%）], [22.6%], [100（0.64%）])]
#strong[結果二：注入超時消失之偵測率／平均偵測延遲（窗）]（每格 233 次注入）

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 6, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([τ\_H warn／reject], [#mi("L_H")], [z \= 3], [z \= 4], [z \= 6], [z \= 8]),
  [#strong[2／3 ★]], [#strong[1]], [#strong[1.00／2.2]], [#strong[1.00／2.2]], [#strong[1.00／2.2]], [#strong[1.00／2.2]],
  [2／3], [2], [1.00／3.2], [1.00／3.2], [1.00／3.2], [1.00／3.2],
  [2／3], [3], [0.11／6.0], [1.00／4.2], [1.00／4.2], [1.00／4.2],
  [3／4], [1], [1.00／3.3], [1.00／3.3], [1.00／3.3], [1.00／3.3],
  [3／4], [2], [0.00], [1.00／4.3], [1.00／4.3], [1.00／4.3],
  [3／4], [3], [0.00], [0.00], [1.00／5.3], [1.00／5.3],
  [4／5], [1], [0.00], [1.00／4.3], [1.00／4.3], [1.00／4.3],
  [4／5], [2], [0.00], [0.00], [1.00／5.3], [1.00／5.3],
  [4／5], [3], [0.00], [0.00], [1.00／6.3], [1.00／6.3],
  [6／7], [1], [0.00], [0.00], [1.00／6.4], [1.00／6.4],
  [6／7], [2], [0.00], [0.00], [0.00], [1.00／7.4],
  [6／7], [3], [0.00], [0.00], [0.00], [1.00／8.4])]
#strong[發現]：

+ #strong[可用性可以偵測速度換取，但代價不低]：trusted 由 50.3% 提高至 71.2%（τ\_H \= 6／7、#mi("L_H = 1")），偵測延遲由 2.2 窗增為 6.4 窗，且強度低於門檻之超時消失（z ≤ 4）完全不被偵測。
+ #strong[於所測之門檻格點中，尚無設定消除乾淨誤拒]：最寬鬆之設定（τ\_H \= 6／7、#mi("L_H = 3")）仍有 100 筆（0.64%）。此與 4.9.6.5 之探索性估算方向一致：只要節點綁有 D1 證據之比例仍高，S\_i 之誤報即常與 D1 證據同窗出現，#raw("R2_SI_D1_BOUND") 之交叉佐證難以區分此類重合與真實之共同異常。此為該規則於高 UE 密度下之限制（只限所測格點；把門檻調至不告警可消除此誤拒，但同時失去偵測力——問題在於能否於保留有用偵測力下改善此代價）。
+ #strong[seed 間變異大]：凍結值下 trusted 之 seed 範圍為 40.5%–60.5%，各格點之範圍寬度約 20–28 個百分點。

#strong[解讀（依規格第七節預先寫定之規則）]：凍結之 D1 門檻係於 7 UE 資料上選定，#strong[並非 30 UE 規模下之最佳操作點]；主結果不因此修改，依部署規模校準 D1 門檻與持續窗、以及使交叉佐證之強度隨「節點綁有 D1 證據之基準比例」調整，列為未來工作。對第四章其餘結果之意涵為：4.12 中 #raw("strict") 准入政策之可用性代價（乾淨資料僅准入約一半），有相當部分來自此規模效應，而非來自攻擊。

（腳本 #raw("run_E14_D1_sensitivity.py")；驗證層級：離線合成注入，D\-30 8 seed；事後新增）

#figure(image("/data/results/d30/fig_E14_D1_sensitivity.png", width: 90%), caption: [E14：D1 門檻與持續窗對乾淨資料之 trusted／rejected 比例及注入偵測延遲之影響（虛線為凍結門檻）])
#heading(level: 2, numbering: none)[4.10 對抗性分析：偽造信任證據所需之最小攻陷]
#heading(level: 3, numbering: none)[4.10.1 方法論定位]
採 #strong[分析論證 \+ 單元件實測 \+ 多節點離線合成注入]，#strong[非 N 節點端到端模擬]。多節點（m ≥ 2）為離線合成——將 active\-cell set 中 m 個節點之 delay 設為同一偽造值以模擬協同上報，active cells \< m 時該窗跳過。宣稱限定為組合下界。

#heading(level: 3, numbering: none)[4.10.2 攻擊者模型]
控制 m 個 mmWave 節點（身分合法、可任意竄改），目標使偽造量測於 S\_i fail\-to\-reject，白箱知識。#strong[限制]：無法控制 LTE 錨點（信任根）、未攻陷節點與物理世界。定義：

#mitex("m^*_{S,50} = \\min\\{\\, m : P(\\text{bypass} \\mid \\text{full consensus}) \\geq 0.5 \\,\\}, \\qquad m^*_{S,100} = \\min\\{\\, m : P(\\text{bypass} \\mid \\text{full consensus}) = 1 \\,\\}")
#heading(level: 3, numbering: none)[4.10.3 抗串謀強度]
攻擊者將 m 個節點之 delay 同步偽造為「場域共識 \+ 6σ」。以每個（窗, m\-子集）為一次 trial，依受控目標 cell 之 peer 數分三層，分母嚴格分離；unavailable 屬證據不可得，不計入有效繞過：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 5, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([m], [full\-consensus trials (peer ≥ 2)], [full\-consensus bypass], [weak (peer \= 1)], [unavailable (peer \= 0)]),
  [1], [15,534], [18（0.1%）], [0], [0],
  [2], [42,967], [529（1.2%）], [0], [0],
  [3], [65,815], [11,077（16.8%）], [0], [0],
  [4], [60,270], [60,266（99.99%）], [0], [0])]
（τ\_S \= 4，全域尺度 s \= 0.0545 ms，D\-30，8 seed；#raw("run_adversarial_msweep.py") 可重現。）#strong[v12 註]：本節為累計平均輸入之歷史版本結果（尺度 0.0545 ms 為累計輸入之值）。表中之繞過率僅就固定偽造幅度（共識 \+ 6σ）而言；幅度低於 τ\_S·s 之偏移，單一節點即可通過（4.7.8 Q4）。

#strong[結果]：#mi("m^*_{S,50} = 4")；單點之殘餘繞過率為 0.1%，兩節點串謀為 1.2%，三節點為 16.8%。m \= 4 時繞過率為 99.99%（60,270 次中 4 次未繞過），故嚴格定義之 #mi("m^*_{S,100}") 於所評估之 m ≤ 4 內未達到。

#strong[機制]：單點（m \= 1）僅控制受測 cell，無法改變由其他 cell 構成之中心 #mi("c_j")，故於 full\-consensus 窗幾乎無法繞過。攻擊者須控制受測節點之 peer 中約半數，方能將 median{其他} 拉向偽造值、使 #mi("z") 由 6σ 降至 τ\_S 以下。D\-30 每窗有 4–7 個活躍 mmWave cell（多數為 6–7 個，4.7.1），受測節點之 peer 為 3–6 個：m \= 3（受測節點加 2 個 peer）僅於 peer 數較少之窗足以拉動中位數（16.8%），m \= 4（加 3 個 peer）則於幾乎所有窗達到半數。

#strong[與場域密度之關係]：前版之 7 UE 資料每窗活躍 cell 較少（僅 54.8% 之窗具備 full consensus），#mi("m^*_{S,50}") 為 2、#mi("m^*_{S,100}") 為 3。抗串謀強度取決於同窗活躍之誠實 peer 數，#strong[於離峰或低密度時段將退化至前版之水準]；#mi("m^*_{S,50} = 4") 僅就 D\-30 之密度成立。

#heading(level: 3, numbering: none)[4.10.4 收斂宣稱]
本節之宣稱於 v12.1 收斂如下。在本文定義之攻擊類別、1 秒觀測粒度、LTE 錨點可信且持續可觀測之條件下，#strong[竄改幅度超出各證據偵測邊界之單點攻擊]（淨變化不為零之基數增刪、1 %\/秒以上之延遲漂移、固定 6σ 之延遲偽造）會以本章所報之比例被至少一項適用之證據標記。#strong[惟單一 O\-DU 可同時通過三類證據之路徑確實存在]，本文之結果即含三例：（一）貼門檻之延遲偏移——Q4 之 oracle 攻擊者（β \= 0.99）全程未被偵測，平均偏差 23.6 %（4.7.8）；（二）×0.8 之延遲階躍——嚴格准入下誘導率仍為 46.2 %（4.12.4）；（三）守恆式替換——C\_i 與 S\_i 皆正常，4.11 之回放僅於 D1 證據為設定值時方非 trusted。前版所稱「尚未發現可由單一 O\-DU 同時繞過全部三類證據之路徑」與上述結果不符，撤回。

單點攻擊於不同類別下通常被至少一項#strong[適用之]驗證證據否證，但不存在「任一單點攻擊必然被某驗證器抓到」之完整性保證——守恆式替換繞過 C\_i、S\_i 於證據不足窗無法判定、單窗脈衝不升級為 rejected、純吞吐量竄改不涵蓋。#mi("m^*_{S,50}") 與 #mi("m^*_{S,100}") 僅為繞過 S\_i 之局部成本；同時通過三殘差之聯合下界 #mi("m^*_{CSH}") 尚未量化。

#figure(image("/data/results/d30/fig_adversarial_mstar.png", width: 90%), caption: [抗串謀強度曲線])
#heading(level: 2, numbering: none)[4.11 階層式融合之規則回放驗證]
#block(width: 100%, fill: luma(240), inset: 8pt, radius: 2pt)[#set text(size: 10pt)
#strong[定位]：本節#strong[不宣稱已完成端到端三殘差聯合實驗]，而以規則回放檢驗 4.4.0 之規則於代表性攻擊下之#strong[決策一致性]。

]
#heading(level: 3, numbering: none)[4.11.1 方法]
對 baseline 與四種代表性攻擊，各取同一個真實量測窗（D\-30 之 seed 4200，window 10，6 個活躍 mmWave cell，受測節點為 cell 6），實際注入後經 C\-ZT 之 P1–P3 三個程序產出結果：#strong[C\_i／S\_i／H\_i\-D2 由 P1 之判定函式於真實資料上計算]，S\_i 之尺度取自凍結基線（LOSO，不含 seed 4200）；#strong[H\_i\-D1 證據位及其歸屬節點為情境設定值（stipulated）]，因單窗回放無法累積 D1 所需之多窗停留歷史；P2 套用 4.4.0 之規則表；P3 以 #raw("strict") 准入政策產出動作與准入結果。「灌水 \+1」於連續 2 窗（#mi("= L_C")）注入，以檢驗持續後之硬否決。D\-30 無「無活躍 mmWave 節點」之窗，#raw("n/a") 之處理於本資料無從回放（該路徑於前版資料上檢驗）。

#heading(level: 3, numbering: none)[4.11.2 結果]
#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 9, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([攻擊], [C\_i], [S\_i], [H\_i\-D2], [H\_i\-D1 †], [決策], [觸發規則], [動作], [准入（strict）]),
  [baseline], [conserved], [normal（z \= 0.47）], [normal], [none], [#strong[trusted]], [#raw("R0_CLEAN")], [allow], [✓],
  [A. 灌水 \+1（持續 \= L\_C）], [violated], [normal（z \= 0.38）], [normal], [none], [#strong[rejected]], [#raw("R1_CI_VETO")], [exclude], [✗],
  [delay drift], [conserved], [violated（z \= 5.89）], [normal], [none], [#strong[low\-trust]], [#raw("R2_SI_ALONE")], [restrict], [✗],
  [teleport], [conserved], [normal（z \= 0.47）], [violated], [none], [#strong[rejected]], [#raw("R1_D2_VETO")], [exclude], [✗],
  [守恆式替換], [conserved], [normal（z \= 0.03）], [normal], [strong（歸屬於受測節點 cell 6）], [#strong[low\-trust]], [#raw("R2_D1_STRONG")], [restrict], [✗])]
† H\_i\-D1 欄及其節點歸屬均為情境設定值，非偵測器輸出。動作欄為 4.9.3 之狀態—動作對應，屬確定性映射；准入欄為 #raw("strict") 准入政策下之結果。各情境中 LTE 錨點均記為 #raw("out_of_scope")，未進入 admitted view。

#heading(level: 3, numbering: none)[4.11.3 決策一致性檢查]
- baseline → trusted（無反例不誤拒）✓
- 灌水 → #raw("R1_CI_VETO") → rejected（硬違反不被統計證據稀釋）✓
- delay drift → #raw("R2_SI_ALONE") → low\-trust（單一統計證據不硬否決）✓
- teleport → #raw("R1_D2_VETO") → rejected ✓
- 守恆式替換 → C\_i conserved，#strong[於 D1 證據存在（設定值）時]非 trusted ✓（D1 是否會對守恆式替換產生證據未驗證，4.6.6）
- LTE 錨點於各情境均為 #raw("out_of_scope")，未進入 admitted view ✓

上述預期值由 4.4.0 之規則表推導，寫入腳本作為內建檢查；任一不符即停止、不輸出結果。

#heading(level: 3, numbering: none)[4.11.4 意涵與界定]
規則回放檢驗三項行為承諾（4.4.3）：(1) #strong[硬違反優先]；(2) #strong[給定 D1 證據時，守恆式替換不得 trusted]——此列之 D1 證據為設定值，所檢驗者為規則之輸出，不是「盲點被接住」之實證；(3) #strong[單一統計證據不冒進]。

#strong[界定]：此為單窗規則回放，驗證的是「給定證據狀態時規則之輸出一致性」，性質近似單元測試；D1 是否真能於對應情境產生該證據屬 4.8.6 之效能問題，二者分離。跨窗持續性升級、共同攻擊資料集上之聯合 FPR\/TPR 與端到端延遲仍待後續。守恆式替換一列 S\_i \= normal（偽造成員使用正常 delay），與 4.6.6 一致。

（腳本 #raw("run_fusion_replay.py")，呼叫 #raw("zt_kpm_xapp.py") 之判定函式、#raw("fuse") 與 #raw("enforce")）

#heading(level: 2, numbering: none)[4.12 資源—政策評估：排除不可採信量測後之可用資源與決策品質]
#block(width: 100%, fill: luma(240), inset: 8pt, radius: 2pt)[#set text(size: 10pt)
#strong[定位]：本節回答 RQ3。資源指標（准入輸入可用率、#mi("\\rho_{\\text{PRB}}")、#mi("V_{\\text{PRB}}")）由#strong[可用資源評估 xApp] 於同一回放迴圈中、每窗 P3 發布後逐窗產出（4.12.4 之「線上輸出」）；攻擊情境下，注入後之 trace 經同一管線重放：資源指標同樣由可用資源評估 xApp 逐窗產出（E18），保護效果與下游決策品質則搭配代理決策評估。二者皆為 trace replay 上之整合原型，未涉及 runtime 控制，亦無閉迴路。本節只評估准入政策下之可用資源，不做資源分配（下一篇之題目）。

]
#heading(level: 3, numbering: none)[4.12.1 問題與量之定義]
RQ3 問：於排除被判定為不可採信之量測後，尚餘多少可用資源；此准入政策之可用性代價為何；驗證之運算開銷為何。運算開銷見 4.9.5；本節定義並評估前二者，另以一個代理決策評估下游決策之品質。

#strong[資源准入遮罩（eligibility mask）]：對每個 (節點 #mi("j"), 窗 #mi("t"))，若 Policy Enforcement 之動作屬准入集合則 #mi("m_j(t) = 1")，否則為 0。准入集合由准入政策決定（4.12.3）。

#strong[保留可用容量比]：

#mitex("\\rho = \\frac{\\sum_t \\sum_{j \\in \\mathcal{A}(t)} m_j(t)\\, K_j}{\\sum_t \\sum_{j \\in \\mathcal{A}(t)} K_j}")
其中 #mi("K_j") 為 cell #mi("j") 之容量參考，取自 #strong[resource inventory（場域組態）]，而非受測節點上報之 KPM。須說明兩點：

+ 此量描述「其量測被准入、因而可供消費端納入決策之節點，其組態容量之佔比」。它不是量測到之頻譜使用量，亦不能用以驗證吞吐量上報——純吞吐量竄改仍未涵蓋（4.5.2）。
+ 本場景（configuration 1）之七個 mmWave gNB 採同一載波設定（中心頻率 3.5 GHz、頻寬 20 MHz，由 #raw("scenario-three.cc") 之全域預設設定，無逐 cell 覆寫），故 #mi("K_j") 相同。分母 #mi("\\mathcal{A}(t)") 取#strong[當窗有上報之 mmWave 節點]；LTE 錨點為驗證用輔助輸入，不在准入範圍內；無活躍 mmWave 節點之窗（#raw("n/a")）不產生註記，亦不在評估之窗內。#mi("K_j") 相同時，#mi("\\rho") 於上式之彙總定義下即等於#strong[可用量測產出率]（准入之註記佔全部註記之比例）；4.12.4 所報者即此量。

#strong[原生 PRB 之保留比例（主指標）]：以模擬器輸出之 E2SM\-KPM #raw("RRU.PrbUsedDl") 為資源量。令 #mi("U_j(t)") 為 cell #mi("j") 於第 #mi("t") 秒之 PRB 時間占用率（各 UE 之 #raw("RRU.PrbUsedDl.UEID") 加總 ÷ 139，取自乾淨模擬、僅下行），則

#mitex("\\rho_{\\text{PRB}} = \\frac{\\sum_t \\sum_{j} m_j(t)\\, U_j(t)}{\\sum_t \\sum_{j \\in \\mathcal{A}(t)} U_j(t)}, \\qquad V_{\\text{PRB}} = 1 - \\rho_{\\text{PRB}}")
#mi("\\rho_{\\text{PRB}}") 為「已使用之 PRB 中，其 KPM 仍被准入決策採用之比例」；#mi("V_{\\text{PRB}}") 稱為 #strong[PRB 能見度損失]，即其 KPM 被排除、消費端決策時看不到之 PRB 負載比例。#strong[#mi("V_{\\text{PRB}}") 不是容量損失]：被排除之節點仍持續排程。#mi("\\rho")（組態容量版本，以下稱 #mi("\\rho_{\\text{cap}}")）保留為輔助指標，便於與前版對照。

#strong[原生 PRB 之性質]（依 ns\-O\-RAN 原始碼查證）：

+ 此模擬器之 MAC 為分時排程，每次配置佔滿整個頻寬，無頻域 PRB 配置；#raw("RRU.PrbUsedDl.UEID") \= 該 UE 於報告窗之排程 OFDM 符號數 ÷（報告窗之 slot 數 × 14）× 139。故原生 PRB 用量等於符號占用率乘以常數。此計算方式與 3GPP TS 28.552 V20.4.0 §5.1.1.2.5 之定義（期間內所用 PRB 數之算術平均、單一整數）不同：模擬器以時間占用比例近似、輸出為非整數。故本研究將其視為模擬器提供之資源用量代理，主表報告占用率與比值，不宣稱與實際設備依 TS 28.552 回報之值等價。
+ 常數 139 為原始碼寫死之值，等於 ceil(100 MHz ÷ 720 kHz)，即 configuration 2 之載波；configuration 1（20 MHz、numerology 2）實際為 28 RB。本節主表報占用率與比值（與此常數無關）；絕對 PRB 數另以 28 RB 尺度換算。
+ cell 層級之 #raw("RRU.PrbUsedDl") 欄位於原始碼中以整數逐 UE 累加、每次截斷小數，系統性偏低，故不採用，改以 UE 層級值加總。
+ 每個 seed 均以 #raw("RxPacketTrace") 之下行排程符號數重算並交叉驗證（#raw("prb_reader.py")，容許差 0.5 PRB）。

#strong[資源指標之區分]：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 2, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([指標], [意義]),
  [PRB 使用量（usage）], [觀測窗內實際使用之資源],
  [PRB 配額（quota）], [設定之資源比例或分配上限，非量測值],
  [分配成功率（allocation success）], [依各研究定義之成功服務之請求比例],
  [保留可用容量（ρ\_cap）], [准入政策下，可用量測所屬節點之組態容量佔比],
  [PRB 能見度損失（V\_PRB）], [已使用之 PRB 中，其 KPM 未被准入決策採用之比例；非容量損失],
  [吞吐量（throughput）], [實際送達之資料率；與資源分配相關，但不等同 PRB 數])]
#strong[政策引致之可用性成本]：乾淨資料上之 #mi("1 - \\rho")，即無攻擊時因誤報與證據不可得而未被准入之比例。

#heading(level: 3, numbering: none)[4.12.2 代理決策]
為評估准入政策對下游決策之影響，定義一個明確之消費端代理決策：於窗 #mi("t") 為一新流量選擇服務 cell，準則為#strong[回報延遲最低者]：

#mitex("j^*(t) = \\arg\\min_{j \\in \\mathcal{M}(t)} \\widehat{\\text{delay}}_j(t)")
其中 #mi("\\mathcal{M}(t) = \\{\\, j \\in \\mathcal{A}(t) : m_j(t) = 1 \\,\\}") 為准入後之候選集。

#strong[關鍵設計]：攻擊者謊報延遲以吸引流量；本節之決策為代理 steering 決策，其代價以原始 trace 中候選 cell 之#strong[真實延遲]計算。不實際移轉 UE，移轉後之負載、排程與延遲回饋不在模型內：

#mitex("\\text{regret}(t) = \\text{delay}^{\\text{true}}_{j^*(t)}(t) - \\min_{j \\in \\mathcal{A}(t)} \\text{delay}^{\\text{true}}_j(t)")
此評估方式與資訊物理系統中評估偽資料注入影響之慣例一致：攻擊影響的是決策，其代價須以真實狀態衡量。

#heading(level: 3, numbering: none)[4.12.3 實驗設定]
#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 2, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([項目], [設定]),
  [資料], [D\-30（8 seed），評估區間為序列後半段],
  [攻擊], [受控節點壓低自身回報延遲以吸引流量：階躍 ×0.8／×0.6；漸進 1%／2% 每秒],
  [攻擊者], [逐一以各 mmWave 節點為攻擊者，結果彙總],
  [准入政策], [#raw("C_none")：不執行准入（對照）；#raw("C_strict")：Policy Enforcement 之 #raw("strict") admitted view，僅 allow 准入；#raw("C_restrict_annot")：Policy Enforcement 之 #raw("restrict_annotated") admitted view，allow 與 restrict（附註記）准入，defer 與 exclude 不准入；#raw("C_notrej")：消費端僅排除 rejected，#strong[包含 abstain（defer）]，不符合 defer 不准入之原則，保留為寬鬆對照組，非 Policy Enforcement 之准入政策],
  [註記政策], [#strong[uebound]（定案，4.9.6.5）；window（對照）],
  [指標], [#strong[原生 PRB 之保留比例 #mi("\\rho_{\\text{PRB}}") 與 PRB 能見度損失 #mi("V_{\\text{PRB}}")]（主）、保留可用容量比 #mi("\\rho_{\\text{cap}}")（#mi("K_j") 相同，等於可用產出率）、決策可用率、相對 regret、誤選率、#strong[誘導率]（攻擊者之 cell 被選中且非最佳之比例）、最佳候選被濾除率；另輸出逐窗之資源准入遮罩（#raw("RQ3_eligibility_mask.jsonl.gz")）與保護效果對 PRB 能見度損失之取捨圖],
  [一致性檢查], [註記由 #raw("zt_kpm_xapp.py") 之 P1–P3 產出；乾淨資料上與 E10 之 #raw("run_policy") 逐筆相同（差異 0）。原生 PRB 之五項檢查（8 個 seed 之交叉驗證，最大差 0.149 PRB；#mi("U \\equiv 1") 時重現 #mi("\\rho_{\\text{cap}}")；兩種 PRB 來源一致；無缺報）全數通過])]
#heading(level: 3, numbering: none)[4.12.4 結果]
#strong[可用資源評估 xApp 之線上輸出（乾淨資料，全序列）]

可用資源評估 xApp 於每窗 P3 發布後，自 DB 讀取准入結果、經 Resource Termination 取得各 cell 之 PRB 用量，逐窗回報。下表為其於 D\-30 乾淨資料全序列（2,400 窗、15,534 筆節點註記）之彙總；括號內為 seed 間範圍：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 6, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([准入政策], [准入輸入可用率], [#mi("\\rho_{\\text{PRB}}")], [#mi("V_{\\text{PRB}}")], [無任何准入輸入之窗], [每窗已用 PRB／其 KPM 被准入者（28 RB 尺度，七個 cell 合計）]),
  [#raw("strict")], [50.3%（40.5%–60.5%）], [51.5%（41.4%–58.4%）], [48.5%（41.6%–58.6%）], [11／2,400], [127.1／65.5 RB],
  [#raw("restrict_annotated")], [99.0%（96.3%–100%）], [99.5%（97.9%–100%）], [0.5%（0.0%–2.1%）], [0／2,400], [—])]
內建檢查：（一）本 xApp 自 DB 讀到之准入節點與 P3 之 execution record 逐窗相同；（二）限於下表之評估窗（序列後半段，1,200 窗）彙總時，其 #mi("\\rho_{\\text{cap}}") 與 #mi("\\rho_{\\text{PRB}}") 與下表乾淨資料之 #raw("C_strict")／#raw("C_restrict_annot") 相同（差 \< 10⁻¹²）；（三）有上報之 (cell, 窗) 皆有 PRB 值；（四）全序列之准入註記數（7,810）與 4.9.6.5 之 trusted 筆數相同。本 xApp 自身之每窗處理時間平均 0.017 ms（P99 0.037 ms），不計入 4.9.5 之 C\-ZT 開銷；此為該次執行之值，與 4.9.5 之 M1（平均 0.013 ms、P99 0.017 ms）為不同次執行，處理時間之引用以 M1 為準。（腳本 #raw("resource_eval_xapp.py")）

#strong[攻擊情境下之重放：註記政策 \= uebound（定案）]

#block(width: 100%, fill: luma(240), inset: 8pt, radius: 2pt)[#set text(size: 10pt)
表中 #mi("\\rho_{\\text{PRB}}")、#mi("\\rho_{\\text{cap}}") 為#strong[准入比例]（4.12.1），隨准入政策而變，與 4.9.6 之信任狀態分布為不同量；例如 #raw("C_restrict_annot") 之 #mi("\\rho") 包含 trusted 與附註記之 low\-trust，不可讀作 low\-trust 比例或誤報率。評估窗為各 seed 之後半段，共 1,200 窗。

]
#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 10, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([攻擊], [准入政策], [#mi("\\rho_{\\text{PRB}}")], [#mi("V_{\\text{PRB}}")], [#mi("\\rho_{\\text{cap}}")], [決策可用], [regret], [誤選率], [誘導率], [最佳被濾]),
  [乾淨], [C\_none], [100.0%], [0.0%], [100.0%], [100.0%], [0.0%], [0.0%], [—], [0.0%],
  [乾淨], [C\_strict], [50.6%], [49.4%], [49.5%], [99.8%], [1.3%], [38.9%], [—], [39.1%],
  [乾淨], [C\_restrict\_annot], [99.5%], [0.5%], [99.0%], [100.0%], [0.0%], [0.0%], [—], [0.0%],
  [乾淨], [C\_notrej], [99.5%], [0.5%], [99.0%], [100.0%], [0.0%], [0.0%], [—], [0.0%],
  [×0.8], [C\_none], [100.0%], [0.0%], [100.0%], [100.0%], [6.1%], [73.8%], [94.6%], [0.0%],
  [×0.8], [C\_strict], [50.3%], [49.7%], [49.3%], [99.7%], [3.7%], [60.9%], [#strong[46.2%]], [40.4%],
  [×0.8], [C\_restrict\_annot], [99.4%], [0.6%], [98.9%], [100.0%], [6.1%], [74.1%], [94.3%], [0.6%],
  [×0.8], [C\_notrej], [99.4%], [0.6%], [98.9%], [100.0%], [6.1%], [74.1%], [94.3%], [0.6%],
  [×0.6], [C\_none], [100.0%], [0.0%], [100.0%], [100.0%], [7.4%], [77.3%], [99.2%], [0.0%],
  [×0.6], [C\_strict], [43.5%], [56.5%], [42.7%], [99.0%], [2.5%], [48.2%], [#strong[2.2%]], [47.8%],
  [×0.6], [C\_restrict\_annot], [93.9%], [6.1%], [93.5%], [100.0%], [4.6%], [50.8%], [58.9%], [4.9%],
  [×0.6], [C\_notrej], [93.9%], [6.1%], [93.5%], [100.0%], [4.6%], [50.8%], [58.9%], [4.9%],
  [漂移 1%], [C\_none], [100.0%], [0.0%], [100.0%], [100.0%], [7.2%], [73.1%], [93.8%], [0.0%],
  [漂移 1%], [C\_strict], [44.8%], [55.2%], [43.9%], [99.1%], [2.3%], [49.0%], [#strong[8.3%]], [46.4%],
  [漂移 1%], [C\_restrict\_annot], [94.8%], [5.2%], [94.3%], [100.0%], [4.2%], [50.2%], [59.1%], [4.2%],
  [漂移 1%], [C\_notrej], [94.8%], [5.2%], [94.3%], [100.0%], [4.2%], [50.2%], [59.1%], [4.2%],
  [漂移 2%], [C\_none], [100.0%], [0.0%], [100.0%], [100.0%], [7.7%], [75.4%], [96.7%], [0.0%],
  [漂移 2%], [C\_strict], [44.1%], [55.9%], [43.1%], [99.1%], [2.1%], [48.2%], [#strong[4.1%]], [47.1%],
  [漂移 2%], [C\_restrict\_annot], [94.2%], [5.8%], [93.7%], [100.0%], [4.1%], [49.1%], [57.2%], [4.5%],
  [漂移 2%], [C\_notrej], [94.2%], [5.8%], [93.7%], [100.0%], [4.1%], [49.1%], [57.2%], [4.5%])]
以 28 RB 尺度換算（configuration 1 之實際 RB 數；七個 cell 合計）：乾淨資料上每窗已使用之 PRB 平均為 126.2 RB，#raw("C_strict") 下其 KPM 仍被准入者為 63.9 RB，#raw("C_restrict_annot") 為 125.5 RB。

#strong[註記政策 \= window（對照）]

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 8, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([攻擊], [准入政策], [#mi("\\rho_{\\text{cap}}")], [決策可用], [regret], [誤選率], [誘導率], [最佳被濾]),
  [乾淨], [C\_none], [100.0%], [100.0%], [0.0%], [0.0%], [—], [0.0%],
  [乾淨], [C\_strict], [0.2%], [0.2%], [0.0%], [0.0%], [—], [99.8%],
  [乾淨], [C\_restrict\_annot], [100.0%], [100.0%], [0.0%], [0.0%], [—], [0.0%],
  [乾淨], [C\_notrej], [100.0%], [100.0%], [0.0%], [0.0%], [—], [0.0%],
  [×0.8], [C\_none], [100.0%], [100.0%], [6.1%], [73.8%], [94.6%], [0.0%],
  [×0.8], [C\_strict], [0.2%], [0.2%], [7.9%], [85.7%], [#strong[100.0%]], [99.8%],
  [×0.8], [C\_restrict\_annot], [100.0%], [100.0%], [6.1%], [73.8%], [94.6%], [0.0%],
  [×0.8], [C\_notrej], [100.0%], [100.0%], [6.1%], [73.8%], [94.6%], [0.0%],
  [×0.6], [C\_none], [100.0%], [100.0%], [7.4%], [77.3%], [99.2%], [0.0%],
  [×0.6], [C\_strict], [0.2%], [0.2%], [0.6%], [14.3%], [#strong[0.0%]], [99.9%],
  [×0.6], [C\_restrict\_annot], [100.0%], [100.0%], [7.4%], [77.3%], [99.2%], [0.0%],
  [×0.6], [C\_notrej], [100.0%], [100.0%], [7.4%], [77.3%], [99.2%], [0.0%],
  [漂移 1%], [C\_none], [100.0%], [100.0%], [7.2%], [73.1%], [93.8%], [0.0%],
  [漂移 1%], [C\_strict], [0.2%], [0.2%], [4.1%], [42.9%], [#strong[50.0%]], [99.8%],
  [漂移 1%], [C\_restrict\_annot], [100.0%], [100.0%], [7.2%], [73.1%], [93.8%], [0.0%],
  [漂移 1%], [C\_notrej], [100.0%], [100.0%], [7.2%], [73.1%], [93.8%], [0.0%],
  [漂移 2%], [C\_none], [100.0%], [100.0%], [7.7%], [75.4%], [96.7%], [0.0%],
  [漂移 2%], [C\_strict], [0.2%], [0.2%], [0.2%], [7.1%], [#strong[0.0%]], [99.8%],
  [漂移 2%], [C\_restrict\_annot], [100.0%], [100.0%], [7.7%], [75.4%], [96.7%], [0.0%],
  [漂移 2%], [C\_notrej], [100.0%], [100.0%], [7.7%], [75.4%], [96.7%], [0.0%])]
#strong[攻擊情境下可用資源評估 xApp 之逐窗輸出（E18）]（規格 #raw("E15_E18_supplementary_spec.md") v1；主結果產出後新增之補充實驗，規格先於結果定案）：將上述四種攻擊注入後之 trace 送入 P1–P3，由該 xApp 於每窗 P3 發布後讀取 DB 並回報。uebound 表中 #raw("C_strict") 與 #raw("C_restrict_annot") 之 #mi("\\rho_{\\text{PRB}}")、#mi("V_{\\text{PRB}}")、#mi("\\rho_{\\text{cap}}") 即為其輸出：八組（攻擊, 准入政策）於同一評估窗上與重放腳本之統計值相同（差 \< 10⁻¹⁴，窗數皆為 8,400 \= 1,200 窗 × 7 個攻擊者 cell；內建檢查）。該 xApp 另回報「當窗無任何准入輸入」之窗數：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 3, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([攻擊], [#raw("strict")：無准入輸入之窗], [#raw("restrict_annotated")：無准入輸入之窗]),
  [×0.8 階躍], [25／8,400], [0／8,400],
  [×0.6 階躍], [80／8,400], [0／8,400],
  [漂移 1 %\/秒], [76／8,400], [0／8,400],
  [漂移 2 %\/秒], [79／8,400], [0／8,400])]
即嚴格准入下，合作消費端於不到 1% 之窗完全沒有可用之輸入（與上表決策可用率 99.0%–99.7% 一致）。

（regret 為相對值，即真值最佳延遲之百分比。D\-30 之 abstain 為 0，故 uebound 政策下 #raw("C_restrict_annot") 與 #raw("C_notrej") 之准入集合相同、各列數值相同；window 政策下 rejected 亦為 0，二者與 #raw("C_none") 相同。window 政策下 #raw("C_strict") 僅准入 0.2% 之註記，其誤選率與誘導率係由極少數之窗計算，#strong[不具統計意義]，僅列出以示該政策之不可用。延遲類攻擊不改變成員組成，故此處之 rejected 僅可能來自交叉佐證。）

#strong[政策引致之可用性成本]：乾淨資料上之 #mi("1-\\rho_{\\text{cap}}")，#raw("C_strict") 於 uebound 為 #strong[50.5%]、window 為 99.8%；#raw("C_restrict_annot") 於 uebound 為 1.0%、window 為 0%。以原生 PRB 計，#raw("C_strict")（uebound）之 PRB 能見度損失 #mi("V_{\\text{PRB}}") 於乾淨資料為 49.4%，攻擊下為 49.7%–56.5%。此成本有相當部分來自 D1 證據之規模效應（4.9.6.6），而非來自攻擊。

#figure(image("/data/results/d30/fig_RQ3_decision_replay.png", width: 90%), caption: [柱為以真值計算之#strong[相對 regret]（真值最佳延遲之百分比，與上表同一口徑），線為 #raw("C_strict") 之決策可用率；左為 uebound、右為 window，兩圖共用縱軸刻度])
#figure(image("/data/results/d30/fig_RQ3_prb_tradeoff.png", width: 90%), caption: [保護效果（誘導率）對 PRB 能見度損失 #mi("V_{\\text{PRB}}")；每點為一組（攻擊, 准入政策），uebound。#raw("C_restrict_annot")（空心）與 #raw("C_notrej") 數值相同])
#heading(level: 3, numbering: none)[4.12.5 四項發現]
#strong[（一）未經驗證時，延遲壓低攻擊之誘導率為 93.8%–99.2%。] 決策之真值代價（相對 regret）為 6.1%–7.7%。此為第一章所述攻擊動機於本代理決策下之量化；代理決策以回報延遲為唯一準則，高誘導率為其直接後果，不代表真實 RIC 決策受誘導之程度（4.12.6）。

#strong[（二）嚴格准入對各幅度之攻擊皆降低誘導率，代價為乾淨資料上約一半之輸入。] 定案政策下，#raw("C_strict") 使 ×0.6 階躍之誘導率由 99.2% 降至 2.2%；漸進 1% 由 93.8% 降至 8.3%，漸進 2% 由 96.7% 降至 4.1%；regret 由 7.2%–7.7% 降至 2.1%–2.5%。×0.8 階躍（壓低 20%）較接近 #mi("\\tau_S")，保護較弱：誘導率僅由 94.6% 降至 46.2%，regret 由 6.1% 降至 3.7%。代價為：#raw("C_strict") 於#strong[乾淨資料]上即濾除 39.1% 之窗之真值最佳候選，引入 1.3% 之 regret 與 38.9% 之誤選率，並使 49.4% 之已用 PRB 之 KPM 不被准入。

#block(width: 100%, fill: luma(240), inset: 8pt, radius: 2pt)[#set text(size: 10pt)
#strong[與前版資料之差異（揭露）]：前版之 7 UE 資料上，×0.8 階躍下嚴格准入使 regret 由 2.5% #strong[反升]至 3.4%（因誤報濾除了最佳候選而攻擊者未被標記）。此現象於 D\-30 #strong[未重現]（6.1% → 3.7%）。「攻擊落於偵測門檻之下時，誤報會轉化為安全問題」之機制仍然存在——D\-30 之 ×0.8 下仍有 46.2% 之誘導率，且 40.4% 之窗之最佳候選被濾除——惟其淨效果是否使 regret 惡化，取決於場域密度與攻擊幅度，不可一概而論。

]
#strong[（三）僅排除 rejected 之准入政策提供部分且非設計所致之保護。] S\_i 違反於 4.4.0 下單獨成立時產出 low\-trust 而非 rejected，故 #raw("C_restrict_annot")（restrict 附註記後納入）與 #raw("C_notrej") 於 D\-30 之准入集合相同。其誘導率於 ×0.8 階躍為 94.3%（與 #raw("C_none") 之 94.6% 幾無差別），於 ×0.6 階躍與漸進漂移為 57.2%–59.1%（#raw("C_none") 為 93.8%–99.2%）。後者之下降來自 #raw("R2_SI_D1_BOUND")：攻擊者節點之 S\_i 違反恰與其綁有之 D1 證據同窗時被拒絕；而 D\-30 有 48.3% 之節點註記綁有 D1 證據（4.9.6.5），此保護實為 D1 證據之高基準比例所附帶，#strong[並非針對延遲攻擊之設計機制]，亦不穩定。欲使保護生效，須將 restrict 設定為自決策輸入排除（即 #raw("C_strict")），或使持續之 S\_i 違反升級為 rejected：E12 顯示，S\_i 持續窗 #mi("L_S = 2") 時 #raw("C_notrej") 之誘導率於 ×0.6 階躍降至 8.6%、漸進 1% 降至 17.2%、漸進 2% 降至 9.3%（決策可用率維持 100%），代價為乾淨資料新增 81 筆誤拒（0.52%）；×0.8 階躍則幾無改善（94.1%）。

#strong[（四）可用資源之多寡取決於證據綁定粒度。] window 政策下 #raw("C_strict") 之決策可用率僅 0.2%，實質不可用；定案之 uebound 下為 99.8%（准入比例 49.5%）。惟 uebound 於乾淨資料上引入 1.3% regret 與 38.9% 誤選——window 政策為全有全無（整窗候選集要嘛完整、要嘛為空），不會濾掉最佳而留下次佳；uebound 產生部分候選集，因而可能濾除真值最佳者。#strong[細粒度換得可用性，代價為新增之誤排除成本。]

#heading(level: 3, numbering: none)[4.12.6 界定]
- 導向策略為本研究定義之#strong[代理決策]（單一新流、以延遲為唯一準則），非真實 RIC 排程器；未建模負載回饋與換手成本。
- #strong[開迴路]：#mi("U_j(t)") 取自乾淨模擬；攻擊誘導之流量轉移不會改變 PRB 用量（未建模負載回饋）。故 #mi("\\rho_{\\text{PRB}}") 描述決策時可見之 PRB 負載，而非攻擊後之實際 PRB 分配。
- #strong[PRB 本身未經驗證]：#raw("RRU.PrbUsedDl") 亦可被受攻陷之 O\-DU 竄改。本節以乾淨之 PRB 為權重，不以上報值為權重；竄改 PRB 之情境本研究未評估。
- 原生 PRB 之絕對數以寫死之常數 139 計算（4.12.1）；比值型指標不受影響。
- 若消費端之目標函數依賴未被驗證之量（如吞吐量，4.5.2 之 B2），C\-ZT 無法提供保護。本實驗以延遲為準則，正因其為 S\_i 所驗證之維度。
- 攻擊僅含延遲類；基數類與成員類攻擊對下游決策之影響未評估。
- 可用資源評估 xApp 之逐窗輸出（乾淨與攻擊情境）為整合原型上之 trace replay：其 DB 與 Resource Termination 為行程內之抽象層，未經 live RIC 之 shared data service。攻擊情境之 PRB 取自乾淨模擬（開迴路）；消費端於閉迴路中之行為未評估。

（腳本 #raw("run_RQ3_decision_replay.py")，註記與准入取自 #raw("zt_kpm_xapp.py") 之 P1–P3；一致性檢查依賴 #raw("run_E10_D1_policy_ablation.py")）

#heading(level: 2, numbering: none)[4.13 本章總結]
本章提出並初步驗證 C\-ZT：以 Detection、Trust Assessment、Policy Enforcement 與可用資源評估四個 xApp（本原型以離線 trace 回放之邏輯模組實作），持續評估 E2 量測資料之可信度、對合作消費端執行准入，並逐窗回報准入政策下之可用資源。在本 ns\-O\-RAN MC 場景與 1 秒觀測粒度下，就三項研究問題之結果如下。

#strong[RQ1：上報值何時構成違反]

- #strong[C\_i] 能證偽造成全域 UE 聯集淨變化之上報資料（D\-30 之 2,400 窗無反例、乾淨誤拒 0），單點虛減於可攻擊窗中之條件偵測率為 100%（以現行報表語意為條件；若報表逐路列出則可能失效，4.6.5）；但對守恆式替換存在明確能力邊界（配平容錯空間 0），持續窗政策下之單窗脈衝亦不升級為 rejected。
- #strong[S\_i]（v12，區間平均延遲，以現行 cell 歸屬（最後事件）為條件）於受控消融中顯示，同時態跨節點參照於 1–2 %\/秒之漸進漂移下偵測率為 0.55–0.77，時間自我參照為 0.11–0.12，與其乾淨誤報率 0.106 相當；空間參照之乾淨誤報率為 0.098，0.5 %\/秒時僅 0.23（4.7.4）。於 AF 1.2–1.5 之階躍攻擊下兩種參照之偵測率皆低（0.13–0.25），v11 之「時間參照捕捉起始點但無法持續標記」於區間輸入下撤回（4.7.5）。以帶標籤注入訓練之監督式分類器（E9b 校準）之乾淨誤報率為 0.423，於全場域共模上升 10 % 時告警率為 0.70（4.7.5.1–4.7.5.2）；惟於相同之誤報校準目標（約 1%；各方法實際測試誤報不同）下（同條件偵測方法比較，4.7.5.5），學過該攻擊方向之監督式 LSTM 之逐窗偵測力高於全部 peer／CUSUM 檢查（delay ×0.6 lift 0.79 對 0.10），只學放大者對調低無反應。#strong[本研究不主張 peer 檢查之偵測力優於監督式方法]，其可主張者為無需攻擊樣本與不依賴攻擊方向。原系統之凍結尺度沿用至區間輸入時，乾淨誤報率升至 0.372／0.331（E\-i，4.7.5.4）。v11 之數字（0.65–0.91 對 0.03–0.04）以累計平均輸入產生，不再採用。D\-30 之全部節點註記皆具備 full consensus，抗串謀之 #mi("m^*_{S,50} = 4")；二者皆取決於 UE 密度，於低密度時將退化。
- #strong[H\_i\-D2] 為由本場景移動行為導出之情境特定斷言：乾淨基線為 vacuous（合法換手從未發生），注入之偵測屬設計必然且非單節點攻擊，其實證效力限於規則行為驗證；#strong[H\_i\-D1] 對明顯超時消失具偵測能力（停留達正常上界之 1.25 倍以上時全數偵測，恰為上界時 0.47；E16），逐 UE 之乾淨誤報率為 0.102，edge UE 偏高（0.20–0.31），此結論對分群門檻不敏感（E15）。

#strong[RQ2：何時拒絕、依何證據、能否恢復]

#block(width: 100%, fill: luma(240), inset: 8pt, radius: 2pt)[#set text(size: 10pt)
#strong[v12 註]：RQ2、RQ3 之數字為累計平均輸入之歷史版本。第一階段以區間延遲重跑 xApp 時，乾淨資料之 rejected 為 844 筆（5.4%）、trusted 為 46.5%（4.9.6.5 之 v12 揭露；非第二階段之正式結果）。

]
- 本章#strong[定義]四種信任狀態與階層式融合規則（4.4.0），以規則稽核揭露交叉佐證之證據綁定缺口，並以規則回放檢驗其決策一致性；每筆判定攜帶其觸發規則與證據。
- D1 證據之節點歸屬定案採 UE 綁定（UE 消失前之 serving mmWave cell）：乾淨資料上可直接採信之註記由 1.2% 升至 50.3%（分母為 15,534 筆有效節點註記），偵測率與延遲不變。乾淨資料之決策分布為 trusted 50.3%／low\-trust 48.7%／abstain 0%／rejected 1.0%（159 筆，全為交叉佐證；L1 硬否決誤觸 0）。
- #strong[D1 證據之規模效應為本章之主要限制]：D1 之逐 UE 誤報率與 7 UE 資料相當，但 30 UE 下 48.3% 之節點註記綁有 D1 證據，使 low\-trust 與誤拒明顯高於前版資料（18.3% 與 0.19%）。事後之敏感度分析（E14）顯示：提高 D1 門檻可將 trusted 提高至 71.2%，代價為偵測延遲由 2.2 窗增為 6.4 窗；所測格點中尚無設定消除乾淨誤拒（最寬鬆設定仍有 0.64%）。凍結之門檻並非此規模之最佳操作點，主結果不因此修改。
- #strong[H\_i\-D1 之基線為「連續最後事件歸屬 LTE」之窗數]，與 mmWave 鏈路劣化相關（4.8.1 之 PHY 交叉驗證；相關不是機制證明）：合法之無線環境變化（如新增遮蔽）可能被視為異常，此與 edge UE 誤報率較高（4.8.6）方向一致。另，D1 之偵測數字基於改動錨點列之注入，不代表單一受攻陷 mmWave O\-DU 可造成之情境（4.8.6）。
- 信任狀態不永久繼承前窗；E11 中所有引發轉移之情境，於 60 秒追蹤期內皆回到乾淨對照，且攻擊造成之判定差異亦包含判定減輕。規則中統計證據升級為 rejected 之唯一路徑為同窗交叉佐證；#mi("S_i") 之持續違反本身不升級。現行 #mi("L_C") \= 2 下，間隔至少一秒之重複單窗脈衝不升級（E11b）。候選之 #mi("S_i") 持續性升級規則（E12）於 #mi("L_S = 2") 時可使僅排除 rejected 之消費端之誘導率降至 8.6%–17.2%，代價為 0.52% 之新增乾淨誤拒；未採用。
- 融合順序之事後修正：原「第一條符合即決定」使 #mi("C_i") 首次違反之窗（#raw("R1_CI_PENDING")）遮蔽同窗之 rejected 證據；改為嚴重度序後（4.4.0（三）），乾淨資料之 15,534 筆註記不變，注入實驗中 222 個 (節點, 窗) 由 low\-trust 改為 rejected（E11 26、E11b 196），其餘實驗逐位相同。

#strong[RQ3：保留之可用資源與驗證開銷]

- 未經驗證時，延遲壓低攻擊之誘導率為 93.8%–99.2%（代理決策）。定案政策與嚴格准入下，×0.6 階躍降至 2.2%、漸進漂移降至 4.1%–8.3%；較接近偵測門檻之 ×0.8 階躍僅降至 46.2%。
- 嚴格准入之代價：乾淨資料上之保留可用容量比 #mi("\\rho_{\\text{cap}}") 為 49.5%、原生 PRB 之保留比例 #mi("\\rho_{\\text{PRB}}") 為 50.6%（PRB 能見度損失 49.4%），決策可用率 99.8%，並引入 1.3% 之 regret。僅排除 rejected 之准入政策於 ×0.8 階躍無保護效果，於較大幅度之攻擊下誘導率仍有 57.2%–59.1%。
- 驗證層（P1–P3）之運算開銷（離線重放微基準之跨窗 P99，不含傳輸、解碼與共享資料層）為 1.16–1.42 ms（三次量測），佔 1 秒量測週期之 0.12%–0.14%；四個 xApp 合計之 P99 為 1.10–1.14 ms（另三次量測），第四個 xApp 僅增加約 0.013 ms。

上述結果支持 E2 量測資料持續零信任驗證之#strong[初步方法可行性]。尚未完成者：三類證據之聯合端到端效能、live E2 綁定與端到端延遲、各 xApp 之獨立部署與其間經 shared data service 之通訊、閉迴路下之決策保護效果、依部署規模校準 D1 門檻與交叉佐證強度，以及吞吐量竄改之驗證（須以資源量測為佐證，4.5.2）。

#heading(level: 2, numbering: none)[實驗設定總表]
#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 7, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([項目], [C\_i], [S\_i], [E9], [H\_i\-D1], [H\_i\-D2], [xApp]),
  [資料集], [D\-30], [D\-30], [D\-30], [D\-30], [D\-30], [D\-30],
  [seeds], [8], [8], [8], [8], [8], [8],
  [duration], [300 s], [300 s], [300 s], [300 s], [300 s], [300 s],
  [window], [1 s], [1 s], [1 s], [1 s], [1 s], [1 s],
  [注入], [灌水／虛減／替換 sweep], [漂移 0.1–15 %\/秒], [階躍 AF 1.2–1.5 \+ 漂移], [超時消失（依強度）], [瞬移 239 例], [無（乾淨）],
  [train\/test], [不需訓練], [LOSO], [LOSO], [LOSO], [不需訓練], [LOSO],
  [輸出], [布林斷言], [robust z], [robust z], [證據強度（z\_d）], [布林斷言], [信任狀態],
  [主要指標], [反例數／偵測率], [偵測率 vs 漂移、FPR], [偵測率 vs 幅度], [FPR\/TPR\/delay], [乾淨基線（vacuous）], [決策分布、延遲])]
#strong[補充實驗]

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 4, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([項目], [E10／E14], [決策重放（4.12）], [E11／E11b／E12]),
  [資料集], [D\-30], [D\-30（序列後半段）], [D\-30],
  [變因], [D1 之節點歸屬政策（window／uebound）× 持續性 #mi("L_H")；E14 另掃 τ\_H（事後新增）], [攻擊 × 准入政策 × 註記政策], [注入長度、脈衝間隔、#mi("L_C")、#mi("L_S")],
  [輸出], [決策分布、偵測率、延遲、歸因], [#mi("\\rho_{\\text{PRB}}")、#mi("V_{\\text{PRB}}")、#mi("\\rho_{\\text{cap}}")、決策可用率、regret、誤選率、誘導率、資源准入遮罩], [轉移／恢復延遲、rejected 比例、乾淨誤拒率],
  [狀態], [已完成（2026\-10\-13，D\-30；4.9.6.5、4.9.6.6）], [已完成（2026\-10\-13，D\-30，含原生 PRB）], [已完成（2026\-10\-13，D\-30；4.4.0（四）、4.6.7）])]
#strong[主結果產出後新增之補充實驗]（規格 #raw("docs/thesis/E15_E18_supplementary_spec.md") v1，先於結果定案；皆不改凍結參數與主結果）：E14（D1 門檻與持續窗，4.9.6.6）、E15（D1 分群門檻，4.8.6）、E16（D1 嚴重度–反應曲線，4.8.6）、E17（校準期中毒 #mi("k = 4")、5，4.7.8）、E18（攻擊情境下可用資源評估 xApp 之逐窗輸出，4.12.4）、M1（四個 xApp 合計之處理時間，4.9.5）。

主結果之全部實驗於 2026\-10\-13 以 #raw("scripts/run_d30_pipeline.sh") 於 D\-30 上依序執行（#raw("ZT_DATASET=d30")），各腳本之內建檢查全數通過；實際秒系列（E9、E9b、E9c、E9d、E13、慢性中毒）之回歸基準於人工核對後建立。S\_i 相關者另於 2026\-11\-15 以區間平均延遲重跑（#raw("scripts/run_phase1_Si.sh")），本文 4.7.1、4.7.4–4.7.5.4 採該次輸出。

#heading(level: 2, numbering: none)[三殘差能力矩陣]
#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 5, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([攻擊], [C\_i], [S\_i], [H\_i\-D1], [H\_i\-D2]),
  [灌水 (\+k)], [#strong[主要可偵測]], [不適用], [不適用], [不適用],
  [單點虛減（現行報表語意：每個 UE 每窗只列於一個 cell）], [#strong[主要可偵測]（可攻擊窗；若報表逐路列出則可能失效）], [不適用], [條件性佐證], [不適用],
  [全域壓制虛減], [#strong[主要可偵測]], [不適用], [條件性], [不適用],
  [delay 漂移／階躍], [不適用], [#strong[1 %\/秒以上之漂移可偵測]（full consensus 窗；乾淨誤報約 0.10）；AF 1.2–1.5 之階躍、0.5 %\/秒以下之漂移與貼門檻偏移之偵測率低（4.7.4–4.7.5、4.7.8）], [不適用（惟於高 UE 密度下常與 D1 證據重合而升級，4.9.6.6）], [不適用],
  [teleport], [不適用], [條件性], [不適用], [#strong[主要可偵測]（by construction）],
  [守恆式替換], [#strong[盲點]], [條件性], [設計上之佐證（未驗證，4.6.6）], [條件性],
  [單窗脈衝灌水], [觀察到但不升級], [不適用], [不適用], [不適用],
  [純吞吐竄改（B2）], [未涵蓋], [未涵蓋], [未涵蓋], [未涵蓋])]
