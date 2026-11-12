# E24-pre 規格 v1：E23 之事後觀察之拆解——增益來自 log 域或來自全域參照（只讀乾淨 D-30）

> 2026-11-13，使用者選「B：先把意外觀察拆開」。本檔先於腳本執行 commit。探索性、事後訂定（已看過 E23 §11）；不改主結果與凍結參數。

## 1. 參照

| 項 | 出處 | 內容 |
|---|---|---|
| 事後觀察 | `E23_external_reference_spec.md` §11.1、§11.3(2) | Ref-0（節點內 UE 之 log 延遲平均 − 訓練 seed 之全域常數）：FA 0.050，DET ×0.892／×0.822／×0.8／×0.6 = 0.398／0.793／0.870／0.990 |
| S_i | `zt_kpm_xapp.py:285–300` | z = \|tgt − ref\| ÷ scale > 4；tgt = 節點內 UE 延遲之算術平均；ref = peer 節點平均之中位數；MIN_PEER = 2 |
| S_i 對學習型／×0.8 | `E19_eval_final_spec.md` §13.3 H3 | 違反比例：學習型 0.54–0.92 %、×0.8 3.7 % |
| 節點層級持續偏差 | `E23pre_cumulative_residual_precheck_spec.md` §6 | 26／56 個 (seed, 節點) 之平均殘差超過 θ |
| 攻擊注入 | `game_core.py:120–131` | 攻擊節點全部 UE 同乘 a；peer 不變 |

## 2. 統計量（皆為逐 (節點, 窗)；門檻 θ = 訓練 seed（LOSO）上 \|v\| 之 0.95 分位，雙邊）

| 代號 | 域 | 參照 | v | 攻擊 ×a 之位移 |
|---|---|---|---|---|
| A | 線性（算術平均） | 同窗 peer 中位數 | tgt − ref（= S_i 之帶符號殘差，未除尺度；分位門檻不受常數尺度影響） | (a−1)·tgt |
| B | **log 平均** | **同窗 peer 中位數** | lm_j − median_peer(lm_c)，lm = 節點內 UE 之 log 延遲平均 | log a |
| C | 線性 | 凍結全域常數 | tgt − 訓練 seed 之 tgt 中位數 | (a−1)·tgt |
| D | log 平均 | 凍結全域常數 | = E23 之 Ref-0 | log a |
| E | 算術平均之 log | 同窗 peer 中位數 | log tgt − log ref | log a |

另報 S_i 原判定（τ_S = 4、凍結尺度）之 FA 與 DET 作對照。a ∈ {0.892, 0.822, 0.8, 0.6}（固定階躍、非適應）。

## 3. 判定（事先寫定）

- **增益來自 log 域（peer 參照可保留）** ⇔ B 之測試 FA ≤ 0.10 且 DET(×0.8) ≥ 0.70。
- **增益來自全域參照** ⇔ B 之 DET(×0.8) < 0.30。
- 其餘：不確定。
- 另報（不入判定）：B 之逐 (seed, 節點) FA > 0.20 之序列數、lag-1 自相關中位數（持續偏差是否仍在）；E 與 B 之差（「先平均再取 log」與「先取 log 再平均」）。

## 4. 檢查（失敗即停）

- E24P-0：D 之 FA 與四個 DET 重現 `E23_s0.json` 之 Ref-0（差 ≤ 1e-12）。
- E24P-1：以 \|A\| ÷ anchor.scale > 4 重算之 S_i 違反筆數，逐 seed 等於乾淨註記之 `S_i == "violated"` 筆數。
- E24P-2：a = 1 時位移為 0。

## 5. 限制（事先揭露）

- 只有固定階躍。「增益來自 log 域」成立 ⇒ 僅表示值得另寫規格以學習型攻擊者驗證（E21-S4 之教訓），不代表可採用，亦不得更動凍結之 τ_S 與主結果。
- B 之 ×0.892 偵測率預期仍有限；學習型攻擊者可再縮小偏離量。
- 輸出：`data/results/d30_fusion_order/severity/E24pre/E24pre_logdomain.json`；腳本 `xapps/verification/residuals/run_E24pre_logdomain.py`。
