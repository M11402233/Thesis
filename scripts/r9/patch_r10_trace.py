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
 'static int\nR10RetxTagMode()')
# TX new
s = once(s, '        packet->AddByteTag(rlcTag);\n    }\n    m_txPdu(m_rnti, m_lcid, packet->GetSize());\n',
 '        packet->AddByteTag(rlcTag);\n    }\n'
 '    if (auto* tf = R10Trace())\n    {\n        RlcTag q;\n        bool has = packet->FindFirstMatchingByteTag(q);\n'
 '        *tf << "T\\t" << Simulator::Now().GetNanoSeconds() << "\\t" << m_rnti << "\\t" << (uint32_t)m_lcid << "\\tN\\t"\n'
 '            << rlcAmHeader.GetSequenceNumber().GetValue() << "\\t" << packet->GetSize() << "\\t" << has << "\\t"\n'
 '            << (has ? q.GetSenderTimestamp().GetNanoSeconds() : -1) << "\\t" << packet->GetUid() << "\\n";\n    }\n'
 '    m_txPdu(m_rnti, m_lcid, packet->GetSize());\n')
# TX retx whole
s = once(s, '                    m_macSapProvider->TransmitPdu(params);\n\n                    m_retxBuffer.at(seqNumberValue).m_retxCount++;\n',
 '                    if (auto* tf = R10Trace())\n                    {\n                        RlcTag q;\n                        bool has = packet->FindFirstMatchingByteTag(q);\n'
 '                        *tf << "T\\t" << Simulator::Now().GetNanoSeconds() << "\\t" << m_rnti << "\\t" << (uint32_t)m_lcid << "\\tR\\t"\n'
 '                            << seqNumberValue << "\\t" << packet->GetSize() << "\\t" << has << "\\t"\n'
 '                            << (has ? q.GetSenderTimestamp().GetNanoSeconds() : -1) << "\\t" << packet->GetUid() << "\\n";\n                    }\n'
 '                    m_macSapProvider->TransmitPdu(params);\n\n                    m_retxBuffer.at(seqNumberValue).m_retxCount++;\n')
# TX retx first segment
s = once(s, '                    nextSeg->AddHeader(nextSegHdr);\n',
 '                    nextSeg->AddHeader(nextSegHdr);\n'
 '                    if (auto* tf = R10Trace())\n                    {\n                        RlcTag q;\n                        bool has = firstSeg->FindFirstMatchingByteTag(q);\n'
 '                        *tf << "T\\t" << Simulator::Now().GetNanoSeconds() << "\\t" << m_rnti << "\\t" << (uint32_t)m_lcid << "\\tS\\t"\n'
 '                            << seqNumberValue << "\\t" << firstSeg->GetSize() << "\\t" << has << "\\t"\n'
 '                            << (has ? q.GetSenderTimestamp().GetNanoSeconds() : -1) << "\\t" << firstSeg->GetUid() << "\\n";\n                    }\n')
# RX
s = once(s, '    g_r9RlcRxTagFound = -1; // R9 O-4\n',
 '    g_r9RlcRxTagFound = -1; // R9 O-4\n'
 '    if (auto* tf = R10Trace())\n    {\n        LteRlcAmHeader r10h;\n        rxPduParams.p->PeekHeader(r10h);\n        bool isData = r10h.IsDataPdu();\n'
 '        *tf << "R\\t" << Simulator::Now().GetNanoSeconds() << "\\t" << m_rnti << "\\t" << (uint32_t)m_lcid << "\\t"\n'
 '            << rxPduParams.p->GetSize() << "\\t" << r7bFound << "\\t" << (r7bFound ? rlcTag.GetSenderTimestamp().GetNanoSeconds() : -1)\n'
 '            << "\\t" << delay.GetNanoSeconds() << "\\t" << isData << "\\t"\n'
 '            << (isData ? (int)r10h.GetSequenceNumber().GetValue() : -1) << "\\t"\n'
 '            << (isData ? (int)r10h.GetResegmentationFlag() : -1) << "\\t" << (isData ? (int)r10h.GetLastSegmentFlag() : -1) << "\\t"\n'
 '            << (isData ? (int)r10h.GetSegmentOffset() : -1) << "\\t" << rxPduParams.p->GetUid() << "\\n";\n    }\n')
wr(n, s); print("r10 trace patch applied")
