#!/bin/bash
# Build r9 with g++-13 in a fresh dir (source copied from ~/ns-3-mmwave-oran-r9; that build untouched)
set -u
SRC=$HOME/ns-3-mmwave-oran-r9; DST=$HOME/ns-3-mmwave-oran-r9-g13; LOG=$HOME/build_r9g13.log
exec > "$LOG" 2>&1
echo "start $(date '+%F %T')"
[ -e "$DST" ] && { echo "DST exists, abort"; echo FAIL > $HOME/build_r9g13.status; exit 1; }
rsync -a --exclude=/build --exclude=/cmake-cache --exclude='/.lock-ns3*' "$SRC/" "$DST/"
# source identity check (everything except build products)
diff -rq --exclude=build --exclude=cmake-cache --exclude='.lock-ns3*' "$SRC" "$DST" && echo "SOURCE IDENTICAL"
cd "$DST"
CXX=g++-13 CC=gcc-13 ./ns3 configure --build-profile=optimized \
  --enable-modules="mmwave;oran-interface;applications;point-to-point;mobility;internet" \
  --disable-examples --disable-tests -- -DNS3_NATIVE_OPTIMIZATIONS=ON -DNS3_ASSERT=OFF -DNS3_LOG=OFF
rc=$?; [ $rc -ne 0 ] && { echo "configure rc=$rc"; echo FAIL > $HOME/build_r9g13.status; exit 1; }
./ns3 build -j12; rc=$?
echo "build rc=$rc end $(date '+%F %T')"
readelf -p .comment build/lib/libns3.38.rc1-mmwave-optimized.so | grep -o 'GCC.*' | sort -u
for k in CMAKE_BUILD_TYPE NS3_NATIVE_OPTIMIZATIONS NS3_ASSERT NS3_LOG NS3_ENABLED_MODULES NS3_EXAMPLES NS3_TESTS CMAKE_CXX_FLAGS_RELEASE CMAKE_CXX_FLAGS: ; do
  echo "KEY $k | r9: $(grep -m1 "^$k" $SRC/cmake-cache/CMakeCache.txt) | g13: $(grep -m1 "^$k" cmake-cache/CMakeCache.txt)"; done
[ $rc -eq 0 ] && echo OK > $HOME/build_r9g13.status || echo FAIL > $HOME/build_r9g13.status
