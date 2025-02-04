#!/bin/bash

ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 $BBB_HOSTNAME "date -s \"`date '+%Y%m%d %T %z'`\" > /dev/null" 

cd /sysroot/root/Bela
echo "Changing Bela branch to $(git rev-parse --short HEAD)..."
git remote remove board
git remote add board $BBB_HOSTNAME:Bela/
ssh $BBB_HOSTNAME "cd Bela && git config receive.denyCurrentBranch updateInstead"
git push -f board tmp:tmp
ssh $BBB_HOSTNAME "cd Bela && git config --unset receive.denyCurrentBranch"
ssh $BBB_HOSTNAME "cd Bela && git checkout tmp"

echo "Rebuilding Bela core and libraries..."
ssh $BBB_HOSTNAME "cd Bela && make lib"
ssh $BBB_HOSTNAME "cd Bela && make -f Makefile.libraries all"
# check for clock skew and rebuild if necessary
ssh $BBB_HOSTNAME "cd Bela && make lib 2>&1 | tee logfile || exit 1;
grep -q \"skew detected\" logfile && { echo CLOCK SKEW DETECTED. CLEANING CORE AND TRYING AGAIN && make coreclean && make lib; } || exit 0;"
ssh $BBB_HOSTNAME "cd Bela && make -f Makefile.libraries all 2>&1 | tee logfile || exit 1;
grep -q \"skew detected\" logfile && { echo CLOCK SKEW DETECTED. CLEANING LIBRARIES AND TRYING AGAIN && make -f Makefile.libraries cleanall && make -f Makefile.libraries all; } || exit 0;"