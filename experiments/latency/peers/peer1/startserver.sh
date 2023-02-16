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
#rm /root/.local/share/torpy/network_status
#python3 -m torpy --url https://facebookcorewwwi.onion

# Start rtun server
#python3 rtun.py -g Quintex13 -p -l -t peer1peer2 -n default -i 1 -d 2
#python3 rtun.py -g Unnamed -r bauruine -k eb688e4f52df90278060 -l -t peer1peer2 -n default -i 1 -d 2
python3 "$SCRIPTPATH/rtun.py" -v INFO -g staysafeandgoodluck -f rendezvous.txt -l -t peer1peer2 -n default -i 1 -d 2
