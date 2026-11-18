# C3 規格 v0：同資料、同攻擊、同誤報之偵測方法比較（含前作類 LSTM 與範圍檢查）

> 2026-11-18，依指導老師審閱（2026-11-18 PDF §4 C3，P0）。本檔先於腳本執行 commit。離線分析，主結果不變。

## 1. 參照

| # | 項目 | 出處 | 內容 |
|---|---|---|---|
| R1 | 前作之偵測器 | thesis_v12_1 §4.7.5.1；`run_E9b_supervised_baseline.py` 檔頭 | Alimohammadi et al.（OJCOMS 2026，arXiv:2512.01596）：以帶標籤之 AF 1.2–1.5 階躍注入訓練之監督式時序分類（LSTM 等），序列長度 10；自報偵測 ≥ 97.9%、誤報 ≤ 0.07%（簡報隱藏頁 80） |
| R2 | 既有同類實作 | `run_E9b_supervised_baseline.py`（LSTM 1→64、2 層、Adam 1e-3、25 epoch、batch 256、K_ONSET 5、fit gate 0.80） | E9b_rt 於區間資料：校準目標 0.1107，測試乾淨誤報 0.423（未於相同誤報水準比較，v12.1 已揭露） |
| R3 | 樣本、攻擊、t0 | `scripts/advisor_20261118/run_B1_log_onesided.py` | D-30 區間延遲（`ZT_DELAY_SOURCE=reconstructed`）、E9 之 seed×cell 樣本（56 條）、t0 = n//2、LOSO 8 fold |
| R4 | peer 之 1% 門檻結果 | `B1_log_onesided.json` 之 V0e／V3e | 本檔之 V0e／V3e 須逐位重現（檢查 C3-1） |
| R5 | CUSUM | `run_B2_B3_cusum.py`（k = 0.5、ARL0 以訓練 seed 二分搜尋） | 單邊下界於 ARL0≈1000 對 ×0.8 未偵測 0.21 |
| R6 | 範圍檢查 | O-RAN SRCS v16 SEC-CTL-NEAR-RT-17（CLAUDE.md 已核實之條號） | 數值範圍驗證；規格未給 delay 之數值範圍 |

## 2. 方法（全部只用訓練 seed 校準；門檻 = 訓練 seed 乾淨序列後半段之逐窗誤報 1%，CUSUM 除外）

| 代號 | 方法 | 輸入 | 判定 |
|---|---|---|---|
| M1 | 範圍檢查 | 自身值 | 超出訓練 seed 全部乾淨 delay 之 [min, max] 即告警（最緊之可辯護範圍；不校準到 1%） |
| M2 | 自我參照 | 自身前 10 窗中位數 | \|o_t − med(o_{t−10..t−1})\| / s_T，s_T = 訓練殘差之 1.4826·MAD |
| M3 | peer 線性雙側（V0e） | 同窗 peer 中位數 | 同 B1 V0，門檻改 1% |
| M4 | peer 對數雙側（V2e） | 同窗 peer log 中位數 | 同 B1 V2 |
| M5 | peer 對數單側下界（V3e） | 同上 | 同 B1 V3 |
| M6 | peer＋CUSUM | 對數殘差 | 單邊下界、單邊上界各自 ARL0 ≈ 1000（k = 0.5）；兩者分列 |
| M7 | 前作類 LSTM | 自身 delay 長度 10（level 正規化，同 E9b level） | AF 1.2／1.3／1.4／1.5 階躍標籤訓練（設定同 R2） |
| M8 | 攻擊已知之監督式 LSTM | 自身 level ＋ peer 對數殘差（2 通道） | AF 0.6–0.9 與 1.2–1.5 階躍標籤訓練；K_ONSET 改 3（計算量），其餘同 M7 |

## 3. 攻擊（全部自 t0 起、至序列結束）

階躍 ×1.2、×1.3、×1.5（前作之族）；×0.9、×0.8、×0.6（本研究之報低）；漂移下行 1%/s（下限 0.5）、上行 1%/s（上限 2.0）。

## 4. 指標

- 乾淨：測試 seed 後半段之逐窗告警率（M6 另報 ARL0）。
- 攻擊：後半段逐窗偵測率、未偵測比例（後半段無任何告警之序列比例）、首次偵測延遲中位數（窗）。
- 皆報 56 條之平均與 seed 間範圍。

## 5. 檢查（失敗即停）

- C3-0：56 條樣本、8 fold。
- C3-1：M3、M5 之乾淨誤報與各攻擊偵測率逐位重現 B1 之 V0e、V3e（共有之攻擊）。
- C3-2：M7、M8 每個 fold 之訓練 balanced accuracy（機率 0.5）≥ 0.80（同 E9b 事先門檻）；未過之 fold 該方法不採計、只記錄。
- C3-3：確定性——固定種子、`torch.use_deterministic_algorithms(True)`。

## 6. 事先揭露之限制

1. M7 **不是前作之重現**：前作輸入為 per-UE 多項 KPM，本實作只有 per-cell delay；模型與訓練量不同。前作自報之 0.07% 誤報屬其資料與評估方式，本檔不宣稱可比。
2. M8 以與測試相同之攻擊倍率訓練，屬樂觀上界（防守方事先知道攻擊型態）。
3. M1 之範圍取自訓練資料之極值，比任何規格範圍都緊；實際部署之範圍檢查只會更寬、偵測更少。
4. CUSUM 之誤報以 ARL0 表示，與逐窗 1% 不完全同口徑，分列。
5. 同一序列之乾淨後半段亦可能告警（B2 之污染問題）；未偵測比例含此成分。
6. 輸出：`data/results/advisor_20261118/C3_comparison.json`、`.log`；腳本 `scripts/advisor_20261118/run_C3_comparison.py`。
