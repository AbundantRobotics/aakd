#!/usr/bin/env python3
import sys
import re
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import cm


fields = []
fields.append(re.compile('il\..*', re.IGNORECASE)) # current related
fields.append(re.compile('vl\..*', re.IGNORECASE)) # velocity related
fields.append(re.compile('pl\.(?!err).*', re.IGNORECASE)) # position related
fields.append(re.compile('.*')) # all the rest

colorss = [cm.Reds, cm.Blues, cm.Greens, cm.Dark2]



if len(sys.argv) < 2:
    exit(-1)

filenb = len(sys.argv) - 1

names = []
ts = []
colss = []
plot_nbs = []

for k in range(filenb):
    filename = sys.argv[k+1]
    names.append('.'.join(filename.split('.')[:-1]))

    ts.append(pd.read_csv(filename, index_col=0))  # we assume first column is abscisse (Time)

    colss.append([])
    for i in range(len(fields)):
        colss[k].append([])

    for c in ts[k].columns:
        if not re.match('[a-zA-Z].*', c):
            print("Columns titles are bad, ex: " + c)
            sys.exit(-1)
        for i, f in enumerate(fields):
            if f.match(c):
                colss[k][i].append(c)
                break

    plot_nbs.append(sum(int(len(c) > 0) for c in colss[k][0:-1]) + len(colss[k][-1]))


f = plt.figure()

i = 0
ax1 = False

def next_subplot(k, title):
    global ax1, i
    i = i + 1
    if not ax1:
        ax1 = f.add_subplot(plot_nbs[k], filenb, 1 + (i-1)*filenb+k)
        ax = ax1
    else:
        ax = f.add_subplot(plot_nbs[k], filenb, 1 + (i-1)*filenb+k, sharex=ax1)
    if i == 1:
        ax.set_title(title)
    return ax

for k in range(filenb):
    i = 0
    for c, colors in zip(colss[k][0:3], colorss):
        if c:
            ax = next_subplot(k, names[k])
            ts[k][c].plot(grid=True, ax=ax, colormap=lambda x : colors(1-(x/2/len(c))))
    for (cn, c) in enumerate(colss[k][-1]):
        ax = next_subplot(k, names[k])
        ts[k][[c]].plot(grid=True, ax=ax, colormap=lambda x : colorss[3](int(x+cn)))


f.canvas.set_window_title('+'.join(names))

plt.show()
