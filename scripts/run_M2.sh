#!/bin/bash
# M2 service time：舊機器、閒置、核心 2；V 與 L 分屬兩個行程依序執行，重複 3 次（規格 M2 v1）
cd ~/oran-zt-kpm-verification
export ZT_DATASET=d30 ZT_FUSION_ORDER=severity
S=xapps/verification/adversarial/run_M2_service_time.py
waitidle() { for i in $(seq 1 60); do l=$(cut -d' ' -f1 /proc/loadavg); awk -v l=$l 'BEGIN{exit !(l<0.3)}' && return 0; sleep 10; done; echo "等待閒置逾時（load $l）"; exit 2; }
for n in 1 2 3; do
  waitidle; taskset -c 2 python3 $S --part V --run $n || exit 2
  waitidle; taskset -c 2 ~/venvs/drl/bin/python3 $S --part L --run $n || exit 2
done
python3 $S --part report
echo M2_DONE
