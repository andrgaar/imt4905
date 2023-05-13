#!/usr/bin/python3

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
import seaborn as sns
import sys
import json
from datetime import datetime


fname = sys.argv[1]

def main():

    # Compute all shortest paths between nodes and compare
    # how much they overlap with peers

    print("Timestamp;Peer;NodeDegree")
    prev_timestamp = None

    with open(fname, "r") as f:

        for line in f:
            timestamp, peer, data = line.strip().split(';')
            
            if not prev_timestamp:
                prev_timestamp = timestamp

            dt_event = datetime.fromtimestamp(float(timestamp))
            dt_prev = datetime.fromtimestamp(float(prev_timestamp))
            dt_offset = round((dt_event - dt_prev).total_seconds())

            #last_time[peer] = dt_event
            # remove peers not seen in last minute
            #remove = set()
            #for k, v in last_time.items():
            #    if (dt_event - v).total_seconds() > 60:
            #        remove.add(k)
            #for k in remove:
            #    del last_time[k]
            #    graphs.pop(k)

            n = json.loads(data)

            nodedeg = len(n)
            # output 
            print("{0};{1};{2}".format(dt_event, peer, str(nodedeg)))


if __name__ == '__main__':
    main()
