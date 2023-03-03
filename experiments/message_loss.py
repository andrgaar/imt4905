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

sent = {}
rcvd = {}
dead = {}
loss = {}

fname = sys.argv[1]
start = None

if len(sys.argv) == 3:
    start = sys.argv[2]


with open(fname, "r") as f:

    #fout = open(f"{fname}.csv", "w")

    #fout.write("{0};{1};{2};{3}\n".format("Timestamp", "Offset", "Event", "Path"))
    #fout.write("{0};{1};{2};{3}\n".format("Offset", "Sent", "P1-P2-P4", "P1-P3-P4"))
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

        if event == 'LOOKUP SENT' or event == 'LOOKUP RECEIVED':
            d = json.loads(data)
            
            if event == 'LOOKUP SENT':
                # to, from, time 
                t = (d['Peer'], peer, diff_sec)
                sent[d['ID']] = t
                loss[d['ID']] = t

            elif event == 'LOOKUP RECEIVED':
                r = d[0]
                path = '-'.join(r['Path'])
                # to, from, path, time 
                t = (r['Destination'], r['Source'], path, diff_sec)
                rcvd[r['ID']] = t
                loss.pop(r['ID'])

        elif event == 'DEAD ROUTES DETECTED' and peer == "P1":
            dead[diff_sec] = 1

# Plot data
fig, (ax2, ax1) = plt.subplots(2, sharex=True)

plt_sent = {}

for k, v in sent.items():
    plt_sent[v[2]] = 1
    print("Sent ", k, v)
print("Total sent: ", len(sent))

plt_path = {}
for k, v in rcvd.items():
    pt = {}
    pt[v[3]] = 1
    #if v[2] in plt_path:
    #    plt_path[v[2]].update(pt)
    #else:
    #    plt_path[v[2]] = pt
    plt_path[v[3]] = v[2]
    print("Received ", k, v)
print("Total received: ", len(rcvd))


#for k, v in plt_path.items():
#    if k == 'P1-P2-P4':
#        marker = '^k:'
#    else:
#        marker = 'vk:'
        
#    ax1.plot(list(v.keys()), list(v.values()), marker, label=k)
marker = 'vk'
ax1.plot(list(plt_path.keys()), list(plt_path.values()), marker, label="Message received")

plt_loss = {}
first_loss = None
last_loss = None
for k,v in sent.items():
    plt_loss[v[2]] = 'Success'
for k,v in loss.items():
    plt_loss[v[2]] = 'Fail'
    if not first_loss:
        first_loss = v[2]
    last_loss = v[2]
print("Total loss: ", len(loss))
print("First loss: ", first_loss, " Last loss: ", last_loss)

ax2.plot(list(plt_loss.keys()), list(plt_loss.values()), 'vk', label="Message sent")
# dead routes
for k, v in dead.items():
    ax1.axvline(x = k, color = 'k', ymin = 0.25, ymax = 1, linestyle = '--', label = 'Dead route detected')
    ax2.axvline(x = k, color = 'k', ymin = 0.25, ymax = 1, linestyle = '--', label = 'Dead route detected')

# Stats
print("Pct of failed messages: ", round( len(loss) / len(sent) * 100 ))

#plt.figsize=(12, 6)
ax1.set_yticks([0,1])
#ax2.set_yticks([0,1])
ax1.set_xlabel('Time (s)')
ax2.set_xlabel('Time (s)')
ax1.set_ylabel('Path selected')
ax2.set_ylabel('Result')
ax1.set_title('Messages received by path')
ax2.set_title('Messages sent')
ax1.legend()
ax2.legend()
fig.tight_layout()
plt.show()

