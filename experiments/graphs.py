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
ts = None
if len(sys.argv) == 3:
    ts = sys.argv[2]

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
        
        if event == 'TOPOLOGY UPDATE':

            if not peer in edges:
                edges[peer] = {}
            
            topology = json.loads(data)
            
            for k, d in topology.items():
                for ik in d:
                    d[ik] = {'weight': d[ik]}
            
            G = nx.DiGraph(topology)

            clustering[x] = nx.average_clustering(G)
            density[x] = nx.density(G)

            if ts and ts == timestamp:
                break
        
        if event == 'DEAD ROUTES RECEIVED':
            dead[x] = peer
            
            
# Clustering 
print("Clustering:")
for t in clustering:
    print(t, clustering[t])

# Density 
print("Density:")
for t in density:
    print(t, density[t])

# Topology graph
elarge = [(u, v) for (u, v, d) in G.edges(data=True) if d["weight"] > 1]
esmall = [(u, v) for (u, v, d) in G.edges(data=True) if d["weight"] <= 0]

pos = nx.spring_layout(G, seed=7)  # positions for all nodes - seed for reproducibility

# nodes
nx.draw_networkx_nodes(G, pos, node_size=700)

# edges
nx.draw_networkx_edges(G, pos, edgelist=elarge, width=6)
nx.draw_networkx_edges(
    G, pos, edgelist=esmall, width=6, alpha=0.5, edge_color="b", style="dashed"
)

# node labels
nx.draw_networkx_labels(G, pos, font_size=20, font_family="sans-serif")
# edge weight labels
edge_labels = nx.get_edge_attributes(G, "weight")
nx.draw_networkx_edge_labels(G, pos, edge_labels)

nx.write_latex(G, 'graph.latex', as_document=False)

ax = plt.gca()
ax.margins(0.08)
plt.axis("off")
plt.tight_layout()
plt.show()

