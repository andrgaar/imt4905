#!/usr/bin/python3

import sys
import json
from datetime import datetime

peer_total = 0
prev_timestamp = None

fname = sys.argv[1]

with open(fname, "r") as f:
    for line in f:
        timestamp, peer, event, data = line.strip().split(';')

        if prev_timestamp == None:
            prev_timestamp = timestamp

        if event == "PEER ENTERED":
            peer_total = peer_total + 1
        elif event == "PEER EXITED":
            peer_total = peer_total - 1
        elif event == 'TOPOLOGY UPDATE':
            seconds, ms = timestamp.split('.')
            dt_event = datetime.fromtimestamp(float(timestamp))
            dt_prev = datetime.fromtimestamp(float(prev_timestamp))
            dt_diff = dt_event - dt_prev

            topology = json.loads(data)
            peers = list(topology.keys())

            print(dt_event, "+{0}".format(round(dt_diff.total_seconds())), peer, event, len(peers), peer_total)

            prev_timestamp = timestamp

        else:
            continue
        


