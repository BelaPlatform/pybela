#!/bin/bash -e
mkdir -p /sysroot/opt/pytorch-install

url=https://github.com/pelinski/bela-torch/releases/download/v2.5.1/pytorch-v2.5.1.tar.gz
echo "Downloading Pytorch from $url"
wget -O - $url | tar -xz -C /sysroot/opt/pytorch-install