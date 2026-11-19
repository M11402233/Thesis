#import "@preview/mitex:0.2.7": mi, mitex
= 持續攻防演化：學習型偵測端與學習型攻擊者（設計；E19 已於累計輸入上執行一次，新主判準 E30 待第二階段執行）
#block(width: 100%, fill: luma(240), inset: 8pt, radius: 2pt)[#set text(size: 10pt)
#strong[狀態與揭露]：本章為 2026\-10\-28 於華沙工業大學（WUT）之討論後新增之研究方向，2026\-11\-07 決定納入本論文。原設計為 E19（#raw("docs/thesis/E19_DRL_game_spec.md") v1／v2、#raw("E19_stage3_data_spec.md")；參數 Q\-a～Q\-g、R\-a～R\-f 皆於訓練前定案）：學習決策只能比規則更嚴、主判準為「相同乾淨誤拒下之偵測力優於規則版前緣」，並以 PSRO 求受限賽局之近似均衡。E19 已於 2026\-11\-09 至 11\-12 以累計平均輸入執行一次：主判準下學習決策未優於規則版基線前緣（負面結果；#raw("E19_eval_final_spec.md") §12–§13，含事後分析之揭露）；6 組中 5 組於 6 輪預算內未達 NashConv 停止門檻。該次結果屬歷史版本，本章不列其數字。另經外部審稿指出（v12.3）：E19 之混合策略由 LOSO 測試 seed 之報酬表求得並回饋下一輪訓練，最終評估亦用同一批 seed，故其測試 seed 並非整個管線之獨立留出（偏差方向有利於學習決策，負面結論不受影響）。#strong[2026\-11\-19 之指導會議（#raw("meeting_minutes_advisor_20261119.md") M1–M4）將本章之主問題改為持續攻防演化]：學習型攻擊者與學習型偵測端於反覆互動中是否持續產生新的攻防情境，偵測端能否識別並適應新的及未見過之攻擊。偵測端改為於事先登錄之區間內雙向調整門檻，以「乾淨誤拒不高於規則版」取代「只能更嚴」；PSRO 改定位為策略池之擴展與探索，NashConv 為輔助。新判準之規格 E30（#raw("docs/thesis/E30_coevolution_spec.md") v1.1）先於任何以新判準所做之計算定案（§6 之數值經使用者確認；輪數上限 6 → 12；§0a 內外層資料分離），於第二階段步 7 以 D\-30P 執行（#raw("phase2_percell_spec_v0.md")），不以修正前之 E19 產物做初步結果；結果處標【待填】。#strong[本章為設計，新功能（動態門檻）尚未實作，新實驗尚未執行]。第四章之規則版（git tag #raw("rulebased-v1")，含 4.4.0（三）之嚴重度序修正）為本章之基準線（F），其數字不因本章而改變。

]
#heading(level: 2, numbering: none)[5.1 動機：固定規則留下之問題]
第四章之攻擊皆為#strong[腳本]：每次模擬只有一種固定形狀與速率，且攻擊者不觀察判定。於此設定下，場域參照對部分攻擊有效（4.13）；四項結果指出適應性攻擊者可得利之處（後三列為累計輸入之歷史版本結果）：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 3, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([第四章之結果], [數值], [章節]),
  [慢速漂移之偵測依賴同時態 peer 參照；以自身歷史為參照者於 ≤ 4 %\/秒時與其誤報水準相當（v12：區間輸入；空間參照優勢限於 ≥ 1 %\/秒）], [1–2 %\/秒：0.55–0.77 vs 0.11–0.12（乾淨誤報 0.098／0.106）], [4.7.4],
  [知道同秒 peer 中位數之手寫攻擊者（Q4 oracle，β \= 0.99）全程未觸發 #mi("S_i")，平均偏差], [23.6 %], [4.7.8],
  [繞過 peer 共識之比例過半所需之串謀節點數], [4（3 個節點時 16.8 %）], [4.10],
  [校準期中毒（E17，#mi("k") \= 4–5）後，1 %\/秒漂移之偵測率], [0.00–0.03], [4.7.8])]
規則本身亦固定：τ\_S \= 4、τ\_H \= 2／3、L\_C \= 2。能觀察自身報告之下場（是否被 steering 選中、是否被判 low\-trust 或 rejected）之攻擊者，可學得規則觸發之位置並停留其下，且可隨時間改變攻擊形狀，而非遵循單一腳本。#strong[第四章未測試此類攻擊者]；Q4 之 23.6 % 為手寫策略之對照點，並非證明之上界，且其 oracle 知識（上報前已知同秒 peer 中位數）於實際 O\-DU 不可得（lag1 攻擊者於 β \= 0.99 時之偵測率為 0.44，4.7.8）。

本章回答 RQ4（1.4）之三個子題：（4a）面對會學習之攻擊者，偵測從何處開始、攻擊者於此前獲得多少；（4b）攻防反覆互動時，攻擊者是否持續找到新的有效攻擊，偵測端能否識別、恢復，並適應未見過之攻擊（E30 之 J1–J5）；（4c）token 隨信任狀態連動洩漏什麼。E19 之原問題——只能更嚴之學習決策能否於相同乾淨誤拒下前移偵測——保留為 J6。

#heading(level: 2, numbering: none)[5.2 賽局之結構：兩個學習者、一條管線]
#strong[參與者]：（一）#strong[學習型攻擊者]：一個被攻陷之 O\-DU（gNB k），身分合法、上報值皆在合法範圍內；（二）#strong[學習型偵測端]：P2 Trust Assessment xApp 內之學習決策（5.3）。其餘 6 個 gNB 為誠實 peer，LTE 錨點為信任根。

#strong[一個時間步]（1 秒）：攻擊者選擇乘數 #mi("a_t")，上報「實際下行延遲 × #mi("a_t")」→ P1 計算證據並檢查 token（5.5）→ P2 依偵測端策略所選之門檻重算規則判定（E30 之 T、TL；TL 再於此下限內選標籤）→ P3 依准入政策產生 policy\-admitted KPM → 代理 steering 決策依准入之資料選擇 cell，其代價以原始 trace 中候選 cell 之真實延遲計算。此為離線 trace 回放：動作不改變下一秒之 UE 歸屬、負載或延遲，不含實際換手或閉迴路回饋。攻擊者觀察其結果（5.4），兩者各自依其獎勵更新策略。

#strong[兩方各自之取捨]：

- #strong[攻擊者：影響力對隱匿性]。謊報越多，越能誘導 steering，但越易觸發 #mi("S_i")；獎勵直接表達此取捨（5.4）。
- #strong[偵測端：偵測對誤拒（可用性）]。判定越嚴抓得越多，但誠實報告被拒，可用資源下降（4.12 之 #mi("\\rho_{\\text{PRB}}")）；固定規則等於事先選定此曲線上之一點，且該點公開、不移動。偵測端之獎勵對誠實報告之 rejected 給予 β \= 5 之懲罰，使「全部拒絕」不能得分（5.3）。
- #strong[互相依賴]：攻擊者之最佳隱匿程度取決於偵測端於何處觸發；偵測端之最佳嚴格度取決於攻擊者如何進攻。此相依使問題成為賽局，而非兩個獨立之最佳化問題。

#strong[對應之賽局設定與訓練流程（PSRO；E19 v2）]：兩個學習者若只輪流訓練一次，可能互相追逐——偵測端學會新攻擊、卻忘記舊攻擊。故訓練採 PSRO（policy\-space response oracles；Lanctot et al., 2017）；以 DRL 作最佳回應之 double oracle 於安全賽局之先例見 Eghtesad et al.（2020）；於假資料偵測，Eghtesad 等人（2026）已以 PSRO 求攻防之混合均衡，且防禦者 reward 含誤報成本（交通路網）。本章沿用此作法，不以 PSRO 或攻防 RL 本身為貢獻；與其差異在於：偵測端之輸入含攻擊者控制不到之場域參照、學習決策受規則下限約束，且賽局為一般和（其為零和），並以 3 個訓練 seed 報告訓練變異。雙方各維持一個策略池：偵測端池之 #mi("D_0") 為第四章之規則版（基線 B1），攻擊者池之 #mi("A_0") 為第四章之腳本攻擊。每一輪：（一）池中每對策略對戰，填出雙方之報酬表（E30：各 fold 之訓練 seed；測試 seed 之報酬另存、只供評估）；（二）以 meta\-solver 求此一般和雙矩陣賽局之 Nash 混合；（三）偵測端以 MaskablePPO、攻擊者以 PPO，各對另一方之混合訓練一個新的最佳回應；（四）加入各自之池。當新訓練之（近似）最佳回應相對上一輪混合之非負改進量之和（NashConv）降至第 1 輪之 5 % 以下，或達最大輪數（E19 為 6、E30 為 12）時停止。於 E30，PSRO 之作用為擴展策略池、產生新的攻防情境，而非求收斂。Round 0 即第四章（#mi("D_0") 對 #mi("A_0")），須重現第四章之數字（一致性檢查 G4）。

#strong[主張之範圍]：策略池內之經驗報酬矩陣以 meta\-solver 求混合策略；NashConv 為近似最佳回應之改進量，作探索診斷與停止規則。近似訓練未找到改進，不代表精確最佳回應沒有改進，故 NashConv 不認證完整策略空間之均衡，亦不是可利用性（exploitability）之上界；反之，亦不得由「未達停止門檻」推論策略池之報酬矩陣沒有均衡——二者屬不同層級。此設定亦可視為防守方承諾策略、攻擊方最佳回應之安全賽局之推廣（Tambe, 2011）。賽局為一般和：偵測端之誤拒代價由系統可用性承擔，非攻擊者之得分。E30 之偵測端策略皆受乾淨誤拒上限約束（5.3），但可比規則寬鬆。

#strong[與資料階段之對應]：Round 1 之偵測端最佳回應對應 Stage 1（穩定場域、腳本攻擊）；其後之輪次對應 Stage 2（學習型攻擊者）；凍結 vs 線上：以最終混合為凍結版，另以線上更新版對最終攻擊者混合比較；Stage 3：最終之策略池於新資料上評估，不再訓練（5.6）。凍結 vs 線上、Stage 3 是否為本篇必做，待作者核認（6.5）。PSRO 於 O\-full 與 O\-outcome 兩種觀測層級各跑一次；token 洩漏於最終輪以 O\-outcome\+token 量測（5.5）。

#strong[定案之參數]（E19 v2 §10b，2026\-11\-08 確認；E30 之變更以「→」標示）：#mi("A_0") 為第四章之三個腳本攻擊（×0.6 階躍、×0.8 階躍、漂移 1 %\/秒）；報酬表於 LOSO 之測試 seed（8 fold）上評估取平均 → E30：選擇用之報酬表取自各 fold 之 7 個訓練 seed，測試 seed 只供評估；meta\-solver 為 Lemke–Howson（初始 label 固定，以確保決定性）；停止門檻為第 1 輪 NashConv 之 5 %（2026\-11\-09 由絕對門檻 ε \= 0.01 改為相對門檻，先於任何 PSRO 訓練；因偵測端每步報酬之量級僅約 0.01；E30 維持）、最多 6 輪 → E30：12 輪（舊 6 輪下 6 組有 5 組跑滿上限）；觀測層級如上；每個最佳回應至多訓練 300,000 步、每 50,000 步存檔，以該 fold 之訓練 seed 驗證並保留分數最高之存檔（#strong[事後修正]，2026\-11\-09：原擬以 Round 1 之學習曲線取平穩點，但攻擊者之學習曲線隨訓練退化，平穩點規則不適用；見 E19 §2b）→ E30：偵測端只在訓練 seed 上乾淨誤拒 ≤ F 之存檔中選。

#strong[資料分離（E30 §0a，v12.3）]：內層（選擇）——meta\-solver、混合策略、NashConv 與下一輪之訓練對手只讀訓練 seed 之報酬表；外層（評估）——測試 seed 之報酬表只供 J1–J6 與最終評估，程式中無任何選擇步驟讀取它（#raw("psro.py --payoff-split train")；預設值重現 E19 之原行為）。

#heading(level: 2, numbering: none)[5.3 學習型偵測端：位於 P2、於事先登錄之區間內調整門檻]
#strong[位置]：學習決策位於 P2 Trust Assessment xApp 內，取代第四章 L2 之固定決策（#mi("S_i") 與 #mi("H_i")\-D1 之情況）；#mi("C_i") 與 #mi("H_i")\-D2 維持 L1 規則式硬否決（其判定不依賴可調門檻，攻擊者只改 delay 時無可試探之界線）。#mi("S_i") 之參照（同窗 peer 中位數、凍結尺度 #mi("s")）亦不由學習改變。

#strong[三種偵測端（E30 §2）]：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 3, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([代號], [門檻], [判定]),
  [F（固定）], [凍結值（τ\_S \= 4、τ\_H^warn／τ\_H^reject \= 2／3）], [規則（＝第四章之規則版，E19 之 #mi("D_0")）],
  [T（動態門檻）], [每秒由策略選 (τ\_S, τ\_H^reject)，τ\_H^warn \= τ\_H^reject − 1], [依所選門檻重算規則判定，不另選標籤],
  [TL（動態門檻＋學習判定）], [同 T], [於「以所選門檻重算之規則判定」之下限內選標籤（action mask，Huang & Ontañón, 2022；同 E19 之 V\-escalate）])]
#strong[門檻區間]（事先登錄）：τ\_S ∈ \[2, 6\]、τ\_H^reject ∈ \[2, 4\]，0.5 一格，每秒至多變化一格（系統穩定性）；另報每節點每 100 秒之門檻變更次數與門檻之時間分佈。L1 硬否決（#raw("R1_AUTHZ")、#raw("R1_CI_VETO")、#raw("R1_D2_VETO")）、L3（abstain）與 P3 之證據可得性閘不交給學習決策，於任何門檻下照常作用。

#strong[誤拒上限（取代「只能更嚴」）]：偵測端最佳回應之存檔只在訓練 seed 上「乾淨誤拒率 ≤ F」者中選；無合格存檔則該輪之最佳回應為 F。測試 seed 上若超過，照實報告。T、TL 於 E9c 共模下之誤拒亦須 ≤ F。

#strong[與 E19 之差異]：E19 之學習決策只能升級規則之判定（主版本 V\-escalate；消融 V\-replace），依構造無法降低乾淨資料之排除（第四章之 D1 規模效應，4.9.6.6）。E30 允許門檻雙向調整，可能降低此代價，但亦打開攻擊者可利用之空間——此代價由 J1–J5 量測，不由構造保證。此設計仍與安全強化學習之 shielding 同一精神：由外部規則與區間限制學習者可採取之動作（Alshiekh et al., 2018）；每筆判定仍記錄所用門檻與規則代碼，可稽核。

#strong[狀態]：#mi("z_j(t)")（#mi("S_i") 殘差）、peer 數、歸屬節點 j 之 D1 #mi("z_d") 最大值與證據強度、#mi("C_i") pending 旗標；上述各值之過去 #mi("k = 5") 秒，以及本決策過去之動作。#strong[不含] peer 中位數與尺度 #mi("s") 本身——參照不由學習決定（4.7.8 Q6：校準被汙染即破壞偵測）。

#strong[獎勵]：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 4, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([真值], [判 rejected], [判 low\-trust], [判 trusted]),
  [竄改], [\+1], [\+λ（0.3）], [−α ×（該秒 steering 錯誤成本，以 RQ3 regret 正規化）；α \= 1],
  [未竄改], [−β（β \= 5）], [−μ（0.05）], [\+μ（0.05）])]
標籤為「該 (節點, 秒) 之報告是否被竄改」；被攻陷節點於注入起點前標為未竄改。

#strong[演算法]：MaskablePPO（sb3\-contrib 2.6.0；PPO：Schulman et al., 2017；Stable\-Baselines3：Raffin et al., 2021），於 PSRO 中作為偵測端之最佳回應訓練器；訓練 seed 0、1、2，報平均與範圍。部署分凍結（frozen）與線上（online）兩種。

#strong[目的與界定]：規則只看一個窗（#mi("C_i") 看 #mi("L_C") \= 2 個窗）；學習型偵測端看 5 秒歷史，可對殘差逐窗爬升之節點提前收緊門檻——此即慢速、適應性攻擊者之樣態（E12 之 #raw("R2_SI_PERSIST") 為其固定規則版對照，4.4.0（四））——亦可於無攻擊跡象時放寬門檻以降低乾淨排除。凍結之策略仍為固定函數，可被試探；線上學習則重新打開校準中毒之風險（Q6）。動態門檻之環境（T、TL）尚未實作（5.8）。

#heading(level: 2, numbering: none)[5.4 學習型攻擊者：模仿之攻擊]
#strong[攻擊]：traffic\-steering 誘導，與 4.12（RQ3）同一威脅。被攻陷之 gNB k 上報較實際為低之下行延遲，使 RC xApp 將 UE 導向實際較差之 cell；數值在合法範圍、身分合法，僅數值為假。第四章不驗證時，腳本版之誘導率為 93.8 %–99.2 %（4.12.4）。

#strong[由腳本到學習]：第四章為 ×0.6、×0.8 階躍與線性漂移，每次模擬一種形狀，且不觀察判定。賽局中攻擊者每秒選擇乘數 #mi("a_t \\in [0.5, 1.5]")，且 #mi("|a_t - a_{t-1}| \\le \\delta = 0.05")；形狀由其自行學得（例如緩慢爬升、停於門檻下、被判 low\-trust 後退回）。控制對象之第一步為 cell 上報之 delay；UE ID 集合（對 #mi("C_i")）為第二步，另訂規格。多節點串謀已由 4.10 之 m\-sweep 涵蓋，本章不納入。

#strong[觀測層級]（兩者皆做，P9）：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 2, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([層級], [攻擊者可見]),
  [O\-outcome], [自身過去上報、steering 結果（是否被選中）、上一已評估秒之 peer 中位數（lag1）],
  [O\-full（最壞情況）], [O\-outcome ＋ 偵測端對自身之過去判定],
  [O\-outcome\+token], [O\-outcome ＋ token 續發／撤銷事件（僅 5.5 之連動版）],
  [禁止], [同秒 peer 中位數（即 Q4 oracle，僅作對照點）])]
#strong[獎勵]：被 steering 選中且非最佳 cell：\+1；被判 low\-trust：−0.1；被判 rejected：−1。

#strong[演算法]：PPO（連續動作），於 PSRO 中作為攻擊者之最佳回應訓練器；訓練 seed 0、1、2。

#strong[與既有攻擊之關係]：KPI poisoning（Alimohammadi et al., 2024）以固定倍數（×1.2–1.5）縮放 KPI；Rogue Cell（Aizikovich et al., 2025）以查詢對預測模型最佳化擾動；本章之攻擊者則依其觀測逐秒調整。

#heading(level: 2, numbering: none)[5.5 授權層：OAuth 2.0 與 #raw("R1_AUTHZ")]
#strong[機制]：於 DU 與 CU／RIC 之間加入 OAuth 2.0（RFC 6749, Hardt, 2012）client credentials 之#strong[邏輯層模擬]（不實作 HTTP；模組 #raw("xapps/verification/authz/")）。token 之 scope 含 DU 身分、可上報之 cell ID、量測類型與請求種類。新規則 #raw("R1_AUTHZ")：token 無效、過期或 scope 不符 → rejected，列於規則表之首（4.4.0（二））。SRCS v16 SEC\-CTL\-NEAR\-RT\-2 NOTE 指出 E2 之認證即授予授權、SCTP 無原生授權機制，此為逐請求授權之動機；本研究#strong[不宣稱] O\-RAN 規範要求於 E2 使用 OAuth。

#strong[分工]：OAuth 限制 DU #strong[能要求什麼]；一致性檢查質疑它#strong[說了什麼]。

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 2, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([情況], [由誰擋下]),
  [未登記或已撤銷之 DU], [token 檢查],
  [合法 DU 為非其所屬之 cell 上報或請求], [scope（#raw("R1_AUTHZ")）；與 E2 Setup 之 cell 清單部分重疊],
  [合法 DU 竄改自身 cell 之數值（主要威脅）], [#strong[OAuth 擋不住]（持有合法 token）；由 #mi("C_i")、#mi("S_i")、#mi("H_i")],
  [合法 DU 試探門檻], [學習決策（5.3）])]
#strong[token 與信任連動（P10 \= B）]：連續 rejected ≥ N \= 3 窗才撤銷或縮小 scope；撤銷生效加隨機延遲 U\[0, D\] 窗，D \= 5；撤銷後重新申請之冷卻 T \= 30 窗。因 token 被拒本身會透露判定，#strong[必報資訊洩漏量測]：（i）攻擊者於 O\-outcome\+token 下推斷「自身是否被判 rejected」之準確度；（ii）連動版與不連動版（對照）之攻擊者可維持偏差差值；（iii）token 事件與判定之互資訊估計。

#strong[目前實作]：授權伺服器之邏輯（發放、檢查、撤銷、連動參數、事件紀錄）已實作並通過單元測試（#raw("test_oauth_sim.py")）；尚未接入回放管線與賽局環境。#raw("R1_AUTHZ") 與 #raw("R1_STAGE1") 皆尚未於 #raw("fuse()") 實作（4.4.0（二））。負載：每個 DU 約每秒一次 token 檢查，2026\-11\-19 會議認為可接受；接入後統計實際請求量。

#heading(level: 2, numbering: none)[5.6 三個階段與資料]
#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 3, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([階段], [情境], [資料與切分]),
  [Stage 1：穩定場域], [7 個 gNB、其中 1 個被攻陷（P8）；偵測端學習正常行為與腳本攻擊（漂移、階躍、超時）；3 DU 僅作壓力測試], [D\-30（#raw("data/ues30_seeds/analysis/")，唯讀）；LOSO：7 seed 訓練、1 seed 測試，輪 8 次；被攻陷 cell 於 cell 2–8 輪流（Q\-a）],
  [Stage 2：學習型攻擊者], [5.4 之攻擊者對凍結偵測端；其後凍結 vs 線上], [同上],
  [Stage 3：提高變異], [正常行為範圍變大：UE 數不同、session 有開有關], [新 ns\-O\-RAN 資料（下表）；訓練於 D\-30 → 測試於 Stage 3（分布外），另報 Stage 3 內 LOSO])]
#strong[Stage 3 資料]（#raw("E19_stage3_data_spec.md")；變體由本研究建議、經同意，依教授所提之「使用者數量與 session 長度」，非 WUT 指定）：除下表所列者外，參數全部同 D\-30（configuration 1、E2 NR 報表、1 秒報表、速度 3–10 m\/s、#raw("--simTime=301")、分析取 0–299 窗），seed 4200–4207（UE 數不同時亂數流不同，#strong[非]配對樣本）。

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 4, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([變體], [改變], [Probe（模擬 6 秒；seed 4200）], [狀態]),
  [S3\-TM3], [30 UE；#raw("--trafficModel=3")：¼ full buffer、¾ bursty（3／0.75／0.15 Mbps，有開有關）], [推估每 seed 約 39 小時；最大 RSS 0.3 GB；5 窗之 UE 數皆為 30], [收集程序已結束（狀態見 5.8）],
  [S3\-U20], [20 UE，full buffer], [約 28 小時；0.9 GB；皆為 20], [收集程序已結束（狀態見 5.8）],
  [S3\-U40], [40 UE，full buffer], [約 78 小時，超過事先訂定之 72 小時上限], [#strong[依事先判準不收]])]
收集自 2026\-11\-08 起以 3 個實例平行執行，共 16 個 seed。每個 seed 完成即檢查：0–299 窗無缺窗、IMSI 集合 \= {1..N}、每窗 UE 數（S3\-TM3 若不恆等於 30，#mi("C_i") 之使用方式須先另訂規格）、PRB 交叉驗證、同 seed 重跑前 5 窗逐位相同；任一失敗即停。新資料只用於本章，第四章之 D\-30 結果不變。

#heading(level: 2, numbering: none)[5.7 指標、基線與成功判準（事先登錄）]
#strong[指標]：主指標為 TPR 與乾淨誤拒率（(節點, 秒)，與 4.9.6.3 同口徑）。另報：離開 trusted／到達 rejected 之延遲（E11 方法）、偵測前已灌入偏差、攻擊者可維持偏差（(a) 未被 #mi("S_i") 偵測，可與 Q4 之 23.6 % 對照；(b) 未被 rejected）、steering 誘導率／regret／#mi("\\rho_{\\text{PRB}}")（4.12）、E9c 共模下之誤報、乾淨 trusted 比例。

#strong[基線]：（1）規則版 L2（嚴重度序）；（2）E12 #raw("R2_SI_PERSIST")（#mi("L_S") 格點）；（3）E14 D1 門檻格點；（4）E9b 監督式分類器。每個學習結果與 1–4 並列（最終評估規格將基線 4 改為只於第四章並列、不納入前緣，#raw("E19_eval_final_spec.md") §2）。偵測端之間之比較須於同一攻擊者下進行；已執行之評估中，針對最終策略訓練之最佳回應攻擊者只對學習型偵測端訓練，規則基線無對應者，該欄之比較不對稱。對基線 1–3 各訓練其最佳回應攻擊者之對稱評估為事後新增，列入第二階段（#raw("phase2_percell_spec_v0.md") §5.1），不取代本節之判準。

#strong[成功判準（E30 §3，2026\-11\-19 起；取代 E19 §8，後者保留為 J6）]：記第 k 輪之攻擊者最佳回應為 #mi("A_k")、當時之偵測端混合為 #mi("\\sigma_D^{(k-1)}")、偵測端最佳回應為 #mi("D_k")。

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 3, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([\#], [問題], [操作定義]),
  [J1], [攻擊者是否找到先前未出現之有效攻擊], [有效：對 #mi("\\sigma_D^{(k-1)}") 之攻擊者增益 \> ε\_A \= 0.01，且 C\_strict 誘導率高於池中既有攻擊者之最佳者；新：五項行為特徵（平均偏移、偏移幅度、作用比例、作用段平均長度、變化度；正規化）與池中每個既有攻擊者之 L∞ 距離 \> δ \= 0.25],
  [J2], [偵測端能否識別新攻擊], [#mi("D_k") 對 #mi("A_k") 之 TPR（非 trusted 為主、rejected 為輔）相對 #mi("\\sigma_D^{(k-1)}") 對 #mi("A_k") 提升 ≥ Δ\_rec \= 0.05],
  [J3], [攻擊改變後能否逐步恢復], [恢復輪數：最小之 r ≥ 1，使 #mi("\\sigma_D^{(k-1+r)}") 對 #mi("A_k") 之 TPR 回到 #mi("\\sigma_D^{(k-1)}") 對池中既有攻擊者之（混合加權）水準；至最後一輪未達者記為截尾],
  [J4], [攻擊者能否持續找到有效攻擊], [逐輪攻擊者增益曲線；增益 ≤ ε\_A 之輪另以加倍步數與另 2 個 seed 訓練，任一 \> ε\_A 則記「探索不足」，不得解讀為防禦提升（此額外訓練不入池、不改混合）],
  [J5], [對未知攻擊之適應], [未入池之 E29 攻擊集（不規則調低／調高之單節點與多節點、×1.2／×1.5 階躍、調高漂移）上之成對 ΔDR，逐輪曲線，並與 F 比較],
  [J6], [偵測品質（E19 之原判準）], [相同乾淨誤拒下對基線前緣之比較])]
結論之寫法（n \= 3 訓練 seed，不做檢定）：每項報「3 組中幾組成立」，3／3 才寫「成立」，2／3 寫「多數情形成立」；O\-full 與 O\-outcome 分開報。NashConv 照報逐輪曲線，不作成功判準。做不到即報負面結果，不調整獎勵使其通過；任何獎勵或超參數之事後調整須標「事後修正」並保留原結果。

#strong[環境之一致性檢查]（先於任何訓練；失敗即停）：G1——無攻擊、規則版 L2 逐筆重現嚴重度序之 15,534 筆乾淨註記；G2——重現 E11 之轉移統計與 RQ3 之誘導率；G3——同一 seed、同一策略重跑逐位相同；G4——PSRO 之 Round 0（#mi("D_0") 對 #mi("A_0")）重現第四章之 TPR、乾淨誤拒與誘導率。環境直接呼叫第四章之判定函式，不複製改寫。E30 另加 C\-1（T 恆選凍結門檻時與 F 逐筆相同）、C\-2（Round 0 重現第二階段步 4–5 之 #mi("D_0") × #mi("A_0")）、C\-3（行為特徵對腳本攻擊之計算值與定義相符）、C\-4（J5 之 F 列重現 E29 之正式結果）。

#heading(level: 2, numbering: none)[5.8 目前狀態]
#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 2, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([項目], [狀態]),
  [規則版基準線], [完成：嚴重度序修正通過 C1–C4，git tag #raw("rulebased-v1")（4.4.0（三））],
  [規格], [E19 v1、Stage 3 資料規格：定案；E19 v2（PSRO）：定案（2026\-11\-08）；#strong[E30 v1.1（持續攻防演化）：定案（2026\-11\-19）]；E29（不規則攻擊）：定案，產生器已實作（#raw("attack_generators.py --selftest")）],
  [授權層], [邏輯已實作並通過單元測試；未接入],
  [Stage 3 資料], [收集程序已結束（S3\-TM3 seed 4200–4205 於 2026\-11\-11；其餘於 2026\-11\-13 至 11\-14）；後者之逐 seed 檢查待做。以原版模擬器收集，適用同一量測語意問題，第二階段是否重收未定],
  [賽局環境（G1–G4）], [完成（2026\-11\-09；累計輸入）],
  [偵測端／攻擊者訓練與結果], [已於累計輸入上執行一次（PSRO 2026\-11\-11、最終評估 2026\-11\-12；主判準為負面結果，歷史版本）；第二階段重訓後填入【待填】。E30：PSRO 之內外層資料分離已實作（#raw("psro.py --payoff-split train --max-rounds 12")）；動態門檻（T、TL）之環境未實作；於第二階段步 7 執行【待填】])]
