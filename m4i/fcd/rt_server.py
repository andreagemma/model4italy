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
import geopandas
import numpy as np

from datetime import datetime, timedelta

from heapq import heappush as push
from heapq import heappop as pop
import geopandas as gpd
import pyproj
            
import warnings
from m4i.database.database import Base
from ..graphs import AbstractGraph, PathList, PathList, AbstractGraph, DynamicGraph
from .build_paths import BuildPaths
from ..params_parser import ParamsParser
from ..connectors import Loader, Writer
from ..utils import export_dataframe, TicToc, multi_line_to_line, to_datetime_auto, to_timedelta_auto, remove_path, pd_concat
from ..utils.ipc import IPC
from ..log import Logger
from .fcd_manager import FCDManager
from ..base_m4i_model import BaseM4IModel


class RTServer(BaseM4IModel):
    """
    FCDServer is a class that handles the matching of Floating Car Data (FCD) to a road network.
    It uses a Map Matching algorithm to align the FCD points with the nearest road segments.
    """
    def __init__(self, parser: ParamsParser, ipc:IPC=None, logger=None, loader:Loader=None, writer:Writer=None, **kwargs):
        super().__init__(loader=loader, writer=writer, ipc=ipc, **kwargs)        
        
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
        self.df_fcd_to_save: gpd.GeoDataFrame = None
        self.mode_trips="w"
        self.mode_fcd="w"
        self.mode_paths="w"
        self.mode_graphs="w"

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
        self.mode_trips="w"
        self.mode_fcd="w"
        self.mode_paths="w"


        ts = self.t_start
        te = self.t_start + self.timeslice

        while te <= self.t_end:
            self.tic.info("Processing period from {ts} to {te}", ts=ts, te=te)
            self.parser.update_date(ts, "simulation")
            self.step(
                t_start=ts, 
                t_end=te, 
                match=self.parser.ini.FCD_SERVER_MAP_MATCHING,
                trips =self.parser.ini.FCD_SERVER_TRIPS,
                paths=self.parser.ini.FCD_SERVER_ROUTING,
                update_speed=self.parser.ini.FCD_SERVER_UPDATE_SPEED,
                share_data=False,
                )
            write_data =self.parser.ini.FCD_SERVER_WRITE_OUTPUT
            if write_data:
                if self.save_paths(paths=self.paths, mode=self.mode_paths):
                    self.mode_paths = "a"
                if self.save_trips(df_trips=self.df_trips, mode=self.mode_trips):
                    self.mode_trips = "a"
                if self.save_fcd(df_fcd=self.df_fcd_to_save, mode=self.mode_fcd):
                    self.mode_fcd = "a"
                if self.save_graph(graph=self.graph, mode=self.mode_graphs):
                    self.mode_graphs = "a"
                self.paths.clear() 
                self.df_trips = None
                self.df_fcd_to_save = None


                

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
        self.mode="w"

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
                share_data=self.parser.ini.FCD_SERVER_SHARE_DATA_ONLINE
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
        if self.df_fcd is not None and not self.df_fcd.empty:
            self.df_fcd["id_trip"] = None
        if clean:
            self.clean(t_start=t_start)

    
        if match or paths:
            if self.df_fcd is not None and not self.df_fcd.empty:        
                self.df_fcd = self.map_matching_fcd(df_fcd=self.df_fcd)
                if update_speed:                
                    self.update_speed(df_fcd=self.df_fcd)

        #self.df_fcd_to_save = self.df_fcd.copy() if self.df_fcd is not None else None

        if self.old_df_fcd is not None and not self.old_df_fcd.empty:
            if self.df_fcd is not None and not self.df_fcd.empty:
                self.df_fcd = pd.concat([self.old_df_fcd, self.df_fcd.astype(self.old_df_fcd.dtypes.to_dict())], ignore_index=True)
            else:
                self.df_fcd = self.old_df_fcd

        if trips or paths:            
            self.df_trips, self.old_df_fcd = self.build_trips(new_df_fcd=self.df_fcd, old_df_trips=self.df_trips, t_end=t_end)

        #self.df_fcd_to_save = pd.concat([self.df_fcd_to_save, self.old_df_fcd, self.old_df_fcd], ignore_index=True).drop_duplicates(subset=["id_fcd"], keep=False)
        if paths:            
            self.calculate_paths(df_fcd=self.df_fcd, df_trips=self.df_trips)

        if share_data:
            self.share_data()

        t_step.info("Step completed in {et} seconds. {n_fcd}/{n_fcd_old} FCDs, {n_trips} trips, {n_paths} paths",
                    n_fcd=self.df_fcd.shape[0] if self.df_fcd is not None else 0,
                    n_fcd_old=self.old_df_fcd.shape[0] if self.old_df_fcd is not None else 0,
                    n_trips=self.df_trips.shape[0] if self.df_trips is not None else 0,
                    n_paths=self.paths.n_paths())


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
        self.graph:DynamicGraph = self.loader.load_graph(df_links=self.df_links, df_nodes=self.df_nodes, df_turns=self.df_turns)
        id_links = set(l["idx"] for l in self.graph.get_all_links())
        self.df_links = self.df_links[self.df_links["id"].isin(id_links)]
        id_nodes = set(self.df_links["from_node"].unique()).union(set(self.df_links["to_node"].unique()))
        self.df_nodes = self.df_nodes[self.df_nodes["id"].isin(id_nodes)]   
        self.graph.resize_attributes(new_total_time=self.timeslice.total_seconds() // 60, new_delta_t=self.ini.FCD_SPEED_AGGREGATION_INTERVAL)
        self.graph["t_base"] = self.t
        self.tic.info("Loaded graph data in {et} seconds")

    def load_fcd_by_timestamp(self, t_start: datetime, t_end: datetime) -> pd.DataFrame:
        """
        Load FCD data from the database based on the given time range.
        """
        self.tic.info("Loading FCD data...").tic()
        df_fcd = self.fcd_manager.load_fcd_by_timestamp(
            t_start=t_start, t_end=t_end, 
            crs_data=self.parser.ini.FCD_SERVER_FCD_CRS_DATA,crs_calc=self.parser.ini.FCD_SERVER_FCD_CRS_CALC ) 
        if df_fcd is None or df_fcd.empty:
            self.tic.warning("No FCD data found for the given time range")
            return df_fcd
        df_fcd["new"] = True
        #df_fcd["x"] = df_fcd.geometry.x
        #df_fcd["y"] = df_fcd.geometry.y        
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
    
    def build_trips(self, new_df_fcd, old_df_trips, t_end) -> pd.DataFrame:
        self.tic.info("Building Trips...").tic()
        new_df_fcd["new"]=True
        if old_df_trips is not None:
            old_df_trips["new"] = False
        
        if new_df_fcd is None or new_df_fcd.empty:
            self.tic.info("No new FCD data to build trips")
        else:
            new_df_trips, old_df_fcd = self.fcd_manager.build_trips(df_fcd=new_df_fcd, t_begin=None, t_finish=None, t_end=t_end)
            self.tic.info("Built {trips} trips in {et} seconds (ramaining {fcd} FCDs)", 
                        trips=new_df_trips.shape[0] if new_df_trips is not None else 0, 
                        fcd=old_df_fcd.shape[0] if old_df_fcd is not None else 0)


        if new_df_trips is None or new_df_trips.empty:
            pass
        else:
            new_df_fcd.set_index("id_fcd", inplace=True, drop=False)        
            for i, row in new_df_trips.iterrows():
                new_df_fcd.loc[row["id_fcds"], "id_trip"] = row["id_trip"]
            new_df_fcd.reset_index(inplace=True, drop=True)
        
            new_df_trips["new"] = True

        if old_df_trips is None:
            pass
        else:
            if new_df_trips is None or new_df_trips.empty:
                new_df_trips = old_df_trips
            else:
                new_df_trips = pd.concat([new_df_trips, old_df_trips], ignore_index=True)
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
            t=int((path["dt_o"]-path["dt_o"].replace(hour=0, minute=0, second=0, microsecond=0)).total_seconds() // 60) ## minuti dalla mezzanotte
            t=(t // self.parser.ini.FCD_ROUTING_AGGRATION_INTERVAL) * self.parser.ini.FCD_ROUTING_AGGRATION_INTERVAL            
            path["t"] = t
            path["t_start"] = t
            path["t_base"] = 0
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
        df["timestamp"] = pd.to_datetime(df["timestamp"])
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
        n_fcd += self.old_df_fcd.shape[0] if self.old_df_fcd is not None else 0
        n_paths = self.paths.n_paths()

        if self.df_trips is not None:            
            self.df_trips = self.df_trips[self.df_trips["dt_d"] >= t_start_mem]
        if self.df_fcd is not None:
            b = self.df_fcd["timestamp"] >= t_start_mem
            if not b.all():
                warnings.warn("There are new FCDs older than the current time - horizon. This may cause issues in the processing pipeline.")
                self.df_fcd = self.df_fcd[b]
        if self.old_df_fcd is not None:
            self.old_df_fcd = self.old_df_fcd[self.old_df_fcd["timestamp"] >= t_start_mem]
        
        self.paths = self.paths.filter(lambda x: x.get("dt_d") >= t_start_mem, inplace=True) # remove paths older than t_start
        n_trips -= self.df_trips.shape[0] if self.df_trips is not None else 0
        n_fcd -= self.df_fcd.shape[0] if self.df_fcd is not None else 0
        n_fcd -= self.old_df_fcd.shape[0] if self.old_df_fcd is not None else 0
        n_paths -= self.paths.n_paths()
        self.tic.info("Cleaned {trips} trips, {fcd} FCDs and {paths} paths in {et} seconds", trips=n_trips, fcd=n_fcd, paths=n_paths)        

    def paths_to_pandas(self, paths = None) -> gpd.GeoDataFrame:
        paths = paths or self.paths
        return paths.to_pandas(self.graph, self.df_links.crs)
    

    def share_data(self) -> None:
        if self.ipc is not None:
            self.tic.info("Sharing data...").tic()
            self.ipc.set_data(_df_links=pd.DataFrame(self.df_links.to_crs(self.parser.ini.CRS)),
                              _df_nodes=pd.DataFrame(self.df_nodes.to_crs(self.parser.ini.CRS)), 
                              _df_turns=self.df_turns,                               
                              _paths=self.paths, 
                              _zones=self.zones.to_crs(self.parser.ini.CRS))
            self.tic.info("Shared data in {et} seconds")
        else:
            self.tic.info("IPC is not initialized. Cannot share data.")
            return

    
    
    def save_paths(self, paths: PathList, mode) -> None:
        """
        Save the calculated paths to a file.
        """
        if not self.writer.has("params.fcd_paths"):
            return False
        self.tic.info("Saving paths...").tic()
        df_paths: gpd.GeoDataFrame = paths.to_pandas(self.graph, self.df_links.crs)
        if df_paths is None or df_paths.shape[0] == 0:
            self.tic.info("No paths to save")
            return False
        else:
            df_paths = df_paths.to_crs(self.build_paths.crs_data)
        
        self.writer.write(df_paths,"params.fcd_paths", mode=mode)
        self.tic.info("Saved paths in {et} seconds")
        return True

    def save_trips(self, df_trips: gpd.GeoDataFrame, mode) -> None:
        """
        Save the calculated paths to a file.
        """
        if not self.writer.has("params.fcd_trips"):
            return False
        self.tic.info("Saving trips...").tic()
        
        df_trips = df_trips.copy()
        df_trips["t"]=(np.floor((df_trips["dt_o"].dt.hour*60+df_trips["dt_o"].dt.minute)/15)*15).astype("Int64")
        df_trips.drop(columns=["new"], inplace=True, errors="ignore")
        if df_trips is None or df_trips.shape[0] == 0:
            self.tic.info("No trips to save")
            return False
        else:
            df_trips = df_trips.to_crs(self.build_paths.crs_data)
        
        self.writer.write(df_trips,"params.fcd_trips", mode=mode)
        self.tic.info("Saved trips in {et} seconds")
        return True
    
    def save_fcd(self, df_fcd: gpd.GeoDataFrame, mode) -> None:
        """
        Save the calculated paths to a file.
        """
        if not self.writer.has("params.fcd_fcd"):
            return False
        self.tic.info("Saving FCD...").tic()
        if df_fcd is None or df_fcd.shape[0] == 0:
            self.tic.info("No FCD to save")
            return False        
        df_fcd = df_fcd.copy()
        df_fcd["t"]=(np.floor((df_fcd["timestamp"].dt.hour*60+df_fcd["timestamp"].dt.minute)/15)*15).astype("Int64")
        df_fcd.drop(columns=["new","x","y"], inplace=True, errors="ignore")
        df_fcd = df_fcd.to_crs(self.build_paths.crs_data)
        
        self.writer.write(df_fcd,"params.fcd_fcd", mode=mode)
        self.tic.info("Saved FCD in {et} seconds")
        return True
    
    def save_graph(self, graph: AbstractGraph, mode) -> None:
        """
        Save the calculated paths to a file.
        """
        self.tic.info("Saving Graph...").tic()
        if graph is None:
            self.tic.info("No Graph to save")
            return False
        #graph.apply_links(
        #    lambda x: x.set_value("geometry", x.get_value("geometry", t=None).to_crs(self.parser.ini.CRS), t=None),
        #)
        if self.writer.has("params.fcd_graph"):
            self.writer.write(graph,"params.fcd_graph", mode=mode)
        self.tic.info("Saved Graph in {et} seconds")
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
            
    


