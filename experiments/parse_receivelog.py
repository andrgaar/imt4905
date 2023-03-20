#!/usr/bin/python3

import sys
import pickle
from datetime import datetime

fname = sys.argv[1]
data = 1

with open(fname, "rb") as f:
    while True:
        try:
            data = pickle.load(f)
        except EOFError:
            break

        print(data)
                


