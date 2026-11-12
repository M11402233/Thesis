# E26 規格 v1：C_i 連帶排除之量化與歸因式縮小

> 2026-11-13，使用者指示「5 可做」。本檔先於腳本執行 commit。事後新增（已看過 E21、E22、E25 之部分輸出）；主結果凍結，歸因變體只在本實驗評估，不改 `fuse()`。

## 1. 參照

| # | 項目 | 出處 | 內容 |
|---|---|---|---|
| R1 | C_i 為場域層級 | `zt_kpm_xapp.py:270–283` `verify_ci` | `violated = (len(union) != N_KNOWN)`；一窗一個判定，套用於該窗全部節點 |
| R2 | C_i 規則 | `zt_kpm_xapp.py:101–102`、`:400–401` | `R1_CI_PENDING`（low-trust，run < L_C）、`R1_CI_VETO`（rejected，run ≥ L_C）；L_C = 2 |
| R3 | 既有歸因 | `zt_kpm_xapp.py:279–281` | `candidate_cells`：僅當聯集含 ID > 9000 之成員時，列出回報該成員之 cell（未用於判定） |
| R4 | 限制之原文 | `chapter6_draft.md` 6.3.3 | 「C_i 為場域層級證據：違反時當窗每個節點皆受影響；攻擊者可藉此使誠實節點一併被排除。此連帶排除之代價未量化。」 |
| R5 | 嚴重度序之符合集合 | `zt_kpm_xapp.py:396–437` | 註記含 `rule_id` 與 `also_matched`（＝全部符合之規則 M）；各規則謂詞獨立 |
| R6 | 注入 | `run_E21_S0_membership.py:73–107` | A1_delete（刪 k 個自身 UE ⇒ N = 30 − k）；T0S、L = 10、k ∈ {1, 3} |
| R7 | D4 歸因 | `E25_cucp_membership_rule_spec.md` §3 | D4a 外來成員、D4b 失蹤成員，歸因於節點 j；乾淨 D-30 觸發 0 |

## 2. 攻擊

- **A1_delete**（R6）：虛減。
- **A5_inflate**（本規格新增）：節點 j 於 [t0, t0+L) 每窗加入 k 個假 ID（9001…），其 delay 取該窗 j 之平均（不改變 j 之平均延遲）⇒ N = 30 + k。j 當窗不在報表時不注入。
- 兩者皆使 C_i 違反；攻擊者之目的設為「使誠實節點被排除」。

## 3. 量測（攻擊區間 [t0, t0+L) 內、節點 c ≠ j 之「誠實 (節點, 窗)」）

- 乾淨回放下之准入率（strict、restrict_annotated）與攻擊下之准入率；**連帶排除 = 兩者之差**。另報判定轉移（→ low-trust、→ rejected）之筆數，與「每一筆竄改 (節點, 窗) 連帶排除之誠實 (節點, 窗) 數」。
- 變體：
  - **V-field（規則版）**：現行判定。
  - **V-cand**：C_i 違反且 `candidate_cells` 非空時，C_i 規則只套用於候選 cell；其餘節點之判定＝自 M 移除 `R1_CI_*` 後依嚴重度序重選（R5）。候選為空時同 V-field。
  - **V-D4**：C_i 違反且當窗有節點之 D4 violated 時，C_i 規則只套用於 D4 violated 之節點；其餘同上。無 D4 violated 之節點時同 V-field（fail-closed）。
- 攻擊節點 j 於三種變體下之 MF（strict、restrict）——歸因不得放過 j。
- 攻擊區間外（含區間後 POST = 10 窗）誠實節點判定與乾淨回放之差異筆數（不繼承之確認）。

## 4. 檢查（失敗即停）

- E26-0：乾淨回放 15,534 筆逐筆重現註記檔。
- E26-1：A1 之竄改筆數重現 E21-S1（2,022／590）。
- E26-2：攻擊區間內有注入之窗，全部節點註記之 C_i 皆為 violated；V-D4、V-cand 下 j 之判定不得較 V-field 寬鬆。
- E26-3：自 M 移除 `R1_CI_*` 之重選函式，對乾淨註記（無 C_i 規則）逐筆等於原判定。

## 5. 事先揭露之限制

1. V-cand 依賴「假 ID > 9000」之模擬慣例，等同已知登記名單；對虛減（A1）無候選。
2. V-D4 繼承 E25 之假設（CU-CP 可信）與限制（D-30 無換手）。
3. 只有腳本注入；攻擊者同時做延遲竄改之組合未評估。
4. 誠實節點「若無 C_i」之判定仍可能因 j 之報表改變（S_i 之 peer 中位數）而與乾淨不同；另報其筆數。
5. 輸出：`data/results/d30_fusion_order/severity/E26/E26_ci_collateral.json`；腳本 `xapps/verification/residuals/run_E26_ci_collateral.py`。
