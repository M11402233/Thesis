# 外部 AI 審稿（v12.2 PDF，2026-11-19）之核對結果

審稿對象：`~/Downloads/Cindy_Thesis_draft_v12_2.pdf`（commit d5f813b）。本檔只記錄 Claude Code 之核對，**未改正文、程式或結果**；修改待使用者決定。

| 項 | 審稿主張 | 核對 | 結果 |
|---|---|---|---|
| A1 | `restrict_annotated` 下 S_i unavailable ＋ D1 weak／strong → low-trust 被准入，與「證據不可得不放行」衝突 | 以審稿附之程式重現（`fuse_detail`／`enforce`） | **成立**：strict 不准入；restrict_annotated 准入（also_matched 含 R3_ABSTAIN）。需使用者決定保證範圍 |
| A2 | PSRO 報酬表取自 LOSO 測試 seed，σ 由其求得並回饋下一輪訓練 | `psro.py` `_eval_job`（測試 seed）→ `fill_payoff` → `solve` → `_train_job(sigma)` | **成立**。最佳回應本身之訓練／存檔選擇用訓練 seed；但混合選擇用到測試 seed → 測試 seed 不是整個管線之最終留出。E19-EVAL 之最終評估亦用同一批 seed。**E30（步 7）尚未執行，須於執行前決定是否改為內層（訓練 seed）求 σ、外層（測試 seed）只評估** |
| A3 | p.15「各 mmWave gNB 各自統計，具完整 per-cell」 | thesis_v12_2.md 第 246 行 | **成立**：與 F1（最後事件歸屬）、兩路混合矛盾 |
| A4 | 「於 Near-RT RIC 內同時運作」「實際承受真實延遲」「UE 換手或不換手」 | 第 399、1689、2136、2361 行 | **成立**：原型為行程內 trace replay，steering 為代理決策、不回饋 |
| A5 | 「split bearer 同時雙路徑非本模擬器所支援」 | chapter6_draft.md 6.4 第 2 點 | **成立**：與 R-5 之「每 UE 每窗皆有兩路事件」矛盾 |
| A6 | 「D2 於 1 秒粒度下成立」 | 第 1674 行 | **成立**：D-30 無合法 NR 換手，只能說未觀察到反例 |
| A7 | 第五章仍為舊設計（6 輪、只能更嚴、近似均衡） | — | **成立**（版本未同步，已知）；另 NashConv 為近似回應之非負改進量，不是 exploitability 上界 |
| A8 | 「同誤報」比較實為校準目標，測試操作點不同 | 4.7.5.5 | **成立**；兩 LSTM 同時改多個變因，正文已揭露 |
| B1 | 「零信任只確認誰在上報」過度概括 | 中英文摘要（**Claude 所寫之初稿**）、第 26 行 | **成立**；摘要為 Claude 之措辭錯誤 |
| B2 | 「注入程式與偵測程式不共享門檻」與白箱／依門檻構造之測試矛盾 | 第 417 行 | **成立** |
| B3 | 「乾淨誤拒無法以門檻消除」 | 第 114、1988、2284 行 | **成立**：只支持所測格點 |
| B4–B6 | P99 為微基準、滑動窗動機、單一參數族 | 未逐句核對 | 方向合理，屬措辭收窄 |
| C1 | p.59 擬合門檻「≥ 0.95」 vs 規格 0.80 | 第 1298 行 vs `C3_same_condition_comparison_spec_v0.md` C3-2、`run_E9b_supervised_baseline.py` FIT_GATE = 0.80 | **成立**：正文寫錯門檻（實際 0.995–0.998，不改通過與否） |
| C2–C3 | 第六章版本聲明疊加、C3 代號同名 | — | 成立，整理類 |
| D、E、F | 非幻覺之項目、須作者認領之決定、核對範圍 | — | 同意；審稿未重跑實驗，數字之真實性未受質疑 |
