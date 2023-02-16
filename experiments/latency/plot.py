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

measured = {}
topology = {}
x_axis = []

fname = sys.argv[1]

with open(fname, "r") as f:

    x_axis = []
    p2 = []
    p3 = []
    p4 = []
    p5 = []
    p5_ping = []

    for line in f:
        timestamp, peer, event, data = line.strip().split(';')

        if event == 'TOPOLOGY UPDATE' or event == 'MEASURED LATENCY':
            if prev_timestamp == None:
                prev_timestamp = timestamp
                
            if not peer in measured:
                measured[peer] = list()
            if not peer in topology:
                topology[peer] = list()

            dt_event = datetime.fromtimestamp(float(timestamp))
            dt_prev = datetime.fromtimestamp(float(prev_timestamp))
            dt_diff = dt_event - dt_prev

            x = round(dt_diff.total_seconds())
            x_axis.append(x)

            if event == 'MEASURED LATENCY':
                y = int(data)
                
                measured[peer].append(y)

                for p in [key for key in measured if key != peer]:
                    measured[p].append(np.nan)
                for p in [key for key in topology if key != peer]:
                    topology[p].append(np.nan)
                
            elif event == 'TOPOLOGY UPDATE':
      
                topology = json.loads(data)
                latencies = topology['P1']
                
                y = latencies['P5']

                topology[peer].append(y)
            
                for p in [key for key in measured if key != peer]:
                    measured[p].append(np.nan)
                for p in [key for key in topology if key != peer]:
                    topology[p].append(np.nan)

            print(dt_event, "+{0}".format(round(dt_diff.total_seconds())), event, y)

    print("X axis: ", x_axis)

    # Plot peers
    for p in measured:
        plt.scatter( x_axis, measured[p], label = f"Measured {p}")

    for p in topology:
        plt.plot( x_axis, topology[p], label = f"Path cost {p}")

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

    #x_axis = np.linspace(0, x_max, x_max)    
    #x_axis = list(s1_h.keys())
    #y1_axis = list(s1_h.values())
    #y2_axis = list(s2_h.values())

    # plot lines
    #plt.plot( list(s1_h.keys()), list(s1_h.values()), label = "Measured", linestyle=":")
    #plt.scatter( list(s1_h.keys()), list(s1_h.values()), label = "Measured")
    #plt.plot( list(s2_h.keys()), list(s2_h.values()), label = "Path cost", linestyle="solid")

    #plt.bar(lat_h.keys(), lat_h.values(), width, label="Rtun")
    #plt.bar(ping_sample.keys(), ping_sample.values(), width, label="ICMP")


    #s1 = p.Series(y1_axis)
    #s2 = p.Series(y2_axis)
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
