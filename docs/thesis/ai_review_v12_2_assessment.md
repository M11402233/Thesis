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

## 使用者決定（2026-11-19）與落實

- **A1 → (b) 改程式**：`zt_kpm_xapp.py` 新增證據可得性閘（`EVIDENCE_GATE`，預設開；`ZT_EVIDENCE_GATE=0` 只供重現歷史輸出）：註記之 S_i 不可得（`si_raw`／`S_i` = unavailable，或 R3_ABSTAIN 為最終或 also_matched 規則）→ 任何准入政策皆不准入，判定標籤不變，另記 `evidence_gate`；`run_RQ3_decision_replay.admitted` 之 C_restrict_annot 同步。審稿之反例重跑：開閘時 strict／restrict_annotated 皆不准入；關閘時與原行為相同。`C_none`、`C_notrej` 為對照用之假想消費端，非 P3 政策，未加閘。影響量測（D-30、區間重建延遲、severity，開閘 vs 關閘）：`data/results/phase2/A1_evidence_gate/`。
- **A2 → E30 修正**：見 `E30_coevolution_spec.md` §0a；`psro.py --payoff-split train`。

## v12.3 落實（2026-11-19）

`thesis_v12_3.md`、`chapter6_v12_3.md`、`thesis_typst/frontpages/abstract.*.typ`；腳本 `scripts/v12_3/`。A1 → 4.4.0（三）、4.4.3（三）、4.9.3（證據可得性閘）、6.3.3；A2 → 1.5 C4、5.2、6.1 RQ4；A3 → 3.3.1；A4 → 4.0 引言、4.9.1–4.9.2、4.12、4.13、5.2；A5 → 6.4 第 2 點；A6 → 4.8 限制；A7 → 1.4（R7、RQ4）、1.5 C4、第五章、6.1／6.2／6.3.4；A8 → 1.5、2 章比較表、4.7.5.5、4.13；B1 → 1.2、摘要；B2 → 4.0.1、4.0.4；B3 → 1.5、4.9.6.6、4.13；B4 → 1.5、4.9.5、4.13、6.1；B5 → 1.2；B6 → 3.3.3、4.8；C1 → 4.7.5.5；C2 → 第六章版本表；C3 → 4.7.5.5 標題與各處引用改「同條件偵測方法比較」。
E 節：資源分配移出本篇（使用者：「這篇做 evaluation，下一篇做 allocation」）→ 1.4 RQ3、1.5 C3、4.12、6.1、6.2、6.4 第 8 點；6.5 之凍結 vs 線上、token 洩漏、Stage 3 改為【待作者核認】。
