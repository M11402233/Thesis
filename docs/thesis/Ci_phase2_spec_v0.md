# C_i 第二階段（步 1）規格 v0（2026-11-19，先於 D-30P 正式資料）

依據：`phase2_percell_spec_v0.md` §5 步 1、§9 Q-P3；`phase2_input_layer_v0.md` §5.1（使用者決定 Q-C1 = a、Q-C2、Q-C3）；`Ci_unified_spec.md` v1（實驗編號與彙總沿用）。

## 1. 輸入
- **(A) 主**：`percell_source.enb_lists` — 每窗 k 於窗末後之 eNB 報表時點之 RRC 連線名單（cell 1 於 +0.5 ms、cell 2–8 於 +0.8 ms，依 cell 合併）。
- **(B) 對照**：`percell_source.traffic_lists` — 窗內 ΔnTx > 0 之 UE。
- 窗 0–299，8 seed（D-30P GCC 13）。

## 2. 規則（Q-C1 = a）
- **主（set）**：mmWave 名單之聯集 ≠ 錨點（cell 1）名單 → 違反（多 → 灌水；少 → 虛減）。實作：`zt_kpm_xapp.verify_ci_ref(mode="set")`；升級沿用 `fuse`（L_C = 2：`R1_CI_PENDING`／`R1_CI_VETO`）。
- **對照（card）**：只比基數 \|聯集\| ≠ \|錨點\|（＝第一階段規則之精神），用以量化「集合相等」比「基數守恆」多抓到什麼。
- **(B)**：只判灌水（mmWave 流量名單中出現錨點名單外之 IMSI）；不判虛減（無流量 ≠ 不在）；報 (B) 與 (A) 之差異。
- 錨點不可由攻擊者控制（威脅模型不變）。

## 3. 實驗（沿用 Ci_unified 編號；攻擊者 = cell 2 之名單）
E0 乾淨；E1 灌水 +1…+6（後半段；延遲）；**E2a** 全域壓制（自全部 mmWave 名單移除，與第一階段對照）；**E2b（新）** 攻擊者自身名單移除 1…4 個 UE（單一 O-DU 實際能做之虛減；名單不足者略過並計數）；E3 自身名單替換 2／2；E4 三段；E5 全窗；E6 持續 D ∈ {1,2,3,5}；E7 不精確替換 10 組；E8 各 cell 名單規模、單 cell 抹除之條件偵測、被多個 mmWave cell 同時列名之 (窗, UE) 數。

## 4. 內建檢查（任一不符即停）
K1 `percell_source.check` PASS（X1–X3）；K2 窗 0–299 完整；K3 判定經 `verify_ci_ref`／`fuse` 且與獨立重算逐窗相同；K4 偽造 IMSI（9001 起）不與真 IMSI 重疊。

## 5. 自動化（使用者 2026-11-19 授權）
`scripts/r9/step1_auto.sh`（新機器 `~/zt_dev/`，`setsid nohup`）：等 `D30P_g13_phase0/DONE|STOPPED` → `scripts/r9/step1_gate.py`（8 seed 主檔、K1–K5、stderr 0；P-2、P-3 pass；P-5 未對應 0；P-6 非前綴檔 ⊆ GCC 11 批已接受之 22 檔）→ 通過才跑 `run_Ci_phase2.py`，輸出 `data/results/phase2/step1_Ci/`（`STEP1_DONE`／`STEP1_FAILED`／`STEP1_NOT_STARTED`、`auto.log`、`gate.json`）。**只跑步 1**；步 2 起待使用者看過結果。gate 已以 GCC 11 批測試（正確判不通過：P-2 8/8、缺 P-6 前綴檔）及人工改為通過之副本測試（正確判通過）。

## 6. 診斷試跑（GCC 11 D-30P，不得引用；`data/results/phase2/step1_Ci_diag_gcc11/`，新機器，15 s）
- K1–K4 全通過。E0：2,400 窗，違反 0、rejected 0；錨點名單每窗 30；mmWave 聯集每窗 = 錨點。
- (A) set：E1 +1…+6、E2a −1…−4、E2b −1…−4 皆 1,200/1,200；**E3 替換 1,200/1,200**；E6 D=1 未升級 1,200/1,200、D ≥ 2 未升級 0；E8 單 cell 抹除 72,000/72,000，被多個 mmWave cell 同時列名 0。
- (A) card：同上，唯 **E3 替換 0/1,200**（第一階段之盲點仍在）。
- (B)：乾淨灌水旗標 0/2,400；+1 灌水 2,400/2,400；mmWave 流量聯集每窗 17–30。

## 7. 對正文主張之影響（待使用者決定寫法；不得先改正文）
1. 集合相等版關閉第一階段之「守恆式替換」盲點（E3、E7 之淨值 0 案例）——條件是偽造之 IMSI 不在錨點名單中；攻擊者若以**錨點名單內、但非本 cell 服務**之真 IMSI 替換，集合相等仍可能被繞過（須另設計 E3'：以其他 cell 之真 IMSI 替換）。
2. 每個 UE 只被一個 mmWave cell 列名 → 單一 O-DU 之任何虛減皆被偵測；但此為 D-30P（無換手）之性質，換手中之雙列名須以 D-30H 檢查。
3. 乾淨 0 反例之意義縮小為「RRC 名單與錨點一致」，不說明 DU 之 KPM 名單可信（phase2 spec §7 已記）。
