# D-30P1 步 3–5（percell，cell 平均版）停止紀錄（2026-11-21；負面結果，保留）

> 依使用者 2026-11-22 決定作成紀錄。本版結果不刪、不覆寫；修正版見 `D30P1_si_uemed_spec.md`。

## 執行

- 接續腳本 `scripts/r9/d30p1_after_chain.sh`，程式鏡像 `~/zt_dev/p2`（repo commit 2611197，code_md5 f74f9a5aaed2），新機器。
- 步 1：與 D-30P 除 meta 外相同（2026-11-21 18:38:16 UTC）。
- 步 2：`d30p1_delay_percell` ALLDONE 19:46:35 UTC；`d30p1_delay_percell_zero` ALLDONE 20:54:47 UTC。
- 步 3–5（percell）：`4a_xapp`、`2x_E13`、`2x_E13_rt`、`3a_E10`、`5a_RQ3`、`4b_E11`、`4c_E11b`、`4d_E12`、`5b_B4` 皆 exit 0；**`4e_fusion` exit 2**，21:18:23 UTC STOPPED。其後 `3b_Hi` … `5e_E18` 未執行；percell_zero 之步 3–5 未執行。
- 紀錄位置（新機器）：`data/results/d30p1_delay_percell/_pipeline_logs_step345/{status.txt,4e_fusion.log}`、`data/results/phase2/D30P1_after_chain.log`。

## 失敗內容（`run_fusion_replay.py` 輸出）

- seed 4200、窗 10、受測節點 6。`delay_drift`（受測 cell 各 UE 延遲設為訓練 seed 之全域中位數 + 6·s）：S_i normal（z = 0.95），決策 trusted／R0_CLEAN／allow；預期 low-trust／R2_SI_ALONE／restrict → 不符。
- 其餘情境（baseline、A_inflate_+1、teleport、conserving_swap、LTE 錨點 out_of_scope）皆符合。
- 腳本依規則停止，不寫任何輸出。

## 步 2 之相關數字（`scripts/r9/delay_decomposition.py` 輸出）

| 指標 | D-30P 舊式 (A) | D-30P1 舊式 (A′) | D-30P 排除零 (B) | D-30P1 有效樣本 (C) |
|---|---|---|---|---|
| spatial 乾淨誤報 | 0.0182 | 0.1911 | 0.1936 | 0.4063 |
| temporal 乾淨誤報 | 0.0213 | 0.1534 | 0.1941 | 0.3635 |
| 延遲 CV 中位數 | 0.3044 | 1.2703 | 0.1876 | 1.4858 |
| E9b 校準後乾淨誤報 | 0.3298 | 0.5048 | 0.2670 | 0.7186 |

- 分解腳本之檢查 K-A（A′ 須逐位等於 A）未通過。原因是 K-A 之前提錯誤：r10 模式 1 依設計會改延遲欄（Q-2／Q-2d 允許），A 與 A′ 本就不同。**未修改 K-A 使其通過；正文須揭露此事前檢查之錯誤。**

## 成因假說（待驗證；唯讀分析摘要；詳見 `D30P1_si_uemed_spec.md` §1、§4）

- 觀察：大延遲樣本與 mmWave 鏈路中斷同時出現。假說（未驗證）：RLC AM 保留之舊 PDU 於恢復後送達，與 ns-3 之 maxRetx 處理有關。
- 中斷普遍：25 % 之連結-窗 SINR < −8 dB，91 % 之連結至少發生一次。
- cell 平均使單一中斷 UE 支配 cell 值；fusion 回放之 +6·s 位移（約 76 ms）落在 peer cell 平均之一般範圍內。
