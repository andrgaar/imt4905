#!/usr/bin/python3

import sys
import json
from datetime import datetime

fname = sys.argv[1]

with open(fname, "r") as f:
    for line in f:
        timestamp, peer, event, data = line.strip().split(';')

        if event != 'TOPOLOGY UPDATE':
            continue
        
        seconds, ms = timestamp.split('.')
        dt_object = datetime.fromtimestamp(float(timestamp))

        topology = json.loads(data)
        peers = list(topology.keys())

        print(dt_object, peer, event, peers)



