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
    outf.write("Timestamp;Peer;Received;Source;Payload\n")

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


def parse(data):
    
    retval = ""
    global prev_timestamp
    
    timestamp = data[0] / 1000.0
    #if not prev_timestamp:
    #    prev_timestamp = timestamp

    dt_event = datetime.fromtimestamp(timestamp)
    #dt_prev = datetime.fromtimestamp(prev_timestamp)
    #dt_offset = round((dt_event - dt_prev).total_seconds())

    source = ""
    payload = ""

    if type(data[2]) is list: # Message
        d = data[2][0]
        if d['Message'] == "HELLO":
            source = d['Peer']
        elif d['Message'] == "HB":
            source = d['RID']
        elif d['Message'] == "LOOKUP":
            source = d['Source']
        elif d['Message'] == "JOIN":
            source = d['Source']
            d['Cookie'] =  d['Cookie'].decode("utf-8") 
        payload = json.dumps(d)

        retval = ';'.join([str(dt_event), data[1], d['Message'], source, payload])

    elif type(data[2]) is dict: # LSA
        lsa = data[2]
        if 'RP' in lsa:
            lsa['RP'] = list(lsa['RP'])
        if 'DEAD' in lsa:
            lsa['DEAD'] = list(lsa['DEAD'])
        payload = json.dumps(lsa)
        retval = ';'.join([str(dt_event), data[1], "LSA", lsa['RID'], payload])
        
    return retval

if __name__ == '__main__':
    main()
