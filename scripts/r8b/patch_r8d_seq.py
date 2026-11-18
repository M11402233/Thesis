#!/usr/bin/env python3
"""r8d_seq = r8d + a creation-order check that does not depend on the 12-bit PDCP SN (DIAGNOSTIC TREE ONLY, never used for data).
Apply to a copy of the r8d tree:  patch_r8d_seq.py <ns3_dir>
 * McEnbPdcp: every PDCP PDU gets a packet tag ZtSeqTag with a global counter (creation order = PDCP SN order, without wrap-around).
 * LteRlcAm::ZtUnackedSdusForForwarding: counts backward steps of that counter in the forwarding set by position
   (ledger part / junction / txonBuffer part) and the PDUs without tag; adds  seqBackL seqBackJ seqBackT noSeq  to the FWD line and
   prints up to 3 'ZT_R8D SEQBACK' lines per call.
Packet tags do not change packet sizes or any simulated behaviour; the SN-based fields of the FWD line must stay identical to r8d."""
import sys
root = sys.argv[1].rstrip('/') + '/src/lte/model/'
def rd(n): return open(root + n).read()
def once(s, old, new):
    assert s.count(old) == 1, (old[:80], s.count(old)); return s.replace(old, new)
open(root + 'zt-seq-tag.h', 'w').write('''#ifndef ZT_SEQ_TAG_H
#define ZT_SEQ_TAG_H
#include "ns3/tag-buffer.h"
#include "ns3/tag.h"
#include "ns3/type-id.h"
#include <cstdint>
#include <ostream>
namespace ns3
{
inline uint64_t g_ztSeqCounter = 0;
class ZtSeqTag : public Tag
{
  public:
    ZtSeqTag() : m_seq(0) {}
    explicit ZtSeqTag(uint64_t s) : m_seq(s) {}
    static TypeId GetTypeId()
    {
        static TypeId tid = TypeId("ns3::ZtSeqTag").SetParent<Tag>().SetGroupName("Lte").AddConstructor<ZtSeqTag>();
        return tid;
    }
    TypeId GetInstanceTypeId() const override { return GetTypeId(); }
    uint32_t GetSerializedSize() const override { return 8; }
    void Serialize(TagBuffer i) const override { i.WriteU64(m_seq); }
    void Deserialize(TagBuffer i) override { m_seq = i.ReadU64(); }
    void Print(std::ostream& os) const override { os << "ZtSeq=" << m_seq; }
    uint64_t Get() const { return m_seq; }
  private:
    uint64_t m_seq;
};
} // namespace ns3
#endif
''')
n = 'mc-enb-pdcp.cc'; s = rd(n); assert 'ZtSeqTag' not in s
s = once(s, '#include "ns3/simulator.h"\n', '#include "ns3/simulator.h"\n#include "zt-seq-tag.h"\n')
s = once(s, '    m_txPdu(m_rnti, m_lcid, p->GetSize());\n    params.pdcpPdu = p;\n',
         '    { ZtSeqTag ztT(++g_ztSeqCounter); p->AddPacketTag(ztT); } // seq diagnostic\n    m_txPdu(m_rnti, m_lcid, p->GetSize());\n    params.pdcpPdu = p;\n')
s = once(s, '    m_ueDataParams.ueData = p;\n    m_txPdu(m_rnti, m_lcid, p->GetSize());\n',
         '    m_ueDataParams.ueData = p;\n    { ZtSeqTag ztT(++g_ztSeqCounter); p->AddPacketTag(ztT); } // seq diagnostic\n    m_txPdu(m_rnti, m_lcid, p->GetSize());\n')
open(root + n, 'w').write(s)
n = 'lte-rlc-am.cc'; s = rd(n); assert 'ZtSeqTag' not in s and 'ZT_R8D' in s
s = once(s, '#include "ns3/simulator.h"\n', '#include "ns3/simulator.h"\n#include "zt-seq-tag.h"\n')
s = once(s, '    std::cerr << "ZT_R8D FWD t="', '''    uint32_t seqBackL = 0, seqBackJ = 0, seqBackT = 0, noSeq = 0, seqPrinted = 0;
    {
        bool haveS = false;
        uint64_t prevS = 0;
        for (size_t i = 0; i < out.size(); ++i)
        {
            ZtSeqTag zt;
            if (!out[i]->PeekPacketTag(zt))
            {
                ++noSeq;
                continue;
            }
            const uint64_t cur = zt.Get();
            if (haveS && cur <= prevS)
            {
                if (i < nLedger)
                {
                    ++seqBackL;
                }
                else if (i == nLedger)
                {
                    ++seqBackJ;
                }
                else
                {
                    ++seqBackT;
                }
                if (seqPrinted++ < 3)
                {
                    std::cerr << "ZT_R8D SEQBACK t=" << Simulator::Now().GetSeconds() << " rnti=" << m_rnti
                              << " i=" << i << " nLedger=" << nLedger << " prevSeq=" << prevS << " curSeq=" << cur
                              << " n=" << out.size() << std::endl;
                }
            }
            prevS = cur;
            haveS = true;
        }
    }
    std::cerr << "ZT_R8D FWD t="''')
s = once(s, '<< " backT=" << backT << std::endl;', '<< " backT=" << backT << " seqBackL=" << seqBackL << " seqBackJ=" << seqBackJ << " seqBackT=" << seqBackT << " noSeq=" << noSeq << std::endl;')
open(root + n, 'w').write(s)
print('patched r8d_seq', root)
