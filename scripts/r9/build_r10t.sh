#!/bin/bash
set -u
SRC=$HOME/ns-3-mmwave-oran-r10; DST=$HOME/ns-3-mmwave-oran-r10t; LOG=$HOME/build_r10t.log
exec > "$LOG" 2>&1
[ -e "$DST" ] && { echo "DST exists"; echo FAIL > $HOME/build_r10t.status; exit 1; }
rm -f $HOME/build_r10t.status
rsync -a --exclude=/build --exclude=/cmake-cache --exclude='/.lock-ns3*' "$SRC/" "$DST/"
python3 "$HOME/oran-zt-kpm-verification/scripts/r9/patch_r10_trace.py" "$DST" || { echo FAIL > $HOME/build_r10t.status; exit 1; }
cd "$DST"
CXX=g++-13 CC=gcc-13 nice -n 15 ./ns3 configure --build-profile=optimized --enable-modules="mmwave;oran-interface;applications;point-to-point;mobility;internet" --disable-examples --disable-tests -- -DNS3_NATIVE_OPTIMIZATIONS=ON -DNS3_ASSERT=OFF -DNS3_LOG=OFF || { echo FAIL > $HOME/build_r10t.status; exit 1; }
nice -n 15 ./ns3 build -j8; rc=$?
[ $rc -eq 0 ] && echo OK > $HOME/build_r10t.status || echo FAIL > $HOME/build_r10t.status
