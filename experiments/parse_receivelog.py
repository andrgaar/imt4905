#!/usr/bin/python3

import sys
import pickle
from datetime import datetime
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
import seaborn as sns
import json
import re


fname = sys.argv[1]
csvfile = f"{fname}.csv"
data = 1
prev_timestamp = None

def main():

    if '.csv' in fname:
        plot(fname)
        return

    outf = open(csvfile, "w")
    outf.write("Timestamp;Offset;Peer;Received;Source\n")

    with open(fname, "rb") as f:
        while True:
            try:
                data = pickle.load(f)
                #print(data)
            except EOFError:
                break
            s = parse(data)
            print(s)
            outf.write(f"{s}\n")

    outf.close()

    plot(csvfile)

def plot(csvfile):

    # plot data
    csv = pd.read_csv(csvfile, sep=";")
    csv = csv.loc[csv['Received'] != "LOOKUP"]
    csv['Timestamp'] = pd.to_datetime(csv['Timestamp']) 

    df = csv[['Timestamp', 'Peer', 'Received']]
    df.set_index('Timestamp', inplace=True)

    print(csv)
    
    grp = df.groupby([pd.Grouper(freq = '1min'),'Peer', 'Received'])['Peer', 'Received'].count()
    print(grp)
    print(grp.dtypes)
    sns.lineplot(data=grp, x="Timestamp", y="Received",  
                hue="Received", hue_order=["LSA", "HB", "LOOKUP", "HELLO", "JOIN"],
            )
    #sns.histplot(data=df, x="Offset",
    #            hue="Received", hue_order=["LSA", "HB", "LOOKUP", "HELLO", "JOIN"],
    #            binwidth=60, stat="count", kde=False, 
    #            #col="Peer"
    #        )

    #csv.plot(x = "Offset", y = "Received", kind="line", color = 'k', figsize=(10, 5), title="Messages received",
    #        xlabel = "Time (s)", ylabel = "#")
    plt.show()

            
def parse(data):
    
    retval = ""
    global prev_timestamp
    
    timestamp = data[0] / 1000.0
    if not prev_timestamp:
        prev_timestamp = timestamp

    dt_event = datetime.fromtimestamp(timestamp)
    dt_prev = datetime.fromtimestamp(prev_timestamp)
    dt_offset = round((dt_event - dt_prev).total_seconds())

    if type(data[2]) is list: # Message
        d = data[2][0]
        if d['Message'] == "HELLO":
            source = d['Peer']
        elif d['Message'] == "HB":
            source = d['RID']
        elif d['Message'] == "LOOKUP":
            source = d['Source']
        else:
            source = ""

        retval = ';'.join([str(dt_event), str(dt_offset), data[1], d['Message'], source])
    elif type(data[2]) is dict: # LSA
        lsa = data[2]
        retval = ';'.join([str(dt_event), str(dt_offset), data[1], "LSA", lsa['RID']])
        
    return retval

if __name__ == '__main__':
    main()
