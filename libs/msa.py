from __future__ import annotations
from libs import Logger
import multiprocessing as mp
import time
from operator import itemgetter
import typing
from typing import List, Dict, Tuple, Any, Union
import itertools
import pdb
import pandas as pd

from libs.writers.state_manager import StateManager
from libs.matrix_od.matrix_ass import MatrixAss
from libs.simulators.micro_sim.sim import Simulator
from libs.simulators.micro_sim.micro_simulator import MicroSimulator
from .matrix_od import MatrixOD, MatrixODT, MatrixAss
from .graphs import DynamicGraph as Graph, DynamicLink as Link, DynamicNode as Node, DynamicTurn as Turn, DynamicGraphElement as GraphElement
from .graphs import SPP
from .graphs import KPathList
from .loaders import BaseLoader
from .writers import BaseWriter
from .utils.util import min2hhmm
from . import BaseSimulator
from .utils import save_dict, load_dict, getsize


class MSA:

    def __init__(
        self,
        loader: BaseLoader = None,
        writer: BaseWriter = None,
        max_k: int = 3,
        max_ite: int = 10,
        max_rel_gap: float = 0,
        simulator: BaseSimulator = None,
        links_cost: str = "time",
        turns_cost: str = "time",
        nodes_cost: str = "time",
        od_estimation : bool = True,
        save_paths: bool = True,
        save_agg_results: bool = True,
        save_state_graph: bool = False,
        load_state_graph: bool = False,
        load_state_paths: bool = False,
        save_state_paths: bool = False
    ):
        self.log = Logger.getLogger("MSA", execution_id=loader.dparams.get("execution_id"))
        self.loader: BaseLoader = loader
        self.writer: BaseWriter = writer
        self.max_k: int = max_k
        self.max_ite: int = max_ite
        self.max_rel_gap: float = max_rel_gap

        self.global_t_start: int = max(0, self.loader.start)
        self.global_t_end: int = min(1440, self.loader.end)
        self.global_time_slice: int = int(min(self.global_t_end-self.global_t_start,loader.ini.MSA_MAX_TIMESLICE))

        self.delta_t = self.loader.delta_t

        self.global_intervals = list(range(self.global_t_start, self.global_t_end, self.global_time_slice))
        self.global_num_intervals = len(self.global_intervals)

        self.simulator: BaseSimulator = simulator

        self.links_cost = links_cost
        self.turns_cost = turns_cost
        self.nodes_cost = nodes_cost

        self.save_paths = save_paths and self.writer.has_write_paths()
        self.save_agg_results = save_agg_results and self.writer.has_write_agg_results() and self.simulator is not None
        self.state_manager = StateManager(params=loader.dparams, settings=loader.ini, loader=loader)
        self.save_state_graph = save_state_graph and self.state_manager.has_write_state()
        self.load_state_graph = load_state_graph and self.state_manager.has_write_state()
        self.save_state_paths = save_state_paths and self.state_manager.has_write_state()
        self.load_state_paths = load_state_paths and self.state_manager.has_write_state()

        self.OD: MatrixODT = self.loader.OD
        self.ODs: dict[str, MatrixODT] = self.loader.ODs
        self.G: Graph = self.loader.G
        self.G_copy: Graph = self.loader.G.copy()
        self.modes = set(self.ODs.keys())

        self.origins: List[int] = self.loader.origins
        self.destinations: List[int] = self.loader.destinations

        self.od_estimation = od_estimation
        self.ass_matrix: MatrixAss = None

        self.eq_factors: dict[str, float] = {mode: params.get("eq_factor", 1) for mode, params in self.loader.modes.items()}        

        self.infos: dict = []
        self.m_paths: KPathList = None
        self.t_start: int = None
        self.t_end: int = None

        self.current_time_start: int = None
        self.current_time_end: int = None
        self.real_time_start: int = None
        self.real_time_end: int = None
        self.current_num_intervals: int = None
        self.current_i_start: int = None
        self.current_i_end: int = None
        self.current_t_starts: List[int] = None
        

    def run(self):
        # self.log.info(f"occupazione graph: {getsize(self.G)/1024/1024}MB")
        # self.log.info(f"occupazione od: {getsize(self.od)/1024/1024}MB")
        if self.save_state_graph:
            self.log.info("Saving state (Graph)...")
            self.state_manager.write_state(self.G, "graph", mode="w")
            self.log.info("Saved state (Graph)")

        self.t_start = time.time()
        start = min2hhmm(self.global_t_start)
        end = min2hhmm(self.global_t_end)
        duration = self.global_t_end - self.global_t_start
        self.log.info(f"""Simulation Parameters: start: {start} end: {end} duration: {duration} time_slice: {self.global_time_slice} delta_t: {self.delta_t}""")

        if len(self.global_intervals) > 1:
            self.log.info(f"Simulation will be splitted into {len(self.global_intervals)} intervals: {self.global_intervals}")
        
        for interval, time_start in enumerate(self.global_intervals):
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
            

            if self.global_num_intervals > 1:     
                self.log.info(f"Simulating ({interval+1}/{self.global_num_intervals}) {rs}-{re} (Original: {cs}-{ce} Global {gs}-{ge}) ...")
            else:
                self.log.info(f"Simulating {rs}-{re} (Original: {cs}-{ce} Global {gs}-{ge}) ...")
                self.log.info(f"Simulating {cs}-{ce} ...")           
            
            if self.simulator:
                self.simulator.initialize_assignment(self.current_time_start, self.current_time_end)

            self.run_msa()

            if interval < self.global_num_intervals - 1 or self.save_agg_results or self.save_paths:
                self.log.info("Finalizing assignment...")
                self.simulator.finalize_assignment(self.current_time_start, self.current_time_end)
            
            self._save_state_paths()
            self._save_paths()            
            self._save_agg_results()
            self.G = self.G_copy.copy()
            

    def _save_paths(self):
        try:
            if self.save_paths:
                self.log.info("Saving paths...")
                for t in range(self.real_time_start,self.real_time_end,self.delta_t):
                    paths = self.get_paths_dataframe(t=t)
                    if paths is None:
                        continue
                    self.writer.write_paths(paths, mode="w", partition=f"t={t}")
                paths = None                            
                self.log.info("Saved paths")
        except Exception as e:
            self.log.error("Failed to save paths:", exc_info=e, stack_info=True)        

    def _save_state_paths(self):
        try:
            if self.save_state_paths:
                self.log.info("Saving state (Paths)...")

                for t in range(self.real_time_start,self.real_time_end,self.delta_t):
                    paths = list(self.m_paths.get_paths_by_t(t))
                    self.state_manager.write_state(paths, "paths", mode="w", partition=f"t={t}")
                paths = None                                                        
                self.log.info("Saved state")
        except Exception as e:
            self.log.error("Failed to save state:", exc_info=e, stack_info=True)        

    def _save_agg_results(self):
        try:                
            if self.save_agg_results:
                self.log.info("Saving aggregated results...")
                df=self.get_aggregated_results_dataframe()
                ds_t = (pd.to_numeric(df["time"]) / 1000000000 % 86400 ) / 60
                for t in range(self.real_time_start,self.real_time_end,self.delta_t):
                    tmp = df[ds_t.between(t,t+self.delta_t)]
                    self.writer.write_agg_results(tmp, mode="W", partition=f"t={t}")
                self.log.info("Saved aggregated results")
        except Exception as e:
            self.log.error("Failed to save aggregated results:", exc_info=e, stack_info=True)

    def run_msa(self):

        self.current_i_start = int(self.current_time_start / self.delta_t)
        self.current_i_end = int(self.current_time_end / self.delta_t)
        self.current_num_intervals = self.current_i_end - self.current_i_start
        self.current_t_starts = [self.delta_t * i for i in range(self.current_num_intervals)]

        self.G.resize_attributes(new_total_time=self.current_num_intervals * self.delta_t, offset=self.current_i_start * self.delta_t)
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
            
        
        if self.simulator:
            self.simulator.set_paths(self.m_paths)

        if self.od_estimation:
            self.matrix_ass: MatrixAss = MatrixAss(self.loader, self.current_num_intervals)
        else:
            self.matrix_ass = None
        
        calc_paths = (True and not self.load_state_graph) or self.m_paths.is_empty()
        k_calculated = self.m_paths.k_paths()

        # %
        self.log.info("Initialization")

        # % inizializzo i flusso
        def reset_links(l: Link):
            l.reset_attribute(name="time", value=l["t0"])
            l.reset_attribute(name="flow", value=0)

        self.G.apply_links(reset_links)

        rgap = 1e308
        file_mode = "w"
        for iteration in range(0, self.max_ite):
            self.iteration = iteration
            info = {"ite": iteration}
            self.infos.append(info)

            self.log.info("Ite: %s - Start of Iteration", iteration)
            
            tempi_od = []

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
                    self.update_performance(k_calculated)
                    self.calc_stats()
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
                self.update_performance(k_calculated)
                self.calc_stats()
                continue

            self.log.info("Ite: %s - MSA flow redistribution...", iteration)

            # % MSA parte 1-1/k
            """
            Decurto 1-1/k di flusso per ogni vecchio percorso
            I nuovi percorsi aumenteranno di 1/k il proprio flusso
            """
            for (o, d, t_start, mode), k_paths in self.m_paths.all_kpaths():
                f = self.ODs[mode][o, d, self.current_time_start + t_start] * self.eq_factors.get(mode, 1)
                k = iteration + 1
                for path in k_paths:
                    path["path_flow"] *= (k - 1) / k


            tot_tt_current = 0
            for (o, d, t_start, mode), k_paths in self.m_paths.all_kpaths():
                if o == d:
                    continue
                f = self.ODs[mode][o, d, self.current_time_start + t_start] * self.eq_factors.get(mode, 1)
                if f > 0:
                    best = min(k_paths, key=lambda path: path["tot_cost"])
                    k = iteration + 1
                    best["path_flow"] += f / k
                    tempi_od.append(best["tot_cost"])
                    tot_tt_current += f * best["tot_cost"]

            info["rgap_time"] = None
            if iteration > 1:
                tot_tt = sum([path["tot_cost"] * path["path_flow"] for path in self.m_paths.all_paths()])
                rgap = abs(tot_tt - tot_tt_current) / tot_tt_current if tot_tt_current > 0 else 0
                info["rgap_time"] = rgap
                self.log.info("Ite: %s - Relative Gap on route times: %s", iteration, rgap)

            self.tot_dom = sum([path["path_flow"] for path in self.m_paths.all_paths()])
            self.log.info("Ite: %s - Veh*h: %s", iteration, tot_tt_current / 60)
            self.log.info("Ite: %s - Total demand on the network: %s", iteration, self.tot_dom)

            # %
            self.log.info("Ite: %s - Updating network performance...", iteration)
            self.update_performance(k_calculated)
            self.calc_stats()
            if rgap < self.max_rel_gap:
                break
        if rgap < self.max_rel_gap:
            self.log.info("Convergence reached")
        else:
            self.log.info("Assignment completed for maximum number of iterations")
            # self.log.info(f"occupazione graph: {getsize(self.G)/1024/1024}MB")
            # self.log.info(f"occupazione paths: {getsize(self.m_paths)/1024/1024}MB")
            # self.log.info(f"occupazione od: {getsize(self.od)/1024/1024}MB")
        
        
    def calculate_paths(self, k):
        n_cpu = self.loader.ini.NUMCPU
        SPP.parallel_engine = self.loader.ini.PARALLEL_ENGINE
        SPP.initialize_parallel(num_cpus=n_cpu)

        ret = KPathList()

        def generate_combinations(origins, destinations, t_starts, modes):
            for o, d, t_start, mode in itertools.product(origins, destinations, t_starts, modes):
                yield {"source": o, "targets": d, "t_start": t_start, "modes": mode, "t_base": self.current_time_start}

        tasks = list(generate_combinations(
            self.origins, 
            [self.destinations], 
            self.current_t_starts, 
            self.modes
            ))
        ret = SPP.multiple_paths(self.G, tasks=tasks, link_cost=self.links_cost, turn_cost=self.turns_cost, node_cost=self.nodes_cost)
        print(getsize(ret)/1024/1024)
        SPP.shutdown_parallel()
        self.m_paths.merge(ret, k)

    def update_performance(self, k: int):
        def reset(l: Link):
            l.reset_attribute(name="flow", value=0)

        self.G.apply_links(reset)

        update_costs = (self.iteration != self.max_ite - 1) or (self.save_paths and self.writer.has_write_paths())
        # aggiorno i tempi nel grafo
        if self.simulator:
            self.simulator.update_performance(
                k=k,
                tstart=self.current_time_start,
                tend=self.current_time_end,
            )        
            
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



    

    def calc_stats(self):
        t_start = self.t_start
        if self.t_end is not None:
            t_start = self.t_end
        self.t_end = time.time()
        self.tot_dom = sum([path["path_flow"] for path in self.m_paths.all_paths()])
        if self.simulator and hasattr(self.simulator, "vehs"):
            if self.simulator.vehs is not None:
                tot_vehicles = len(self.simulator.vehs)
            else:
                tot_vehicles = 0
            self.log.info(
                f"""Ite: {self.iteration} - cpu_time: {int(self.t_end - t_start)}, total_flows: {int(self.tot_dom)}, moving_vehicles: {tot_vehicles}, n_paths: {self.m_paths.n_paths()}, k_calculated: {self.m_paths.k_paths()}"""
            )
        else:
            self.log.info(
                f"""Ite: {self.iteration} - cpu_time: {int(self.t_end - t_start)}, total_flows: {int(self.tot_dom)}, n_paths: {self.m_paths.n_paths()}, k_calculated: {self.m_paths.k_paths()}"""
            )

    def calc_matrice_ass(self, time_start, time_end):
        self.log.info ("Assignment matrix calculation...")
        for (source, target, t_start, mode), paths in self.m_paths.all_kpaths():
            for path in paths:
                costs = tuple(path.get_costs())
                self.OD[o, d, self.current_time_start + t_start] * self.eq_factors.get(mode, 1)
                f = self.od[o, d, time_start + tstart * self.delta_t]

                if f <= 0:
                    continue
                idxs = list(map(lambda x: int(x // self.delta_t), costs))
                links = path["links"]
                for idx, l in zip(idxs, links):  # [t for t in zip(idxs, links) if t[1] in self.matrix_ass.detectors]:
                    if self.assegna_flussi_msa:
                        if idx < (len(l["flow"]) - 1):
                            l["flow"][idx] += path["path_flow"]
                    self.matrix_ass.add(o, d, l=l["idx"], t_start=t_start, tenter=idx, flow=path["path_flow"] / f)
        self.log.info ("Assignment matrix calculated")

    
    def get_aggregated_results_dataframe(self):
        from .utils import ST_Multi
        import geopandas as gpd

        G = self.loader.G
        if self.simulator is None:
            return None
        results = self.simulator.agg_results(self.global_t_start, self.global_t_end, agg_int=self.loader.ini.OUTPUT_AGG_INT)
        id_links = results["id_link"].unique()
        df_geometry = pd.DataFrame([[id_link,ST_Multi(G.get_link(id_link).get_value("geometry"))] for id_link in id_links], columns=["id_link","geometry"])
        results = results.merge(df_geometry, on="id_link")
        results = gpd.GeoDataFrame(results, geometry="geometry" ,crs="EPSG:4326")
        return results
        
    def get_paths_dataframe(self, t=None):
        from shapely import MultiLineString
        from .utils import multi_line_to_line
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
                results = gpd.GeoDataFrame(results, geometry=geom ,crs="EPSG:4326")
                break

        return results