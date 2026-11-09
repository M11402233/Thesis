# 交接：DRL 賽局（E19）移至新機器（2026-11-09）

> 新機器上之 Claude 工作階段：**先讀本檔與 CLAUDE.md，再讀 `docs/thesis/E19_DRL_game_spec.md` §2a、§2b、§3a、§10b**。不要一次讀入正文全文。

## 1. 現況（2026-11-09）

| 項目 | 狀態 |
|---|---|
| 規格 E19 v2（PSRO） | 定案。R-a～R-f 依建議值（11-08）；**R-d 改為相對門檻**（11-09，使用者）：NashConv ≤ 0.05 × 第 1 輪 NashConv 即停、最多 6 輪；**R-f 事後修正**（11-09，使用者）：每個最佳回應至多 300,000 步、每 50,000 步以訓練 seed 驗證、保留最佳存檔 |
| 環境 | `xapps/verification/adversarial/`：`game_core.py`、`env_kpm_game.py`、`psro.py`、`lcurve.py`、`check_env.py`（G1–G3）、`check_speedup.py`（S1–S2） |
| 一致性檢查（舊機器） | G1 15,534 筆逐筆相同；G2a 434,952 筆；G2b RQ3 最大差 0；G2c E11 S_i 類 224 列；G3 決定性；S1 批次 = 逐節點；S2 T0Cache 等價；G4 誘導率 2.2363%／46.2092%／8.2922% 與乾淨誤拒 159／15,534 |
| 學習曲線（R-f，舊機器，僅供決定規則） | 偵測端 10 萬步即平穩；攻擊者 5 萬步達最高後退化。結果於 `data/results/d30/drl/lcurve/` |
| 舊機器上之 O-full t0 PSRO | 2026-11-09 起以 1 核心試跑；**移機後視為試跑，不引用**（兩機 CPU 指令集不同，結果不會逐位相同） |
| 簡報 | v1.7 第 42 頁仍寫 ε = 0.01（待使用者決定是否出 v1.8） |

## 2. 新機器之安裝與檢查（裸機；全部通過才可訓練）

以下在**新機器**執行（舊機器 `cindy1@10.10.10.136`；新機器假設為 Ubuntu 22.04、Python 3.10.12，與舊機器相同）。

### 2.1 系統套件
```bash
sudo apt update
sudo apt install -y python3-venv python3-pip git curl tar openssh-client
python3 --version          # 須為 3.10.x（舊機器 3.10.12）
```

### 2.2 程式（含 git 歷史，不含 data；約 12 MB，不需先 push）
```bash
ssh cindy1@10.10.10.136 "cd ~ && tar czf - --exclude=oran-zt-kpm-verification/data oran-zt-kpm-verification" | tar xzf - -C ~
cd ~/oran-zt-kpm-verification && git log --oneline -3      # 確認與舊機器最新 commit 相同
git config --global user.name "M11402233"
git config --global user.email "M11402233@mail.ntust.edu.tw"
```

### 2.3 唯讀資料（約 35 MB）
```bash
R=cindy1@10.10.10.136:/home/cindy1/oran-zt-kpm-verification/data
D=~/oran-zt-kpm-verification/data
mkdir -p $D/ues30_seeds $D/results/d30_fusion_order $D/results/d30/drl
scp -r $R/ues30_seeds/analysis $D/ues30_seeds/
scp -r $R/results/d30_fusion_order/severity $D/results/d30_fusion_order/
scp -r $R/results/d30/drl/lcurve $D/results/d30/drl/          # R-f 紀錄（選擇性）
ls $D/ues30_seeds/analysis | wc -l                           # 應為 9（8 個 seed 檔 + manifest.json）
```

### 2.4 Python 環境（版本須與舊機器相同）
```bash
python3 -m venv ~/venvs/drl
~/venvs/drl/bin/python -m pip install --upgrade pip
~/venvs/drl/bin/pip install torch==2.5.1+cpu --index-url https://download.pytorch.org/whl/cpu
~/venvs/drl/bin/pip install -r ~/oran-zt-kpm-verification/xapps/verification/adversarial/requirements_drl.txt
~/venvs/drl/bin/python ~/oran-zt-kpm-verification/xapps/verification/adversarial/check_versions.py   # 須顯示 ✓
```

### 2.5 Claude Code 與記憶檔
```bash
curl -fsSL https://claude.ai/install.sh | bash               # 安裝 Claude Code（依畫面指示登入）
# 記憶檔：資料夾名稱 = repo 絕對路徑之 / 換成 -（新機器 /home/cindy/oran-zt-kpm-verification）
mkdir -p ~/.claude/projects/-home-cindy-oran-zt-kpm-verification
scp -r cindy1@10.10.10.136:/home/cindy1/.claude/projects/-home-cindy1-oran-zt-kpm-verification/memory \
       ~/.claude/projects/-home-cindy-oran-zt-kpm-verification/
cd ~/oran-zt-kpm-verification && claude
```
開啟後第一句：「讀 `docs/thesis/HANDOFF_DRL_20261109.md`，從 2.6 開始做。」

### 2.6 記錄機器與一致性檢查（Claude 執行；任一失敗即停，回報使用者，**不調參數**）
```bash
cd ~/oran-zt-kpm-verification
(date -u; lscpu; nproc; taskset -cp $$; free -g; ~/venvs/drl/bin/pip freeze) > data/results/d30/drl/machine.txt
cd xapps/verification/adversarial
export ZT_DATASET=d30 ZT_FUSION_ORDER=severity PYTHONWARNINGS=ignore
~/venvs/drl/bin/python check_env.py        # G1–G3（舊機器約 10 分鐘）
~/venvs/drl/bin/python check_speedup.py    # S1–S2
~/venvs/drl/bin/python psro.py --level O-full --train-seed 0 --workers 1 --g4-only   # G4
mv ../../../data/results/d30/drl/psro/O-full/t0 ../../../data/results/d30/drl/psro/O-full/t0_g4only_newmachine
```
注意：`nproc` 於新機器曾回報 14（28 執行緒中可用 14），正式執行之 worker 總數以 `nproc` 與當時另一組實驗之負載為準。

## 3. 正式執行（6 組 PSRO）

- 組合：`--level {O-full, O-outcome}` × `--train-seed {0,1,2}`；一律以 `setsid nohup` 啟動，`PYTHONUNBUFFERED=1`、`nice`。
- 每組 `--workers` 依可用核心分配（例如 12 核 → 每組 2 個 worker，6 組同時）；可中斷續跑（已完成之模型自動跳過）。
- 終止行程時**不要用 `pkill -f <會同時匹配 Bash 指令本身之字串>`**（曾因此殺掉自己之 shell）；以 PID 終止。
- 之後之步驟（規格 §3a）：token 洩漏（最終輪，O-outcome+token）、凍結 vs 線上、Stage 3 評估——各自先寫規格細節再執行。

## 4. 仍在舊機器進行之事

- Stage 3 ns-3 模擬（S3-TM3、S3-U20；3 個實例，預計約 11/16 收齊）。每個 seed 完成後之檢查（`E19_stage3_data_spec.md` §5）在舊機器做，完成後再將 `data/game_stage3/` 複製到新機器供 Stage 3 評估。
