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
