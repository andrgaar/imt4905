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

def main():

    print("Timestamp;Peer;Destination;Source;ID;Route;NextHop")

    with open(routed, "r") as f:
        while True:
            line = f.readline()
            #print(line)
            if not line:
                break
            cols = line.strip().split(';')
            data = json.loads(cols[2])
            a = []
            for v in data.values():
                a.append(str(v))

            out = [ cols[0], cols[1] ] + a
            print( ';'.join(out) )

if __name__ == '__main__':
    main()
