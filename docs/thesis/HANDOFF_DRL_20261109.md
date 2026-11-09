# 交接：DRL 賽局（E19）移至新機器（2026-11-09）

> 新機器上之 Claude 工作階段：**先讀本檔與 CLAUDE.md，再讀 `docs/thesis/E19_DRL_game_spec.md` §2a、§2b、§3a、§10b**。不要一次讀入正文全文。

## 1. 現況（2026-11-09）

| 項目 | 狀態 |
|---|---|
| 規格 E19 v2（PSRO） | 定案。R-a～R-f 依建議值（11-08）；**R-d 改為相對門檻**（11-09，使用者）：NashConv ≤ 0.05 × 第 1 輪 NashConv 即停、最多 6 輪；**R-f 事後修正**（11-09，使用者）：每個最佳回應至多 300,000 步、每 50,000 步以訓練 seed 驗證、保留最佳存檔 |
| 環境 | `xapps/verification/adversarial/`：`game_core.py`、`env_kpm_game.py`、`psro.py`、`lcurve.py`、`check_env.py`（G1–G3）、`check_speedup.py`（S1–S2） |
| 一致性檢查（舊機器） | G1 15,534 筆逐筆相同；G2a 434,952 筆；G2b RQ3 最大差 0；G2c E11 S_i 類 224 列；G3 決定性；S1 批次 = 逐節點；S2 T0Cache 等價；G4 誘導率 2.2363%／46.2092%／8.2922% 與乾淨誤拒 159／15,534 |
| 學習曲線（R-f，舊機器，僅供決定規則） | 偵測端 10 萬步即平穩；攻擊者 5 萬步達最高後退化。結果於 `data/results/d30/drl/lcurve/` |
| 舊機器上之 O-full t0 PSRO | 2026-11-09 起以 1 核心試跑；**移機後視為試跑，不引用**（兩機 CPU 指令集不同，結果不會逐位相同） |
| 簡報 | v1.7 第 42 頁仍寫 ε = 0.01（待使用者決定是否出 v1.8） |

## 2. 新機器之安裝與檢查（全部通過才可訓練）

1. 取得 repo（`git clone` 或 scp），路徑 `~/oran-zt-kpm-verification`（程式以 `~` 解析，不需改路徑）。
2. 自舊機器複製（唯讀資料，路徑相同）：
   - `data/ues30_seeds/analysis/`（D-30 分析檔，7.4 MB）
   - `data/results/d30_fusion_order/severity/`（G1、G2、G4 之比對基準，25 MB）
   - 選擇性：`data/results/d30/drl/lcurve/`（R-f 紀錄）
3. venv `~/venvs/drl`，版本須與舊機器相同：torch 2.5.1+cpu、gymnasium 1.1.1、stable-baselines3 2.6.0、sb3-contrib 2.6.0、numpy 2.2.6、scipy 1.15.3、nashpy 0.0.43。
4. 依序執行（`export ZT_DATASET=d30 ZT_FUSION_ORDER=severity`；於 `xapps/verification/adversarial/`）：
   - `python check_env.py`（G1–G3，約 10 分鐘）
   - `python check_speedup.py`（S1–S2）
   - `python psro.py --level O-full --train-seed 0 --workers 1 --g4-only`（G4；完成後將該目錄改名保存，正式執行重新開始）
   - 任一失敗即停，回報使用者，**不調參數**。
5. 記錄新機器之 CPU、核心數與 `pip freeze` 於 `data/results/d30/drl/machine.txt`。

## 3. 正式執行（6 組 PSRO）

- 組合：`--level {O-full, O-outcome}` × `--train-seed {0,1,2}`；一律以 `setsid nohup` 啟動，`PYTHONUNBUFFERED=1`、`nice`。
- 每組 `--workers` 依可用核心分配（例如 12 核 → 每組 2 個 worker，6 組同時）；可中斷續跑（已完成之模型自動跳過）。
- 終止行程時**不要用 `pkill -f <會同時匹配 Bash 指令本身之字串>`**（曾因此殺掉自己之 shell）；以 PID 終止。
- 之後之步驟（規格 §3a）：token 洩漏（最終輪，O-outcome+token）、凍結 vs 線上、Stage 3 評估——各自先寫規格細節再執行。

## 4. 仍在舊機器進行之事

- Stage 3 ns-3 模擬（S3-TM3、S3-U20；3 個實例，預計約 11/16 收齊）。每個 seed 完成後之檢查（`E19_stage3_data_spec.md` §5）在舊機器做，完成後再將 `data/game_stage3/` 複製到新機器供 Stage 3 評估。
