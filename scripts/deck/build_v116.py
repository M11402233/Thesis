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

# ======================= v1.16 (2026-11-19, E29 decisions) =======================
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../xapps/verification/residuals'))
import attack_generators as AG
NEW = 'E6F7F6'

_tmpl_cache = {}
def notes_xml(tmpl, paras):
    x = _tmpl_cache.setdefault(tmpl, open(tmpl).read())
    i = x.find('<p:ph type="body"'); j = x.find('<p:txBody>', i); k = x.find('</p:txBody>', j)
    body = '<p:txBody><a:bodyPr/><a:lstStyle/>' + ''.join(
        f'<a:p><a:r><a:rPr lang="{"zh-TW" if any(ord(ch) > 0x2E80 for ch in p) else "en-US"}" dirty="0"/><a:t>{esc(p)}</a:t></a:r></a:p>' for p in paras) + '</p:txBody>'
    return x[:j] + body + x[k + len('</p:txBody>'):]

# ---------- slide97 (p.45): irregular row decided ----------
_id[0] = 100
SEC = 'SECTION Proposed Approach · D. Learn'
hdr = [cell(h, True, a) for h, a in [('Generator','l'),('Learns?','ctr'),('When it attacks','l'),('How much','l'),('Nodes','l'),('Basis','l')]]
rows = [(hdr, 0.42),
 ([cell('Step', b=True), cell('no',algn='ctr'), cell('every 1 s window from t0\n(window 150 of 300), no pause'), cell('fixed ×0.6–0.9 or ×1.2–1.5'), cell('1 per run\n(cells 2–8 in turn)'), cell('fixed scaling [13]')], 0.62),
 ([cell('Drift', b=True), cell('no',algn='ctr'), cell('every window from t0'), cell('ramp: 0.5–2 % of the mean per s'), cell('1 per run'), cell('this work (E9)')], 0.5),
 ([cell('Irregular (new, E29)', b=True, fill=NEW), cell('no',algn='ctr',fill=NEW), cell('random start 30–150 s; on / off\nas a Poisson process (on 10 s, off 20 s)', fill=NEW), cell('new size per burst:\n×0.6–0.9 or ×1.2–1.5', fill=NEW), cell('1, or up to 4\narriving at random', fill=NEW), cell('advisor feedback, Nov 19', fill=NEW)], 0.62),
 ([cell('Learning (E19)', b=True), cell('yes · PPO\nO-full knows\nthe threshold',algn='ctr'), cell('every window from t0;\npicks a_t from what it saw'), cell('a_t ∈ [0.5, 1.5],\nchange ≤ 0.05 per s'), cell('1 per run'), cell('cf. optimised\nperturbation [14]')], 0.72),
]
body97 = table(0.6, 1.45, [1.95, 1.25, 2.9, 2.2, 1.6, 2.23], rows, None)
body97 += card(0.6, 4.55, 5.95, 1.4, TEAL, [
    para([run('Fix: an attacker that is hard to read', 1400, NAVY, True)], spc_after=400),
    para([run('Random start, random gaps, random size: one minute of watching no longer reveals the rule.', 1200)])])
body97 += card(6.78, 4.55, 5.95, 1.4, GOLD, [
    para([run('How often is a node compromised?', 1400, NAVY, True)], spc_after=400),
    para([run('Tested as a stress test: 1 node, or nodes arriving every 30 / 60 / 120 s. A 300 s run cannot show “one per two days”. Real-world basis: to be added.', 1150)])])
body97 += textbox(0.6, 6.1, 12.13, 0.35, [para([run('The attacker changes only the delay field of its own KPM report; the field (ns-O-RAN trace) is not changed — offline injection. Settings: p. 49.', 1100, GRAY, i=True)])])
open(f'{U}/slides/slide97.xml', 'w').write(make_slide(f'{U}/slides/slide94.xml', SEC, 'Attack Generators: What, When, How Much', body97))

# ---------- slide98 (p.46): three charts ----------
_id[0] = 100
P = 'pending'
def drow(label, h=0.36, fill=None):
    return ([cell(label, sz=1100, fill=fill), cell(P,algn='ctr',color=GRAY,i=True,sz=1100,fill=fill), cell(P,algn='ctr',color=GRAY,i=True,sz=1100,fill=fill)], h)
def chart_tbl(first, labels, news):
    h = [cell(first,True,'l',sz=1100), cell('Rule',True,'ctr',sz=1100), cell('Rule + DRL',True,'ctr',sz=1100)]
    return [(h,0.38)] + [drow(a, fill=NEW if a in news else None) for a in labels]
c1a = ['Step ×0.6','Step ×0.8','Drift ↓ 1 %/s','Drift ↓ 2 %/s','Irregular ↓ · 1 node','Irregular ↓ · multi']
c1b = ['Step ×1.2','Step ×1.5','Drift ↑ 1 %/s','Irregular ↑ · 1 node','Irregular ↑ · multi']
c2  = ['O-outcome','O-full (knows threshold)','O-outcome + token']
body98 = textbox(0.6, 1.42, 12.13, 0.42, [para([run('Fixed: ', 1300, NAVY, True), run('P1 evidence · P3 policy · P4 evaluation. ', 1300), run('Changed: ', 1300, NAVY, True), run('only the P2 decision — same reports, same clean false-rejection rate reported for both.', 1300)])], 'ctr')
W = [1.85, 0.95, 1.15]; X = [0.6, 4.69, 8.78]
for x, t1, t2 in zip(X, ['Chart 1a · General, lowers delay','Chart 1b · General, raises delay','Chart 2 · Learning attacker'], ['(does not learn)','(does not learn)','(trained against that column)']):
    body98 += textbox(x, 1.92, 3.95, 0.5, [para([run(t1, 1250, NAVY, True)]), para([run(t2, 1050, GRAY)])], 'ctr')
body98 += table(X[0], 2.48, W, chart_tbl('Attack', c1a, c1a[4:]), None)
body98 += table(X[1], 2.48, W, chart_tbl('Attack', c1b, c1b[3:]), None)
body98 += table(X[2], 2.48, W, chart_tbl('Attacker sees', c2, []), None)
body98 += card(0.6, 5.12, 12.13, 1.12, GOLD, [
    para([run('Metrics: ', 1150, NAVY, True), run('detection rate (falsified (node, s) judged low-trust or rejected) and attacker gain (lured / repelled steering) with regret — attacking less often lowers detections but also lowers harm.', 1150)], spc_after=300),
    para([run('Repeats: ', 1150, NAVY, True), run('irregular rows × 10 random seeds on 56 sequences. Rule + DRL may only escalate above the rule floor.', 1150)])])
open(f'{U}/slides/slide98.xml', 'w').write(make_slide(f'{U}/slides/slide94.xml', SEC, 'Evaluation Design: Rule vs Rule + DRL', body98))

# ---------- slide99 (new p.49, Analysis): attack behaviour settings ----------
_id[0] = 100
X0, XW, T = 2.35, 10.38, AG.T
def sx(t): return X0 + XW * t / T
def lane(y, h, bursts, color, label, sub=None):
    s = textbox(0.6, y - 0.02, 1.7, h + 0.04, [para([run(label, 1050, NAVY, True)])] + ([para([run(sub, 900, GRAY)])] if sub else []), 'ctr')
    s += rect(X0, y + h / 2 - 0.01, XW, 0.02, BORDER, 'Axis')
    for a, b, f in bursts:
        hh = h * (0.35 + 0.65 * min(1.0, abs(1 - f) / 0.4))
        s += rect(sx(a), y + (h - hh) / 2, max(0.03, sx(b) - sx(a)), hh, color, 'Burst')
    return s
sg = AG.irregular(4200, 3, 0, 'down')
mg = AG.irregular(4200, 3, 0, 'down', 'multi')
body = textbox(0.6, 1.5, 12.13, 0.3, [para([run('One run = 300 s (x-axis). Bar = falsified seconds; bar height = how far the delay is scaled. Examples drawn by the generator (seed 4200, cell 3, r = 0).', 1050, GRAY, i=True)])])
y = 1.9
body += lane(y, 0.3, [(150, 300, 0.6)], NAVY, 'Step (today)', 'same start, no pause'); y += 0.42
body += lane(y, 0.3, sg['events'][0]['bursts'], RED, 'Irregular · 1 node', 'random start, gaps, size'); y += 0.42
lanes = mg['events']
body += textbox(0.6, y, 1.7, 0.22 * len(lanes), [para([run('Irregular · multi', 1050, NAVY, True)]), para([run('nodes arrive (Poisson)', 900, GRAY)])], 'ctr')
for e in lanes:
    body += rect(X0, y + 0.1, XW, 0.015, BORDER, 'Axis')
    body += rect(sx(e['compromised_at']) - 0.01, y, 0.02, 0.2, GOLD, 'Arrival')
    for a, b, f in e['bursts']:
        body += rect(sx(a), y + 0.03, max(0.03, sx(b) - sx(a)), 0.14, RED, 'Burst')
    y += 0.22
for t in (0, 50, 100, 150, 200, 250, 300):
    body += textbox(sx(t) - 0.3, y + 0.02, 0.6, 0.2, [para([run(f'{t} s', 850, GRAY)], 'ctr')])
y += 0.3
hdr = [cell(h, True, 'l', sz=1050) for h in ('Setting', 'Rule', 'Why')]
R = [('Start', 'random t0, 30–150 s', 'not always the middle of the run'),
     ('On / off', 'on 3 + geometric (mean 10 s), off 3 + geometric (mean 20 s): burst starts form a Poisson process', '≥ 3 s per burst > L_C = 2, so we do not only re-test the known 1-window pulse gap'),
     ('Size', 'new factor per burst: lower ×0.6–0.9, raise ×1.2–1.5; fixed inside a burst', 'same range as the step attacks'),
     ('Direction', 'lower and raise kept separate — one chart each', 'lowering lures traffic; raising pushes it away'),
     ('Nodes', '(a) 1 node, cells 2–8 in turn; (b) up to 4 nodes, arrival gap mean 30 / 60 / 120 s, never recovered', '(b) is a compressed-time stress test, not a real frequency'),
     ('Knowledge', 'irregular: no threshold, no verdicts; learning (O-full): sees its own verdicts → learns the threshold', 'keeps “general” and “learning” apart'),
     ('Repeats', '10 random seeds × 56 sequences (8 seeds × 7 cells)', 'mean and range per row')]
rows = [(hdr, 0.3)] + [([cell(a, b=True, sz=1000), cell(b_, sz=1000), cell(c, sz=1000, color=GRAY)], 0.29) for a, b_, c in R]
body += table(0.6, y, [1.35, 6.4, 4.38], rows, None)
open(f'{U}/slides/slide99.xml', 'w').write(make_slide(f'{U}/slides/slide94.xml', 'SECTION Analysis', 'Attack Behaviour Settings', body))
print('end y of table approx', y + 0.3 + 7 * 0.29)

# ---------- notes ----------
N = f'{U}/notesSlides'
for _n in ('notesSlide98', 'notesSlide99'):
    notes_xml(f'{N}/{_n}.xml', [])
open(f'{N}/notesSlide98.xml', 'w').write(notes_xml(f'{N}/notesSlide98.xml', [
 '【English】',
 'Before comparing detectors, here is every attack generator we use. Step and drift do not learn: they start at the middle of the run and change every window, without a pause, in one fixed shape. My advisor pointed out that this is too regular — after one minute of watching, the rule is obvious.',
 'So we added an irregular generator, E29. It starts at a random time between 30 and 150 seconds, switches on and off at random — burst starts follow a Poisson process, with bursts of about 10 seconds and gaps of about 20 seconds — and draws a new size for every burst. The exact settings are on page 49.',
 'The learning attacker from E19 adapts. Under O-full it sees its own verdicts, so it can learn where the threshold is.',
 'On how often a node is compromised: we test one node, and also up to four nodes arriving every 30, 60 or 120 seconds on average. A 300-second run cannot show one compromise per two days, so this is a stress test; the real-world basis still has to be added.',
 '【中文逐字稿】',
 '比較偵測方法之前，先說明我們用了哪些攻擊產生器。階躍和漂移都不會學習：從 run 的正中間開始，每一個窗都竄改、不會停，而且只有一種形狀。老師指出這太規律了，看一分鐘就知道規則。',
 '所以我們加入不規則產生器 E29：起點在 30 到 150 秒之間隨機；攻擊會隨機開關，每段攻擊的起點是 Poisson 過程，平均攻 10 秒、停 20 秒；每一段重新抽幅度。詳細設定在第 49 頁。',
 'E19 的學習型攻擊者會調整策略；在 O-full 下它看得到自己被判成什麼，所以可以學到門檻在哪裡。',
 '至於多久出現一個被攻陷節點：我們測一個節點，也測最多四個節點、平均每 30、60 或 120 秒出現一個。一個 run 只有 300 秒，模擬不了「兩天一個」，所以這是壓力測試；真實頻率的依據還要補上。']))
open(f'{N}/notesSlide99.xml', 'w').write(notes_xml(f'{N}/notesSlide99.xml', [
 '【English】',
 'This is how we answer “who detects better”. P1, P3 and P4 stay fixed; only the P2 decision changes. Both versions judge the same reports, and we report the clean false-rejection rate of each.',
 'There are three charts. Chart 1a is general attackers that lower the delay, which lures traffic. Chart 1b is general attackers that raise it, which pushes traffic away. Chart 2 is the learning attacker, trained against the detector in that column, at each observation level.',
 'Each row is a pair of bars: rules only against rules plus DRL. DRL may only escalate above the rule floor.',
 'We report two kinds of numbers: the detection rate, and the attacker’s gain with regret. The second matters because an attacker that attacks less often is caught less often, but it also does less harm. The irregular rows are repeated with 10 random seeds. All cells are still pending.',
 '【中文逐字稿】',
 '這頁說明怎麼回答「誰比較會抓」。P1、P3、P4 固定，只換 P2 的判定；兩個版本判同一批報表，而且各自的乾淨誤拒率都會一起報。',
 '共三張圖：圖 1a 是調低延遲、把流量騙過來的一般攻擊者；圖 1b 是調高延遲、把流量推走的一般攻擊者；圖 2 是對該欄偵測端訓練出來的學習型攻擊者，分不同觀測層級。',
 '每一列是一對長條：只有規則，對比規則加 DRL。DRL 只能在規則之上更嚴。',
 '我們報兩種數字：偵測率，以及攻擊者得利加 regret。後者很重要，因為攻擊得越少，被抓的次數本來就越少，但造成的傷害也越小。不規則攻擊的列用 10 組亂數重複。目前全部還是 pending。']))
open(f'{N}/notesSlide100.xml', 'w').write(notes_xml(f'{N}/notesSlide99.xml', [
 '【English】',
 'This page fixes how every attack in this chapter behaves. The top row is today’s step attack: it always starts at 150 seconds and never stops. The second row is the irregular attacker on one node, drawn by our generator: it starts at a random time, attacks in bursts, pauses at random, and each burst has its own size — the taller the bar, the stronger the change.',
 'The third row is the multi-node case: compromised nodes arrive as a Poisson process — the gold ticks — and each one runs its own random schedule. They are never recovered within the run.',
 'The rules are in the table. Each burst lasts at least 3 seconds, longer than the 2-window persistence of the population check, so we do not just re-test the known one-window gap. Sizes use the same range as the step attacks. Lowering and raising are kept apart, one chart each.',
 'The irregular attacker does not know the threshold. The learning attacker under O-full sees its own verdicts, so it can learn it. Every irregular setting is repeated with 10 random seeds over the 56 sequences.',
 'One limit: a run is 300 seconds, so the arrival gaps of 30 to 120 seconds are a compressed-time stress test, not a claim about how often real nodes are compromised.',
 '【中文逐字稿】',
 '這頁固定本章所有攻擊的行為。第一列是目前的階躍攻擊：一律從 150 秒開始，之後不停。第二列是單一節點的不規則攻擊，由產生器實際畫出來：起點隨機、分段攻擊、隨機停頓，每段幅度不同，長條越高代表改得越多。',
 '第三列是多節點：被攻陷的節點依 Poisson 過程陸續出現，就是金色的刻度；每個節點有自己的隨機排程，run 內不會復原。',
 '規則在下面的表。每段攻擊至少 3 秒，比人數檢查的 2 窗持續門檻長，所以不只是重測已知的單窗缺口。幅度範圍和階躍攻擊相同。調低和調高分開，各自一張圖。',
 '不規則攻擊者不知道門檻；O-full 下的學習型攻擊者看得到自己的判定，所以可以學到門檻。每個不規則設定都用 10 組亂數、在 56 條序列上重複。',
 '限制：一個 run 只有 300 秒，所以 30 到 120 秒的到達間隔是壓縮時間尺度的壓力測試，不代表真實節點被攻陷的頻率。']))
open(f'{N}/_rels/notesSlide100.xml.rels', 'w').write(open(f'{N}/_rels/notesSlide99.xml.rels').read().replace('slide98.xml', 'slide99.xml'))
open(f'{U}/slides/_rels/slide99.xml.rels', 'w').write(open(f'{U}/slides/_rels/slide98.xml.rels').read().replace('notesSlide99.xml', 'notesSlide100.xml'))

# ---------- package bookkeeping: slide99 after slide46 ----------
ct = open(f'{U}/../[Content_Types].xml').read()
if 'slide99.xml' not in ct:
    ct = ct.replace('</Types>', '<Override PartName="/ppt/slides/slide99.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
                    '<Override PartName="/ppt/notesSlides/notesSlide100.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml"/></Types>')
    open(f'{U}/../[Content_Types].xml', 'w').write(ct)
pr = open(f'{U}/_rels/presentation.xml.rels').read()
if 'slides/slide99.xml' not in pr:
    pr = pr.replace('</Relationships>', '<Relationship Id="rId199" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide99.xml"/></Relationships>')
    open(f'{U}/_rels/presentation.xml.rels', 'w').write(pr)
p = open(f'{U}/presentation.xml').read()
rid46 = re.search(r'Id="(rId\d+)"[^>]*Target="slides/slide46.xml"|Target="slides/slide46.xml"[^>]*Id="(rId\d+)"', open(f'{U}/_rels/presentation.xml.rels').read())
rid46 = rid46.group(1) or rid46.group(2)
m = re.search(rf'<p:sldId id="(\d+)" r:id="{rid46}"/>', p)
if 'r:id="rId199"' not in p:
    newid = max(int(v) for v in re.findall(r'<p:sldId id="(\d+)"', p)) + 1
    p = p.replace(m.group(0), m.group(0) + f'<p:sldId id="{newid}" r:id="rId199"/>')
    p = p.replace(f'<p14:sldId id="{m.group(1)}"/>', f'<p14:sldId id="{m.group(1)}"/><p14:sldId id="{newid}"/>')
    open(f'{U}/presentation.xml', 'w').write(p)
print('v1.16 written')
