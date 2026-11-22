# v1.19（2026-11-22）：由 v1.18 改第 52、55 頁之狀態文字與逐字稿（不放 D-30P1 數字）。用法：解開 v1.18 至 <dir>，python3 build_v119.py <dir>，再依原檔順序重新打包；第 55 頁狀態格之樣式對調另以一次性程式完成（見 commit 說明）。
import re, sys
from xml.sax.saxutils import escape as esc
U = sys.argv[1] + '/ppt/'
def sub(f, pairs):
    x = open(U + f, encoding='utf-8').read()
    for old, new in pairs:
        o = '<a:t>' + esc(old) + '</a:t>'
        assert x.count(o) == 1, (f, old[:60], x.count(o))
        x = x.replace(o, '<a:t>' + esc(new) + '</a:t>')
    open(U + f, 'w', encoding='utf-8').write(x)
# 第 55 頁
sub('slides/slide101.xml', [
 ('running · checks ≈ Nov 20 morning', 'done · gate passed'),
 ('Build check', 'D-30P1 data'),
 ('first batch (GCC 11) changed only SINR last digits in one trace → diagnosis only; rebuilt with GCC 13',
  're-collect (r11): a retransmitted packet keeps its first-send time; delay from effective samples only'),
 ('gate passed', 'done · 8 / 8 acceptance'),
 ('population, peer, mobility, fusion, admission, resource evaluation on D-30P',
  'population, peer, mobility, fusion, admission, resource evaluation on D-30P1'),
 ('≈ Nov 22', 'stopped · cause under check'),
 ('full PSRO: 9 detectors, 432 attacker best responses → Rule + DRL, Chart 2',
  'full PSRO + symmetric best responses (8 rule detectors, 384) → Rule + DRL, Chart 2'),
 ('≈ Nov 26–28', 'after the data is settled'),
 ('Every number marked “pre-correction” is replaced from D-30P.',
  'Peer check on D-30P1: too many clean false alarms, from a long delay tail; a small run now tests whether it is a simulator gap.'),
 ('Until then, phase-1 numbers (interval delay on the old data) appear only where labelled; dates are estimates from the current simulation speed.',
  'Until the data is settled, phase-1 numbers appear only where labelled, and no dates are given.'),
])
# 第 52 頁
sub('slides/slide53.xml', [
 ('D-30P (phase 2)', 'D-30P / D-30P1 (phase 2)'),
 ('collecting · replaces every number', 'collected · D-30P1 delay tail under check'),
 ('D-30P re-runs the same command line with per-cell counters, so ', 'D-30P re-runs the same command line with per-cell counters (old fields bit-identical to D-30); '),
 ('its old fields are bit-identical to D-30', 'D-30P1 changes the delay field by design'),
])
# 逐字稿：第 52 頁
sub('notesSlides/notesSlide52.xml', [
 ('【v1.18 addition】The field picture from the old “Field Behind Every Number” page is now here. Phase 2 re-collects the same eight runs as D-30P, with per-cell counters; its old fields match D-30 bit for bit, and every number in this chapter will be replaced from it.',
  '【v1.19 update】The field picture from the old “Field Behind Every Number” page is now here. Phase 2 re-collected the same eight runs twice. D-30P adds per-cell counters, and its old fields match D-30 bit for bit. D-30P1 goes one step further: a retransmitted packet keeps its first-send time, so the delay field changes on purpose and no longer matches D-30. D-30P1 currently shows a long delay tail that we are still checking, so no number in this chapter has been replaced yet.'),
 ('【v1.18 補充】原本「Field Behind Every Number」那頁的場域圖移到這裡。第二階段把同樣八個 run 重收成 D-30P，多了逐 cell 計數器；舊欄位與 D-30 逐位相同，本章所有數字之後都會改用它。',
  '【v1.19 更新】原本「Field Behind Every Number」那頁的場域圖移到這裡。第二階段把同樣八個 run 重收了兩次。D-30P 多了逐 cell 計數器，舊欄位與 D-30 逐位相同。D-30P1 再進一步：重傳的封包保留第一次傳送的時間，所以延遲欄位依設計改變，不再與 D-30 相同。D-30P1 目前有延遲長尾還在檢查，所以本章的數字都還沒有換掉。'),
])
# 逐字稿：第 55 頁
sub('notesSlides/notesSlide102.xml', [
 ('This page shows where the phase-2 rebuild stands. The new data, D-30P, re-runs D-30 with per-cell counters. A first batch built with GCC 11 changed only the last digits of SINR in one trace file, so we kept it for diagnosis and rebuilt with GCC 13; the GCC 13 build passed its gate, and the eight seeds are about a third of the way through.',
  'This page shows where the phase-2 rebuild stands. D-30P, the re-collection with per-cell counters, is done and passed its gate. We then collected D-30P1, where a retransmitted packet keeps its first-send time, so the delay includes the time spent waiting for retransmission. It passed acceptance on all eight seeds.'),
 ('The new input layer is written and passes its three checks on all eight diagnostic seeds. One design change: in the new data the LTE anchor lists all thirty UEs every window, so it becomes the reference set — the union of mmWave lists must equal it. More means inflation, fewer means deletion.',
  'The input layer and the population rule are unchanged: the LTE anchor lists all thirty UEs every window, so it is the reference set — the union of mmWave lists must equal it. More means inflation, fewer means deletion.'),
 ('Next come steps one to five, then the full PSRO with nine detectors. The dates are estimates from the current simulation speed.',
  'Steps one to five on D-30P1 stopped. On clean data the peer check raised far too many false alarms, because a small share of packets show delays of seconds to tens of seconds. Using the median UE instead of the mean per cell helped only a little. A small instrumented run now tests whether this tail comes from a gap in the simulator or is a normal result of this scenario. Until that is settled, PSRO and the symmetric best responses — eight distinct rule detectors, 384 best responses — do not start, and I give no dates.'),
 ('這頁說明第二階段重建的進度。新資料 D-30P 是用逐 cell 計數器把 D-30 重跑一次。第一批是 GCC 11 編的，只有一個 trace 檔的 SINR 末位數不同，所以留作診斷，改用 GCC 13 重編；GCC 13 版已通過閘門檢查，八個 seed 大約跑了三分之一。',
  '這頁說明第二階段重建的進度。D-30P（加逐 cell 計數器的重收）已完成並通過閘門檢查。之後又收了 D-30P1：重傳的封包保留第一次傳送的時間，所以延遲包含等待重傳的時間。八個 seed 都通過驗收。'),
 ('新輸入層已經寫好，在八個診斷 seed 上三項檢查全部通過。有一個設計改變：新資料裡 LTE 錨點每一窗都列出全部 30 個 UE，所以錨點改成參照集合，mmWave 名單的聯集必須等於它；多了是灌水，少了是刪除。',
  '輸入層與人數規則不變：LTE 錨點每一窗都列出全部 30 個 UE，所以錨點是參照集合，mmWave 名單的聯集必須等於它；多了是灌水，少了是刪除。'),
 ('接下來是第 1 到 5 步，然後是 9 個偵測端的完整 PSRO。日期是依目前模擬速度估的。',
  '在 D-30P1 上的第 1 到 5 步停住了。乾淨資料上，同儕檢查的誤報太多，原因是少數封包的延遲長達幾秒到幾十秒。把每個 cell 的代表值從 UE 平均改成 UE 中位數，只改善一點。現在用一個加了觀測輸出的小型模擬，檢查這段長尾是模擬器的缺陷，還是這個情境本來就會發生。確定之前，PSRO 和對稱最佳回應（8 個不同的規則偵測端、384 個最佳回應）都不開始，也不給日期。'),
])
print('edits OK')
