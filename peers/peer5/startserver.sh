#!/bin/bash

set -x

BASEDIR=$(dirname $0)

SCRIPTPATH="${BASEDIR}/../../rtun-routing"

export PYTHONPATH="${BASEDIR}/../../torpy-rtun-fork/"

# Setup OpenVPN
#mkdir -p /dev/net
#mknod /dev/net/tun c 10 200
#chmod 600 /dev/net/tun

# Download consensus doc
#python3 -m torpy --url https://facebookcorewwwi.onion

# Start rtun server
#python3 rtun.py -p -c -t peer1peer2 -n default -i 2 -d 1 &
python3 "$SCRIPTPATH/rtun.py" -v INFO -g lw -f rendezvous.txt -t peer1peer2 -n default -i 5 -d 6

