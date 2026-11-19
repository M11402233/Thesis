# 碩論初稿（NTUST Typst 模板 ＋ Word 版）

來源：`docs/thesis/thesis_v12_3.md`（HackMD 正文）＋ `docs/thesis/chapter6_v12_3.md`。正文改了就重跑轉換，不要直接改 `sections/*.typ`（會被覆蓋）。

```bash
# 1. Typst（NTUST 模板 @preview/ntust-thesis-unofficial:1.3.0；需 typst ≥ 0.14、字型 Liberation Serif ＋ TW-MOE-Std-Kai）
python3 thesis_typst/tools/md2typ.py . thesis_typst/sections
typst compile --root . --font-path <字型目錄> thesis_typst/main.typ thesis.pdf
# 2. Word（python-docx；格式近 NTUST 規定，數學式為 Unicode 近似）
python3 thesis_typst/tools/md2docx.py . thesis.docx
```

- 校徽 `logo.png` 不入 repo（授權不明），下載方式見模板 README。
- 封面資料在 `frontpages/names.typ`；【待填】：指導教授英文姓名、誌謝（系所＝電子工程系、口試＝民國 116 年 6 月已填；系所英文名為推測）。摘要為 Claude 依第一章所寫之草稿。
- 第五章尚未依 2026-11-19 會議決定（`meeting_minutes_advisor_20261119.md`）改寫。
