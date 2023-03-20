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

def datetime_to_timedelta(dt):
    return (dt - dt_origin).total_seconds()


def rate(x):
    s = np.sum(x)
    f = s / 30
    return round(f)

prev_timestamp = None
epoch_time = datetime(1970, 1, 1)

topology = {}

fname = sys.argv[1]

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

    upload = df[['Timestamp', 'Peer', 'Upload']]
    upload['Timestamp'] = pd.to_datetime(upload['Timestamp'])  
    #df['Delta'] = df["Timestamp"].apply(lambda dt: datetime_to_timedelta(dt)) 
    
    #df['Delta'] = pd.to_timedelta(df['Delta'])  
    upload.set_index('Timestamp', inplace=True)
    print(upload)
    upload.resample("30S").mean().plot(color="black", style="-o", figsize=(10, 5), legend=False);

    df2 = df.describe()
    print(df2)

    plt.xlabel("Time")
    plt.ylabel("Bytes/sec") 
    plt.show()
    sys.exit()

    df_g = df.groupby([pd.Grouper(freq='10s'), 'Peer']).agg(Upload=('Upload', np.mean), Download=('Download', np.mean))
    print(df_g)
    #print(df_g)
    #df.plot(kind='line', y=["Upload"])
    #res = sns.lineplot(x="Delta", y="Upload", data=df)
    sns.relplot(
        data=df_g, kind="line", legend=False,
        x="Timestamp", y="Upload", col="Peer", 
        hue="Peer", #size="Peer", style="Peer",
        facet_kws=dict(sharex=False), col_wrap=2, palette=['k']
        )
    
            
