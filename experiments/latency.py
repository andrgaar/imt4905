#!/usr/bin/python3

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import networkx as nx
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats
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
    translate = {"P2": "NO", "P3": "JP", "P4": "US", "P5": "ES"}
    distance = {"P2": 10, "P3": 8200, "P4": 6500, "P5": 2600}
    ds = []

    for line in f:
        timestamp, peer, event, data = line.strip().split(';')

        if prev_timestamp == None:
            prev_timestamp = timestamp

        dt_event = datetime.fromtimestamp(float(timestamp))
        dt_prev = datetime.fromtimestamp(float(prev_timestamp))
        dt_diff = dt_event - dt_prev
        
        x = round(dt_diff.total_seconds())
        
        if event == 'MEASURED LATENCY' and peer == "P1":

            data = data.replace("'", '"')

            latency = json.loads(data)
            for p, v in latency.items():
                if not p in topology:
                    topology[p] = []

                topology[p].append(v)
                ds.append( (distance[p], v) )
                print(p, ": ", v)
    
    df = pd.DataFrame(ds, columns =['Distance', 'RTT'])
    print(df)
    #ax1 = df.plot.scatter(y='Distance', x='RTT', c='Black')
    sp = sns.scatterplot(x="Distance", y="RTT", color="Black", data=df);
    sp.set_xlabel("Distance (km)")
    sp.set_ylabel("RTT (ms)")
    sp.set_title("Distribution of Round-Trip Time (RTT) measurements")

    sns.lmplot(x="Distance", y="RTT", markers=".", scatter_kws={'color': 'black'}, line_kws={'color': 'black'}, data=df);
    pearson = stats.pearsonr(df['Distance'], df['RTT'])
    print("Pearson r-value: ", round(pearson.statistic, 2), ", p-value: ", round(pearson.pvalue, 16))
    #print(stats.pointbiserialr(df['Distance'], df['RTT']))

    fig, axs = plt.subplots(len(topology.keys()), sharex=True)
    #fig.tight_layout(pad=1.0)

    i = 0
    for p, a in topology.items():
        mean = round(np.mean(a))
        median = round(np.median(a))
        print(p, " Mean: ", mean, " Median: ", median)

        axs[i].hist(a, bins = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 2000, 4000], weights=np.ones(len(a)) / len(a), color="Black")
        axs[i].set_ylim([0, 1])
        axs[i].yaxis.set_major_formatter(mtick.PercentFormatter(1))
        axs[i].set_xlabel('RTT(ms)')
        axs[i].set_title(translate[p])
        i += 1

    plt.subplots_adjust(left=0.1,
                    bottom=0.1,
                    right=0.9,
                    top=0.9,
                    wspace=1.0,
                    hspace=1.0)
    plt.show() 
            
