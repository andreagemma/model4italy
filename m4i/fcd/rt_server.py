from __future__ import annotations
import dateutil
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
from ..graphs import AbstractGraph, PathList, PathList, AbstractGraph, DynamicGraph, DynamicTimeArrayAttribute
from .build_paths import BuildPaths
from .paths_clustering import PathsClustering

from ..params_parser import ParamsParser
from ..connectors import Loader, Writer
from ..utils import export_dataframe, TicToc, multi_line_to_line, to_datetime_auto, to_timedelta_auto, remove_path, pd_concat
from ..utils.ipc import IPC
from ..log import Logger
from .fcd_manager import FCDManager
from ..base_m4i_model import BaseM4IModel
from ..graphs import KPathList
import tempfile

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
                                      crs_calc=parser.ini.CRS_CALC,
                                      crs_data=parser.ini.CRS,                                      
                                      logger=logger,
                                      )
        self.fcd_manager = FCDManager(
            loader=self.loader,
            writer=self.writer,
            ipc=self.ipc
        )

        self.reload_graph=False
        if not self.reload_graph:
            self.tmp_graph = tempfile.NamedTemporaryFile(delete=False)
            self.tmp_links = tempfile.NamedTemporaryFile(delete=False)
            self.tmp_nodes = tempfile.NamedTemporaryFile(delete=False)
            self.tmp_turns = tempfile.NamedTemporaryFile(delete=False)
            self.tmp_zones = tempfile.NamedTemporaryFile(delete=False)
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
        self.reload_map_matching_data = False

                          
    def elaborate_offline(self, 
                         t_start: Union[str,int,datetime], 
                         t_end: Union[str,int,datetime]
                         ):
        tic=self.tic.get().info("Elaborating offline...")
        assert isinstance(t_start, (str,int,datetime)), "t_start must be a string, int or datetime"
        assert isinstance(t_end, (str,int,datetime)), "t_end must be a string, int or datetime"
        self.t_start = to_datetime_auto(t_start,unit="minutes", tz_localize=self.parser.ini.TZ_LOCAL, tz_convert=self.parser.ini.TZ_CALC)
        self.t_end = to_datetime_auto(t_end,unit="minutes", tz_localize=self.parser.ini.TZ_LOCAL, tz_convert=self.parser.ini.TZ_CALC)
        self.horizon = to_timedelta_auto(self.parser.ini.FCD_SERVER_FCD_HORIZON, unit="minutes")
        self.timeslice = to_timedelta_auto(self.parser.ini.FCD_SERVER_FCD_TIMESLICE_OFFLINE, unit="minutes") 
        if self.parser.ini.FCD_SERVER_SAVE_DELAY:
            self.start_save = self.t_start +timedelta(minutes=self.parser.ini.FCD_SERVER_SAVE_DELAY)
        else:
            self.start_save = self.t_start

        if self.parser.ini.FCD_SERVER_SAVE_START:
            self.start_save = to_datetime_auto(self.parser.ini.FCD_SERVER_SAVE_START, tz_localize=self.parser.ini.TZ_LOCAL, tz_convert=self.parser.ini.TZ_CALC)

        self.recover_mode = self.parser.ini.FCD_SERVER_RECOVERY_MODE

        if not self.recover_mode or self.start_save == self.t_start:
            self.mode_trips="w"
            self.mode_fcd="w"
            self.mode_paths="w"
            self.mode_graphs="w"
        else:
            self.mode_trips="a"
            self.mode_fcd="a"
            self.mode_paths="a"
            self.mode_graphs="a"

        ts = self.t_start
        te = self.t_start + self.timeslice

        while te <= self.t_end:
            self.tic.info("Processing period from {ts} to {te}", ts=ts, te=te)
            self.parser.update_date(to_datetime_auto(ts, tz_convert=self.parser.ini.TZ_LOCAL), "simulation")
            self.step(
                t_start=ts, 
                t_end=te, 
                match=self.parser.ini.FCD_SERVER_MAP_MATCHING and ts >= self.start_save,
                trips =self.parser.ini.FCD_SERVER_TRIPS,
                paths=self.parser.ini.FCD_SERVER_ROUTING,
                update_speed=self.parser.ini.FCD_SERVER_UPDATE_SPEED and ts >= self.start_save,
                share_data=False,
                )
            write_data =self.parser.ini.FCD_SERVER_WRITE_OUTPUT or self.parser.ini.FCD_SERVER_WRITE_STATE
            
            if write_data and ts >= self.start_save: # in recovery mode, skip saving data for the initial periods     
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
            elif write_data:
                self.tic.info("Skipping saving data for period from {ts} to {te} due to recovery delay", ts=ts, te=te)
            ts = te
            te = ts + self.timeslice

    def elaborate_online(self, 
                         t_end: Union[str,int,datetime]
                         ):
        tic=self.tic.get().info("Elaborating online...")
        assert isinstance(t_end, (str,int,datetime)), "t_end must be a string, int or datetime"
        self.t_end = to_datetime_auto(t_end,unit="minutes").tz_localize(self.parser.ini.TZ_LOCAL).tz_convert(self.parser.ini.TZ_CALC)        
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
             share_data: bool = True
             ) -> None:
        """
        Perform a step in the FCD processing pipeline.
        """
        t_step=self.tic.get().info("Performing step...")
        self.tic.info("Step from {t_start} to {t_end}", t_start=t_start, t_end=t_end)
        self.t = t_start
        self.load_graph()
        self.df_fcd = self.load_fcd_by_timestamp(t_start=t_start, t_end=t_end)      
        if self.df_fcd is not None and not self.df_fcd.empty:
            self.df_fcd["id_trip"] = None
        if clean:
            self.clean(t_start=t_start)
            t_step.info("Remaining {n_fcd} (old: {n_fcd_old}) FCDs, {n_trips} trips, {n_paths} paths",
                    n_fcd=self.df_fcd.shape[0] if self.df_fcd is not None else 0,
                    n_fcd_old=self.old_df_fcd.shape[0] if self.old_df_fcd is not None else 0,
                    n_trips=self.df_trips.shape[0] if self.df_trips is not None else 0,
                    n_paths=self.paths.n_paths())
    
        if match or update_speed or (paths and (self.ini.FCD_ROUTING_END_TO_ZONE==0 or self.ini.FCD_ROUTING_START_FROM_ZONE==0)):
            if self.df_fcd is not None and not self.df_fcd.empty:        
                self.df_fcd = self.map_matching_fcd(df_fcd=self.df_fcd)
                if update_speed:                
                    self.update_speed(df_fcd=self.df_fcd)

        self.df_fcd_to_save = self.df_fcd.copy() if self.df_fcd is not None else None

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

        t_step.info("Step completed in {et} seconds. {n_fcd} (old: {n_fcd_old}) FCDs, {n_trips} trips, {n_paths} paths",
                    n_fcd=self.df_fcd.shape[0] if self.df_fcd is not None else 0,
                    n_fcd_old=self.old_df_fcd.shape[0] if self.old_df_fcd is not None else 0,
                    n_trips=self.df_trips.shape[0] if self.df_trips is not None else 0,
                    n_paths=self.paths.n_paths())


    def load_graph(self) -> None:
        self.tic.info("Loading graph data...").tic()
        to_reload = self.reload_graph or self.df_links is None or self.df_nodes is None or self.df_turns is None or self.zones is None
        if self.zones is None:
            self.zones = self.loader.zonization

        if self.df_links is None or self.df_nodes is None or self.df_turns is None:
            self.df_links, self.df_nodes, self.df_turns = self.loader.load_df_graph()

        if not to_reload:
            self.graph = DynamicGraph.load(self.tmp_graph.name) if os.path.exists(self.tmp_graph.name) else self.graph
            self.df_links = pd.read_pickle(self.tmp_links.name) if os.path.exists(self.tmp_links.name) else self.df_links
            self.df_nodes = pd.read_pickle(self.tmp_nodes.name) if os.path.exists(self.tmp_nodes.name) else self.df_nodes
            self.df_turns = pd.read_pickle(self.tmp_turns.name) if os.path.exists(self.tmp_turns.name) else self.df_turns
            self.zones = pd.read_pickle(self.tmp_zones.name) if os.path.exists(self.tmp_zones.name) else self.zones
            self.tic.info("Reloaded graph data in {et} seconds")
        else:
            self.graph:DynamicGraph = self.loader.load_graph(
                df_links=self.df_links.fillna({"connector":0}), 
                df_nodes=self.df_nodes.fillna({"centroid":0}), 
                df_turns=self.df_turns)
            if not self.reload_graph:
                self.graph.save(self.tmp_graph.name)
                self.df_links.to_pickle(self.tmp_links.name)
                self.df_nodes.to_pickle(self.tmp_nodes.name)
                self.df_turns.to_pickle(self.tmp_turns.name)
                self.zones.to_pickle(self.tmp_zones.name)
                self.tic.info("Reloaded graph data in {et} seconds")
        
        
        self.graph["t_start"] = self.t
        t_base = self.graph["t_start"]
        t_base = int(round(t_base.hour * 60 + t_base.minute + t_base.second / 60))
        self.graph["t_base"] = t_base
        

        id_links = set(l["idx"] for l in self.graph.get_all_links())
        self.df_links = self.df_links[self.df_links["id"].isin(id_links)]
        id_nodes = set(self.df_links["from_node"].unique()).union(set(self.df_links["to_node"].unique()))
        self.df_nodes = self.df_nodes[self.df_nodes["id"].isin(id_nodes)]   
        for l in self.graph.get_all_links():
            l["fcd_speed"] = DynamicTimeArrayAttribute([0.0])
            l["fcd_n"] = DynamicTimeArrayAttribute([0.0])            

        self.graph.resize_attributes(new_total_time=self.timeslice.total_seconds() // 60, new_delta_t=self.ini.FCD_SPEED_AGGREGATION_INTERVAL)        
        self.tic.info("Loaded graph data in {et} seconds")

    def load_fcd_by_timestamp(self, t_start: datetime, t_end: datetime) -> pd.DataFrame:
        """
        Load FCD data from the database based on the given time range.
        """
        self.tic.info("Loading FCD data...").tic()
        df_fcd = self.fcd_manager.load_fcd_by_timestamp(t_start=t_start, t_end=t_end) 
        if df_fcd is None or df_fcd.empty:
            self.tic.warning("No FCD data found for the given time range")
            return df_fcd
        df_fcd.dropna(subset=["heading"], inplace=True)
        #df_fcd["timestamp"] =df_fcd["timestamp"].dt.tz_convert(self.parser.ini.TZ_LOCAL)
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
        if not self.reload_map_matching_data and self.fcd_manager.mm is not None:
            segments_gdf = self.fcd_manager.mm.segments_gdf
        else:
            segments_gdf = None
        df_fcd = self.fcd_manager.map_matching_fcd(df_fcd=df_fcd, df_links=self.df_links, links_id_col="id",links_direction_col=None, segments_gdf=segments_gdf)
        self.tic.info("Matched {fcd} FCDs in {et} seconds", fcd=df_fcd.shape[0])
        return df_fcd
    
    def build_trips(self, new_df_fcd, old_df_trips, t_end) -> pd.DataFrame:
        self.tic.info("Building Trips...").tic()
        new_df_fcd["new"]=True
        if old_df_trips is not None:
            old_df_trips["new"] = False
        
        if new_df_fcd is None or new_df_fcd.empty:
            new_df_trips = None
            old_df_fcd = None
            self.tic.info("No new FCD data to build trips")
        else:
            new_df_trips, old_df_fcd = self.fcd_manager.build_trips(
                df_fcd=new_df_fcd, 
                t_begin=None, t_finish=None, t_end=t_end)
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
                                     geometry=new_trips.geometry.apply(lambda geom: Point(geom.xy[0][0], geom.xy[1][0])),
                                     crs=new_trips.crs)
            tmp = self.zones[['id', 'geometry']].rename(columns={"id":"id_zone_o"}).copy()
            #tmp["geometry_o"] = tmp["geometry"]
            tmp.set_crs(new_trips.crs, inplace=True)
            joined = gpd.sjoin(gdf_start_points, tmp, how='left', predicate='within')
            new_trips = new_trips.merge(joined[["id_trip","id_zone_o"]].drop_duplicates(subset="id_trip"), on="id_trip", how="left")
        if self.parser.ini.FCD_ROUTING_END_TO_ZONE:
            gdf_start_points = gpd.GeoDataFrame(new_trips.drop(columns='geometry'), 
                                     geometry=new_trips.geometry.apply(lambda geom: Point(geom.xy[0][-1], geom.xy[1][-1])),
                                     crs=df_trips.crs)
            tmp = self.zones[['id', 'geometry']].rename(columns={"id":"id_zone_d"})
            #tmp["geometry_d"] = tmp["geometry"]
            tmp.set_crs(new_trips.crs, inplace=True)
            joined = gpd.sjoin(gdf_start_points, tmp, how='left', predicate='within')
            new_trips = new_trips.merge(joined[["id_trip","id_zone_d"]].drop_duplicates(subset="id_trip"), on="id_trip", how="left")

        new_paths = self.build_paths.calculate_paths(df_links=self.df_links, df_fcd=df_fcd, df_trips=new_trips, G=self.graph)
        for path in new_paths.all_paths():
            costs = list(path.get_costs(self.graph, update_links=True, update_nodes=True, update_turns=True))
            tot_cost = costs[-1]
            path["tot_cost"] = tot_cost
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
        #df["timestamp"] = pd.to_datetime(df["timestamp"]).tz_convert(self.parser.ini.TZ_LOCAL)
        dt = (df["timestamp"]-self.graph["t_start"])
        df["t"] = np.round(dt.dt.total_seconds() / 60).astype("Int16")
        df=df.groupby(["mm_id_link","t"]).agg(speed=("speed", "mean"), n=("speed", "count")).reset_index()
        for i, row in df.iterrows():
            l = self.graph.get_link(row["mm_id_link"])
            fcd_speed = l.get_value("fcd_speed", t=row["t"])
            fcd_n = l.get_value("fcd_n", t=row["t"])
            if fcd_speed is None or fcd_n is None or fcd_n == 0:
                l.set_value("fcd_speed", float(row["speed"]), t=row["t"])
                l.set_value("fcd_n", float(row["n"]), t=row["t"])
            else:
                fcd_speed = (fcd_speed * fcd_n + row["speed"] * row["n"]) / (fcd_n + row["n"])
                fcd_n += row["n"]
                l.set_value("fcd_speed", float(fcd_speed), t=row["t"])
                l.set_value("fcd_n", float(fcd_n), t=row["t"])            
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
            self.ipc.set_data(_df_links=pd.DataFrame(self.df_links),
                              _df_nodes=pd.DataFrame(self.df_nodes), 
                              _df_turns=self.df_turns,                               
                              _paths=self.paths, 
                              _zones=self.zones)
            self.tic.info("Shared data in {et} seconds")
        else:
            self.tic.info("IPC is not initialized. Cannot share data.")
            return
    
    def save_paths(self, paths: PathList, mode) -> None:
        # TODO: Verificare formato con DB
        """
        Save the calculated paths to a file.
        """
        if paths is None or len(paths)== 0:
            self.tic.info("No paths to save")
            return False
        if not self.writer.has("params.fcd_paths"):
            return False
        self.tic.info("Saving paths...").tic()
        df_paths: Optional[gpd.GeoDataFrame] = None
        if self.parser.ini.FCD_ROUTING_CLUSTERING:
            df_paths: gpd.GeoDataFrame = paths.to_pandas(self.graph, self.df_links.crs)
            if df_paths is None or df_paths.shape[0] == 0:
                self.tic.info("No paths to save")
                return False
            PathsClustering(loader=self.loader,writer=self.writer,ipc=self.ipc).run(
                df_paths,
                eps = self.parser.ini.FCD_ROUTING_CLUSTERING_EPS,
                mode=self.mode_paths
            )
            
        if self.parser.ini.FCD_SERVER_WRITE_OUTPUT:  
            if df_paths is None:
                df_paths: gpd.GeoDataFrame = paths.to_pandas(self.graph, self.df_links.crs)          
            if df_paths is None or df_paths.shape[0] == 0:
                self.tic.info("No paths to save")
                return False
            df_paths = df_paths.to_crs(self.build_paths.crs_data)
            if "dt_o" in df_paths.columns:
                df_paths["dt_o"] = df_paths["dt_o"].dt.tz_convert(self.parser.ini.TZ_LOCAL)
            if "dt_d" in df_paths.columns:
                df_paths["dt_d"] = df_paths["dt_d"].dt.tz_convert(self.parser.ini.TZ_LOCAL)
            df_paths["t"] = (np.floor((df_paths["dt_o"].dt.hour * 60 + df_paths["dt_o"].dt.minute)/self.parser.ini.FCD_ROUTING_AGGRATION_INTERVAL) * self.parser.ini.FCD_ROUTING_AGGRATION_INTERVAL).astype("Int64")
            df_paths.drop(["dt_o","dt_d"], axis='columns', inplace=True, errors="ignore")
            df_paths["t_start"] = df_paths["t"].copy()
            df_paths["t_base"] = 0
            
            self.writer.write_paths(df_paths, params="params.fcd_paths", mode=mode, first_query=mode=="w")
            self.tic.info("Saved paths in {et} seconds").tic()

        if self.parser.ini.FCD_SERVER_WRITE_STATE:
            if self.parser.ini.FCD_ROUTING_CLUSTERING:
                paths = KPathList().from_pandas(df_paths)
                self.state_manager.write_state(paths, "fcd_paths")
            else:
                def add_info(path):
                    path["t"] = (np.floor((path["dt_o"].hour * 60 + path["dt_o"].minute)/self.parser.ini.FCD_ROUTING_AGGRATION_INTERVAL) * self.parser.ini.FCD_ROUTING_AGGRATION_INTERVAL).astype(np.int64)
                    path["t_start"] = path["t"]
                    path["t_base"] = 0
                    #path.pop("dt_o", None)
                    #path.pop("dt_d", None)
                    return path
                PathList.apply(paths, add_info) 
                self.state_manager.write_state(paths, "fcd_paths",mode=mode, first_query=mode=="w")
            self.tic.info("Saved state paths in {et} seconds").tic()


        
        return True

    def save_trips(self, df_trips: gpd.GeoDataFrame, mode) -> None:
        """
        Save the calculated paths to a file.
        """
        if self.parser.ini.FCD_SERVER_WRITE_OUTPUT:
            if df_trips is None or df_trips.shape[0] == 0:
                self.tic.info("No trips to save")
                return False
            if not self.writer.has("params.fcd_trips"):
                return False
            self.tic.info("Saving trips...").tic()
            
            df_trips = df_trips.copy()
            df_trips["dt_o"] = df_trips["dt_o"].dt.tz_convert(self.parser.ini.TZ_LOCAL)
            df_trips["dt_d"] = df_trips["dt_d"].dt.tz_convert(self.parser.ini.TZ_LOCAL)
            df_trips["t"]=(np.floor((df_trips["dt_o"].dt.hour*60+df_trips["dt_o"].dt.minute)/self.parser.ini.FCD_ROUTING_AGGRATION_INTERVAL)*self.parser.ini.FCD_ROUTING_AGGRATION_INTERVAL).astype("Int64")
            df_trips.drop(columns=["new"], inplace=True, errors="ignore")
            if df_trips is None or df_trips.shape[0] == 0:
                self.tic.info("No trips to save")
                return False
            else:
                df_trips = df_trips.to_crs(self.build_paths.crs_data)
            
            self.writer.write(df_trips,"params.fcd_trips", mode=mode, first_query=mode=="w")
            self.tic.info("Saved trips in {et} seconds")
        return True
    
    def save_fcd(self, df_fcd: gpd.GeoDataFrame, mode) -> None:
        """
        Save the calculated paths to a file.
        """
        if self.parser.ini.FCD_SERVER_WRITE_OUTPUT:
            if df_fcd is None or df_fcd.shape[0] == 0:
                self.tic.info("No FCD to save")
                return False        
            if not self.writer.has("params.fcd_fcd"):
                return False
            self.tic.info("Saving FCD...").tic()
            df_fcd = df_fcd.copy()
            df_fcd["timestamp"] = df_fcd["timestamp"].dt.tz_convert(self.parser.ini.TZ_LOCAL)
            df_fcd["t"]=(np.floor((df_fcd["timestamp"].dt.hour*60+df_fcd["timestamp"].dt.minute)/self.parser.ini.FCD_ROUTING_AGGRATION_INTERVAL)*self.parser.ini.FCD_ROUTING_AGGRATION_INTERVAL).astype("Int64")
            df_fcd.drop(columns=["new","x","y"], inplace=True, errors="ignore")
            df_fcd = df_fcd.to_crs(self.build_paths.crs_data)
            
            self.writer.write(df_fcd,"params.fcd_fcd", mode=mode, first_query=mode=="w")
            self.tic.info("Saved FCD in {et} seconds")
        return True

    def save_all_graph(self, graph: AbstractGraph, mode) -> None:
        """
        Save the calculated paths to a file.
        """
        if self.parser.ini.FCD_SERVER_WRITE_OUTPUT:
            self.tic.info("Saving Graph...").tic()
            if graph is None:
                self.tic.info("No Graph to save")
                return False
            self.graph["t_start"] = to_datetime_auto(self.graph["t_start"], tz_localize=self.parser.ini.TZ_CALC, tz_convert=self.parser.ini.TZ_LOCAL)
            t_base = self.graph["t_start"]
            t_base = (np.floor((t_base.hour * 60 + t_base.minute)/self.parser.ini.FCD_ROUTING_AGGRATION_INTERVAL) * self.parser.ini.FCD_ROUTING_AGGRATION_INTERVAL).astype("Int64") 
            self.graph["t_base"] = t_base

            #graph.apply_links(
            #    lambda x: x.set_value("geometry", x.get_value("geometry", t=None).to_crs(self.parser.ini.CRS), t=None),
            #)
        
            if self.writer.has("params.fcd_graph"):
                self.writer.write(graph,"params.fcd_graph", mode=mode, first_query=mode=="w")
            self.tic.info("Saved Graph in {et} seconds").tic()
            return True
        
    def save_graph(self, graph: AbstractGraph, mode) -> None:
        #TODO: salvare solo i dati modificati in json o altro
        # TODO: Verificare formato con DB
        """
        Save the calculated paths to a file.
        """
        if self.parser.ini.FCD_SERVER_WRITE_OUTPUT:
            self.tic.info("Saving Graph...").tic()
            if graph is None:
                self.tic.info("No Graph to save")
                return False
            updated_links = []
            self.graph["t_start"] = to_datetime_auto(self.graph["t_start"], tz_localize=self.parser.ini.TZ_CALC, tz_convert=self.parser.ini.TZ_LOCAL)
            t_base = self.graph["t_start"]
            t_base = int(round(t_base.hour * 60 + t_base.minute + t_base.second / 60))
            self.graph["t_base"] = t_base
            for l in graph.get_all_links():
                if "fcd_n" not in l:
                    continue
                fcd_n = l.get_values("fcd_n")
                if sum(fcd_n)==0:
                    continue
                updated_links.append({
                    "id": l["idx"],
                    "fcd_n": fcd_n,
                    "fcd_speed": l.get_values("fcd_speed"),
                    "t_base": t_base,
                })
            df = pd.DataFrame(updated_links)
            if df.empty:
                self.tic.info("No Graph to save")
                return False
            if self.writer.has("params.fcd_graph"):
                self.writer.write(df,"params.fcd_graph", mode=mode)
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
            
    


