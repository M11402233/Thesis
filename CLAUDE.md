# CLAUDE.md — 碩論：O-RAN NPN 邊緣節點之零信任 KPM 驗證

> 本檔由 claude.ai 上的長對話整理而來。詳細推導與可貼正文在 `docs/thesis/`，需要時再開啟，不要一次全部讀入。

## 專案一句話

被攻陷但身分合法的 O-DU 在 E2SM-KPM 組裝點竄改量測。本研究以外部佐證（C_i 基數守恆、S_i 跨節點同時態共識、H_i 成員轉移）與內部一致性（P_i 吞吐量—資源，路線 B 進行中）驗證 KPM 數值，經階層式規則融合為逐 (node, window) 信任註記。

## 路徑

- Repo：`~/oran-zt-kpm-verification`
- ns-3：`~/ns-3-mmwave-oran`（`scratch/scenario-three.cc`）
- 驗證腳本：`xapps/verification/residuals/`
- 資料：
  - `data/batchFinal_seeds/seed4200–4209.txt` = **D-C**（10 seed × 60 s，C_i 用）
  - `data/batchFinal_seeds_VERIFY/_logs_*/seed42??_aux/` = D-C 之完整 ns-3 輸出（含 `RxPacketTrace.txt`）
  - `data/si_lstm_seeds/ues1_t300_seed4200–4203.txt` = **D-SH**（4 seed × 300 s，S_i／H_i／xApp／E9／E10／RQ3 用）
  - `data/si_lstm_aux/ues1_t300_seed42??_aux/` = D-SH 重跑之 aux（`RxPacketTrace.txt.gz`、`DlMacStats.txt.gz` 為壓縮檔；尚未產出，見下）
  - `data/si_lstm_seeds_aux/` = 舊 aux 腳本之輸出目錄，**已棄用**（空目錄）
  - `data/results/` = 所有實驗輸出

## ⚠️ 硬性規則（違反會毀掉論文資料）

1. **絕不寫入或覆蓋** `data/si_lstm_seeds/` 與 `data/batchFinal_seeds/`——第四章所有數字的依據。
2. **絕不執行** `scripts/collect_Si_LSTM_data.sh` 或 `scripts/collect_Si_LSTM_ues1_final.sh`——兩者都寫入 `data/si_lstm_seeds/`。要重跑一律用 `scripts/collect_DSH_aux.sh`（寫入 `si_lstm_aux/`，`si_lstm_seeds/` 只讀用於 cmp）。`scripts/collect_Si_LSTM_ues1_aux.sh` 已棄用。
3. **可能有長時間 ns-3 模擬在背景跑**（約 15 小時）。動手前先 `pgrep -af "scenario-three|collect_DSH|collect_Si"`（注意 pgrep 會命中自身 shell，只看 ns3／bash collect 行程）；**不得終止**這些行程。log 在 `/tmp/collectAux.log`。
4. **`zt_kpm_xapp.py` 必須是新版**（含 `RULE` 表與 `R2_SI_D1_UNBOUND`）。repo 舊版不相容，E10／RQ3 會拒絕執行。
5. **每支實驗腳本都有內建一致性檢查**（E9 須重現 4.7.4；E10 之 P0 須重現 742／2335／83／0）。檢查失敗時**停下來回報**，不要調參數讓它通過。
6. **論文中的數字一律來自腳本輸出**，不得估算或補寫。不確定時標【待填】。
7. 所有實驗皆為確定性；同一 seed 重跑應逐位相同。

## 定案參數

| 參數 | 值 | 備註 |
|---|---|---|
| ns-3 configuration | 1 | 3.5 GHz／20 MHz／isd 1000 m（「mmWave」為 MC 架構命名慣例） |
| N_known | 7 | ues=1 × 7 cell |
| 觀測窗 | 1 s | indicationPeriodicity = 1.0 |
| τ_S | 4 | S_i 門檻；尺度 s = 1.4826·MAD_global，凍結 |
| τ_H^warn／τ_H^reject | 2／3 | H_i-D1 證據強度（非信任狀態） |
| L_C | 2 | C_i 持續窗 |
| MIN_PEER | 2 | S_i 最少同窗 peer 數 |
| τ_P | 4 | P_i-C（路線 B） |
| LTE 錨點 | CellId 1 | C_i 聯集必含 |

## 信任狀態與融合（權威定義在第四章 4.4.0）

四狀態：trusted ／ low-trust ／ abstain ／ rejected。嚴重度 trusted ≺ abstain ≺ low-trust ≺ rejected。**rejected 指不採信該筆 KPM，不代表節點是攻擊者。** abstain 永不等於可信（fail-closed）。不繼承：每窗重新判定。

規則依序評估：L1 硬否決（`R1_CI_VETO`、`R1_CI_PENDING`、`R1_D2_VETO`、`R1_STAGE1`）→ L2 統計證據（`R2_SI_D1_BOUND`、`R2_SI_D1_UNBOUND`、`R2_SI_ALONE`、`R2_D1_STRONG`、`R2_D1_WEAK`）→ L3 `R3_ABSTAIN` → L0 `R0_CLEAN`。路線 B 將新增 `R1_PI_BOUND`、`R2_SI_PI_BOUND`、`R2_PI_ALONE`。

**已知結構缺口（已處理）**：window 政策下 `R2_SI_D1_BOUND` 無合法觸發路徑（D1 證據 UE 必在錨點）；定案之 uebound 以「UE 消失前之 serving mmWave cell」綁定，使其可觸發，代價為乾淨資料 6 筆誤拒（4.9.6.5）。

## 已確立之結果（引用時以腳本輸出為準）

- C_i：600 窗 0 反例；配平容錯空間 0；D=1 脈衝於 L_C=2 下 100% 不升級；同窗雙掛率 0%（12,600 樣本）
- S_i：受控消融 0.5–2%/窗 時空間 0.26–0.74 vs 時間 0.01（**「窗」為受評估之 full-consensus 窗，非實際秒；以實際秒計之結果不同，見 2026-10-06 查證**）；full-consensus 覆蓋 54.8%；$m^*_{S,50}=2$、$m^*_{S,100}=3$
- E9：階躍 AF≥1.3 時時間參照 onset 命中 0.88–1.00 但全程偵測 0.08–0.11（被滑動視窗吸收）；空間 0.62–0.96
- E10：UE 綁定（uebound，已定案）使 trusted 23.6% → 57.2%（分母 3,150 有效節點註記），偵測率與延遲不變；注入實驗中 76.9% 事件之告警窗，其（正確）歸屬節點當窗無有效節點註記（非「無節點可歸屬」）
- xApp（bound/all/uebound，定案）：trusted 57.2%／low-trust 18.3%／abstain 24.3%／rejected 0.19%（6/3,150，全為 `R2_SI_D1_BOUND`；L1 硬否決誤觸 0）。window 對照：23.6／73.8／2.6／0。P99 0.837 ms 為舊量測，待 aux 完成後於閒置機器重測
- **誤報口徑**：與他文 FPR 對應者僅「乾淨誤拒率」0.19%，且為對應量非等價量（單位 (節點,窗) vs (UE,record)）；low-trust／abstain 不是誤報。RQ3 之 ρ（如 C_restrict_annot 73.9%）為准入比例，勿與 low-trust 比例混用
- RQ3：不驗證時延遲壓低攻擊之誘導率 94.5–98.1%；×0.6 階躍下 C_strict 誘導率降至 2.8%（uebound 定案；window 為 1.1%）；×0.8 時過濾反而使 regret 變差；`C_notrej` 無保護效果
- P_i 探測（D-C 10 seed）：成員穩定窗覆蓋 73.0%；穩健殘差逐 seed 中位數 0.227；4σ 乾淨誤報 3.2%；天真灌水約需 ~1.9× 方可偵測

## 主要腳本

| 腳本 | 用途 |
|---|---|
| `zt_kpm_xapp.py` | 驗證 xApp、規則稽核、runtime（`--fusion bound --eval-mode all`） |
| `run_Si_reference_ablation.py` | 4.7.4 參照機制消融 |
| `run_E9_operating_regime.py` | 4.7.5 階躍 vs 漂移操作區對照 |
| `run_E10_D1_policy_ablation.py` | D1 證據綁定／持續性政策消融 |
| `run_RQ3_decision_replay.py` | RQ3 決策重放（依賴上兩者） |
| `run_Pi_experiments.py` | 路線 B：P_i 獨立評估（需 `*_aux` 目錄） |
| `probe_prb_feasibility_v4.py` | P_i 可行性探測 |
| `run_adversarial_msweep.py` | 4.10 抗串謀 m-sweep |
| `run_fusion_replay.py` | 4.11 規則回放 |
| `make_fig_Hi_D1_grading.py` | D1 證據強度分級圖 |

## 目前狀態與待辦

**D-SH aux 重跑狀態（2026-10-05）**：
- 2026-10-04 以 `collect_Si_LSTM_ues1_aux.sh` 啟動之重跑**實際未執行**：4 seed 皆 0 秒 exit=1（ns-3 編譯失敗，非時間預算問題），無任何輸出。
- 根因：2026-07-25 以 flexric `e2sim-kpmv3` 之 deb 取代系統 e2sim-dev（KPM v3 ASN.1，無 `choice` 成員），ns-3 `oran-interface` 編譯失敗。D-SH（07-14）建置時所用為 `~/oran-e2sim/e2sim/build/e2sim-dev_1.0.0_amd64.deb`（dpkg.log：06-10 09:13 安裝，至 07-25 被移除）。
- 已備份 kpmv3 版於 `~/e2sim_backup_kpmv3_20261005/`（含兩個 deb，可 `sudo dpkg -i` 還原給 flexric/OAI 用）。
- ns-3 原始碼自 06-29 起未變（scenario-three.cc、唯一本地修改 sta-wifi-mac.h 皆早於 D-SH）。
- 下一步：還原 oran-e2sim 之 e2sim-dev（需 sudo）→ `./ns3 build` 確認通過 → 以 `collect_DSH_aux.sh` 重跑（log `/tmp/collectAux.log`）。
- 腳本每完成一 seed 即自動與 `si_lstm_seeds/` 逐位 cmp。手動複查：
```bash
for s in 4200 4201 4202 4203; do cmp data/si_lstm_seeds/ues1_t300_seed$s.txt data/si_lstm_aux/ues1_t300_seed${s}_aux/DlE2RlcStats.txt && echo "$s ✓" || echo "$s ✗"; done
```
- `run_Pi_experiments.py` 目前讀未壓縮之 `RxPacketTrace.txt`；用 D-SH aux 前須支援 `.gz` 或先解壓。
任何 ✗ 即停止，不得混用新舊資料。

**下一步（依序）**：
1. 路線 B 階段 1：`run_Pi_experiments.py` 於 D-C 獨立評估（檢查容量斷言誤觸≈0、乾淨誤報 3–5%、最小可偵測倍數 ~2×）
2. 路線 B 階段 3：P_i 整合進 `zt_kpm_xapp.py`（需 D-SH aux）
3. RQ3 以 PHY 資源重算（路線 A，順帶完成）
4. 第四章套用 `docs/thesis/chapter4_v6.md` 並依路線 B 重新編號（P_i 為 4.9，其後順延）

**已決定**：UE 綁定（uebound）為定案政策；L_H = 1；無節點窗為 n/a（分母 3,150）。

## 寫作慣例

- 論文正文：繁體中文。簡報：英文內容 + 中文逐字稿。
- 每項貢獻附「驗證層級」誠實標記；未評估者明寫未評估。
- 標準引用只用 Citation Map v2 已核實之條號（TS 33.501 V20.2.0、TR 33.809 V18.1.0、SRCS v15、xApp-TR v07、ZTA-TR v06、E2GAP V4.1.0、E2SM-KPM v08、NIST SP 800-207）。**不引** 舊版 Security-Requirements-Specification、「MARRS 框架」、未查證之 T-AIML 威脅編號。
- Alimohammadi 引 FNWF 2024（攻擊 + LSTM）與 arXiv:2512.01596（2026 多層框架），**不寫 2025**。
- P_i 屬「內部一致性」類，**不得**併入「證據來源皆在受測節點之外」之主張。
- 自我參照之盲點只能宣稱於「以自身近期觀測為參照者」，不外推至監督式模型。

## 參考文件（需要時再開，勿全部載入）

- `docs/thesis/MASTER_TODO.md` — 工作清單總表
- `docs/thesis/chapter4_v6.md` — 第四章完整改版
- `docs/thesis/section_4_2_6_preconditions.md` — 先驗條件 P1–P6
- `docs/thesis/RQ_contribution_alignment.md` — RQ 與貢獻一對一
- `docs/thesis/RQ3_results_and_text.md` — RQ3 結果與正文
- `docs/thesis/route_B_design.md` — P_i 設計與導入計畫
- `docs/thesis/E9_E10_run_guide.md` — E9／E10 執行與解讀
- `docs/thesis/eight_questions_answers.md` — 架構層級八問
- `docs/thesis/main_text_v5.md` — 第一～三、六章正文
- `docs/thesis/batchB_verification.md` — 章節編號、引用年份等查證
