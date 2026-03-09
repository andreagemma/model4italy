from __future__ import annotations
import numpy as np
import csv
import pandas as pd
from scipy.sparse import csr_matrix as matrix, SparseEfficiencyWarning
import glob
import warnings
warnings.simplefilter('ignore',SparseEfficiencyWarning)

class MatrixAss:
    class OD:

        def __init__(self, origins, destinations, detectors):
            self.origins = origins
            self.destinations = destinations
            #self.detectors = detectors
            no = len(origins)
            nd = len(destinations)
            nl = len(detectors)

            self.mat = matrix((nl, no * nd))
            self.no = no
            self.nd = nd
            self.nl = nl

        def __getitem__(self, key):
            i, j, l = key
            idx = i * self.nd + j
            return self.mat[l, idx]

        def __setitem__(self, key, value):
            i, j, l = key
            idx = i * self.nd + j
            self.mat[l, idx] = value
            

    def __init__(self, loader=None, n_intervals=None, links_detected=None, G=None, pre_intervals=None):
        from ..connectors import Loader
        loader: Loader = loader
        self.G = loader.G if G is None else G
        self.origins = loader.origins
        self.destinations = loader.destinations
        
        self.detectors = sorted(loader.detectors["id_link"].to_list() if links_detected is None else links_detected)

        self.delta_t = loader.delta_t
        self.n_intervals = n_intervals
        self.pre_intervals = int(loader.ini.OD_ESTIMATION_WHISKERS / self.delta_t) if pre_intervals is None else pre_intervals

        self.mats = {}
        self.d_mats = {}

        self.o2i = dict([(self.origins[i], i) for i in range(len(self.origins))])
        self.d2i = dict([(self.destinations[i], i) for i in range(len(self.destinations))])
        self.l2i = dict([(self.detectors[i], i) for i in range(len(self.detectors))])

        for tenter in range(self.n_intervals):
            for tstart in range(tenter-self.pre_intervals,tenter + 1):
                # print('.',tstart, tenter, self._idx(tstart, tenter))
                # print(tenter,tstart)
                if tenter - tstart > self.pre_intervals:
                    continue
                self.mats[(tenter, tstart)] = MatrixAss.OD(self.origins, self.destinations, self.detectors)

    def from_df(self, df):
        df = df.to_dict(orient="records")
        for r in df:
            k = (r["tenter"], r["tstart"])
            # print(tstart,tenter)
            if k in self.mats:
                od: MatrixAss.OD = self.mats[k]
                od.mat[r["link"], r["od"]] += r["value"]

    def save(self, folder, time_start=0):
        import os

        if not os.path.exists(folder):
            os.makedirs(folder)
        files = glob.glob(os.path.join(folder, "*"))
        for f in files:
            os.remove(f)
        for k, od in self.mats.items():
            tenter, tstart = k
            tenter += time_start
            tstart += time_start
            fname = os.path.join(folder, f"m_{int(tenter)}.csv")
            header = not os.path.exists(fname)

            with open(fname, 'a', newline='') as f:
                writer = csv.writer(f)
                if header:
                    writer.writerow(['tstart', 'link', 'od', 'value'])
                for r in range(od.mat.shape[0]):
                    for ind in range(od.mat.indptr[r], od.mat.indptr[r + 1]):
                        writer.writerow((tstart, r, od.mat.indices[ind], od.mat.data[ind]))

            # fname = os.path.join(folder, f"md_{int(k[0])}_{int(k[1])}.csv")
            # df = pd.DataFrame(data=od.mat.todense()).replace(0,None)
            # df.to_csv(fname, index=False)

    # def _idx(self, tstart, tenter):
    #    return int((tenter+ 1) * tenter / 2 + (tstart + 1) - 1)

    def add(self, o, d, l, t_start, t_enter, flow):
        if l not in self.detectors:
            return
        k = (t_enter, t_start)
        # print(tstart,tenter)
        if k in self.mats:
            mat: MatrixAss.OD = self.mats[k]
            io = self.o2i[o]
            id = self.d2i[d]
            il = self.l2i[l]
            mat[io, id, il] += flow

    def __getitem__(self, key) -> MatrixAss.OD:
        if isinstance(key, tuple):
            return self.mats[key]
        else:
            raise KeyError(f"Key {key} not found in MatrixAss")

    def get_all_matrix_by_tenter(self):
        keys = list(self.mats.keys())
        df = pd.DataFrame(keys, columns=["tenter", "tstart"])
        grp = df.groupby("tenter")
        for t_enter, g in grp:
            ret = []
            for t_start in g["tstart"].unique():
                if (t_enter, t_start) not in self.mats:
                    continue
            ret.append(((t_enter, t_start), self.mats[(t_enter, t_start)].mat))
            yield t_enter, ret

    def set_matrix(self, t_enter, t_start, mat):
        self.mats[(t_enter, t_start)].mat += mat

