#import "@preview/mitex:0.2.7": mi, mitex
= 對抗賽局：學習型偵測端與學習型攻擊者（設計；已於累計輸入上執行一次，待第二階段重訓）
#block(width: 100%, fill: luma(240), inset: 8pt, radius: 2pt)[#set text(size: 10pt)
#strong[狀態與揭露]：本章為 2026\-10\-28 於華沙工業大學（WUT）之討論後新增之研究方向，2026\-11\-07 決定納入本論文。本章內容為#strong[事先登錄之規格]（#raw("docs/thesis/E19_DRL_game_spec.md")、#raw("docs/thesis/E19_stage3_data_spec.md")）：v1 之參數（Q\-a～Q\-g）已於 2026\-11\-07 確認；v2 將訓練流程改為 PSRO，其參數 R\-a～R\-f 於 2026\-11\-08 經使用者確認（皆採建議值），亦於任何訓練之前定案。#strong[本章不列實驗數字]：PSRO 訓練（6 組：O\-full／O\-outcome × 3 個訓練 seed）與最終評估已於 2026\-11\-09 至 11\-12 以累計平均輸入執行一次，事先登錄之主判準下學習決策未優於規則版基線前緣（負面結果；#raw("E19_eval_final_spec.md") §12–§13，含事後分析之揭露）；6 組中 5 組於 6 輪預算內未達 NashConv 停止門檻。該次結果屬歷史版本，待第二階段以更正後之輸入重訓（#raw("phase2_percell_spec_v0.md") 步 7）後再報，結果處標【待填】。第四章之規則版（git tag #raw("rulebased-v1")，含 4.4.0（三）之嚴重度序修正）為本章之基準線，其數字不因本章而改變。

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

本章回答 RQ4（1.4）之三個子題：（4a）面對會學習之攻擊者，偵測從何處開始、攻擊者於此前獲得多少；（4b）只能比規則更嚴之學習決策，能否於相同之乾淨誤拒率下將此點前移；（4c）token 隨信任狀態連動洩漏什麼。

#heading(level: 2, numbering: none)[5.2 賽局之結構：兩個學習者、一條管線]
#strong[參與者]：（一）#strong[學習型攻擊者]：一個被攻陷之 O\-DU（gNB k），身分合法、上報值皆在合法範圍內；（二）#strong[學習型偵測端]：P2 Trust Assessment xApp 內之學習決策（5.3）。其餘 6 個 gNB 為誠實 peer，LTE 錨點為信任根。

#strong[一個時間步]（1 秒）：攻擊者選擇乘數 #mi("a_t")，上報「實際下行延遲 × #mi("a_t")」→ P1 計算證據並檢查 token（5.5）→ P2 先以規則表得出判定下限，學習決策於下限之上作出判定 → P3 依准入政策產生 policy\-admitted KPM → RC xApp 依准入之資料做 traffic steering → UE 換手或不換手。攻擊者觀察其結果（5.4），兩者各自依其獎勵更新策略。

#strong[兩方各自之取捨]：

- #strong[攻擊者：影響力對隱匿性]。謊報越多，越能誘導 steering，但越易觸發 #mi("S_i")；獎勵直接表達此取捨（5.4）。
- #strong[偵測端：偵測對誤拒（可用性）]。判定越嚴抓得越多，但誠實報告被拒，可用資源下降（4.12 之 #mi("\\rho_{\\text{PRB}}")）；固定規則等於事先選定此曲線上之一點，且該點公開、不移動。偵測端之獎勵對誠實報告之 rejected 給予 β \= 5 之懲罰，使「全部拒絕」不能得分（5.3）。
- #strong[互相依賴]：攻擊者之最佳隱匿程度取決於偵測端於何處觸發；偵測端之最佳嚴格度取決於攻擊者如何進攻。此相依使問題成為賽局，而非兩個獨立之最佳化問題。

#strong[對應之賽局設定與訓練流程（PSRO；E19 v2）]：兩個學習者若只輪流訓練一次，可能互相追逐——偵測端學會新攻擊、卻忘記舊攻擊。故訓練採 PSRO（policy\-space response oracles；Lanctot et al., 2017）；以 DRL 作最佳回應之 double oracle 於安全賽局之先例見 Eghtesad et al.（2020）；於假資料偵測，Eghtesad 等人（2026）已以 PSRO 求攻防之混合均衡，且防禦者 reward 含誤報成本（交通路網）。本章沿用此作法，不以 PSRO 或攻防 RL 本身為貢獻；與其差異在於：偵測端之輸入含攻擊者控制不到之場域參照、學習決策受規則下限約束，且賽局為一般和（其為零和），並以 3 個訓練 seed 報告訓練變異。雙方各維持一個策略池：偵測端池之 #mi("D_0") 為第四章之規則版（基線 B1），攻擊者池之 #mi("A_0") 為第四章之腳本攻擊。每一輪：（一）池中每對策略於評估 seed 上對戰，填出雙方之報酬表；（二）以 meta\-solver 求此一般和雙矩陣賽局之 Nash 混合；（三）偵測端以 MaskablePPO、攻擊者以 PPO，各對另一方之混合訓練一個新的最佳回應；（四）加入各自之池。當新的最佳回應相對目前混合之增益和（NashConv，即 exploitability）降至第 1 輪之 5 % 以下（完成總下降量之 95 %），或達最大輪數時停止。Round 0 即第四章（#mi("D_0") 對 #mi("A_0")），須重現第四章之數字（一致性檢查 G4）。

#strong[主張之範圍]：僅為#strong[受限賽局（目前之策略池）之近似均衡]，以 NashConv 衡量並報告其隨輪數之曲線；#strong[不是]全域均衡保證。此設定亦可視為防守方承諾策略、攻擊方最佳回應之安全賽局之推廣（Tambe, 2011）。賽局為一般和：偵測端之誤拒代價由系統可用性承擔，非攻擊者之得分。所有偵測端策略皆受規則下限約束（5.3），故任何混合仍只會比規則更嚴。

#strong[與資料階段之對應]：Round 1 之偵測端最佳回應對應 Stage 1（穩定場域、腳本攻擊）；其後之輪次對應 Stage 2（學習型攻擊者）；凍結 vs 線上：以最終混合為凍結版，另以線上更新版對最終攻擊者混合比較；Stage 3：最終之策略池於新資料上評估，不再訓練（5.6）。PSRO 於 O\-full 與 O\-outcome 兩種觀測層級各跑一次；token 洩漏於最終輪以 O\-outcome\+token 量測（5.5）。

#strong[定案之參數]（E19 v2 §10b，2026\-11\-08 確認）：#mi("A_0") 為第四章之三個腳本攻擊（×0.6 階躍、×0.8 階躍、漂移 1 %\/秒）；報酬表於 LOSO 之測試 seed（8 fold）上評估取平均；meta\-solver 為 Lemke–Howson（初始 label 固定，以確保決定性）；停止門檻為第 1 輪 NashConv 之 5 %（2026\-11\-09 由絕對門檻 ε \= 0.01 改為相對門檻，先於任何 PSRO 訓練；因偵測端每步報酬之量級僅約 0.01）、最多 6 輪；觀測層級如上；每個最佳回應至多訓練 300,000 步、每 50,000 步存檔，以該 fold 之訓練 seed 驗證並保留分數最高之存檔（#strong[事後修正]，2026\-11\-09：原擬以 Round 1 之學習曲線取平穩點，但攻擊者之學習曲線隨訓練退化，平穩點規則不適用；見 E19 §2b）。

#heading(level: 2, numbering: none)[5.3 學習型偵測端：位於 P2、規則下限之上]
#strong[位置]：學習決策位於 P2 Trust Assessment xApp 內，取代第四章 L2 之固定決策（#mi("S_i") 與 #mi("H_i")\-D1 之情況）；#mi("C_i") 與 #mi("H_i")\-D2 維持 L1 規則式硬否決（其判定不依賴可調門檻，攻擊者只改 delay 時無可試探之界線）。

#strong[規則下限（floor）與 action mask]：每個 (節點 j, 秒 t) 先以 4.4.0 之規則表（嚴重度序）得出判定，作為下限。若觸發 L1 之 rejected 規則（#raw("R1_AUTHZ")、#raw("R1_CI_VETO")、#raw("R1_D2_VETO")）或 L3（abstain），由規則直接決定，不交給學習決策。其餘情況，學習決策之動作為 {trusted, low\-trust, rejected}，以 action mask（Huang & Ontañón, 2022）限於嚴重度不低於下限者：

#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 2, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([規則下限], [學習決策可選之動作]),
  [trusted], [trusted、low\-trust、rejected],
  [low\-trust], [low\-trust、rejected],
  [rejected], [rejected（無選擇）],
  [abstain], [abstain（僅由規則產生，永不視為 trusted）])]
因此#strong[學習決策只能升級、不能放寬]規則之判定：依構造仍為 fail\-closed，且每筆判定仍記錄設定其下限之規則代碼。此設計與安全強化學習之 shielding 同一精神——由外部規則限制學習者可採取之動作（Alshiekh et al., 2018）。主版本為 V\-escalate（下限為嚴重度序 #raw("fuse()") 之完整判定）；消融版本 V\-replace 之下限僅含 L1（#raw("R1_CI_PENDING") → ≥ low\-trust）與 L3，用以量測下限之價值；若 V\-replace 於相同乾淨誤拒下 TPR 較規則低，如實報告。

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

#strong[目的與界定]：規則只看一個窗（#mi("C_i") 看 #mi("L_C") \= 2 個窗）；學習決策看 5 秒歷史，可對殘差逐窗爬升之節點提前升級——此即慢速、適應性攻擊者之樣態（E12 之 #raw("R2_SI_PERSIST") 為其固定規則版對照，4.4.0（四））。學習決策#strong[不能]將 low\-trust 放寬為 trusted，故不能改善第四章之 D1 規模效應（4.9.6.6）；凍結之策略仍為固定函數，可被試探；線上學習則重新打開校準中毒之風險（Q6）。

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

#strong[目前實作]：授權伺服器之邏輯（發放、檢查、撤銷、連動參數、事件紀錄）已實作並通過單元測試（#raw("test_oauth_sim.py")）；尚未接入回放管線與賽局環境。#raw("R1_AUTHZ") 與 #raw("R1_STAGE1") 皆尚未於 #raw("fuse()") 實作（4.4.0（二））。

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

#strong[成功判準]：偵測端於相同乾淨誤拒率下，「TPR 對偵測延遲」優於基線 1–3 之前緣，且 E9c 共模下之誤報不高於規則版。V\-escalate 之 TPR 依構造不低於基線 1。做不到即報負面結果，不調整獎勵使其通過；任何獎勵或超參數之事後調整須標「事後修正」並保留原結果。

#strong[環境之一致性檢查]（先於任何訓練；失敗即停）：G1——無攻擊、規則版 L2 逐筆重現嚴重度序之 15,534 筆乾淨註記；G2——重現 E11 之轉移統計與 RQ3 之誘導率；G3——同一 seed、同一策略重跑逐位相同；G4——PSRO 之 Round 0（#mi("D_0") 對 #mi("A_0")）重現第四章之 TPR、乾淨誤拒與誘導率。環境直接呼叫第四章之判定函式，不複製改寫。

#heading(level: 2, numbering: none)[5.8 目前狀態]
#block(width: 100%)[#set text(size: 9pt)
#set par(first-line-indent: 0pt, justify: false)
#table(columns: 2, inset: 4pt, align: left, stroke: 0.5pt,
  table.header([項目], [狀態]),
  [規則版基準線], [完成：嚴重度序修正通過 C1–C4，git tag #raw("rulebased-v1")（4.4.0（三））],
  [規格], [E19 v1、Stage 3 資料規格：定案；E19 v2（PSRO）：定案（2026\-11\-08）],
  [授權層], [邏輯已實作並通過單元測試；未接入],
  [Stage 3 資料], [收集程序已結束（S3\-TM3 seed 4200–4205 於 2026\-11\-11；其餘於 2026\-11\-13 至 11\-14）；後者之逐 seed 檢查待做。以原版模擬器收集，適用同一量測語意問題，第二階段是否重收未定],
  [賽局環境（G1–G4）], [完成（2026\-11\-09；累計輸入）],
  [偵測端／攻擊者訓練與結果], [已於累計輸入上執行一次（PSRO 2026\-11\-11、最終評估 2026\-11\-12；主判準為負面結果，歷史版本）；第二階段重訓後填入【待填】])]
