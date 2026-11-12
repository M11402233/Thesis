# 多模擬器可行性：OAI ＋ FlexRIC 於舊機器之試跑紀錄（2026-11-13）

> 使用者指示「先確認 OAI 跑不跑得起來；講求效能的話移一部分到新機器」。本檔只記錄試跑事實，不是實驗規格；未產生任何論文數字。試跑檔案皆在工作階段之暫存目錄，未寫入 repo 之 `data/`。

## 環境（舊機器 10.10.10.136，使用者 cindy1）

| 項 | 值 |
|---|---|
| OAI | `~/openairinterface5g`，commit `1d479b2aa9`（integration_2025_w12）；`nr-softmodem`、`nr-uesoftmodem`、`librfsimulator.so` 已建置；`E2_AGENT=ON`、`E2AP_V2`、`KPM_V2_03` |
| 既有 FlexRIC | `~/flexric/build`：`E2AP_V1`、`KPM_V3_00` ⇒ **與 OAI 之 E2 agent 版本不相容**（RIC 解碼 E2 Setup 時 assert） |
| 權限 | `sudo` 需密碼；`docker` 無權限（`permission denied … docker.sock`） |

## 做了什麼

1. 以 OAI 內附之 FlexRIC 原始碼（`openair2/E2AP/flexric`，submodule `beabdd07`）另建一份相容版：`~/flexric_build_e2apv2_kpmv203_gcc13`（gcc-13、**Debug**、`E2AP_V2`、`KPM_V2_03`、`XAPP_MULTILANGUAGE=OFF`、`UNIT_TEST=FALSE`）。未改動 `~/flexric` 與 `/usr/local/lib/flexric`。
   - Release 建置（`~/flexric_build_e2apv2_kpmv203`）之 nearRT-RIC 啟動即 segfault，**不可用**；該目錄可刪（工具之安全檢查擋下了我的刪除指令，留給使用者）。
2. 不用 sudo：`nr-softmodem --rfsim --phy-test`（band 78、106 PRB）＋ `nr-uesoftmodem --rfsim --phy-test` ＋ nearRT-RIC ＋ `xapp_kpm_moni`，皆以暫存目錄為工作目錄（build 目錄內有 root 擁有之 `nrMAC_stats.log`，在該處執行會失敗）。

## 結果

- gNB 與 UE 啟動並同步（`Initial sync successful`；gNB 之 MAC 統計顯示 UE 1234 有上下行流量）。無 SYS_NICE 權限，僅警告。
- E2 鏈路成立：`E2 SETUP-REQUEST rx … Node ID 3584`、RIC 接受 RAN function（含 ID 2 `ORAN-E2SM-KPM`）；xApp 註冊（`Registered E2 Nodes = 1`）、KPM 訂閱 `SUBSCRIPTION RESPONSE rx`、解除訂閱成功，`Test xApp run SUCCESSFULLY`。
- **未取得含 UE 之 KPM 量測列**：phy-test 模式之 UE 無 RRC／核心網 context，xApp 未印出逐 UE 量測。要有逐 UE 之 KPM，需 SA 模式＋ 5G 核心網（OAI CN5G 為 docker 部署）⇒ **需要 docker 權限或 sudo**。

## 判斷

- 「跑不跑得起來」：**RAN ＋ E2 ＋ RIC ＋ xApp 之鏈路可以**；**逐 UE 之 KPM 量測尚未驗證**，卡在核心網之權限。
- 單一 gNB ＋ 單一 UE 之 rfsim 於 4 核心舊機器可即時執行；多 gNB、多 UE（S_i 需 ≥ 3 個同時有 UE 之節點）之 CPU 需求未量測，預期須移至新機器。
- 下一步需使用者決定／提供：(a) 舊機器之 docker 群組權限或 sudo，或改在新機器（使用者 cindy）上建置；(b) 多模擬器之範圍（建議：成員類規則 C_i／D3／D4 之乾淨誤觸與 live E2 之小規模交叉驗證，不重現 S_i 與 DRL 賽局）。
