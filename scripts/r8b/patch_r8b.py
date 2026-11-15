#!/usr/bin/env python3
"""r8b: guard for the null m_keepS0Reassemble crash in LteRlcAm::Reassemble (handover forwarding).
Usage: patch_r8b.py <ns3_dir>.  Diagnostic build: the guard only fires where the original dereferences
a null pointer (no-loss, WAITING_SI_SF, FI = NO_FIRST_BYTE|*, no kept S0); it then treats the PDU as
'with loss' (headless fragment discarded) and prints one ZT_R8B_GUARD line to stderr."""
import sys, re
p = sys.argv[1].rstrip('/') + '/src/lte/model/lte-rlc-am.cc'
s = open(p).read()
assert 'ZT_R8B' not in s, 'already patched'
a = s.index('\nLteRlcAm::Reassemble(Ptr<Packet> packet)\n'); b = s.index('\nLteRlcAm::CreateRlcSduBuffer()')
f = s[a:b]
o1 = '    bool expectedSnLost;\n'
assert f.count(o1) == 1
f = f.replace(o1, o1 + '    const uint16_t ztPrevExpected = m_reassembleExpectedSeqNumber.GetValue(); // ZT_R8B\n')
o2 = '    if (!expectedSnLost)\n    {\n        NS_LOG_DEBUG("Reassembling NO LOSS ");\n'
assert f.count(o2) == 1
g = r'''    // ZT_R8B guard: no kept S0 while waiting for a continuation -> the original dereferences a null Ptr.
    if (!expectedSnLost && m_assemblingState == WAITING_SI_SF && !m_keepS0Reassemble &&
        (framingInfo == (LteRlcAmHeader::NO_FIRST_BYTE | LteRlcAmHeader::LAST_BYTE) ||
         framingInfo == (LteRlcAmHeader::NO_FIRST_BYTE | LteRlcAmHeader::NO_LAST_BYTE)))
    {
        std::cerr << "ZT_R8B_GUARD t=" << Simulator::Now().GetSeconds() << " rnti=" << m_rnti
                  << " lcid=" << (uint32_t)m_lcid << " sn=" << currSeqNumber.GetValue()
                  << " prevExpected=" << ztPrevExpected << " fi=" << (uint32_t)framingInfo
                  << " nSdu=" << m_sdusAssembleBuffer.size() << " vtA=" << m_vtA.GetValue()
                  << " vtS=" << m_vtS.GetValue() << " entryState=" << g_ztEntryState << " snlist=";
        for (auto v : g_ztSnList)
        {
            std::cerr << v << ",";
        }
        std::cerr << std::endl;
        expectedSnLost = true;
    }
'''
f = f.replace(o2, g + o2)
s = s[:a] + f + s[b:]
# file-scope diagnostics + fill in RlcPdusToRlcSdus
o3 = '\nvoid\nLteRlcAm::Reassemble(Ptr<Packet> packet)\n'
assert s.count(o3) == 1
s = s.replace(o3, '\nstatic std::vector<uint16_t> g_ztSnList; // ZT_R8B diagnostics\nstatic int g_ztEntryState = -1;\n' + o3)
o4 = '    uint16_t isGotExpectedSeqNumber = 0;\n    for (std::vector<LteRlcAm::RetxPdu>::iterator it = RlcPdus.begin(); it != RlcPdus.end(); it++)\n    {\n'
assert s.count(o4) == 1, s.count(o4)
g4 = '''    g_ztSnList.clear(); // ZT_R8B diagnostics (no effect on behaviour)
    g_ztEntryState = (int)m_assemblingState;
    for (auto& ztp : RlcPdus)
    {
        if (ztp.m_pdu)
        {
            LteRlcAmHeader zth;
            ztp.m_pdu->PeekHeader(zth);
            g_ztSnList.push_back(zth.IsDataPdu() ? zth.GetSequenceNumber().GetValue() : 9999);
        }
    }
'''
s = s.replace(o4, g4 + o4)
if '#include <iostream>' not in s:
    s = s.replace('#include "lte-rlc-am.h"', '#include "lte-rlc-am.h"\n#include <iostream>', 1)
open(p, 'w').write(s); print('patched', p)
