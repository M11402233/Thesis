# RQ3 三欄拆分：攻擊者 cell 被誰擋下（教授 B1-3；P0）規格 v0

**問題**：簡報第 61 頁「strict：×0.6 → 2.2%」為修正前數字，且未說明是哪一條規則擋下攻擊者。教授懷疑主要是 D1 low-trust 的大量排除，而非 S_i 偵測。

**做法**（不改 `zt_kpm_xapp.py`、不改凍結值）
- 資料：D-30，`ZT_DELAY_SOURCE=reconstructed`、`ZT_FUSION_ORDER=severity`、`ZT_DATASET=d30`；註記政策 uebound；LOSO 之 `TrustAnchor`（與 RQ3 相同）。
- 攻擊：沿用 `run_RQ3_decision_replay.ATTACKS` 與 `apply_attack`（clean、step ×0.8、×0.6、drift 1%、2%；drift 下限 0.05，原式）；注入起點 = 序列中點，只看後半。
- 對每個 (seed, 攻擊 cell, 攻擊, 窗 k)：記錄攻擊者 cell 之註記 S_i、H_i-D1、C_i、決策與 strict 是否准入；以及「無驗證時攻擊者會不會被選中」（C_none 之選擇 = 攻擊者且非真值最佳）。
- 歸因（只對 strict 未准入之窗；互斥優先序 S_i > D1 > C_i > 其他，並另報重疊）：
  - S_i：攻擊者 cell 之 S_i = violated
  - D1：H_i-D1 ∈ {strong, weak}（S_i 非 violated）
  - C_i：C_i = violated（前兩者皆否）
  - 其他：abstain 等
- **對照**：同一 cell、同一窗在 clean 下之未准入率與歸因（若攻擊下被 D1 擋的比例與 clean 相同，代表擋下與攻擊無關）。
- 主表：lure 機會（C_none 會選攻擊者且其非最佳）中，strict 擋下之比例，依 S_i／D1／C_i／其他拆三（四）欄；另列 clean 對照。

**內建檢查**：clean 下之 strict 准入率（yield）須等於既有 `data/results/d30_delay_reconstructed/` 之 xApp 結果（若有可比數字），否則報告差異、不調。

**限制**：cell 歸屬沿用主檔（最後一筆 PDU 所在 cell）；代理決策（最低回報延遲），非閉迴路。

## 結果（2026-11-18，`data/results/advisor_20261118/RQ3_rule_split.json`）
- 內建檢查：clean 攻擊半段 strict 准入 3,513／7,747 = 0.4535，與 `d30_delay_reconstructed` 之 xApp 註記（同區段）逐筆相同 ✓。
- strict 下攻擊達成率（lure 機會中仍被選中）：×0.8 **52.1%**、×0.6 **47.8%**、drift 1% 14.9%、drift 2% 6.8%（RQ3 原式 drift 下限 0.05）。**簡報第 61 頁「×0.6 → 2.2%」於區間資料不成立。**
- 擋下者（占 lure 機會）：×0.8：D1 0.458、S_i 0.021；×0.6：D1 0.464、S_i 0.058；drift 1%：S_i 0.700、D1 0.151；drift 2%：S_i 0.868、D1 0.064；C_i 皆 0。
- 階躍攻擊下被擋之攻擊者窗，×0.8 有 4,050／4,119、×0.6 有 3,936／4,244 在 clean 同窗也被擋 → 擋下與攻擊無關（D1 之常態排除）。
