import re, sys
from xml.sax.saxutils import escape as esc
U = sys.argv[1] + '/ppt'
EMU = 914400
def E(v): return int(round(v * EMU))
NAVY, TEAL, RED, GOLD, GRAY, TXT, LIGHT, BORDER = '0B2545','0FB5AE','C0392B','C9A227','5A6B7D','16202E','F5F8FC','D5E0EC'
FONT = '<a:latin typeface="Calibri" pitchFamily="34" charset="0"/><a:ea typeface="Calibri" pitchFamily="34" charset="-122"/><a:cs typeface="Calibri" pitchFamily="34" charset="-120"/>'
_id = [100]
def nid():
    _id[0] += 1; return _id[0]
def run(t, sz=1200, color=TXT, b=False, i=False):
    bb = ' b="1"' if b else ''
    ii = ' i="1"' if i else ''
    return (f'<a:r><a:rPr lang="en-US" sz="{sz}"{bb}{ii} dirty="0">'
            f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill>{FONT}</a:rPr><a:t>{esc(t)}</a:t></a:r>')
def para(runs, algn='l', spc_after=0):
    sa = f'<a:spcAft><a:spcPts val="{spc_after}"/></a:spcAft>' if spc_after else ''
    return f'<a:p><a:pPr marL="0" indent="0" algn="{algn}">{sa}<a:buNone/></a:pPr>{"".join(runs)}</a:p>'
def textbox(x, y, w, h, paras, anchor='t', name='Text'):
    i = nid()
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="{name} {i}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
            f'<p:spPr><a:xfrm><a:off x="{E(x)}" y="{E(y)}"/><a:ext cx="{E(w)}" cy="{E(h)}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>'
            f'<p:txBody><a:bodyPr wrap="square" lIns="0" tIns="0" rIns="0" bIns="0" rtlCol="0" anchor="{anchor}"><a:normAutofit/></a:bodyPr><a:lstStyle/>{"".join(paras)}</p:txBody></p:sp>')
def rect(x, y, w, h, fill, name='Card'):
    i = nid()
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="{name} {i}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
            f'<p:spPr><a:xfrm><a:off x="{E(x)}" y="{E(y)}"/><a:ext cx="{E(w)}" cy="{E(h)}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
            f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill><a:ln><a:noFill/></a:ln></p:spPr>'
            f'<p:txBody><a:bodyPr rtlCol="0" anchor="ctr"/><a:lstStyle/><a:p><a:endParaRPr lang="en-US" dirty="0"/></a:p></p:txBody></p:sp>')
def card(x, y, w, h, accent, paras):
    return rect(x, y, w, h, LIGHT) + rect(x, y, 0.1, h, accent, 'Accent') + textbox(x + 0.3, y + 0.12, w - 0.45, h - 0.24, paras, 'ctr')
LN = ''.join(f'<a:{s} w="12700" cap="flat" cmpd="sng" algn="ctr"><a:solidFill><a:srgbClr val="{BORDER}"/></a:solidFill><a:prstDash val="solid"/><a:round/><a:headEnd type="none" w="med" len="med"/><a:tailEnd type="none" w="med" len="med"/></a:{s}>' for s in ('lnL','lnR','lnT','lnB'))
def cell(t, header=False, algn='l', fill=None, sz=1200, color=None, b=None, i=False):
    fill = fill or (NAVY if header else 'FFFFFF')
    color = color or ('FFFFFF' if header else TXT)
    b = header if b is None else b
    lines = t.split('\n')
    ps = ''.join(f'<a:p><a:pPr marL="0" indent="0" algn="{algn}"><a:buNone/></a:pPr>{run(l, sz, color, b, i)}</a:p>' for l in lines)
    return (f'<a:tc><a:txBody><a:bodyPr/><a:lstStyle/>{ps}</a:txBody>'
            f'<a:tcPr marL="64008" marR="64008" marT="36576" marB="36576" anchor="ctr">{LN}<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill></a:tcPr></a:tc>')
def table(x, y, colw, rows, rowh):
    """rows: list of (list_of_cell_xml, height_in)"""
    i = nid()
    grid = ''.join(f'<a:gridCol w="{E(c)}"/>' for c in colw)
    trs = ''.join(f'<a:tr h="{E(h)}">{"".join(cs)}</a:tr>' for cs, h in rows)
    H = sum(h for _, h in rows)
    return (f'<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="{i}" name="Table {i}"/><p:cNvGraphicFramePr><a:graphicFrameLocks noGrp="1"/></p:cNvGraphicFramePr><p:nvPr/></p:nvGraphicFramePr>'
            f'<p:xfrm><a:off x="{E(x)}" y="{E(y)}"/><a:ext cx="{E(sum(colw))}" cy="{E(H)}"/></p:xfrm><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table">'
            f'<a:tbl><a:tblPr firstRow="1" bandRow="0"/><a:tblGrid>{grid}</a:tblGrid>{trs}</a:tbl></a:graphicData></a:graphic></p:graphicFrame>')

def make_slide(src, section, title, body):
    x = open(src).read()
    x = x.replace('<a:t>DATA   styled table</a:t>', f'<a:t>{esc(section)}</a:t>').replace('<a:t>Table style</a:t>', f'<a:t>{esc(title)}</a:t>')
    # drop template's empty text box and table; keep placeholders (section, title, slide number)
    x = re.sub(r'<p:sp><p:nvSpPr><p:cNvPr id="4" name="Text 2"/>.*?</p:sp>', '', x, count=1, flags=re.S)
    x = re.sub(r'<p:graphicFrame>.*?</p:graphicFrame>', '', x, count=1, flags=re.S)
    x = x.replace('</p:spTree>', body + '</p:spTree>')
    return x

SEC = 'SECTION Proposed Approach · D. Learn'
TBD = 'FFF6DA'
# ---------- slide97: attack generators ----------

# ======================= v1.18 (2026-11-19): p.51–59 de-duplicated; P1 workflow in Part 3 =======================
import os
S = f'{U}/slides'; N = f'{U}/notesSlides'
NEW = 'E6F7F6'; OKF, RUNF = 'E6F4EA', 'FFF6DA'
_tc = {}
def notes_xml(tmpl, paras):
    x = _tc.setdefault(tmpl, open(tmpl).read())
    i = x.find('<p:ph type="body"'); j = x.find('<p:txBody>', i); k = x.find('</p:txBody>', j)
    body = '<p:txBody><a:bodyPr/><a:lstStyle/>' + ''.join(
        f'<a:p><a:r><a:rPr lang="{"zh-TW" if any(ord(ch) > 0x2E80 for ch in p) else "en-US"}" dirty="0"/><a:t>{esc(p)}</a:t></a:r></a:p>' for p in paras) + '</p:txBody>'
    return x[:j] + body + x[k + len('</p:txBody>'):]
def notes_of(sl):
    return re.search(r'notesSlide\d+\.xml', open(f'{S}/_rels/{sl}.xml.rels').read()).group(0)
def append_notes(sl, paras):
    f = f'{N}/{notes_of(sl)}'; x = open(f).read()
    k = x.rfind('</p:txBody>')
    add = ''.join(f'<a:p><a:r><a:rPr lang="{"zh-TW" if any(ord(ch) > 0x2E80 for ch in p) else "en-US"}" dirty="0"/><a:t>{esc(p)}</a:t></a:r></a:p>' for p in paras)
    open(f, 'w').write(x[:k] + add + x[k:])
def sub_once(path, old, new):
    x = open(path).read()
    if old not in x: raise SystemExit(f'not found in {os.path.basename(path)}: {old[:60]}')
    open(path, 'w').write(x.replace(old, new))
def bullets(items, sz=1150):
    """items: list of list-of-(text, color, bold)"""
    out = []
    for it in items:
        rs = ''.join(run(t, sz, c, b) for t, c, b in it)
        out.append(f'<a:p><a:pPr marL="228600" indent="-228600"><a:buFont typeface="Arial"/><a:buChar char="•"/><a:spcAft><a:spcPts val="300"/></a:spcAft></a:pPr>{rs}</a:p>')
    return out
def accent_card(x, y, w, h, title, items, accent=TEAL, sz=1150):
    ps = ([para([run(title, 1300, NAVY, True)], spc_after=300)] if title else []) + bullets(items, sz)
    return rect(x, y, w, h, LIGHT) + rect(x, y, 0.08, h, accent, 'Accent') + textbox(x + 0.28, y + 0.12, w - 0.42, h - 0.24, ps, 't')
def pic(rid, x, y, w, h):
    i = nid()
    return (f'<p:pic><p:nvPicPr><p:cNvPr id="{i}" name="Picture {i}" descr="Field topology: 7 gNBs and 1 LTE anchor, 30 UEs"/><p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr>'
            f'<p:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>'
            f'<p:spPr><a:xfrm><a:off x="{E(x)}" y="{E(y)}"/><a:ext cx="{E(w)}" cy="{E(h)}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:ln w="9525"><a:solidFill><a:srgbClr val="{BORDER}"/></a:solidFill></a:ln></p:spPr></p:pic>')
R_, B_ = RED, True

# ---------- (1) p.51 + p.59 merged → slide53 (One Dataset for Every Check) ----------
_id[0] = 100
rels = open(f'{S}/_rels/slide53.xml.rels').read()
if 'image6.png' not in rels:
    rels = rels.replace('</Relationships>', '<Relationship Id="rId9" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image6.png"/></Relationships>')
    open(f'{S}/_rels/slide53.xml.rels', 'w').write(rels)
body = pic('rId9', 0.6, 1.6, 4.5, 4.5 * 2398 / 3080)
hd = [cell('', True, sz=1050), cell('D-30 (results so far)', True, sz=1050), cell('D-30P (phase 2)', True, sz=1050), cell('Earlier (appendix)', True, sz=1050)]
rows = [(hd, 0.32)] + [([cell(a, b=True, sz=1050), cell(b, sz=1050), cell(c, sz=1050, fill=NEW), cell(d, sz=1050, color=GRAY)], 0.3) for a, b, c, d in [
    ('Independent runs', '8', '8 (same seeds)', '10 and 4'),
    ('Windows analysed', '2,400 (0–299 s)', '2,400 (0–299 s)', '600 and 1,200'),
    ('Per-cell counters', 'no', 'yes', 'no'),
    ('Status', 'pre-correction where labelled', 'collecting · replaces every number', '7 UEs · superseded')]]
body += table(5.4, 1.6, [1.75, 1.95, 1.95, 1.68], rows, None)
body += textbox(5.4, 3.55, 7.33, 0.5, [para([run('Field: ', 1100, NAVY, True), run('7 gNBs + 1 LTE anchor (the node the attacker cannot control) · MR-DC · 3.5 GHz / 20 MHz · ISD 1000 m · 30 UEs at 3–10 m/s · 1 s windows', 1100)])])
body += accent_card(5.4, 4.15, 7.33, 2.0, 'Why a single dataset', [
    [('All checks, the fusion rules and the resource evaluation use ', TXT, False), ('the same 30-UE trajectories', R_, B_), (', so results compare directly', TXT, False)],
    [('Thresholds were fixed on the earlier 7-UE data; ', TXT, False), ('this dataset chose no threshold', R_, B_)],
    [('D-30P re-runs the same command line with per-cell counters, so ', TXT, False), ('its old fields are bit-identical to D-30', R_, B_)],
    [('Cost: ', R_, B_), ('Population Check runs drop from 10 to 8 (windows rise from 600 to 2,400)', TXT, False)]], sz=1100)
open(f'{S}/slide53.xml', 'w').write(make_slide(f'{S}/slide94.xml', 'SECTION Analysis', 'One Dataset for Every Check', body))
append_notes('slide53', [
 '【v1.18 addition】The field picture from the old “Field Behind Every Number” page is now here. Phase 2 re-collects the same eight runs as D-30P, with per-cell counters; its old fields match D-30 bit for bit, and every number in this chapter will be replaced from it.',
 '【v1.18 補充】原本「Field Behind Every Number」那頁的場域圖移到這裡。第二階段把同樣八個 run 重收成 D-30P，多了逐 cell 計數器；舊欄位與 D-30 逐位相同，本章所有數字之後都會改用它。'])

# ---------- (2) p.52 rebuilt (From Observation to Check) + granularity + complementarity ----------
_id[0] = 100
hd = [cell(h, True, sz=1050) for h in ('Observed to be stable', 'Measured in clean data (D-30)', 'So we can ask', 'Check', 'Granularity')]
rws = [('Distinct UE count in the field', 'always 30 in 2,400 windows (8 runs); zero counterexamples', 'Does the count equal N_known?', 'Population C_i', 'field'),
       ('Delay agreement across cells', 'median CV 0.275 across cells in the same window (interval delay)', 'Do peers support this reading?', 'Peer S_i', 'per cell'),
       ('UE presence and serving cell', '0 serving-cell changes in 240 UE-runs (2,400 windows)', 'Is this dwell / transition consistent?', 'Mobility H_i', 'per UE')]
rows = [(hd, 0.34)] + [([cell(a, sz=1050), cell(b, sz=1050, color=RED, b=True), cell(c, sz=1050), cell(d, sz=1050, b=True), cell(e, sz=1050, algn='ctr')], 0.5) for a, b, c, d, e in rws]
body = table(0.6, 1.45, [2.45, 3.6, 2.75, 1.68, 1.65], rows, None)
body += accent_card(0.6, 3.55, 5.95, 1.85, 'Throughput fails the same test', [
    [('Per-window throughput is more spread still (cross-cell CV 0.63 vs 0.275 for delay)', TXT, False)],
    [('Native PRB is collected but used only for resource evaluation, not as verification evidence', TXT, False)],
    [('Pure throughput falsification is declared ', TXT, False), ('out of coverage, not overlooked', R_, B_)]], sz=1100)
body += accent_card(6.78, 3.55, 5.95, 1.85, 'One annotation per (node, window)', [
    [('Each check reads one synchronized 1 s field-window plus frozen baselines; the three answers are fused into ', TXT, False), ('one trust annotation per (node, window)', R_, B_)],
    [('Complementary, not statistically independent: ', R_, B_), ('Population and Mobility both depend on UE identity and cell reporting; a missing anchor report degrades both', TXT, False)]], accent=GOLD, sz=1100)
open(f'{S}/slide48.xml', 'w').write(make_slide(f'{S}/slide94.xml', 'SECTION Analysis', 'From Observation to Check', body))
append_notes('slide48', [
 '【v1.18 addition】Two points from removed pages are here now: the granularity column — field, per cell, per UE — and the caveat that the checks are complementary but not statistically independent.',
 '【v1.18 補充】刪除頁面的兩個重點移到這裡：粒度欄（全場、每 cell、每 UE），以及三項檢查互補但不是統計獨立。'])

# ---------- (3) p.54 restyled (Phase 2) ----------
_id[0] = 100
st = [cell(h, True, sz=1100) for h in ('Step', 'What', 'Status')]
rows = [(st, 0.34)] + [([cell(a, b=True, sz=1050), cell(b, sz=1050), cell(c, sz=1050, fill=f, color=(RED if f == RUNF else TXT), b=(f == RUNF))], h) for a, b, c, f, h in [
 ('D-30P data', 're-collect D-30 with per-cell counters (r9): 8 seeds × 301 s, same command line', 'running · checks ≈ Nov 20 morning', RUNF, 0.4),
 ('Build check', 'first batch (GCC 11) changed only SINR last digits in one trace → diagnosis only; rebuilt with GCC 13', 'gate passed', OKF, 0.46),
 ('Input layer', 'per-cell interval delay, zero-delay samples, RRC lists, serving cell', '3 checks pass · 8 / 8 diagnostic seeds', OKF, 0.4),
 ('Population rule', 'LTE anchor lists all 30 UEs → anchor is the reference set; mmWave union must equal it', 'decided Nov 19', OKF, 0.46),
 ('Steps 1–5', 'population, peer, mobility, fusion, admission, resource evaluation on D-30P', '≈ Nov 22', 'FFFFFF', 0.4),
 ('Step 7', 'full PSRO: 9 detectors, 432 attacker best responses → Rule + DRL, Chart 2', '≈ Nov 26–28', 'FFFFFF', 0.4)]]
body = table(0.6, 1.45, [1.75, 7.25, 3.13], rows, None)
body += accent_card(0.6, 4.4, 12.13, 0.95, None, [
    [('Every number marked “pre-correction” is replaced from D-30P.', R_, B_)],
    [('Until then, phase-1 numbers (interval delay on the old data) appear only where labelled; dates are estimates from the current simulation speed.', TXT, False)]], sz=1150)
open(f'{S}/slide101.xml', 'w').write(make_slide(f'{S}/slide94.xml', 'SECTION Analysis', 'Phase 2: Rebuilding the Data, Then Every Number', body))

# ---------- (4) new slide102: P1 workflow (Part 3, after slide34) ----------
_id[0] = 100
def box(x, y, w, h, lines, fill='FFFFFF', line=NAVY, prst='roundRect', sz=1000, color=TXT, bold_first=False, name='Step'):
    i = nid()
    ps = ''.join(f'<a:p><a:pPr algn="ctr"/>{run(l, sz, color, bold_first and k == 0)}</a:p>' for k, l in enumerate(lines))
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="{name} {i}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
            f'<p:spPr><a:xfrm><a:off x="{E(x)}" y="{E(y)}"/><a:ext cx="{E(w)}" cy="{E(h)}"/></a:xfrm><a:prstGeom prst="{prst}"><a:avLst/></a:prstGeom>'
            f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill><a:ln w="12700"><a:solidFill><a:srgbClr val="{line}"/></a:solidFill></a:ln></p:spPr>'
            f'<p:txBody><a:bodyPr wrap="square" lIns="45720" tIns="18288" rIns="45720" bIns="18288" anchor="ctr"><a:normAutofit/></a:bodyPr><a:lstStyle/>{ps}</p:txBody></p:sp>')
def arrow(x1, y1, x2, y2, color=GRAY, dash=False, label=None, lx=0, ly=0):
    i = nid()
    fh = ' flipH="1"' if x2 < x1 else ''; fv = ' flipV="1"' if y2 < y1 else ''
    d = '<a:prstDash val="dash"/>' if dash else ''
    s = (f'<p:cxnSp><p:nvCxnSpPr><p:cNvPr id="{i}" name="Arrow {i}"/><p:cNvCxnSpPr/><p:nvPr/></p:nvCxnSpPr>'
         f'<p:spPr><a:xfrm{fh}{fv}><a:off x="{E(min(x1, x2))}" y="{E(min(y1, y2))}"/><a:ext cx="{E(abs(x2 - x1))}" cy="{E(abs(y2 - y1))}"/></a:xfrm>'
         f'<a:prstGeom prst="straightConnector1"><a:avLst/></a:prstGeom><a:ln w="15875"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill>{d}<a:tailEnd type="triangle"/></a:ln></p:spPr></p:cxnSp>')
    if label:
        s += textbox(lx, ly, 0.9, 0.22, [para([run(label, 900, color, True)], 'ctr')])
    return s
def chip(x, y, w, text, kind):
    f, l, c = {'ok': ('E6F4EA', '2E7D32', '2E7D32'), 'bad': ('FDE7E7', RED, RED), 'mid': ('FFF6DA', 'B7950B', '8A6D00'), 'na': ('F2F4F7', GRAY, GRAY)}[kind]
    return box(x, y, w, 0.3, [text], fill=f, line=l, sz=900, color=c, name='Outcome')
DEC = 'EEF3FA'
body = ''
# row 1: start-up → window → any report?
body += box(0.6, 1.5, 2.6, 0.62, ['Start-up, once', 'load N_known = 30, UE IDs, frozen baselines'], fill=LIGHT, bold_first=True, sz=950)
body += arrow(3.2, 1.81, 3.6, 1.81)
body += box(3.6, 1.5, 3.0, 0.62, ['Every aligned 1 s window t', 'receive KPM + token from each node'], fill=LIGHT, bold_first=True, sz=950)
body += arrow(6.6, 1.81, 7.0, 1.81)
body += box(7.0, 1.44, 2.2, 0.74, ['Any node reported in t?'], fill=DEC, prst='flowChartDecision', sz=950)
body += arrow(9.2, 1.81, 9.75, 1.81, label='no', lx=9.03, ly=1.55)
body += chip(9.75, 1.66, 2.2, 'window n/a → skip to t + 1', 'na')
body += arrow(8.1, 2.18, 8.1, 2.5, label='yes', lx=8.15, ly=2.2)
# row 2: field-level C_i
body += textbox(0.6, 2.5, 2.4, 0.45, [para([run('Field level', 1150, NAVY, True)]), para([run('once per window', 900, GRAY)])], 'ctr')
body += box(3.6, 2.5, 6.2, 0.55, ['C_i: |UE-ID union, all cells + LTE anchor| = N_known ?'], fill=DEC, prst='flowChartDecision', sz=1000)
body += arrow(9.8, 2.775, 10.15, 2.775)
body += chip(10.15, 2.47, 2.6, '=  →  C ok · r_C = 0', 'ok')
body += chip(10.15, 2.8, 2.6, '≠  →  C violated · r_C + 1', 'bad')
body += arrow(6.7, 3.05, 6.7, 3.4)
# row 3: per node j frame
fy, fh = 3.4, 2.25
i = nid()
body += (f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="Loop frame {i}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="{E(0.6)}" y="{E(fy)}"/><a:ext cx="{E(12.13)}" cy="{E(fh)}"/></a:xfrm>'
         f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln w="12700"><a:solidFill><a:srgbClr val="{GRAY}"/></a:solidFill><a:prstDash val="dash"/></a:ln></p:spPr>'
         f'<p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:endParaRPr lang="en-US"/></a:p></p:txBody></p:sp>')
body += textbox(0.75, fy + 0.06, 6.0, 0.28, [para([run('for each node j that reported in t', 1100, NAVY, True), run('   (all four run; none decides a trust state)', 950, GRAY)])])
cols = [(0.8, 'Token', 'valid and in scope?', [('yes → AUTHZ_j ok', 'ok'), ('no → AUTHZ_j fail', 'bad'), ('(P2 applies R1_AUTHZ)', 'na')]),
        (3.8, 'S_i  peers', 'peers(j) ≥ 2 ?  then  z_j > τ_S (4) ?', [('< 2 peers → unavailable', 'na'), ('z_j > 4 → violated', 'bad'), ('else → ok', 'ok')]),
        (6.8, 'H_i  D2', 'a UE of j skips the anchor?', [('yes → D2_j violated', 'bad'), ('no → D2_j ok', 'ok')]),
        (9.8, 'H_i  D1', 'z_d of a UE bound to j', [('z_d ≥ 3 → strong', 'bad'), ('z_d ≥ 2 → warning', 'mid'), ('else → none', 'ok')])]
for x, t1, t2, outs in cols:
    body += box(x, fy + 0.42, 2.75, 0.6, [t1, t2], fill=DEC, bold_first=True, sz=950)
    for k, (txt, kind) in enumerate(outs):
        body += chip(x + 0.15, fy + 1.12 + k * 0.35, 2.45, txt, kind)
body += arrow(6.7, fy + fh, 6.7, fy + fh + 0.25)
# row 4: hand-over
hy = fy + fh + 0.25
body += box(2.2, hy, 5.0, 0.45, ['send {C, r_C, S, D1, D2, AUTHZ} + availability → P2'], fill=LIGHT, line=TEAL, sz=1000)
body += box(7.5, hy, 3.0, 0.45, ['raw KPM records → DB'], fill=LIGHT, line=TEAL, sz=1000)
body += arrow(10.5, hy + 0.22, 11.2, hy + 0.22, dash=True)
body += textbox(11.2, hy + 0.05, 1.55, 0.35, [para([run('next window t + 1', 950, GRAY, True)])], 'ctr')
body += textbox(0.6, hy + 0.52, 12.13, 0.3, [para([run('P1 never sets a trust state — P2 does. z_j: robust z vs same-window peer median (scale 1.4826·MAD, frozen); z_d: robust z of a UE’s last-event-LTE dwell vs its frozen baseline. Phase 2: the anchor list becomes the reference set. Pseudo-code: backup.', 850, GRAY, i=True)])])
open(f'{S}/slide102.xml', 'w').write(make_slide(f'{S}/slide94.xml', 'SECTION Proposed Approach', 'P1 Detection: Workflow per 1 s Window', body))
T = f'{N}/{notes_of("slide98")}'
open(f'{N}/notesSlide103.xml', 'w').write(notes_xml(T, [
 '【English】',
 'This is the P1 decision logic drawn as a workflow; the same logic as pseudo-code is in the backup.',
 'At start-up P1 loads the trust anchors once. Then, for every aligned one-second window, it first asks whether any node reported; if not, the window is n/a and skipped.',
 'Next comes the one field-level check, the population check: the union of UE IDs from all cells and the LTE anchor must equal the known population. If not, the window is violated and the persistence counter goes up.',
 'Then, for each node that reported, four checks run side by side: the token, the peer check with its two-peer minimum and threshold 4, the D2 transition rule, and the D1 dwell test with thresholds 2 and 3.',
 'P1 hands all of this, with availability, to P2, writes the raw records to the DB, and moves to the next window. P1 never decides a trust state — that is P2’s job.',
 '【中文逐字稿】',
 '這頁把 P1 的判斷邏輯畫成流程圖；同一套邏輯的虛擬碼放在附錄。',
 '啟動時 P1 只載入一次信任錨點。之後每個對齊的一秒窗，先問有沒有任何節點回報；沒有的話這個窗是 n/a，直接跳過。',
 '接著是唯一一個全場層級的檢查：人數檢查。所有 cell 加上 LTE 錨點的 UE ID 聯集要等於已知人數；不相等就判違反，持續計數加一。',
 '然後對每個有回報的節點，四項檢查並排進行：token、需要至少兩個 peer、門檻 4 的 peer 檢查、D2 轉移規則，以及門檻 2 和 3 的 D1 停留檢定。',
 'P1 把這些結果連同可用性交給 P2，原始紀錄寫進 DB，然後進到下一個窗。P1 不決定信任狀態，那是 P2 的工作。']))
open(f'{N}/_rels/notesSlide103.xml.rels', 'w').write(re.sub(r'slides/slide\d+\.xml', 'slides/slide102.xml', open(f'{N}/_rels/{notes_of("slide98")}.rels').read()))
open(f'{S}/_rels/slide102.xml.rels', 'w').write(open(f'{S}/_rels/slide98.xml.rels').read().replace(notes_of('slide98'), 'notesSlide103.xml'))
# cross-references
sub_once(f'{S}/slide27.xml', 'Full if/else: p. 28', 'Workflow: after the P1 sequence · pseudo-code: backup')
sub_once(f'{S}/slide34.xml', 'full if/else: backup', 'workflow: next page · pseudo-code: backup')
sub_once(f'{N}/{notes_of("slide34")}', 'the full if/else is on page 28', 'the workflow is on the next page and the pseudo-code in the backup')
sub_once(f'{S}/slide28.xml', 'SECTION Backup · P1 detail', 'SECTION Backup · P1 pseudo-code')

# ---------- package: add slide102 after slide34; drop slide47, 50, 51, 52 ----------
ct = open(f'{U}/../[Content_Types].xml').read()
if '/slide102.xml' not in ct:
    ct = ct.replace('</Types>', '<Override PartName="/ppt/slides/slide102.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
                    '<Override PartName="/ppt/notesSlides/notesSlide103.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml"/></Types>')
    open(f'{U}/../[Content_Types].xml', 'w').write(ct)
pr = open(f'{U}/_rels/presentation.xml.rels').read()
if 'slides/slide102.xml' not in pr:
    pr = pr.replace('</Relationships>', '<Relationship Id="rId202" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide102.xml"/></Relationships>')
    open(f'{U}/_rels/presentation.xml.rels', 'w').write(pr)
def rid_of(sl):
    m = re.search(rf'<Relationship [^>]*Target="slides/{sl}.xml"[^>]*>', pr)
    return re.search(r'Id="(rId\d+)"', m.group(0)).group(1)
p = open(f'{U}/presentation.xml').read()
m = re.search(rf'<p:sldId id="(\d+)" r:id="{rid_of("slide34")}"/>', p)
newid = max(int(v) for v in re.findall(r'<p:sldId id="(\d+)"', p)) + 1
p = p.replace(m.group(0), m.group(0) + f'<p:sldId id="{newid}" r:id="rId202"/>')
for sl in ('slide47', 'slide50', 'slide51', 'slide52'):
    p, n = re.subn(rf'<p:sldId id="\d+" r:id="{rid_of(sl)}"/>', '', p)
    assert n == 1, sl
open(f'{U}/presentation.xml', 'w').write(p)
print('v1.18 written')
# order within the old p.51–59 block: dataset first, then observation → check
p = open(f'{U}/presentation.xml').read()
a = re.search(rf'<p:sldId id="\d+" r:id="{rid_of("slide53")}"/>', p).group(0)
b = re.search(rf'<p:sldId id="\d+" r:id="{rid_of("slide48")}"/>', p).group(0)
p = p.replace(a, '').replace(b, a + b)
open(f'{U}/presentation.xml', 'w').write(p)
print('reordered')
