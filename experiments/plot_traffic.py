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
#arg2 = sys.argv[2]
data = 1
prev_timestamp = None

FREQ= '60s'

def main():

    #receivelog(arg1)
    f, (ax1) = plt.subplots(1, 1, sharex=True, layout='tight', figsize=(6,20))

    #d1 = plot_traffic(None, arg1 + '/combined-receive.log.csv', '')
    #d2 = plot_lookups(ax1, arg1 + '/combined-lookups.log.csv', 'Path selection P1 to P4')
    d3 = plot_cost(ax1, arg1 + '/combined-cost.log.csv', '')
    #d4 = plot_failed(ax4, arg1 + '/combined-lookups.log.csv', 'Messages sent and received P1 to P4')
    
    #result = pd.merge_ordered(d1, d2, on="Offset", fill_method="ffill")
    #print(result)

    #plot_msgdist(arg1 + '/combined-receive.log.csv')

    plt.show()

    #sns.lmplot(x="Convergence", y="Loss", data=result)
    #plt.show()

def plot_msgdist(csvfile):
    csv = pd.read_csv(csvfile, sep=";")
    csv = csv.loc[csv['Received'] != "LOOKUP"]

    sns.displot(csv, x="Received", col="Peer", col_wrap=2, color='black')

    return csv


def plot_traffic(ax, csvfile, title):
    csv = pd.read_csv(csvfile, sep=";")
    csv = csv.loc[csv['Received'] != "LOOKUP"]

    csv['Timestamp'] = pd.to_datetime(csv['Timestamp'])
    t0 = csv.min()['Timestamp']
    csv['Offset'] = (csv['Timestamp'] - t0).dt.total_seconds()
    csv['Offset'] = pd.to_timedelta(csv['Offset'], unit='sec')
    csv = csv[['Offset', 'Peer', 'Received', 'Source']]
    csv.set_index('Offset', inplace=True)

    csv = csv.groupby([pd.Grouper(freq = FREQ), 'Peer', 'Received']).size().fillna(0).reset_index()
    csv['Offset'] = csv['Offset'].dt.total_seconds()
    csv.set_index('Offset', inplace=True)
    csv['Received'] = csv['Received'] * 512 / 15
    csv.columns = ['Time (s)', 'Peer', 'Type']

    #filter1 = csv["Peer"] == "P3"
    #csv = csv[ filter1 ]

    print(csv)

    plot.set(xlabel ="Time (s)", ylabel = "Received (bytes/s)", title ='Received data')
    ax.set_xlabels('Time (s)')
    ax.set_ylabels('Received (bytes/s)')
    #csv.plot(ax=ax, kind='line', colormap="tab20", legend=True,
    #      xlabel = "Time (s)", ylabel = "")

    return csv

def plot_lookups(ax, csvfile, title):
    csv = pd.read_csv(csvfile, sep=";")
    #csv = csv.loc[csv['Received'] != "LOOKUP"]

    csv['Timestamp'] = pd.to_datetime(csv['Timestamp'])
    t0 = csv.min()['Timestamp']
    csv['Offset'] = (csv['Timestamp'] - t0).dt.total_seconds()
    csv['Offset'] = pd.to_timedelta(csv['Offset'], unit='sec')
    csv['Offset'] = csv['Offset'].dt.total_seconds()

    csv = csv[['Offset', 'Source', 'Destination', 'Result', 'Path']]
    csv.reset_index(inplace=True)
   
    ## Calculate loss
    #csv2 = csv[['Source', 'Destination', 'Result']]
    #grp = csv2.groupby(['Source', 'Destination', 'Result'])['Result'].size().unstack().fillna(0).reset_index()
    #grp['Loss'] = grp['Failed'] / ( grp['Failed'] + grp['Success'] ) * 100 
    #grp['Failed'] = grp['Failed'].round(decimals=0).astype(int)
    #grp['Success'] = grp['Success'].round(decimals=0).astype(int)
    #grp['Loss'] = grp['Loss'].round(0).astype(int)
    ##

    filter1 = csv["Source"] == "P1"
    filter2 = csv["Destination"] == "P4"
    filter3 = csv["Result"] == "Success"
    filter4 = csv["Path"].isin(['P1-P2-P4','P1-P3-P4','P1-P4'])
    #csv = csv.where(filter1 & filter2 & filter3, inplace = False)
    csv = csv[ filter1 ]
    csv = csv[ filter2 ]
    csv = csv[ filter3 ]
    csv = csv[ filter4 ]
    
    csv = csv[['Offset', 'Path']]
    csv.set_index('Offset', inplace=True)
    print(csv)


    ax.set_title(title)

    plot = sns.stripplot(ax=ax, data=csv, x="Offset", y="Path", color="black")
    plot.set_xlabel("Time (s)")
    plot.set_ylabel("Path")

    #plot.set(title='Path selected P1 to P4')

    #grp = grp.append(grp.sum(numeric_only=False), ignore_index=True)
    #print("Loss per path")
    #print(grp)
    #print(grp.to_latex(index=False,
    #              #formatters={"name": str.upper},
    #              #float_format="{:.1f}".format,
    #))  

    return csv

def plot_failed(ax, csvfile, title):
    csv = pd.read_csv(csvfile, sep=";")

    csv['Timestamp'] = pd.to_datetime(csv['Timestamp'])
    t0 = csv.min()['Timestamp']
    csv['Offset'] = (csv['Timestamp'] - t0).dt.total_seconds()
    csv['Offset'] = pd.to_timedelta(csv['Offset'], unit='sec')
    #csv['Offset'] = csv['Offset'].dt.total_seconds()

    csv = csv[['Offset', 'Source', 'Destination', 'Result', 'Path']]
    csv.reset_index(inplace=True)
    
    filter1 = csv["Source"] == "P1"
    filter2 = csv["Destination"] == "P4"
    csv = csv[ filter1 ]
    csv = csv[ filter2 ]
   
    csv = csv[['Offset', 'Result']]
    csv.set_index('Offset', inplace=True)
    print(csv)

    csv = csv.groupby([pd.Grouper(freq = FREQ),'Result']).size().unstack().fillna(0).reset_index()
    csv['Offset'] = csv['Offset'].dt.total_seconds()
    csv.set_index('Offset', inplace=True)

    csv = csv.stack().reset_index()
    csv.columns = ['Time (s)', 'Result', 'Amount']
    csv['Amount'] = csv['Amount'].astype(int)

    print(csv)

    sns.lineplot(ax=ax, x='Time (s)', y='Amount', style='Result', color='black', data=csv)

    return csv

def plot_cost(ax, csvfile, title):
    csv = pd.read_csv(csvfile, sep=";")
    #csv = csv.loc[csv['Received'] != "LOOKUP"]

    csv['Timestamp'] = pd.to_datetime(csv['Timestamp'])
    t0 = csv.min()['Timestamp']
    csv['Offset'] = (csv['Timestamp'] - t0).dt.total_seconds()
    csv['Offset'] = pd.to_timedelta(csv['Offset'], unit='sec')
    csv['Offset'] = csv['Offset'].dt.total_seconds()

    #csv = csv[['Offset', 'Source', 'Destination', 'Result', 'Path']]
    csv.reset_index(inplace=True)
    
    #filter1 = csv["Peer"] == "P1"
    #paths = ['P1-P2-P4', 'P1-P3-P4']
    #filter2 = csv["Path"].isin(paths)
    #csv = csv[ filter1 ]
    csv = csv[ (csv.Path == "P1-P2") | (csv.Path == "P2-P4") | (csv.Path == "P3-P1") ]
    
    csv = csv[['Offset', 'Path', 'Cost']]
    #csv.set_index('Offset', inplace=True)
    print(csv)

    ax.set_title(title)

    plot = sns.lineplot(ax=ax, data=csv, x='Offset', y='Cost',
                style="Path", 
                # multiple="stack",
                #hue_order=["LSA", "HB", "LOOKUP", "HELLO", "JOIN"],
                #binwidth=10, stat="count", kde=False, 
                #col="Peer", col_wrap=2,
                legend=True, color='black'
            )
    plot.set_xlabel("Time (s)")
    plot.set_ylabel("Cost")

    return csv    

if __name__ == '__main__':
    main()
