#!/usr/bin/env python3
"""r9 = r8d + O-1, O-3, O-4, O-5 (docs/thesis/phase2_percell_spec_v0.md §2).  Apply to an r8d tree:  patch_r9.py <ns3_dir>
Read-only observation: new files only; no RNG draw, no state change, no change to any existing output.
 O-1  R9_enb_uemap.txt  every E2 report of every cell (LTE cell 1 and mmWave cells), at the report instant:
                        each UeManager of that cell's RRC (rnti, imsi, UeManager state).  = the list the report uses (F5).
      R9_ue_rrc.txt     at each distinct mmWave report instant: per MC UE, LTE RRC (cell, rnti, state) and
                        mmWave RRC (cell, rnti, state) as seen by the UE.
 O-2  (no code) existing handover / switch event files.
 O-3  R9_pdcp_split.txt at each LTE cell report: per McEnbPdcp (LTE rnti, lcid) cumulative SDUs/bytes sent to LTE and
                        to NR, current m_perPckToLTE, m_useMmWaveConnection, NR target cell (live entity only).
 O-4  <stats>_r9rx.txt  with every E2 stats write: per (event cell, IMSI, LCID) cumulative nRx, nRx with delay = 0,
                        nRx without RlcTag (RLC AM only; 'unknown' when the trace was not from RLC AM).
 O-5  <stats>_r9lastset.txt with every E2 stats write: per (IMSI, LCID) time / direction / cell of the last write of
                        the reported cell column (m_dlCellId), plus the reported cell for cross-check.
All times are simulation ns (integers)."""
import sys
root = sys.argv[1].rstrip('/') + '/src/'
def rd(n): return open(root + n).read()
def wr(n, s): open(root + n, 'w').write(s)
def once(s, old, new):
    assert s.count(old) == 1, (old[:80], s.count(old)); return s.replace(old, new)

# ---------- lte-rlc-am.cc : tag flag for the stats calculator (O-4)
n = 'lte/model/lte-rlc-am.cc'; s = rd(n); assert 'ZT_R8D' in s and 'R9' not in s
s = once(s, 'namespace ns3\n{\n', 'namespace ns3\n{\n\n// R9 O-4: RlcTag presence of the PDU whose m_rxPdu trace is being fired (-1 = not inside RLC AM rx trace)\nint g_r9RlcRxTagFound = -1;\n')
s = once(s, '    m_rxPdu(m_rnti, m_lcid, rxPduParams.p->GetSize(), delay.GetNanoSeconds());\n',
 '    g_r9RlcRxTagFound = r7bFound ? 1 : 0; // R9 O-4 (read-only)\n    m_rxPdu(m_rnti, m_lcid, rxPduParams.p->GetSize(), delay.GetNanoSeconds());\n    g_r9RlcRxTagFound = -1; // R9 O-4\n')
wr(n, s)

# ---------- stats calculator (O-4, O-5)
n = 'lte/helper/mmwave-bearer-stats-calculator.h'; s = rd(n)
s = once(s, '    std::map<R5CellKey, R5CellAcc> m_r5DlPerCell;',
 '''    struct R9RxAcc { uint64_t nRx{0}, nZero{0}, nNoTag{0}, nUnknown{0}; };
    std::map<R5CellKey, R9RxAcc> m_r9DlRx; //!< R9 O-4 (cumulative)
    struct R9LastSet { int64_t tNs{-1}; int dir{-1}; uint16_t cell{0}; };
    std::map<ImsiLcidPair_t, R9LastSet> m_r9DlLastSet; //!< R9 O-5
    bool m_firstR9RxWrite{true};
    bool m_firstR9LastSetWrite{true};
    std::map<R5CellKey, R5CellAcc> m_r5DlPerCell;''')
wr(n, s)
n = 'lte/helper/mmwave-bearer-stats-calculator.cc'; s = rd(n)
s = once(s, 'namespace ns3\n{\n', 'namespace ns3\n{\n\nextern int g_r9RlcRxTagFound; // R9 O-4 (defined in lte-rlc-am.cc)\n')
s = once(s, '            { R5CellAcc& r5 = m_r5DlPerCell[R5CellKey{cellId, imsi, lcid}]; r5.nTx++; r5.txBytes += packetSize; } // R-5 additive\n',
 '            { R5CellAcc& r5 = m_r5DlPerCell[R5CellKey{cellId, imsi, lcid}]; r5.nTx++; r5.txBytes += packetSize; } // R-5 additive\n'
 '            { R9LastSet& l = m_r9DlLastSet[p]; l.tNs = Simulator::Now().GetNanoSeconds(); l.dir = 0; l.cell = cellId; } // R9 O-5\n')
s = once(s, '            { R5CellAcc& r5 = m_r5DlPerCell[R5CellKey{cellId, imsi, lcid}]; r5.nRx++; r5.rxBytes += packetSize; r5.delaySumNs += delay; } // R-5 additive\n',
 '            { R5CellAcc& r5 = m_r5DlPerCell[R5CellKey{cellId, imsi, lcid}]; r5.nRx++; r5.rxBytes += packetSize; r5.delaySumNs += delay; } // R-5 additive\n'
 '            { R9RxAcc& a = m_r9DlRx[R5CellKey{cellId, imsi, lcid}]; a.nRx++; if (delay == 0) a.nZero++;\n'
 '              if (g_r9RlcRxTagFound == 0) a.nNoTag++; else if (g_r9RlcRxTagFound < 0) a.nUnknown++; } // R9 O-4\n'
 '            { R9LastSet& l = m_r9DlLastSet[p]; l.tNs = Simulator::Now().GetNanoSeconds(); l.dir = 1; l.cell = cellId; } // R9 O-5\n')
s = once(s, '        pc.close();\n    }\n}\n', r'''        pc.close();

        // R9 O-4 / O-5 (additive files)
        std::string base = (dot == std::string::npos ? GetDlOutputFilename() : GetDlOutputFilename().substr(0, dot));
        std::ofstream rx;
        if (m_firstR9RxWrite)
        {
            rx.open((base + "_r9rx.txt").c_str());
            rx << "% start\tend\tEventCellId\tIMSI\tLCID\tnRxPDUs\tnRxZeroDelay\tnRxNoRlcTag\tnRxTagUnknown" << std::endl;
            m_firstR9RxWrite = false;
        }
        else
        {
            rx.open((base + "_r9rx.txt").c_str(), std::ios_base::app);
        }
        for (auto& kv : m_r9DlRx)
        {
            rx << m_startTime.GetNanoSeconds() << "\t" << endTime.GetNanoSeconds() << "\t" << kv.first.cell << "\t"
               << kv.first.imsi << "\t" << (uint32_t)kv.first.lcid << "\t" << kv.second.nRx << "\t" << kv.second.nZero
               << "\t" << kv.second.nNoTag << "\t" << kv.second.nUnknown << std::endl;
        }
        rx.close();
        std::ofstream ls;
        if (m_firstR9LastSetWrite)
        {
            ls.open((base + "_r9lastset.txt").c_str());
            ls << "% start\tend\tIMSI\tLCID\tlastSetTimeNs\tlastSetDir(0=Tx,1=Rx)\tlastSetCell\treportedCellId" << std::endl;
            m_firstR9LastSetWrite = false;
        }
        else
        {
            ls.open((base + "_r9lastset.txt").c_str(), std::ios_base::app);
        }
        for (auto& kv : m_r9DlLastSet)
        {
            ImsiLcidPair_t q = kv.first;
            uint32_t rep = m_dlCellId.count(q) ? m_dlCellId[q] : 0;
            ls << m_startTime.GetNanoSeconds() << "\t" << endTime.GetNanoSeconds() << "\t" << q.m_imsi << "\t"
               << (uint32_t)q.m_lcId << "\t" << kv.second.tNs << "\t" << kv.second.dir << "\t" << kv.second.cell << "\t"
               << rep << std::endl;
        }
        ls.close();
    }
}
''')
wr(n, s)

# ---------- McEnbPdcp (O-3)
n = 'lte/model/mc-enb-pdcp.h'; s = rd(n)
s = once(s, '    double m_perPckToLTE;\n', '    double m_perPckToLTE;\n\n  public:\n    // R9 O-3: read-only accessors for the split observation\n    double R9GetPerPckToLte() const { return m_perPckToLTE; }\n    bool R9GetUseMmWave() const { return m_useMmWaveConnection; }\n    uint16_t R9GetNrTarget() const { return m_ueDataParams.targetCellId; }\n    uint16_t R9GetRnti() const { return m_rnti; }\n    uint8_t R9GetLcid() const { return m_lcid; }\n\n  private:\n')
s = once(s, '\n} // namespace ns3', '\n/// R9 O-3: append the PDCP split counters (cumulative) to R9_pdcp_split.txt\nvoid R9WritePdcpSplit(uint16_t lteCellId);\n\n} // namespace ns3')
wr(n, s)
n = 'lte/model/mc-enb-pdcp.cc'; s = rd(n)
s = once(s, '#include "ns3/simulator.h"\n', '#include "ns3/simulator.h"\n\n#include <fstream>\n#include <map>\n#include <utility>\n')
s = once(s, 'NS_LOG_COMPONENT_DEFINE("McEnbPdcp");\n', r'''NS_LOG_COMPONENT_DEFINE("McEnbPdcp");

// ---- R9 O-3 (read-only): cumulative split counters per (LTE rnti, lcid) ----
namespace
{
struct R9SplitAcc
{
    uint64_t nLte{0}, bLte{0}, nNr{0}, bNr{0};
    const McEnbPdcp* live{nullptr};
};
std::map<std::pair<uint16_t, uint8_t>, R9SplitAcc>&
R9Split()
{
    static std::map<std::pair<uint16_t, uint8_t>, R9SplitAcc> m;
    return m;
}
bool g_r9SplitFirst = true;
} // namespace

void
R9WritePdcpSplit(uint16_t lteCellId)
{
    std::ofstream f;
    if (g_r9SplitFirst)
    {
        f.open("R9_pdcp_split.txt");
        f << "% timeNs\tlteCellId\tlteRnti\tLCID\tnSduLte\tbytesLte\tnSduNr\tbytesNr\tlive\tperPckToLte\tuseMmWave\tnrTargetCell"
          << std::endl;
        g_r9SplitFirst = false;
    }
    else
    {
        f.open("R9_pdcp_split.txt", std::ios_base::app);
    }
    const int64_t t = Simulator::Now().GetNanoSeconds();
    for (auto& kv : R9Split())
    {
        const R9SplitAcc& a = kv.second;
        f << t << "\t" << lteCellId << "\t" << kv.first.first << "\t" << (uint32_t)kv.first.second << "\t" << a.nLte
          << "\t" << a.bLte << "\t" << a.nNr << "\t" << a.bNr << "\t" << (a.live ? 1 : 0) << "\t";
        if (a.live)
        {
            f << a.live->R9GetPerPckToLte() << "\t" << (a.live->R9GetUseMmWave() ? 1 : 0) << "\t" << a.live->R9GetNrTarget();
        }
        else
        {
            f << "NA\tNA\tNA";
        }
        f << std::endl;
    }
}
''')
s = once(s, 'McEnbPdcp::~McEnbPdcp()\n{\n    NS_LOG_FUNCTION(this);\n',
 'McEnbPdcp::~McEnbPdcp()\n{\n    NS_LOG_FUNCTION(this);\n    for (auto& kv : R9Split()) // R9 O-3\n    {\n        if (kv.second.live == this)\n        {\n            kv.second.live = nullptr;\n        }\n    }\n')
s = once(s, '    m_txPdu(m_rnti, m_lcid, p->GetSize());\n    params.pdcpPdu = p;\n',
 '    m_txPdu(m_rnti, m_lcid, p->GetSize());\n    { R9SplitAcc& a = R9Split()[std::make_pair(m_rnti, m_lcid)]; a.nLte++; a.bLte += p->GetSize(); a.live = this; } // R9 O-3\n    params.pdcpPdu = p;\n')
s = once(s, '    m_ueDataParams.ueData = p;\n    m_txPdu(m_rnti, m_lcid, p->GetSize());\n',
 '    m_ueDataParams.ueData = p;\n    m_txPdu(m_rnti, m_lcid, p->GetSize());\n    { R9SplitAcc& a = R9Split()[std::make_pair(m_rnti, m_lcid)]; a.nNr++; a.bNr += p->GetSize(); a.live = this; } // R9 O-3\n')
wr(n, s)

# ---------- O-1 helper shared by both eNB devices: declared in lte-enb-rrc.h, defined in lte-enb-rrc.cc
n = 'lte/model/lte-enb-rrc.h'; s = rd(n)
s = once(s, '\n} // namespace ns3\n', '\n/// R9 O-1: append this cell\'s UeManager list (rnti, imsi, state) to R9_enb_uemap.txt\nvoid R9WriteEnbUeMap(uint16_t cellId, Ptr<LteEnbRrc> rrc);\n\n} // namespace ns3\n')
wr(n, s)
n = 'lte/model/lte-enb-rrc.cc'; s = rd(n); assert 'ZT_R8D' in s
s = once(s, '\nUeManager::UeManager()\n', r'''
// ---- R9 O-1 (read-only) ----
void
R9WriteEnbUeMap(uint16_t cellId, Ptr<LteEnbRrc> rrc)
{
    static bool first = true;
    std::ofstream f;
    if (first)
    {
        f.open("R9_enb_uemap.txt");
        f << "% timeNs\tcellId\trnti\tIMSI\tueManagerState" << std::endl;
        first = false;
    }
    else
    {
        f.open("R9_enb_uemap.txt", std::ios_base::app);
    }
    const int64_t t = Simulator::Now().GetNanoSeconds();
    if (!rrc)
    {
        return;
    }
    for (auto& kv : rrc->GetUeMap())
    {
        f << t << "\t" << cellId << "\t" << kv.first << "\t" << kv.second->GetImsi() << "\t"
          << (int)kv.second->GetState() << std::endl;
    }
}

UeManager::UeManager()
''')
if '#include <fstream>' not in s:
    s = once(s, '#include <cstdlib>\n', '#include <cstdlib>\n#include <fstream>\n')
wr(n, s)

# ---------- LTE eNB device: O-1 (cell 1 list) + O-3 at each report
n = 'lte/model/lte-enb-net-device.cc'; s = rd(n)
a = s.index('\nLteEnbNetDevice::BuildAndSendReportMessage(E2Termination::RicSubscriptionRequest_rval_s params)\n{\n')
anchor = '    if (m_sendCuUp)\n'
b = s.index(anchor, a)
s = s[:b] + '    R9WriteEnbUeMap(m_cellId, m_rrc); // R9 O-1 (read-only)\n    R9WritePdcpSplit(m_cellId);       // R9 O-3 (read-only)\n\n' + s[b:]
wr(n, s)

# ---------- mmWave eNB device: O-1 (cell list + UE-side RRC view)
n = 'mmwave/model/mmwave-enb-net-device.cc'; s = rd(n)
s = once(s, '#include "mmwave-ue-net-device.h"\n', '#include "mmwave-ue-net-device.h"\n#include "mc-ue-net-device.h"\n\n#include <ns3/lte-ue-rrc.h>\n#include <ns3/node-list.h>\n#include <fstream>\n')
s = once(s, '\nMmWaveEnbNetDevice::BuildAndSendReportMessage(E2Termination::RicSubscriptionRequest_rval_s params)\n{\n',
 r'''
// ---- R9 O-1 (read-only): UE-side RRC view, once per distinct report instant ----
static void
R9WriteUeRrc()
{
    static bool first = true;
    static int64_t lastT = -1;
    const int64_t t = Simulator::Now().GetNanoSeconds();
    if (t == lastT)
    {
        return;
    }
    lastT = t;
    std::ofstream f;
    if (first)
    {
        f.open("R9_ue_rrc.txt");
        f << "% timeNs\tIMSI\tlteCell\tlteRnti\tlteState\tmmCell\tmmRnti\tmmState" << std::endl;
        first = false;
    }
    else
    {
        f.open("R9_ue_rrc.txt", std::ios_base::app);
    }
    for (uint32_t i = 0; i < NodeList::GetNNodes(); ++i)
    {
        Ptr<Node> node = NodeList::GetNode(i);
        for (uint32_t d = 0; d < node->GetNDevices(); ++d)
        {
            Ptr<McUeNetDevice> ue = DynamicCast<McUeNetDevice>(node->GetDevice(d));
            if (!ue)
            {
                continue;
            }
            Ptr<LteUeRrc> l = ue->GetLteRrc();
            Ptr<LteUeRrc> m = ue->GetMmWaveRrc();
            f << t << "\t" << ue->GetImsi() << "\t";
            if (l)
            {
                f << l->GetCellId() << "\t" << l->GetRnti() << "\t" << (int)l->GetState() << "\t";
            }
            else
            {
                f << "NA\tNA\tNA\t";
            }
            if (m)
            {
                f << m->GetCellId() << "\t" << m->GetRnti() << "\t" << (int)m->GetState();
            }
            else
            {
                f << "NA\tNA\tNA";
            }
            f << std::endl;
        }
    }
}

MmWaveEnbNetDevice::BuildAndSendReportMessage(E2Termination::RicSubscriptionRequest_rval_s params)
{
    R9WriteEnbUeMap(m_cellId, m_rrc); // R9 O-1 (read-only)
    R9WriteUeRrc();                    // R9 O-1 (read-only)
''')
# the static function was inserted between 'void' and the method name; move 'void' accordingly
s = once(s, 'void\n// ---- R9 O-1 (read-only): UE-side RRC view', '// ---- R9 O-1 (read-only): UE-side RRC view')
s = once(s, '\nMmWaveEnbNetDevice::BuildAndSendReportMessage(E2Termination::RicSubscriptionRequest_rval_s params)\n{\n    R9WriteEnbUeMap',
 '\nvoid\nMmWaveEnbNetDevice::BuildAndSendReportMessage(E2Termination::RicSubscriptionRequest_rval_s params)\n{\n    R9WriteEnbUeMap')
wr(n, s)
print('patched r9', root)
