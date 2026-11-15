# r8b：4202 當機（RLC AM 換手轉送）之診斷版修正（2026-11-15）

- 新機器 `~/ns-3-mmwave-oran-r8b` ＝ r8 ＋ `patch_r8b.py`（只改 `src/lte/model/lte-rlc-am.cc`）。
- 當機點：`LteRlcAm::Reassemble`，無遺失分支、狀態 `WAITING_SI_SF`、FI = NO_FIRST_BYTE|*，`m_keepS0Reassemble` 為空而被解參考。
- r8b 之防護**只在原版必然解參考空指標之條件下**觸發：改走「有遺失」分支（丟棄無頭片段），並於 stderr 印一行 `ZT_R8B_GUARD`（含 SN 清單、VT(A)／VT(S)、進入時狀態）。其餘路徑不變。
- **待驗證之成因假說**（未證實）：轉送時依緩衝區索引（SN 值 0..1023）而非自 VT(A) 起之模序走訪；SN 繞回後順序錯置，「有遺失＋SI_SF＋單一片段」分支把 expected 設為 SN−1 且清空 kept S0，下一筆恰為 SN−1 時當機。
- 執行（新機器，`~/chain_r8b.sh`）：建置 → (a) 8 秒等價閘門 G9 對 G8（r8）→ (b) seed 4202 全長診斷 run，輸出 `data/ues30_ho_r8b_diag/`（**診斷用，非正式資料**）。
- 正式修正方式（僅防護 vs 修正走訪順序；後者會改變所有 seed 之輸出、須 8 seed 全部重收）待診斷結果與使用者決定。
