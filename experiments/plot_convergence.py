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

argv = sys.argv
argv.pop(0)

data = 1
prev_timestamp = None

FREQ= '60s'
CUTOFF=600

def main():

    #receivelog(arg1)
    #f, ((ax1, ax2), (ax3, ax4), (ax5, ax6)) = plt.subplots(3, 2, sharex=True
    f, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, sharex=True
            , layout='constrained')
    axes = [ax1,ax2,ax3,ax4]
    i = 0
    for arg in argv:
        print("-----------------------------------")
        print(arg)
        print("-----------------------------------")
        #plot_convergence(ax1, arg + '/combined-topology.log.csv', '2 peers, s=n/a')
        #plot_reliability(ax2, arg + '/peer1/sent.log', arg + '/combined-receive.log.csv', '2 peers, s=n/a')
        #plot_avgdegree(ax3, arg + '/combined-topology.log.csv', '2 peers, s=n/a')
        #plot_clustering(ax4, arg + '/combined-topology.log.csv', '2 peers, s=n/a')
        #plot_nodeclustering(ax5, arg + '/combined-topology.log.csv', '2 peers, s=n/a')
        #plot_avgcost(ax6, arg + '/combined-topology.log.csv', '2 peers, s=n/a')
        plot_latency(axes[i], arg + '/peer1/sent.log', arg + '/peer5/receive.log.csv', f"Set {i+1}")
        i += 1

    #plt.tight_layout()
    #f.suptitle('5 peers, min=3, s=3, hb=10', fontsize=12)
    #plt.show()

    #plot_routes(None, arg + "/combined-routes.csv", '')
    #plot_msgdist(None, arg + "/combined-receive.log.csv")
    plt.show()


def to_offset(df):
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    t0 = df.min()['Timestamp']
    df['Offset'] = (df['Timestamp'] - t0).dt.total_seconds()
    df['Offset'] = pd.to_timedelta(df['Offset'], unit='sec')
    df.set_index('Offset', inplace=True)

    return df

def plot_reliability(ax, sent, receive, title):
    sent_df = pd.read_csv(sent, sep=";")
    sent_df['Timestamp'] = pd.to_datetime(sent_df['Timestamp'], unit='ms')
    sent_df = to_offset(sent_df).reset_index()
    sent_df = sent_df[['Offset', 'ID']]
    print(sent_df)

    receive_df = pd.read_csv(receive, sep=";")
    receive_df = receive_df.loc[receive_df['Received'] == 'LOOKUP']
    receive_df = to_offset(receive_df).reset_index()
    receive_df['Result'] = 'Success'
    receive_df = receive_df[['ID', 'Result']]
    print(receive_df)

    result = pd.merge(
    sent_df,
    receive_df,
    how="left",
    on='ID',
    left_on=None,
    right_on=None,
    left_index=False,
    right_index=False,
    sort=True,
    suffixes=("_x", "_y"),
    copy=True,
    indicator=False,
    validate=None,
    )
    result = result.replace(np.nan, 'Failed')
    result.set_index('Offset', inplace=True)
    result = result.groupby([pd.Grouper(freq = FREQ), 'Result'])['Result'].size().unstack().reset_index()
    result['Offset'] = result['Offset'].dt.total_seconds()
    result = result.loc[result['Offset'] <= CUTOFF]
    result = result.replace(np.nan, 0)
    try:
        result['SuccessRate'] = result['Success'] / (result['Failed'] + result['Success']) * 100
    except Exception:
        result['SuccessRate'] = 100

    print(result)

    result.plot(ax=ax, x='Offset', y='SuccessRate', kind='line', colormap="tab20", legend=False,
          xlabel = "Time (s)", ylabel = "Reliability (%)")

def plot_latency(ax, sent, receive, title):
    sent_df = pd.read_csv(sent, sep=";")
    sent_df['Timestamp'] = pd.to_datetime(sent_df['Timestamp'])
    sent_df = to_offset(sent_df).reset_index()
    sent_df = sent_df[['Timestamp', 'Offset', 'ID', 'Route', 'Shortest']]
    print(sent_df)

    receive_df = pd.read_csv(receive, sep=";")
    receive_df = receive_df.loc[receive_df['Received'] == 'LOOKUP']
    receive_df['Timestamp'] = pd.to_datetime(receive_df['Timestamp'])
    #receive_df = to_offset(receive_df).reset_index()
    #receive_df['Result'] = 'Success'
    receive_df = receive_df[['Timestamp', 'ID']]
    print(receive_df)

    result = pd.merge(
    sent_df,
    receive_df,
    how="left",
    on='ID',
    left_on=None,
    right_on=None,
    left_index=False,
    right_index=False,
    sort=True,
    suffixes=("_x", "_y"),
    copy=True,
    indicator=False,
    validate=None,
    )
    #result = result.replace(np.nan, 0)
    result['Latency'] = result.Timestamp_y - result.Timestamp_x
    result['Latency'] = result['Latency'].dt.total_seconds() * 1000
    result = result.loc[result['Latency'] <= 1000]
    result.set_index('Offset', inplace=True)
    #result = result.groupby([pd.Grouper(freq = FREQ),'Shortest'])['Latency'].mean().unstack().reset_index()
    result = result.groupby([pd.Grouper(freq = FREQ),'Shortest'])['Latency'].mean().reset_index()
    result['Offset'] = result['Offset'].dt.total_seconds()
    #result = result.reset_index()
    result = result.replace(True, "Shortest (Dijkstra)")
    result = result.replace(False, "Others")
    result = result.rename(columns={"Shortest": "Actual latency"})
    print(result)

    #result.plot(ax=ax, x='Offset', kind='line', colormap="tab20", legend=True,
    #      xlabel = "Time (s)", ylabel = "Latency (ms)")

    p = sns.lineplot(ax=ax, data=result, x='Offset', y='Latency', hue='Actual latency', style='Actual latency')
    ax.set_title(title)
    ax.set(xlabel='Time (s)', ylabel='Latency (ms)')
    #p = sns.scatterplot(data=result, x='Offset', y='Latency', hue='Measured shortest path', style='Measured shortest path')
    #p = sns.kdeplot(data=result, x='Offset', y='Latency', hue='Measured shortest path', style='Measured shortest path')



def plot_avgdegree(ax, csvfile, title):
    df = pd.read_csv(csvfile, sep=";")
    df = to_offset(df).reset_index()
    df = df[['Offset', 'AvgDegree']]
    df.set_index('Offset', inplace=True)

    df = df.groupby([pd.Grouper(freq = FREQ)])['AvgDegree'].mean().reset_index()
    df['Offset'] = df['Offset'].dt.total_seconds()
    df = df.loc[df['Offset'] <= CUTOFF]
    print(df)

    df.plot(ax=ax, x='Offset', y='AvgDegree', kind='line', colormap="tab20", legend=False,
          xlabel = "Time (s)", ylabel = "Avg. node degree")

def plot_clustering(ax, csvfile, title):
    df = pd.read_csv(csvfile, sep=";")
    df = to_offset(df).reset_index()
    df = df[['Offset', 'Clustering']]
    df.set_index('Offset', inplace=True)

    df = df.groupby([pd.Grouper(freq = FREQ)])['Clustering'].mean().reset_index()
    df['Offset'] = df['Offset'].dt.total_seconds()
    df = df.loc[df['Offset'] <= CUTOFF]
    print(df)

    df.plot(ax=ax, x='Offset', y='Clustering', kind='line', colormap="tab20", legend=False,
          xlabel = "Time (s)", ylabel = "Clustering coeff.")

def plot_nodeclustering(ax, csvfile, title):
    df = pd.read_csv(csvfile, sep=";")
    df = to_offset(df).reset_index()
    df = df[['Offset', 'Peer', 'NodeClustering']]
    df.set_index('Offset', inplace=True)

    df = df.groupby([pd.Grouper(freq = FREQ), 'Peer'])['NodeClustering'].mean().unstack().reset_index()
    df['Offset'] = df['Offset'].dt.total_seconds()
    df = df.loc[df['Offset'] <= CUTOFF]
    print(df)

    df.plot(ax=ax, x='Offset', kind='line', colormap="tab20", legend=False,
          xlabel = "Time (s)", ylabel = "Node clustering coeff.")

def plot_avgcost(ax, csvfile, title):
    df = pd.read_csv(csvfile, sep=";")
    df = to_offset(df).reset_index()
    df = df[['Offset', 'AvgCost']]
    df.set_index('Offset', inplace=True)

    df = df.groupby([pd.Grouper(freq = FREQ)])['AvgCost'].mean().reset_index()
    df['Offset'] = df['Offset'].dt.total_seconds()
    df = df.loc[df['Offset'] <= CUTOFF]
    print(df)

    df.plot(ax=ax, x='Offset', y='AvgCost', kind='line', colormap="tab20", legend=False,
          xlabel = "Time (s)", ylabel = "Avg. path cost")

def plot_routes(ax, csvfile, title):
    df = pd.read_csv(csvfile, sep=";")
    df = df.loc[df['Peer'] == "P1"]
    df = to_offset(df).reset_index()
    df = df[['Offset', 'Path', 'RP']]
    df.set_index('Offset', inplace=True)

    df = df.groupby([pd.Grouper(freq = FREQ)])['RP'].first().reset_index()
    df['Offset'] = df['Offset'].dt.total_seconds()
    df = df.loc[df['Offset'] <= CUTOFF]
    print(df)
    print(df.to_latex(index=False))

def plot_msgdist(ax, csvfile):
    df = pd.read_csv(csvfile, sep=";")
    df = df.loc[df['Peer'] != "Peer"]
    df = df.loc[df['Received'] != "LOOKUP"]
    df = df[['Peer', 'Received']]

    print("plot_msgdist:")
    print(df)

    df.hist(ax=ax, column='Received', by='Peer')
    #df['Received'].value_counts().plot(kind='bar')

    
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

    csv = csv.groupby([pd.Grouper(freq = FREQ), 'Result'])['Result'].size().unstack().reset_index()
    #csv = csv.reindex()
    csv['Loss'] = 100 * csv['Failed'] / ( csv['Failed'] + csv['Success'] )
    csv = csv[['Offset', 'Loss']]
    csv['Offset'] = csv['Offset'].dt.total_seconds()
    csv['Loss'] = csv['Loss'].fillna(0)
    #csv.set_index('Offset', inplace=True)

    print(csv)

    csv.plot(ax=ax, x='Offset', y='Loss', kind='line', colormap="tab20", legend=True,
          xlabel = "Time (s)", ylabel = "Loss (%)")

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

def plot_convergence(ax, csvfile, title):
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
    filter = csv["Offset"]<900
    csv.where(filter, inplace = True)
    print(csv)
    
    csv.plot(ax=ax, x='Offset', y='Convergence', kind="line", legend=False,
            xlabel = "Time (s)", ylabel = "Convergence (%)")


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
