#!/bin/bash

echo "Building pybela DrumSynth..."

cmake -S . -B build \
-DPROJECT_NAME=pybela-drumsynth-inference \
-DCMAKE_TOOLCHAIN_FILE=../Toolchain.cmake \
-DCMAKE_SYSROOT=/sysroot/root/Bela/
# -DCMAKE_CURRENT_SOURCE_DIR=$(pwd)/src

cmake --build build -j

echo "Copying drumsynth project to Bela..."
rsync \
--timeout=10 \
-avzP build/pybela-drumsynth-inference \
root@$BBB_HOSTNAME:~/Bela/projects/pybela-drumsynth-inference/