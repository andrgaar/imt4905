#!/usr/bin/python3

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as p
import sys
import json
from datetime import datetime

prev_timestamp = None
epoch_time = datetime(1970, 1, 1)

next_hop = {}
last_hop = None
time_hop = {}
last_time = 0

fname = sys.argv[1]
start = None

if len(sys.argv) == 3:
    start = sys.argv[2]


with open(fname, "r") as f:

    for line in f:
        timestamp, peer, event, data = line.strip().split(';')
        
        if start and timestamp < start:
            continue

        if prev_timestamp == None:
            prev_timestamp = timestamp

        dt_event = datetime.fromtimestamp(float(timestamp))
        dt_prev = datetime.fromtimestamp(float(prev_timestamp))
        dt_diff = dt_event - dt_prev
        diff_sec = round(dt_diff.total_seconds())

        if event == 'LEAST COST PATH':
            d = json.loads(data)
            if 'P5' in d:
                n = d['P5'][0]
                if not n in time_hop:
                    time_hop[n] = 0
                    last_time = diff_sec
                if n != last_hop:
                    next_hop[diff_sec] = n
                    time_hop[n] = time_hop[n] + ( diff_sec - last_time )
                    last_time = diff_sec
                    last_hop = n

for k, v in next_hop.items():
    print(k, v)

total_time = 0
for k, v in time_hop.items():
    print(k, v)
    total_time += v
print("Total: ", total_time)
for k, v in time_hop.items():
    print(k, round(v / total_time * 100))


x = list(next_hop.keys())
y = list(next_hop.values())

# Plot data
#fig, (ax1) = plt.subplots(2)

plt.step(x, y, 'ko:', label='P1 route selection')
#plt.figsize=(12, 6)
#ax1.set_yticks([0,1])
#ax2.set_yticks([0,1])
plt.xlabel('Time (s)')
#ax2.set_xlabel('Time (s)')
plt.ylabel('Next hop')
#ax2.set_ylabel('Result')
#ax1.set_title('Messages received by path')
#ax2.set_title('Messages sent')
plt.legend()
#ax2.legend()
#fig.tight_layout()
plt.show()

