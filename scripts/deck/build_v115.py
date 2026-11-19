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
hdr = [cell(h, True, a) for h, a in [('Generator','l'),('Learns?','ctr'),('When it attacks','l'),('How much','l'),('Nodes','l'),('Basis','l')]]
R = lambda *c: c
rows = [(hdr, 0.42),
 ([cell('Step', b=True), cell('no',algn='ctr'), cell('every 1 s window from t0\n(window 150 of 300), no pause'), cell('fixed ×0.6–0.9 or ×1.2–1.5'), cell('1 per run\n(cells 2–8 in turn)'), cell('fixed scaling [13]')], 0.62),
 ([cell('Drift', b=True), cell('no',algn='ctr'), cell('every window from t0'), cell('ramp: 0.5–2 % of the mean per s'), cell('1 per run'), cell('this work (E9)')], 0.5),
 ([cell('Irregular (new)', b=True, fill=TBD), cell('no',algn='ctr',fill=TBD), cell('random on / off — to decide', fill=TBD, i=True), cell('random size — to decide', fill=TBD, i=True), cell('to decide', fill=TBD, i=True), cell('advisor feedback, Nov 19', fill=TBD)], 0.5),
 ([cell('Learning (E19)', b=True), cell('yes · PPO',algn='ctr'), cell('every window from t0;\npicks a_t from what it saw'), cell('a_t ∈ [0.5, 1.5],\nchange ≤ 0.05 per s'), cell('1 per run'), cell('cf. optimised\nperturbation [14]')], 0.62),
]
body97 = table(0.6, 1.45, [1.75, 1.05, 2.75, 2.55, 1.75, 2.28], rows, None)
body97 += card(0.6, 4.35, 5.95, 1.55, RED, [
    para([run('Problem: every scripted attack is regular', 1400, NAVY, True)], spc_after=400),
    para([run('Same start time, every window, one shape — one minute of watching reveals the rule, so it is easy to catch.', 1200)])])
body97 += card(6.78, 4.35, 5.95, 1.55, GOLD, [
    para([run('How often is a node compromised?', 1400, NAVY, True)], spc_after=400),
    para([run('One node per run, attacking from t0. No arrival process (e.g., one node per day) is modelled. Basis: to be added.', 1200)])])
body97 += textbox(0.6, 6.1, 12.13, 0.35, [para([run('The attacker changes only the delay field of its own KPM report; the field (ns-O-RAN trace) is not changed — offline injection.', 1100, GRAY, i=True)])])
s97 = make_slide(f'{U}/slides/slide94.xml', SEC, 'Attack Generators: What, When, How Much', body97)
open(f'{U}/slides/slide97.xml', 'w').write(s97)

# ---------- slide98: evaluation design ----------
_id[0] = 100
P = 'pending'
def drow(label, h=0.38):
    return ([cell(label), cell(P,algn='ctr',color=GRAY,i=True), cell(P,algn='ctr',color=GRAY,i=True)], h)
lh = [cell('Attack',True,'l'), cell('Rule (B1)',True,'ctr'), cell('Rule + DRL',True,'ctr')]
left = [(lh,0.4)] + [drow(a) for a in ['Step ×0.6','Step ×0.8','Step ×1.2','Step ×1.5','Drift ↓ 1 %/s']] + \
       [([cell('Irregular (form to decide)', fill=TBD), cell(P,algn='ctr',fill=TBD,color=GRAY,i=True), cell(P,algn='ctr',fill=TBD,color=GRAY,i=True)],0.38)]
rh = [cell('Attacker sees',True,'l'), cell('Rule (B1)',True,'ctr'), cell('Rule + DRL',True,'ctr')]
right = [(rh,0.4)] + [drow(a) for a in ['O-outcome: steering result','O-full: + its own verdicts','O-outcome + token']]
body98 = textbox(0.6, 1.42, 12.13, 0.45, [para([run('Fixed: ', 1300, NAVY, True), run('P1 evidence · P3 policy · P4 evaluation. ', 1300), run('Changed: ', 1300, NAVY, True), run('only the P2 decision. Both detectors judge the same reports, at the same clean false-rejection rate.', 1300)])], 'ctr')
body98 += textbox(0.6, 1.98, 5.95, 0.36, [para([run('Chart 1 · General attacker ', 1400, NAVY, True), run('(does not learn)', 1200, GRAY)])], 'ctr')
body98 += textbox(6.78, 1.98, 5.95, 0.36, [para([run('Chart 2 · Learning attacker ', 1400, NAVY, True), run('(trained against the defence)', 1200, GRAY)])], 'ctr')
body98 += table(0.6, 2.4, [2.75, 1.6, 1.6], left, None)
body98 += table(6.78, 2.4, [2.75, 1.6, 1.6], right, None)
body98 += card(6.78, 4.05, 5.95, 0.92, TEAL, [para([run('Each chart: one pair of bars per row — Rule vs Rule + DRL. ', 1150), run('The stronger detector catches more falsified reports.', 1150, NAVY, True)])])
body98 += card(0.6, 5.15, 12.13, 1.05, GOLD, [
    para([run('Metric (to confirm): ', 1200, NAVY, True), run('detection rate = share of falsified (node, s) judged low-trust or rejected; attacker success = 1 − detection.', 1200)], spc_after=300),
    para([run('Rule + DRL: ', 1200, NAVY, True), run('DRL may only escalate above the rule floor (see “The Rule Floor”). Chart 2: the attacker is a best response to the detector in that column.', 1200)])])
s98 = make_slide(f'{U}/slides/slide94.xml', SEC, 'Evaluation Design: Rule vs Rule + DRL', body98)
open(f'{U}/slides/slide98.xml', 'w').write(s98)
print('slides written')
