#!/usr/bin/python3

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import networkx as nx
import numpy as np
import pandas as p
import sys
import json
from datetime import datetime

prev_timestamp = None
epoch_time = datetime(1970, 1, 1)

graphs = []
topology = {}
last_time = {} # last time peer seen
ax = None


fname = sys.argv[1]
#offset = int(sys.argv[2])

def main():
    prev_timestamp = None

    global ax
    fig, ax = plt.subplots(figsize=(6,4))

    with open(fname, "r") as f:
        for line in f:
            timestamp, peer, data = line.strip().split(';')
            
            if not prev_timestamp:
                prev_timestamp = timestamp

            dt_event = datetime.fromtimestamp(float(timestamp))
            dt_prev = datetime.fromtimestamp(float(prev_timestamp))
            dt_offset = round((dt_event - dt_prev).total_seconds())

            last_time[peer] = dt_event
            # remove peers not seen in last minute
            remove = set()
            for k, v in last_time.items():
                if (dt_event - v).total_seconds() > 60:
                    remove.add(k)
            for k in remove:
                del last_time[k]
                graphs.pop(k)

            if peer == "P1":
                graph = json.loads(data)
                adjacency_list , graph_nodes, rp_nodes = organizeGraph(graph)

                for k, d in adjacency_list.items():
                    for ik in d:
                        d[ik] = {'weight': d[ik] * -1}
                
                G = nx.Graph(adjacency_list)
                
                graphs.append(G)


    ani = FuncAnimation(fig, draw_graph, frames=len(graphs), interval=500, repeat=True)
    plt.show()
    
            
def draw_graph(i):

    global graphs
    G = graphs.pop(0)

    global ax
    ax.clear()

    # Topology graph
    elarge = [(u, v) for (u, v, d) in G.edges(data=True) if d["weight"] > -1000]
    esmall = [(u, v) for (u, v, d) in G.edges(data=True) if d["weight"] == -1000]

    init_pos = {'P1':(100,100), 'P2':(200,100),'P3':(50,150),'P4':(250,50),'P5':(50,100),'P6':(250,100),'P7':(50,50),'P8':(250,150)}

    pos = nx.spring_layout(G, pos=init_pos, fixed=['P1'], weight='weight')  # positions for all nodes - seed for reproducibility
    #pos = nx.circular_layout(G)  # positions for all nodes - seed for reproducibility
    #pos = nx.kamada_kawai_layout(G, pos=init_pos, weight=None)  # positions for all nodes - seed for reproducibility

    # nodes
    nx.draw_networkx_nodes(G, pos, node_size=700)

    # edges
    nx.draw_networkx_edges(G, pos, edgelist=elarge, width=3)
    nx.draw_networkx_edges(
    G, pos, edgelist=esmall, width=6, alpha=0.5, edge_color="b", style="dashed"
    )

    # node labels
    nx.draw_networkx_labels(G, pos, font_size=20, font_family="sans-serif")
    # edge weight labels
    edge_labels = nx.get_edge_attributes(G, "weight")
    #nx.draw_networkx_edge_labels(G, pos, edge_labels)

    #nx.write_latex(G, 'graph.latex', as_document=False)

    #ax = plt.gca()
    #ax.margins(0.08)
    #plt.axis("off")
    #plt.tight_layout()
    plt.title(f"frame {i}")

def organizeGraph(graph_arg):

    # Set to contain nodes within graph
    nodes = set()

    # Determine nodes in entire topology
    # and update set of nodes
    for node in graph_arg:
        if node[0] not in nodes:
            nodes.add(node[0])
            #nodes.add(node[0] + node[3])
        if node[1] not in nodes:
            nodes.add(node[1])
            #nodes.add(node[1]+node[3])

    # Sort nodes alphabetically
    sorted_nodes = sorted(nodes)

    # Create dict to store all edges between
    # vertices as an adjacency list
    new_LL = dict()
    new_RP = dict() # holds RP of peer
    for node in sorted_nodes:
        new_LL[node] = dict()
        new_RP[node] = dict()

    # Using all link-state advertisement received
    # from all nodes, create the initial adjacency list
    # based solely on data received from neighbours
    for node in sorted_nodes:
        for link in graph_arg:
            if node == link[0]:
                new_LL[node].update({link[1] : link[2]})
                new_RP[node].update({link[1] : link[3]})

    # Update adjacency list so as to reflect all outgoing/incoming
    # links (Graph should now fully represent the network topology
    for node in sorted_nodes:
        for source_node , cost in new_LL[node].items():
            new_LL[source_node].update({node : cost})
        for source_node , rp_node in new_RP[node].items():
            new_RP[source_node].update({node : rp_node})


    # Return adjacency list and least_cost_path dict
    # to use for Dijkstra Computation
    return (new_LL , sorted_nodes, new_RP)

if __name__ == '__main__':
    main()
