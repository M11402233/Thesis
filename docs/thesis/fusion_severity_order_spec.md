# 規格：融合規則改為「最嚴重符合規則決定」（severity-first）

> 狀態：**草案，待使用者確認後才實作與產生結果**（2026-11-07）。
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
