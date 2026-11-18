# 指導教授 v1.12 審查意見（2026-11-18）對照紀錄

來源：`Cindy_v1.12_審查意見_2026-11-18.pdf`（11 頁）。本檔只記錄對照與已算出之數字；**不改任何正文／結果**。腳本：`scripts/advisor_20261118/`，輸出：`data/results/advisor_20261118/`（`data/` 被 gitignore）。

## 週一：τ·s／median（第 (1) 件事）
- 輸入：D-30 區間延遲（`ZT_DELAY_SOURCE=reconstructed`）；尺度 = E9 族之 C-2 `global_scale`（LOSO，每受測 seed 用其餘 7 seed）：0.160–0.171 ms。peer 中位數 = 同窗其他 mmWave cell 之中位數（`MIN_NEIGHBOR=2`）。
- τ·s／median：**中位數 0.785**（p10 0.67、p90 0.90；15,534 個 (cell, 窗)）；seed/cell 中位數範圍 0.72（4206）–0.85（4204）；≥1 者 0.92%。→ 報低約 21% 以下才可能被抓；B1 結論（中等報低抓不到）成立，容許帶為 ±79% 而非 ±110%。
- xApp 融合用 C-1 尺度（0.131–0.140，比 C-2 小 17–21%），比值更小；此處僅以比例推估（≈0.65），**未逐窗計算**。
- B2 公式（1 − τc／(rT)，c = s／該序列平均，T = 注入後窗數 ≈ 150，偏移為 r·(t−t0)·mean 線性、無上限）vs E9 空間參照實測：0.5%/s 0.04 vs 0.22；1%/s 0.48 vs 0.54；2%/s 0.74 vs 0.77；4%/s 0.87 vs 0.88；8%/s 0.93 vs 0.94；15%/s 0.965 vs 0.965。0.5%/s 以下差異來自乾淨誤報底（≈0.11）。
- B3：殘差 (d − peer 中位數) 之 z 分布不對稱：p1 −3.5、p5 −2.1、p95 +5.4、p99 +11.9；|z|>4 為 8.4%（常態應 0.006%）。殘差之穩健標準差 0.203 ms > C-2 尺度 0.165 ms；以殘差自身尺度則 5.9%。教授推測「尺度仍用累計資料」不成立（區間尺度 0.160–0.171、累計 0.054）。**探索性（全部節點-窗），與論文 0.098–0.11 之樣本不同，不得取代。**

## 週一：S3-TM3 每窗成員數（第 (3) 件事）
- 完全無列：4203 窗 0–6（7 窗）、4204 窗 0–3（4 窗）各缺 1 UE，其餘 0。
- 有列但本窗無新 Rx（累計 nRxPDUs 未增）：每窗平均 3.5–5.6、最多 12；300 窗中 287–299 窗至少 1 個 → 區間語意下 TM3 幾乎每窗有「缺值」UE；`interval_source` 缺值直接報錯，須先訂缺值規則才能用 TM3。
- 同窗兩 cell：0，但主檔每 UE 一列，此數字無資訊量；須 r9 重收之 Stage 3 才量得到。→ 成員等式之「成員」須取 RRC 掛載名單（O-1／CU-CP），不能取「本窗有流量」。

## 與既有工作之對照
- B5：E25（逐 cell CU-CP 名單，D-30 乾淨 0／15,534，閉合 A1–A4）、E26（連帶拒絕與歸責）、D-30 雙掛 0／72,000。N22 自然換手 75 個窗中換手案例：窗尾歸屬 75/75 正確，71 個兩 cell 同窗皆有 Rx → 合法重疊存在於「流量」定義，不存在於 O-1 定義（雙掛 0）。
- B6：D-30 為 NoAuto（無 NR 間換手）；v11/v12 已改稱「最後事件歸屬 LTE」；D-30H（r8d）已收、D-30P 進行中。
- C1：E19 判準為對基線前緣之比較（非字面「同 FRR」）；實測 DRL 乾淨誤拒 0.0102 與 D0 逐位相同；PSRO 5/6 組未達門檻（方案 A）。
- B4：時間參照＝前 10 窗中位數（`W_HIST=10`），隨漂移移動，非凍結基線。

## E5：簡報 v1.12 未標 pre-correction 之數字（已讀 .pptx 原文）
- 第 8 頁：「93.8–99.2% of opportunities」（備註亦同）。
- 第 61 頁（RQ3）：93.8–99.2%、×0.6→2.2%、drift 4.1–8.3%、×0.8→46.2%、49.4% PRB 可見度損失、99.8%、38.9%。
- 第 64 頁：m*_S,50 = 4、3 節點 16.8%、4 節點 99.99%、peer-vs-self gap +0.76–+0.83（v12 區間資料之空間 vs 時間為 0.55–0.77 vs 0.11–0.12）。
- 第 56 頁（人口檢查）：未見延遲語意相依（以 UE 名單基數為準），是否須標示待使用者判斷。
- 尚未對照：第 15/16/17/45/66/72 頁矛盾字樣、第 22 頁「248.5%」、第 31/50 頁等（E5 其餘列）。

## 書目核對（以 WebSearch 查詢結果之書目資料，非逐字原文）
- Liu, Ning, Reiter, "False data injection attacks against state estimation in electric power grids", ACM CCS 2009, pp. 21–32, doi:10.1145/1653662.1653666 ✓（擴充版：ACM TISSEC 14(1), 2011）。
- Mo, Sinopoli, "Secure control against replay attacks", 47th Allerton 2009, pp. 911–918, doi:10.1109/ALLERTON.2009.5394956 ✓。
- Ganeriwal, Balzano, Srivastava, "Reputation-based framework for high integrity sensor networks", ACM TOSN 4(3), Art. 15, May 2008, doi:10.1145/1362542.1362546 ✓。
- Carlini et al., "On Evaluating Adversarial Robustness", arXiv:1902.06705 ✓；Tramèr, Carlini, Brendel, Mądry, "On Adaptive Attacks to Adversarial Example Defenses", NeurIPS 2020, arXiv:2002.08347 ✓。
- **未核對**：NIST IR 8625［15］、arXiv:2603.11433［22］、［24］–［26］、TS 28.552 granularity period 條號、TS 23.501 §5.30（SNPN）。須逐筆查原文（CLAUDE.md 規則：標準條號只用已核實者）。
