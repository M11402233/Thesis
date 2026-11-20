# D-30P1：r10 模式 1 重收規格（v0，2026-11-20，事前登記；結果未出前定案）

## 1. 目的與決定
- 使用者 11-20 決定：重傳 PDU 之延遲採 **模式 1**（`ZT_R10_RETX_TAG=1`：沿用首次傳送時間戳，延遲含重傳等待）。
- S_i 之尺度公式與門檻 **不改**（凍結），用以評估「量測修正」本身之影響；重新校準另列規格。
- 主版本仍為「排除零延遲」（現在零延遲 ≈ 殘留無時間戳 PDU），含零為對照。

## 2. 資料
| 項目 | 值 |
|---|---|
| 名稱 | D-30P1（`ZT_DATASET=d30p1`） |
| ns-3 | `~/ns-3-mmwave-oran-r10`（= r9-g13 ＋ `scripts/r9/patch_r10.py`），`ZT_R7_S2=1`、`ZT_R10_RETX_TAG=1` |
| 命令列 | 與 D-30P 相同（30 UE、`--e2nrEnabled=true`、configuration 1、simTime 301、分析 0–299 窗） |
| seed | 4200–4207，8 個同時（新機器） |
| 輸出 | `data/ues30_p_r10_seeds/`（`D30P1_ues30_t300_seed<s>_aux/`）；分析主檔 `data/ues30_p_r10_seeds/analysis/` |
| 結果 | `data/results/d30p1_delay_<VARIANT>/`（不覆寫 `d30p_*`） |

## 3. 接收檢查（任一失敗即停，不調參數）
| 編號 | 內容 | 判準 |
|---|---|---|
| Q-0 | meta 記錄 `ZT_R7_S2=1`、`ZT_R10_RETX_TAG=1`、二進位與 `lte-rlc-am.cc` md5 | 與 r10 樹相同 |
| K1–K5 | 既有 `check_r9_outputs.py` | 全過 |
| N | 每窗 N_total = 30、IMSI 1–30、無缺窗 | 全過 |
| Q-2a | 與 D-30P（r9-g13）同 seed 之 aux：**允許清單外** 之檔案解壓後逐位相同（du-cell／cu-* 之牆鐘首欄移除，同 P-2） | 0 不同 |
| Q-2b | 允許清單內之檔案（`DlE2RlcStats{,Lte}{,_exact,_percell,_r9rx}.txt`、`DlRlcStats.txt`、`du-cell-*.txt`、`R7b_rlc_rx_tag_hist.txt`）：列數與鍵相同；只准延遲欄不同（percell／exact：delaySumNs；r9rx：nRxZeroDelay、nRxNoRlcTag；主檔與 DlRlcStats：delay、stdDev、min、max；du-cell：`DRB.UEThpDl.UEID`；R7b：總數相同） | 0 違規 |
| Q-2c | 分析主檔與 D-30 分析主檔：同列、只准延遲欄（第 11–14 欄）不同 | 0 違規 |
| Q-2d | delaySumNs（percell，累計）逐鍵 ≥ D-30P；增量只出現在 D-30P 該鍵有零延遲 PDU 者 | 0 違規 |
| P-3 | 既有：percell 加總 = exact（RLC） | 8／8 |
| P-5 | 既有：只報告 | — |
| P-6 | seed 4200 之 31 s 短跑與全長 run 之前綴相同（同 D-30P 程序） | 通過 |
| X1–X3 | `percell_source.check` | 8／8 |
| 報告 | 殘留零延遲比例（21 s 驗證為 0.14 %）、記憶體峰值 | 只報告 |

允許清單取自 21 s 驗證（`data/r10_validation/`，模式 1 vs 0 不同之 17 檔），**事前固定**；新出現之不同檔案一律視為失敗。

## 4. 已預見之失敗點與處置（重收前完成）
| # | 問題 | 處置 |
|---|---|---|
| F1 | 收集腳本未傳遞、未記錄 `ZT_R10_RETX_TAG` | 腳本要求 r10 時必設並寫入 meta |
| F2 | P-2（與 D-30 逐位相同）依設計必失敗 | 以 Q-2a–d 取代 |
| F3 | `aux_matches_main` 對 D-30 主檔必失敗 | D-30P1 之主檔用自身截斷版（`prepare_d30.py`），另以 Q-2c 對 D-30 |
| F4 | 多支程式寫死 `"d30p"` | 改為「第二階段資料集」集合 |
| F5 | 步 2 腳本寫死 `ZT_DATASET=d30p` 與第零階段目錄 | 參數化 |
| F6 | 新資料集無回歸基準 → E17 等停止 | 依 11-20 之程序 `SETBASE=1`，註記「建立，結果未經作者審閱」 |
| F7 | OUT_DIR 保護清單未含 D-30P 之目錄 | 加入 `ues30_p_r9*_seeds`、`ues30_p_r10_seeds`（後者僅限空目錄時寫入） |
| F8 | 與 100 UE 探測同機 | 9 行程 ≤ 14 核；記憶體峰值 8 × 1 GB ＋ 探測 < 31 GB；PSRO 不同時跑 |

## 5. 可能出現但不屬程式錯誤之結果（出現時照實回報，不調參數）
- 尺度 s 大幅變大（21 s in-sample：366 ms）：S_i 偵測力與誤報可能大幅改變。
- E9b 擬合檢查（balanced accuracy ≥ 0.80）可能未過。
- 主版本與含零對照幾乎相同（零值僅剩約 0.14 %）。
