# CLAUDE.md — 碩論：O-RAN NPN 邊緣節點之零信任 KPM 驗證

> 本檔由 claude.ai 上的長對話整理而來。詳細推導與可貼正文在 `docs/thesis/`，需要時再開啟，不要一次全部讀入。

## 專案一句話

被攻陷但身分合法的 O-DU 在 E2SM-KPM 組裝點竄改量測。本研究以三類外部佐證（C_i 基數守恆、S_i 跨節點同時態共識、H_i 成員轉移）驗證 KPM 數值，經階層式規則融合為逐 (node, window) 信任註記。C-ZT 為**四個 xApp**：Detection、Trust Assessment、Policy Enforcement（P1–P3）與 Available-resource evaluation。**P_i（吞吐量—資源，路線 B）已於 2026-10-13 由使用者決定自論文移除**，正文不得再出現；`run_Pi_experiments.py` 僅留存於 repo。

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
  - **`data/ues30_seeds/` = D-30（2026-10-06 定案之主資料，收集中）**：30 UE（`--totalUes=30`）＋ E2 NR 報表（`--e2nrEnabled=true`，cell 2–8 之 `du-cell-*.txt` 含原生 `RRU.PrbUsedDl`）× **8 seed（4200–4207）** × 301 s（分析取 0–299 窗）。**收齊並通過檢查後，第四章全部實驗（含 C_i、P_i、RQ3 之 PRB）統一改用 D-30**，取代 D-C 與 D-SH；舊資料保留唯讀，僅供附錄對照
  - `data/ues28_seeds/` = 28 UE 校準紀錄（已被 D-30 取代，僅保留校準證據）

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
| N_known | 7 → **30**（D-30 啟用後） | 由 `datasets.py` 依 `ZT_DATASET` 決定；ns-3 以 `--totalUes` 指定（`scenario-three.cc` 已 patch，預設行為不變） |
| 觀測窗 | 1 s | indicationPeriodicity = 1.0 |
| τ_S | 4 | S_i 門檻；尺度 s = 1.4826·MAD_global，凍結 |
| τ_H^warn／τ_H^reject | 2／3 | H_i-D1 證據強度（非信任狀態） |
| L_C | 2 | C_i 持續窗 |
| MIN_PEER | 2 | S_i 最少同窗 peer 數 |
| LTE 錨點 | CellId 1 | C_i 聯集必含 |

## 信任狀態與融合（權威定義在第四章 4.4.0）

四狀態：trusted ／ low-trust ／ abstain ／ rejected。嚴重度 trusted ≺ abstain ≺ low-trust ≺ rejected。**rejected 指不採信該筆 KPM，不代表節點是攻擊者。** abstain 永不等於可信（fail-closed）。不繼承：每窗重新判定。

規則依序評估：L1 硬否決（`R1_CI_VETO`、`R1_CI_PENDING`、`R1_D2_VETO`、`R1_STAGE1`）→ L2 統計證據（`R2_SI_D1_BOUND`、`R2_SI_D1_UNBOUND`、`R2_SI_ALONE`、`R2_D1_STRONG`、`R2_D1_WEAK`）→ L3 `R3_ABSTAIN` → L0 `R0_CLEAN`。

**已知結構缺口（已處理）**：window 政策下 `R2_SI_D1_BOUND` 無合法觸發路徑（D1 證據 UE 必在錨點）；定案之 uebound 以「UE 消失前之 serving mmWave cell」綁定，使其可觸發，代價為乾淨資料 6 筆誤拒（4.9.6.5）。

## 已確立之結果（D-30，2026-10-13；引用時以 `data/results/d30/` 之腳本輸出為準）

> 前版 7 UE 資料（D-SH／D-C）之數字已不再作為主結果，僅見 thesis 附錄 A 與各節之「揭露」。

- 資料：8 seed × 300 窗，全部通過 `prepare_d30.py` 與 PRB 交叉驗證（最大差 0.149）；全部 15,534 筆 (節點, 窗) 皆具 full consensus，abstain = 0
- C_i：2,400 窗 0 反例、乾淨 rejected 0；灌水／虛減全數偵測；守恆式替換 0／1,200（盲點）；D=1 脈衝於 L_C=2 下 1,200／1,200 不升級；同窗雙掛 0／72,000
- S_i（實際秒、共同集合，56 樣本）：乾淨誤報 空間 0.046／時間 0.029；漂移 0.5–2 %/秒 空間 0.65–0.91 vs 時間 0.03–0.04；共同集合 94.7%；$m^*_{S,50}=4$（m=3 繞過 16.8%）
- E9：AF≥1.3 時間參照 onset 0.93–0.96、全程 0.06–0.07；空間 0.61–1.00。E9b 監督式乾淨誤報 0.144（校準目標 0.0515）；E9c 共模 ×1.1 監督式 0.53 vs 空間 0.03；**E9d 於 D-30 未觀察到誤報集中於高負載背景**（前版之 1.8 倍未重現）
- xApp（uebound，定案）：trusted 50.3%／low-trust 48.7%／abstain 0%／rejected 1.0%（159／15,534，全為 `R2_SI_D1_BOUND`；L1 誤觸 0）。window 對照：trusted 1.2%。P99 1.16–1.42 ms（閒置機器三次量測）
- **D1 規模效應（主要限制）**：逐 UE 誤報 0.102（與 7 UE 之 0.116 相當），但 48.3% 節點註記綁有 D1 證據；159 筆誤拒未高於 S_i 誤報 × D1 證據在獨立假設下之預期（197）；僅探索性檢查，不得寫成「已證明獨立」。E14（事後新增，規格 `E14_D1_sensitivity_spec.md`）：τ_H 6／7 時 trusted 71.2%、延遲 2.2→6.4 窗，誤拒仍 0.64–0.71%。**主結果維持凍結值，不得依 E14 改門檻**
- RQ3（uebound）：不驗證誘導率 93.8–99.2%；C_strict：×0.6 → 2.2%、漂移 → 4.1–8.3%、×0.8 → 46.2%（regret 6.1%→3.7%，**前版「×0.8 時 regret 反升」未重現**）；乾淨 ρ_cap 49.5%、ρ_PRB 50.6%；`C_restrict_annot` ≡ `C_notrej`（abstain=0）
- E12（候選、未採用）：L_S=2 使 C_notrej 誘導率降至 8.6–17.2%，新增乾淨誤拒 81 筆（0.52%）
- 可用資源評估 xApp（`resource_eval_xapp.py`，乾淨全序列）：strict 准入輸入可用率 50.3%、ρ_PRB 51.5%、V_PRB 48.5%、無准入輸入之窗 11／2,400；restrict_annotated 99.0%／99.5%／0.5%
- 補充實驗（規格 `E15_E18_supplementary_spec.md` v1，皆不改主結果）：E15 分群門檻 0.50／0.55／0.60 下整體 FPR 皆 0.102、edge>resident 8／8；E16 D1 於 ≥1.25× 正常上界全數偵測、1.0× 為 0.47；E17 校準期中毒 k=4／5（ε 0.61–0.77）漸進竄改使 1 %/秒偵測降至 0.00–0.03，固定偏移呈崩潰後非單調；E18 攻擊情境之 ρ_PRB 由可用資源評估 xApp 逐窗產出並重現 RQ3；M1 四個 xApp 合計 P99 1.10–1.14 ms
- 回歸基準：rt 系列 6 個已於 2026-10-13 `--set-baseline`（`data/results/d30/`）

## 主要腳本

| 腳本 | 用途 |
|---|---|
| `zt_kpm_xapp.py` | 驗證 xApp、規則稽核、runtime（`--fusion bound --eval-mode all`） |
| `datasets.py` | **資料集登錄**：`ZT_DATASET=dsh｜dc｜d28｜d30`（預設 dsh＝修訂前行為，2026-10-06 回歸逐位重現）。決定資料路徑、N_known、aux 路徑、輸出目錄（d28／d30 → `data/results/d28/`、`data/results/d30/`，不覆寫既有結果）。D-SH 專屬期望值（742／2335／83／0、1803／575／766／6、凍結 FPR、4.7.7 十等分表）僅於 dsh 檢查；非 dsh 時明示略過，其餘檢查照常 |
| `prepare_d30.py` | D-30 分析用主檔：自原始檔截取 0–299 窗至 `data/ues30_seeds/analysis/`（d30 之 DATA_DIR），內建缺窗、前綴、N_total、aux 一致檢查；每個 seed 收集完成後執行 |
| `prb_reader.py` | 原生 PRB 讀取（`du-cell-*.txt[.gz]`，Σ_UE `RRU.PrbUsedDl.UEID`）＋ RxPacketTrace 交叉驗證；`PRB_CONST`=139、`N_RB_CFG1`=28 |
| `make_fig_Ci_unified.py` | Fig 4-1～4-4 統一版（讀 `Ci_unified_<tag>.json`；檔名加 `_<tag>`） |
| `run_Ci_unified.py` | C_i 之 E0–E8 統一版（規格 `docs/thesis/Ci_unified_spec.md`）：判定一律經 `verify_ci`／`fuse`、載入經 `TraceReplaySource`、`--ues` 檢查 N_known；`--mode legacy` 須重現 D-C 舊輸出。舊 `run_Ci_experiments.py`（5 % 容忍帶）不再使用 |
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

**2026-10-13：D-30 收齊、全流程跑完、正文第四章已全部換成 D-30。** 以 `scripts/run_d30_pipeline.sh` 重跑（`setsid nohup`；任一檢查失敗即停）。融合維持 C_i／S_i／H_i 三類（依簡報 v0.6 之流程圖）；P_i 已自論文移除；C-ZT 稱為四個 xApp（簡報第 27 頁標題仍寫 Three-xApp，待使用者改）。
- **架構（簡報 v0.6 第 27 頁，2026-10-13 與老師確認）**：P1 Detection → P2 Trust Assessment → P3 Policy Enforcement；P3 將 policy-admitted KPM 寫入 DB；RC xApp 與 **Available-resource evaluation xApp** 自 DB 讀取（後者經 Resource Termination）。可用資源評估**是一個 xApp、與 P1–P3 同時運作、逐窗執行，不是離線統計**（`resource_eval_xapp.py`；`run_xapp(on_published=…)` 回呼）。原型中 DB／Resource Termination 為行程內抽象，正文須如實寫。使用者說的「P1／P2／P3」是程序，**不是 P_i**；勿混淆。
- 待辦：35 張圖上傳 HackMD 並填連結（`data/results/d30_figs_20261013.tar.gz`）；簡報（`~/Downloads/Cindy_Thesis_v0.6.pptx`，前 40 頁已與老師確認）之結果頁換 D-30 數字；FNWF 2024／Hung／Hashem Eiza／ns-O-RAN 之 PDF 待使用者補；push 由使用者執行。
- 論文題目定案：Zero-Trust Verification and Admission of KPM Reports in Non-Public O-RAN: Countering Falsification by Authenticated Nodes with Field-Referenced Consistency Evidence（簡報 v0.6 第 1 頁仍為舊題目）。
- 以下各小節為歷史紀錄。

**資料集統一（2026-10-06 定案：D-30）**：
- 動機：口試／審查曾質疑 C_i 與 S_i／H_i 使用不同資料集；比較之文獻以 10 之倍數 UE 為基準；reviewer 可能要求模擬器原生之 PRB。故改為單一資料集 D-30，所有殘差、融合、RQ3（含 PRB 取捨）皆在同一組資料上評估。
- 收集：`scripts/collect_ues30.sh`，兩個實例平行（A：4200/4202/4204/4206；B：4201/4203/4205/4207），log `data/ues30_seeds/collect_A.log`、`collect_B.log`。2026-10-06 14:10 UTC 開始。**一律以 `setsid nohup` 啟動**（Claude 工作階段結束會殺掉其子行程）。每個 seed 於模擬約 30 s 時檢查記憶體斜率；是否加開第 3 個實例須問使用者。
- 校準：`data/ues30_seeds/calibration_20261006/README.md`（確定性、`--totalUes` 等價性、E2 NR 副作用、PRB 交叉驗證）。
- **E2 NR 報表之副作用**：最後一窗遺失（故 simTime = 301）；PDCP 統計每次報表後歸零（管線不用 PDCP）；RLC／PHY 不受影響。
- **PRB**：原生 `RRU.PrbUsedDl` = 排程符號數 ÷（slot 數 × 14）× 139；139 為原始碼寫死（configuration 1 實際為 28，見下）；cell 層級欄位因 uint32 逐 UE 截斷而偏低，**以 UE 層級 `RRU.PrbUsedDl.UEID` 加總為準**；du-cell 之 timestamp 為實際時間，報表依序對應模擬第 k 秒。
- **configuration 1 實際 RB 數 = 28**（numerology 2，RB 寬 720 kHz，ceil(20 MHz ÷ 720 kHz)，依 ns-3 原始碼）；139 = ceil(100 MHz ÷ 720 kHz)（configuration 2 之載波）。
- **待辦（資料到齊後）**：每個 seed 完成後跑 `prepare_d30.py`（0–299 窗）與 `prb_reader.py <aux>`；RQ3 改用原生 PRB 之規格 `docs/thesis/RQ3_PRB_spec.md`（v1 定案：ρ_PRB 主、ρ_cap 輔、僅 DL、不新增 PRB 準則決策、占用率＋28 RB 尺度、B4 移附錄）；28→30 之規格文件與正文更新。
- 代價須於正文誠實說明：C_i 之 seed 數由 10 降為 8（窗數由 600 增為 2,400）。
- **D-30 執行順序**（rt 版之檢查依賴同資料集之舊版輸出，故舊版須先跑）：`export ZT_DATASET=d30` → `zt_kpm_xapp.py --fusion bound --eval-mode all` → `run_E9_operating_regime.py` → `run_E9_rt.py` → `run_E9b_rt.py`（校準目標改取同資料集 E9 空間乾淨 FPR，定義不變）→ `run_E9c_rt.py`／`run_E9d_rt.py` → `run_E13_tauS_sensitivity.py` → `run_E13_rt.py` → `run_slow_poisoning_suite.py` → `run_slow_poisoning_rt.py` → `run_E10_D1_policy_ablation.py` → `run_RQ3_decision_replay.py` → E11／E11b／E12／B4 → `run_Ci_unified.py` → 圖。rt 系列之回歸基準於 d30 為「未核對」，須人工核對後 `--set-baseline`。

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
- 標準引用只用 Citation Map v2 已核實之條號（TS 33.501 V20.2.0、TR 33.809 V18.1.0、SRCS v15、xApp-TR v07、ZTA-TR v06、E2GAP V4.1.0、E2SM-KPM v08、NIST SP 800-207）。**不引** 舊版 Security-Requirements-Specification、未查證之 T-AIML 威脅編號。MARRS／APATE 僅作為 Rogue Cell（Aizikovich et al., arXiv:2505.01816v1，已核對原文）之方法名稱提及，不當成通用框架引用。
- Alimohammadi 引 FNWF 2024（攻擊 + LSTM）與 arXiv:2512.01596（2026 多層框架），**不寫 2025**。
- 正文不寫 P_i（已移除）。
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
