#!/usr/bin/python3

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import networkx as nx
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats
import sys
import json
from datetime import datetime

dt_origin = None
CUTOFF = 300

def datetime_to_timedelta(dt):
    return (dt - dt_origin).total_seconds()


def rate(x):
    s = np.sum(x)
    f = s / 30
    return round(f)

prev_timestamp = None
epoch_time = datetime(1970, 1, 1)

topology = {}

argv = sys.argv
argv.pop(0)

f, axes = plt.subplots(len(argv), sharex=True, layout='constrained')
ax_i = 0
for arg in argv:
    fname = arg
    if len(argv) > 1:
        ax = axes[ax_i]
    else:
        ax = axes

    with open(fname, "r") as f:

        fout_name = f"{fname}.csv"
        fout = open(fout_name, "w")
        fout.write("Timestamp;Peer;Upload;Download\n")

        for line in f:
            timestamp, pid, name, cmd, upload, download = line.strip().split(';')
            if timestamp == "Time":
                continue
            
            cmd_a = json.loads(cmd)
            if cmd_a[0] != "python3":
                continue
            i = 0 
            while i < len(cmd_a):
                if cmd_a[i] == "-i":
                    p = cmd_a[i + 1]
                    break
                i += 1
            p = "P" + p

            if prev_timestamp == None:
                prev_timestamp = timestamp
                dt_origin = datetime.fromtimestamp(float(timestamp))

            dt_event = datetime.fromtimestamp(float(timestamp))
            dt_prev = datetime.fromtimestamp(float(prev_timestamp))
            dt_diff = dt_event - dt_prev
            
            x = round(dt_diff.total_seconds())
            
            fout.write("{0};{1};{2};{3}\n".format(dt_event, p, upload, download))
        fout.close()

        df = pd.read_csv(fout_name, sep=';')
        
        df = df.loc[df['Peer'] == "P1"]
        df = df.tail(-5)

        df['Timestamp'] = pd.to_datetime(df['Timestamp'])
        t0 = df.min()['Timestamp']
        df['Offset'] = (df['Timestamp'] - t0).dt.total_seconds()
        df = df.loc[df['Offset'] <= CUTOFF]
        df['Offset'] = pd.to_timedelta(df['Offset'], unit='sec')

        upload = df[['Offset', 'Peer', 'Upload', 'Download']]
        df.set_index('Offset', inplace=True)
        #print(upload)

        df1 = df.groupby([pd.Grouper(freq='1s'), 'Peer']).agg(Upload=('Upload', np.mean), Download=('Download', np.mean)).reset_index()
        df1['Offset'] = df1['Offset'].dt.total_seconds()
        df1 = df1.rename(columns={"Upload": "Outbound", "Download": "Inbound"})
        df1[ 'Outbound rolling avg' ] = df1.Outbound.rolling(30).mean()
        df1[ 'Inbound rolling avg' ] = df1.Inbound.rolling(30).mean()
        #print(df1)

        df1.plot(ax=ax, x='Offset', y='Outbound', kind='area', legend=True, xlabel = "Time (s)", ylabel = "Bytes / sec", stacked=False)
        df1.plot(ax=ax, x='Offset', y='Outbound rolling avg', kind='line', style="-", legend=True, xlabel = "Time (s)", ylabel = "Bytes / sec")
        
        df1.plot(ax=ax, x='Offset', y='Inbound', kind='area', legend=True, xlabel = "Time (s)", ylabel = "Bytes / sec", stacked=False)
        df1.plot(ax=ax, x='Offset', y='Inbound rolling avg', kind='line', style="--", legend=True, xlabel = "Time (s)", ylabel = "Bytes / sec")

        #ax.set_title(arg.split('/')[0])
        
        print()
        print(arg)
        print(df1.describe())

    ax_i += 1

plt.show()
