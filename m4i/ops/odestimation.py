# -*- coding: utf-8 -*-
"""
Created on Thu Jun 24 23:21:48 2021

@author: andge
"""

# -*- coding: utf-8 -*-
"""
@author: andge
"""
from ..utils.task import task
from .. import ODEstimator
from ..connectors import Loader
from ..matrix import MatrixAss, MatrixODT
from ..graphs import AbstractGraph
import logging
import pandas as pd
import numpy as np
import pdb

@task
class ODEstimation:

    def __init__(self, loader: Loader, assignment, od_estimator):
        self.loader: Loader = loader
        self.ODz2z: MatrixODT = loader.OD
        self.G: AbstractGraph = loader.G
        self.MSA = assignment

        self.fobs = []
        self.links_info = {"ite": [], "flows": [], "counts": []}

    def run(self, max_ite=10, rgap=0.01, msa_max_ite=10, msa_rgap=0.01, msa_k=2, params=None):
        log = logging.getLogger("ODM")
        log.info("Inizializzazione dati")
        # %% associo alle zone i nodi O-D 

        stima = StimaOD(self.loader, self.ODz2z.ods)
        log.info("Inizio")
        start = int(max(self.loader.start, 0))
        end = int(min(self.loader.end, 1440))
        for tstart in range(start, end, int(self.loader.ini.STIMA_OD_TIMESLICE)):
            tend = min(int(tstart + self.loader.ini.STIMA_OD_TIMESLICE), end)
            log.info("Ottimizzazione %s - %s", min2hhmm(tstart), min2hhmm(tend))
            for ite in range(1, max_ite + 1):
                log.info("Ite: %s - Inizio", ite)
                msa = self.MSA(loader=self.loader,
                               max_k=msa_k, max_ite=msa_max_ite, max_rgap=msa_rgap, stima_od=True,
                               tstart=int(tstart - self.loader.ini.STIMA_OD_PRE),
                               tend=int(tend + self.loader.ini.STIMA_OD_PRE),
                               time_slice=int(tend - tstart + 2 * self.loader.ini.STIMA_OD_PRE))
                msa.run()

#                self.df_grouped.to_csv("res_ite_%d.csv"%ite)
                M = msa.matrix_ass
                log.info("Ite: %s - Aggiornamento Matrice", ite)
                od_updated = stima.update(OD=self.ODz2z.ods, M=M, tstart=tstart, tend=tend)
                for t, od in od_updated.items():
                    self.ODz2z[t].mat = self.ODz2z[t].mat * 0 + od.mat
                log.info("Ite: %s - FOB: %s", ite, stima.fob)
                log.info("Ite: %s - ODTOT: %s", ite, sum([od.mat.sum() for od in self.ODz2z.ods.values()]))
        
        msa.max_ite = 1
        msa.run()
        tstart=int(start - self.loader.ini.STIMA_OD_PRE)
        tend=int(end + self.loader.ini.STIMA_OD_PRE)
        self.df_grouped, self.stats, self.vsl_results = msa.sim.agg_results(tstart = tstart*60, tduration = (tend-tstart)*60)
        log.info("Fine")
        return self.ODz2z
    
    def get_sim_results(self):
        return self.df_grouped, self.stats, self.vsl_results 


    def get_results(self):

        if self.ODz2z is None:
            return None
        ret = {"o": [], "d": [], "ts": [], "val": []}

        ori = self.ODz2z.rows
        ori_vec = [len(ori) * [o] for o in ori]
        ori_vec = [o for ov in ori_vec for o in ov]
        d_vec = [o for o in ori for o in ori]

        for t, od in self.ODz2z.ods.items():
            od_flat = list(od.mat.flatten())
            t_vec = len(od_flat) * [t]

            ret["o"] += ori_vec
            ret["d"] += d_vec
            ret["ts"] += t_vec
            ret["val"] += od_flat

        return pd.DataFrame(ret)
