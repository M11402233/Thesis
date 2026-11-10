# Stage 3 (S3-TM3) 移至新機器 — 步驟與閘門（2026-11-10）

背景：舊機器 2026-11-10 停電，S3-TM3 seed 4203–4205 中斷（4200–4202 完整、已檢查）。使用者決定 Stage 3 改在新機器（i7-14700）收。

## 風險（必讀）
舊機器 ns-3 以 `NS3_NATIVE_OPTIMIZATIONS=ON`（-march=native，Xeon Silver 4110，含 AVX-512）建置。
1. 舊機器的執行檔**不能直接拷過去**（i7-14700 無 AVX-512，會 illegal instruction）；須在新機器重新建置。
2. 重新建置的浮點行為可能與舊機器不同 → 同一 seed 不保證逐位相同 → **4200–4202（舊機）與 4203–4205（新機）可能混用兩種建置**。
3. 因此新機器須先通過**閘門 G-S3**：用新建置重跑 S3-TM3 seed 4200 前 30 窗，與舊機器已完成之輸出逐位比對。
   - 通過：照原計畫補收 4203–4205（以及規格所需之其餘 seed）。
   - 不通過：**停下回報，不調參數**。選項：(a) 關閉 native 優化於新機重建並全部 seed 在新機重收（4200–4202 也要重跑）；(b) 接受混用並於論文揭露。由使用者決定。

## 步驟（皆在新機器）
### 1. 取得 ns-3 原始碼（含 scenario-three.cc 未提交修改；不含 build 與輸出檔，約 140 MB）
```bash
OLD=cindy1@10.10.10.136
ssh $OLD "cd ~ && tar czf - --exclude=ns-3-mmwave-oran/build --exclude=ns-3-mmwave-oran/cmake-cache --exclude='ns-3-mmwave-oran/*Stats*.txt' --exclude=ns-3-mmwave-oran/RxPacketTrace.txt --exclude='ns-3-mmwave-oran/cu-*-cell-*.txt' --exclude='ns-3-mmwave-oran/du-cell-*.txt' --exclude=ns-3-mmwave-oran/RlcAmBufferSize.txt ns-3-mmwave-oran" | tar xzf - -C ~
mkdir -p ~/oran-e2sim/e2sim/build
scp $OLD:oran-e2sim/e2sim/build/e2sim-dev_1.0.0_amd64.deb ~/oran-e2sim/e2sim/build/
```
### 2. 相依套件與 e2sim（與舊機器相同的 deb；舊機器已核對內容一致）
```bash
sudo apt update
sudo apt install -y build-essential cmake g++ python3 libsctp-dev libssl-dev libboost-all-dev libeigen3-dev libgsl-dev libsqlite3-dev libxml2-dev libgtk-3-dev pkg-config
sudo dpkg -i ~/oran-e2sim/e2sim/build/e2sim-dev_1.0.0_amd64.deb
```
（若 ns-3 configure 抱怨缺其他套件，照訊息補裝並回報，不要改程式。）
### 3. 建置（記錄 gcc 版本；舊機器 gcc 13.4 PPA）
```bash
gcc --version | head -1 > ~/build_gcc.txt
cd ~/ns-3-mmwave-oran && ./ns3 configure --build-profile=optimized --enable-examples=no --enable-tests=no && ./ns3 build scenario-three 2>&1 | tail -20
```
（configure 旗標以舊機器 `cmake-cache/CMakeCache.txt` 為準；有疑問先回報。）
### 4. 閘門 G-S3（約數分鐘至數十分鐘；SIMTIME=31 即可）
```bash
cd ~/oran-zt-kpm-verification
SIMTIME=31 OUT_DIR=$HOME/s3gate VARIANT=S3-TM3 SEEDS="4200" bash scripts/collect_stage3.sh
# 舊機器之 4200 完整輸出：先拉一份
scp $OLD:oran-zt-kpm-verification/data/game_stage3/S3-TM3/S3-TM3_ues30_t300_seed4200.txt /tmp/old4200.txt
# 前 30 窗 = 表頭 + 30*30 列 = 901 行
cmp <(head -901 /tmp/old4200.txt) <(head -901 $HOME/s3gate/S3-TM3_ues30_t300_seed4200.txt) && echo G-S3 PASS || echo G-S3 FAIL
```
（輸出檔名以腳本實際產生者為準。）
### 5. 正式補收（僅 G-S3 PASS 且使用者確認後；與 PSRO 同機，ns-3 每實例固定 1 核心、記憶體防護 600 MB）
```bash
cd ~/oran-zt-kpm-verification && mkdir -p data/game_stage3/S3-TM3
for s in 4203 4204 4205; do
  VARIANT=S3-TM3 SEEDS="$s" setsid nohup taskset -c <核心> bash scripts/collect_stage3.sh >> data/game_stage3/S3-TM3/collect_$s.log 2>&1 < /dev/null &
done
```
核心編號避開 PSRO workers（`nproc`/`taskset -cp $$` 確認）。
