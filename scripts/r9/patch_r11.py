#!/usr/bin/env python3
"""r11 = r10 + 有效延遲樣本統計（D30P1_r10_recollection_spec.md §6.1；2026-11-20）。
只新增一個檔 DlE2RlcStats_r11eff.txt；既有輸出（含 r10 模式 1 之延遲）逐位不變，須以驗證確認。
有效延遲樣本 = 資料 PDU 且 有時間戳 且 帶新位元組（每個 (SN, 首次傳送時間) 實例之已收位元組聯集，與接收端緩衝無關）
              且 接收端判定為 AN／AS（實際放入緩衝）。判定於 m_rxPdu 之前以唯讀方式預測，須與實際分支逐筆相符（追蹤驗證）。
位元組範圍 = [segOffset, segOffset + p.size − headerLength)；整包 PDU 之 GetLastOffset 為 0xffff，不可用。
判定碼：0 AN 新 SN 且 offset 0｜1 AS 接續｜2 DW 整包重複｜3 OI 不接續且 PDU 已完整｜4 OE 不接續且未完整（清緩衝）｜5 DO 新 SN 但 offset>0｜6 W 窗外
用法：patch_r11.py <ns3_dir>（r10 樹之複本）"""
import sys
root = sys.argv[1].rstrip('/') + '/src/'
def rd(n): return open(root + n).read()
def wr(n, s): open(root + n, 'w').write(s)
def once(s, old, new):
    assert s.count(old) == 1, (old[:90], s.count(old)); return s.replace(old, new)

# ---- lte-rlc-am.h：覆蓋記錄成員
n = 'lte/model/lte-rlc-am.h'; s = rd(n); assert 'R11' not in s
s = once(s, '    std::map<uint16_t, PduBuffer> m_rxonBuffer; ///< Reception buffer\n',
 '    std::map<uint16_t, PduBuffer> m_rxonBuffer; ///< Reception buffer\n'
 '    // R11: 已收位元組聯集，鍵 = (SN, 首次傳送時間 ns)；與 m_rxonBuffer 無關（緩衝被清除不得遺忘）\n'
 '    std::map<std::pair<uint16_t, int64_t>, std::vector<std::pair<uint32_t, uint32_t>>> m_r11Cov;\n')
wr(n, s)

# ---- lte-rlc-am.cc
n = 'lte/model/lte-rlc-am.cc'; s = rd(n); assert 'g_r11' not in s
s = once(s, 'int g_r9RlcRxTagFound = -1;',
 'int g_r9RlcRxTagFound = -1;\n'
 '// R11（唯讀預測；於 m_rxPdu 回呼期間有效，之後重置為 -1）\n'
 'int g_r11Eff = -1;      // -1 控制 PDU／未知；0 資料但非有效樣本；1 有效延遲樣本\n'
 'int g_r11Dec = -1;      // 判定碼（見 patch_r11.py）\n'
 'int g_r11Part = 0;      // 有效樣本且部分重疊（部分位元組已收過）\n'
 'int g_r11Empty = 0;     // 資料 PDU 但無資料位元組\n'
 'int g_r11Len = 0, g_r11New = 0;')
prelude = '''    // R11: 有效延遲樣本判定（唯讀；與下方實際接收分支逐筆對照於追蹤驗證）
    g_r11Eff = -1; g_r11Dec = -1; g_r11Part = 0; g_r11Empty = 0; g_r11Len = 0; g_r11New = 0;
    {
        LteRlcAmHeader r11h;
        rxPduParams.p->PeekHeader(r11h);
        if (r11h.IsDataPdu())
        {
            const SequenceNumber10 r11sn = r11h.GetSequenceNumber();
            const uint32_t r11a = r11h.GetSegmentOffset();
            const uint32_t r11sz = rxPduParams.p->GetSize();
            const uint32_t r11b = r11a + (r11sz > r11h.GetSerializedSize() ? r11sz - r11h.GetSerializedSize() : 0);
            int dec;
            if (!IsInsideReceivingWindow(r11sn))
            {
                dec = 6;
            }
            else
            {
                auto r11it = m_rxonBuffer.find(r11sn.GetValue());
                if (r11it != m_rxonBuffer.end())
                {
                    if (r11h.GetResegmentationFlag() == LteRlcAmHeader::SEGMENT)
                    {
                        LteRlcAmHeader r11last;
                        r11it->second.m_byteSegments.back()->PeekHeader(r11last);
                        if (r11h.GetSegmentOffset() == r11last.GetLastOffset() ||
                            r11h.GetSegmentOffset() + 32768 == r11last.GetLastOffset())
                        {
                            dec = 1;
                        }
                        else
                        {
                            dec = (r11it->second.m_pduComplete == false) ? 4 : 3;
                        }
                    }
                    else
                    {
                        dec = 2;
                    }
                }
                else
                {
                    dec = (r11h.GetSegmentOffset() == 0) ? 0 : 5;
                }
            }
            g_r11Dec = dec;
            g_r11Len = (int)(r11b - r11a);
            g_r11Empty = (r11b <= r11a) ? 1 : 0;
            bool r11eff = false;
            if (r7bFound && r11b > r11a)
            {
                auto& cov = m_r11Cov[std::make_pair((uint16_t)r11sn.GetValue(), (int64_t)rlcTag.GetSenderTimestamp().GetNanoSeconds())];
                uint32_t inter = 0;
                for (const auto& iv : cov)
                {
                    const uint32_t lo = std::max(iv.first, r11a), hi = std::min(iv.second, r11b);
                    if (hi > lo) inter += hi - lo;
                }
                g_r11New = (int)((r11b - r11a) - inter);
                // 聯集更新（不論接收端是否接受；與追蹤分析之定義一致）
                std::vector<std::pair<uint32_t, uint32_t>> merged;
                uint32_t na = r11a, nb = r11b; bool placed = false;
                for (const auto& iv : cov)
                {
                    if (iv.second < na) merged.push_back(iv);
                    else if (iv.first > nb) { if (!placed) { merged.emplace_back(na, nb); placed = true; } merged.push_back(iv); }
                    else { na = std::min(na, iv.first); nb = std::max(nb, iv.second); }
                }
                if (!placed) merged.emplace_back(na, nb);
                cov.swap(merged);
                r11eff = (g_r11New > 0) && (dec == 0 || dec == 1);
                g_r11Part = (r11eff && g_r11New < g_r11Len) ? 1 : 0;
                if (m_r11Cov.size() > 4096)
                {
                    // 上界：窗外之 SN 不可能再被接受，清除其覆蓋記錄（確定性）
                    for (auto it2 = m_r11Cov.begin(); it2 != m_r11Cov.end();)
                    {
                        if (!IsInsideReceivingWindow(SequenceNumber10(it2->first.first))) it2 = m_r11Cov.erase(it2);
                        else ++it2;
                    }
                }
            }
            g_r11Eff = r11eff ? 1 : 0;
        }
    }
'''
s = once(s, '    g_r9RlcRxTagFound = r7bFound ? 1 : 0; // R9 O-4 (read-only)\n',
 prelude + '    g_r9RlcRxTagFound = r7bFound ? 1 : 0; // R9 O-4 (read-only)\n')
s = once(s, '    g_r9RlcRxTagFound = -1; // R9 O-4\n',
 '    g_r9RlcRxTagFound = -1; // R9 O-4\n    g_r11Eff = -1; g_r11Dec = -1; g_r11Part = 0; g_r11Empty = 0; g_r11Len = 0; g_r11New = 0;\n')
wr(n, s)

# ---- mmwave-bearer-stats-calculator.h / .cc
n = 'lte/helper/mmwave-bearer-stats-calculator.h'; s = rd(n); assert 'R11' not in s
s = once(s, '    std::map<R5CellKey, R9RxAcc> m_r9DlRx; //!< R9 O-4 (cumulative)\n',
 '    std::map<R5CellKey, R9RxAcc> m_r9DlRx; //!< R9 O-4 (cumulative)\n'
 '    struct R11Acc { uint64_t nRx{0}, nData{0}, nDataNoTag{0}, nDataEmpty{0}, nEff{0}, delaySumEff{0}, nPart{0}, delaySumPart{0}, dec[7]{0, 0, 0, 0, 0, 0, 0}; };\n'
 '    std::map<R5CellKey, R11Acc> m_r11DlEff; //!< R11 有效延遲樣本（累計）\n'
 '    bool m_firstR11Write{true};\n')
wr(n, s)
n = 'lte/helper/mmwave-bearer-stats-calculator.cc'; s = rd(n)
s = once(s, 'extern int g_r9RlcRxTagFound; // R9 O-4 (defined in lte-rlc-am.cc)\n',
 'extern int g_r9RlcRxTagFound; // R9 O-4 (defined in lte-rlc-am.cc)\n'
 'extern int g_r11Eff, g_r11Dec, g_r11Part, g_r11Empty; // R11 (defined in lte-rlc-am.cc)\n')
s = once(s, '              if (g_r9RlcRxTagFound == 0) a.nNoTag++; else if (g_r9RlcRxTagFound < 0) a.nUnknown++; } // R9 O-4\n',
 '              if (g_r9RlcRxTagFound == 0) a.nNoTag++; else if (g_r9RlcRxTagFound < 0) a.nUnknown++; } // R9 O-4\n'
 '            { R11Acc& e = m_r11DlEff[R5CellKey{cellId, imsi, lcid}]; e.nRx++; // R11\n'
 '              if (g_r11Eff >= 0)\n              {\n'
 '                  e.nData++; if (g_r9RlcRxTagFound == 0) e.nDataNoTag++; if (g_r11Empty) e.nDataEmpty++;\n'
 '                  if (g_r11Dec >= 0 && g_r11Dec < 7) e.dec[g_r11Dec]++;\n'
 '                  if (g_r11Eff == 1) { e.nEff++; e.delaySumEff += delay; if (g_r11Part) { e.nPart++; e.delaySumPart += delay; } }\n'
 '              } }\n')
s = once(s, '        std::ofstream ls;\n        if (m_firstR9LastSetWrite)\n',
 '        std::ofstream ef;\n'
 '        if (m_firstR11Write)\n        {\n            ef.open((base + "_r11eff.txt").c_str());\n'
 '            ef << "% start\\tend\\tEventCellId\\tIMSI\\tLCID\\tnRxPDUs\\tnDataPDUs\\tnDataNoTag\\tnDataEmpty\\tnEffSamples\\tdelaySumEffNs\\tnEffPartial\\tdelaySumPartialNs"\n'
 '               << "\\tnDecAN\\tnDecAS\\tnDecDW\\tnDecOI\\tnDecOE\\tnDecDO\\tnDecW" << std::endl;\n'
 '            m_firstR11Write = false;\n        }\n        else\n        {\n            ef.open((base + "_r11eff.txt").c_str(), std::ios_base::app);\n        }\n'
 '        for (auto& kv : m_r11DlEff)\n        {\n'
 '            const R11Acc& e = kv.second;\n'
 '            ef << m_startTime.GetNanoSeconds() << "\\t" << endTime.GetNanoSeconds() << "\\t" << kv.first.cell << "\\t" << kv.first.imsi << "\\t"\n'
 '               << (uint32_t)kv.first.lcid << "\\t" << e.nRx << "\\t" << e.nData << "\\t" << e.nDataNoTag << "\\t" << e.nDataEmpty << "\\t" << e.nEff\n'
 '               << "\\t" << e.delaySumEff << "\\t" << e.nPart << "\\t" << e.delaySumPart;\n'
 '            for (int i = 0; i < 7; ++i) ef << "\\t" << e.dec[i];\n'
 '            ef << std::endl;\n        }\n        ef.close();\n'
 '        std::ofstream ls;\n        if (m_firstR9LastSetWrite)\n')
wr(n, s)
print("r11 patch applied")
