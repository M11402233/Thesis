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

# ======================= v1.17 (2026-11-19): data corrections + phase-2 status + E29 dev run =======================
import json, os
_tc = {}
def notes_xml(tmpl, paras):
    x = _tc.setdefault(tmpl, open(tmpl).read())
    i = x.find('<p:ph type="body"'); j = x.find('<p:txBody>', i); k = x.find('</p:txBody>', j)
    body = '<p:txBody><a:bodyPr/><a:lstStyle/>' + ''.join(
        f'<a:p><a:r><a:rPr lang="{"zh-TW" if any(ord(ch) > 0x2E80 for ch in p) else "en-US"}" dirty="0"/><a:t>{esc(p)}</a:t></a:r></a:p>' for p in paras) + '</p:txBody>'
    return x[:j] + body + x[k + len('</p:txBody>'):]

def sub_once(path, old, new, regex=False):
    x = open(path).read()
    if regex:
        y, n = re.subn(old, new, x, count=1, flags=re.S)
    else:
        n = x.count(old); y = x.replace(old, new)
    if n == 0:
        raise SystemExit(f'not found in {os.path.basename(path)}: {old[:60]}')
    open(path, 'w').write(y)

S = f'{U}/slides'
NEW = 'E6F7F6'
# ---- data corrections on existing slides ----
sub_once(f'{S}/slide16.xml', '<a:t>shown on D-30</a:t>', '<a:t>D-30 · phase-2 re-run pending</a:t>')
for ev, ev2 in [('trace replay, D-30 (8 seeds × 300 s)', 'trace replay, D-30 (8 seeds × 300 s) — running-mean input; re-run on D-30P (phase 2)'),
                ('offline, open-loop replay', 'offline, open-loop replay — running-mean input; re-run on D-30P (phase 2)'),
                ('6 runs on D-30; final evaluation done; delay attacks only', '6 runs on D-30 (running-mean input), delay attacks only — full PSRO re-run on D-30P (9 detectors)')]:
    sub_once(f'{S}/slide95.xml',
             rf'<a:t>{re.escape(ev)}</a:t>(.*?<a:srgbClr val=")\w+("/></a:solidFill><a:ln w="15875"><a:solidFill><a:srgbClr val=")\w+(".*?<a:t>)done(</a:t>)',
             rf'<a:t>{ev2}</a:t>\g<1>FFF2CC\g<2>D6B656\g<3>redo\g<4>', regex=True)
sub_once(f'{S}/slide95.xml', '<a:t>TM3 6/8; U20 collecting</a:t>', '<a:t>old runs lack per-cell attribution (not formal); re-collect with r9 after D-30P</a:t>')
sub_once(f'{S}/slide95.xml', '(<a:t>old runs lack per-cell attribution \\(not formal\\); re-collect with r9 after D-30P</a:t>.*?<a:t>)running(</a:t>)', r'\g<1>pending\g<2>', regex=True)
sub_once(f'{S}/slide95.xml', '<a:t>Solid = implemented and evaluated · everything else is labelled where it appears</a:t>',
         '<a:t>redo = implemented and evaluated on the running-mean input; numbers are replaced from D-30P in phase 2</a:t>')
sub_once(f'{S}/slide61.xml', '<a:t>Pre-correction result (running-mean input); re-run in phase 2</a:t>',
         '<a:t>Pre-correction result (running-mean input). Interval-delay re-run (phase 1, unofficial): rejected 5.4 % (844 / 15,534), trusted 46.5 %; formal values in phase 2</a:t>')
sub_once(f'{S}/slide29.xml', '<a:t>Counts usable input and lost PRB visibility; changes no trust state</a:t>',
         '<a:t>Counts usable input and lost PRB visibility; allocates nothing (allocation: next paper)</a:t>')
sub_once(f'{S}/slide98.xml', 'detection rate (falsified (node, s) judged low-trust or rejected) and attacker gain',
         'detection gain ΔDR (falsified (node, s) judged low-trust or rejected, minus the same (node, s) on clean data) and attacker gain')

# ---- new slide100: E29 development run (after slide99) ----
R = json.load(open(sys.argv[2]))['rows']
def pc(x): return '—' if x is None else f'{x:+.3f}'
def pg(x): return '—' if x is None else f'{x:.2f}'
_id[0] = 100
hdr = [cell(h, True, a, sz=1050) for h, a in [('Attack', 'l'), ('ΔDR', 'ctr'), ('Δ rejected', 'ctr'), ('Gain: none → strict', 'ctr')]]
def rowdef(label, key, fill=None):
    v = R[key]
    return ([cell(label, sz=1050, fill=fill), cell(pc(v['dDR_flag']), algn='ctr', sz=1050, fill=fill),
             cell(pc(v['dDR_rej']), algn='ctr', sz=1050, fill=fill), cell(f"{pg(v['gain_none'])} → {pg(v['gain_strict'])}", algn='ctr', sz=1050, fill=fill)], 0.3)
down = [('Step ×0.6', 'down|Step x0.6'), ('Step ×0.8', 'down|Step x0.8'), ('Drift ↓ 1 %/s', 'down|Drift down 1%/s'), ('Drift ↓ 2 %/s', 'down|Drift down 2%/s'),
        ('Irregular ↓ · 1 node', 'down|Irregular down 1 node'), ('Irregular ↓ · multi 60 s', 'down|Irregular down multi 60s')]
up = [('Step ×1.2', 'up|Step x1.2'), ('Step ×1.5', 'up|Step x1.5'), ('Drift ↑ 1 %/s', 'up|Drift up 1%/s'),
      ('Irregular ↑ · 1 node', 'up|Irregular up 1 node'), ('Irregular ↑ · multi 60 s', 'up|Irregular up multi 60s')]
W = [2.05, 0.95, 1.05, 1.8]
body = textbox(0.6, 1.42, 12.13, 0.32, [para([run('Development run — not citable. ', 1150, RED, True), run('Old D-30 with interval delay, rule baseline B1 (severity order), 10 random seeds × 56 sequences. Formal numbers come from D-30P.', 1100, GRAY, i=True)])])
body += textbox(0.6, 1.82, 5.85, 0.3, [para([run('Lowering the delay (lure traffic in)', 1250, NAVY, True)])])
body += textbox(6.88, 1.82, 5.85, 0.3, [para([run('Raising the delay (push traffic away)', 1250, NAVY, True)])])
body += table(0.6, 2.16, W, [(hdr, 0.32)] + [rowdef(a, b, NEW if 'Irregular' in a else None) for a, b in down], None)
body += table(6.88, 2.16, W, [(hdr, 0.32)] + [rowdef(a, b, NEW if 'Irregular' in a else None) for a, b in up], None)
body += card(0.6, 4.45, 3.95, 1.75, RED, [para([run('Lowering is almost invisible', 1250, NAVY, True)], spc_after=300),
    para([run('Steps and irregular bursts add ≈ 0 detection over clean; only drift, which grows large, is caught.', 1100)])])
body += card(4.69, 4.45, 3.95, 1.75, GOLD, [para([run('Raising: flagging helps the attacker', 1250, NAVY, True)], spc_after=300),
    para([run('Its goal is to push traffic away; excluding its report does exactly that, so gain rises under strict admission.', 1100)])])
body += card(8.78, 4.45, 3.95, 1.75, TEAL, [para([run('Why the metric changed', 1250, NAVY, True)], spc_after=300),
    para([run('53.5 % of clean (node, s) are already low-trust or rejected, so raw detection sits at that floor; ΔDR subtracts it.', 1100)])])
body += textbox(0.6, 6.3, 12.13, 0.3, [para([run('Gain = share of opportunities where steering is lured (lowering) or the truly best cell is skipped (raising). Pipeline check: clean rejected 844 / 15,534 = phase-1 re-run.', 950, GRAY, i=True)])])
NEW = 'E6F7F6'
open(f'{S}/slide100.xml', 'w').write(make_slide(f'{S}/slide94.xml', 'SECTION Analysis', 'First Rule Run on E29 (Development)', body))

# ---- new slide101: phase-2 status (after slide96, the correction slide) ----
_id[0] = 100
st = [cell(h, True, 'l', sz=1100) for h in ('Step', 'What', 'Status')]
OK, RUN, TODO = 'E6F4EA', 'FFF6DA', 'FFFFFF'
rows = [(st, 0.34),
 ([cell('D-30P data', b=True, sz=1050), cell('re-collect D-30 with per-cell counters (r9): 8 seeds × 301 s, same command line', sz=1050), cell('running · ≈ 100 / 301 s simulated · checks ≈ Nov 20 morning', sz=1050, fill=RUN)], 0.42),
 ([cell('Build check', b=True, sz=1050), cell('first batch (GCC 11 build) changed only SINR last digits in one trace → kept for diagnosis only; rebuilt with GCC 13', sz=1050), cell('gate passed (all files = reference)', sz=1050, fill=OK)], 0.48),
 ([cell('Input layer', b=True, sz=1050), cell('per-cell interval delay, zero-delay samples, RRC lists, serving cell — from the new counters', sz=1050), cell('written · 3 checks pass on 8 / 8 diagnostic seeds', sz=1050, fill=OK)], 0.42),
 ([cell('Population rule', b=True, sz=1050), cell('the LTE anchor now lists all 30 UEs every window → anchor becomes the reference set: mmWave union must equal it (more = inflation, fewer = deletion)', sz=1050), cell('decided Nov 19', sz=1050, fill=OK)], 0.48),
 ([cell('Steps 1–5', b=True, sz=1050), cell('re-run population, peer, mobility, fusion, admission and resource evaluation on D-30P', sz=1050), cell('next · ≈ Nov 22', sz=1050, fill=TODO)], 0.42),
 ([cell('Step 7', b=True, sz=1050), cell('full PSRO on D-30P: 9 detectors, 432 attacker best responses; fills Rule + DRL and Chart 2', sz=1050), cell('after steps 1–5 · ≈ Nov 26–28', sz=1050, fill=TODO)], 0.42)]
body = table(0.6, 1.5, [1.75, 7.0, 3.38], rows, None)
body += textbox(0.6, 4.75, 12.13, 0.9, [para([run('Every number marked “pre-correction” in this deck is replaced from D-30P. ', 1200, NAVY, True), run('Until then, phase-1 numbers (interval delay on the old data) are shown only where labelled, and the dates above are estimates from the current simulation speed.', 1150)])])
open(f'{S}/slide101.xml', 'w').write(make_slide(f'{S}/slide94.xml', 'SECTION Analysis', 'Phase 2: Rebuilding the Data, Then Every Number', body))

# ---- notes ----
N = f'{U}/notesSlides'
T99 = f'{N}/notesSlide99.xml'; notes_xml(T99, [])
open(f'{N}/notesSlide101.xml', 'w').write(notes_xml(T99, [
 '【English】',
 'This is a first run of the rule baseline on the new attacks. It is a development run on the old data with interval delay, so none of these numbers are citable; it only checks that the pipeline works and shows what to expect.',
 'The pipeline is right: on clean data it reproduces the phase-1 count exactly, 844 rejected out of 15,534.',
 'Three things stand out. First, lowering the delay is almost invisible to the rules: steps and irregular bursts add about zero detection over clean data; only drift, which grows large, is caught. Second, for raising, flagging the report helps the attacker, because its goal is to push traffic away. Third, we changed the metric: more than half of clean reports are already low-trust or rejected, so we subtract the same node-second on clean data.',
 'If D-30P shows the same, chart 1a leaves a clear gap for the DRL policy to fill — or shows that the limit lies in the evidence, not the rules.',
 '【中文逐字稿】',
 '這是規則版在新攻擊上的第一次試跑，用的是舊資料加區間延遲，所以數字都不能引用，只用來確認流程、看看大概的趨勢。',
 '流程是對的：乾淨資料上完整重現第一階段的數字，15,534 筆裡 844 筆 rejected。',
 '有三點：第一，調低延遲對規則來說幾乎看不見，階躍和不規則攻擊比乾淨時多抓到的大約是 0，只有會越漂越大的漂移抓得到。第二，調高延遲時，把報告標成不可信反而幫了攻擊者，因為它本來就想把流量推走。第三，我們改了指標：乾淨資料本來就有超過一半被判 low-trust 或 rejected，所以要扣掉同一個節點同一秒在乾淨時的結果。',
 '如果 D-30P 也是這樣，圖 1a 就留下一塊 DRL 可以證明自己的空間；如果 DRL 也抓不到，代表限制在證據本身，而不是規則。']))
open(f'{N}/notesSlide102.xml', 'w').write(notes_xml(T99, [
 '【English】',
 'This page shows where the phase-2 rebuild stands. The new data, D-30P, re-runs D-30 with per-cell counters. A first batch built with GCC 11 changed only the last digits of SINR in one trace file, so we kept it for diagnosis and rebuilt with GCC 13; the GCC 13 build passed its gate, and the eight seeds are about a third of the way through.',
 'The new input layer is written and passes its three checks on all eight diagnostic seeds. One design change: in the new data the LTE anchor lists all thirty UEs every window, so it becomes the reference set — the union of mmWave lists must equal it. More means inflation, fewer means deletion.',
 'Next come steps one to five, then the full PSRO with nine detectors. The dates are estimates from the current simulation speed.',
 '【中文逐字稿】',
 '這頁說明第二階段重建的進度。新資料 D-30P 是用逐 cell 計數器把 D-30 重跑一次。第一批是 GCC 11 編的，只有一個 trace 檔的 SINR 末位數不同，所以留作診斷，改用 GCC 13 重編；GCC 13 版已通過閘門檢查，八個 seed 大約跑了三分之一。',
 '新輸入層已經寫好，在八個診斷 seed 上三項檢查全部通過。有一個設計改變：新資料裡 LTE 錨點每一窗都列出全部 30 個 UE，所以錨點改成參照集合，mmWave 名單的聯集必須等於它；多了是灌水，少了是刪除。',
 '接下來是第 1 到 5 步，然後是 9 個偵測端的完整 PSRO。日期是依目前模擬速度估的。']))
for sl, nt in (('slide100', 'notesSlide101'), ('slide101', 'notesSlide102')):
    open(f'{N}/_rels/{nt}.xml.rels', 'w').write(open(f'{N}/_rels/notesSlide99.xml.rels').read().replace('slide98.xml', f'{sl}.xml'))
    open(f'{S}/_rels/{sl}.xml.rels', 'w').write(open(f'{S}/_rels/slide98.xml.rels').read().replace('notesSlide99.xml', f'{nt}.xml'))

# ---- bookkeeping ----
ct = open(f'{U}/../[Content_Types].xml').read()
for sl, nt in (('slide100', 'notesSlide101'), ('slide101', 'notesSlide102')):
    if f'/{sl}.xml' not in ct:
        ct = ct.replace('</Types>', f'<Override PartName="/ppt/slides/{sl}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
                        f'<Override PartName="/ppt/notesSlides/{nt}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml"/></Types>')
open(f'{U}/../[Content_Types].xml', 'w').write(ct)
pr = open(f'{U}/_rels/presentation.xml.rels').read()
for sl, rid in (('slide100', 'rId200'), ('slide101', 'rId201')):
    if f'slides/{sl}.xml' not in pr:
        pr = pr.replace('</Relationships>', f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/{sl}.xml"/></Relationships>')
open(f'{U}/_rels/presentation.xml.rels', 'w').write(pr)
p = open(f'{U}/presentation.xml').read()
def rid_of(sl):
    m = re.search(rf'<Relationship [^>]*Target="slides/{sl}.xml"[^>]*>', pr)
    return re.search(r'Id="(rId\d+)"', m.group(0)).group(1)
for after, rid in (('slide99', 'rId200'), ('slide96', 'rId201')):
    m = re.search(rf'<p:sldId id="(\d+)" r:id="{rid_of(after)}"/>', p)
    newid = max(int(v) for v in re.findall(r'<p:sldId id="(\d+)"', p)) + 1
    p = p.replace(m.group(0), m.group(0) + f'<p:sldId id="{newid}" r:id="{rid}"/>')
    p = p.replace(f'<p14:sldId id="{m.group(1)}"/>', f'<p14:sldId id="{m.group(1)}"/><p14:sldId id="{newid}"/>')
open(f'{U}/presentation.xml', 'w').write(p)
print('v1.17 written')
