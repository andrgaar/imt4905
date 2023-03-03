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
    

    for line in f:
        timestamp, peer, event, data = line.strip().split(';')

        if prev_timestamp == None:
            prev_timestamp = timestamp

        if event == 'TOPOLOGY UPDATE':
            dt_event = datetime.fromtimestamp(float(timestamp))
            dt_prev = datetime.fromtimestamp(float(prev_timestamp))
            dt_diff = dt_event - dt_prev

            if not peer in edges:
                edges[peer] = {}

            x = round(dt_diff.total_seconds())

            topology = json.loads(data)
            num = 0
            for p in topology:
                num = num + len(topology[p].keys())

            edges[peer][x] = num

            #print(dt_event, "{0}".format(round(dt_diff.total_seconds())), f"\"{event}\"", peer, num)

        if event == 'NODE FAILURE':
            dt_event = datetime.fromtimestamp(float(timestamp))
            dt_prev = datetime.fromtimestamp(float(prev_timestamp))
            dt_diff = dt_event - dt_prev
            x = round(dt_diff.total_seconds())

            if not peer in dead:
                dead[peer] = {}
            
            if data != "set()":
                plt.axvline(x = x, color = 'b')
                print(dt_event, "{0}".format(round(dt_diff.total_seconds())), f"\"{event}\"", peer, data)

            

    # Plot peers
    for p in edges:
        plt.plot( edges[p].keys(), edges[p].values(), label = p)

    # Find close pings for each latency#
    #ping_sample = {}
    #for sample_key in lat_h:
    #    ping_times = [key for key in ping_h if key >= sample_key - 15 and key < sample_key + 15]
    #    print(sample_key, ":", ping_times)
    #    val = 0
    #    for pt in ping_times:
    #        val = val + ping_h[pt]
    #    avg_ping = round(val / len(ping_times))
    #
    #    ping_sample[sample_key + 10] = avg_ping
    #    print(sample_key, " (avg)", avg_ping)

    
    width = 10

    #x_edges = np.linspace(0, x_max, x_max)    
    #x_edges = list(s1_h.keys())
    #y1_edges = list(s1_h.values())
    #y2_edges = list(s2_h.values())

    # plot lines
    #plt.plot( list(s1_h.keys()), list(s1_h.values()), label = "Measured", linestyle=":")
    #plt.scatter( list(s1_h.keys()), list(s1_h.values()), label = "Measured")
    #plt.plot( list(s2_h.keys()), list(s2_h.values()), label = "Path cost", linestyle="solid")

    #plt.bar(lat_h.keys(), lat_h.values(), width, label="Rtun")
    #plt.bar(ping_sample.keys(), ping_sample.values(), width, label="ICMP")


    #s1 = p.Series(y1_edges)
    #s2 = p.Series(y2_edges)
    #corr1 = s1.corr(s2)
    #corr2 = s2.corr(s1)
    #print("Correlation s1 to s2: ", corr1)
    #print("Correlation s2 to s1: ", corr2)
    #plt.plot(np.unique(s1), np.poly1d(np.polyfit(s1, s2, 1))(np.unique(s1)), color = 'green') 
    #plt.scatter(s1, s2)

    # Topology graph
    #g = nx.Graph(topology)
    #nx.draw(g, with_labels = True)
    #plt.show()

    
    plt.legend()
    plt.show()
