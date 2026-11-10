# 第四章數字核對（thesis_v10 對 `data/results/d30_fusion_order/severity/`）— 進行中，2026-11-10

方法：以腳本從 JSON 重新產生表格儲存格，逐格與 `docs/thesis/thesis_v10.md` 字串比對（格式化至正文位數）。輸出已先確認可由原始資料逐位重現（`d30_repro_20261109`）。

## 已核對、全部相符（0 處不符）
| 正文位置 | 來源 | 範圍 |
|---|---|---|
| RQ3 表（window，行 2086 起） | RQ3_decision_replay.json | 20 列 × 6 欄 |
| RQ3 表（uebound，行 2059 起） | 同上 | 20 列 × 8 欄 |
| 4.9.6 政策消融表（P0–P4）與 P3 規則計數 7,810／6,183／1,133／249／159 | E10_D1_policy_ablation.json | 5 列：比例、UE 告警率、偵測率、延遲 |
| 4.9.6.6 E14 敏感度表 | E14_D1_sensitivity.json | 12 列：trusted（seed 範圍）、low-trust、rejected 數與比例 |
| 4.7.4 漂移表與乾淨 FPR（0.046／0.029） | E9_operating_regime_rt.json（common） | 8 個速率 |
| 4.7.5 階躍列（AF 1.3–1.5）偵測率與 onset | 同上 | 3 列 |
| 4.10 m-sweep 表與 m*=4、16.8% | adversarial_msweep.json | 4 列 |
| 4.7.5 E9b 乾淨 FPR 0.144（0.036–0.417）、校準目標 0.0515 | E9b_supervised_baseline_rt.json | |
| 4.6.2 E0（2,400 窗、0 反例、0 rejected）；E3 0／1,200；E8 72,000 窗-UE、雙掛 0 | Ci_unified_unified.json | |

## 注意事項（非錯誤）
- `Si_reference_ablation.json`（以窗序號為單位）與正文 4.7.4 表**不同**：正文表來自 `E9_operating_regime_rt.json`（實際秒）。引用時勿混用（例：時間參照乾淨 FPR 為 0.029，非 0.022）。
- RQ3 正文表已逐格相符；CLAUDE.md 所稱「×0.8 時 regret 6.1%→3.7%」係 window C_none 對 uebound C_strict，兩表皆已核對。

## 尚未核對
4.8.6（H_i D1 效能）、4.7.7（E13 τ_S 敏感度）、4.7.8（慢性中毒題組）、E9c／E9d 正文表、E11／E11b／E12、4.9.5（運算開銷；屬量測，每次不同，正文應標明機器與條件）、4.11（規則回放）、可用資源評估 xApp 表（strict／restrict_annotated）、附錄 B 之數字、第一／六章摘要中引用第四章之數字。
