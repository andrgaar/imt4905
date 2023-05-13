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
                parts = log_str.split(' ')
                
                (filename, date) = parts[0].split(':')
                
                fn = filename.split('/')
                
                peer = fn[-2][4]
                peer = 'P' + peer

                # Extract the date and time information
                date_time = date + ' ' + parts[1]

                # Extract the log level (e.g., WARNING)
                log_level = parts[4]

                # Extract the thread information
                thread_info = parts[6]

                # Extract the dead routes information
                dead_routes = parts[10].split(',')

                for route in dead_routes:
                    print(f"{date_time};{peer};{route}")

if __name__ == '__main__':
    main()
