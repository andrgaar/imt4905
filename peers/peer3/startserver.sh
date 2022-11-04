#!/bin/bash

set -x

export PYTHONPATH=/root/git/imt4905/torpy-rtun-fork/

# Setup OpenVPN
#mkdir -p /dev/net
#mknod /dev/net/tun c 10 200
#chmod 600 /dev/net/tun

# Download consensus doc
#python3 -m torpy --url https://facebookcorewwwi.onion

# Start rtun server
#python3 rtun.py -p -c -t peer1peer2 -n default -i 2 -d 1 &
python3 rtun.py -r MIGHTYWANG -k eb688e4f52df90278060 -c -t peer1peer2 -n default -i 3 -d 1 

sleep 10

# Start a ping of the peer
ping 10.1.0.1
