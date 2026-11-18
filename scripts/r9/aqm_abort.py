#!/usr/bin/env python3
"""r9 addendum: F4 supports only EnableAQM=false -> abort instead of warning.  Apply to an r9 tree: aqm_abort.py <ns3_dir>
Default EnableAQM=false and scenario-three never sets it, so no existing output changes."""
import sys
n = sys.argv[1].rstrip('/') + '/src/lte/model/lte-rlc-am.cc'
s = open(n).read()
def once(s, old, new):
    assert s.count(old) == 1, (old[:70], s.count(old)); return s.replace(old, new)
s = once(s, '        std::cerr << "ZT_R8D AQM not supported by F4" << std::endl;\n',
         '        NS_FATAL_ERROR("ZT_R8D AQM not supported by F4 (EnableAQM must be false)");\n')
s = once(s, '    ++m_txPacketsInReportingPeriod;\n    m_txBytesInReportingPeriod += p->GetSize();\n\n    if (m_enableAqm == false)\n',
         '    ++m_txPacketsInReportingPeriod;\n    m_txBytesInReportingPeriod += p->GetSize();\n\n    NS_ABORT_MSG_IF(m_enableAqm, "ZT_R8D AQM not supported by F4 (EnableAQM must be false)");\n    if (m_enableAqm == false)\n')
if '#include "ns3/abort.h"' not in s and '#include <ns3/abort.h>' not in s:
    i = s.index('#include'); s = s[:i] + '#include "ns3/abort.h"\n#include "ns3/fatal-error.h"\n' + s[i:]
open(n, 'w').write(s); print('patched', n)
