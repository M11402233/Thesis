# D-30P（r9）第二階段步驟 0 驗收結果（2026-11-19）

規格：`docs/thesis/phase2_percell_spec_v0.md` §6。檢查程式：`scripts/r9/check_d30p_phase0.py`（573d0d1，於看到 D-30P 結果前定稿）。
自動鏈：`scripts/r9/phase0_d30p.sh`（新機器）。輸出：`data/results/phase2/D30P_phase0/`（自動）與 `manual/`（事後人工核對）。
D-30P 收集：8 seed 皆 K1–K5 通過、stderr 0 行（新機器 2026-11-19 04:25–06:06 UTC+8 完成）。

## 總表

| 檢查 | 自動判定 | 人工核對 | 結論 |
|---|---|---|---|
| P-2 舊格式檔與 D-30 逐位相同 | **FAIL 8/8** | 34/35 檔逐位相同；唯 `RxPacketTrace.txt` 不同 | **依規格未通過**；差異已定位為編譯器版本（見下），待使用者決定 |
| P-3 逐 cell 守恆（RLC） | PASS 8/8 | — | 通過：DlE2RlcStats 9,000／9,000、DlE2RlcStatsLte 9,030／9,030 筆，每 seed 0 不符 |
| P-3 PDCP（不計入通過，依 573d0d1 事前決定） | — | — | nTx／TxBytes 不符 8,970／9,000（NR）、9,000／9,030（LTE）；nRx／RxBytes／delay 不符 452–979 筆／seed |
| P-5 O-1／O-2 一致（僅報告） | — | — | 每 seed mmCell 變更 30 次、未對應 0；uemap 集合變更 0（NoAuto，無換手，30 次＝初始附著） |
| P-6 確定性（31 s 重跑 vs 全程，seed 4200） | **FAIL** | 76 檔中 54 檔為全程之嚴格前綴；22 檔首差皆在 sim t ≥ 30 s 或為結束時彙總 | **依規格（首差 ≥ 29.9 s 可容許）通過**；自動判定為檢查程式缺陷 |

## P-2：RxPacketTrace 之差異（`manual/RxPacketTrace_coldiff_<seed>.json`，`scripts/r9/rxpt_diff.py`）

行數 8 seed 皆相同。不同之行只在 SINR 欄（第 14 欄），另有 2 行 TBler 欄不同；**corrupt 欄（封包是否損毀）全部相同**，其餘 34 檔（含 DlE2RlcStats、DlMacStats、du-cell、cu-*-cell）逐位相同，故模擬軌跡未改變。

| seed | 差異行 | SINR 最大絕對差 | TBler 差異行（最大差） |
|---|---|---|---|
| 4200 | 114,703 | 1e-4 | 1（0.218） |
| 4201 | 53 | 1e-4 | 0 |
| 4202 | 6,224 | 1e-4 | 0 |
| 4203 | 1,258 | 1e-4 | 0 |
| 4204 | 8 | 1e-5 | 0 |
| 4205 | 461 | 1e-4 | 1（0.0065） |
| 4206 | 42 | 1e-4 | 0 |
| 4207 | 189 | 1e-4 | 0 |

SINR 差異均為第 6 位有效數字之捨入（例：seed 4202 第 28,096 行 −0.0584861 vs −0.058486）。

### 成因定位（seed 4202，simTime=2，比對前 59,000 行）

| 程式 | 機器 | 編譯器 | 與 D-30 相同？ |
|---|---|---|---|
| 原版（D-30 所用） | 舊（Xeon 4110） | GCC 13.4 | 基準 |
| r9 | 舊 | GCC 13.4 | ✓ 相同 |
| 原版 | 新（i7-14700） | g++-13（13.4） | ✓ 相同 |
| r9（D-30P 所用） | 新 | **GCC 11.4** | ✗ 第 28,096 行不同 |

（兩者皆 `-O3 -march=native`。）→ 差異來自**編譯器版本**（GCC 11 vs 13 之浮點運算序／內聯差異），非 r9 修改、非 CPU。注意：新機器之 `ns-3-mmwave-oran-r8d`（D-30H r8d 正式重收所用）同為 GCC 11.4 建置。

## P-6：人工前綴核對（`manual/P6_prefix_4200.json`，`scripts/r9/p6_prefix.py`）

自動檢查將「短 run 檔案結束」誤判為差異（t=None），且 bsState 剝除錯欄（第 2 欄才是 UNIX 時戳；bsState 不在 D-30 參照中，不影響 P-2）。檢查程式未修改；改以前綴核對（剝除 du/cu 第 1 欄、bsState 第 2 欄）：
- 54 檔為全程之嚴格前綴（含 DlE2RlcStats、_percell、_exact、DlMacStats、R9_ue_rrc、du-cell、cu-*-cell、bsState）。
- 22 檔之首差：30–31 s 窗（短 run 於結束時沖出之最後一窗：Dl/UlE2*Lte*、_r9lastset、_r9rx）；sim t ≥ 30.9 s（RxPacketTrace、MmWaveSinrTime、RlcAmBufferSize、X2Stats、DlPhyTransmissionTrace／EnbSchedAllocTraces frame 3091）；或結束時彙總（DlPdcpStats／DlRlcStats／UlRlcStats 之單行、R7b_rlc_rx_tag_hist）。無任何 sim t < 29.9 s 之差異。

## 待使用者決定

P-2 依規格未通過。選項：
- (a) 接受並揭露：所用欄位全同，差異僅 PHY 除錯 trace 之 SINR 印出位數。
- (b) 以 g++-13 另建 r9（新目錄，不覆寫現有建置）重收 D-30P，取得逐位相同（8 seed 平行約 6–8 h）。
決定前不進行第二階段步驟 1。
