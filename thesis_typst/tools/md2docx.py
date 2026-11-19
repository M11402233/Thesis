#!/usr/bin/env python3
"""thesis_v12_2.md ＋ chapter6_draft.md → Word 初稿（.docx）。與 md2typ.py 讀同一來源、同一章節切分。
格式：標楷體／Times New Roman 12 pt、1.5 倍行距、A4、上下 2.5 cm 左 3 cm 右 2.5 cm（近 NTUST 規定；正式格式以 Typst 版為準）。
數學式以 Unicode 近似呈現（精確版見 Typst PDF）。用法：python3 md2docx.py <repo> <out.docx>"""
import os, re, sys
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_SECTION
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

REPO, OUT = sys.argv[1], sys.argv[2]
SRC = os.path.join(REPO, "docs/thesis/thesis_v12_2.md"); CH6 = os.path.join(REPO, "docs/thesis/chapter6_draft.md")
HACKMD = {"https://hackmd.io/_uploads/S1NP2wItzx.jpg": "thesis_typst/figures/hackmd_S1NP2wItzx.jpg",
          "https://hackmd.io/_uploads/HJZ2XzboGx.png": "thesis_typst/figures/hackmd_HJZ2XzboGx.png"}
CN = "一二三四五六七八九十"
SYM = {r"\rho": "ρ", r"\tau": "τ", r"\sigma": "σ", r"\mu": "μ", r"\lambda": "λ", r"\alpha": "α", r"\beta": "β", r"\delta": "δ",
       r"\Delta": "Δ", r"\epsilon": "ε", r"\varepsilon": "ε", r"\pi": "π", r"\theta": "θ", r"\Sigma": "Σ", r"\sum": "Σ", r"\cdot": "·",
       r"\times": "×", r"\in": "∈", r"\notin": "∉", r"\prec": "≺", r"\le": "≤", r"\leq": "≤", r"\ge": "≥", r"\geq": "≥", r"\approx": "≈",
       r"\neq": "≠", r"\ne": "≠", r"\iff": "⇔", r"\Rightarrow": "⇒", r"\to": "→", r"\rightarrow": "→", r"\infty": "∞", r"\setminus": "∖",
       r"\cup": "∪", r"\cap": "∩", r"\mid": "|", r"\pm": "±", r"\ldots": "…", r"\dots": "…", r"\bar": "", r"\hat": "", r"\lvert": "|", r"\rvert": "|"}


def tex(s):
    s = re.sub(r"\\(text|mathrm|mathbf|mathit|operatorname|mathcal|textbf)\s*\{([^{}]*)\}", r"\2", s)
    for _ in range(3):
        s = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"(\1)/(\2)", s)
    for k in sorted(SYM, key=len, reverse=True):
        s = re.sub(re.escape(k) + r"(?![A-Za-z])", SYM[k], s)
    s = re.sub(r"\\(big|Big|left|right|bigl|bigr)", "", s)
    s = re.sub(r"\\(qquad|quad|,|;|!|:| )", " ", s)
    s = s.replace(r"\{", "{").replace(r"\}", "}").replace(r"\%", "%")
    s = re.sub(r"_\{([^{}]*)\}", r"_\1", s); s = re.sub(r"\^\{([^{}]*)\}", r"^\1", s)
    return re.sub(r"\s+", " ", s).strip()


INLINE = re.compile(r"(?P<code>`[^`]+`)|(?P<math>\$[^$]+\$)|(?P<bold>\*\*(?=\S)(?:.+?)(?<=\S)\*\*)"
                    r"|(?P<link>\[[^\]]+\]\([^)\s]+\))|(?P<it>(?<![\*\w])\*(?=[^\s*])(?:[^*]+?)(?<=[^\s*])\*(?![\*\w]))")


def set_font(r, size=None, mono=False):
    r.font.name = "Consolas" if mono else "Times New Roman"
    rp = r._element.get_or_add_rPr(); rf = rp.find(qn("w:rFonts"))
    if rf is None: rf = OxmlElement("w:rFonts"); rp.append(rf)
    rf.set(qn("w:eastAsia"), "標楷體")
    if size: r.font.size = Pt(size)


def runs(p, s, bold=False, it=False, size=None):
    pos = 0
    for m in INLINE.finditer(s):
        if m.start() > pos: _r(p, s[pos:m.start()], bold, it, size)
        g = m.group(0); pos = m.end()
        if m.group("code"): _r(p, g[1:-1], bold, it, size, mono=True)
        elif m.group("math"): _r(p, tex(g[1:-1]), bold, True, size)
        elif m.group("bold"): runs(p, g[2:-2], True, it, size)
        elif m.group("link"):
            t, u = re.match(r"\[([^\]]+)\]\(([^)\s]+)\)", g).groups(); _r(p, f"{t}（{u}）", bold, it, size)
        else: runs(p, g[1:-1], bold, True, size)
    if pos < len(s): _r(p, s[pos:], bold, it, size)


def _r(p, t, bold, it, size, mono=False):
    r = p.add_run(t); r.bold = bold or None; r.italic = it or None
    set_font(r, (size - 1 if mono and size else (9 if mono else size)), mono)


def shade(p, color="EDEDED"):
    pPr = p._p.get_or_add_pPr(); sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear"); sh.set(qn("w:color"), "auto"); sh.set(qn("w:fill"), color); pPr.append(sh)


def split_row(line):
    line = line.strip().replace("\\|", "\x00").strip("|")
    cells, cur, inb, inm = [], "", False, False
    for ch in line:
        if ch == "`" and not inm: inb = not inb
        elif ch == "$" and not inb: inm = not inm
        if ch == "|" and not inb and not inm: cells.append(cur); cur = ""
        else: cur += ch
    cells.append(cur)
    return [c.strip().replace("\x00", "|") for c in cells]


class W:
    def __init__(self, doc):
        self.d = doc; self.fig = {}; self.chap = 0

    def heading(self, md_level, text, offset):
        m = re.match(r"^(第[一二三四五六七八九十]+章)[\s　]*(.*)$", text)
        if m:
            self.chap += 1
            self.d.add_page_break() if self.chap > 1 else None
            h = self.d.add_heading(level=1); runs(h, f"{m.group(1)}　{m.group(2)}", size=18)
            h.alignment = WD_ALIGN_PARAGRAPH.CENTER; return None
        num = re.match(r"^(\d+(?:\.\d+)+)\s", text)
        if num:
            lv = len(num.group(1).split("."))
            if offset is None: offset = md_level - lv
        else:
            lv = md_level - (offset if offset is not None else md_level - 2)
        lv = max(2, min(4, lv))
        h = self.d.add_heading(level=lv); runs(h, text, size={2: 16, 3: 14, 4: 12}[lv])
        return offset

    def blocks(self, lines, quote=False, offset=None):
        i, n = 0, len(lines)
        while i < n:
            l = lines[i]; s = l.strip()
            if not s or re.match(r"^(-{3,}|\*{3,})$", s): i += 1; continue
            if s.startswith("```"):
                j = i + 1; buf = []
                while j < n and not lines[j].strip().startswith("```"): buf.append(lines[j]); j += 1
                p = self.d.add_paragraph(); shade(p, "F4F4F4"); p.paragraph_format.line_spacing = 1.0
                _r(p, "\n".join(buf), False, False, 8.5, mono=True); i = j + 1; continue
            m = re.match(r"^(#{1,6})\s+(.*)$", s)
            if m: offset = self.heading(len(m.group(1)), m.group(2).strip(), offset); i += 1; continue
            if s.startswith("$$"):
                buf = s[2:]; j = i
                if not (buf.endswith("$$") and len(buf) >= 2):
                    j = i + 1
                    while j < n and "$$" not in lines[j]: buf += " " + lines[j]; j += 1
                    if j < n: buf += " " + lines[j]
                p = self.d.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                _r(p, tex(buf.replace("$$", "")), False, True, 12); i = j + 1; continue
            if s.startswith("|"):
                j = i
                while j < n and lines[j].strip().startswith("|"): j += 1
                rows = [split_row(x) for x in lines[i:j] if not re.match(r"^\s*\|?\s*:?-{2,}", x)]
                k = max(len(r) for r in rows); t = self.d.add_table(rows=len(rows), cols=k); t.style = "Table Grid"
                for a, r in enumerate(rows):
                    for b in range(k):
                        c = t.cell(a, b); p = c.paragraphs[0]; p.paragraph_format.line_spacing = 1.0
                        p.paragraph_format.first_line_indent = Cm(0)
                        runs(p, re.sub(r"<br\s*/?>", " ", r[b] if b < len(r) else ""), bold=(a == 0), size=9)
                self.d.add_paragraph(); i = j; continue
            m = re.match(r"^!\[([^\]]*)\]\((.*)\)\s*$", s)
            if m:
                alt, url = m.groups(); path = HACKMD.get(url)
                mm = re.search(r"(data/results/[\w/.-]+\.png)", url)
                if mm and os.path.exists(os.path.join(REPO, mm.group(1))): path = mm.group(1)
                j = i + 1
                while j < n and not lines[j].strip(): j += 1
                cap = alt
                if j < n and re.match(r"^\*\*(Fig|圖)", lines[j].strip()):
                    cap = re.sub(r"^\*\*(Fig|圖)[^*]*\*\*\s*(（`[^`]*`）)?\s*", "", lines[j].strip()); i = j + 1
                else: i += 1
                self.fig[self.chap] = self.fig.get(self.chap, 0) + 1
                p = self.d.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                if path: p.add_run().add_picture(os.path.join(REPO, path), width=Cm(14))
                else: _r(p, f"【待填：圖檔】{alt}", True, False, 11)
                c = self.d.add_paragraph(); c.alignment = WD_ALIGN_PARAGRAPH.CENTER
                runs(c, f"圖 {self.chap}-{self.fig[self.chap]}　{cap}", size=11); continue
            if s.startswith(">"):
                j = i; buf = []
                while j < n and lines[j].strip().startswith(">"): buf.append(re.sub(r"^\s*>\s?", "", lines[j])); j += 1
                start = len(self.d.paragraphs); self.blocks(buf, True, offset)
                for p in self.d.paragraphs[start:]: shade(p)
                i = j; continue
            if re.match(r"^\s*([-*+]|\d+\.)\s+", l):
                j = i; items = []
                while j < n:
                    mm = re.match(r"^(\s*)([-*+]|\d+\.)\s+(.*)$", lines[j])
                    if mm: items.append([len(mm.group(1).expandtabs(4)), mm.group(2), mm.group(3)]); j += 1
                    elif lines[j].strip() and items and lines[j].startswith(("  ", "\t")) and not lines[j].strip().startswith(("|", ">", "```", "!")):
                        items[-1][2] += " " + lines[j].strip(); j += 1
                    else: break
                lv = sorted({x[0] for x in items})
                for ind, mk, txt in items:
                    p = self.d.add_paragraph(style="List Number" if mk[0].isdigit() else "List Bullet")
                    p.paragraph_format.left_indent = Cm(0.75 * (lv.index(ind) + 1)); p.paragraph_format.first_line_indent = Cm(-0.5)
                    runs(p, txt)
                i = j; continue
            j = i; buf = []
            while j < n and lines[j].strip() and not re.match(r"^\s*(#{1,6}\s|\||>|```|!\[|\$\$|([-*+]|\d+\.)\s)", lines[j]):
                buf.append(lines[j].strip()); j += 1
            if not buf: buf = [s]; j = i + 1
            p = self.d.add_paragraph(); runs(p, " ".join(buf)); i = j
        return offset


def toc(doc):
    p = doc.add_paragraph(); r = p.add_run()
    for t, v in (("begin", None), (None, 'TOC \\o "1-3" \\h \\z \\u'), ("separate", None), ("end", None)):
        if t:
            e = OxmlElement("w:fldChar"); e.set(qn("w:fldCharType"), t); r._r.append(e)
            if t == "separate":
                tt = OxmlElement("w:t"); tt.text = "（開啟後按右鍵「更新功能變數」以產生目錄）"; r._r.append(tt)
        else:
            e = OxmlElement("w:instrText"); e.set(qn("xml:space"), "preserve"); e.text = v; r._r.append(e)


def main():
    d = Document()
    sec = d.sections[0]; sec.page_height, sec.page_width = Cm(29.7), Cm(21.0)
    sec.top_margin = sec.bottom_margin = Cm(2.5); sec.left_margin = Cm(3.0); sec.right_margin = Cm(2.5)
    st = d.styles["Normal"]; st.font.name = "Times New Roman"; st.font.size = Pt(12)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "標楷體")
    st.paragraph_format.line_spacing = 1.5; st.paragraph_format.first_line_indent = Cm(0.85)
    for k in range(1, 5):
        h = d.styles[f"Heading {k}"]; h.font.color.rgb = RGBColor(0, 0, 0); h.font.name = "Times New Roman"
        h.element.get_or_add_rPr(); rf = h.element.rPr.find(qn("w:rFonts"))
        if rf is None: rf = OxmlElement("w:rFonts"); h.element.rPr.append(rf)
        rf.set(qn("w:eastAsia"), "標楷體"); h.paragraph_format.first_line_indent = Cm(0)
    # 封面
    for t, sz in (("國立臺灣科技大學", 20), ("電子工程系", 18), ("碩士學位論文", 18), ("", 12),
                  ("非公眾網路 O-RAN 邊緣節點的零信任 E2 量測資料可信度驗證：以跨節點空間物理一致性對抗 KPM 偽造", 16),
                  ("Zero-Trust Verification and Admission of KPM Reports in Non-Public O-RAN: Countering Falsification by Authenticated Nodes with Field-Referenced Consistency Evidence", 14),
                  ("", 12), ("研究生：王芊瑜（M11402233）", 14), ("指導教授：王瑞堂 博士", 14), ("", 12), ("中華民國 116 年 6 月", 14)):
        p = d.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.first_line_indent = Cm(0)
        if t: r = p.add_run(t); set_font(r, sz); r.bold = sz >= 16
    w = W(d)
    for title, f in (("摘要", "abstract.zh.typ"), ("ABSTRACT", "abstract.en.typ"), ("誌謝", "ackn.typ")):
        d.add_page_break(); h = d.add_heading(level=1); runs(h, title, size=18); h.alignment = WD_ALIGN_PARAGRAPH.CENTER
        txt = open(os.path.join(REPO, "thesis_typst/frontpages", f)).read()
        txt = "\n".join(x for x in txt.split("\n") if not x.startswith("#block("))
        txt = re.sub(r"#v\([^)]*\)", "", txt).replace("#text(weight: \"bold\")[關鍵字：]", "**關鍵字：**").replace("*Keywords:*", "**Keywords:**")
        txt = re.sub(r"#align\(right\)\[([^\]]*)\]", r"\1", txt)
        d.add_paragraph("【初稿，由 Claude 依正文 v12.2 第一章摘寫，未列數字；請依最終結果改寫】" if f != "ackn.typ" else "")
        w.blocks(txt.split("\n"))
    d.add_page_break(); h = d.add_heading(level=1); runs(h, "目錄", size=18); h.alignment = WD_ALIGN_PARAGRAPH.CENTER; toc(d)
    L = open(SRC, encoding="utf-8").read().replace("\r", "").split("\n")
    idx = {}
    for k, l in enumerate(L):
        m = re.match(r"^##\s+(第[一二三四五六七八九十]+章|圖目錄|程式碼目錄|參考文獻|附錄 A)", l)
        if m: idx.setdefault(m.group(1), k)
    order = ["第一章", "第二章", "第三章", "第四章", "第五章", "圖目錄", "程式碼目錄", "參考文獻", "附錄 A"]
    pos = [idx[o] for o in order] + [len(L)]; seg = {o: L[pos[i]:pos[i + 1]] for i, o in enumerate(order)}
    d.add_page_break()
    note = [l for l in L[1:idx["第一章"]] if l.strip() and not l.startswith("## code")]
    for o in ["第一章", "第二章", "第三章", "第四章", "第五章"]:
        w.blocks(seg[o][:1])
        if o == "第一章":
            p = d.add_paragraph(); runs(p, "**初稿說明（自 HackMD 正文 v12.2 轉出）**", size=10); shade(p, "E3E3E3")
            s0 = len(d.paragraphs); w.blocks([re.sub(r"^>\s?", "", x) for x in note])
            for p in d.paragraphs[s0:]: shade(p, "E3E3E3")
        w.blocks(seg[o][1:])
    c6 = open(CH6, encoding="utf-8").read().replace("\r", "").split("\n"); c6[0] = re.sub(r"^#\s+", "## ", c6[0])
    w.blocks(c6)
    d.add_page_break(); h = d.add_heading(level=1); runs(h, "參考文獻", size=18); h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    w.blocks(seg["參考文獻"][1:], offset=0)
    d.add_page_break(); h = d.add_heading(level=1); runs(h, "附錄", size=18); h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    w.chap = 0
    w.blocks(seg["附錄 A"] + ["", "## 附錄 B：程式碼目錄"] + seg["程式碼目錄"][1:], offset=0)
    for sct in d.sections:
        fp = sct.footer.paragraphs[0]; fp.alignment = WD_ALIGN_PARAGRAPH.CENTER; r = fp.add_run()
        for t in ("begin", "PAGE", "end"):
            if t == "PAGE":
                e = OxmlElement("w:instrText"); e.text = "PAGE"; r._r.append(e)
            else:
                e = OxmlElement("w:fldChar"); e.set(qn("w:fldCharType"), t); r._r.append(e)
    d.save(OUT); print("saved", OUT)


if __name__ == "__main__":
    main()
