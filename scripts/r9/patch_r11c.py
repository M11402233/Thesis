#!/usr/bin/env python3
"""r11c = r11t + 因果驗證之觀測輸出（docs/thesis/D30P1_causal_maxretx_spec.md §4）。只觀測、不改行為；套用於 r11t 之副本。
僅於 ZT_R10_TRACE 設定時輸出（與 r11t 同一開關）：
  R10_trace.txt 新增
    Q <ns> <rnti> <lcid> <imsi> <size> <txonBytes>                         傳送緩衝區滿 → RLC SDU 丟棄（ns-3 唯一之 RLC 丟棄路徑）
    E <ns> <rnti> <lcid> <imsi> <txonN> <txonBytes> <txedN> <retxN> <oldestTagNs>   模擬結束（DoDispose）時仍在緩衝區者
  R11C_rrc.txt（LteEnbRrc，LTE 錨點之 RRC 視角）
    U <ns> <imsi> <servCell> <servSinrDb> <bestCell> <bestSinrDb> <usingLte> <assoc>   每 IMSI 每 100 ms 至多一行
    W <ns> <imsi> <rnti> <useMmWave>                                       SendRrcConnectionSwitch（切換 LTE／mmWave）
  R11C_rlf.txt（LteUeRrc::DoNotifyRadioLinkFailure 被呼叫時才建立；原始碼查無呼叫者，預期不存在）
map 一律以 find() 讀取，不以 operator[]（避免插入新鍵而改變行為）。"""
import sys
root = sys.argv[1].rstrip('/') + '/src/lte/model/'
def rd(n): return open(root + n).read()
def wr(n, s): open(root + n, 'w').write(s)
def once(s, old, new):
    assert s.count(old) == 1, (old[:90], s.count(old)); return s.replace(old, new)

n = 'lte-rlc-am.cc'; s = rd(n); assert 'R10Trace()' in s and '"Q\\t"' not in s
s = once(s, '            // Discard full RLC SDU\n',
 '            // Discard full RLC SDU\n'
 '            if (auto* tf = R10Trace())\n            {\n'
 '                *tf << "Q\\t" << Simulator::Now().GetNanoSeconds() << "\\t" << m_rnti << "\\t" << (uint32_t)m_lcid << "\\t" << m_imsi\n'
 '                    << "\\t" << p->GetSize() << "\\t" << m_txonBufferSize << "\\n";\n            }\n')
s = once(s, 'LteRlcAm::DoDispose()\n{\n    NS_LOG_FUNCTION(this);\n',
 'LteRlcAm::DoDispose()\n{\n    NS_LOG_FUNCTION(this);\n'
 '    if (auto* tf = R10Trace())\n    {\n'
 '        uint32_t nTxed = 0, nRetx = 0;\n        int64_t oldest = -1;\n'
 '        auto scan = [&](std::vector<RetxPdu>& b, uint32_t& c) {\n'
 '            for (auto& r : b)\n            {\n                if (!r.m_pdu)\n                {\n                    continue;\n                }\n'
 '                c++;\n                RlcTag q;\n'
 '                if (r.m_pdu->FindFirstMatchingByteTag(q))\n                {\n'
 '                    int64_t t = q.GetSenderTimestamp().GetNanoSeconds();\n'
 '                    if (oldest < 0 || t < oldest)\n                    {\n                        oldest = t;\n                    }\n                }\n            }\n        };\n'
 '        scan(m_txedBuffer, nTxed);\n        scan(m_retxBuffer, nRetx);\n'
 '        *tf << "E\\t" << Simulator::Now().GetNanoSeconds() << "\\t" << m_rnti << "\\t" << (uint32_t)m_lcid << "\\t" << m_imsi << "\\t"\n'
 '            << m_txonBuffer.size() << "\\t" << m_txonBufferSize << "\\t" << nTxed << "\\t" << nRetx << "\\t" << oldest << "\\n";\n'
 '        tf->flush();\n    }\n')
wr(n, s)

n = 'lte-enb-rrc.cc'; s = rd(n); assert 'R11cRrc' not in s
s = once(s, '#include <ns3/simulator.h>\n', '#include <ns3/simulator.h>\n\n#include <cstdlib>\n#include <fstream>\n#include <map>\n')
s = once(s, 'NS_LOG_COMPONENT_DEFINE("LteEnbRrc");\n',
 'NS_LOG_COMPONENT_DEFINE("LteEnbRrc");\n\n'
 'static std::ofstream*\nR11cRrc()\n{\n    static std::ofstream* f = std::getenv("ZT_R10_TRACE") ? new std::ofstream("R11C_rrc.txt") : nullptr;\n    return f;\n}\n')
s = once(s, '            if ((maxSinrDb < m_outageThreshold ||\n                 (m_imsiUsingLte[imsi] && maxSinrDb < m_outageThreshold + 2)) &&\n',
 '            if (auto* rf = R11cRrc())\n            {\n'
 '                static std::map<uint64_t, int64_t> r11cLast;\n'
 '                int64_t b = Simulator::Now().GetMilliSeconds() / 100;\n'
 '                auto li = r11cLast.find(imsi);\n'
 '                if (li == r11cLast.end() || li->second != b)\n                {\n'
 '                    r11cLast[imsi] = b;\n'
 '                    auto sc = m_lastMmWaveCell.find(imsi);\n                    auto ul = m_imsiUsingLte.find(imsi);\n'
 '                    *rf << "U\\t" << Simulator::Now().GetNanoSeconds() << "\\t" << imsi << "\\t"\n'
 '                        << (sc == m_lastMmWaveCell.end() ? -1 : (int)sc->second) << "\\t" << (double)currentSinrDb << "\\t"\n'
 '                        << maxSinrCellId << "\\t" << (double)maxSinrDb << "\\t"\n'
 '                        << (ul == m_imsiUsingLte.end() ? -1 : (int)ul->second) << "\\t" << alreadyAssociatedImsi << "\\n";\n'
 '                }\n            }\n'
 '            if ((maxSinrDb < m_outageThreshold ||\n                 (m_imsiUsingLte[imsi] && maxSinrDb < m_outageThreshold + 2)) &&\n')
s = once(s, 'UeManager::SendRrcConnectionSwitch(bool useMmWaveConnection)\n{\n',
 'UeManager::SendRrcConnectionSwitch(bool useMmWaveConnection)\n{\n'
 '    if (auto* rf = R11cRrc())\n    {\n'
 '        *rf << "W\\t" << Simulator::Now().GetNanoSeconds() << "\\t" << m_imsi << "\\t" << m_rnti << "\\t" << useMmWaveConnection << "\\n";\n    }\n')
s = once(s, 'LteEnbRrc::DoDispose()\n{\n    NS_LOG_FUNCTION(this);\n',
 'LteEnbRrc::DoDispose()\n{\n    NS_LOG_FUNCTION(this);\n    if (auto* rf = R11cRrc())\n    {\n        rf->flush();\n    }\n')
wr(n, s)

n = 'lte-ue-rrc.cc'; s = rd(n); assert 'R11C_rlf' not in s
s = once(s, '#include <ns3/simulator.h>\n', '#include <ns3/simulator.h>\n\n#include <cstdlib>\n#include <fstream>\n')
s = once(s, 'LteUeRrc::DoNotifyRadioLinkFailure(double lastSinrValue)\n{\n    NS_LOG_DEBUG("Rlf");\n',
 'LteUeRrc::DoNotifyRadioLinkFailure(double lastSinrValue)\n{\n    NS_LOG_DEBUG("Rlf");\n'
 '    if (std::getenv("ZT_R10_TRACE"))\n    {\n'
 '        static std::ofstream* f = new std::ofstream("R11C_rlf.txt");\n'
 '        *f << "L\\t" << Simulator::Now().GetNanoSeconds() << "\\t" << m_imsi << "\\t" << m_rnti << "\\t" << lastSinrValue << "\\n";\n'
 '        f->flush();\n    }\n')
wr(n, s)
print("patch_r11c OK")
