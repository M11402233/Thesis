# 非公眾網路 O-RAN 邊緣節點的零信任 E2 量測資料可信度驗證：以跨節點空間物理一致性對抗 KPM 偽造

> **v13 之數字規則（2026-11-26）**：本版依研究方法 v13（`docs/thesis/research_method_v13_draft.md` v2）改寫。**正文之全部結果數字只來自 D-50PH（50 UE，主）與 D-S12（12 UE，低密度對照）**；兩者收集或重跑完成前，結果一律標【待定】，由此導出之結論亦標【待定】，不以任何前版資料之數字代替。量測定義採第二階段修正後之定義（3.3.1）；修正之原因、逐封包驗證與適用限制見附錄 A，附錄不列修正前之效能數字。門檻沿用定案值，不以 D-50PH 或 D-S12 重選。前版（v12.3）保留於 `thesis_v12_3.md`，僅供對照，不引用其數字。


*Zero-Trust Verification of E2 Measurement-Data Trustworthiness for NPN O-RAN Edge Nodes: Defending KPM Falsification via Cross-Node Spatial-Physical Consistency*

**版本**： v13（2026-11-26）——v12.3 ＋ 研究方法 v13：（1）資料改為 D-50PH（主）與 D-S12（低密度對照），刪除前版資料集與其數字；（2）量測定義改為第二階段之逐 cell 歸屬與有效延遲樣本（3.3.1），H_i-D2 改以換手事件判定合法轉移；（3）第五章改寫為規則版作為學習之基礎：訓練與測試之攻擊集分離（E29 只測試、依與訓練池之差異分三類報告）、證據不足之處理（abstain，任何准入政策下皆不准入）、形式化安全性質 S1–S5、規模轉移（50 UE 訓練 → 12 UE 測試）、固定對手池下之獎勵敏感度、直接比較基線（B-3σ、B-LSTM、B-AE）與 OAI 介面整合（O-1–O-4）；（4）附錄 A 改為量測定義之修正紀錄。**未改任何判定規則與門檻**；全部結果待重跑，標【待定】。第六章（`chapter6_v12_3.md`）尚未依本版改寫。

## code
[**githu**b](https://github.com/M11402233/Thesis.git)

---
