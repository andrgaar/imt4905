#!/usr/bin/python3

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
import seaborn as sns
import sys
import json
from datetime import datetime

epoch_time = datetime(1970, 1, 1)

graphs = {}
last_time = {} # last time peer seen

fname = sys.argv[1]
csvfile = f"{fname}.csv"

def main():

    fout = open(csvfile, "w")
    fout.write("Timestamp;Offset;Convergence\n")
    prev_timestamp = None

    with open(fname, "r") as f:
        x = list()
        y = list()

        for line in f:
            timestamp, peer, data = line.strip().split(';')
            
            if not prev_timestamp:
                prev_timestamp = timestamp

            dt_event = datetime.fromtimestamp(float(timestamp))
            dt_prev = datetime.fromtimestamp(float(prev_timestamp))
            dt_offset = (dt_event - dt_prev).total_seconds()

            last_time[peer] = dt_event
            # remove peers not seen in last minute
            remove = set()
            for k, v in last_time.items():
                if (dt_event - v).total_seconds() > 60:
                    remove.add(k)
            for k in remove:
                del last_time[k]
                graphs.pop(k)

            graph = json.loads(data)
            adjacency_list , graph_nodes, rp_nodes = organizeGraph(graph)

            for k, d in adjacency_list.items():
                for ik in d:
                    d[ik] = {'weight': d[ik]}
            
            G = nx.Graph(adjacency_list)
            hits, total, equal_sets = convergence(G, peer)
           
            pct = 100
            if total > 0:
                pct = round(hits / total * 100) 
            #print(timestamp, peer, pct, hits, total, ":")

            #for p, g in graphs.items():
            #    print(p, ":", nx.edges(g))
            
            # output 
            fout.write("{0};{1};{2}\n".format(dt_event, dt_offset, pct))
            #if nx.number_of_edges(G) > 0 and nx.average_clustering(G) > 0:
            #    draw_graph(G)
        fout.close()

    # plot data
    csv = pd.read_csv(csvfile, sep=";")
    print(csv)

    csv.plot(x = "Offset", y = "Convergence", kind="line", color = 'k', figsize=(10, 5), title="Convergence",
            xlabel = "Time (s)", ylabel = "Percent")
    plt.show()

    sns.relplot(
        data=csv, kind="line",
        x="Offset", y="Convergence", 
        #col="align", hue="choice", size="coherence", style="choice",
        facet_kws=dict(sharex=False),
    )
    plt.show()
    

def convergence(G, peer):

    graphs[peer] = G
    g = list()
    unique_edges = set()
    equal = 0

    for v in graphs.values():
        for e in nx.edges(v):
            unique_edges.add(e)
    #print("Edges: ", unique_edges)
    num_edges = len(unique_edges)
    if num_edges == 0:
        return 1, 1, None

    for g in graphs.values():
        n = nx.number_of_edges(g)
        #print(n, num_edges)
        equal += (n / num_edges)

    return equal, len(graphs), None


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
