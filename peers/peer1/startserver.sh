#!/bin/bash

set -x

export PYTHONPATH=/root/git/torpy-rtun-fork/

# Setup OpenVPN
#mkdir -p /dev/net
#mknod /dev/net/tun c 10 200
#chmod 600 /dev/net/tun

# Download consensus doc
#rm /root/.local/share/torpy/network_status
#python3 -m torpy --url https://facebookcorewwwi.onion

# Start rtun server
#python3 rtun.py -g Quintex13 -p -l -t peer1peer2 -n default -i 1 -d 2
python3 rtun.py -g Tororist1 -r a9 -k eb688e4f52df90278060 -l -t peer1peer2 -n default -i 1 -d 2
