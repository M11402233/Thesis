# 規格：Stage 3（提高變異）新 ns-O-RAN 資料收集

> 狀態：v1 草案（2026-11-07）。依據：P6 = A（重跑 ns-O-RAN）、每變體 8 seed（使用者 2026-11-07 決定）；變異維度由 Claude 建議，使用者授權（「你給我建議」）。
> 本規格只規定**資料收集**；Stage 3 之實驗（賽局、指標）另於 `E19_DRL_game_spec.md` 規定。

## 1. 目的

教授之第三階段：「改變使用者數量與 session 長度，讓正常行為範圍變大，看兩個模型的對抗如何改變」。D-30 為單一負載型態（30 UE、full buffer），正常行為範圍窄。本資料提供：

- **場域內**（within-run）非平穩：UE 有開有關之 session（流量 on/off）。
- **場域間**（across-run）負載差異：UE 數不同。

## 2. 變體

| 變體 | `--totalUes` | `--trafficModel` | 其餘 | 對應教授之說法 |
|---|---|---|---|---|
| **S3-TM3** | 30 | 3（0.25 full buffer、0.25 bursty 3 Mbps、0.25 bursty 0.75 Mbps、0.25 bursty 0.15 Mbps） | 同 D-30 | session 長度／流量非平穩 |
| **S3-U20** | 20 | 0（full buffer） | 同 D-30 | 使用者數量（較少） |
| **S3-U40** | 40 | 0 | 同 D-30 | 使用者數量（較多）；**僅在 probe 通過 §4 判準時收** |

其餘參數全部同 D-30：configuration 1、`--e2nrEnabled=true`、`--indicationPeriodicity=1.0`、`--heuristicType=-1`、速度 3–10 m/s、`--simTime=301`（分析取 0–299 窗）。

不納入（留待日後另訂規格）：較高移動速度；UE 進出場域（須 patch `scenario-three.cc`，並先完成 C_i 成員／唯一性斷言規格）。

## 3. Seed 與輸出

- seed 4200–4207（每變體 8 個，與 D-30 同編號；UE 數不同時亂數流不同，故**不是**配對樣本）。
- 輸出：`data/game_stage3/<variant>/<variant>_ues<N>_t300_seed<s>.txt`（DlE2RlcStats）與 `_aux/`（與 D-30 保留相同檔案）。
- 腳本：`scripts/collect_stage3.sh`（由 `collect_ues30.sh` 複製；僅改變體參數與輸出目錄；拒絕寫入既有資料目錄）。
- 一律以 `setsid nohup` 啟動。

## 4. Probe（先於正式收集）

每變體 seed 4200、`--simTime=6`，輸出 `data/game_stage3/_probe/`。量測並記錄：

1. 實際耗時／模擬秒（rate），推估 301 s 之耗時；
2. RSS 與其斜率，推估 301 s 之記憶體；
3. 每窗出現於 RLC 報表之 UE 數（**S3-TM3 之 bursty UE 於 off 期間可能不出現於報表 → C_i 之 N_total 守恆可能誤觸**；僅記錄，不修改 C_i）。

S3-U40 收集判準：推估記憶體 ≤ 12 GB／實例，且推估單 seed 耗時 ≤ 72 h。不符則不收，並於正文寫明。

## 5. 內建檢查（每個 seed 完成即跑；失敗即停，回報，不改參數）

- 0–299 窗不得缺窗；IMSI 集合 = {1..N}。
- 每窗 N_total：S3-U20／S3-U40 須恆等於 N（同 D-30）；S3-TM3 **只記錄分布**（依 probe 結果；若不恆等於 30，C_i 於 S3-TM3 之使用方式須另訂規格）。
- PRB 交叉驗證：`prb_reader.py <aux>`（同 D-30）。
- 確定性：任選一 seed 以 `--simTime=6` 重跑，DlE2RlcStats 前 5 窗須逐位相同。

## 6. 排程

- 平行度依 probe 之記憶體決定（31 GB 機器，保留 ≥ 4 GB）；預設 2 實例。
- 順序：S3-TM3 → S3-U20 → S3-U40（若收）。
- Probe 結果（2026-11-07，seed 4200，`--simTime=6`；與 C4 檢查同時執行，速度偏慢）：

  | 變體 | 6 s 耗時 | 推估 301 s | 最大 RSS | 每窗 N_total |
  |---|---|---|---|---|
  | S3-TM3 | 47 min | 約 39 h | 0.3 GB | 5 窗皆 = 30 |
  | S3-U20 | 34 min | 約 28 h | 0.9 GB | 5 窗皆 = 20 |
  | S3-U40 | 93 min | 約 78 h | 2.2 GB | 5 窗皆 = 40 |

  （RSS 於長跑後段會增加；D-30 單實例最高 5.5 GB。）
- **S3-U40：推估 78 h > 72 h，依 §4 判準不收**（probe 速度含 C4 之 CPU 競爭；正文須寫明此判準與結果）。
- S3-TM3：probe 之 5 窗 N_total 恆為 30；正式資料仍逐 seed 檢查，若出現不恆等之窗即依 §5 停下另訂規格。
- 2026-11-07 21:14 UTC 起，3 實例平行（使用者同意）：A＝TM3 4200/4203/4206、U20 4201/4204；B＝TM3 4201/4204/4207、U20 4202/4205；C＝TM3 4202/4205、U20 4200/4203/4206/4207。log `data/game_stage3/collect_{A,B,C}.log`。推估約 8 天收齊。

## 7. 揭露

- 新資料只用於 Stage 3 與其後之實驗；第四章既有 D-30 結果不改。
- 變體之選擇為 Claude 建議、使用者授權，非教授指定；正文須如實寫。
