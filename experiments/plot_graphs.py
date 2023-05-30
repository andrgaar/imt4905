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

clustering_df = pd.DataFrame()
reliability_df = pd.DataFrame()
deadroutes_df = pd.DataFrame()
latency_df = pd.DataFrame()

hue_order = ['P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7', 'P8']

def main(_set):
    global t0

    cmb_df1 = pd.DataFrame()

    sp_rows = len(argv)
    if _set in ([2,3]):
        sp_rows = sp_rows * 2
    #receivelog(arg1)
    #f, ((ax1, ax2), (ax3, ax4), (ax5, ax6)) = plt.subplots(3, 2, sharex=True
    #f, (ax1, ax2, ax3) = plt.subplots(3, 1, sharex=True, 
    f, axes = plt.subplots(sp_rows, 1, sharex=True, figsize=(12, 6) ,# subplot_kw={'ylim': (0,100)}
    #f, ax = plt.subplots(1, 1, sharex=True, # subplot_kw={'ylim': (0,100)}
            layout='constrained')
    #ax = plt.figure().add_subplot(projection='3d')
    i = 0
    ax = None
    for arg in argv:
        if sp_rows == 1:
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
            plot_degree(ax, arg + '/combined-neighbours.csv', 'Node degree - ' + title)
            sns.despine(fig=None, ax=ax, top=True, right=True, left=False, bottom=False, offset=None, trim=False)
            ax.grid(axis='y')
            ax.set_title('Node degree : ' + title, fontsize = 8)

            i += 1
            ax = axes[i]
            plot_deadroutes(ax, arg + '/combined-deadroutes.csv', 'Dead routes - ' + title)
            sns.despine(fig=None, ax=ax, top=True, right=True, left=False, bottom=False, offset=None, trim=False)
            ax.grid(axis='y')
            ax.set_title('Dead routes : ' + title, fontsize = 8)

            #f.supxlabel('Time (m)')
            #f.supylabel('Node degree')
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
        if _set == 8:
            df1 = plot_reliability(None, arg + '/combined-sent.log.csv', arg + '/combined-receive.log.csv', title)
            df2 = plot_deadroutes(None, arg + '/combined-deadroutes.csv', title)
            
            df1.Offset = df1.Offset.round()
            df2.Offset = df2.Offset.round()
            
            combined_df = pd.merge(
                df1, df2,
                how="inner",
                on='Offset',
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
            print("combined_df:")
            print(combined_df)

            cmb_df1 = pd.concat(
                [cmb_df1, combined_df],
                axis=0,
                join="outer",
                ignore_index=True,
                keys=None,
                levels=None,
                names=None,
                verify_integrity=False,
                copy=True,
                )

            print("Combined:")
            print(cmb_df1)
        if _set == 9:
            #plot_latency(ax, arg + '/combined-sent.log.csv', arg + '/combined-receive.log.csv', title)
            plot_avgpathlen(ax, arg + '/combined-topology.log.csv', '')
        if _set == 10:
            plot_messages(ax, arg + '/combined-receive.log.csv')
        if _set == 11:
            plot_avgcost(ax, arg + '/combined-topology.log.csv', '')
            

        #plot_msgdist(axes[i], arg)
        #plot_routes(ax, arg, "")
        #plot_cost(ax, arg, "")
        #plot_errors(ax, arg + '/combined-handle_error.log.csv')
        
        sns.despine(fig=None, ax=ax, top=True, right=True, left=False, bottom=False, offset=None, trim=False)
        ax.grid(axis='y')
        #ax.set_title(title, fontsize = 8)
        i += 1

    if _set == 8:
        plot_deadroutes_vs_reliability(ax, cmb_df1, title)

        
    #f.suptitle('8 peers, min=2', fontsize=12)
    if _set not in([1,3,4,6,9]):
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

def plot_deadroutes_vs_reliability(ax, df, title):

    df = df.rename(columns = {'Peer':'Dead routes', 'SuccessRate':'Success rate'})

    print("Dead routes vs reliability")
    print(df)

    g = sns.relplot(kind="line", data=df, x='Dead routes', y='Success rate');

def plot_reliability(ax, sent, receive, title):
    FREQ = '60s'

    sent_df = pd.read_csv(sent, sep=";")
    sent_df['Timestamp'] = pd.to_datetime(sent_df['Timestamp']).dt.tz_localize('UTC')
    sent_df = to_offset(sent_df).reset_index()
    sent_df = sent_df[['Offset', 'ID']]
    #print(sent_df)

    receive_df = pd.read_csv(receive, sep=";")
    receive_df = receive_df.loc[receive_df['Received'] == 'LOOKUP']
    receive_df = receive_df.loc[receive_df['Peer'] == receive_df['Destination']]
    receive_df['Timestamp'] = pd.to_datetime(receive_df['Timestamp']).dt.tz_localize('Europe/Amsterdam').dt.tz_convert('UTC')
    receive_df = to_offset(receive_df).reset_index()
    receive_df['Result'] = 'Success'
    receive_df = receive_df[['ID', 'Result']]
    #print(receive_df)

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

    failed_df = result
    failed_df = failed_df.loc[failed_df['Result'] == 'Failed']
    print(failed_df.to_string())

    result.set_index('Offset', inplace=True)
    result = result.groupby([pd.Grouper(freq = FREQ), 'Result'])['Result'].size().unstack().reset_index()
    result['Offset'] = result['Offset'].dt.total_seconds() / 60
    result = result.loc[result['Offset'] <= CUTOFF]
    result = result.replace(np.nan, 0)
    try:
        result['SuccessRate'] = result['Success'] / (result['Failed'] + result['Success']) * 100
    except Exception:
        result['SuccessRate'] = 100

    print("Reliability")
    #print(result)
    print(result.describe())

    p = sns.lineplot(ax=ax, data=result, x='Offset', y='SuccessRate', legend=True)
    #p = sns.barplot(ax=ax, data=result, x='Offset', y='SuccessRate')

    p.set(xlabel =None, ylabel = None, title=None)
    p.set_ylim(0, 105)
    #xticks = range(len(result))
    #print(xticks)
    #p.set_xticks(xticks, xticks) # <--- set the ticks first

    return result

def plot_latency(ax, sent, receive, title):
    FREQ = '60s'

    sent_df = pd.read_csv(sent, sep=";")
    sent_df['Timestamp'] = pd.to_datetime(sent_df['Timestamp']).dt.tz_localize('UTC')
    sent_df = to_offset(sent_df).reset_index()
    sent_df = sent_df[['Timestamp', 'Offset', 'ID', 'Route', 'Shortest']]
    #print(sent)
    #print(sent_df)

    receive_df = pd.read_csv(receive, sep=";")
    receive_df = receive_df.loc[receive_df['Received'] == 'LOOKUP']
    receive_df = receive_df.loc[receive_df['Peer'] == receive_df['Destination']]
    receive_df['Timestamp'] = pd.to_datetime(receive_df['Timestamp']).dt.tz_localize('Europe/Amsterdam').dt.tz_convert('UTC')
    receive_df = to_offset(receive_df).reset_index()
    #receive_df['Result'] = 'Success'
    receive_df = receive_df[['Timestamp', 'ID']]
    #print(receive_df)

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
    print(result.to_string())

    result['Latency'] = result.Timestamp_y - result.Timestamp_x
    result['Latency'] = result['Latency'].dt.total_seconds() * 1000
    result = result.loc[result['Latency'] < 1000]
    #result.set_index('Offset', inplace=True)
    #result = result.groupby([pd.Grouper(freq = FREQ),'Shortest','Route'])['Latency'].mean().reset_index()
    result['Time_min'] = result['Offset'].dt.total_seconds() / 60
    #result['Offset'] = result['Offset'].dt.total_seconds()
    #result['Offset'] = result['Offset'].round(0)
    result = result.replace(True, "Shortest (Dijkstra)")
    result = result.replace(False, "Others")
    result = result.rename(columns={"Shortest": "Actual latency"})
    #result = result.loc[result['Offset'] <= CUTOFF]
    max_y = result.Latency.max() + 100
    print("Latencies")
    print(result.to_string())
    #print(result.describe())

    global latency_df
    latency_df = result

    #p = sns.lineplot(ax=ax, data=result, x='Offset', y='Latency', hue='Actual latency', style='Actual latency', legend=True)
    #p = sns.lineplot(ax=ax, data=result, x='Offset', y='Latency', hue='Route', legend=True)
    p = sns.scatterplot(ax=ax, data=result, x='Time_min', y='Latency', hue='Route', legend=True)

    shortest_df = result.loc[result['Actual latency'] == 'Shortest (Dijkstra)']
    p = sns.lineplot(ax=ax, data=shortest_df, x='Time_min', y='Latency', color='black', size='Actual latency', legend=True)

    xlabels = [int(x) for x in p.get_xticks()]
    p.set_xticklabels(xlabels)

    #ax.set_title(title)
    #ax.set(xlabel='Time (s)', ylabel='Latency (ms)')
    ax.set(xlabel=None, ylabel=None)
    #p.set_ylim(0, 1200)

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

    print("-----------------------")
    print("Best each minute")
    ax2 = plt.figure().add_subplot()

    shortest_df.set_index('Offset', inplace=True)
    shortest_df = shortest_df.groupby([pd.Grouper(freq = '60s')])['Latency'].mean().reset_index()
    shortest_df['Time_min'] = shortest_df['Offset'].dt.total_seconds() / 60
    shortest_df['Mean latency'] = 'Selected path'

    sns.lineplot(ax=ax2, data=shortest_df, x='Time_min', y='Latency', hue='Mean latency', palette=['black'], legend=True)
    

    result.set_index('Offset', inplace=True)
    grp_df = result.groupby([pd.Grouper(freq = '60s')])['Latency'].mean().reset_index()
    grp_df['Time_min'] = grp_df['Offset'].dt.total_seconds() / 60
    grp_df['Mean latency'] = 'All paths'
    #grp_df = grp_df[['Time_min', 'Actual latency', 'Latency']]
    print(grp_df.to_string())

    p2 = sns.lineplot(ax=ax2, data=grp_df, x='Time_min', y='Latency', hue='Mean latency', palette=['orange'], legend=True)

    xlabels = [int(x) for x in p2.get_xticks()]
    p2.set_xticklabels(xlabels)
    ax2.set(xlabel='Time (m)', ylabel='Latency (ms)')

def plot_deadroutes(ax, csvfile, title):
    df = pd.read_csv(csvfile, sep=";")
    df['Timestamp'] = pd.to_datetime(df['Timestamp']).dt.tz_localize('UTC')
    df = to_offset(df).reset_index()
    df = df[['Offset', 'Peer', 'DeadPeer']]

    df.set_index('Offset', inplace=True)
    df = df.groupby([pd.Grouper(freq = FREQ)])['Peer'].size().reset_index()
    
    df['Offset'] = df['Offset'].dt.total_seconds() / 60
    #df = df.loc[df['Offset'] <= CUTOFF]
    print("Deadroutes")
    print(df)
    #p = sns.scatterplot(ax=ax, data=df, x='Offset', y='Peer', hue='DeadPeer', legend=True)
    #ax.set(xlabel='Time (m)', ylabel='Peer detecting')

    p = sns.lineplot(ax=ax, data=df, x='Offset', y='Peer', legend=True)

    #ax.set(xlabel=None, ylabel=None)
    #ax.grid(axis='y')

    return df

def plot_avgpathlen(ax, csvfile, title):
    df = pd.read_csv(csvfile, sep=";")
    df['Timestamp'] = pd.to_datetime(df['Timestamp']).dt.tz_localize('Europe/Amsterdam').dt.tz_convert('UTC')
    df = to_offset(df).reset_index()
    df = df[['Offset', 'AvgPathLen', 'AvgCost']]
    df = df.loc[df['AvgPathLen'] > 0]
    df = df.loc[df['AvgCost'] < 1000]
    df.set_index('Offset', inplace=True)
    print(df)

    #df = df.groupby([pd.Grouper(freq = '60s')])['AvgPathLen'].mean().reset_index()
    df = df.groupby([pd.Grouper(freq = '60s')]).agg(MeanPathLen=('AvgPathLen', np.mean), MeanCost=('AvgCost', np.mean)).reset_index()
    df['Offset'] = df['Offset'].dt.total_seconds() / 60

    print(df)
    
    
    #dfm = df.melt('Offset', var_name='Parameter', value_name='Value')
    #df1 = df[['Offset', 'MeanPathLen']]
    #df2 = df[['Offset', 'MeanCost']]
    
    #sns.relplot(ax=ax, data=df, x='AvgPathLen', y='AvgCost')

    p2 = sns.lineplot(ax=ax, data=df, x='Offset', y='MeanCost', color="orange", linestyle="dashed", label='Cost', legend=False)
    ax.set(xlabel='Time (m)', ylabel='Mean path cost')
    ax.legend(loc='upper right')
    ax2 = ax.twinx()
    p1 = sns.lineplot(ax=ax2, data=df, x='Offset', y='MeanPathLen', color="blue", label='Path length', legend=False)
    ax2.set(xlabel='Time (m)', ylabel='Mean path length')
    ax2.legend(loc='upper center')


    global latency_df
    if not latency_df.empty:
        
        df.Offset = df.Offset.round(0)
        latency_df.Offset = latency_df.Offset.round(0)
        print("Latency:")
        print(latency_df)

        result = pd.merge(
            df,
            latency_df,
            how="left",
            on='Offset',
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
        print(result)
        p3 = sns.lineplot(ax=ax, data=result, x='Offset', y='Latency', color="red", label='Actual latency', legend=True)


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
    p.set(xlabel='Time (m)', ylabel='Node degree')
    #p.set(xlabel=None, ylabel=None)
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
    df = df[['Offset', 'AvgCost', 'AvgPathLen']]
    df.set_index('Offset', inplace=True)

    df = df.groupby([pd.Grouper(freq = FREQ)]).agg(MeanPathLen=('AvgPathLen', np.mean), MeanCost=('AvgCost', np.mean)).reset_index()
    df['Offset'] = df['Offset'].dt.total_seconds() / 60
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


def plot_messages(ax, csvfile):
    csv = pd.read_csv(csvfile, sep=";")

    csv['Timestamp'] = pd.to_datetime(csv['Timestamp']).dt.tz_localize('Europe/Amsterdam').dt.tz_convert('UTC')
    csv = csv.loc[csv['Received'] == "LSA"]
    csv = csv.loc[csv['Peer'] == "P1"]
    csv = to_offset(csv)
    csv = csv[['Offset', 'Peer']]
    csv.set_index('Offset', inplace=True)

    csv = csv.groupby([pd.Grouper(freq = '1min'),'Peer']).size().reset_index(name='Received')
    csv['Offset'] = csv['Offset'].dt.total_seconds() / 60

    print(csv)

    p = sns.lineplot(ax=ax, data=csv, x='Offset', y='Received', hue='Peer', legend=True)
    p.set(xlabel='Time (m)', ylabel='Msgs rcvd. / min')


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
    #csv = csv.loc[csv['Offset'] <= CUTOFF]
    print(csv)
    
    #p = sns.pointplot(ax=ax, data=csv, x='Offset', y='Convergence')
    p = sns.lineplot(ax=ax, data=csv, x='Offset', y='Convergence', legend=True)

    p.set(xlabel = None, ylabel = None)
    #p.set_xlim(0, 30)
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
