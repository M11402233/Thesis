# S_i 區間延遲更正分析 規格 v0（2026-11-13；第一階段；待使用者確認 §9）

> 上游：`report_semantics_spec_v0.md`（v0.1，§8.1 已決）、`ns3_report_semantics_audit_20261113.md`、`review_ch4_verification_20261113.md`。
> **定位**：已知資料（D-30，8 seed）之**更正分析**，不稱為全新未見測試；正文須揭露 D-30 各 seed 已於舊版本中看過。

## 1. 目的

以正確之區間（每窗）延遲重做 S_i 之乾淨校準／評估與 E9，回答：
- **Q-A（第一個問題）**：區間延遲於可比較之 mmWave cell 之間，是否仍有足夠穩定之關係可供檢核（跨 cell CV、乾淨誤報）。
- **Q-B**：語意錯置對原系統之影響（E-i）。
- **Q-C**：區間量測版本之方法效益（E-ii）：空間參照 vs 時間參照之相對表現是否保持。

## 2. 前提（硬性，未過即停）

| # | 前提 | 未過時 |
|---|---|---|
| P-1 | R-6：NoAuto seed 4200 跑滿 301 s 之舊檔與 D-30 原檔逐位相同（最後一窗除外） | 停，R-5 build 有副作用，先查 |
| P-2 | Q2 準則（`check_Q2_acceptance.py`，同一 301 s run）：全體與窗 ≥ 270 之 p99 ≤ 0.05·s′、max ≤ 0.25·s′；S_i 乾淨判定逐筆相同 ≥ 99.9 %；門檻附近逐筆列出 | 反推不可用：D-30 須以 R-5 build 重新收集（8 seed，約 7 天／2 實例）後以 `exact` 重做本規格 |
| P-3 | 所有讀延遲之入口均已切換（§4），預設路徑逐位不變（已驗：`TraceReplaySource` 與三個 `load_cell_delay` 於 8 seed 之輸出雜湊相同） | 停 |

s′ 之來源（Q2-(i)）：R-5 run 之精確值經凍結之 `TrustAnchor` 公式（1.4826·MAD＋1e-9）。**精確值只有一個 run，無法 LOSO**；此偏離見 §9 Q-1。

## 3. 輸入

| 模式 | 用途 |
|---|---|
| `ZT_DELAY_SOURCE=reconstructed` | D-30 8 seed（P-2 通過後才得作為正式結果；之前之輸出一律標「探索性」） |
| `ZT_DELAY_SOURCE=exact` | R-5 run（seed 4200）：作為 reconstructed 之對照 |
| 預設（cumulative） | 舊結果，不重跑、不覆寫 |

cell 歸屬**沿用主檔列之 cell**（最後一筆 PDU 所在 cell）。此歸屬之機制待 R-5 之 `_percell` 旁路輸出查明（§7）；第一階段**不改歸屬**，結論須附此限制。

## 4. 入口切換（已實作；預設逐位不變）

- `interval_source.py`：`parse_interval()`、`cell_delay_means()`；缺值（ΔN = 0）直接報錯（fail-closed）。
- `zt_kpm_xapp.TraceReplaySource._parse`、`run_E9_operating_regime.load_cell_delay`（planB_rt、E9_rt／E9b／E9c／E9d／E11／E13 經此）、`run_Si_reference_ablation.load_cell_delay`、`run_adversarial_msweep.load_cell_delay`。
- `datasets.results_dir()`：非預設來源時目錄加 `_delay_<mode>`（d30 → `data/results/d30_delay_reconstructed/`），不覆寫舊結果；回歸基準（`planB_rt_baselines.json`）在新目錄內重新建立，人工核對前一律為「未核對」。
- **未切換**（第一階段不用）：`run_E20_error_rates.py`、`run_E9d_real_load_alarms.py`（另有自己的讀法，須在用到前補）、`run_B4_used_resources.py`、`run_E23_reference.py`、`run_Si_experiments.py`。

## 5. 校準程序（凍結；與舊版相同，只換輸入）

| 程序 | 公式 | 使用者 |
|---|---|---|
| C-1 `TrustAnchor` | 訓練 seed 之所有 mmWave (UE, 窗) 延遲 → 1.4826·MAD＋1e-9；LOSO | `zt_kpm_xapp`（融合、xApp） |
| C-2 `global_scale`／`fold_scale` | 訓練 seed 之 **cell 層級**平均 → 1.4826·MAD＋1e-9；LOSO | E9 族、planB_rt |

τ_S = 4、MIN_PEER = 2、時間參照之參數、注入參數（AF、漂移速率、起點）**全部沿用舊值，不調**。不得在評估資料上挑選任何參數。

## 6. 兩種評估

| 評估 | 輸入 | 尺度 | 實作 |
|---|---|---|---|
| E-i 診斷 | 區間（reconstructed） | 舊尺度：以**累計**輸入依 C-1／C-2 算出（即舊版凍結值） | **待寫**：小型驅動程式，訓練集以 cumulative 載入算尺度、受測 seed 以 reconstructed 載入；只做 S_i 乾淨誤報與 E9 之階躍／漂移偵測率 |
| E-ii 方法 | 區間 | 同一程序於**區間**輸入重算（LOSO） | 既有腳本於 `ZT_DELAY_SOURCE=reconstructed` 下依 CLAUDE.md 之 D-30 執行順序重跑（只到 E9d） |

E-ii 執行順序：`cv_interval.py` → `zt_kpm_xapp.py --fusion bound --eval-mode all`（僅取 S_i 欄位與乾淨誤報；融合結果屬第二階段，不解讀）→ `run_Si_reference_ablation.py`（4.7.4）→ `run_E9_operating_regime.py` → `run_E9_rt.py` → `run_E9b_rt.py` → `run_E9c_rt.py` → `run_E9d_rt.py`。任一內建檢查失敗即停、回報，不調參數。

## 7. 同時進行之查核（不改結果）

- cell 1 歸屬之機制：已知 `m_e2RlcStatsVector` 內兩個計算器接收**相同**事件（D-30H、M0 之 `DlE2RlcStats.txt` 與 `DlE2RlcStatsLte.txt` 逐位相同），cell 欄被每筆 Tx（eNB 端）與 Rx（UE 端）覆寫。假設：UE 端 Rx 之 trace 以 LTE cellId 綁定。以 R-5 之 `DlE2RlcStats_percell.txt`（依事件自身 cellId 累計之 Tx／Rx）檢驗。
- 若假設成立：S_i 之 cell 層級平均混入「列被歸到 cell 1 而被排除」之 UE（約 42 %），peer 母體與尺度都受影響——這是第二階段每 cell 統計要修的；第一階段結論須註明。

## 8. 產出與判讀

- 輸出全在 `data/results/d30_delay_reconstructed/`（E-ii）與 `.../d30_delay_reconstructed/E_i/`（E-i）。
- 報告 Q-A／Q-B／Q-C 之數字並列舊值；**不預設方向**：正面與負面結果皆須照實報告。
- 正文（v12）等第一階段完成後一併改寫。

## 9. 待使用者決定（附建議）

| # | 問題 | 建議 |
|---|---|---|
| Q-1 | s′ 只能取自單一 R-5 run（無 LOSO） | 接受為 Q2 之工程準則尺度；並另報 8 seed 反推值之 C-1 尺度作對照，兩者差 > 10 % 時停下來問 |
| Q-2 | E-i 之「舊尺度」指 C-1／C-2 以累計輸入之 LOSO 值 | 採用；不另造尺度 |
| Q-3 | E-ii 是否含 E13（τ_S 敏感度）與 4.10 m-sweep | 不含；第一階段只到 E9d。E13／m-sweep 屬第二階段（依賴 peer 歸屬） |
