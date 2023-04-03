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


routed  = sys.argv[1]
receive = sys.argv[2]

sent = {}
received = {}

def main():


    with open(routed, "r") as f:
        while True:
            line = f.readline()
            #print(line)
            if not line:
                break
            cols = line.strip().split(';')
            data = json.loads(cols[2])
            if data['ID'] == 0 or cols[1] != data['Source']:
                continue
            data_dict = {'Timestamp': cols[0], 'Peer': cols[1], 'Data': data}
            sent[data['ID']] = data_dict

        #for k in sent:
        #    print(k)

    with open(receive, "r") as f:
        while True:
            line = f.readline()
            if not line:
                break
            cols = line.strip().split(';')
            if cols[2] != "LOOKUP":
                continue
            d = json.loads(cols[4])
            if cols[1] == d['Destination']:
                #lookups[d['ID']] = ('Success', cols[0], cols[1], d['Source'], d['Destination'], d['Path'], len(d['Path']))
                received[d['ID']] = {'Timestamp': cols[0], 'Peer': cols[1], 'Data': d}
            #else:
            #    if d['ID'] not in lookups or lookups[d['ID']] != 'Success':
            #        lookups[d['ID']] = ('Failed', cols[0], cols[1], d['Source'], d['Destination'], d['Path'], len(d['Path']))



        #for k, v in received.items():
        #    print(k)

    print("Timestamp;ID;Source;Destination;Result;Path;Pathlen")
    for msgid, s in sent.items():
        ds = s['Data']
        if msgid in received:
            status = "Success"
            path = received[msgid]['Data']['Path']
        else:
            status = "Failed"
            path = []

        source = ds['Source']
        destination = ds['Destination']

        out = ';'.join([s['Timestamp'], msgid, source, destination, status, '-'.join(path), str(len(path))])
        print(out)

if __name__ == '__main__':
    main()
