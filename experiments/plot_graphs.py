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
CUTOFF=2500
t0 = None

clustering_df = None
reliability_df = None

hue_order = ['P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7', 'P8']

def main(_set):
    global t0
    #receivelog(arg1)
    #f, ((ax1, ax2), (ax3, ax4), (ax5, ax6)) = plt.subplots(3, 2, sharex=True
    #f, (ax1, ax2, ax3) = plt.subplots(3, 1, sharex=True, 
    f, axes = plt.subplots(len(argv), 1, sharex=True, figsize=(12, 6) ,# subplot_kw={'ylim': (0,100)}
    #f, ax = plt.subplots(1, 1, sharex=True, # subplot_kw={'ylim': (0,100)}
            layout='constrained')
    #ax = plt.figure().add_subplot(projection='3d')
    i = 0
    ax = None
    for arg in argv:
        if len(argv) == 1:
            ax = axes
        else:
            ax = axes[i]

        title = arg.split('/')[0]

        print("-----------------------------------")
        print(arg)
        print("-----------------------------------")
        
        # Set common start time
        df = pd.read_csv(arg + '/combined-topology.log.csv', sep=";")
        df['Timestamp'] = pd.to_datetime(df['Timestamp']).dt.tz_localize('Europe/Amsterdam').dt.tz_convert('UTC')
        t0 = df.min()['Timestamp']
        print(f"t0: {t0}")

        if _set == 1:
            plot_convergence(ax, arg + '/combined-convergence.csv', title)
            
            f.supxlabel('Time (m)')
            f.supylabel('Network convergence (%)')
        if _set == 2:
            plot_reliability(ax, arg + '/combined-sent.log.csv', arg + '/combined-receive.log.csv', title)
            
            f.supxlabel('Time (m)')
            f.supylabel('Network reliability (%)')

        if _set == 3:
            avgdeg = plot_avgdegree(ax, arg + '/combined-topology.log.csv', None)
            plot_degree(ax, arg + '/combined-neighbours.csv', title)

            f.supxlabel('Time (m)')
            f.supylabel('Node degree')
        if _set == 4:
            plot_latency(ax, arg + '/combined-sent.log.csv', arg + '/combined-receive.log.csv', title)
            #plot_avgcost(ax, arg + '/combined-topology.log.csv', title)
            
            f.supxlabel('Time (m)')
            f.supylabel('Latency (ms)')

        if _set == 5:
            plot_deadroutes(ax, arg + '/combined-deadroutes.csv', title)

            f.supxlabel('Time (m)')
            f.supylabel('Peer detecting dead route')

        if _set == 6:
            plot_clustering(ax, arg + '/combined-topology.log.csv', title)
            plot_nodeclustering(ax, arg + '/combined-topology.log.csv', title)
            f.supxlabel('Time (m)')
            f.supylabel('Clustering coeffiecient')
        if _set == 7:
            plot_clustering_vs_reliability(ax, title)
            f.supxlabel('Time (m)')
            f.supylabel('Clustering coeffiecient')

        #plot_avgcost(ax1, arg + '/combined-topology.log.csv', '')
        #plot_msgdist(axes[i], arg)
        #plot_routes(ax, arg, "")
        #plot_cost(ax, arg, "")
        #plot_avgpathlen(ax2, arg + '/combined-topology.log.csv', '')
        #plot_lookups(ax3, arg + '/combined-receive.log.csv')
        #plot_errors(ax, arg + '/combined-handle_error.log.csv')
        
        sns.despine(fig=None, ax=ax, top=True, right=True, left=False, bottom=False, offset=None, trim=False)
        ax.grid(axis='y')
        ax.set_title(title, fontsize = 8)
        i += 1


    #f.suptitle('8 peers, min=2', fontsize=12)
    handles, labels = ax.get_legend_handles_labels()
    f.legend(handles, labels, loc="upper right")#, bbox_to_anchor=(0.65,1.05))
    try:
        for ax in axes:
            ax.get_legend().remove()
    except Exception:
        pass

    plt.show()


def to_offset(df, set_index=False):
    global t0
    df['Offset'] = (df['Timestamp'] - t0).dt.total_seconds()
    df['Offset'] = pd.to_timedelta(df['Offset'], unit='sec')
    if set_index:
        df.set_index('Offset', inplace=True)
    else:
        df = df.reset_index()

    return df

def plot_clustering_vs_reliability(ax, title):

    clustering_df.Offset = clustering_df.Offset.round()
    reliability_df.Offset = reliability_df.Offset.round()

    combined_df = pd.concat([clustering_df, reliability_df]
                            , axis = 1
                            , ignore_index=True
                            )
                        

    print(combined_df)

def plot_reliability(ax, sent, receive, title):
    FREQ = '60s'

    sent_df = pd.read_csv(sent, sep=";")
    sent_df['Timestamp'] = pd.to_datetime(sent_df['Timestamp']).dt.tz_localize('UTC')
    sent_df = to_offset(sent_df).reset_index()
    sent_df = sent_df[['Offset', 'ID']]
    print(sent_df)

    receive_df = pd.read_csv(receive, sep=";")
    receive_df = receive_df.loc[receive_df['Received'] == 'LOOKUP']
    receive_df = receive_df.loc[receive_df['Peer'] == receive_df['Destination']]
    receive_df['Timestamp'] = pd.to_datetime(receive_df['Timestamp']).dt.tz_localize('Europe/Amsterdam').dt.tz_convert('UTC')
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
    result['Offset'] = result['Offset'].dt.total_seconds() / 60
    result = result.loc[result['Offset'] <= CUTOFF]
    result = result.replace(np.nan, 0)
    try:
        result['SuccessRate'] = result['Success'] / (result['Failed'] + result['Success']) * 100
    except Exception:
        result['SuccessRate'] = 100

    global reliability_df
    reliability_df = result
    print(result)

    p = sns.lineplot(ax=ax, data=result, x='Offset', y='SuccessRate', legend=True)
    #p = sns.barplot(ax=ax, data=result, x='Offset', y='SuccessRate')

    p.set(xlabel =None, ylabel = None, title=None)
    p.set_ylim(0, 105)
    #xticks = range(len(result))
    #print(xticks)
    #p.set_xticks(xticks, xticks) # <--- set the ticks first

def plot_latency(ax, sent, receive, title):
    FREQ = '60s'

    sent_df = pd.read_csv(sent, sep=";")
    sent_df['Timestamp'] = pd.to_datetime(sent_df['Timestamp']).dt.tz_localize('UTC')
    sent_df = to_offset(sent_df).reset_index()
    sent_df = sent_df[['Timestamp', 'Offset', 'ID', 'Route', 'Shortest']]
    print(sent)
    print(sent_df)

    receive_df = pd.read_csv(receive, sep=";")
    receive_df = receive_df.loc[receive_df['Received'] == 'LOOKUP']
    receive_df = receive_df.loc[receive_df['Peer'] == receive_df['Destination']]
    receive_df['Timestamp'] = pd.to_datetime(receive_df['Timestamp']).dt.tz_localize('Europe/Amsterdam').dt.tz_convert('UTC')
    receive_df = to_offset(receive_df).reset_index()
    #receive_df['Result'] = 'Success'
    receive_df = receive_df[['Timestamp', 'ID']]
    print(receive)
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
    print("sent JOIN receive")
    print(result)
    #result = result.replace(np.nan, 0)
    result['Latency'] = result.Timestamp_y - result.Timestamp_x
    result['Latency'] = result['Latency'].dt.total_seconds() * 1000
    #result = result.loc[result['Latency'] <= 1000]
    result.set_index('Offset', inplace=True)
    result = result.groupby([pd.Grouper(freq = FREQ),'Shortest'])['Latency'].mean().reset_index()
    result['Offset'] = result['Offset'].dt.total_seconds() / 60
    #result = result.reset_index()
    result = result.replace(True, "Shortest (Dijkstra)")
    result = result.replace(False, "Others")
    result = result.rename(columns={"Shortest": "Actual latency"})
    result = result.loc[result['Offset'] <= CUTOFF]
    max_y = result.Latency.max() + 100
    print("Latencies")
    print(result)

    #p = sns.lineplot(ax=ax, data=result, x='Offset', y='Latency', hue='Actual latency', style='Actual latency', legend=True)
    p = sns.lineplot(ax=ax, data=result, x='Offset', y='Latency', legend=True)
    ax.set_title(title)
    #ax.set(xlabel='Time (s)', ylabel='Latency (ms)')
    ax.set(xlabel=None, ylabel=None)
    p.set_ylim(0, 1200)
    #p.set_xticklabels(['2011','2012','2013','2014','20

    # Volume
    #sent_df = sent_df[['Timestamp', 'Offset', 'ID', 'Route', 'Shortest']]
    #vol_df = sent_df[['Offset', 'ID']]
    #vol_df.set_index('Offset', inplace=True)
    #vol_df = vol_df.groupby([pd.Grouper(freq = FREQ)])['ID'].size().reset_index()
    #vol_df['Offset'] = vol_df['Offset'].dt.total_seconds()
    #vol_df = vol_df.loc[vol_df['Offset'] <= CUTOFF]
    #print(vol_df)
    #ax2 = ax.twinx()
    #p2 = sns.barplot(data=vol_df, x='Offset', y='ID', alpha=0.5, ax=ax2)
    
    #xticks = range(len(vol_df))
    #p.set_xticks(xticks, xticks) # <--- set the ticks first
    #p2.set_xticks(xticks, xticks) # <--- set the ticks first
    #print(xticks)

def plot_deadroutes(ax, csvfile, title):
    df = pd.read_csv(csvfile, sep=";")
    df['Timestamp'] = pd.to_datetime(df['Timestamp']).dt.tz_localize('UTC')
    df = to_offset(df).reset_index()
    df = df[['Offset', 'Peer', 'DeadPeer']]
    df['Offset'] = df['Offset'].dt.total_seconds() / 60
    df = df.loc[df['Offset'] <= CUTOFF]
    #df.set_index('Offset', inplace=True)
    print(df)
    p = sns.scatterplot(ax=ax, data=df, x='Offset', y='Peer', hue='DeadPeer', legend=True)
    #ax.set(xlabel='Time (s)', ylabel='Peer')
    ax.set(xlabel=None, ylabel=None)
    #ax.grid(axis='y')

def plot_avgpathlen(ax, csvfile, title):
    df = pd.read_csv(csvfile, sep=";")
    df = to_offset(df).reset_index()
    df = df[['Offset', 'AvgPathLen']]
    df.set_index('Offset', inplace=True)

    df = df.groupby([pd.Grouper(freq = '30s')])['AvgPathLen'].mean().reset_index()
    df['Offset'] = df['Offset'].dt.total_seconds()
    df = df.loc[df['Offset'] <= CUTOFF]
    print(df)

    df.plot(ax=ax, x='Offset', y='AvgPathLen', kind='line', colormap="tab20", legend=False,
          xlabel = "Time (s)", ylabel = "Avg. path length")

def plot_avgdegree(ax, csvfile, title):
    df = pd.read_csv(csvfile, sep=";")
    df['Timestamp'] = pd.to_datetime(df['Timestamp']).dt.tz_localize('Europe/Amsterdam').dt.tz_convert('UTC')
    df = to_offset(df).reset_index()
    df = df[['Offset', 'AvgDegree']]
    df.set_index('Offset', inplace=True)

    df = df.groupby([pd.Grouper(freq = FREQ)])['AvgDegree'].mean().reset_index()
    df['Offset'] = df['Offset'].dt.total_seconds() / 60
    df = df.loc[df['Offset'] <= CUTOFF]
    print(df)

    p = sns.lineplot(ax=ax, data=df, x='Offset', y='AvgDegree', legend=True, linewidth = 2, linestyle = "dashed" )

    return p

def plot_degree(ax, csvfile, title):
    df = pd.read_csv(csvfile, sep=";")
    df['Timestamp'] = pd.to_datetime(df['Timestamp']).dt.tz_localize('Europe/Amsterdam').dt.tz_convert('UTC')

    #df = df.loc[df['Peer'] == "P8"]
    df = to_offset(df)
    df = df[['Offset', 'Peer', 'NodeDegree']]
    #df.set_index('Offset', inplace=True)

    #df = df.groupby([pd.Grouper(freq = FREQ), 'Peer'])['NodeDegree'].mean().unstack().reset_index()
    df['Offset'] = df['Offset'].dt.total_seconds() / 60
    df = df.loc[df['Offset'] <= CUTOFF]
    print(df)

    p = sns.lineplot(ax=ax, data=df, x='Offset', y='NodeDegree', hue='Peer', hue_order=hue_order, legend=True)
    #p.set(xlabel='Time (s)', ylabel='Node degree')
    p.set(xlabel=None, ylabel=None)
    p.set_ylim(0, 8)

    

def plot_clustering(ax, csvfile, title):

    df = pd.read_csv(csvfile, sep=";")
    df['Timestamp'] = pd.to_datetime(df['Timestamp']).dt.tz_localize('Europe/Amsterdam').dt.tz_convert('UTC')
    df = to_offset(df).reset_index()
    df = df[['Offset', 'Clustering']]
    df.set_index('Offset', inplace=True)

    df = df.groupby([pd.Grouper(freq = FREQ)])['Clustering'].mean().reset_index()
    df['Offset'] = df['Offset'].dt.total_seconds() / 60
    df = df.loc[df['Offset'] <= CUTOFF]
    print(df)

    global clustering_df
    clustering_df = df

    p = sns.lineplot(ax=ax, data=df, x='Offset', y='Clustering', legend=True, linewidth = 2, linestyle = "dashed" )
    #p.set(xlabel='Time (s)', ylabel='Node degree')
    p.set(xlabel=None, ylabel=None)
    p.set_ylim(0, 1.1)

def plot_nodeclustering(ax, csvfile, title):
    df = pd.read_csv(csvfile, sep=";")
    df['Timestamp'] = pd.to_datetime(df['Timestamp']).dt.tz_localize('Europe/Amsterdam').dt.tz_convert('UTC')
    df = to_offset(df).reset_index()
    df = df[['Offset', 'Peer', 'NodeClustering']]
    df.set_index('Offset', inplace=True)

    df = df.groupby([pd.Grouper(freq = FREQ), 'Peer'])['NodeClustering'].mean().reset_index()
    df['Offset'] = df['Offset'].dt.total_seconds() / 60
    df = df.loc[df['Offset'] <= CUTOFF]
    print(df)

    p = sns.lineplot(ax=ax, data=df, x='Offset', y='NodeClustering', hue='Peer', legend=True)
    #p.set(xlabel='Time (s)', ylabel='Node degree')
    p.set(xlabel=None, ylabel=None)
    p.set_ylim(0, 1.1)

def plot_avgcost(ax, csvfile, title):
    df = pd.read_csv(csvfile, sep=";")
    df['Timestamp'] = pd.to_datetime(df['Timestamp']).dt.tz_localize('Europe/Amsterdam').dt.tz_convert('UTC')
    df = to_offset(df).reset_index()
    df = df[['Offset', 'AvgCost']]
    df.set_index('Offset', inplace=True)

    df = df.groupby([pd.Grouper(freq = FREQ)])['AvgCost'].mean().reset_index()
    df['Offset'] = df['Offset'].dt.total_seconds() / 60
    #df = df.loc[df['Offset'] <= CUTOFF]
    print(df)

    p = sns.lineplot(ax=ax, data=df, x='Offset', y='AvgCost', legend=True)
    p.set(xlabel=None, ylabel=None)

def plot_routes(ax, csvfile, title):
    df = pd.read_csv(csvfile, sep=";")
    path = df["Path"].str.split("-", n = 1, expand = True)
    df['Source'] = path[0]
    df['Destination'] = path[1]
    #df = df.loc[df['Peer'] == "P2"]
    #df = to_offset(df).reset_index()
    #df = df[['Offset', 'Peer', 'Path', 'Source', 'Destination', 'RP', 'Cost']]
    df = df[['Path', 'RP']]
    #df.set_index('Offset', inplace=True)

    #df = df.groupby([pd.Grouper(freq = FREQ)])['RP'].first().reset_index()
    #df['Offset'] = df['Offset'].dt.total_seconds()
    #df = df.loc[df['Offset'] <= CUTOFF]
    df = df.groupby(['Path'])['RP'].nunique()

    print(df)
    #sns.stripplot(
    #    data=df, x="Offset", y="Path", hue="RP",)
    #sns.lineplot(data=df, x="Offset", y="RP", hue="Path")
    df.plot(kind='barh', ax=ax)
    ax.set_xlabel("# Rendezvous Points used")
    ax.set_ylabel("Path")

def plot_msgdist(ax, csvfile):
    df = pd.read_csv(csvfile, sep=";")
    df = df.loc[df['Peer'] != "Peer"]
    df = df.loc[df['Received'] != "LOOKUP"]

    # pct total
    sp_title = csvfile.split('/')[0]
    df = df[['Received']]
    df_add = pd.DataFrame({'Received': ['HB','LSA','JOIN','HELLO']})
    df = df.append(df_add)
    df = df.groupby(['Received'])['Received'].size().reset_index(name="Count")
    df['Pct'] = 100 * df['Count'] / df.Count.sum()
    df = df[['Received','Pct']]
    print("plot_msgdist:")
    print(df)

    df.plot(ax=ax, kind='bar', x='Received', legend=False)
    ax.set_title(sp_title)
    ax.set_xlabel("Message")
    ax.set_ylabel("Received (%)")
    #sns.barplot(ax=ax, data=df, x='Received', y='0', hue='Set')
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
    csv['Timestamp'] = pd.to_datetime(csv['Timestamp']).dt.tz_localize('Europe/Amsterdam').dt.tz_convert('UTC')
    csv = csv.loc[csv['Received'] == "LOOKUP"]
    csv = to_offset(csv)
    csv = csv[['Offset', 'Peer']]
    csv.set_index('Offset', inplace=True)

    csv = csv.groupby([pd.Grouper(freq = '1min'), 'Peer']).size().reset_index(name='Received')
    csv['Offset'] = csv['Offset'].dt.total_seconds()

    print(csv)

    p = sns.lineplot(ax=ax, data=csv, x='Offset', y='Received', hue='Peer', legend=False)
    p.set(xlabel='Time (s)', ylabel='Msgs rcvd. / min')


def plot_cost(ax, csvfile, title):
    df = pd.read_csv(csvfile, sep=";")
    df = df.loc[df['Peer'] == "P1"]
    df = to_offset(df).reset_index()
    df['Offset'] = df['Offset'].dt.total_seconds()
    df = df[['Offset', 'Path', 'RP', 'Cost']]
    print(df)

    plot = sns.lineplot(ax=ax, data=df, x='Offset', y='Cost',
                style="Path", hue="Path",
                # multiple="stack",
                #hue_order=["LSA", "HB", "LOOKUP", "HELLO", "JOIN"],
                #binwidth=10, stat="count", kde=False, 
                #col="Peer", col_wrap=2,
                legend=True
            )
    plot.set_xlabel("Time (s)")
    plot.set_ylabel("Cost")

    df2 = df.groupby(['Path', 'RP'])['Offset'].first().reset_index()
    df2 = df2.sort_values(by="Offset")
    print(df2)
    

    df3 = df.loc[df['Cost'] != "1000"]
    df3 = df3.groupby(['Path', 'RP'])['Cost'].mean().reset_index()
    print(df3)

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
    
    csv['Timestamp'] = pd.to_datetime(csv['Timestamp']).dt.tz_localize('Europe/Amsterdam').dt.tz_convert('UTC')
    csv = to_offset(csv)
    csv = csv[['Offset', 'Peer', 'Convergence']]
    csv.set_index('Offset', inplace=True)

    csv = csv.groupby([pd.Grouper(freq = '1s')])['Convergence'].mean().reset_index()
    #csv = csv.groupby(['Offset'])['Convergence'].mean().reset_index()
    #csv.where(filter, inplace = True)
    csv['Offset'] = csv['Offset'].dt.total_seconds() / 60
    csv = csv.loc[csv['Offset'] <= CUTOFF]
    print(csv)
    
    #p = sns.pointplot(ax=ax, data=csv, x='Offset', y='Convergence')
    p = sns.lineplot(ax=ax, data=csv, x='Offset', y='Convergence', legend=True)

    p.set(xlabel = None, ylabel = None)
    p.set_ylim(0, 105)
    ax.set_title(title, fontsize = 8)
    #xticks = range(len(csv))
    #p.set_xticks(xticks, xticks) # <--- set the ticks first
    #xlabels = ['{:,.2f}'.format(x) for x in p.get_xticks()/60]
    #p.set_xticklabels(xlabels)

def plot_errors(ax, errors):
    df = pd.read_csv(errors, sep=";")
    df['Timestamp'] = pd.to_datetime(df['Timestamp']).dt.tz_localize('UTC')
    df = to_offset(df, True)
    #df = df.groupby([pd.Grouper(freq = '60s'), 'Peer'])['RelayIP'].size().reset_index()
    df['Offset'] = df['Offset'].dt.total_seconds()
    df = df[['Offset', 'Peer', 'RelayIP']]
    print(df)
    p = sns.lineplot(ax=ax, data=df, x='Offset', y='RelayIP', hue='Peer', legend=False)
    ax.set(xlabel='Time (s)', ylabel='Errors')



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

    #for s in range(1,8,1):
    #    main(s)
    main(4)
