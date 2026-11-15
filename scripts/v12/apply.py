import sys; sys.path.insert(0, sys.argv[1])
import edits_a, edits_b, edits_c, edits_d
src = open("thesis_v11.md").read(); s = src
extra = [
 ("（多數時間僅由錨點回報者，即 mmWave 鏈路長期劣化者，判為 edge）", "（多數時間最後事件歸屬 LTE 者判為 edge；此與 mmWave 鏈路長期劣化相關，4.8.1）"),
 ("LTE-only（僅錨點回報）停留時間分布", "最後事件歸屬 LTE 之停留時間分布"),
]
bad = []
for i, (o, n) in enumerate(edits_a.E + edits_b.E + edits_c.E + edits_d.E + extra):
    c = s.count(o)
    if c != 1: bad.append((i, c, o[:80])); continue
    s = s.replace(o, n)
if bad:
    for b in bad: print("MISS", b)
    sys.exit(1)
k = s.count("LTE-only"); s = s.replace("LTE-only", "最後事件歸屬 LTE")
open("thesis_v12.md", "w").write(s)
print("edits", len(edits_a.E + edits_b.E + edits_c.E + edits_d.E + extra), "global LTE-only", k, "lines", s.count("\n"))
