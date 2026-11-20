#!/bin/bash
# Build r10 (= r9-g13 + patch_r10.py) in a fresh dir; r9-g13 (running 100 UE probe) untouched. Niced.
set -u
SRC=$HOME/ns-3-mmwave-oran-r9-g13; DST=$HOME/ns-3-mmwave-oran-r10; LOG=$HOME/build_r10.log
exec > "$LOG" 2>&1
echo "start $(date '+%F %T')"
[ -e "$DST" ] && { echo "DST exists, abort"; echo FAIL > $HOME/build_r10.status; exit 1; }
rsync -a --exclude=/build --exclude=/cmake-cache --exclude='/.lock-ns3*' "$SRC/" "$DST/"
python3 "$HOME/oran-zt-kpm-verification/scripts/r9/patch_r10.py" "$DST" || { echo FAIL > $HOME/build_r10.status; exit 1; }
diff -rq --exclude=build --exclude=cmake-cache --exclude='.lock-ns3*' --exclude=.git "$SRC" "$DST"
cd "$DST"
CXX=g++-13 CC=gcc-13 nice -n 15 ./ns3 configure --build-profile=optimized \
  --enable-modules="mmwave;oran-interface;applications;point-to-point;mobility;internet" \
  --disable-examples --disable-tests -- -DNS3_NATIVE_OPTIMIZATIONS=ON -DNS3_ASSERT=OFF -DNS3_LOG=OFF
rc=$?; [ $rc -ne 0 ] && { echo "configure rc=$rc"; echo FAIL > $HOME/build_r10.status; exit 1; }
nice -n 15 ./ns3 build -j8; rc=$?
echo "build rc=$rc end $(date '+%F %T')"
[ $rc -eq 0 ] && echo OK > $HOME/build_r10.status || echo FAIL > $HOME/build_r10.status
