# 如何運行 Cardinality 驗證模組

## ✅ 正確的執行方式

### 從本目錄直接運行

```bash
# 方式 1：運行基礎分析（生成表格數據）
python cardinality.py

# 方式 2：運行視覺化生成（生成 PNG 圖表）
python test_cardinality.py
```

### 從 project root 運行

```bash
cd c:\Users\user\Desktop\thesis\oran-zt-kpm-verification
python 3_xapps/verification/residuals/cardinality.py
python 3_xapps/verification/residuals/test_cardinality.py
```

## ⚠️ 常見問題

### Q: 為什麼 `python3 cardinality.py` 沒有輸出？
**A:** 本系統上 `python3` 命令不可用。請改用 `python` 命令。

### Q: 運行時出現編碼錯誤？
**A:** 已在檔案開頭添加 `# -*- coding: utf-8 -*-` 聲明，應該可以解決。如果問題仍存在，請確保：
- Windows PowerShell 的語言設定為繁體中文或支持 UTF-8
- 或改用 `cmd.exe` 執行

## 📊 輸出說明

### cardinality.py 生成的表格
- **Baseline（乾淨資料）**：原始數據的基準線
- **ε 建議**：自動建議的容忍度參數
- **攻擊 A 灌水**：捏造 UE 的檢測結果
- **攻擊 A 單節點虛減**：單一節點丟棄 UE 的結果
- **攻擊 A 跨節點虛減**：多節點協同虛減的結果

### test_cardinality.py 生成的 PNG
- `cardinality_Ci.png`：三面板視覺化
  - (a) Field-wide UE cardinality N_total(t)
  - (b) Cardinality residual C_i(t)
  - (c) Response curve C_i vs N_total

## 🔍 依賴關係

- **loader.py**：父目錄的前處理模組
- **matplotlib**：用於圖表生成
- **pandas**、**numpy**：數據處理

確保這些依賴已安裝：
```bash
pip install matplotlib pandas numpy
```
