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

def main():

    with open(fname, "r") as f:
        for line in f:
            timestamp, peer, data = line.strip().split(';')
     
            graph = json.loads(data)
            adjacency_list , graph_nodes, rp_nodes = organizeGraph(graph)

            for k, d in adjacency_list.items():
                for ik in d:
                    d[ik] = {'weight': d[ik]}
            
            G = nx.DiGraph(adjacency_list)
            print(G)

            if nx.number_of_edges(G) > 0 and nx.average_clustering(G) > 0:
                draw_graph(G)
            
def draw_graph(G):
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


# Uses the global graph to construct a adjacency list
# (represented using python 'dict') which in turn is
# used by the Dijkstra function to compute shortest paths
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
