#!/usr/bin/env python3
"""r8c: fix of the RLC AM handover-forwarding reassembly (LteRlcAm::RlcPdusToRlcSdus / Reassemble).
Apply to a pristine r8 tree:  patch_r8c.py <ns3_dir>.   Only src/lte/model/lte-rlc-am.cc changes.
 F1 order   : PDUs are processed in modular SN order starting at VT(A) (original: buffer index order 0..1023,
              wrong after SN wrap-around; confirmed by r8b diagnostics on seed 4202: vtA=1023, list 0,1023).
 F2 state   : every forwarding reassembly starts from the constructor's state (WAITING_SI_SF, no kept S0, empty
              buffer). Original: m_assemblingState / m_keepS0Reassemble / m_sdusAssembleBuffer persist from the
              previous forwarding call on the same RLC entity (seed 4202 entered with WAITING_SI_SF).
 F3 headless: a PDU that is 'in sequence' but inconsistent with the state (continuation without a kept S0,
              or a new SDU start while a kept S0 is pending) is handled by the existing 'with loss' branch
              (original: null dereference, or the fragment is left in the buffer and later delivered as an SDU).
Each F1 reordering / F3 event prints one 'ZT_R8C' line to stderr."""
import sys
p = sys.argv[1].rstrip('/') + '/src/lte/model/lte-rlc-am.cc'
s = open(p).read()
assert 'ZT_R8' not in s, 'tree is not pristine r8'
a = s.index('\nLteRlcAm::Reassemble(Ptr<Packet> packet)\n'); b = s.index('\nLteRlcAm::CreateRlcSduBuffer()')
f = s[a:b]
o2 = '    if (!expectedSnLost)\n    {\n        NS_LOG_DEBUG("Reassembling NO LOSS ");\n'
assert f.count(o2) == 1
g = r'''    // ZT_R8C F3: in-sequence PDU that does not fit the reassembly state -> use the 'with loss' branch.
    if (!expectedSnLost)
    {
        const bool ztNoFirst = (framingInfo & LteRlcAmHeader::NO_FIRST_BYTE) != 0;
        const bool ztBad = (m_assemblingState == WAITING_SI_SF) ? (!ztNoFirst || !m_keepS0Reassemble)
                                                                : ztNoFirst;
        if (ztBad)
        {
            std::cerr << "ZT_R8C F3 t=" << Simulator::Now().GetSeconds() << " rnti=" << m_rnti
                      << " lcid=" << (uint32_t)m_lcid << " sn=" << currSeqNumber.GetValue()
                      << " state=" << (int)m_assemblingState << " fi=" << (uint32_t)framingInfo
                      << " kept=" << (m_keepS0Reassemble ? 1 : 0) << std::endl;
            expectedSnLost = true;
        }
    }
'''
f = f.replace(o2, g + o2)
s = s[:a] + f + s[b:]
a = s.index('\nLteRlcAm::RlcPdusToRlcSdus(std::vector<LteRlcAm::RetxPdu> RlcPdus)\n'); b = s.index('\n}\n', a) + 3
f = s[a:b]
o4 = '    uint16_t isGotExpectedSeqNumber = 0;\n'
assert f.count(o4) == 1
g4 = r'''    // ZT_R8C F1: process PDUs in modular SN order starting at VT(A).
    {
        std::vector<std::pair<uint16_t, LteRlcAm::RetxPdu>> ztKeyed;
        const uint16_t ztBase = m_vtA.GetValue();
        bool ztSorted = true;
        for (auto& ztp : RlcPdus)
        {
            if (!ztp.m_pdu)
            {
                continue;
            }
            LteRlcAmHeader zth;
            ztp.m_pdu->PeekHeader(zth);
            uint16_t k = (uint16_t)((zth.GetSequenceNumber().GetValue() + 1024 - ztBase) % 1024);
            if (!ztKeyed.empty() && k < ztKeyed.back().first)
            {
                ztSorted = false;
            }
            ztKeyed.emplace_back(k, ztp);
        }
        if (!ztSorted)
        {
            std::stable_sort(ztKeyed.begin(), ztKeyed.end(),
                             [](const std::pair<uint16_t, LteRlcAm::RetxPdu>& x,
                                const std::pair<uint16_t, LteRlcAm::RetxPdu>& y) { return x.first < y.first; });
            std::cerr << "ZT_R8C F1 t=" << Simulator::Now().GetSeconds() << " rnti=" << m_rnti
                      << " lcid=" << (uint32_t)m_lcid << " vtA=" << ztBase << " vtS=" << m_vtS.GetValue()
                      << " n=" << ztKeyed.size() << std::endl;
        }
        RlcPdus.clear();
        for (auto& kv : ztKeyed)
        {
            RlcPdus.push_back(kv.second);
        }
    }
    const size_t ztStaleSdus = m_transmittingRlcSdus.size(); // diagnostics only
    const size_t ztNPdu = RlcPdus.size();
    // ZT_R8C F2: start every forwarding reassembly from a clean state.
    m_assemblingState = WAITING_SI_SF; // same as the constructor's initial state
    m_keepS0Reassemble = nullptr;
    m_sdusAssembleBuffer.clear();
'''
f = f.replace(o4, g4 + o4)
o5 = '    CreateRlcSduBuffer();\n}'
assert f.count(o5) == 1
f = f.replace(o5, """    // ZT_R8C diagnostics (no effect on behaviour): one line per forwarding reassembly.
    std::cerr << "ZT_R8C FWD t=" << Simulator::Now().GetSeconds() << " rnti=" << m_rnti
              << " lcid=" << (uint32_t)m_lcid << " nPdu=" << ztNPdu << " sdusBefore=" << ztStaleSdus
              << " sdusAfter=" << m_transmittingRlcSdus.size() << " mapBefore="
              << m_transmittingRlcSduBuffer.size() << " seg=" << (m_segmented_rlcsdu ? 1 : 0)
              << " txon=" << m_txonBuffer.size() << std::endl;
""" + o5)
s = s[:a] + f + s[b:]
for inc in ('<iostream>', '<algorithm>'):
    if '#include ' + inc not in s:
        s = s.replace('#include "lte-rlc-am.h"', '#include "lte-rlc-am.h"\n#include ' + inc, 1)
open(p, 'w').write(s); print('patched', p)
