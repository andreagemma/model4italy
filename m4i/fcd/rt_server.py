from __future__ import annotations
import logging
import __future__
from numbers import Number
import os
import time
from typing import Optional, Union, Iterable, Hashable

from shapely import Point, LineString, frechet_distance, remove_repeated_points
from shapely.ops import split, substring
from shapely.validation import make_valid
import pandas as pd
import geopandas as gpd


from datetime import datetime, timedelta

from heapq import heappush as push
from heapq import heappop as pop
import geopandas as gpd

            
from ..graphs import AbstractGraph, PathList, PathList
from .build_paths import BuildPaths
from ..params_parser import ParamsParser
from ..connectors import Loader, Writer
from ..utils import export_dataframe, TicToc, multi_line_to_line
from ..utils.ipc import IPC
from ..log import Logger


class RTServer:
    """
    FCDServer is a class that handles the matching of Floating Car Data (FCD) to a road network.
    It uses a Map Matching algorithm to align the FCD points with the nearest road segments.
    """
    def __init__(self, parser: ParamsParser, ipc:IPC=None, logger=None, loader:Loader=None, writer:Writer=None):
        self.log: logging.Logger = logger or Logger.getLogger(self.__class__.__name__)
        self.tic: TicToc = TicToc(logger=self.log)
        self.parser: ParamsParser = parser
        self.loader: Loader = Loader(parser=parser) if loader is None else loader
        self.writer: Writer = Writer(parser=parser) if writer is None else writer
        self.build_paths = BuildPaths(parser=self.parser, 
                                      loader=self.loader, 
                                      n_workers_mm=parser.ini.FCD_MAP_MATCHING_CPUS, 
                                      n_workers_pm=parser.ini.FCD_PATH_MATCHING_CPUS,
                                      max_distance=parser.ini.FCD_MAP_MATCHING_MAX_DISTANCE,
                                      max_angle=parser.ini.FCD_MAP_MATCHING_MAX_ANGLE,
                                      crs_calc=parser.ini.FCD_CRS_CALC,
                                      crs_data=parser.ini.FCD_CRS_CALC,
                                      logger=logger,
                                      )
        self.ipc: IPC = ipc
        self.df_links: gpd.GeoDataFrame = None
        self.df_nodes: gpd.GeoDataFrame = None
        self.df_turns: gpd.GeoDataFrame = None
        self.graph: AbstractGraph = None
        self.paths: PathList = PathList(key=lambda x: x.get("id_trip"))
        self.df_fcd: gpd.GeoDataFrame = None
        self.df_trips: gpd.GeoDataFrame = None
        self.zones: gpd.GeoDataFrame = None
        self.t:int = 0

    def to_datetime(self, t: Union[str,int,datetime]) -> datetime:
        """
        Convert a string or int to a datetime object.
        """
        if isinstance(t, str):
            if t.isnumeric():
                t = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(minutes=float(t))
            else:
                try:
                    t = datetime.strptime(t, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    raise ValueError("Invalid date format. Use 'YYYY-MM-DD HH:MM:SS' or a number.")
        elif isinstance(t, (float,int)):
            t = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(minutes=t)
        return t
    def to_timedelta(self, t: Union[str,int,datetime]) -> timedelta:
        """
        Convert a string or int to a datetime object.
        """
        if isinstance(t, str):
            if t.isnumeric():
                t = timedelta(minutes=float(t))
            else:
                raise ValueError("Invalid timedelta format. Use a number.")
        elif isinstance(t, (float,int)):
            t = timedelta(minutes=t)
        return t  

    def elaborate_period(self, 
                         t_start: Union[str,int,datetime], 
                         t_end: Union[str,int,datetime],
                         horizon: Union[str,int,timedelta]=15,
                         ):
        tic=self.tic.get().info("Elaborating period...")
        assert isinstance(t_start, (str,int,datetime)), "t_start must be a string, int or datetime"
        assert isinstance(t_end, (str,int,datetime)), "t_end must be a string, int or datetime"
        t_start = self.to_datetime(t_start)
        t_end = self.to_datetime(t_end)
        horizon = self.to_timedelta(horizon)

        ts = t_start
        te = t_start + horizon
        mode = "w"
        while te <= t_end:
            self.tic.info("Processing period from {ts} to {te}", ts=ts, te=te)
            self.step(t_start=ts, t_end=te, share_on_ipc=False, clean=False)
            path_to_save = self.paths.filter(lambda x: x.get("closed") == True, inplace=False)
            if self.save_paths(paths=path_to_save,path_parameters="params.rt_paths", mode=mode):
                mode = "a"
            for path in path_to_save.all_paths():
                self.paths.delete(path)
            ts = te
            te = ts + horizon


    def step(self, 
             t_start: Union[str,int,datetime]=None, 
             t_end: Union[str,int,datetime]=None, 
             horizon: Union[str,int,timedelta]=None,
             share_on_ipc: bool=True,
             clean: bool=True,     
             ) -> None:
        """
        Perform a step in the FCD processing pipeline.
        """
        t_step=self.tic.get().info("Performing step...")
        if t_start is not None:            
            t_start = self.to_datetime(t_start)
        if t_end is not None:
            t_end = self.to_datetime(t_end)
        if horizon is not None:
            horizon = self.to_timedelta(horizon)

        if t_start is None and t_end is None:
            t_end = datetime.now()
            horizon = horizon or timedelta(minutes=self.parser.ini.FCD_HORIZON)
            t_start = t_end - horizon
        elif t_start is None and t_end is not None:
            t_end = t_end
            horizon = horizon or timedelta(minutes=self.parser.ini.FCD_HORIZON)
            t_start = t_end - horizon
        elif t_start is not None and t_end is None:
            horizon = horizon or timedelta(minutes=self.parser.ini.FCD_HORIZON)
            t_end = t_start + horizon
        elif t_start is not None and t_end is not None:
            if t_start >= t_end:
                raise ValueError("t_start must be less than t_end")
            horizon = t_end - t_start
        self.tic.info("Step from {t_start} to {t_end} with horizon {horizon}", t_start=t_start, t_end=t_end, horizon=horizon)
        self.t = int((t_start-t_start.replace(hour=0, minute=0, second=0, microsecond=0)).total_seconds() // 60)
        self.load_graph(share_on_ipc=share_on_ipc)
        self.build_paths.load_graph(df_links=self.df_links)
        new_df_fcd = self.load_fcd_by_timetamp(t_start=t_start, t_end=t_end)                    
        self.match_fcd(fcd_data=new_df_fcd, old_fcd_data=self.df_fcd)
        if clean:
            self.clean(t_end=t_end)
        self.update_speed(df_fcd=self.df_fcd)
        self.calculate_paths(df_fcd=self.df_fcd, df_trips=self.df_trips)        
        self.share_data(share_on_ipc=share_on_ipc)
        t_step.info("Step completed in {et} seconds")

    def paths_to_pandas(self, paths = None) -> gpd.GeoDataFrame:
        paths = paths or self.paths
        return paths.to_pandas(self.graph, self.df_links.crs)
    
    def clean(self, t_end: datetime) -> None:
        self.tic.info("Cleaning data...").tic()
        horizon = timedelta(minutes=self.parser.ini.FCD_HORIZON)
        t_start_mem = t_end - horizon
        t = int((t_start_mem-t_start_mem.replace(hour=0, minute=0, second=0, microsecond=0)).total_seconds() // 60) # t_start in minutes

        n_trips = self.df_trips.shape[0]
        n_fcd = self.df_fcd.shape[0]
        n_paths = self.paths.n_paths()

        self.df_trips = self.df_trips[self.df_trips["dt_d"] >= t_start_mem]
        self.df_fcd = self.df_fcd.merge(self.df_trips["id_trip"], on="id_trip", how="left")
        self.paths = self.paths.filter(lambda x: x.get("t") >= t, inplace=True) # remove paths older than t_start
        n_trips -= self.df_trips.shape[0]
        n_fcd -= self.df_fcd.shape[0]
        n_paths -= self.paths.n_paths()
        self.tic.info("Cleaned {trips} trips, {fcd} FCDs and {paths} in {et} seconds", trips=n_trips, fcd=n_fcd, paths=n_paths)        

    def load_fcd_by_timetamp(self, t_start: datetime, t_end: datetime) -> pd.DataFrame:
        """
        Load FCD data from the database based on the given time range.
        """
        self.tic.info("Loading FCD data...").tic()
        df_fcd: pd.DataFrame = self.build_paths.load_fcd_by_timestamp(t_start=t_start, t_end=t_end, crs_data=self.parser.ini.FCD_CRS_DATA)
        self.tic.info("Loaded {fcd} FCDs in {et} seconds", fcd=df_fcd.shape[0])
        return df_fcd
    
    def match_fcd(self, fcd_data: pd.DataFrame, old_fcd_data: pd.DataFrame) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
        """
        Match FCD data to the road network using Map Matching algorithm.
        """
        self.tic.info(f"Matching {fcd_data.shape[0]} FCDs...").tic()
        #estraggo i nuovi fcd e li matcho unendonli con i vecchi e ricalcolo i trips
        if old_fcd_data is not None:
            old_fcd_data["new"] = False
        fcd_data["new"] = True
        df_fcd, df_trips = self.build_paths.match_fcd(fcd_data, old_fcd_data)
        if df_fcd is None or df_trips is None:
            self.tic.info("No FCDs or trips to match")
            return None, None
        self.df_fcd = df_fcd 
        # se i trips sono cambiati (dt_d diverso) allora li inserisco tra i trip da calcolare
        df_trips["new"] = True
        n_trips = df_trips.shape[0]        
        if self.df_trips is not None:
            df_trips.set_index('id_trip', inplace=True, drop=True)            
            merged = df_trips.merge(self.df_trips.set_index('id_trip', drop=True), on="id_trip", how='left', suffixes=('_new','_old'))
            changed_ids = merged.loc[merged['dt_d_new'] != merged['dt_d_old']].index
            updated_rows = df_trips.loc[changed_ids].reset_index(drop=False)            
            self.df_trips = pd.concat([self.df_trips,updated_rows]).drop_duplicates(subset=["id_trip"], keep="last")
            #self.df_trips.reset_index(inplace=True)
        else:
            self.df_trips = df_trips
        self.tic.info("Matched {fcd} FCDs and {trips} trips built in {et} seconds", fcd=df_fcd.shape[0], trips=df_trips.shape[0], new=n_trips)
        return self.df_fcd, self.df_trips
    
    def update_speed(self, df_fcd: gpd.GeoDataFrame) -> None:
        self.tic.info("Updating speed...").tic()
        if df_fcd is None:
            self.tic.info("No FCD data to update speed")
            return
        df = df_fcd[df_fcd["new"] == True].copy()
        df["t"] = df["timestamp"].dt.hour*60+df["timestamp"].dt.minute + df["timestamp"].dt.second/60
        df=df.groupby(["mm_id_link","t"]).agg(speed=("speed", "mean"), n=("speed", "count")).reset_index()
        for i, row in df.iterrows():
            l = self.graph.get_link(row["mm_id_link"])
            fcd_speed = l.get_value("fcd_speed", t=row["t"])
            fcd_n = l.get_value("fcd_n", t=row["t"])
            if fcd_speed is None or fcd_n is None or fcd_n == 0:
                l.set_value("fcd_speed", row["speed"], t=row["t"])
                l.set_value("fcd_n", row["n"], t=row["t"])
            else:
                fcd_speed = (fcd_speed * fcd_n + row["speed"] * row["n"]) / (fcd_n + row["n"])
                fcd_n += row["n"]
                l.set_value("fcd_speed", fcd_speed, t=row["t"])
                l.set_value("fcd_n", fcd_n, t=row["t"])            
        self.tic.info("Updated speed in {et} seconds")
    
    def load_graph(self, share_on_ipc: bool=True) -> None:
        """
        Load the road network graph from the database.
        """
        self.tic.info("Loading graph data...").tic()
        load_from_ipc = self.ipc is not None and share_on_ipc
        if load_from_ipc:
            if self.ipc.get("_zones") is not None:
                self.tic.info("Loading zones from IPC...")
                self.zones = self.ipc.get("_zones")                
                
            if self.ipc.get("_df_links") is not None:
                self.tic.info("Loading df_links from IPC...")
                self.df_links = self.ipc.get("_df_links")
                self.df_links = gpd.GeoDataFrame(self.df_links, crs=self.parser.ini.FCD_CRS_DATA).to_crs(self.parser.ini.FCD_CRS_CALC)
            if self.ipc.get("_df_nodes") is not None:
                self.tic.info("Loading df_nodes from IPC...")
                self.df_nodes = self.ipc.get("_df_nodes")
                self.df_nodes = gpd.GeoDataFrame(self.df_nodes, crs=self.parser.ini.FCD_CRS_DATA).to_crs(self.parser.ini.FCD_CRS_CALC)
            if self.ipc.get("_df_turns") is not None:
                self.tic.info("Loading df_turns from IPC...")
                self.df_turns = self.ipc.get("_df_turns")

        if self.zones is None:
            self.zones = self.loader.zonization.to_crs(self.parser.ini.FCD_CRS_CALC)
        else:
            self.zones = self.zones.to_crs(self.parser.ini.FCD_CRS_CALC)

        if self.df_links is None or self.df_nodes is None or self.df_turns is None:
            self.df_links, self.df_nodes, self.df_turns = self.loader.load_df_graph()
            self.df_nodes = gpd.GeoDataFrame(self.df_nodes, crs=self.parser.ini.FCD_CRS_DATA).to_crs(self.parser.ini.FCD_CRS_CALC)
            self.df_links = gpd.GeoDataFrame(self.df_links, crs=self.parser.ini.FCD_CRS_DATA).to_crs(self.parser.ini.FCD_CRS_CALC)
        self.graph = self.loader.load_graph(df_links=self.df_links, df_nodes=self.df_nodes, df_turns=self.df_turns)
        id_links = set(l["idx"] for l in self.graph.get_all_links())
        self.df_links = self.df_links[self.df_links["id"].isin(id_links)]
        id_nodes = set(self.df_links["from_node"].unique()).union(set(self.df_links["to_node"].unique()))
        self.df_nodes = self.df_nodes[self.df_nodes["id"].isin(id_nodes)]
            
        
        self.tic.info("Loaded graph data in {et} seconds")

    def share_data(self, share_on_ipc: bool=True) -> None:
        if self.ipc is not None and share_on_ipc:
            self.tic.info("Sharing data...").tic()
            self.ipc.set_data(_df_links=pd.DataFrame(self.df_links.to_crs(self.parser.ini.FCD_CRS_DATA)),
                              _df_nodes=pd.DataFrame(self.df_nodes.to_crs(self.parser.ini.FCD_CRS_DATA)), 
                              _df_turns=self.df_turns, 
                              paths=self.paths, 
                              _zones=self.zones.to_crs(self.parser.ini.FCD_CRS_DATA))
            self.tic.info("Shared data in {et} seconds")

    def calculate_paths(self, df_fcd: gpd.GeoDataFrame, df_trips: gpd.GeoDataFrame) -> PathList:
        """
        Calculate paths for the matched FCD data using the road network graph.
        """        
        if df_trips is None:
            self.tic.info("No trips to calculate paths")
            return None
        new_trips = df_trips[df_trips["new"] == True]
        
        self.tic.info(f"Calculating {new_trips.shape[0]} paths...").tic()
        for path in self.paths.all_paths():
            path["closed"] = True
        if self.parser.ini.FCD_PATH_START_FROM_ZONE:
            gdf_start_points = gpd.GeoDataFrame(new_trips.drop(columns='geometry'), 
                                     geometry=new_trips.geometry.apply(lambda geom: Point(geom.xy[0][0], geom.xy[1][0]))
                                     )
            tmp = self.zones[['id', 'geometry']].rename(columns={"id":"id_zone_o"})
            #tmp["geometry_o"] = tmp["geometry"]
            #tmp.crs = new_trips.crs
            joined = gpd.sjoin(gdf_start_points, tmp, how='left', predicate='within')
            new_trips = new_trips.merge(joined[["id_trip","id_zone_o"]].drop_duplicates(subset="id_trip"), on="id_trip", how="left")
        if self.parser.ini.FCD_PATH_END_TO_ZONE:
            gdf_start_points = gpd.GeoDataFrame(new_trips.drop(columns='geometry'), 
                                     geometry=new_trips.geometry.apply(lambda geom: Point(geom.xy[0][-1], geom.xy[1][-1]))
                                     )
            tmp = self.zones[['id', 'geometry']].rename(columns={"id":"id_zone_d"})
            #tmp["geometry_d"] = tmp["geometry"]
            #tmp.crs = new_trips.crs
            joined = gpd.sjoin(gdf_start_points, tmp, how='left', predicate='within')
            new_trips = new_trips.merge(joined[["id_trip","id_zone_d"]].drop_duplicates(subset="id_trip"), on="id_trip", how="left")

        new_paths = self.build_paths.calculate_paths(df_links=self.df_links, df_fcd=df_fcd, df_trips=new_trips, G=self.graph)
        for path in new_paths.all_paths():
            costs = list(path.get_costs(self.graph, update_links=True, update_nodes=True, update_turns=True))
            tot_cost = costs[-1]
            path["tot_cost"] = tot_cost
            t=(self.t // self.parser.ini.FCD_PATH_AGGRATION_INTERVAL) * self.parser.ini.FCD_PATH_AGGRATION_INTERVAL
            path["t"] = t
            path["t_start"] = t
            path["t_base"] = 0
            path["closed"] = False
            self.paths.add_path(path)
        df_trips["new"] = False
        self.tic.info("Calculated {n_trips} paths in {et} seconds ({tot_paths})", n_trips=new_paths.n_paths(), tot_paths=new_paths.n_paths())
        return new_paths
    
    def save_paths(self, paths: PathList, filename: str=None, mode="w", path_parameters: dict=None) -> None:
        """
        Save the calculated paths to a file.
        """
        self.tic.info("Saving paths...").tic()
        df_paths: gpd.GeoDataFrame = paths.to_pandas(self.graph, self.df_links.crs)
        if df_paths is None or df_paths.shape[0] == 0:
            self.tic.info("No paths to save")
            return False
        else:
            df_paths = df_paths.to_crs(self.build_paths.crs_data)
        if filename is not None:
            export_dataframe(df_paths, filename, layer="paths", mode=mode)
        elif path_parameters is not None:
            self.writer.write(df_paths, 
                              path=path_parameters, 
                              mode=mode
                              )
        self.tic.info("Saved paths in {et} seconds")
        return True

    def run(self):
        """
        Run the FCD processing pipeline.
        """
        if self.ipc is not None:
            self.tic.info("Listening for IPC messages...").tic()
            self.ipc.init()
            self.ipc.subscribe("rt_server", self.handler_ipc)
            self.ipc.listen()
        else:
            raise ValueError("IPC is not initialized. Cannot run the server.")


    def handler_ipc(self, msg):
        if msg is None:
            self.tic.info("No message received")
            return
        if isinstance(msg, str):
            self.tic.info("Received message: {msg}", msg=msg)
            try:
                import ast            
                msg = ast.literal_eval(msg)
            except Exception as e:
                self.tic.info("Do Nothing")
                return
        if not isinstance(msg, dict):
            self.tic.info("Received message is not a dictionary")
            return
        cmd = msg.get("cmd")
        if cmd == "exit":
            self.tic.info("Received exit message")
            import sys
            sys.exit(0)            
            return
        if cmd == "step":
            self.tic.info("Received step message")
            t_end = msg.get("t_end")
            t_start = msg.get("t_start")
            horizon = msg.get("horizon")            
            self.step(t_start=t_start,t_end=t_end, horizon=horizon)
    

