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
csvfile = "combined-routes.csv"

def main():

    # Compute all shortest paths between nodes and compare
    # how much they overlap with peers

    fout = open(csvfile, "w")
    fout.write("Timestamp;Peer;Path;RP;Cost\n")
    prev_timestamp = None

    with open(fname, "r") as f:
        x = list()
        y = list()

        #print("Timestamp;Peer;Neighbour;Path;Cost")

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

            graph = json.loads(data)

            if not graph:
                continue

            for edge in graph:
                path = edge[0] + "-" + edge[1]
                cost = edge[2]
                rp = edge[3]
            # output 
            fout.write("{0};{1};{2};{3};{4}\n".format(dt_event, peer, path, str(rp), str(cost)))

        fout.close()

if __name__ == '__main__':
    main()
