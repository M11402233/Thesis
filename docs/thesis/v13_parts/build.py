"""Assemble docs/thesis/thesis_v13.md from v13_parts and unchanged ranges of thesis_v12_3.md."""
import os
from asm import L, rep

HERE = os.path.dirname(os.path.abspath(__file__))
def P(name): return open(os.path.join(HERE, name), encoding='utf-8').read().rstrip('\n') + '\n'

# ---- ch.2 ----
ch2 = rep(L(165, 198), [
    ("本研究資料中同窗跨 cell 區間平均延遲之變異係數中位數為 0.275（4.7.1），並不小，故「相近」之程度須由 4.7.4 之乾淨誤報率實測，不能由離散度推定",
     "同窗跨 cell 延遲之離散度於 D-50PH 上量測【待定】（4.7.1）；「相近」之程度須由 4.7.4 之乾淨誤報率實測，不能由離散度推定"),
    ("各裝置「連續最後事件歸屬 LTE」之窗數（與 mmWave 鏈路劣化相關，4.8.1）具穩定模式",
     "各裝置「已連線但連續無 mmWave 接收」之窗數（3.3.3）具穩定模式"),
    ("固定 30 個已登記之裝置、7 個 gNB 與 1 個涵蓋全場域之 LTE 錨點（4.0.3、4.2.1）",
     "固定之已登記裝置（主資料 50 個、低密度對照 12 個）、7 個 gNB 與 1 個涵蓋全場域之 LTE 錨點（4.0.3、4.2.1）"),
])

# ---- ch.3 up to 3.3.0 ----
ch3a = L(200, 240)

ch3_332 = r'''#### 3.3.2 (A) S_i：跨節點空間一致性殘差（延遲場域共識）

S_i 驗證「此節點的觀測是否被同一時刻的其他節點支持」。偵測維度選定為**延遲**（3.3.1 之 cell 延遲值）：吞吐量自然變異大且無 PRB／CQI 硬約束（見 3.3.5），UE 數則屬 C_i 的守備範圍。同窗跨 cell 延遲與吞吐量之離散度於 D-50PH 上量測【待定】（4.7.1）；延遲是否足以作為共識參照，由 4.7.4 之乾淨誤報率直接實測。**此維度選擇由資料的經驗可觀測性決定，而非預設攻擊落於延遲。**

對受測 cell j 於窗 t：

```
中心   c_j(t) = median{ DLY_k(t) : k 為同窗其他有有效樣本之 mmWave cell }   （同一時刻跨節點共識）
尺度   s      = 1.4826 · MAD_global                                     （訓練 seed 之乾淨資料，凍結）
殘差   z_j(t) = | DLY_j(t) − c_j(t) | / s
判定   S_i violated  ⟺  z_j(t) > τ_S                 （τ_S = 4，凍結；敏感度見 4.7.7）
```

- **（空間性）** 中心取自同一時刻其他 cell，故 z_j(t) 度量節點 j 對場域即時共識的偏離——此為跨節點空間一致性，非節點自身的時間基準。
- **（尺度穩定）** 因同窗有效 cell 數少（N ≤ 7），即時 MAD 有小樣本高變異問題，故尺度改由乾淨資料全域估計；1.4826 使 MAD 成為常態下標準差的漸近一致估計量。門檻 τ_S 凍結；尺度 $s$ 於新資料上以 LOSO 重新估計（不含 held-out seed），此為估計而非選擇門檻。
- **（每窗獨立）** 每窗獨立對照固定尺度與同窗中心，不累積歷史殘差。
- **（S_i 證據不可得）** 當受測 cell 之同窗 peer 數 < MIN_PEER = 2（即同窗有效 mmWave cell < 3），或受測 cell 當窗無有效延遲樣本時，S_i 判 **unavailable**：若同窗無其他證據則判 abstain，不論最終標籤，於任何准入政策下皆不准入（4.9.3）。證據可用率取決於 UE 密度，於 D-50PH 與 D-S12 各報【待定】（4.7.1）；abstain 之**決策**比例另受融合順序影響，不等於證據不可得率（4.4.0）。此確保「證據不足」不等於「證據支持」——零信任的體現。

**尚待實作**：`config/topology.yaml` 鄰接矩陣（依場景座標計算）用於 S_i 的拓樸加權強化，非 S_i 主判據前提。
'''

ch3_335 = r'''#### 3.3.5 涵蓋範圍與 PRB 定位

三殘差涵蓋基數（C_i）、跨節點延遲一致（S_i）、成員轉移（H_i）。**純吞吐量竄改不在涵蓋範圍**：RLC 統計無 PRB／CQI，吞吐量缺乏物理硬約束。純吞吐量竄改若伴隨延遲異常則落入 S_i、伴隨 UE 數異常則落入 C_i，其未涵蓋角落限縮於「純數值、無副作用」之攻擊；其影響不推定為低（4.5.2）。**PRB 之定位**：三殘差之驗證不使用 PRB。D-50PH 與 D-S12 開啟 ns-O-RAN 之 E2 NR 報表（`--e2nrEnabled=true`），由 cell 2–8 之 DU 報表取得原生 `RRU.PrbUsedDl`；該量**僅用於 4.12 之資源評估**（准入政策下已用 PRB 之保留比例與能見度損失），不作為驗證證據，且其本身亦可被受攻陷之節點竄改。CQI 仍未取得。
'''

ch4 = ''.join(P('ch4/' + n) + '\n' for n in
              ['41_45.md', '46_475.md', '4751_4755.md', '476_478.md', '48.md', '49.md', '410_tables.md'])

figs = rep(L(2510, 2539), [
    ("| Fig 4-5 | `fig_Si_reference_ablation_rt` | 參照機制受控消融（實際秒；圖片連結待上傳） |", "| Fig 4-5 | `fig_Si_reference_ablation_rt` | 參照機制受控消融 |"),
    ("| 階躍與漸進攻擊下之操作區對照（實際秒；圖片連結待上傳） |", "| 階躍與漸進攻擊下之操作區對照 |"),
    ("| 監督式分類器（階躍訓練）之漂移對照（實際秒；圖片連結待上傳） |", "| 監督式分類器（階躍訓練）之漂移對照 |"),
    ("| 良性共模擾動下之誤報（實際秒；圖片連結待上傳） |", "| 良性共模擾動下之誤報 |"),
    ("| 自我參照 LSTM 基準（%/秒；圖片連結待上傳） |", "| 自我參照 LSTM 基準 |"),
    ("| τ_S 敏感度（實際秒；圖片連結待上傳） |", "| τ_S 敏感度 |"),
    ("| 慢性中毒：偵測前沿（實際秒；圖片連結待上傳） |", "| 慢性中毒：偵測前沿 |"),
    ("| 慢性中毒：偵測前偏差（實際秒；圖片連結待上傳） |", "| 慢性中毒：偵測前偏差 |"),
    ("| 慢性中毒：貼門檻攻擊（實際秒；圖片連結待上傳） |", "| 慢性中毒：貼門檻攻擊 |"),
    ("| 最後事件歸屬 LTE 停留分布 |", "| mmWave 缺席之停留分布 |"),
    ("| D2 注入完整性檢查 |", "| D2：換手事件對應與注入完整性檢查 |"),
    ("| E14：D1 門檻與持續窗之敏感度（事後新增） |", "| E14：D1 門檻與持續窗之敏感度 |"),
])
figs = figs.replace('## 圖目錄\n', '## 圖目錄\n\n全部圖於 D-50PH（與 D-S12）重跑後重新產生【待定】。\n', 1)

code = rep(L(2540, 2582), [
    ("| `collect_ues30.sh` | D-30 資料集收集（30 UE、E2 NR 報表、8 seed） | 4.0.3 |\n| `collect_Ci_60s_10seed.sh` | 前版 D-C 資料集收集 | 附錄 |",
     "| `scripts/r9/d50ph_chain.sh` | D-50PH 收集與驗收（50 UE、FixedTtt、r11、8 seed） | 4.0.3 |\n| `scripts/r9/run_ds12_full.sh`、`scripts/collect_ds12_r11.sh` | D-S12 收集與驗收（12 UE） | 4.0.3 |"),
    ("| `run_Ci_experiments.py`、`run_Ci_extended_E6E8.py`、`make_fig_Ci_final.py` | 前版（D-C）之 C_i 腳本；僅供附錄對照 | 附錄 |\n", ""),
    ("| `run_Si_reference_ablation.py`、`run_E9_operating_regime.py`、`run_E9b_supervised_baseline.py`、`run_E9c_common_mode.py`、`run_E13_tauS_sensitivity.py`、`run_slow_poisoning_suite.py` | 時間單位修訂前（%/窗）之版本；僅供附錄對照 | 附錄 |\n", ""),
    ("| `audit_delay_cv.py` | 同窗跨 cell 延遲離散度、S_i 證據可用性、serving cell 轉移統計 | 4.7.1、4.8.4 |",
     "| `audit_delay_cv.py` | 同窗跨 cell 延遲離散度、S_i 證據可用性、serving cell 改變統計 | 4.7.1、4.8.4 |"),
    ("| `prepare_d30.py` | D-30 分析檔（0–299 窗）與一致性檢查 | 4.0.3、4.2.3 |",
     "| `prepare_d30.py` | 分析檔（0–299 窗）與一致性檢查；D-50PH／D-S12 之版本待補 | 4.0.3、4.2.3 |"),
    ("| `scripts/run_d30_pipeline.sh` | D-30 全部實驗之執行順序（任一內建檢查失敗即停止） | 全章 |",
     "| `scripts/run_d30_pipeline.sh` | 全部實驗之執行順序（任一內建檢查失敗即停止）；D-50PH／D-S12 之版本待補 | 全章 |\n| `scripts/advisor_20261118/run_C3_comparison.py` | 同條件偵測方法比較（C3） | 4.7.5.5 |\n| `xapps/verification/residuals/attack_generators.py` | E29 不規則攻擊產生器（只用於測試） | 5.2a |"),
])

refs = L(2583, 2644)
refs = rep(refs, [
    ("- Schmidt, R., Irazabal, M., Nikaein, N. (2021).",
     "- Lacava, A., Bordin, M., Polese, M., Sivaraj, R., Zugno, T., Cuomo, F., Melodia, T. (2023). \"ns-O-RAN: Simulating O-RAN 5G Systems in ns-3.\" *Proc. Workshop on ns-3 (WNS3 2023)*.（作者、頁碼與 doi【待核對】；Scenario Zero 之 12 UE 設定亦以此為出處【待核對】）\n- Schmidt, R., Irazabal, M., Nikaein, N. (2021)."),
    ("- Aizikovich, E., Mimran, D.,",
     "- El-Hajj, M. (2025). 零信任與聯邦學習之 O-RAN 遙測完整性框架. *Future Internet* 17(5), 233.（作者全名、題目與卷期【待核對】）\n- Aizikovich, E., Mimran, D.,"),
])

doc = ''.join([
    P('00_header.md'), '\n', P('01_ch1.md'), '\n', ch2, '\n', ch3a, '\n',
    P('03_331.md'), '\n', ch3_332, '\n', P('03_333_334.md'), '\n', ch3_335, '\n',
    P('04_intro_40.md'), '\n', ch4, P('05_ch5.md'), '\n---\n\n',
    figs, '\n', code, '\n', refs, '\n', P('09_appendixA.md'),
])
dst = os.path.expanduser('~/oran-zt-kpm-verification/docs/thesis/thesis_v13.md')
open(dst, 'w', encoding='utf-8').write(doc)
print(dst, len(doc.split('\n')), 'lines')
