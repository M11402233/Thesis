# r8b：4202 當機（RLC AM 換手轉送）之診斷版修正（2026-11-15）

- 新機器 `~/ns-3-mmwave-oran-r8b` ＝ r8 ＋ `patch_r8b.py`（只改 `src/lte/model/lte-rlc-am.cc`）。
- 當機點：`LteRlcAm::Reassemble`，無遺失分支、狀態 `WAITING_SI_SF`、FI = NO_FIRST_BYTE|*，`m_keepS0Reassemble` 為空而被解參考。
- r8b 之防護**只在原版必然解參考空指標之條件下**觸發：改走「有遺失」分支（丟棄無頭片段），並於 stderr 印一行 `ZT_R8B_GUARD`（含 SN 清單、VT(A)／VT(S)、進入時狀態）。其餘路徑不變。
- **待驗證之成因假說**（未證實）：轉送時依緩衝區索引（SN 值 0..1023）而非自 VT(A) 起之模序走訪；SN 繞回後順序錯置，「有遺失＋SI_SF＋單一片段」分支把 expected 設為 SN−1 且清空 kept S0，下一筆恰為 SN−1 時當機。
- 執行（新機器，`~/chain_r8b.sh`）：建置 → (a) 8 秒等價閘門 G9 對 G8（r8）→ (b) seed 4202 全長診斷 run，輸出 `data/ues30_ho_r8b_diag/`（**診斷用，非正式資料**）。
- 正式修正方式（僅防護 vs 修正走訪順序；後者會改變所有 seed 之輸出、須 8 seed 全部重收）待診斷結果與使用者決定。

## 診斷結果（2026-11-15 18:46 UTC）與 r8c

- 等價閘門 G9（r8b vs r8，8 s，FixedTtt，seed 4200）：62 檔 0 差異。
- seed 4202 於原當機點印出：`ZT_R8B_GUARD t=54.5428 rnti=100 lcid=3 sn=1023 prevExpected=1023 fi=3 nSdu=1 vtA=1023 vtS=1 entryState=2 snlist=0,1023,`
  → **假說證實**：VT(A)=1023、VT(S)=1，正確順序為 1023→0，程式依索引處理為 0→1023；且進入時狀態為 WAITING_SI_SF（=2）、無 kept S0。
  （更正：`m_assemblingState` 為換手重組專用，與接收端之 `m_reassemblingState` 分開；進入時之狀態來自建構子初值或同一 RLC 前一次轉送之殘留，非接收端。）
- **r8c ＝ r8 ＋ `patch_r8c.py`**（根本修正，新機器 `~/ns-3-mmwave-oran-r8c`）：F1 自 VT(A) 起依模序處理；F2 每次轉送自建構子初始狀態開始；F3 與狀態不一致之「連續」PDU 改走既有之有遺失分支。F1 重排與 F3 事件各印一行 `ZT_R8C`。
- 閘門（`~/chain_r8c.sh`）：G10（FixedTtt 8 s vs r8 之 G8）、G11（無換手 8 s vs r8 之 H2）、G12（G10 重跑之確定性）。G10／G11 與 r8 不同不必然為失敗（修正本身會改變行為），須連同 `ZT_R8C` 行數解讀。
- 未涵蓋：轉送路徑之其他部分（txon 緩衝區中尚未切完之 SDU 殘段、`MergeBuffers`）未逐行稽核。

## r8c 閘門結果與正式重收（2026-11-15）

| 閘門（8 s，seed 4200） | 結果 |
|---|---|
| G11 無換手 vs r8（H2） | 57 檔 0 差異；F1／F3／轉送呼叫皆 0 次 |
| G12 FixedTtt 重跑 vs G10 | 62 檔 0 差異（確定性） |
| G10 FixedTtt vs r8（G8） | 8／62 檔不同（PDCP 統計、X2Stats、RlcAmBufferSize、cu-up-cell-1、du-cell-6／8）；F1 重排 4 次（123 次換手）、F3 0 次 |
| G13／G14（加 `ZT_R8C FWD` 診斷行後）vs G10／G11 | 皆 0 差異 |

轉送路徑稽核（`UeManager::ForwardRlcBuffers`、`LteRlcAm` 之 LL HO 部分）：
- `MergeBuffers`：未發現錯誤（順序問題由 F1 涵蓋）。
- 重組結果（`m_transmittingRlcSdus`）不清空：G13 之 118 次轉送呼叫中，進入時非空者 0 次 → 於此情境未發生重複轉送。
- **未修正、須揭露**：(a) 118 次中 72 次重組出 0 個完整 SDU，此時走「只轉送 txon」分支，切到一半之 SDU 不補送（每次換手至多遺失 1 個 SDU）；(b) 其餘 46 次補送 `m_segmented_rlcsdu`（最後一個被切過之 SDU 之完整備份），該備份不隨 SDU 送完而清除，可能為重複或過時之 SDU（每次至多 1 個）；(c) 原作者刻意補送 PDCP SN 相鄰之前 1–3 個 SDU。三者合計每次換手約數個封包之遺失／重複，屬此模組「lossless HO」實作之限制；修正須改動每次傳輸機會皆執行之切段路徑（影響無換手資料），風險高於效益，**本版不修**。
- 正式重收：新機器 `data/ues30_ho_r8c_seeds/`，8 seed 同時，2026-11-15 21:51 UTC 起。

## r8d（2026-11-16）：轉送集合之根本修正 F4（使用者 2026-11-16 決定「必須修正」）

r8c 稽核所列之限制 (a)(b)(c) 不再保留為「揭露」，改以 `patch_r8d.py`（套用於 r8c 樹；改 `lte-rlc-am.{h,cc}`、`lte-enb-rrc.cc`）修正。逐行閱讀後原程式之問題：
(a) 未重組出完整 SDU 時，切到一半之 SDU 不補送；(b) 備份 `m_segmented_rlcsdu` 從不清除，可能為已完整傳送者（重複／過時）；
(c) 自不完整之歷史補送前 3 個 SDU（含第一個 SDU 自身之副本）；(d) 切剩之後半段（無 PDCP 標頭）被當成封包轉送；(e) 首段已 ACK、尾段未 ACK 之 SDU 被丟棄。

F4：RLC 於每個 SDU 交給 PDU 時記帳（完整副本、首／末 PDU SN、是否全部交出）；換手時轉送「帳上尚未全部確認者（未交完，或至少一個 PDU 未 ACK）」各一次、依序，其後接 txonBuffer（去掉切剩片段）。原重組程式保留作對照（其重組出之 SDU 必須皆在 F4 清單內）。記帳僅保留封包副本，不改 PDU 組法。僅支援 EnableAQM=false（本情境之預設）。

| 驗證（新機器，seed 4200，8 s） | 結果 |
|---|---|
| G16／G19 無換手 vs r8c（G11） | 62 檔 0 差異 |
| G17 有換手重跑 vs G15；G18、G20（僅改診斷）vs 前一版 | 0 差異 |
| G15 有換手 vs r8c（G10） | 14／62 檔不同（預期；轉送內容改變） |
| 轉送呼叫 | 153 次（30 次為起始切換、無資料；123 次帶資料） |
| 對照缺漏 missing／MISMATCH、PRE、AQM 警示 | 0／0 |
| 帳本轉送 SDU 合計／原重組合計 | 1,463／1,243（每次差 0–4） |
| 帶切到一半 SDU 之轉送 | 122 次（片段不再送出，改送完整 SDU） |
| 重複封包（uid） | 0 |
| PDCP SN 倒退：帳本內／接合處／txonBuffer 內 | 0／0／203 處（83 次轉送） |

txonBuffer 內之倒退：診斷印出之 139 處步幅僅 −1（14）與 −2（125），型態為兩條各自有序之串流交錯（例 1394, 1392, 1395, 1393）。
推論（未逐一以程式驗證）：路徑切換時，仍送往舊 cell 再被轉送之封包與直接送往新 cell 之封包於到達目標 RLC 時交錯；F4 不改變 txonBuffer 之順序。屬到達順序而非轉送清單之錯誤，未修；正文須揭露。
第一次編譯因複製之 cmake 快取失敗、三個驗證以舊 r8c 執行檔起跑約半分鐘，已停止並改名 `G1[5-7]*.stale_r8cbinary`。

r8d md5（含診斷之最終版；G20：FWD 153 FLAGS 0）：
```
694dcf8fdd64bc6eb49f89d930eff5c6  build/scratch/ns3.38.rc1-scenario-three-optimized
619af23f855de6efa8e966bfb9f68243  build/lib/libns3.38.rc1-lte-optimized.so
e7946d1b7341722d2a9adac0462f3f59  src/lte/model/lte-rlc-am.cc
ae35ebaac23fa7482f2c8fe9aa7d8bee  src/lte/model/lte-rlc-am.h
1c60e1e9d8af1e46eb0fccf49e2337ec  src/lte/model/lte-enb-rrc.cc
```
r8c 之 D-30H 重收（`data/ues30_ho_r8c_seeds/`）降為診斷用；seed 4202 已通過 54.27 s（2026-11-16 05:00 UTC 時於模擬 92 s）。r9 改以 r8d 為基礎。

## D-30H r8d full run: diagnostics (2026-11-18)

8 seeds × 301 s finished 2026-11-17 08:25–10:25 UTC (4202 included); collection checks passed (300 windows, 30 IMSI, N_total = 30).
Binary md5 unchanged (694dcf8f…, lib 619af23f…).

`ZT_R8D` totals over 8 seeds: FWD 37,178; MISMATCH 0; PRE 0; AQM 0; `missing` 0 in every FWD line; dup 0; partial = frag in every call.
Back-steps (PDCP SN, 12-bit, step ≥ 2048 mod 4096 counted as backward): backT 199,791; **backL 279; backJ 42** (the 8 s gate had 0 / 0).

Classification of the 321 ledger/junction back-steps (analysis of run.log BACK lines, 8 seeds):
* 253 are large jumps (|SN step| > 8), 68 are small (≤ 8). 247 of the 321 repeat an (seed, prev SN, cur SN) pair already printed at an earlier
  forwarding, i.e. the same neighbouring SDUs are forwarded again after another handover (222 of these were first printed in the txon part).
* CORRECTION of the first version of this note: "all large steps occur in sets with more than 4096 SDUs, so SN wrap-around explains them" is
  not evidence. 36,043 of 37,178 forwarding calls (97 %) have such sets (median ≈ 8,000), so that cross-tabulation has no discriminating
  power. The 12-bit SN can alias inside such a set, but nothing shows that this is the cause.
* Leading explanation (inference, not verified): the transmission queue at the target is an interleaving of two ordered streams (SDUs forwarded
  from the source and fresh SDUs arriving through the anchor); the ledger records transmission order and inherits that interleaving, so a
  ledger/junction back-step is the earlier txon back-step carried one step further. This is the same mechanism as backT.
* The 8 s gate had 3 ledger/junction back-steps in 1,224 forwarding calls before t < 8 s (all seeds); the long runs have 321 in 37,178 calls.
* Side finding: forwarding sets of ≈ 8,000 SDUs exceed the 2,048-SN reordering window of a 12-bit PDCP SN; ns-3's receiving PDCP does not use
  the SN, so delivery in the simulator is unaffected, but this would not hold in a real stack (disclose).
* Order check independent of the SN: `patch_r8d_seq.py` (diagnostic tree `~/ns-3-mmwave-oran-r8d-seq`, new machine) tags every PDCP PDU with
  its creation counter and counts backward steps of that counter by position. Result: see the section below once available.
