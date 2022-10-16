#!/bin/bash

set -x

# Setup OpenVPN
#mkdir -p /dev/net
#mknod /dev/net/tun c 10 200
#chmod 600 /dev/net/tun

# Download consensus doc
#python3 -m torpy --url https://facebookcorewwwi.onion

# Start rtun server
python3 rtun.py -p -c -t peer1peer2 -n default -i 2 -d 1 &
#python3 rtun.py -r MonsterEdgeRangers -k 3148d35cc3353845db51 -c -t peer1peer2 -n default -i 2 -d 1 &

sleep 10

# Start a ping of the peer
ping 10.1.0.1
