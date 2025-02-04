#!/bin/bash
git clone https://github.com/BelaPlatform/bb.org-overlays.git /sysroot/opt/bb.org-overlays
cd /sysroot/opt/bb.org-overlays
echo "Push Bela overlay to Bela..."
git remote add board $BBB_HOSTNAME:/opt/bb.org-overlays
ssh $BBB_HOSTNAME "cd /opt/bb.org-overlays && git config receive.denyCurrentBranch updateInstead"
git push -f board master:master
ssh $BBB_HOSTNAME "cd /opt/bb.org-overlays && git config --unset receive.denyCurrentBranch"
ssh $BBB_HOSTNAME "cd /opt/bb.org-overlays && git checkout master"

echo "Rebuilding Bela overlay..."
ssh $BBB_HOSTNAME "cd /opt/bb.org-overlays && make clean && make && make install"
ssh $BBB_HOSTNAME "make -C /root/Bela/resources/tools/board_detect/ board_detect install"
ssh $BBB_HOSTNAME "reboot"
echo "Rebooting Bela..."