#!/usr/bin/python3

import sys
import os
import pickle
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as md
import networkx as nx
import numpy as np
import pandas as pd
import seaborn as sns
import json
import re

FREQ = '30s'

arg1 = sys.argv[1]

def main():
   
    f, (ax1, ax2, ax3) = plt.subplots(3, 1, sharex=True, layout='constrained')

    plot_nodedegree(ax1, arg1, '')
    plot_pathlen(ax2, arg1, '')
    plot_clustering(ax3, arg1, '')

    plt.show()
            
def plot_nodedegree(ax, csvfile, title):
    csv = pd.read_csv(csvfile, sep=";")
    
    csv['Timestamp'] = pd.to_datetime(csv['Timestamp'])
    t0 = csv.min()['Timestamp']
    
    #csv = csv[ csv["Peer"].isin('P4','P5') ]

    csv['Offset'] = (csv['Timestamp'] - t0).dt.total_seconds()
    csv['Offset'] = pd.to_timedelta(csv['Offset'], unit='sec')
    csv = csv[['Offset', 'Peer', 'Degree']]
    csv.set_index('Offset', inplace=True)
    csv = csv.groupby([pd.Grouper(freq = FREQ), 'Peer'])['Degree'].mean().reset_index()
    csv['Offset'] = csv['Offset'].dt.total_seconds()
        
    print(csv)

    plot = sns.lineplot(data=csv, ax=ax, x='Offset', y='Degree', hue='Peer', drawstyle='steps-pre', legend=False)
    plot.set(xlabel ="Time (s)", ylabel = "Degree")

def plot_pathlen(ax, csvfile, title):
    csv = pd.read_csv(csvfile, sep=";")
    
    csv['Timestamp'] = pd.to_datetime(csv['Timestamp'])
    t0 = csv.min()['Timestamp']
    
    #csv = csv[ csv["Peer"].isin('P4','P5') ]

    csv['Offset'] = (csv['Timestamp'] - t0).dt.total_seconds()
    csv['Offset'] = pd.to_timedelta(csv['Offset'], unit='sec')
    csv = csv[['Offset', 'Peer', 'AvgPathLen']]
    csv.set_index('Offset', inplace=True)
    csv = csv.groupby([pd.Grouper(freq = FREQ)])['AvgPathLen'].mean().reset_index()
    csv['Offset'] = csv['Offset'].dt.total_seconds()
        
    print(csv)

    plot = sns.lineplot(data=csv, ax=ax, x='Offset', y='AvgPathLen', color='k', drawstyle='steps-pre', legend=False)
    plot.set(xlabel ="Time (s)", ylabel = "Avg. number of hops")

def plot_clustering(ax, csvfile, title):
    csv = pd.read_csv(csvfile, sep=";")
    
    csv['Timestamp'] = pd.to_datetime(csv['Timestamp'])
    t0 = csv.min()['Timestamp']
    
    #csv = csv[ csv["Peer"].isin('P4','P5') ]

    csv['Offset'] = (csv['Timestamp'] - t0).dt.total_seconds()
    csv['Offset'] = pd.to_timedelta(csv['Offset'], unit='sec')
    csv = csv[['Offset', 'Peer', 'Clustering']]
    csv.set_index('Offset', inplace=True)
    csv = csv.groupby([pd.Grouper(freq = FREQ)])['Clustering'].mean().reset_index()
    csv['Offset'] = csv['Offset'].dt.total_seconds()
        
    print(csv)

    plot = sns.lineplot(data=csv, ax=ax, x='Offset', y='Clustering', drawstyle='steps-pre', legend=False)
    plot.set(xlabel ="Time (s)", ylabel = "Clustering")



if __name__ == '__main__':
    main()
