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
from ..utils import export_dataframe, TicToc, multi_line_to_line, to_datetime_auto, to_timedelta_auto
from ..utils.ipc import IPC
from ..log import Logger
from .fcd_manager import FCDManager


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
                                      n_workers_pm=parser.ini.FCD_ROUTING_CPUS,
                                      max_distance=parser.ini.FCD_MAP_MATCHING_MAX_DISTANCE,
                                      max_angle=parser.ini.FCD_MAP_MATCHING_MAX_ANGLE,
                                      crs_calc=parser.ini.FCD_SERVER_FCD_CRS_CALC,
                                      crs_data=parser.ini.FCD_SERVER_FCD_CRS_CALC,
                                      logger=logger,
                                      )
        self.ipc: IPC = ipc
        self.fcd_manager = FCDManager(
            loader=self.loader,
            writer=self.writer,
            ipc=self.ipc
        )

        self.df_links: gpd.GeoDataFrame = None
        self.df_nodes: gpd.GeoDataFrame = None
        self.df_turns: gpd.GeoDataFrame = None
        self.graph: AbstractGraph = None
        self.paths: PathList = PathList(key=lambda x: x.get("id_trip"))
        self.df_fcd: gpd.GeoDataFrame = None
        #self.df_paths: gpd.GeoDataFrame = None
        self.df_trips: gpd.GeoDataFrame = None
        self.zones: gpd.GeoDataFrame = None
        self.t:int = 0

        self.t_start: datetime = None
        self.t_end: datetime = None
        self.horizon: timedelta = None
        self.timeslice: timedelta = None
        
        self.new_fcd: gpd.GeoDataFrame = None
        self.old_df_fcd: gpd.GeoDataFrame = None

    def elaborate_offline(self, 
                         t_start: Union[str,int,datetime], 
                         t_end: Union[str,int,datetime]
                         ):
        tic=self.tic.get().info("Elaborating offline...")
        assert isinstance(t_start, (str,int,datetime)), "t_start must be a string, int or datetime"
        assert isinstance(t_end, (str,int,datetime)), "t_end must be a string, int or datetime"
        self.t_start = to_datetime_auto(t_start,unit="minutes", tz_localize=self.parser.ini.TZ_LOCAL, tz_convert=self.parser.ini.FCD_SERVER_TZ_DATA)
        self.t_end = to_datetime_auto(t_end,unit="minutes", tz_localize=self.parser.ini.TZ_LOCAL, tz_convert=self.parser.ini.FCD_SERVER_TZ_DATA)
        self.horizon = to_timedelta_auto(self.parser.ini.FCD_SERVER_FCD_HORIZON, unit="minutes")
        self.timeslice = to_timedelta_auto(self.parser.ini.FCD_SERVER_FCD_TIMESLICE_OFFLINE, unit="minutes") 


        ts = self.t_start
        te = self.t_start + self.timeslice
        mode = "w"

        while te <= self.t_end:
            self.tic.info("Processing period from {ts} to {te}", ts=ts, te=te)
            self.step(
                t_start=ts, 
                t_end=te, 
                match=self.parser.ini.FCD_SERVER_MAP_MATCHING,
                trips =self.parser.ini.FCD_SERVER_TRIPS,
                paths=self.parser.ini.FCD_SERVER_ROUTING,
                share_data=self.parser.ini.FCD_SERVER_SHARE_DATA
                )
            write_data =self.parser.ini.FCD_SERVER_WRITE_OUTPUT
            if write_data:
                path_to_save = self.paths.filter(lambda x: x.get("closed") == True, inplace=False)
                if self.save_paths(paths=path_to_save,path_parameters="params.rt_paths", mode=mode):
                    mode = "a"
                for path in path_to_save.all_paths():
                    self.paths.delete(path)

            ts = te
            te = ts + self.timeslice

    def elaborate_online(self, 
                         t_end: Union[str,int,datetime]
                         ):
        tic=self.tic.get().info("Elaborating online...")
        assert isinstance(t_end, (str,int,datetime)), "t_end must be a string, int or datetime"
        self.t_end = to_datetime_auto(t_end,unit="minutes").tz_localize(self.parser.ini.TZ_LOCAL).tz_convert(self.parser.ini.FCD_SERVER_TZ_DATA)        
        self.horizon = to_timedelta_auto(self.parser.ini.FCD_SERVER_FCD_HORIZON, unit="minutes")
        self.timeslice = to_timedelta_auto(self.parser.ini.FCD_SERVER_FCD_TIMESLICE, unit="minutes") 


        te = self.t_end
        te = self.t_start - self.timeslice

        while te <= t_end:
            self.tic.info("Processing period from {ts} to {te}", ts=ts, te=te)
            self.step(
                t_start=ts, 
                t_end=te, 
                match=self.parser.ini.FCD_SERVER_MAP_MATCHING,
                trips =self.parser.ini.FCD_SERVER_TRIPS,
                paths=self.parser.ini.FCD_SERVER_ROUTING,
                share_data=self.parser.ini.FCD_SERVER_SHARE_DATA
                )

            ts = te
            te = ts + self.timeslice            


    def step(self, 
             t_start: datetime=None, 
             t_end: datetime=None,
             match: bool = True,
             trips: bool = True,
             paths: bool = True,
             update_speed: bool = True,
             clean: bool = True,
             share_data: bool = True,
             ) -> None:
        """
        Perform a step in the FCD processing pipeline.
        """
        t_step=self.tic.get().info("Performing step...")

        self.tic.info("Step from {t_start} to {t_end}", t_start=self.t_start, t_end=self.t_end)
        self.t = int((t_start-t_start.replace(hour=0, minute=0, second=0, microsecond=0)).total_seconds() // 60) ## minuti dalla mezzanotte
        self.load_graph()
        self.df_fcd = self.load_fcd_by_timestamp(t_start=t_start, t_end=t_end)        
        if clean:
            self.clean(t_start=t_start)

        if match or paths:
            self.df_fcd = self.map_matching_fcd(df_fcd=self.df_fcd)
            if update_speed:                
                self.update_speed(df_fcd=self.df_fcd)

        if self.old_df_fcd is not None:
            self.df_fcd = pd.concat([self.old_df_fcd, self.df_fcd], ignore_index=True)

        if trips or paths:
            self.df_trips, self.old_df_fcd = self.build_trips(new_df_fcd=self.df_fcd, old_df_trips=self.df_trips)

        if paths:            
            self.calculate_paths(df_fcd=self.df_fcd, df_trips=self.df_trips)

        if share_data:
            self.share_data()

        t_step.info("Step completed in {et} seconds")

    def load_graph(self) -> None:
        self.tic.info("Loading graph data...").tic()
        if self.zones is None:
            self.zones = self.loader.zonization.to_crs(self.parser.ini.FCD_SERVER_FCD_CRS_CALC)
        else:
            self.zones = self.zones.to_crs(self.parser.ini.FCD_SERVER_FCD_CRS_CALC)

        if self.df_links is None or self.df_nodes is None or self.df_turns is None:
            self.df_links, self.df_nodes, self.df_turns = self.loader.load_df_graph()
            self.df_nodes = gpd.GeoDataFrame(self.df_nodes, crs=self.parser.ini.FCD_SERVER_FCD_CRS_DATA).to_crs(self.parser.ini.FCD_SERVER_FCD_CRS_CALC)
            self.df_links = gpd.GeoDataFrame(self.df_links, crs=self.parser.ini.FCD_SERVER_FCD_CRS_DATA).to_crs(self.parser.ini.FCD_SERVER_FCD_CRS_CALC)
        self.graph = self.loader.load_graph(df_links=self.df_links, df_nodes=self.df_nodes, df_turns=self.df_turns)
        id_links = set(l["idx"] for l in self.graph.get_all_links())
        self.df_links = self.df_links[self.df_links["id"].isin(id_links)]
        id_nodes = set(self.df_links["from_node"].unique()).union(set(self.df_links["to_node"].unique()))
        self.df_nodes = self.df_nodes[self.df_nodes["id"].isin(id_nodes)]                    
        self.tic.info("Loaded graph data in {et} seconds")

    def load_fcd_by_timestamp(self, t_start: datetime, t_end: datetime) -> pd.DataFrame:
        """
        Load FCD data from the database based on the given time range.
        """
        self.tic.info("Loading FCD data...").tic()
        df_fcd = self.fcd_manager.load_fcd_by_timestamp(
            t_start=t_start, t_end=t_end, 
            crs_data=self.parser.ini.FCD_SERVER_FCD_CRS_DATA,crs_calc=self.parser.ini.FCD_SERVER_FCD_CRS_CALC ) 
        df_fcd["new"] = True
        self.tic.info("Loaded {fcd} FCDs in {et} seconds", fcd=df_fcd.shape[0])
        return df_fcd
    
    def map_matching_fcd(self, df_fcd) -> pd.DataFrame:
        """
        Load FCD data from the database based on the given time range.
        """
        self.tic.info("Map Matching FCD data...").tic()
        df_fcd = self.fcd_manager.map_matching_fcd(df_fcd=df_fcd, df_links=self.df_links, links_id_col="id",links_direction_col=None)
        self.tic.info("Matched {fcd} FCDs in {et} seconds", fcd=df_fcd.shape[0])
        return df_fcd
    
    def build_trips(self, new_df_fcd, old_df_trips) -> pd.DataFrame:
        self.tic.info("Building Trips...").tic()
        new_df_fcd["new"]=True
        if old_df_trips is not None:
            old_df_trips["new"] = False
        
        new_df_trips, old_df_fcd = self.fcd_manager.build_trips(df_fcd=self.df_fcd, t_begin=None, t_end=None)

        new_df_trips["new"] = True
        if old_df_trips is None:
            pass
        else:
            new_df_trips = pd.concat([new_df_trips, old_df_trips], ignore_index=True)

        old_df_fcd["new"] = False        
        self.tic.info("Built {trips} trips in {et} seconds (ramaining {fcd} FCDs)", trips=new_df_trips.shape[0], fcd=old_df_fcd.shape[0])
        return new_df_trips, old_df_fcd
        
    
    def calculate_paths(self, df_fcd: gpd.GeoDataFrame=None, df_trips: gpd.GeoDataFrame=None) -> PathList:
        """
        Calculate paths for the matched FCD data using the road network graph.
        """        
        df_trips = self.df_trips if df_trips is None else df_trips
        df_fcd = self.df_fcd if df_fcd is None else df_fcd

        if df_trips is None:
            self.tic.info("No trips to calculate paths")
            return None
        self.build_paths.load_graph(self.df_links)
        new_trips = df_trips[df_trips["new"] == True]
        
        self.tic.info(f"Calculating {new_trips.shape[0]} paths...").tic()
        for path in self.paths.all_paths():
            path["closed"] = True
        if self.parser.ini.FCD_ROUTING_START_FROM_ZONE:
            gdf_start_points = gpd.GeoDataFrame(new_trips.drop(columns='geometry'), 
                                     geometry=new_trips.geometry.apply(lambda geom: Point(geom.xy[0][0], geom.xy[1][0]))
                                     )
            tmp = self.zones[['id', 'geometry']].rename(columns={"id":"id_zone_o"})
            #tmp["geometry_o"] = tmp["geometry"]
            #tmp.crs = new_trips.crs
            joined = gpd.sjoin(gdf_start_points, tmp, how='left', predicate='within')
            new_trips = new_trips.merge(joined[["id_trip","id_zone_o"]].drop_duplicates(subset="id_trip"), on="id_trip", how="left")
        if self.parser.ini.FCD_ROUTING_END_TO_ZONE:
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
            t=(self.t // self.parser.ini.FCD_ROUTING_AGGRATION_INTERVAL) * self.parser.ini.FCD_ROUTING_AGGRATION_INTERVAL
            path["t"] = t
            path["t_start"] = t
            path["t_base"] = 0
            path["closed"] = False
            self.paths.add_path(path)
        df_trips["new"] = False
        self.tic.info("Calculated {n_trips} paths in {et} seconds ({tot_paths})", n_trips=new_paths.n_paths(), tot_paths=new_paths.n_paths())
        return new_paths

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

    def clean(self, t_start: datetime) -> None:
        self.tic.info("Cleaning data...").tic()
        self.horizon = timedelta(minutes=self.parser.ini.FCD_SERVER_FCD_HORIZON)
        t_start_mem = t_start - self.horizon
        #t = int((t_start_mem-t_start_mem.replace(hour=0, minute=0, second=0, microsecond=0)).total_seconds() // 60) # t_start in minutes

        n_trips = self.df_trips.shape[0] if self.df_trips is not None else 0
        n_fcd = self.df_fcd.shape[0] if self.df_fcd is not None else 0
        n_paths = self.paths.n_paths()

        if self.df_trips is not None:
            self.df_trips = self.df_trips[self.df_trips["dt_d"] >= t_start_mem]
        if self.df_fcd is not None:
            self.df_fcd = self.df_fcd[self.df_fcd["timestamp"] >= t_start_mem]
            if self.df_trips is not None and self.df_trips.shape[0] > 0 and "id_trip" in self.df_fcd.columns:
                self.df_fcd = self.df_fcd[self.df_fcd["id_trip"].isin(self.df_trips["id_trip"])]
        
        self.paths = self.paths.filter(lambda x: x.get("dt_d") >= t_start_mem, inplace=True) # remove paths older than t_start
        n_trips -= self.df_trips.shape[0] if self.df_trips is not None else 0
        n_fcd -= self.df_fcd.shape[0] if self.df_fcd is not None else 0
        n_paths -= self.paths.n_paths()
        self.tic.info("Cleaned {trips} trips, {fcd} FCDs and {paths} in {et} seconds", trips=n_trips, fcd=n_fcd, paths=n_paths)        

    def paths_to_pandas(self, paths = None) -> gpd.GeoDataFrame:
        paths = paths or self.paths
        return paths.to_pandas(self.graph, self.df_links.crs)
    

    def share_data(self) -> None:
        if self.ipc is not None:
            self.tic.info("Sharing data...").tic()
            self.ipc.set_data(_df_links=pd.DataFrame(self.df_links.to_crs(self.parser.ini.FCD_SERVER_FCD_CRS_DATA)),
                              _df_nodes=pd.DataFrame(self.df_nodes.to_crs(self.parser.ini.FCD_SERVER_FCD_CRS_DATA)), 
                              _df_turns=self.df_turns, 
                              _paths=self.paths, 
                              _zones=self.zones.to_crs(self.parser.ini.FCD_SERVER_FCD_CRS_DATA))
            self.tic.info("Shared data in {et} seconds")
        else:
            self.tic.info("IPC is not initialized. Cannot share data.")
            return

    
    
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
            self.elaborate_online(t_end=t_end)
            
    

