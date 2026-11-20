#!/usr/bin/env python3
"""r10 = r9-g13 + RLC AM retransmission timestamp (observation only; default ZT_R10_RETX_TAG=0 == r9 bit-identical).
Apply to a copy of r9-g13:  patch_r10.py <ns3_dir>
Cause (diagnosed 2026-11-20): the new PDU is copied into the txedBuffer BEFORE its RlcTag byte tag is added (lte-rlc-am.cc),
so every retransmitted PDU/segment reaches the receiver without a tag and LteRlcAm::DoReceivePdu reports delay = 0
(zero-delay PDUs == PDUs without RlcTag in all 8 D-30P seeds; DL mmWave share 13.5-20.8 %).
  ZT_R10_RETX_TAG=0  unchanged (r9)
  ZT_R10_RETX_TAG=1  the stored copy carries the first-transmission timestamp; a retransmission reports now - first Tx time
                     (includes the wait for the retransmission)
  ZT_R10_RETX_TAG=2  each retransmission is re-stamped at its own transmission; reports the delay of that attempt only
Byte tags do not affect simulation behaviour, so modes 1/2 must leave every non-delay output identical to mode 0."""
import sys
root = sys.argv[1].rstrip('/') + '/src/'
def rd(n): return open(root + n).read()
def wr(n, s): open(root + n, 'w').write(s)
def once(s, old, new):
    assert s.count(old) == 1, (old[:90], s.count(old)); return s.replace(old, new)

n = 'lte/model/lte-rlc-am.cc'; s = rd(n); assert 'R9 O-4' in s and 'R10' not in s
s = once(s, 'int g_r9RlcRxTagFound = -1;',
 'int g_r9RlcRxTagFound = -1;\n'
 '// R10: retransmission timestamp mode (0 = r9; 1 = keep first-Tx timestamp; 2 = re-stamp at each retransmission)\n'
 'static int\nR10RetxTagMode()\n{\n    static const int m = []() {\n        const char* e = std::getenv("ZT_R10_RETX_TAG");\n'
 '        return e ? std::atoi(e) : 0;\n    }();\n    return m;\n}')
s = once(s, '    m_txedBuffer.at(rlcAmHeader.GetSequenceNumber().GetValue()).m_pdu = packet->Copy();\n',
 '    if (R10RetxTagMode() == 1)\n    {\n        RlcTag r10Tag(Simulator::Now()); // R10: stored copy carries the first-Tx timestamp\n'
 '        packet->AddByteTag(r10Tag);\n    }\n'
 '    m_txedBuffer.at(rlcAmHeader.GetSequenceNumber().GetValue()).m_pdu = packet->Copy();\n')
s = once(s, '    // Sender timestamp\n    RlcTag rlcTag(Simulator::Now());\n    packet->AddByteTag(rlcTag);\n',
 '    // Sender timestamp\n    RlcTag rlcTag(Simulator::Now());\n    if (R10RetxTagMode() != 1) // R10: mode 1 already tagged before the copy\n    {\n        packet->AddByteTag(rlcTag);\n    }\n')
s = once(s, '                    packet->AddHeader(rlcAmHeader);\n                    NS_LOG_LOGIC("new AM RLC header: " << rlcAmHeader);\n',
 '                    packet->AddHeader(rlcAmHeader);\n                    NS_LOG_LOGIC("new AM RLC header: " << rlcAmHeader);\n'
 '                    if (R10RetxTagMode() == 2)\n                    {\n                        RlcTag r10Tag(Simulator::Now()); // R10 mode 2\n                        packet->AddByteTag(r10Tag);\n                    }\n')
s = once(s, '                    nextSeg->AddHeader(nextSegHdr);\n',
 '                    nextSeg->AddHeader(nextSegHdr);\n'
 '                    if (R10RetxTagMode() == 2)\n                    {\n                        RlcTag r10Tag(Simulator::Now()); // R10 mode 2 (first segment sent now)\n                        firstSeg->AddByteTag(r10Tag);\n                    }\n')
s = once(s, '#include "ns3/abort.h"\n', '#include "ns3/abort.h"\n#include <cstdlib>\n')
wr(n, s)
print("r10 patch applied")
