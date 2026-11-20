#!/bin/bash
# Build r11 (= r10 + patch_r11.py) and r11t (= r11 + patch_r10_trace.py). r10 / r10t / running jobs untouched. Niced.
set -u
SRC=$HOME/ns-3-mmwave-oran-r10; LOG=$HOME/build_r11.log
exec > "$LOG" 2>&1
echo "start $(date '+%F %T')"
for V in ${VARS:-r11 r11t}; do
  DST=$HOME/ns-3-mmwave-oran-$V
  [ -e "$DST" ] && { echo "$DST exists, abort"; echo FAIL > $HOME/build_r11.status; exit 1; }
  rsync -a --exclude=/build --exclude=/cmake-cache --exclude='/.lock-ns3*' "$SRC/" "$DST/"
  python3 "$HOME/oran-zt-kpm-verification/scripts/r9/patch_r11.py" "$DST" || { echo FAIL > $HOME/build_r11.status; exit 1; }
  [ "$V" = r11t ] && { python3 "$HOME/oran-zt-kpm-verification/scripts/r9/patch_r10_trace.py" "$DST" || { echo FAIL > $HOME/build_r11.status; exit 1; }; }
  cd "$DST"
  CXX=g++-13 CC=gcc-13 nice -n 15 ./ns3 configure --build-profile=optimized \
    --enable-modules="mmwave;oran-interface;applications;point-to-point;mobility;internet" \
    --disable-examples --disable-tests -- -DNS3_NATIVE_OPTIMIZATIONS=ON -DNS3_ASSERT=OFF -DNS3_LOG=OFF
  rc=$?; [ $rc -ne 0 ] && { echo "$V configure rc=$rc"; echo FAIL > $HOME/build_r11.status; exit 1; }
  nice -n 15 ./ns3 build -j8; rc=$?
  echo "$V build rc=$rc end $(date '+%F %T')"
  [ $rc -ne 0 ] && { echo FAIL > $HOME/build_r11.status; exit 1; }
done
echo OK > $HOME/build_r11.status
