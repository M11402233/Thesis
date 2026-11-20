#!/usr/bin/env python3
"""r10t = r10 + per-PDU trace (ZT_R10_TRACE=1 -> R10_trace.txt in cwd). Observation only; apply to a COPY of r10.
Lines:  T <ns> <rnti> <lcid> <kind N|R|S> <sn> <size> <tagFound> <tagTimeNs>        (RLC AM data PDU sent)
        R <ns> <rnti> <lcid> <size> <tagFound> <tagTimeNs> <delayNs> <isData> <sn> <segFlag> <lastSeg> <segOff>   (received)
Kind N = new PDU; R = whole-PDU retransmission; S = first segment of a re-segmented retransmission."""
import sys
root = sys.argv[1].rstrip('/') + '/src/'
def rd(n): return open(root + n).read()
def wr(n, s): open(root + n, 'w').write(s)
def once(s, old, new):
    assert s.count(old) == 1, (old[:90], s.count(old)); return s.replace(old, new)
n = 'lte/model/lte-rlc-am.cc'; s = rd(n); assert 'R10RetxTagMode' in s and 'R10Trace' not in s
s = once(s, '#include <cstdlib>\n', '#include <cstdlib>\n#include <fstream>\n')
s = once(s, 'static int\nR10RetxTagMode()',
 'static std::ofstream*\nR10Trace()\n{\n    static std::ofstream* f = std::getenv("ZT_R10_TRACE") ? new std::ofstream("R10_trace.txt") : nullptr;\n    return f;\n}\n\n'
 'int64_t g_r10RxTagT = -1;\nint g_r10RxSn = -1, g_r10RxSeg = -1, g_r10RxSegOff = -1;\n\n'
 'static int\nR10RetxTagMode()')
# TX new
s = once(s, '        packet->AddByteTag(rlcTag);\n    }\n    m_txPdu(m_rnti, m_lcid, packet->GetSize());\n',
 '        packet->AddByteTag(rlcTag);\n    }\n'
 '    if (auto* tf = R10Trace())\n    {\n        RlcTag q;\n        bool has = packet->FindFirstMatchingByteTag(q);\n'
 '        *tf << "T\\t" << Simulator::Now().GetNanoSeconds() << "\\t" << m_rnti << "\\t" << (uint32_t)m_lcid << "\\tN\\t"\n'
 '            << rlcAmHeader.GetSequenceNumber().GetValue() << "\\t" << packet->GetSize() << "\\t" << has << "\\t"\n'
 '            << (has ? q.GetSenderTimestamp().GetNanoSeconds() : -1) << "\\t" << packet->GetUid() << "\\t" << m_imsi << "\\n";\n    }\n'
 '    m_txPdu(m_rnti, m_lcid, packet->GetSize());\n')
# TX retx whole
s = once(s, '                    m_macSapProvider->TransmitPdu(params);\n\n                    m_retxBuffer.at(seqNumberValue).m_retxCount++;\n',
 '                    if (auto* tf = R10Trace())\n                    {\n                        RlcTag q;\n                        bool has = packet->FindFirstMatchingByteTag(q);\n'
 '                        *tf << "T\\t" << Simulator::Now().GetNanoSeconds() << "\\t" << m_rnti << "\\t" << (uint32_t)m_lcid << "\\tR\\t"\n'
 '                            << seqNumberValue << "\\t" << packet->GetSize() << "\\t" << has << "\\t"\n'
 '                            << (has ? q.GetSenderTimestamp().GetNanoSeconds() : -1) << "\\t" << packet->GetUid() << "\\t" << m_imsi << "\\n";\n                    }\n'
 '                    m_macSapProvider->TransmitPdu(params);\n\n                    m_retxBuffer.at(seqNumberValue).m_retxCount++;\n')
# TX retx first segment
s = once(s, '                    nextSeg->AddHeader(nextSegHdr);\n',
 '                    nextSeg->AddHeader(nextSegHdr);\n'
 '                    if (auto* tf = R10Trace())\n                    {\n                        RlcTag q;\n                        bool has = firstSeg->FindFirstMatchingByteTag(q);\n'
 '                        *tf << "T\\t" << Simulator::Now().GetNanoSeconds() << "\\t" << m_rnti << "\\t" << (uint32_t)m_lcid << "\\tS\\t"\n'
 '                            << seqNumberValue << "\\t" << firstSeg->GetSize() << "\\t" << has << "\\t"\n'
 '                            << (has ? q.GetSenderTimestamp().GetNanoSeconds() : -1) << "\\t" << firstSeg->GetUid() << "\\t" << m_imsi << "\\n";\n                    }\n')
# RX (calculator-level, with cell / IMSI): globals valid only during m_rxPdu
s = once(s, '    g_r9RlcRxTagFound = r7bFound ? 1 : 0; // R9 O-4 (read-only)\n',
 '    const int r10cDec = g_r11Dec, r10cEff = g_r11Eff, r10cPart = g_r11Part, r10cLen = g_r11Len, r10cNew = g_r11New; // r11 預測值（m_rxPdu 後被重置）\n'
 '    if (R10Trace())\n    {\n        LteRlcAmHeader r10g;\n        rxPduParams.p->PeekHeader(r10g);\n'
 '        g_r10RxTagT = r7bFound ? rlcTag.GetSenderTimestamp().GetNanoSeconds() : -1;\n'
 '        g_r10RxSn = r10g.IsDataPdu() ? (int)r10g.GetSequenceNumber().GetValue() : -1;\n'
 '        g_r10RxSeg = r10g.IsDataPdu() ? (int)r10g.GetResegmentationFlag() : -1;\n'
 '        g_r10RxSegOff = r10g.IsDataPdu() ? (int)r10g.GetSegmentOffset() : -1;\n    }\n'
 '    g_r9RlcRxTagFound = r7bFound ? 1 : 0; // R9 O-4 (read-only)\n')
# RX
s = once(s, '    g_r9RlcRxTagFound = -1; // R9 O-4\n',
 '    g_r9RlcRxTagFound = -1; // R9 O-4\n    g_r10RxTagT = -1; g_r10RxSn = g_r10RxSeg = g_r10RxSegOff = -1;\n'
 '    if (auto* tf = R10Trace())\n    {\n        LteRlcAmHeader r10h;\n        rxPduParams.p->PeekHeader(r10h);\n        bool isData = r10h.IsDataPdu();\n'
 '        *tf << "R\\t" << Simulator::Now().GetNanoSeconds() << "\\t" << m_rnti << "\\t" << (uint32_t)m_lcid << "\\t"\n'
 '            << rxPduParams.p->GetSize() << "\\t" << r7bFound << "\\t" << (r7bFound ? rlcTag.GetSenderTimestamp().GetNanoSeconds() : -1)\n'
 '            << "\\t" << delay.GetNanoSeconds() << "\\t" << isData << "\\t"\n'
 '            << (isData ? (int)r10h.GetSequenceNumber().GetValue() : -1) << "\\t"\n'
 '            << (isData ? (int)r10h.GetResegmentationFlag() : -1) << "\\t" << (isData ? (int)r10h.GetLastSegmentFlag() : -1) << "\\t"\n'
 '            << (isData ? (int)r10h.GetSegmentOffset() : -1) << "\\t" << rxPduParams.p->GetUid() << "\\n";\n    }\n')
# 接收端判定（只讀；2026-11-20 使用者要求先確認分段與部分重疊之判定）：
#  W 窗外丟棄｜DW 整包重複（SN 已在緩衝區，非分段）｜AS 分段接續（offset == 前段 lastOffset）
#  OE 分段不接續且 PDU 未完整 → 清除該 SN 之緩衝｜OI 分段不接續且 PDU 已完整 → 忽略
#  AN 新 SN 且 offset 0 → 放入緩衝｜DO 新 SN 但 offset > 0 → 忽略
s = once(s, '        if (!IsInsideReceivingWindow(seqNumber))\n        {\n            NS_LOG_LOGIC("PDU discarded");\n            return;\n        }\n',
 '        const char* r10dec = "?";\n'
 '        auto r10emit = [&]() {\n            if (auto* tf = R10Trace())\n            {\n'
 '                *tf << "D\\t" << Simulator::Now().GetNanoSeconds() << "\\t" << m_rnti << "\\t" << (uint32_t)m_lcid << "\\t" << m_imsi\n'
 '                    << "\\t" << seqNumber.GetValue() << "\\t" << (r7bFound ? rlcTag.GetSenderTimestamp().GetNanoSeconds() : -1)\n'
 '                    << "\\t" << (uint32_t)rlcAmHeader.GetResegmentationFlag() << "\\t" << rlcAmHeader.GetSegmentOffset()\n'
 '                    << "\\t" << rlcAmHeader.GetLastOffset() << "\\t" << (uint32_t)rlcAmHeader.GetLastSegmentFlag() << "\\t" << r10dec << "\\t" << r10cDec << "\\t" << r10cEff << "\\t" << r10cPart << "\\t" << r10cLen << "\\t" << r10cNew << "\\t" << rxPduParams.p->GetSize() << "\\t" << rlcAmHeader.GetSerializedSize() << "\\n";\n'
 '            }\n        };\n'
 '        if (!IsInsideReceivingWindow(seqNumber))\n        {\n            NS_LOG_LOGIC("PDU discarded");\n            r10dec = "W"; r10emit();\n            return;\n        }\n')
s = once(s, '                NS_LOG_LOGIC("Received duplicate SN");\n',
 '                NS_LOG_LOGIC("Received duplicate SN");\n                r10dec = "DW";\n')
s = once(s, '                        // segment is next in sequence\n',
 '                        // segment is next in sequence\n                        r10dec = "AS";\n')
s = once(s, '                        if (it->second.m_pduComplete == false)\n                        {\n                            m_rxonBuffer.erase(it);\n',
 '                        r10dec = "OI";\n                        if (it->second.m_pduComplete == false)\n                        {\n                            r10dec = "OE";\n                            m_rxonBuffer.erase(it);\n')
s = once(s, '                if (rlcAmHeader.GetSegmentOffset() == 0)\n                {\n                    NS_LOG_LOGIC("Place PDU in the reception buffer',
 '                r10dec = "DO";\n                if (rlcAmHeader.GetSegmentOffset() == 0)\n                {\n                    r10dec = "AN";\n                    NS_LOG_LOGIC("Place PDU in the reception buffer')
s = once(s, '        // 5.1.3.2.3 Actions when a RLC data PDU is placed in the reception buffer\n',
 '        r10emit();\n\n        // 5.1.3.2.3 Actions when a RLC data PDU is placed in the reception buffer\n')
wr(n, s)
n = 'lte/helper/mmwave-bearer-stats-calculator.cc'; s = rd(n)
s = once(s, 'extern int g_r9RlcRxTagFound; // R9 O-4 (defined in lte-rlc-am.cc)\n',
 'extern int g_r9RlcRxTagFound; // R9 O-4 (defined in lte-rlc-am.cc)\n'
 'extern int64_t g_r10RxTagT; // R10 trace (defined in lte-rlc-am.cc)\nextern int g_r10RxSn, g_r10RxSeg, g_r10RxSegOff;\n'
 'static std::ofstream*\nR10CalcTrace()\n{\n    static std::ofstream* f = std::getenv("ZT_R10_TRACE") ? new std::ofstream("R10_trace_calc.txt") : nullptr;\n    return f;\n}\n')
s = once(s, '              if (g_r9RlcRxTagFound == 0) a.nNoTag++; else if (g_r9RlcRxTagFound < 0) a.nUnknown++; } // R9 O-4\n',
 '              if (g_r9RlcRxTagFound == 0) a.nNoTag++; else if (g_r9RlcRxTagFound < 0) a.nUnknown++; } // R9 O-4\n'
 '            if (auto* tf = R10CalcTrace())\n            {\n'
 '                *tf << "C\\t" << this << "\\t" << Simulator::Now().GetNanoSeconds() << "\\t" << cellId << "\\t" << imsi << "\\t" << rnti\n'
 '                    << "\\t" << (uint32_t)lcid << "\\t" << packetSize << "\\t" << delay << "\\t" << g_r9RlcRxTagFound << "\\t" << g_r10RxTagT\n'
 '                    << "\\t" << g_r10RxSn << "\\t" << g_r10RxSeg << "\\t" << g_r10RxSegOff << "\\n";\n            }\n')
if '#include <fstream>' not in s:
    s = once(s, '#include <algorithm>\n', '#include <algorithm>\n#include <cstdlib>\n#include <fstream>\n')
wr(n, s); print("r10 trace patch applied")
