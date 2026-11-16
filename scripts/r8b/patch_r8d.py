#!/usr/bin/env python3
"""r8d = r8c + F4: exact handover forwarding set for RLC AM.   Apply to an r8c tree:  patch_r8d.py <ns3_dir>
Changes src/lte/model/{lte-rlc-am.h, lte-rlc-am.cc, lte-enb-rrc.cc}.

Original behaviour (UeManager::ForwardRlcBuffers, RLC AM branch), found by the r8c audit:
 (a) if no complete SDU is reassembled from the un-ACKed PDUs, only the transmission buffer is forwarded; the SDU
     that is partly transmitted is not re-sent, and its untransmitted remainder (payload bytes without a PDCP
     header) is forwarded as if it were a packet;
 (b) otherwise a backup copy (m_segmented_rlcsdu) is inserted, but the backup is never cleared, so it can be an
     SDU that was already transmitted completely (duplicate or stale); the remainder fragment is still forwarded;
 (c) up to three 'previous' SDUs are re-sent from an incomplete history, including a copy of the first SDU itself;
 (d) an SDU whose first bytes are in an ACKed PDU and whose last bytes are in an un-ACKed PDU is dropped.
F4: the RLC keeps a ledger of every SDU handed to PDUs (complete copy, first/last PDU SN, whether all bytes were
handed over).  At forwarding, the list is: every ledger SDU that is incomplete or has at least one un-ACKed PDU
(each once, in transmission order), followed by the transmission buffer without the remainder fragment.
This is the set 'SDUs whose delivery has not been confirmed' of lossless handover.
The ledger is bookkeeping only (packet copies); PDU construction is unchanged.  The original reassembly still runs
as a cross-check: every SDU it reassembles must be in the F4 list ('missing' must be 0).
One 'ZT_R8D FWD' line per forwarding call; 'ZT_R8D MISMATCH' / 'ZT_R8D PRE' / 'ZT_R8D AQM' lines flag
inconsistencies (expected: none)."""
import sys
d = sys.argv[1].rstrip('/') + '/src/lte/model/'
def rd(n): return open(d + n).read()
def once(s, old, new, n=1):
    assert s.count(old) == n, (old, s.count(old)); return s.replace(old, new)

# ---------------- lte-rlc-am.h
h = rd('lte-rlc-am.h'); assert 'ZT_R8D' not in h
h = once(h, '#include <fstream>\n', '#include <deque>\n#include <fstream>\n')
h = once(h, '    void RlcPdusToRlcSdus(std::vector<RetxPdu> Pdus);\n',
 '''    void RlcPdusToRlcSdus(std::vector<RetxPdu> Pdus);
    // ZT_R8D F4: SDUs whose delivery is not confirmed (in order, each once) followed by txonBuffer
    // without its leading remainder fragment. Clears the ledger.
    std::vector<Ptr<Packet>> ZtUnackedSdusForForwarding(std::vector<Ptr<Packet>> txonBuffer);
''')
h = once(h, '    Ptr<Packet> m_segmented_rlcsdu;\n',
 '''    Ptr<Packet> m_segmented_rlcsdu;
    // ZT_R8D F4 ledger (bookkeeping only)
    struct ZtSduEntry
    {
        Ptr<Packet> sdu;  ///< complete copy
        uint16_t firstSn; ///< SN of the PDU carrying its first byte
        uint16_t lastSn;  ///< SN of the last PDU carrying bytes of it so far
        bool complete;    ///< all bytes handed to PDUs
    };
    std::deque<ZtSduEntry> m_ztLedger;
    bool ZtAllAcked(const ZtSduEntry& e) const;
    void ZtLedgerTake(Ptr<Packet> firstSegment);
    void ZtLedgerComplete();
''')
open(d + 'lte-rlc-am.h', 'w').write(h)

# ---------------- lte-rlc-am.cc
s = rd('lte-rlc-am.cc'); assert 'ZT_R8C' in s and 'ZT_R8D' not in s
for inc in ('<iostream>', '<algorithm>', '<set>'):
    if '#include ' + inc not in s:
        s = once(s, '#include <fstream>\n', '#include <fstream>\n#include ' + inc + '\n')
s = once(s, '    Ptr<Packet> firstSegment = (*(m_txonBuffer.begin()))->Copy();\n',
 '''    Ptr<Packet> firstSegment = (*(m_txonBuffer.begin()))->Copy();
    ZtLedgerTake(firstSegment); // ZT_R8D F4 (bookkeeping only)
''')
s = once(s, '                // Whole segment was taken, so adjust tag\n',
 '''                // Whole segment was taken, so adjust tag
                ZtLedgerComplete(); // ZT_R8D F4
''')
a = s.index('        else if ((nextSegmentSize - firstSegment->GetSize() <= 2) ||')
b = s.index('        else // (firstSegment->GetSize () < m_nextSegmentSize)', a)
f = once(s[a:b], '            dataField.push_back(firstSegment);\n            firstSegment = 0;\n',
 '''            dataField.push_back(firstSegment);
            firstSegment = 0;
            ZtLedgerComplete(); // ZT_R8D F4
''')
s = s[:a] + f + s[b:]
s = once(s, '            firstSegment = (*(m_txonBuffer.begin()))->Copy();\n',
 '''            firstSegment = (*(m_txonBuffer.begin()))->Copy();
            ZtLedgerComplete();         // ZT_R8D F4: the previous SDU went entirely into this PDU
            ZtLedgerTake(firstSegment); // ZT_R8D F4
''')
s = once(s, '    m_txedRlcSduBuffer.clear();\n    m_txedRlcSduBufferSize = 0;\n',
 '    m_txedRlcSduBuffer.clear();\n    m_txedRlcSduBufferSize = 0;\n    m_ztLedger.clear(); // ZT_R8D\n')
s = once(s, '\nPtr<Packet>\nLteRlcAm::GetSegmentedRlcsdu()\n', r'''
// ---------------------------------------------------------------- ZT_R8D F4
bool
LteRlcAm::ZtAllAcked(const ZtSduEntry& e) const
{
    if (m_txedBuffer.size() < 1024 || m_retxBuffer.size() < 1024)
    {
        return true;
    }
    for (uint16_t sn = e.firstSn;; sn = (sn + 1) % 1024)
    {
        if (m_txedBuffer[sn].m_pdu || m_retxBuffer[sn].m_pdu)
        {
            return false;
        }
        if (sn == e.lastSn)
        {
            break;
        }
    }
    return true;
}

void
LteRlcAm::ZtLedgerTake(Ptr<Packet> firstSegment)
{
    // drop confirmed SDUs from the front (keeps the ledger within the transmitting window)
    while (!m_ztLedger.empty() && m_ztLedger.front().complete && ZtAllAcked(m_ztLedger.front()))
    {
        m_ztLedger.pop_front();
    }
    const uint16_t sn = m_vtS.GetValue(); // SN of the PDU being built
    LteRlcSduStatusTag tag;
    const bool isRemainder =
        firstSegment->PeekPacketTag(tag) && tag.GetStatus() == LteRlcSduStatusTag::LAST_SEGMENT;
    if (isRemainder)
    {
        if (m_ztLedger.empty() || m_ztLedger.back().complete)
        {
            std::cerr << "ZT_R8D MISMATCH kind=1 t=" << Simulator::Now().GetSeconds() << " rnti="
                      << m_rnti << " lcid=" << (uint32_t)m_lcid << " sn=" << sn << std::endl;
        }
        else
        {
            m_ztLedger.back().lastSn = sn;
        }
        return;
    }
    if (!m_ztLedger.empty() && !m_ztLedger.back().complete)
    {
        std::cerr << "ZT_R8D MISMATCH kind=2 t=" << Simulator::Now().GetSeconds() << " rnti="
                  << m_rnti << " lcid=" << (uint32_t)m_lcid << " sn=" << sn << std::endl;
        m_ztLedger.back().complete = true;
    }
    ZtSduEntry e;
    e.sdu = firstSegment->Copy();
    e.firstSn = sn;
    e.lastSn = sn;
    e.complete = false;
    m_ztLedger.push_back(e);
}

void
LteRlcAm::ZtLedgerComplete()
{
    if (m_ztLedger.empty())
    {
        std::cerr << "ZT_R8D MISMATCH kind=3 t=" << Simulator::Now().GetSeconds() << " rnti="
                  << m_rnti << " lcid=" << (uint32_t)m_lcid << std::endl;
        return;
    }
    m_ztLedger.back().complete = true;
    m_ztLedger.back().lastSn = m_vtS.GetValue();
}

std::vector<Ptr<Packet>>
LteRlcAm::ZtUnackedSdusForForwarding(std::vector<Ptr<Packet>> txonBuffer)
{
    std::vector<Ptr<Packet>> out;
    if (m_enableAqm)
    {
        std::cerr << "ZT_R8D AQM not supported by F4" << std::endl;
    }
    // 1. the untransmitted remainder of a partly transmitted SDU is not a packet: drop it
    bool frag = false;
    if (!txonBuffer.empty())
    {
        LteRlcSduStatusTag tag;
        if (txonBuffer.front()->PeekPacketTag(tag) &&
            tag.GetStatus() == LteRlcSduStatusTag::LAST_SEGMENT)
        {
            frag = true;
            txonBuffer.erase(txonBuffer.begin());
        }
    }
    const bool partial = !m_ztLedger.empty() && !m_ztLedger.back().complete;
    if (partial != frag)
    {
        std::cerr << "ZT_R8D MISMATCH kind=4 t=" << Simulator::Now().GetSeconds() << " rnti="
                  << m_rnti << " lcid=" << (uint32_t)m_lcid << " partial=" << partial
                  << " frag=" << frag << std::endl;
    }
    // 2. ledger SDUs whose delivery is not confirmed
    std::set<uint16_t> sns;
    LtePdcpHeader ph;
    uint32_t confirmed = 0;
    for (auto& e : m_ztLedger)
    {
        if (e.complete && ZtAllAcked(e))
        {
            ++confirmed;
            continue;
        }
        out.push_back(e.sdu->Copy());
        if (e.sdu->GetSize() >= 2)
        {
            e.sdu->PeekHeader(ph);
            sns.insert(ph.GetSequenceNumber());
        }
    }
    const size_t nLedger = out.size();
    // 3. cross-check against the original reassembly (must be a subset)
    uint32_t missing = 0;
    for (auto& p : m_transmittingRlcSdus)
    {
        if (p && p->GetSize() >= 2)
        {
            p->PeekHeader(ph);
            if (!sns.count(ph.GetSequenceNumber()))
            {
                ++missing;
            }
        }
    }
    // 4. rest of the transmission buffer
    out.insert(out.end(), txonBuffer.begin(), txonBuffer.end());
    // order diagnostics: repeated packet uid; backward PDCP SN step (12 bit, modular) by position
    uint32_t dup = 0;
    uint32_t backL = 0; // inside the ledger part
    uint32_t backJ = 0; // at the ledger / txonBuffer junction
    uint32_t backT = 0; // inside txonBuffer (arrival order at this RLC, not changed by F4)
    {
        std::set<uint64_t> seen;
        bool have = false;
        uint16_t prev = 0;
        for (size_t i = 0; i < out.size(); ++i)
        {
            Ptr<Packet> p = out[i];
            if (!p || p->GetSize() < 2)
            {
                continue;
            }
            if (!seen.insert(p->GetUid()).second)
            {
                ++dup;
            }
            p->PeekHeader(ph);
            const uint16_t x = ph.GetSequenceNumber();
            if (have && ((x + 4096 - prev) % 4096) >= 2048)
            {
                if (i < nLedger)
                {
                    ++backL;
                }
                else if (i == nLedger)
                {
                    ++backJ;
                }
                else
                {
                    ++backT;
                }
                if (i <= nLedger || backT <= 2)
                {
                    std::cerr << "ZT_R8D BACK t=" << Simulator::Now().GetSeconds() << " rnti="
                              << m_rnti << " i=" << i << " nLedger=" << nLedger << " prev=" << prev
                              << " cur=" << x << " n=" << out.size() << std::endl;
                }
            }
            prev = x;
            have = true;
        }
    }
    std::cerr << "ZT_R8D FWD t=" << Simulator::Now().GetSeconds() << " rnti=" << m_rnti
              << " lcid=" << (uint32_t)m_lcid << " ledger=" << m_ztLedger.size()
              << " confirmed=" << confirmed << " fwdSdu=" << nLedger << " partial=" << partial
              << " frag=" << frag << " reasm=" << m_transmittingRlcSdus.size()
              << " missing=" << missing << " txon=" << txonBuffer.size() << " dup=" << dup
              << " backL=" << backL << " backJ=" << backJ << " backT=" << backT << std::endl;
    m_ztLedger.clear();
    m_transmittingRlcSdus.clear();
    m_transmittingRlcSduBufferSize = 0;
    m_transmittingRlcSduBuffer.clear();
    return out;
}

Ptr<Packet>
LteRlcAm::GetSegmentedRlcsdu()
''')
open(d + 'lte-rlc-am.cc', 'w').write(s)

# ---------------- lte-enb-rrc.cc
r = rd('lte-enb-rrc.cc'); assert 'ZT_R8D' not in r
a = r.index('        // this cycle adds the SDUs given by the merge of txed and retxed buffers\n')
e_anchor = '            m_x2forwardingBuffer = txonBuffer;\n            m_x2forwardingBufferSize += txonBufferSize;\n        }\n'
assert r.count(e_anchor) == 1
b = r.index(e_anchor, a) + len(e_anchor)
assert r[a:b].count('GetSegmentedRlcsdu') == 1 and r[a:b].count('GetTxedRlcSduBuffer') == 1
new = '''        // ZT_R8D F4: forward exactly the SDUs whose delivery is not confirmed (each once, in order),
        // then the untouched part of the transmission buffer. Replaces the original construction
        // (reassembled SDUs + backup SDU + up to 3 previous SDUs + txonBuffer incl. remainder fragment).
        {
            if (!m_x2forwardingBuffer.empty())
            {
                std::cerr << "ZT_R8D PRE t=" << Simulator::Now().GetSeconds() << " rnti=" << m_rnti
                          << " n=" << m_x2forwardingBuffer.size() << std::endl;
            }
            (void)txonBufferSize;
            std::vector<Ptr<Packet>> ztFwd = rlcAm->ZtUnackedSdusForForwarding(txonBuffer);
            for (auto& ztP : ztFwd)
            {
                m_x2forwardingBuffer.push_back(ztP);
                m_x2forwardingBufferSize += ztP->GetSize();
            }
        }
'''
r = r[:a] + new + r[b:]
if '#include <iostream>' not in r:
    i = r.index('#include'); r = r[:i] + '#include <iostream>\n' + r[i:]
open(d + 'lte-enb-rrc.cc', 'w').write(r)
print('patched r8d', d)
