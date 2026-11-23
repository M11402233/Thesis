# D-50PH：50 UE 小型換手試跑規格 v0（2026-11-23；結果出來前寫定）

## 1. 決定與動機

- 使用者 2026-11-23 決定：主資料由 30 UE 改為 **50 UE**，並選**方案 B**：停止 30 UE 之 D-30PH 收集，先做 50 UE 小型換手試跑，通過後收 50 UE 全長。30 UE 之 D-30PH 已停止並封存（`D30PH_collection_spec.md` §8）。
- 50 UE 之校準尚未做過（30 UE 之確定性、換手長尾縮小、記憶體、覆蓋率皆不能直接沿用）。本試跑回答：**50 UE 下**（i）模擬是否確定、輸出是否完整（每窗 50 個 IMSI）；（ii）允許換手是否仍使延遲長尾明顯縮小；（iii）記憶體與時間。

## 2. 設計

| 項目 | 值 |
|---|---|
| ns-3 | `~/ns-3-mmwave-oran-r11`（凍結 md5：同 `scripts/r9/d30ph_chain.sh` 閘門；GCC 13.4.0）；`ZT_R7_S2=1`、`ZT_R10_RETX_TAG=1`；不設 `ZT_R10_TRACE` |
| 共同命令列 | `--RngRun=<s> --simTime=31 --totalUes=50 --e2nrEnabled=true --configuration=1 --minSpeed=3 --maxSpeed=10 --indicationPeriodicity=1.0 --heuristicType=-1` |
| 臂 `ho` | 加 `--handoverMode=FixedTtt`，seed 4200–4203 |
| 臂 `na` | 不帶 `--handoverMode`（NoAuto，同 D-30P1 之命令列），seed 4200–4203 |
| 臂 `det` | `ho` 之 seed 4200 重複一次（確定性） |
| 規模 | 9 個模擬同時，各 31 s（分析窗 0–29） |
| 腳本 | 收集 `scripts/collect_d50ph_r11.sh`（由 `collect_d30ph_r11.sh` 改：N_KNOWN=50、`HO_MODE`、`RATE`）；啟動 `scripts/r9/run_d50_pilot.sh`；判讀 `scripts/r9/d50_pilot_report.py`；輸出 `data/pilot_d50/`（僅診斷，不併入正式資料） |
| 資源（估） | 時間 ≈ 4 h：30 UE 之 31 s 跑約 1.9 h（D-30P1 於模擬 20 s 耗 4,322 s）；100 UE 試跑 31 s 耗 11.2 h（`data/scale_probe_ues100`）；以此估耗時約隨 UE 數之 1.5 次方，(50/30)^1.5 ≈ 2.15 倍。記憶體：100 UE 之 31 s 為 RSS 1.4 GB，故 50 UE 應 < 1 GB／行程，9 個 < 10 GB／31 GB。**皆為估計，非量測** |
| 逾時 | `RATE=900` → 約 11.8 h（保險） |
| 防護 | 收集腳本之 `MemAvailable < 600 MB` 即停止該次模擬 |

## 3. 接收檢查（任一失敗 → 試跑無效，停止回報，不調參數）

| 編號 | 內容 | 判準 |
|---|---|---|
| K1–K5、N | 收集腳本內建：O-1／eRN／CU-CP 一致性等 5 項；**每窗 N_total = 50、IMSI 1–50、無缺窗** | 9 個模擬全過 |
| Q-0 | meta 記錄 `ZT_R7_S2=1`、`ZT_R10_RETX_TAG=1`，二進位／函式庫／原始碼 md5 與 r11 樹相同 | 9／9 |
| Q-4 | `_r11eff` 與 `_percell` 一致性 | 9／9 |
| P-3 | percell 加總 = exact（RLC） | 9／9 |
| **確定性** | `det` 與 `ho` seed 4200 之 aux 目錄**全部檔案逐位相同**（`check_d30ph_phase0.py equal`；牆鐘欄除外；無 SINR 容忍，同二進位） | 0 不同 |
| 換手次數 | `ho` 臂各 seed `EnbHandoverStartStats` 行數 > 0（`na` 臂只報告） | 4／4 |
| 覆蓋率 | `ho` 臂有效 (UE, 窗) 占 50 × 30 之比例 ≥ 0.70 | 通過 |
| 跳窗 | 每個 (cell, UE, LCID) 之 `_r11eff` 逐窗無跳窗 | 0 |

**無外部參照**：50 UE 無已收之 D-30H 類資料，故 30 UE 之 Q-2H（對 D-30H 逐行比對）在此不適用；確定性與前述檢查為替代。此為已知限制：本資料與 D-30H／D-30P1 不能逐行比對，只能於結果層級對照。

## 4. 判讀（事前寫定）

- 指標：`scripts/r9/analyze_d30ph_tail.py`（`--nue 50 --nwin 30`）之 **W1**＝有效 (UE, 窗) 中區間平均延遲 > 1 s 之比例；W2（> 30 s 個數；31 s 內必為 0）、W3（最大值）、覆蓋率只報告。`ho` 與 `na` 同 4 個 seed、窗 0–29，合併。
- **判準**：W1(ho)／W1(na) ≤ 0.2 →「明顯縮小」；≥ 1.5 →「變大」；其餘 →「無明顯差異」（與 30 UE 小型驗證 §5 相同門檻）。若 W1(na) = 0 →「無法判定」。
- 限制：僅 31 s、4 seed；`ho` 與 `na` 為不同模擬（同 seed）；看不到 > 30 s 之延遲；此為 (UE, 窗) 層級，與逐封包比例不同。

## 5. 之後（依 `d50_pilot_report.py` 退出碼）

- **0（有效且「明顯縮小」）**：依使用者選擇 B（試跑通過後收 50 UE 全長），撰寫 D-50PH 全長收集規格（8 seed 4200–4207 × 301 s、`--handoverMode=FixedTtt`、`RATE=900`、同樣之 K1–K5／N／Q-0／Q-4／P-3／P-6／確定性檢查、記憶體防護；預估 44–57 h，由 20.5–26.7 h × 2.15 推得，未驗證），**寫定後啟動**。
- **2（有效但非「明顯縮小」）**或 **1（無效）**：**停止並回報**，由使用者決定（不自行收集）。

## 6. 腳本自查（2026-11-23，啟動前）

- 為本試跑修改既有腳本：`check_d30ph_phase0.py` 新增 `equal` 子命令與 SINR 容忍開關；`analyze_d30ph_tail.py` 新增 `--nue`（預設 30）與 D50PH 變體名。回歸：Q-2H 對照（正向：通過 55 檔；反向：失敗 26 檔）與修改前相同；`analyze_d30ph_tail.py` 對 D-30P1 自身 60,556／0.138863／290.768 s／比值 1.0，與修改前相同。`equal`：自比通過（85 檔）、不同長度失敗（82 檔）；G1 配對（追蹤開／關）只有追蹤檔不同（`R10_trace`、`R10_trace_calc`、`R11C_rrc`），符合預期。
- 判讀腳本乾跑：以 30 UE 小型驗證之既有資料（`r11c_ho`／`r11c_causal`，已看過）於 `/tmp/d50_dry` 以符號連結建構（只寫該目錄內之 `tail.json`／`decision.json`）。端到端可執行；W1 比值 0.01346、換手次數 517／386／469／483 與先前報告一致；預期之失敗全部出現（無 `meta.txt` → Q-0 失敗；30 UE 資料對 50 UE 分母 → 覆蓋率 0.599 < 0.70）。**判準未因乾跑調整。**

## 7. 執行紀錄
- 2026-11-23 09:52:54 UTC（台灣 17:52）：`scripts/r9/run_d50_pilot.sh` 啟動（`setsid nohup`，log `data/pilot_d50_run.log`、`data/pilot_d50/summary.txt`）。閘門通過；9 個模擬同時執行；已核對命令列：`ho` 臂含 `--handoverMode=FixedTtt`，`na` 臂不含，其餘相同（`--totalUes=50`），環境變數僅 `ZT_R7_S2=1`、`ZT_R10_RETX_TAG=1`。預估約 4 h（估計）→ 台灣時間約 22:00 前後；完成後自動執行 `d50_pilot_report.py`。
