#!/bin/bash
# Build r8d with g++-13 in a fresh dir (source copied from ~/ns-3-mmwave-oran-r8d; that tree untouched). D30P1_ho_pilot_spec.md §8a
set -u
SRC=$HOME/ns-3-mmwave-oran-r8d; DST=$HOME/ns-3-mmwave-oran-r8d-g13; LOG=$HOME/build_r8d_g13.log; ST=$HOME/build_r8d_g13.status
exec > "$LOG" 2>&1
echo "start $(date '+%F %T')"
[ -e "$DST" ] && { echo "DST exists, abort"; echo FAIL > $ST; exit 1; }
md5sum $SRC/build/scratch/ns3.38.rc1-scenario-three-optimized $SRC/build/lib/libns3.38.rc1-lte-optimized.so $SRC/src/lte/model/lte-rlc-am.cc $SRC/src/lte/model/lte-enb-rrc.cc
rsync -a --exclude=/build --exclude=/cmake-cache --exclude='/.lock-ns3*' "$SRC/" "$DST/"
diff -rq --exclude=build --exclude=cmake-cache --exclude='.lock-ns3*' "$SRC" "$DST" && echo "SOURCE IDENTICAL" || { echo "SOURCE DIFF"; echo FAIL > $ST; exit 1; }
cd "$DST"
CXX=g++-13 CC=gcc-13 ./ns3 configure --build-profile=optimized \
  --enable-modules="mmwave;oran-interface;applications;point-to-point;mobility;internet" \
  --disable-examples --disable-tests -- -DNS3_NATIVE_OPTIMIZATIONS=ON -DNS3_ASSERT=OFF -DNS3_LOG=OFF
rc=$?; [ $rc -ne 0 ] && { echo "configure rc=$rc"; echo FAIL > $ST; exit 1; }
./ns3 build -j12; rc=$?
echo "build rc=$rc end $(date '+%F %T')"
readelf -p .comment build/lib/libns3.38.rc1-mmwave-optimized.so | grep -o 'GCC.*' | sort -u
for k in CMAKE_BUILD_TYPE NS3_NATIVE_OPTIMIZATIONS NS3_ASSERT NS3_LOG NS3_ENABLED_MODULES NS3_EXAMPLES NS3_TESTS CMAKE_CXX_COMPILER: ; do
  for d in r8d r8d-g13 r11c; do echo "KEY $k | $d: $(grep -m1 "^$k" $HOME/ns-3-mmwave-oran-$d/cmake-cache/CMakeCache.txt)"; done; done
[ $rc -eq 0 ] && echo OK > $ST || echo FAIL > $ST
