#!/bin/bash
# build_r11 完成後：r11t 開／關各 6 s → check_r11_trace.py；報表寫入 ~/r11t_report.txt（完成才建立 DONE 標記）
set -u
R=$HOME/r11t_report.txt; rm -f $R $HOME/r11t_report.done
while [ ! -s $HOME/build_r11.status ]; do sleep 30; done
S=$(cat $HOME/build_r11.status); echo "build=$S" > $R
if [ "$S" != OK ]; then grep -m8 "error" $HOME/build_r11.log | cut -c1-260 >> $R; touch $HOME/r11t_report.done; exit 1; fi
bash $HOME/oran-zt-kpm-verification/scripts/r9/run_r11t.sh >> $R 2>&1
O=$HOME/oran-zt-kpm-verification/data/r11_trace
for v in on off; do echo "$v: $(tail -n 1 $O/$v/run.log)" >> $R; done
cat $O/cmp_vs_r10t.txt >> $R
cd $HOME/oran-zt-kpm-verification/scripts/r9 && ~/venvs/drl/bin/python check_r11_trace.py 2>&1 | cut -c1-300 >> $R
touch $HOME/r11t_report.done
