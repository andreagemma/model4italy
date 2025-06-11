from __future__ import annotations
import multiprocessing as mp
import time
from operator import itemgetter
import typing
from typing import List, Dict, Tuple, Any, Union
import itertools
import pdb
import pandas as pd

from libs.utils.tictoc import TicToc
from libs.assignment_models.assignment_model import AssignmentModel
from ..utils.parallel import Parallel
from ..connectors import StateManager
from ..simulators.micro_sim.micro_simulator import MicroSimulator
from ..matrix import MatrixOD, MatrixODT, MatrixAss
from ..graphs import DynamicGraph as Graph, DynamicLink as Link, DynamicNode as Node, DynamicTurn as Turn, DynamicGraphElement as GraphElement
from ..graphs import SPP
from ..graphs import KPathList
from ..connectors import Loader
from ..connectors import Writer
from ..utils.util import min2hhmm
from ..simulators import BaseSimulator
from ..log import Logger
from ..utils import save_dict, load_dict, getsize
from ..utils.ipc import IPC
from ..database import Execution
import numpy as np
from .assignment_model import AssignmentModel

class MSA(AssignmentModel):

    def __init__(
        self,
        loader: Loader = None,
        writer: Writer = None,
        simulator: BaseSimulator = None,
        links_cost: str = "time",
        turns_cost: str = "time",
        nodes_cost: str = "time",
        od_estimation : bool = False,
        save_paths: bool = True,
        save_agg_results: bool = True,
        save_state_graph: bool = False,
        load_state_graph: bool = False,
        save_state_paths: bool = False,
        load_state_paths: bool = False,
        save_ass_matrix: bool = False,
        log: Logger = None,
        ipc: IPC = None,
        max_rel_gap: float = None,
        max_ite: int = None,
        max_k: int = None,
        **kwargs
        ):
        super().__init__(
            loader=loader,
            writer=writer,
            simulator=simulator,
            links_cost=links_cost,
            turns_cost=turns_cost,
            nodes_cost=nodes_cost,
            od_estimation=od_estimation,
            save_paths=save_paths,
            save_agg_results=save_agg_results,
            save_state_graph=save_state_graph,
            load_state_graph=load_state_graph,
            save_state_paths=save_state_paths,
            load_state_paths=load_state_paths,
            save_ass_matrix=save_ass_matrix,
            log=log,
            ipc=ipc,
            max_ite=max_ite,
            max_rel_gap=max_rel_gap,
            **kwargs
        )
        self.max_k = max_k

    def calc_task_steps(self):
        ite_con_cammini = min(self.max_ite, self.max_k)
        ite_senza_cammini = max(0, self.max_ite-ite_con_cammini)
        return super().calc_task_steps() + len(self.global_intervals)* ( ite_con_cammini*2 + ite_senza_cammini)
        
    def run_assignment(self):
        calc_paths = (not self.load_state_graph) or self.m_paths.is_empty()
        k_calculated = self.m_paths.k_paths()
        
        for iteration in range(0, self.max_ite):
            self.iteration = iteration

            self.log.info("Ite: %s - Start of Iteration", iteration)
            
            # precarico i percorsi con 1/k di flusso ciascuno con k pari al numero di percorsi dell'od            
            if calc_paths:
                if k_calculated < self.max_k:
                    self.log.info("Ite: %s - Calculating paths (k=%d)...", iteration, k_calculated + 1)
                    self.calculate_paths(k_calculated)                    
                    k_calculated += 1                
                if iteration < self.max_k:
                    self.log.info("Ite: %s - Preloading (k=%d)...", iteration, k_calculated)
                    for (o, d, t_start, mode), k_paths in self.m_paths.all_kpaths():
                        f = self.ODs[mode][o, d, self.current_time_start + t_start] * self.eq_factors.get(mode, 1)
                        k = len(k_paths)
                        for path in k_paths:
                            path["path_flow"] = f / k                    
                    self.log.info("Ite: %s - Updating network performance...", iteration)
                    self.calc_rgap()
                    self.update_performance()
                    self.update_infos()                    
                    continue
                else:
                    calc_paths = False
            elif iteration == 0:
                self.log.info("Ite: %s - Preloading...", iteration)
                for (o, d, t_start, mode), k_paths in self.m_paths.all_kpaths():
                    f = self.ODs[mode][o, d, self.current_time_start + t_start] * self.eq_factors.get(mode, 1)
                    k = len(k_paths)
                    for path in k_paths:
                        path["path_flow"] = f / k
                self.log.info("Ite: %s - Updating network performance...", iteration)
                
                self.update_performance()                                
                self.update_infos()
                continue


            self.log.info("Ite: %s - MSA flow redistribution...", iteration)

            # % MSA parte 1-1/k
            """
            Decurto 1-1/k di flusso per ogni vecchio percorso
            I nuovi percorsi aumenteranno di 1/k il proprio flusso
            """
            for (o, d, t_start, mode), k_paths in self.m_paths.all_kpaths():
                f = self.ODs[mode][o, d, self.current_time_start + t_start] * self.eq_factors.get(mode, 1)
                if self.loader.ini.MSA_K_BALANCING>0:
                    k = iteration - len(k_paths) + self.loader.ini.MSA_K_BALANCING
                else:
                    k = iteration + 1
                for path in k_paths:
                    path["path_flow"] *= (k - 1) / k


            for (o, d, t_start, mode), k_paths in self.m_paths.all_kpaths():
                if o == d:
                    continue
                f = self.ODs[mode][o, d, self.current_time_start + t_start] * self.eq_factors.get(mode, 1)
                if f > 0:
                    best = min(k_paths, key=lambda path: path["tot_cost"])
                    if self.loader.ini.MSA_K_BALANCING>0:
                        k = iteration - len(k_paths) + self.loader.ini.MSA_K_BALANCING
                    else:
                        k = iteration + 1
                    best["path_flow"] += f / k

            # %
            self.log.info("Ite: %s - Updating network performance...", iteration)
            self.calc_rgap()
            self.update_performance()
            self.update_infos()
            
            if self.test_convergence():
                self.log.info("Convergence reached with relative gap: %s", self.rgap)
                break
            
