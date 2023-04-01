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


arg1 = sys.argv[1]
data = 1
prev_timestamp = None

FREQ= '5s'

def main():

    #receivelog(arg1)
    f, (ax1, ax2) = plt.subplots(2, 1, sharex=True, layout='constrained')

    d1 = plot_convergence(ax1, arg1 + '/combined-topology.log.csv')
    d2 = plot_lookups(ax2, arg1 + '/combined-lookups.log.csv')
    #d3 = plot_failedpaths(ax3, arg1 + '/combined-lookups.log.csv')
    #d4 = plot_lsa(ax3, arg1 + '/combined-lsa.log.csv')
    
    #result = pd.merge_ordered(d1, d2, on="Offset", fill_method="ffill")
    #print(result)

    plt.show()

    #sns.lmplot(x="Convergence", y="Loss", data=result)
    #plt.show()

def plot_lsa(ax, csvfile):
    csv = pd.read_csv(csvfile, sep=";")
    csv['Timestamp'] = pd.to_datetime(csv['Timestamp'])
    
    t0 = csv.min()['Timestamp']
    print(t0)

    csv['Offset'] = (csv['Timestamp'] - t0).dt.total_seconds()
    csv['Offset'] = pd.to_timedelta(csv['Offset'], unit='sec')
    csv.set_index('Offset', inplace=True)

    csv = csv.groupby([pd.Grouper(freq = FREQ), 'Peer', 'Source']).count()['SN'].unstack()
    print(csv)
    csv.plot()


def plot_lookups(ax, csvfile):
    csv = pd.read_csv(csvfile, sep=";")

    csv['Timestamp'] = pd.to_datetime(csv['Timestamp'])
    t0 = csv.min()['Timestamp']
    csv['Offset'] = (csv['Timestamp'] - t0).dt.total_seconds()
    csv['Offset'] = pd.to_timedelta(csv['Offset'], unit='sec')
    #csv = csv.loc[csv['Result'] == "Failed"]
    csv = csv[['Offset', 'Result']]
    csv.set_index('Offset', inplace=True)

    csv = csv.groupby([pd.Grouper(freq = FREQ), 'Result'])['Result'].size().unstack()
    csv.reindex()
    csv['Loss'] = 100 * csv['Failed'] / ( csv['Failed'] + csv['Success'] )
    csv.set_index('Offset', inplace=True)
    csv = csv[['Offset', 'Loss']]
    csv['Offset'] = csv['Offset'].dt.total_seconds()

    print(csv)

    csv.plot(ax=ax, x='Offset', y='Loss', kind='line', colormap="tab20", legend=True,
          xlabel = "Time (s)", ylabel = "# messages")

    return csv

def plot_failedpaths(ax, csvfile):
    csv = pd.read_csv(csvfile, sep=";")
    csv = csv.loc[csv['Result'] == "Failed"]
    csv = csv[['Offset', 'Path']]
    csv['Offset'] = pd.to_timedelta(csv['Offset'], 'sec')
    csv.set_index('Offset', inplace=True)

    csv = csv.groupby([pd.Grouper(freq = FREQ), 'Path'])['Path'].size().unstack()
    #print(csv)
    csv.plot(ax=ax, kind='line', colormap="tab20", legend=True,
            xlabel = "Time (s)", ylabel = "# messages")

    return csv

def plot_convergence(ax, csvfile):
    csv = pd.read_csv(csvfile, sep=";")
    
    csv['Timestamp'] = pd.to_datetime(csv['Timestamp'])
    t0 = csv.min()['Timestamp']
    csv['Offset'] = (csv['Timestamp'] - t0).dt.total_seconds()
    csv['Offset'] = pd.to_timedelta(csv['Offset'], unit='sec')
    csv = csv[['Offset', 'Convergence']]
    csv.set_index('Offset', inplace=True)

    csv = csv.groupby([pd.Grouper(freq = FREQ)])['Convergence'].mean().reset_index()
    csv = csv[['Offset', 'Convergence']]
    csv['Offset'] = csv['Offset'].dt.total_seconds()
    #csv = csv.groupby('Offset')['Convergence'].mean()
    print(csv)
    
    #sns.lineplot(data=csv, x='Offset', y='Convergence', color='k', drawstyle='steps-pre')
    csv.plot(ax=ax, x='Offset', y='Convergence', kind="line", color = 'k', figsize=(10, 5), legend=False, #title="Convergence",
            xlabel = "Time (s)", ylabel = "Convergence (%)")
    #ax.grid(True)
    #ax.xaxis.set_major_locator(md.MinuteLocator(interval=5))  
    #ax.xaxis.set_major_formatter(md.DateFormatter('%H:%M'))  

    return csv

def receivelog(csvfile):
    # plot data
    csv = pd.read_csv(csvfile, sep=";")
    csv = csv.loc[csv['Received'] != "LOOKUP"]
    csv['Timestamp'] = pd.to_datetime(csv['Timestamp']) 
    csv = csv[['Offset', 'Peer', 'Received']]
    #csv['Offset'] = pd.to_timedelta(csv['Offset'], 'sec').dt.total_seconds().round(0)
    csv['Offset'] = pd.to_timedelta(csv['Offset'], 'sec')
    csv.set_index('Offset', inplace=True)

    csv = csv.groupby([pd.Grouper(freq = '1min'), 'Peer'])['Received'].size()
    csv.unstack().plot(kind='bar', stacked=True, colormap="tab20")

    #plt.gca().xaxis.set_major_formatter(md.DateFormatter('%H:%M'))

    #csv = csv.groupby(['Offset', 'Received']).size().unstack()
    #sns.lineplot(data=csv)
    print(csv)
    
    #grp = csv.groupby(['Offset', 'Received']).size()
    #ticks = np.arange(len(grp), step=60)
    #grp.plot(x='Offset', y="Received", xticks=ticks, kind='line', stacked=True)
    #print("GRP:", grp)
    #barWidth = 0.25
    #r1 = np.arange(len(grp))
    #plt.bar(r1, grp, stacked=True, color='#7f6d5f', width=barWidth, label='Messages')
    
    #sns.lineplot(data=csv,
                #hue="Peer", 
                #multiple="stack",
                #style="Peer", 
                #hue_order=["LSA", "HB", "LOOKUP", "HELLO", "JOIN"],
                #binwidth=10, stat="count", kde=False, 
    #            col="Peer"
    #        )

    #csv.plot(x = "Offset", y = "Received", kind="line", color = 'k', figsize=(10, 5), title="Messages received",
    #        xlabel = "Time (s)", ylabel = "#")
    plt.show()

            
if __name__ == '__main__':
    main()
