#!/usr/bin/env python3
"""P-4 test hook (TEST TREE ONLY, never for data):  patch_p4_test.py <ns3_dir>
Adds to scratch/scenario-three.cc: env ZT_P4_HO="ms:imsi:target[,ms:imsi:target...]" schedules a manual handover of the UE (through the
same calls as the control-file path F9: TakeUeHoControl + PerformHandoverToTargetCell) at the given simulation time in ms.
target = 0 -> the next mmWave cell (2..8).  F9 itself can only act at E2 period + 5 ms (lte-enb-net-device.cc:1042), so it cannot make
a handover in the middle of a window.  One 'ZT_P4 HO ...' line per command on stderr."""
import sys
p = sys.argv[1].rstrip('/') + '/scratch/scenario-three.cc'
s = open(p).read(); assert 'ZT_P4' not in s
old = '  bool run = true;\n  if (run)\n'
assert s.count(old) == 1
new = '''  // ---- P-4 test hook (TEST TREE ONLY)
  if (const char* p4 = std::getenv ("ZT_P4_HO"))
    {
      std::string spec (p4);
      std::stringstream ss (spec);
      std::string item;
      while (std::getline (ss, item, ','))
        {
          long ms = 0; unsigned long imsiX = 0; unsigned tgtX = 0;
          if (std::sscanf (item.c_str (), "%ld:%lu:%u", &ms, &imsiX, &tgtX) != 3) continue;
          Simulator::Schedule (MilliSeconds (ms), [lte_rrc, imsiX, tgtX] () {
            uint16_t rnti = lte_rrc->GetRntiFromImsi (imsiX);
            uint16_t src = lte_rrc->GetUeManager (rnti)->GetMmWaveCellId ();
            uint16_t tc = tgtX ? tgtX : (src - 2 + 1) % 7 + 2;
            std::cerr << "ZT_P4 HO t_ns=" << Simulator::Now ().GetNanoSeconds () << " imsi=" << imsiX
                      << " src=" << src << " tgt=" << tc << std::endl;
            if (tc == src) return;
            lte_rrc->TakeUeHoControl (imsiX);
            Simulator::ScheduleWithContext (1, Seconds (0), &LteEnbRrc::PerformHandoverToTargetCell, lte_rrc, imsiX, tc);
          });
        }
    }

'''
s = s.replace(old, new + old)
if '#include <cstdio>' not in s:
    i = s.index('#include'); s = s[:i] + '#include <cstdio>\n#include <cstdlib>\n#include <sstream>\n' + s[i:]
open(p, 'w').write(s); print('patched', p)
