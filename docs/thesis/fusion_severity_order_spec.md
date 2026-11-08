# 規格：融合規則改為「最嚴重符合規則決定」（severity-first）

> 狀態：**已採用（2026-11-08）**：C1–C4 全數通過，差異僅限預期組合（§7）。草案 2026-11-07；使用者同意實作與檢查（2026-11-07）。
> 本修正為**事後新增**：起因於 4.4.0（三）已揭露之遮蔽缺陷（bd91386），正文須標示「事後修正」。

## 1. 問題

`zt_kpm_xapp.py` 之 `fuse()` 採「第一條符合即決定」。C_i 第一個違反窗回傳 `R1_CI_PENDING`（low-trust）後即返回，因此同窗之 `R1_D2_VETO` 與 `R2_SI_D1_BOUND`（皆為 rejected）不會被評估：

```
if ci == "violated": return R1_CI_VETO if ci_run >= L_C else R1_CI_PENDING   # ← 提前返回
if d2 == "violated": return R1_D2_VETO
...
```

既有注入每次僅一種偽造，故此組合未被觸發；乾淨 D-30 之 C_i 違反為 0，故亦未觸發。

## 2. 修正

新增 `--fusion-order {first-match, severity}`，**預設 first-match**（逐位重現既有全部輸出與回歸基準）。

severity 模式：
1. 評估全部規則，得符合集合 M（不含 `R0_CLEAN`）。
2. 決策 = M 中嚴重度最高者，嚴重度 trusted ≺ abstain ≺ low-trust ≺ rejected（4.4.0 定義，不變）。
3. 同嚴重度時，以 RULE 表之層級（L1 ≺ L2 ≺ L3）再以表內順序決定 `rule_id`。
4. 規則稽核輸出新增欄位 `also_matched`（M 之其餘規則）。
5. M 為空 → `R0_CLEAN`。

等價描述：把 `R1_CI_PENDING` 移到所有 rejected 規則之後。除此之外，現有規則之相對結果不變（逐一檢查：CI_PENDING 與 R2 low-trust／R3 abstain 之組合，first-match 與 severity 結果相同）。

## 3. 預期與檢查（腳本內建，失敗即停）

| 檢查 | 判準 |
|---|---|
| C1 預設模式回歸 | `--fusion-order first-match` 逐位重現 `data/results/d30/` 之 xApp 輸出與 rt 回歸基準 |
| C2 乾淨資料不變 | severity 模式於乾淨 D-30：trusted／low-trust／abstain／rejected 與 159 筆 `R2_SI_D1_BOUND` 逐筆相同（理由：乾淨資料 C_i 違反為 0） |
| C3 單元測試 | 人工構造：C_i 第 1 窗 + D2 違反 → rejected（`R1_D2_VETO`，`also_matched` 含 `R1_CI_PENDING`）；C_i 第 1 窗 + S_i + 綁定強 D1 → rejected（`R2_SI_D1_BOUND`） |
| C4 注入實驗差異 | 重跑 C_i 注入（E1–E8）與 E10／RQ3：報告**改變判定之 (節點, 窗) 數**與其規則組合；預期只出現在「C_i 第一違反窗 ∩ 同窗 D2 或綁定 D1」 |

C4 若出現預期外之差異：停下回報，不調整規則。

## 4. 採用判準

C1–C3 通過且 C4 之差異僅限預期組合 → 以 severity 為正文主結果之融合順序，4.4.0（三）之「已知缺陷」段改寫為「已修正（事後）」並附差異數；否則維持 first-match 並保留揭露。

## 5. 與 DRL（E19）之關係

DRL 規格須以本修正後之 severity 版為 L1 基礎，並採「規則下限」設計（見 `WUT_feedback_DRL_ZT_plan.md` §4.4）：L1 rejected 規則先行；`R1_CI_PENDING` 不再提前返回，而是作為 DRL state 之輸入與決策下限（≥ low-trust）。

## 6. 附註

`R1_STAGE1` 見於正文與 CLAUDE.md 之規則清單，但目前 `fuse()` 未實作（身分前提於重放層恆成立）。實作 `R1_AUTHZ` 時一併說明二者於原型中之狀態。

## 7. 檢查結果（2026-11-08）

執行：`scripts/run_fusion_order_check.sh first-match|severity`（commit e8d0cba；severity 鏈於 15_E11 停下後依使用者選項 A 修改 E11 之獨立 trace 並續跑，2026-11-07 23:50 UTC ALLDONE，各步驟 exit 0；`fuse_detail()` 之內建檢查——非預期差異即 SystemExit——全程未觸發）。比對：`compare_fusion_order.py data/results/d30_fusion_order/first-match data/results/d30_fusion_order/severity`。

| 檢查 | 結果 |
|---|---|
| C1 | first-match 重跑 16 個輸出與 `data/results/d30/` 逐位相同（時間欄位除外） |
| C2 | severity 於乾淨 D-30：15,534 筆註記逐筆相同；159 筆 `R2_SI_D1_BOUND` |
| C3 | `test_fusion_order.py` 通過（窮舉 216 組合／模式；bound 28、legacy 33 組不同，皆為預期且皆更嚴） |
| C4 | 只有 E11 與 E11b 改變；其餘（E10、RQ3、E12、B4、fusion replay、C_i 統一版、可用資源評估、E14、E15／E16、E18 等）逐位相同 |

C4 之改變（全部為 `R1_CI_PENDING`（low-trust）→ `R2_SI_D1_BOUND`（rejected）；`R1_D2_VETO` 之組合未出現）：

- **E11**：26 個 (節點, 窗)（受測 13、其他節點 13）。於 first-match 下，此 26 筆皆為「乾淨回放為 rejected（`R2_SI_D1_BOUND`）、注入 $C_i$ 後被首次違反窗降為 low-trust」之判定減輕；severity 下與乾淨對照相同。受測節點之判定減輕：$C_i$ 灌水 2／7 → 0／0、虛減 1／3 → 0／0（T = 10／30）。另 seed 4203 target 6 虛減（T = 10、30）之 `leave_s` 由 9 變為 None：其唯一之「離開 trusted」事件即為上述減輕。n_records_traced 1,319,703 不變。
- **E11b**：$L_C$ = 2 與 3 各 98 個（受測 19：g = 1／2／3／5 為 6／5／3／5；同窗其他節點 79：17／25／20／17）；`R1_CI_VETO` 比例仍為 0；$L_C$ = 1 不變。n_records_traced 1,351,458 不變。
- `adversarial_msweep.json` 之 4 處「nan → nan」為比對器將 NaN 視為不等之假差異，非實質差異。

**附帶發現**：重算 E11 表（`make_table_E11.py`）時，正文 v7 之 E11 表有 4 格與腳本輸出不符（first-match 輸出：$C_i$ 虛減同狀態改規則 42／97，v7 寫 41／95；D2 降級 61／68，v7 寫 57／67）；`data/results/d30/E11_transitions.json` 與本次 first-match 重跑逐位相同，故為正文抄錄錯誤，v8 起以腳本輸出為準。

**採用**：依 §4，severity 為正文主結果之融合順序；程式預設仍為 first-match（重現既有回歸基準），主結果以 `ZT_FUSION_ORDER=severity` 產生，輸出在 `data/results/d30_fusion_order/severity/`。運算開銷（4.9.5）未以 severity 於閒置機器重新量測。
