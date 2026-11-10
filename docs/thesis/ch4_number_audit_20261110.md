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

## 第二輪（同日）— 追加核對，同樣 0 處不符
| 正文位置 | 來源 | 範圍 |
|---|---|---|
| 4.8.6 逐 seed 表、E15 分群門檻表、E16 倍數表 | Hi_D1_performance.json、E15_E16_D1_robustness.json | 8 + 3 + 8 列 |
| 4.7.7 E13 τ_S 敏感度表與十等分表 | E13_tauS_sensitivity_rt.json | 5 + 10 列 |
| 4.7.5 E9c 兩張表（共模擾動、攻擊並存）與 E9d 全部數字（含逐 seed 3/8 方向、三組敏感度） | E9c_common_mode_rt.json、E9d_real_load_alarms_rt.json | |
| 4.7.8 慢性中毒題組：r*_D 表、Q2 速率表、Q4 hugging 表、Q6/E17 校準中毒表（含 k=4、5 之 s 放大 6.5–40.9、E17 引用的 0.00–0.03） | slow_poisoning_suite_rt.json、slow_poisoning_Q6_ext.json | 4 + 6 + 9 + 6 列 |
| 4.11 規則回放表（z 值、決策、規則、動作） | fusion_replay.json | 5 列 |
| 4.12 可用資源評估 xApp 表與攻擊下「無准入輸入之窗」25／80／76／79 | resource_eval_xapp_*.json | |
| 4.9.5 M1 四 xApp 合計延遲表 | resource_eval_xapp_benchmark_run1-3.json | |
| 4.6.7 E11b 分母、PENDING／BOUND 計數（6／5／3／5，合計 19）、未注入 31–45／560、1,351,458 筆 | E11b_pulses.json | |
| 4.4.0 E11 轉移表 | `make_table_E11.py` 重新產生 | 14 列與正文逐字相同 |

過程中曾有一次「不符」為核對腳本自身索引錯誤（誤取不同組別），修正後相符，非正文問題。

## 尚未核對
E12 表（候選規則 L_S）、4.9.5 前兩張延遲表（單 xApp 三次量測，屬量測值，應標明機器與條件）、4.0 資料集描述性統計、4.6.3–4.6.5（E1／E7／E8 表）、4.8 其餘表（D2、H1–H4）、4.9.6 其他小節之敘述性數字、附錄 B、第一／六章摘要中的第四章數字。
