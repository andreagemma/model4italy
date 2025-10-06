# -*- coding: utf-8 -*-
"""
Created on Thu Jun 24 23:21:48 2021

@author: andge
"""

# -*- coding: utf-8 -*-
"""
@author: andge
"""
from ..assignment_models.assignment_model import AssignmentModel
from ..simulators import BaseSimulator, MicroSimulator
from .op import OP
from ..connectors import Loader, Writer
from ..matrix import MatrixAss, MatrixODT
from ..graphs import AbstractGraph
from ..assignment_models.msa import MSA
from ..od_estimator import ODEstimatorOffline
from ..utils.util import min2hhmm
import logging
import pandas as pd
import numpy as np
import pdb

class ODEstimation(OP):

    def __init__(self, loader: Loader, writer: Writer, **kwargs):
        super().__init__(loader, writer, **kwargs)
        tstart:int=max(0,self.loader.start-int(self.ini.OD_ESTIMATION_WHISKERS))
        tend:int=min(1440,int(self.loader.end+self.ini.OD_ESTIMATION_WHISKERS))
        timestamps=list(range(tstart,tend,self.ini.DELTA_T))
        #loader.reset(tstart=tstart, tend=tend)        
        loader.load_demand(timestamps=timestamps)
        loader.load_counts(tstart=tstart, tend=tend)
        self.ODz2z: MatrixODT = loader.OD
        self.G: AbstractGraph = loader.G
        self.MSA = MSA

        self.fobs = []
        self.links_info = {"ite": [], "flows": [], "counts": []}

    def run(self):
        self.log.info("Inizializzazione dati")
        # %% associo alle zone i nodi O-D 

        stima = ODEstimatorOffline(loader=self.loader, writer=self.writer, ODSeed=self.ODz2z.ods)
        self.log.info("Inizio")
        start = int(max(self.loader.start, 0))
        end = int(min(self.loader.end, 1440))
        
        self.simulator: BaseSimulator = MicroSimulator(loader=self.loader)
        self.simulator.task_steps = 1
        self.simulator.task_parent = self
        self.simulator.task_weight = 10
        tstarts = list(range(start, end, int(self.ini.OD_ESTIMATION_MSA_TIMESLICE)))
        self.task_set_steps(len(tstarts) * self.ini.OD_ESTIMATION_MAX_ITE)

        for tstart in tstarts:
            tend = min(int(tstart + self.ini.OD_ESTIMATION_MSA_TIMESLICE), end)
            self.log.info("Analyzing %s - %s...", min2hhmm(tstart), min2hhmm(tend))
            for ite in range(1, self.ini.OD_ESTIMATION_MAX_ITE + 1):
                self.task_step_done(f"t: {tstart}-{tend} ite: {ite} - Start")
                msa: AssignmentModel = self.MSA(
                    task_parent = self,
                    loader = self.loader,
                    writer = self.writer,
                    max_k=self.ini.OD_ESTIMATION_MSA_K, 
                    max_ite=self.ini.OD_ESTIMATION_MSA_MAX_ITE, 
                    max_rgap=self.ini.OD_ESTIMATION_MSA_RGAP, 
                    start=tstart - self.ini.OD_ESTIMATION_WHISKERS,
                    end = tend + self.ini.OD_ESTIMATION_WHISKERS,
                    time_slice=tend - tstart + 2 * self.ini.OD_ESTIMATION_WHISKERS,
                    od_estimation=True,
                    simulator=self.simulator,
                    save_state_graph=False,
                    load_state_graph=False,
                    save_state_paths=False,
                    load_state_paths=False,
                    save_ass_matrix=False,
                    save_paths=False,
                    load_off_line_paths=self.ini.OD_ESTIMATION_USE_OBSERVED_PATHS,                
                    save_agg_results=False,
                )
                n_steps = msa.calc_task_steps()
                if n_steps:
                    msa.task_set_steps(n_steps)                
                msa.run()

#                self.df_grouped.to_csv("res_ite_%d.csv"%ite)
                M = msa.ass_matrix
                self.log.info("Ite: %s - Aggiornamento Matrice", ite)
                od_updated = stima.update(OD=self.ODz2z.ods, M=M, tstart=tstart, tend=tend)
                for t, od in od_updated.items():
                    self.ODz2z[t].mat = self.ODz2z[t].mat * 0 + od.mat
                self.log.info("Ite: %s - FOB: %s", ite, stima.fob)
                self.log.info("Ite: %s - ODTOT: %s", ite, sum([od.mat.sum() for od in self.ODz2z.ods.values()]))
        
        msa.max_ite = 1
        msa.run()
        tstart=int(start - self.loader.ini.OD_ESTIMATION_WHISKERS)
        tend=int(end + self.loader.ini.OD_ESTIMATION_WHISKERS)
        #self.df_grouped, self.stats, self.vsl_results = msa.sim.agg_results(tstart = tstart*60, tduration = (tend-tstart)*60)
        self.log.info("Fine")
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
