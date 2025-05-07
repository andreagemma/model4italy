from __future__ import annotations
import logging
import __future__
from numbers import Number
import os
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
from .. import ParamsParser, Loader,  Logger
from ..utils import export_dataframe, TicToc, multi_line_to_line
from ..utils.ipc import IPC
from .. import Logger

class FCDServer:
    """
    FCDServer is a class that handles the matching of Floating Car Data (FCD) to a road network.
    It uses a Map Matching algorithm to align the FCD points with the nearest road segments.
    """
    def __init__(self, parser: ParamsParser, ipc:IPC=None):
        self.log: logging.Logger = Logger.getLogger("M4I")
        self.tic: TicToc = TicToc(logger=self.log)
        self.parser: ParamsParser = parser
        self.loader: Loader = Loader(parser=parser)
        self.build_paths = BuildPaths(parser=self.parser, 
                                      loader=self.loader, 
                                      n_workers_mm=parser.ini.FCD_MAP_MATCHING_CPUS, 
                                      n_workers_pm=parser.ini.FCD_PATH_MATCHING_CPUS,
                                      max_distance=parser.ini.FCD_MAP_MATCHING_MAX_DISTANCE,
                                      max_angle=parser.ini.FCD_MAP_MATCHING_MAX_ANGLE,
                                      crs_calc=parser.ini.FCD_CRS_CALC,
                                      crs_data=parser.ini.FCD_CRS_CALC,
                                      )
        self.ipc: IPC = ipc
        self.df_links: gpd.GeoDataFrame = None
        self.df_nodes: gpd.GeoDataFrame = None
        self.df_turns: gpd.GeoDataFrame = None
        self.graph: AbstractGraph = None
        self.paths: PathList = PathList(key=lambda x: x.get("id_trip"))
        self.df_fcd: gpd.GeoDataFrame = None
        self.df_trips: gpd.GeoDataFrame = None
        self.t:int = 0


    def step(self, t_end: datetime) -> None:
        """
        Perform a step in the FCD processing pipeline.
        """
        t_step=self.tic.get().info("Performing step...")
        horizon = timedelta(minutes=self.parser.ini.FCD_TIMESLICE)
        t_start: datetime = t_end - horizon
        self.t = int((t_start-t_start.replace(hour=0, minute=0, second=0, microsecond=0)).total_seconds() // 60)
        self.load_graph()
        self.build_paths.load_graph(df_links=self.df_links)
        new_df_fcd = self.load_fcd_by_timetamp(t_start=t_start, t_end=t_end)                    
        self.match_fcd(fcd_data=new_df_fcd, old_fcd_data=self.df_fcd)
        self.clean(t_end=t_end)
        self.update_speed(df_fcd=self.df_fcd)
        self.calculate_paths(df_fcd=self.df_fcd, df_trips=self.df_trips)        
        self.share_data()
        t_step.info("Step completed in {et} seconds")

    def paths_to_pandas(self) -> gpd.GeoDataFrame:
        return self.paths.to_pandas(self.graph, self.df_links.crs)
    
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
        self.paths = self.paths.filter(lambda x: x.get("t") >= t) # remove paths older than t_start
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
        
    def load_graph(self):
        """
        Load the road network graph from the database.
        """
        self.tic.info("Loading graph data...").tic()
        load_from_ipc = self.ipc is not None
        if load_from_ipc:
            if self.ipc.get("graph") is not None:
                self.tic.info("Loading graph from IPC...")
                self.graph = self.ipc.get("graph")
                self.zones = self.ipc.get("zones")
                self.df_links = self.ipc.get("df_links")
                self.df_nodes = self.ipc.get("df_nodes")
                self.df_turns = self.ipc.get("df_turns")
                self.tic.info("Loaded graph data in {et} seconds")
                return
            else:
                self.tic.info("Graph not found in IPC, loading from data laoder...")
        self.df_links, self.df_nodes, self.df_turns = self.loader.load_df_graph()
        self.df_nodes = gpd.GeoDataFrame(self.df_nodes, crs=self.parser.ini.FCD_CRS_DATA).to_crs(self.parser.ini.FCD_CRS_CALC)
        self.df_links = gpd.GeoDataFrame(self.df_links, crs=self.parser.ini.FCD_CRS_DATA).to_crs(self.parser.ini.FCD_CRS_CALC)
        self.graph = self.loader.load_graph(df_links=self.df_links, df_nodes=self.df_nodes, df_turns=self.df_turns)
        id_links = set(l["idx"] for l in self.graph.get_all_links())
        self.df_links = self.df_links[self.df_links["id"].isin(id_links)]
        id_nodes = set(self.df_links["from_node"].unique()).union(set(self.df_links["to_node"].unique()))
        self.df_nodes = self.df_nodes[self.df_nodes["id"].isin(id_nodes)]
        self.zones = self.loader.zonization.to_crs(self.parser.ini.FCD_CRS_CALC)
        
        self.tic.info("Loaded graph data in {et} seconds")

    def share_data(self):
        if self.ipc is not None:
            self.tic.info("Sharing data...").tic()
            self.ipc.set_data(df_links=self.df_links,
                              df_nodes=self.df_nodes, 
                              df_turns=self.df_turns, 
                              graph=self.graph,
                              paths=self.paths, 
                              zones=self.zones)
            self.tic.info("Shared data in {et} seconds")

    def calculate_paths(self, df_fcd: gpd.GeoDataFrame, df_trips: gpd.GeoDataFrame) -> PathList:
        """
        Calculate paths for the matched FCD data using the road network graph.
        """        
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

        tot_paths = self.build_paths.calculate_paths(df_links=self.df_links, df_fcd=df_fcd, df_trips=new_trips, G=self.graph)
        for path in tot_paths.all_paths():
            costs = list(path.get_costs(self.graph, update_links=True, update_nodes=True, update_turns=True))
            tot_cost = costs[-1]
            path["tot_cost"] = tot_cost
            path["t"] = self.t
            path["t_start"] = self.t
            path["t_base"] = 0
            path["closed"] = False
            self.paths.add_path(path)
        df_trips["new"] = False
        self.tic.info("Calculated {n_trips} paths in {et} seconds ({tot_paths})", n_trips=tot_paths.n_paths(), tot_paths=tot_paths.n_paths())
        return tot_paths
    
    def save_paths(self, paths: PathList, filename: str):
        """
        Save the calculated paths to a file.
        """
        self.tic.info("Saving paths...").tic()
        df_paths: gpd.GeoDataFrame = paths.to_pandas(self.graph, self.df_links.crs)
        if df_paths is None:
            self.tic.info("No paths to save")
            return
        else:
            df_paths = df_paths.to_crs(self.build_paths.crs_data)
        export_dataframe(df_paths, filename, layer="paths", mode="w")
        self.tic.info("Saved paths in {et} seconds")
    

