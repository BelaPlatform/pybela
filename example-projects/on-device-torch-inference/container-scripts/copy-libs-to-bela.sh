#!/bin/bash

echo "Copying libbelafull to Bela..."
rsync \
--timeout=10 \
-avzP  /sysroot/root/Bela/lib/libbelafull.so \
root@$BBB_HOSTNAME:Bela/lib/libbelafull.so

echo "Copying libtorch to Bela..."
rsync \
--timeout=10 \
-avzP  /sysroot/opt/pytorch-install/lib/libtorch_cpu.so /sysroot/opt/pytorch-install/lib/libtorch.so /sysroot/opt/pytorch-install/lib/libc10.so root@$BBB_HOSTNAME:Bela/lib/

echo "Finished"