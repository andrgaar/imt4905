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

peer_sn = {}
lsa_sn = {}
last_seen = {}

def main():

    global lsa_sn
    global peer_sn
    global last_seen
    global prev_timestamp

    print("Timestamp;Peer;Convergence")

    with open(csvfile, "r") as f:
        while True:
            line = f.readline()
            if not line:
                break
            cols = line.strip().split(';')

            try:
                timestamp = datetime.strptime(cols[0], '%Y-%m-%d %H:%M:%S.%f')
            except ValueError:
                try:
                    timestamp = datetime.strptime(cols[0], '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    continue

            #print(line)

            if not prev_timestamp:
                prev_timestamp = timestamp 

            dt_event = timestamp
            dt_prev = prev_timestamp
            dt_offset = round((dt_event - dt_prev).total_seconds())

            peer = cols[1]
            src = cols[3]
            if cols[2] == "HB":
                last_seen[src] = dt_offset
                continue

            if cols[2] != "LSA":
                continue
            
            last_seen[src] = dt_offset
            # Init peer if not exists
            if peer not in lsa_sn:
                lsa_sn[peer] = {}
            if src not in peer_sn:
                peer_sn[src] = 1
            
            # clean out
            remove = []
            for p in peer_sn:
                if last_seen[p] < dt_offset - 30:
                    remove.append(p)
            for r in remove:
                #print("Remove ", r)
                peer_sn.pop(r)
                for k in lsa_sn:
                    if r in lsa_sn[k]:
                        lsa_sn[k].pop(r)

            peer_agree = parse(peer, cols)

            for p, pct in peer_agree.items():
                print(f"{dt_event};{p};{pct}")

            #print(out)


def parse(peer, data):

    global lsa_sn
    global peer_sn
    
    retval = ""

    lsa = json.loads(data[4])
    
    if 'RP' in lsa:
        lsa['RP'] = list(lsa['RP'])
    if 'DEAD' in lsa:
        lsa['DEAD'] = list(lsa['DEAD'])

    # update peer
    if lsa['RID'] not in peer_sn:
        peer_sn[lsa['RID']] = lsa['SN']
    elif peer_sn[lsa['RID']] < lsa['SN']:
        peer_sn[lsa['RID']] = lsa['SN']
    # update our lsa_sn
    tmp_dict = { lsa['RID']: lsa['SN'] }
    if lsa['RID'] in lsa_sn[peer]:
        lsa_sn[peer].update(tmp_dict)
    else:
        lsa_sn[peer][lsa['RID']] = lsa['SN'] 

    # compare all lsa
    num_peers = len(peer_sn)
    peer_agree = {}
    visited = []
    for p in peer_sn:
        match = 1
        if p not in lsa_sn:
            continue
        sn_db = lsa_sn[p]
        for p2 in peer_sn:
            #if p == p2:
            #    continue
            if p2 not in sn_db:
                continue
            if sn_db[p2] == peer_sn[p2]:
                match += 1
        
        peer_agree[p] = round(match / num_peers * 100)

    return peer_agree


if __name__ == '__main__':
    main()
