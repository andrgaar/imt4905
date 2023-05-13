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


args = sys.argv
args.pop(0)

def main():

    print("Timestamp;Peer;DeadPeer")
    for arg in args:
        with open(arg, "r") as f:
            while True:
                log_str = f.readline().strip()
                if not log_str:
                    break
                # Split the log string into different parts
                parts = log_str.split(' - ')
                #print(parts)
                
                filename = parts[0][0:14]
                timestamp = parts[0][15:-1]

                peer = filename[4]
                peer = 'P' + peer

                # Extract the date and time information
                #date_time = date + ' ' + parts[1]

                # Extract relay IP
                relay_ip = parts[2]

                print(f"{timestamp};{peer};{relay_ip}")

if __name__ == '__main__':
    main()
