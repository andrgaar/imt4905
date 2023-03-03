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

topology = {}

fname = sys.argv[1]

with open(fname, "r") as f:

    edges = {}
    dead = {}
    updates = {}
    dt_diff = 0
    g_prev = None    
    diff = None
    G = None
    clustering = {}
    density = {}

    for line in f:
        timestamp, peer, event, data = line.strip().split(';')

        if prev_timestamp == None:
            prev_timestamp = timestamp

        dt_event = datetime.fromtimestamp(float(timestamp))
        dt_prev = datetime.fromtimestamp(float(prev_timestamp))
        dt_diff = dt_event - dt_prev
        
        x = round(dt_diff.total_seconds())
        
        if event == 'TOPOLOGY UPDATE' and peer == "P1":

            if not peer in edges:
                edges[peer] = {}
            
            topology = json.loads(data)
            
            for k, d in topology.items():
                for ik in d:
                    d[ik] = {'weight': d[ik]}
            
            G = nx.DiGraph(topology)

            clustering[x] = nx.average_clustering(G)
            density[x] = nx.density(G)
        
        if event == 'DEAD ROUTES RECEIVED':
            dead[x] = peer
            
fig, axs = plt.subplots(2, sharex=True)
#fig.suptitle('Average clustering coeffisient and density')

# Clustering 
print("Clustering:")
for t in clustering:
    print(t, clustering[t])

x = list(clustering.keys())
y = list(clustering.values())
axs[0].step(x, y, where="post", color="black", marker='o', linestyle='dashed', label="Clustering coeff.")
axs[0].set_xlabel("Time(s)")
axs[0].set_ylabel("Clustering coeff.")

# Density 
print("Density:")
for t in density:
    print(t, density[t])

x = list(density.keys())
y = list(density.values())
axs[1].step(x, y, where="post", color="black", marker='o', linestyle='dashed', label="Average density")
axs[1].set_xlabel("Time(s)")
axs[1].set_ylabel("Avg. density")

for t in dead.keys():
    axs[0].axvline(t, color = 'r')
    axs[1].axvline(t, color = 'r')

#fig.legend()
plt.show()

