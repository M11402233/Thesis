# E14：H_i-D1 門檻與持續性之敏感度（規格 v1，2026-10-13）

> **性質：事後新增（post-hoc）之敏感度分析。** 本規格於看過 D-30 主結果之後才撰寫，正文須如實揭露。
> 本規格於 E14 之任何結果產出前定案；定案後不因結果修改，若須修改另立 v2 並揭露。

## 一、動機（已觀察到之事實，皆來自 D-30 腳本輸出）

- D-30（30 UE × 8 seed）乾淨資料、凍結參數（τ_H = 2／3、L_H = 1、uebound）下：trusted 50.3%、low-trust 48.7%、rejected 1.0%（159／15,534）。
- D1 逐 UE 之乾淨誤報與 7 UE 資料相當（`Hi_D1_performance.json`：0.102 ± 0.022；D-SH 0.116 ± 0.066）。
- 48.3% 之節點註記綁有 D1 證據（7,502／15,534）；S_i 違反 408 筆。159 筆 rejected 全為 `R2_SI_D1_BOUND`。
- 推論（待本實驗量化）：節點層級之 low-trust 與誤拒隨每節點 UE 數上升，屬規模效應。

## 二、問題

在 D-30 上，D1 之門檻（τ_H^warn／τ_H^reject）與持續窗（L_H）改變時，
(a) 乾淨資料之決策分布與誤拒、(b) 超時消失注入之偵測率與延遲，如何取捨？

## 三、不做的事

- **不改主結果**：第四章主結果一律維持凍結值（τ_H = 2／3、L_H = 1；`D30_parameter_freeze.md` v1）。
- **不從本實驗選擇新的操作點**；本實驗只報告敏感度與限制。
- 不改 D1 之定義、基線估計方式（LOSO）、綁定政策（uebound）、融合規則表。

## 四、設計

- 資料：D-30，8 seed，LOSO（D1 停留基線只用訓練 seed）。
- 綁定：uebound（定案政策）。
- 格點（12 組）：(τ_H^warn, τ_H^reject) ∈ {(2, 3)★、(3, 4)、(4, 5)、(6, 7)} × L_H ∈ {1★、2、3}；★ 為凍結值。
- 實作：直接呼叫 `run_E10_D1_policy_ablation.py` 之 `run_policy`、`inject_overtime`、`load_windows` 與 `zt_kpm_xapp` 之 `TrustAnchor`／`fuse`，僅於呼叫期間覆寫 `X.TAU_H_WARN`／`X.TAU_H_REJECT`，結束後還原。不複製判定邏輯。
- 注入：與 E10 相同之超時消失（停留長度 = ceil(median + z·σ)，至少 2 窗；注入點規則相同），z ∈ {3, 4, 6, 8}。
  加入 z = 8 之理由：τ_H^warn = 6 時 z ≤ 6 之注入依定義幾乎不可偵測，需有一個高於所有門檻之強度。

## 五、指標

1. 乾淨資料（分母 = 有效節點註記數）：trusted／low-trust／abstain／rejected 之筆數與比例；rejected 之規則來源；UE 告警率。
2. 注入：各 z 之偵測率（TPR）、平均偵測延遲（窗）、達 strong 之平均延遲。
3. 逐 seed 之 trusted 比例與 rejected 筆數（seed 為統計單位，報告範圍）。

## 六、內建檢查（任一失敗即停止、不寫檔、不調參數）

1. 開始時 `X.TAU_H_WARN`／`X.TAU_H_REJECT` 須等於 2.0／3.0；結束時須已還原。
2. (2, 3, L_H = 1) 之乾淨決策計數須與同資料集 `E10_D1_policy_ablation.json` 之 `P3_uebound_L1` 完全相同；(2, 3, L_H = 2) 須與 `P4_uebound_L2` 完全相同。
3. 上述兩組於 z ∈ {3, 4, 6} 之注入筆數、TPR、平均延遲須與 E10 相同。
4. 單調性：固定 L_H 時，門檻升高則 trusted 筆數不減；固定門檻時，L_H 增加則 trusted 筆數不減（D1 合格證據集合為子集關係，違反即表示實作有誤）。
5. 各組之有效節點註記總數須相同。

## 七、解讀規則（預先寫定）

- 若提高門檻或 L_H 可明顯提升 trusted 而偵測延遲僅小幅增加：於正文報告為「凍結值非此規模之最佳操作點」之限制，並列為未來工作（依部署規模校準）；**主結果不改**。
- 若 rejected 不隨門檻下降：報告為 `R2_SI_D1_BOUND` 之交叉佐證在高 UE 密度下之結構性限制。
- 無論結果為何，三類指標（可操作性、偵測率、延遲）須並列呈現，不得只報其一。

## 八、輸出

- `data/results/d30/E14_D1_sensitivity.json`、`fig_E14_D1_sensitivity.png`
- 腳本：`xapps/verification/residuals/run_E14_D1_sensitivity.py`
