#!/bin/bash

set -x

# Setup OpenVPN
mkdir -p /dev/net
mknod /dev/net/tun c 10 200
chmod 600 /dev/net/tun

# Download consensus doc
#python3 -m torpy --url https://facebookcorewwwi.onion

# Start rtun server
python3 rtun.py -g vanguardarchie -p -l -t peer1peer2 -n default -i 1 -d 2
