// 碩士論文初稿（NTUST 模板 @preview/ntust-thesis-unofficial:1.3.0）
// 章節檔由 tools/md2typ.py 自 docs/thesis/thesis_v12_2.md（HackMD 正文）與 chapter6_draft.md 產生
// 編譯（於 repo 根目錄）：typst compile --root . --font-path <fonts> thesis_typst/main.typ
#import "@preview/ntust-thesis-unofficial:1.3.0": ntust-thesis
#import "frontpages/names.typ": thesis-info

#show: ntust-thesis.with(
  lang: "zh",
  info: thesis-info,
  abstracts: (
    zh: include "frontpages/abstract.zh.typ",
    en: include "frontpages/abstract.en.typ",
  ),
  acknowledgement: include "frontpages/ackn.typ",
  references: none,                    // 參考文獻沿用正文之手寫清單（sections/references.typ）
  appendix: include "sections/appendix.typ",
  logo: image("logo.png"),
)

#include "sections/ch1.typ"
#include "sections/ch2.typ"
#include "sections/ch3.typ"
#include "sections/ch4.typ"
#include "sections/ch5.typ"
#include "sections/ch6.typ"
#include "sections/references.typ"
