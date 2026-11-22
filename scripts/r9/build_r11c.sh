#!/bin/bash
# Build r11c (= r11t + patch_r11c.py; observation only). r11 / r11t untouched. Niced.
set -u
SRC=$HOME/ns-3-mmwave-oran-r11t; DST=$HOME/ns-3-mmwave-oran-r11c; LOG=$HOME/build_r11c.log
exec > "$LOG" 2>&1
echo "start $(date '+%F %T')"
[ -e "$DST" ] && { echo "$DST exists, abort"; echo FAIL > $HOME/build_r11c.status; exit 1; }
rsync -a --exclude=/build --exclude=/cmake-cache --exclude='/.lock-ns3*' "$SRC/" "$DST/"
python3 "$HOME/oran-zt-kpm-verification/scripts/r9/patch_r11c.py" "$DST" || { echo FAIL > $HOME/build_r11c.status; exit 1; }
for f in lte-rlc-am.cc lte-enb-rrc.cc lte-ue-rrc.cc; do diff "$SRC/src/lte/model/$f" "$DST/src/lte/model/$f" > "$DST/r11c_$f.diff"; done
cd "$DST"
CXX=g++-13 CC=gcc-13 nice -n 15 ./ns3 configure --build-profile=optimized \
  --enable-modules="mmwave;oran-interface;applications;point-to-point;mobility;internet" \
  --disable-examples --disable-tests -- -DNS3_NATIVE_OPTIMIZATIONS=ON -DNS3_ASSERT=OFF -DNS3_LOG=OFF
rc=$?; [ $rc -ne 0 ] && { echo "configure rc=$rc"; echo FAIL > $HOME/build_r11c.status; exit 1; }
nice -n 15 ./ns3 build -j8; rc=$?
echo "build rc=$rc end $(date '+%F %T')"
[ $rc -ne 0 ] && { echo FAIL > $HOME/build_r11c.status; exit 1; }
echo OK > $HOME/build_r11c.status
