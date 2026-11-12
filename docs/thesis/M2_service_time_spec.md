# 規格 M2：Service time 量測——驗證層與學習決策分開量測再加總（v1，2026-11-12）

> 依據：導師會議 2026-11-10（`meeting_minutes_advisor_20261110.md`）D1、D2：延遲改以 **service time** 為口徑；驗證（P1–P3 與可用資源評估）與學習決策之推論**分開量測再加總**，不共用 CPU；不做「同一顆 CPU 切兩半」之共用量測。
> 使用者核可排程（2026-11-12：「可以」）。本規格**不改任何判定與主結果**；只量時間。

## 1. 定義

- **Service time（每窗）**：一個 1 秒之 KPM 聚合窗自「聚合完成、進入處理」至「處理完成、輸出離開」之 wall-clock 時間（`time.perf_counter_ns`）。不含檔案 I/O（trace 預載）、E2SM-KPM ASN.1 解碼、SCTP 傳輸（與 M1、4.9.5 同界定）。
- **V（驗證層）**：P1–P3（證據偵測、信任評估、政策執行）＋可用資源評估 xApp；即 M1 之「四個 xApp 合計」（`resource_eval_xapp.run_benchmark`）。
- **L（學習決策）**：E19 之學習型偵測端於該窗對全部待決節點（規則下限為 trusted／low-trust 者）之決策——觀測向量組成＋遮罩＋一次批次前向推論（`game_core.decide_pending`，與評估時之呼叫相同）。**不含**：規則下限之計算（屬 V）；`Episode.end()` 中之歷史更新（與評估用之統計累計混在同一函式，無法單獨計時；揭露）。
- **合計**：同一 (seed, 窗) 之 V + L，逐窗配對後求分位數（非 P99 之相加）；另報 P99(V) + P99(L) 作保守上界。

## 2. 量測條件

- 機器：舊機器（Xeon Silver 4110，`nproc` = 4），**閒置**：開始前檢查無 ns-3／收集腳本行程、1 分鐘負載 < 0.3，並記錄。
- V 與 L **分屬兩個行程、依序執行**（不同時），皆以 `taskset -c 2` 固定同一核心；torch `set_num_threads(1)`；量測期間停用 gc（同 M1）。
  - 揭露：前人做法為兩台機器分別量；本研究為同一閒置機器、分開行程、依序量測，兩者皆不共用 CPU 時間。
- 每個 seed：暖身 3 回合、量測 5 回合，取逐窗中位數（同 M1）。整組量測重複 **3 次**（run1–run3），報範圍。
- 資料：D-30 乾淨 8 seed × 0–299 窗；`ZT_DATASET=d30`、`ZT_FUSION_ORDER=severity`。
- 學習型偵測端：E19 六組（O-full／O-outcome × t0–t2）最終 σ_D 之**支撐內每個偵測端**（共 13 個 id），每個 seed 用其 LOSO fold 之模型（與 eval_final 相同）。模型取自 `data/results/d30/drl/psro_newmachine_20261111/psro/`（路徑由新機器之絕對路徑改寫為本機備份，內容逐位相同）。torch 2.5.1+cpu、stable-baselines3 2.6.0、sb3-contrib 2.6.0（與新機器 `eval_final.json` → meta 相同）。

## 3. 一致性檢查（任一失敗即停，不寫結果）

- **M2-1**：L 量測中每個偵測端 × seed 之乾淨判定計數（clean_n、clean_rej、clean_nontrust）須與 `eval_final/pairs.json` 之 `<det>|CLEAN|` → `per_seed` 逐一相同——確認計時之對象就是被評估之偵測端。
- **M2-2**：V 之註記判定經 `run_xapp` 產生，與第四章同一路徑；V 之 P1–P3 量測同時檢查（同 M1）不改輸出。
- **M2-3**：閒置條件（§2）不符即不開始。

## 4. 輸出

`data/results/d30_fusion_order/severity/M2/`：`M2_V_run{1,2,3}.json`、`M2_L_run{1,2,3}.json`、`M2_service_time.json`（彙整：V、各偵測端 L、配對合計之 mean／P95／P99／max；各 run 之 σ_D 支撐內最大 P99）、`env_run{n}.txt`（CPU、負載、行程檢查）。

## 5. 不做／揭露

- 不量 CPU 使用率（D1）；不做共用 CPU 量測（D2）。
- 單機離線量測，不模擬 RIC 併發負載；數值只涵蓋驗證層與學習決策之計算。
- σ_D 為混合策略：部署時每窗之偵測端依 σ_D 抽樣；本規格報支撐內各偵測端之分布與其最大 P99（保守），不另做抽樣模擬。
