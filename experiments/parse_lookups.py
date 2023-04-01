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


csvfile = sys.argv[1]
prev_timestamp = None

lookups = {}

def main():

    print("Timestamp;Offset;ID;Result;Source;Destination;Path;Pathlen\n")

    with open(csvfile, "r") as f:
        while True:
            line = f.readline()
            #print(line)
            if not line:
                break
            cols = line.strip().split(';')
            if cols[3] != "LOOKUP":
                continue

            d = json.loads(cols[5])
            if cols[2] == d['Destination']:
                lookups[d['ID']] = ('Success', cols[0], cols[1], d['Source'], d['Destination'], d['Path'], len(d['Path']))
            else:
                if d['ID'] not in lookups or lookups[d['ID']] != 'Success':
                    lookups[d['ID']] = ('Failed', cols[0], cols[1], d['Source'], d['Destination'], d['Path'], len(d['Path']))



        for k, v in lookups.items():
            print("{0};{1};{2};{3};{4};{5};{6};{7}".format(v[1], v[2], k, v[0], v[3], v[4], v[5], v[6]))


def parse(data):
    
    retval = ""
    global prev_timestamp
    
    timestamp = data[0] / 1000.0
    if not prev_timestamp:
        prev_timestamp = timestamp

    dt_event = datetime.fromtimestamp(timestamp)
    dt_prev = datetime.fromtimestamp(prev_timestamp)
    dt_offset = round((dt_event - dt_prev).total_seconds())

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

        retval = ';'.join([str(dt_event), str(dt_offset), data[1], d['Message'], source, payload])

    elif type(data[2]) is dict: # LSA
        lsa = data[2]
        if 'RP' in lsa:
            lsa['RP'] = list(lsa['RP'])
        if 'DEAD' in lsa:
            lsa['DEAD'] = list(lsa['DEAD'])
        payload = json.dumps(lsa)
        retval = ';'.join([str(dt_event), str(dt_offset), data[1], "LSA", lsa['RID'], payload])
        
    return retval

if __name__ == '__main__':
    main()
