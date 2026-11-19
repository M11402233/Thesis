#!/usr/bin/env python3
"""thesis_v12_3.md（HackMD 正文）＋ chapter6_v12_3.md → NTUST Typst 模板之章節檔。
用法：python3 md2typ.py <repo> <out_dir>
- 第 X 章 → 一級標題（模板自動編「第X章」）；其餘標題保留原文編號（4.7.4 等）、不另編號，使正文交叉引用仍正確
- LaTeX 數學以 @preview/mitex 呈現（#mi／#mitex）
- 圖：HackMD 連結改用本機檔（data/results/d30/*.png）或下載之 HackMD 圖；缺檔者以待填方框
"""
import os, re, sys

REPO, OUT = sys.argv[1], sys.argv[2]
SRC = os.path.join(REPO, "docs/thesis/thesis_v12_3.md")
CH6 = os.path.join(REPO, "docs/thesis/chapter6_v12_3.md")
HACKMD = {"https://hackmd.io/_uploads/S1NP2wItzx.jpg": "/thesis_typst/figures/hackmd_S1NP2wItzx.jpg",
          "https://hackmd.io/_uploads/HJZ2XzboGx.png": "/thesis_typst/figures/hackmd_HJZ2XzboGx.png"}

ESC = set('\\#$*_`@<>[]~/=-+')


def esc(t):
    return "".join("\\" + c if c in ESC else c for c in t)


def tstr(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


INLINE = re.compile(r"(?P<code>`[^`]+`)|(?P<math>\$[^$]+\$)|(?P<bold>\*\*(?=\S)(?:.+?)(?<=\S)\*\*)"
                    r"|(?P<link>\[[^\]]+\]\([^)\s]+\))|(?P<it>(?<![\*\w])\*(?=[^\s*])(?:[^*]+?)(?<=[^\s*])\*(?![\*\w]))")


def inline(s):
    out, pos = [], 0
    for m in INLINE.finditer(s):
        out.append(esc(s[pos:m.start()])); pos = m.end(); g = m.group(0)
        if m.group("code"):
            out.append("#raw(" + tstr(g[1:-1]) + ")")
        elif m.group("math"):
            out.append("#mi(" + tstr(g[1:-1]) + ")")
        elif m.group("bold"):
            out.append("#strong[" + inline(g[2:-2]) + "]")
        elif m.group("link"):
            t, u = re.match(r"\[([^\]]+)\]\(([^)\s]+)\)", g).groups()
            out.append("#link(" + tstr(u) + ")[" + inline(t) + "]")
        else:
            out.append("#emph[" + inline(g[1:-1]) + "]")
    out.append(esc(s[pos:]))
    return "".join(out)


def split_row(line):
    line = line.strip().replace("\\|", "\x00")
    if line.startswith("|"): line = line[1:]
    if line.endswith("|"): line = line[:-1]
    cells, cur, inb, inm = [], "", False, False
    for ch in line:
        if ch == "`" and not inm: inb = not inb
        elif ch == "$" and not inb: inm = not inm
        if ch == "|" and not inb and not inm:
            cells.append(cur); cur = ""
        else:
            cur += ch
    cells.append(cur)
    return [c.strip().replace("\x00", "|") for c in cells]


def table(lines):
    rows = [split_row(l) for l in lines if not re.match(r"^\s*\|?\s*:?-{2,}", l)]
    n = max(len(r) for r in rows)
    rows = [r + [""] * (n - len(r)) for r in rows]
    cell = lambda c: "[" + inline(re.sub(r"<br\s*/?>", " ", c)) + "]"
    head = "table.header(" + ", ".join(cell(c) for c in rows[0]) + ")"
    body = ",\n  ".join(", ".join(cell(c) for c in r) for r in rows[1:])
    return (f"#block(width: 100%)[#set text(size: 9pt)\n#set par(first-line-indent: 0pt, justify: false)\n"
            f"#table(columns: {n}, inset: 4pt, align: left, stroke: 0.5pt,\n  {head},\n  {body})]\n")


def image(alt, url, caption):
    path = HACKMD.get(url)
    m = re.search(r"(data/results/[\w/.-]+\.png)", url)
    if m and os.path.exists(os.path.join(REPO, m.group(1))):
        path = "/" + m.group(1)
    cap = inline(caption) if caption else inline(alt)
    if path:
        return f"#figure(image({tstr(path)}, width: 90%), caption: [{cap}])\n"
    return (f"#figure(rect(width: 80%, height: 4cm, stroke: (dash: \"dashed\"))[#align(center + horizon)[【待填：圖檔】 {inline(alt)}]],"
            f" caption: [{cap}])\n")


class Conv:
    def __init__(self):
        self.offset = 1

    def heading(self, md_level, text):
        text = text.strip()
        m = re.match(r"^(第[一二三四五六七八九十]+章)[\s　]*(.*)$", text)
        if m:
            self.offset = None
            return f"= {inline(m.group(2))}\n"
        num = re.match(r"^(\d+(?:\.\d+)+)\s", text)
        if num:
            lv = len(num.group(1).split("."))
            if self.offset is None:
                self.offset = md_level - lv
        else:
            lv = md_level - (self.offset if self.offset is not None else md_level - 2)
        lv = max(2, min(5, lv))
        return f"#heading(level: {lv}, numbering: none)[{inline(text)}]\n"

    def blocks(self, lines):
        out, i, n = [], 0, len(lines)
        while i < n:
            l = lines[i]
            s = l.strip()
            if not s or re.match(r"^(-{3,}|\*{3,})$", s):
                i += 1; continue
            if s.startswith("```"):
                lang = s[3:].strip(); j = i + 1; buf = []
                while j < n and not lines[j].strip().startswith("```"):
                    buf.append(lines[j]); j += 1
                body = "\n".join(buf)
                out.append(f"#block(width: 100%, fill: luma(245), inset: 6pt)[#set text(size: 8.5pt)\n#raw({tstr(body)}, block: true{', lang: ' + tstr(lang) if lang else ''})]\n")
                i = j + 1; continue
            m = re.match(r"^(#{1,6})\s+(.*)$", s)
            if m:
                out.append(self.heading(len(m.group(1)), m.group(2))); i += 1; continue
            if s.startswith("$$"):
                buf = s[2:]
                if buf.endswith("$$") and len(buf) >= 2:
                    buf = buf[:-2]; j = i
                else:
                    j = i + 1
                    while j < n and "$$" not in lines[j]:
                        buf += "\n" + lines[j]; j += 1
                    if j < n: buf += "\n" + lines[j].replace("$$", "")
                out.append(f"#mitex({tstr(buf.strip())})\n"); i = j + 1; continue
            if s.startswith("|"):
                j = i
                while j < n and lines[j].strip().startswith("|"): j += 1
                out.append(table(lines[i:j])); i = j; continue
            m = re.match(r"^!\[([^\]]*)\]\((.*)\)\s*$", s)
            if m:
                j = i + 1
                while j < n and not lines[j].strip(): j += 1
                cap = None
                if j < n and re.match(r"^\*\*(Fig|圖)", lines[j].strip()):
                    cap = re.sub(r"^\*\*(Fig|圖)[^*]*\*\*\s*(（`[^`]*`）)?\s*", "", lines[j].strip()); i = j + 1
                else:
                    i += 1
                out.append(image(m.group(1), m.group(2), cap)); continue
            if s.startswith(">"):
                j = i; buf = []
                while j < n and lines[j].strip().startswith(">"):
                    buf.append(re.sub(r"^\s*>\s?", "", lines[j])); j += 1
                inner = "".join(self.blocks(buf))
                out.append(f"#block(width: 100%, fill: luma(240), inset: 8pt, radius: 2pt)[#set text(size: 10pt)\n{inner}]\n"); i = j; continue
            if re.match(r"^\s*([-*+]|\d+\.)\s+", l):
                j = i; items = []
                while j < n:
                    lj = lines[j]
                    mm = re.match(r"^(\s*)([-*+]|\d+\.)\s+(.*)$", lj)
                    if mm:
                        items.append([len(mm.group(1).expandtabs(4)), mm.group(2), mm.group(3)]); j += 1
                    elif lj.strip() and items and (lj.startswith("  ") or lj.startswith("\t")) and not lj.strip().startswith(("|", ">", "```", "!")):
                        items[-1][2] += " " + lj.strip(); j += 1
                    else:
                        break
                levels = sorted({it[0] for it in items})
                for ind, mk, txt in items:
                    lv = levels.index(ind)
                    marker = "+" if mk[0].isdigit() else "-"
                    out.append("  " * lv + f"{marker} {inline(txt)}\n")
                out.append("\n"); i = j; continue
            j = i; buf = []
            while j < n and lines[j].strip() and not re.match(r"^\s*(#{1,6}\s|\||>|```|!\[|\$\$|([-*+]|\d+\.)\s)", lines[j]):
                buf.append(lines[j].strip()); j += 1
            if not buf:
                buf = [lines[i].strip()]; j = i + 1
            out.append(inline(" ".join(buf)) + "\n\n"); i = j
        return out


def main():
    os.makedirs(OUT, exist_ok=True)
    L = open(SRC, encoding="utf-8").read().replace("\r", "").split("\n")
    idx = {}
    for k, l in enumerate(L):
        m = re.match(r"^##\s+(第[一二三四五六七八九十]+章|圖目錄|程式碼目錄|參考文獻|附錄 A)", l)
        if m: idx.setdefault(m.group(1), k)
    order = ["第一章", "第二章", "第三章", "第四章", "第五章", "圖目錄", "程式碼目錄", "參考文獻", "附錄 A"]
    pos = [idx[o] for o in order] + [len(L)]
    seg = {o: L[pos[i]:pos[i + 1]] for i, o in enumerate(order)}
    pre = L[:idx["第一章"]]
    head = ["#import \"@preview/mitex:0.2.7\": mi, mitex\n"]
    # 前置說明（版本、資料狀態、程式庫連結）→ 第一章之前之灰框
    note = [l for l in pre[1:] if not l.startswith("## code")]
    for n_, (o, fn) in enumerate([("第一章", "ch1"), ("第二章", "ch2"), ("第三章", "ch3"), ("第四章", "ch4"), ("第五章", "ch5")]):
        c = Conv(); body = c.blocks(seg[o])
        if o == "第一章":
            prebox = c.blocks([">" + l for l in note if l.strip()])
            body = body[:1] + ["#block(width: 100%, fill: luma(235), inset: 8pt)[#set text(size: 9.5pt)\n#strong[初稿說明（自 HackMD 正文 v12.3 轉出）]\n\n"] + [x[x.index(']\n') + 2:-2] if x.startswith('#block') else x for x in prebox] + ["]\n"] + body[1:]
        open(os.path.join(OUT, f"{fn}.typ"), "w").write("".join(head + body))
    c6 = open(CH6, encoding="utf-8").read().replace("\r", "").split("\n")
    c6[0] = re.sub(r"^#\s+", "## ", c6[0])
    open(os.path.join(OUT, "ch6.typ"), "w").write("".join(head + Conv().blocks(c6)))
    ref = seg["參考文獻"][1:]
    open(os.path.join(OUT, "references.typ"), "w").write("".join(head + ["#heading(level: 1, numbering: none)[參考文獻]\n#set par(first-line-indent: 0pt)\n"] + Conv().blocks(ref)))
    app = ["## 附錄 A" + seg["附錄 A"][0][len("## 附錄 A"):]] + seg["附錄 A"][1:] + ["", "## 附錄 B：程式碼目錄"] + seg["程式碼目錄"][1:]
    c = Conv(); c.offset = 0
    ab = [x.replace("level: 2, numbering: none)[附錄", "level: 1, numbering: none)[附錄") for x in c.blocks(app)]
    open(os.path.join(OUT, "appendix.typ"), "w").write("".join(head + ab))
    print("written:", sorted(os.listdir(OUT)))


if __name__ == "__main__":
    main()
