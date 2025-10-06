from __future__ import annotations
import multiprocessing as mp
import time
from operator import itemgetter
import typing
from typing import List, Dict, Tuple, Any, Union
import itertools
import pdb
import pandas as pd
from ..utils.tictoc import TicToc
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
from ..base_m4i_model import BaseM4IModel
import numpy as np

class AssignmentModel(BaseM4IModel):

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
        save_agg_results_stats: bool = True,
        save_trace_results: bool = True,
        save_signal_results: bool = True,
        save_state_graph: bool = False,
        load_state_graph: bool = False,
        load_state_paths: bool = False,
        save_state_paths: bool = False,
        save_ass_matrix: bool = False,
        load_off_line_paths: bool = True,
        off_line_paths: str = "",
        ipc: IPC = None,
        max_rel_gap: float = None,
        max_ite: int = None,
        start: int = None,
        end: int = None,
        max_timeslice:int = None,
        **kwargs
        ):
        super().__init__(loader=loader, writer=writer, ipc=ipc)
        self.loader.load_from_ipc(ipc=self.ipc)
        self.max_ite: int = max_ite
        self.max_rel_gap: float = max_rel_gap

        self.global_t_start: int = max(0, self.loader.start if start is None else start)
        self.global_t_end: int = min(1440, self.loader.end if end is None else end)
        self.global_time_slice: int = int(loader.ini.MSA_MAX_TIMESLICE if max_timeslice is None else max_timeslice)
        self.global_time_slice: int = int(min(self.global_t_end-self.global_t_start,self.global_time_slice))

        self.delta_t = self.loader.delta_t

        self.global_intervals = list(range(self.global_t_start, self.global_t_end, self.global_time_slice))
        self.global_num_intervals = len(self.global_intervals)

        self.simulator: BaseSimulator = simulator

        self.links_cost = links_cost
        self.turns_cost = turns_cost
        self.nodes_cost = nodes_cost
        
        self.calc_ass_matrix = od_estimation
        
        self.save_paths = save_paths and self.writer.has_write_paths()
        self.save_agg_results = save_agg_results and self.writer.has_write_agg_results() and self.simulator is not None
        self.save_agg_results_stats = save_agg_results_stats and self.writer.has_write_agg_results_stats() and self.simulator is not None
        self.save_trace_results = save_trace_results and self.writer.has_write_trace_results() and self.simulator is not None
        self.save_signal_results = save_signal_results and self.writer.has_write_signal_results() and self.simulator is not None
        self.state_manager = StateManager(self.loader.parser)

        self.save_state_ass_matrix = save_ass_matrix and self.state_manager.has_write_state() and self.calc_ass_matrix
        self.save_state_graph = save_state_graph and self.state_manager.has_write_state()
        self.load_state_graph = load_state_graph and self.state_manager.has_write_state()
        self.save_state_paths = save_state_paths and self.state_manager.has_write_state()
        self.load_state_paths = load_state_paths and self.state_manager.has_write_state()
        if not off_line_paths:
            self.off_line_paths = "params.fcd_paths_clustered"
        else:
            self.off_line_paths = off_line_paths
        self.load_off_line_paths = load_off_line_paths and self.loader.has(self.off_line_paths)
        

        self.OD: MatrixODT = None
        self.ODs: dict[str, MatrixODT] = None
        self.G: Graph = None
        self.G_copy: Graph = None
        self.modes = None

        self.origins: List[int] = None
        self.destinations: List[int] = None

        self.ass_matrix: MatrixAss = None

        self.eq_factors: dict[str, float] = None

        self.infos: dict = []
        self.m_paths: KPathList = None
        self.tic_end: int = None

        self.current_time_start: int = None
        self.current_time_end: int = None
        self.real_time_start: int = None
        self.real_time_end: int = None
        self.current_num_intervals: int = None
        self.current_i_start: int = None
        self.current_i_end: int = None
        self.current_t_starts: List[int] = None
        self.interval:int = None    
        self.iteration:int = None
        self.rgap: float = 1E308
        self.use_prelaoded_paths: bool = False

        self.tot_dom: float = None
        self.tot_tt: float = None
        self.tot_tt_current: float = None

    def calc_task_steps(self):
        n_steps = 2 + len(self.global_intervals) * 5
        if self.calc_ass_matrix:
            n_steps += len(self.global_intervals)
        self.task_set_steps(n_steps)          
        return n_steps
    
    def run(self):
        # self.log.info(f"occupazione graph: {getsize(self.G)/1024/1024}MB")
        # self.log.info(f"occupazione od: {getsize(self.od)/1024/1024}MB")      
        self.task_step_done("Loading parameters")

        self.OD: MatrixODT = self.loader.OD
        self.ODs: dict[str, MatrixODT] = self.loader.ODs
        self.G: Graph = self.loader.G
        self.G_copy: Graph = self.loader.G.copy()
        self.modes = set(self.ODs.keys())
        self.origins: List[int] = self.loader.origins
        self.destinations: List[int] = self.loader.destinations
        self.eq_factors: dict[str, float] = {mode: params.get("eq_factor", 1) for mode, params in self.loader.modes.items()}        

        if self.save_state_graph:
            self.log.info("Saving state (Graph)...")
            self.state_manager.write_state(self.G, "graph", mode="w")
            self.log.info("Saved state (Graph)")

        self.tic: TicToc = TicToc(logger=self.log)

        start = min2hhmm(self.global_t_start)
        end = min2hhmm(self.global_t_end)
        duration = self.global_t_end - self.global_t_start
        self.log.info(f"""Simulation Parameters: start: {start} end: {end} duration: {duration} time_slice: {self.global_time_slice} delta_t: {self.delta_t}""")

        if len(self.global_intervals) > 1:
            self.log.info(f"Simulation will be splitted into {len(self.global_intervals)} intervals: {self.global_intervals}")
        
        for self.interval, time_start in enumerate(self.global_intervals):
            self.current_time_start = time_start
            self.real_time_start = self.current_time_start
            if self.global_num_intervals > 1:
                self.current_time_start -= self.loader.ini.MSA_PRELOAD
                self.current_time_start = max([self.current_time_start, self.global_t_start, 0])             
            self.current_time_end = min(self.real_time_start + self.global_time_slice,1440)
            self.real_time_end = self.current_time_end
            if self.global_num_intervals > 1:
                self.current_time_end += self.loader.ini.MSA_POSTLOAD
                self.current_time_end = min([self.current_time_end, self.global_t_end, 1440])

                
            self.loader.dparams["current_start_time"] = self.real_time_start
            self.loader.dparams["current_end_time"] = self.real_time_end
            rs = min2hhmm(self.real_time_start)
            re = min2hhmm(self.real_time_end)
            cs = min2hhmm(self.current_time_start)
            ce = min2hhmm(self.current_time_end)
            gs = min2hhmm(self.global_t_start)
            ge = min2hhmm(self.global_t_end)
            
            self.task_step_done(f"{cs}-{ce} - Starting simulation")

            if self.global_num_intervals > 1:     
                self.log.info(f"Simulating ({self.interval+1}/{self.global_num_intervals}) {rs}-{re} (Original: {cs}-{ce} Global {gs}-{ge}) ...")
            else:
                self.log.info(f"Simulating {rs}-{re} (Original: {cs}-{ce} Global {gs}-{ge}) ...")
                self.log.info(f"Simulating {cs}-{ce} ...")           
            
            self.task_step_done(f"{cs}-{ce} - Initialize simulation")
            if self.simulator:
                self.simulator.initialize_assignment(self.current_time_start, self.current_time_end)

            self.task_step_done(f"{cs}-{ce} - Running simulation")
            self.run_internal_step()

            self.task_step_done(f"{cs}-{ce} - Finalizing simulation")
            if self.interval < self.global_num_intervals - 1 or self.save_agg_results or self.save_paths:
                self.simulator.finalize_assignment(self.current_time_start, self.current_time_end)

            if self.calc_ass_matrix:
                self.ass_matrix: MatrixAss = MatrixAss(self.loader, self.current_num_intervals)
                self.task_step_done(f"{cs}-{ce} - Calculating Assignment Matrix...")
                self.calculate_ass_matrix()
            else:
                self.ass_matrix = None

            self.task_step_done(f"{cs}-{ce} - Saving results")
            self.write_stats()
            self.write_state_paths()
            self.write_state_ass_matrix()
            self.write_paths()            
            self.write_agg_results()
            self.write_agg_results_stats()
            self.write_trace_results()
            self.write_signal_results()
            
            
            
            self.G = self.G_copy.copy()
        self.task_step_done("Finish")
        self.task_finish()

    def write_stats(self):
        try:
            if self.writer.has("params.statistics"):
                self.log.info("Saving stats...")
                df = pd.DataFrame.from_dict(self.infos)
                mode = None if self.interval==0 else "a"
                self.writer.write(df,"params.statistics", mode=mode)
        except Exception as e:
            self.log.error("Failed to save paths:", exc_info=e, stack_info=True)     

    def write_paths(self):
        try:
            if self.save_paths:
                self.log.info("Saving paths...")
                saved = True
                paths = self.get_paths_dataframe()
                mode = None if self.interval==0 else "a"
                saved = self.writer.write_paths(paths, mode=mode, crs=self.loader.ini.CRS)
                paths = None   
                if saved:
                    self.log.info("Saved paths")
                else:
                    self.log.warning("Failed to save paths")                                         
        except Exception as e:
            self.log.error("Failed to save paths:", exc_info=e, stack_info=True)        

    def write_state_paths(self):
        try:
            if self.save_state_paths:
                self.log.info("Saving state (Paths)...")
                for t in range(self.real_time_start,self.real_time_end,self.delta_t):
                    paths = list(self.m_paths.get_paths_by_t(t))
                    self.state_manager.write_state(paths, "paths", partition=f"t={t}")
                paths = None                                                        
                self.log.info("Saved state")
        except Exception as e:
            self.log.error("Failed to save state:", exc_info=e, stack_info=True)        

    def write_agg_results(self):
        try:                
            if self.save_agg_results:
                self.log.info("Saving aggregated results...")
                saved = True
                df=self.get_aggregated_results_dataframe()
                ds_t = (pd.to_numeric(df["time"]) / 1000000000 % 86400 ) / 60
                if df["time"].dt.tz is None:
                    df["time"] = df["time"].dt.tz_localize(self.parser.ini.TZ_LOCAL)  
                mode = None if self.interval==0 else "a"
                df["t"] = ds_t.astype("Int64")
                saved = self.writer.write_agg_results(df, crs=self.loader.ini.CRS, mode=mode)
                                
                if saved:                    
                    self.log.info("Saved aggregated results")
                else:
                    self.log.warning("Failed to save aggregated results")
        except Exception as e:
            self.log.error("Failed to save aggregated results:", exc_info=e, stack_info=True)

    def write_agg_results_stats(self):
        try:                
            if self.save_agg_results_stats:
                self.log.info("Saving aggregated stats...")
                saved = True
                df=self.get_aggregated_results_stats_dataframe()
                mode = None if self.interval==0 else "a"
                saved = self.writer.write_agg_results_stats(df, mode=mode, crs=self.loader.ini.CRS)
                                
                if saved:                    
                    self.log.info("Saved aggregated stats")
                else:
                    self.log.warning("Failed to save aggregated stats")
        except Exception as e:
            self.log.error("Failed to save aggregated stats:", exc_info=e, stack_info=True)

    def write_trace_results(self):
        try:                
            if self.save_trace_results:
                self.log.info("Saving trace results...")
                saved = True
                df=self.get_trace_results_dataframe()
                ds_t = (pd.to_numeric(df["time"]) / 1000000000 % 86400 ) / 60
                if df["time"].dt.tz is None:
                    df["time"] = df["time"].dt.tz_localize(self.parser.ini.TZ_LOCAL)  
                mode = None if self.interval==0 else "a"
                df["t"] = ds_t.astype("Float32")
                saved = self.writer.write_trace_results(df, mode=mode, crs=self.loader.ini.CRS)
                                
                if saved:                    
                    self.log.info("Saved trace results")
                else:
                    self.log.warning("Failed to save trace results")
        except Exception as e:
            self.log.error("Failed to save trace results:", exc_info=e, stack_info=True)

    def write_signal_results(self):
        try:                
            if self.save_signal_results:
                self.log.info("Saving signal results...")
                saved = True
                df=self.get_signal_results_dataframe()
                ds_t = (pd.to_numeric(df["time"]) / 1000000000 % 86400 ) / 60
                if df["time"].dt.tz is None:
                    df["time"] = df["time"].dt.tz_localize(self.parser.ini.TZ_LOCAL)  
                mode = None if self.interval==0 else "a"
                df["t"] = ds_t.astype("Float32")
                saved = self.writer.write_signal_results(df, mode=mode, crs=self.loader.ini.CRS)
                                
                if saved:                    
                    self.log.info("Saved trace results")
                else:
                    self.log.warning("Failed to save trace results")
        except Exception as e:
            self.log.error("Failed to save trace results:", exc_info=e, stack_info=True)

    def write_state_ass_matrix(self):
        try:
            if self.save_state_ass_matrix:
                self.log.info("Saving state (Assignment Matrix)...")

                for t_enter, mat in self.ass_matrix.get_all_matrix_by_tenter():
                    self.state_manager.write_state(mat, "ass_matrix", mode="w", partition=f"t_enter={t_enter}")
                mat = None                                                        
                self.log.info("Saved state")
        except Exception as e:
            self.log.error("Failed to save state:", exc_info=e, stack_info=True) 
            

    def run_internal_step(self):
        self.current_i_start = int(self.current_time_start / self.delta_t)
        self.current_i_end = int(self.current_time_end / self.delta_t)
        self.current_num_intervals = self.current_i_end - self.current_i_start
        self.current_t_starts = [self.delta_t * i for i in range(self.current_num_intervals)]

        self.G.resize_attributes(new_total_time=self.current_num_intervals * self.delta_t, offset=self.current_i_start * self.delta_t)
        self.G["t_base"] = self.current_time_start
        self.m_paths = KPathList()
        if self.load_state_paths:
            self.log.info("Loading state (Paths)...")            
            for t_start, t in enumerate(range(self.current_time_start,self.current_time_end,self.delta_t)):
                paths = self.state_manager.load_state("paths", partition=f"t={t}")
                if paths is None:
                    self.m_paths = KPathList()
                    self.log.info("No paths found")
                    calc_paths = True
                    break
                else:
                    for path in paths:
                        path["t"] = t
                        path["t_start"] = t_start * self.delta_t
                        path["t_base"] = t-(t_start* self.delta_t)
                        self.m_paths.add_path(path)
            self.log.info("Loaded state (Paths)")
        if self.load_off_line_paths:
            self.log.info("Loading off-line paths...")
            try:
                tot_paths = self.loader.load(self.off_line_paths,filters=[("day_type","==",self.parser.get("day_type_simulation"))], from_output=True)
                for t_start, t in enumerate(range(self.current_time_start,self.current_time_end,self.delta_t)):
                    df_paths = tot_paths.query("t >= @t_start and t< @t").reset_index(drop=True)
                    if df_paths is not None and not df_paths.empty:
                        df_paths["t"] = t
                        df_paths["t_start"] = t_start * self.delta_t
                        df_paths["t_base"] = t - (t_start * self.delta_t)                        
                        df_paths.astype({"t": "Int64", "t_start": "Int64", "t_base": "Int64", "day_type": "str"})                        
                        df_no_mode = df_paths[df_paths["mode"].isna()]
                        for mode in self.modes:                
                            tmp = df_no_mode.copy()
                            tmp["mode"] = mode
                            df_paths=pd.concat([df_paths, tmp], ignore_index=True, sort=False)
                        df_paths.dropna(subset=["mode"], inplace=True)
                        df_paths = df_paths[df_paths["source"].isin(self.loader.origins) & df_paths["target"].isin(self.loader.destinations)]

                        self.m_paths.add_from_dataframe(df_paths)
                    
            except Exception as e:
                self.log.error("Failed to load off-line paths:", exc_info=e, stack_info=True)
            self.log.info("Loaded off-line paths")
            
        if self.simulator:
            self.simulator.set_paths(self.m_paths)
                            
        # %
        self.log.info("Initialization")

        # % inizializzo i flusso
        def reset_links(l: Link):
            l.reset_attribute(name="time", value=l["t0"])
            l.reset_attribute(name="flow", value=0)

        self.G.apply_links(reset_links)
        self.rgap = None
        self.tot_dom = None
        self.tot_tt = None
        self.tot_tt_current = None

        self.run_assignment()
        
        if self.rgap is not None and self.rgap < self.max_rel_gap:
            self.log.info("Convergence reached")
        else:
            self.log.info("Assignment completed for maximum number of iterations")

    def run_assignment(self):
        raise NotImplementedError("This method should be implemented in subclasses")
        calc_paths = (not self.load_state_graph) # or self.m_paths.is_empty()
        k_calculated = 0
        
        for iteration in range(0, self.max_ite):
            self.iteration = iteration

            self.log.info("Ite: %s - Start of Iteration", iteration)
            
            # precarico i percorsi con 1/k di flusso ciascuno con k pari al numero di percorsi dell'od            
            if calc_paths:
                if k_calculated < self.max_k:
                    self.log.info("Ite: %s - Calculating paths (k=%d)...", iteration, k_calculated + 1)
                    self.calculate_paths()                    
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
            
    def test_convergence(self):
        if self.iteration > 1 and self.rgap is not None:
            if self.rgap < self.max_rel_gap:
                return True
            else:
                self.log.info("Convergence not reached, relative gap: %s", self.rgap)
        return False
    def calc_rgap(self):
        if self.iteration > 1:
            self.tot_tt_current = 0
            for (o, d, t_start, mode), k_paths in self.m_paths.all_kpaths():
                if o == d:
                    continue
                f = self.ODs[mode][o, d, self.current_time_start + t_start] * self.eq_factors.get(mode, 1)
                if f > 0:
                    best = min(k_paths, key=lambda path: path["tot_cost"])
                    self.tot_tt_current += f * best["tot_cost"]            
            
            self.rgap = abs(self.tot_tt - self.tot_tt_current) / self.tot_tt_current if self.tot_tt_current > 0 else 0
            self.log.info("Ite: %s - Relative Gap on route times: %s", self.iteration, self.rgap)  

    def update_infos(self):
        info = {
            "global_t_start": self.global_t_start,
            "global_t_end": self.global_t_end,
            "interval": self.interval,
            "real_time_start": self.real_time_start,
            "real_time_end": self.real_time_end,
            "iteration": self.iteration,
            "current_time_start": self.current_time_start,
            "current_time_end": self.current_time_end,
            "rgap_time": None,
            "tot_tt": None,
            "tot_tt_current": None,
            "tot_domand": None,
            "tot_vehicles": None,
            "cpu_time": None,
            "total_paths": self.m_paths.n_paths(),
            "unique_paths": self.m_paths.n_unique_paths(),
            "k_paths": self.m_paths.k_paths(),
            }
        info["rgap_time"] = self.rgap
        self.tot_dom = sum([path["path_flow"] for path in self.m_paths.all_paths()])
        self.tot_tt = sum([path["tot_cost"] * path["path_flow"] for path in self.m_paths.all_paths()])
        self.tot_tt_current = self.tot_tt if self.tot_tt_current is None else self.tot_tt_current
        info["tot_tt"] = self.tot_tt
        info["tot_tt_current"] = self.tot_tt_current
        info["tot_domand"] = self.tot_dom
        if self.simulator and hasattr(self.simulator, "vehs"):
            if self.simulator.vehs is not None:
                tot_vehicles = len(self.simulator.vehs)
                info["tot_vehicles"] = tot_vehicles      
        et = self.tic.elapsed_time()
        info["cpu_time"] = et.to_s
        self.infos.append(info)
        self.write_stats()
        
        self.log.info("Ite: %s - Total Flows: %s", self.iteration, info["tot_domand"])
        self.log.info("Ite: %s - Last Veh*h: %s", self.iteration, info["tot_tt_current"] / 60)
        self.log.info("Ite: %s - Total Veh*h: %s", self.iteration, info["tot_tt"] / 60)
        self.log.info("Ite: %s - Total Paths: %s", self.iteration, info["total_paths"])
        self.log.info("Ite: %s - Unique Paths: %s", self.iteration, info["unique_paths"])
        self.log.info("Ite: %s - K Paths: %s", self.iteration, info["k_paths"])

        if info["tot_vehicles"] is not None:
            self.log.info("Ite: %s - Moving Vehicles: %s", self.iteration, info["tot_vehicles"])
        
        

    def calculate_paths(self):
        self.task_step_done(f"{min2hhmm(self.current_time_start)}-{min2hhmm(self.current_time_end)} - Iteration: {self.iteration}/{self.max_ite} - Calculating paths")
        n_cpu = self.loader.ini.MSA_SPP_NUMCPUS        

        ret = KPathList()

        ret = SPP.multiple_paths(graph=self.G, 
                                 origins=self.origins,
                                 targets=self.destinations,
                                 t_starts=self.current_t_starts,
                                 modes=self.modes,
                                 t_base=self.current_time_start,
                                 link_cost=self.links_cost, 
                                 turn_cost=self.turns_cost, 
                                 node_cost=self.nodes_cost,
                                 n_workers=n_cpu)

        self.log.info("Ite: %s - Paths calculated", self.iteration)        
        self.m_paths.merge(ret)
        
        #print(getsize(self.m_paths)/1024/1024,len(self.m_paths["paths"]),len(self.m_paths["ull"]))

    def update_performance(self):
        self.task_step_done(f"{min2hhmm(self.current_time_start)}-{min2hhmm(self.current_time_end)} - Iteration: {self.iteration}/{self.max_ite} - Updating performance")
        def reset(l: Link):
            l.reset_attribute(name="flow", value=0)

        self.G.apply_links(reset)

        update_costs = (self.iteration != self.max_ite - 1) or (self.save_paths and self.writer.has_write_paths())
        # aggiorno i tempi nel grafo
        if self.simulator:
            self.simulator.update_performance(
                tstart=self.current_time_start,
                tend=self.current_time_end,
            )        
            #print(getsize(self.simulator)/1024/1024)
            
            if isinstance(self.simulator, MicroSimulator):
                if update_costs:
                    self.update_paths_costs(update_nodes=False, update_links=True, update_turns=False)
            else:
                if update_costs:
                    self.update_paths_costs(update_nodes=self.nodes_cost is not None, update_links=self.links_cost is not None, update_turns=self.turns_cost is not None)
        else:
            if update_costs:
                self.update_paths_costs(update_nodes=self.nodes_cost is not None, update_links=self.links_cost is not None, update_turns=self.turns_cost is not None)

    def update_paths_costs(self, update_nodes=True, update_links=True, update_turns=True):
        self.log.info("Ite: %s - Updating costs...", self.iteration)
        for path in self.m_paths.all_paths():
            if len(path["links"]) == 0:
                continue
            cost = 0
            prev_l = None
            for i, l_idx in enumerate(path.get_links()):
                t = path["t"] + cost
                l = self.G.get_link(l_idx)
                if update_turns and i > 0:
                    turn = self.G.get_turn(prev_l["idx"], l["idx"])
                    if turn:
                        cost += turn.get_value(self.turns_cost, t=t, delta_t=self.delta_t, graph=self.G, default=0)
                if update_nodes:
                    cost += self.G.get_node(l["i"]).get_value(name=self.nodes_cost, t=t, in_link=prev_l, out_link=l, graph=self.G, default=0)
                if update_links:
                    cost += l.get_value(name=self.links_cost, t=t, delta_t=self.delta_t, in_link=prev_l, graph=self.G, default=0)
                prev_l = l

            path["tot_cost"] = cost


    def calculate_ass_matrix(self):
        self.log.info ("Assignment matrix calculation...")

        def fn_calc_mat_ass(tasks, eq_factors, G, links_cost, nodes_cost, turns_cost, current_time_start, OD, detectors):
            ret = []
            for (source, target, t_start, mode), paths in tasks:
                for path in paths:
                    f = OD[source, target, current_time_start + t_start] * eq_factors.get(mode, 1)
                    if f <= 0:
                        continue
                    costs = tuple(path.get_costs(G, links_cost=links_cost, nodes_cost=nodes_cost, turns_cost=turns_cost))
                    links = path.get_links()
                    for t, l_idx in zip(costs, links):  # [t for t in zip(idxs, links) if t[1] in self.matrix_ass.detectors]:   
                        if l_idx in detectors:             
                            ret.append((source, target, l_idx, t_start, t, path["path_flow"] / f))
            return ret        
        tasks = list(self.m_paths.all_kpaths()) 
        
        n_workers = 1
        if n_workers>1:
            for params in Parallel.execute(fn_calc_mat_ass, tasks, n_workers=n_workers, 
                                        eq_factors=self.eq_factors, G=self.G, 
                                        links_cost=self.links_cost, nodes_cost=self.nodes_cost, turns_cost=self.turns_cost,
                                        current_time_start=self.current_time_start, OD=self.OD, detectors=self.ass_matrix.detectors):
                for (source, target, l, t_start, t, flow) in params:
                    t_start = int(np.floor(t_start))
                    t_enter = int(t_start + np.floor(t/self.delta_t))
                    self.ass_matrix.add(source, target, l=l, t_start=t_start, t_enter=t_enter, flow=flow)
        else:
            for (source, target, l, t_start, t, flow) in fn_calc_mat_ass(tasks, 
                                        eq_factors=self.eq_factors, G=self.G, 
                                        links_cost=self.links_cost, nodes_cost=self.nodes_cost, turns_cost=self.turns_cost,
                                        current_time_start=self.current_time_start, OD=self.OD, detectors=self.ass_matrix.detectors):
                    t_start = int(np.floor(t_start))
                    t_enter = int(t_start + np.floor(t/self.delta_t))
                    self.ass_matrix.add(source, target, l=l, t_start=t_start, t_enter=t_enter, flow=flow)
        self.log.info ("Assignment matrix calculated")

    def get_trace_results_dataframe(self):
        if self.simulator is None:
            return None
<<<<<<< HEAD
        res = self.simulator.agg_results(self.global_t_start, self.global_t_end, agg_int=self.loader.ini.OUTPUT_AGG_INT)
        trace_res = self.simulator.get_trace_res(self.global_t_start, self.global_t_end)
        sign_res = self.simulator.get_signalized_res(self.global_t_start, self.global_t_end)
        stats = self.simulator.agg_stats(self.global_t_start, self.global_t_end)
=======
        return self.simulator.get_trace_res(self.global_t_start, self.global_t_end)

    def get_signal_results_dataframe(self):
        if self.simulator is None:
            return None
        return self.simulator.get_signalized_res(self.global_t_start, self.global_t_end)

    def get_aggregated_results_stats_dataframe(self):
        if self.simulator is None:
            return None
        return self.simulator.agg_stats(self.global_t_start, self.global_t_end)

    def get_aggregated_results_dataframe(self):
        if self.simulator is None:
            return None
        #from ..utils import ST_Multi
        #import geopandas as gpd

        #G = self.loader.G
        #results = self.simulator.agg_results(self.global_t_start, self.global_t_end, agg_int=self.loader.ini.OUTPUT_AGG_INT)
        #id_links = results["id_link"].unique()
        #df_geometry = pd.DataFrame([[id_link,ST_Multi(G.get_link(id_link).get_value("geometry"))] for id_link in id_links], columns=["id_link","geometry"])     
        #results = results.merge(df_geometry, on="id_link").merge(self.loader.df_links[["id_link", "length", "lanes"]], on="id_link")
        #results["q_length"] = (results["max_q"] / results["lanes"]) * self.ini.CAR_LENGTH / results["length"] * 100
        #results = gpd.GeoDataFrame(results, geometry="geometry" ,crs=self.loader.ini.CRS_CALC)
        #return results
        res = self.simulator.agg_results(self.global_t_start, self.global_t_end, agg_int=self.loader.ini.OUTPUT_AGG_INT)
>>>>>>> fdca169cce56362b2a49e34baab62fad6758cf32
        


        #id_links = results["id_link"].unique()
        #df_geometry = pd.DataFrame([[id_link,ST_Multi(G.get_link(id_link).get_value("geometry"))] for id_link in id_links], columns=["id_link","geometry"])
        #results = results.merge(df_geometry, on="id_link")
        #results = gpd.GeoDataFrame(results, geometry="geometry" ,crs=self.loader.ini.CRS_CALC)
<<<<<<< HEAD
        return res
=======
        return res		
>>>>>>> fdca169cce56362b2a49e34baab62fad6758cf32
        
    def get_paths_dataframe(self, t=None):
        from shapely import MultiLineString
        from ..utils import multi_line_to_line
        import geopandas as gpd

        G = self.loader.G

        if t:
            results: pd.DataFrame = pd.DataFrame(self.m_paths.get_paths_by_t(t))
        else:
            results: pd.DataFrame = pd.DataFrame(self.m_paths.all_paths())
        l = next(G.get_all_links())
        for geom in ("geom","geometry"):
            if geom in l:
                results[geom]=[MultiLineString([multi_line_to_line(G.get_link(l_idx).get_value(geom)) for l_idx in links]) for links in results["links"]]
                results = gpd.GeoDataFrame(results, geometry=geom ,crs=self.loader.ini.CRS_CALC)
                break

        return results
        