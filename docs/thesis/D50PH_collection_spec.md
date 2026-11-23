# D-50PH：50 UE 含換手之全長收集規格 v0（2026-11-23；啟動前寫定）

## 1. 決定與依據
- 使用者 2026-11-23 決定主資料改為 50 UE（方案 B：試跑通過即收全長）。正文不引用任何 30 UE 資料，亦不寫改用 50 UE 之理由（使用者 11-23）。
- 試跑結果（`D50PH_pilot_spec.md`；`data/pilot_d50/decision.json`，**預先寫定之判準**）：**有效**（9/9 之 K1–K5／N／Q-0／Q-4／P-3 通過；確定性重複跑 85 檔逐位相同；換手次數 ho 臂 888／721／837／629，na 臂 0），長尾 **「明顯縮小」**：W1（區間平均延遲 > 1 s 之 (UE, 窗) 比例）ho = 0.0（5,978 個有效 (UE, 窗)，覆蓋率 0.996）對 na = 0.108（5,057，覆蓋率 0.843）；最大值 0.969 s 對 26.4 s。限制：31 s、4 seed、窗 0–29。
- 試跑耗時（量測）：ho 臂 5.2–5.6 h、na 臂 4.5–4.8 h（9 個同時，31 s）；峰值 RSS ho 803–810 MB。

## 2. 設計
| 項目 | 值 |
|---|---|
| ns-3／環境 | r11 凍結建置（md5 閘門同 `d50_pilot`）、`ZT_R7_S2=1`、`ZT_R10_RETX_TAG=1`、不設 `ZT_R10_TRACE` |
| 命令列 | `--RngRun=<s> --simTime=301 --totalUes=50 --e2nrEnabled=true --handoverMode=FixedTtt --configuration=1 --minSpeed=3 --maxSpeed=10 --indicationPeriodicity=1.0 --heuristicType=-1`（同試跑 ho 臂，僅 simTime 不同） |
| seed／規模 | 4200–4207，8 個同時；分析窗取 0–299 |
| 腳本 | `scripts/r9/d50ph_chain.sh`（呼叫 `scripts/collect_d50ph_r11.sh`，`RATE=1000`）；輸出 `data/ues50_ph_r11_seeds/`；驗收輸出 `data/results/phase2/D50PH_phase0/`（summary.txt、STOPPED／DONE） |
| 逾時／防護 | 每 seed 逾時 = 1000 × 301 × 1.5 + 600 s ≈ 125 h；MemAvailable < 600 MB 即停該次模擬 |

## 3. 驗收（任一失敗即停，不調參數）
逐 seed：收集腳本之 K1–K5 與 N（每窗 50 IMSI、無缺窗）、Q-0（meta、md5）、Q-4、P-3；**P-6**：試跑 ho 臂同 seed 之 31 s 短跑須為本全長之前綴（`p6_prefix.py`，容許結尾 0.1 s 效應；seed 4200–4203 有短跑可比，4204–4207 為 n/a）。**無外部逐行參照**（無 50 UE 之舊資料）；Q-2H 不適用。

## 4. 時間（估計，非量測）
- 下限：線性外推 301/31 × 5.4 h ≈ 52 h。上限：30 UE 之全長相對 31 s 短跑每模擬秒慢約 1.75 倍（D-30P1 約 384 s/s 對 31 s 跑之 220 s/s；估計），套用得約 92 h。**預估 52–92 h**（約 2–4 天）。**更正**：先前於試跑規格 §5 寫之 44–57 h 偏低（係以 4 h 試跑估之），以此為準。
- 資源：31 GB 記憶體，8 個 × 約 0.8 GB（31 s 時）；全長之記憶體斜率未知（r8＋S2 於 30 UE 為 832 MB 持平，50 UE 未驗證），收集腳本之防護與 `mem_trace.tsv` 記錄之。

## 5. 之後
收齊並通過後：分析用主檔（50 UE 版 `prepare`）與 `datasets.py` 之 50 UE 登錄、各檢查中硬編碼之 30（N_known 等）改為 50，另寫規格；第四章全部以 50 UE 重跑。**不得終止；加開實例須問使用者；分析腳本不得寫入 `data/ues50_ph_r11_seeds/`。**

## 6. 執行紀錄
