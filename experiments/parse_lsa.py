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

lsa = {}

def main():

    print("Timestamp;Peer;Source;SN")

    with open(csvfile, "r") as f:
        while True:
            line = f.readline()
            #print(line)
            if not line:
                break
            cols = line.strip().split(';')
            if cols[3] != "LSA":
                continue

            out = parse(cols)

            print(out)


def parse(data):
    
    retval = ""
    
    global prev_timestamp
    try:
        timestamp = datetime.strptime(data[0], '%Y-%m-%d %H:%M:%S.%f')
    except ValueError:
        timestamp = datetime.strptime(data[0], '%Y-%m-%d %H:%M:%S')

    if not prev_timestamp:
        prev_timestamp = timestamp 

    dt_event = timestamp
    dt_prev = prev_timestamp
    dt_offset = round((dt_event - dt_prev).total_seconds())

    lsa = json.loads(data[5])
    
    if 'RP' in lsa:
        lsa['RP'] = list(lsa['RP'])
    if 'DEAD' in lsa:
        lsa['DEAD'] = list(lsa['DEAD'])

    retval = ';'.join([str(dt_event), data[2], lsa['RID'], str(lsa['SN'])])
        
    return retval

if __name__ == '__main__':
    main()
