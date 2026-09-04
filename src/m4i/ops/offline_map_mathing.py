from trycode.model4italy_client import params
import time
from .op import OP
from ..graphs.abstract_graph import AbstractGraph
from ..connectors import Loader, Writer
from ..fcd.map_matching import MapMatching
from ..utils import TicToc

from datetime import datetime, timedelta
from typing import Union
import pandas as pd
import geopandas as gpd
import numpy as np


class OfflineMapMatching(OP):
    def __init__(self, loader: Loader, writer: Writer, **kwargs):
        super().__init__(loader, writer, task_steps=1, **kwargs)
        self.tic: TicToc = TicToc()
        self.df_fcd: gpd.GeoDataFrame = None
        self.df_links: gpd.GeoDataFrame = None
        self.graph: AbstractGraph = self.loader.G

        self.map_matching = MapMatching(
            self.graph,
            links_id_col="idx",
            links_direction_col=None,
        )

    def run(self):
        t_start = self.parser.get("date_start")
        t_end = self.parser.get("date_end")
        horizon = self.ini.FCD_SERVER_FCD_HORIZON
        tic = self.tic.get().info("Elaborating period...")
        assert isinstance(t_start, (str, int, datetime)), "date_start must be a string, int or datetime"
        assert isinstance(t_end, (str, int, datetime)), "date_end must be a string, int or datetime"
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
            if self.save_paths(paths=path_to_save, path_parameters="params.rt_paths", mode=mode):
                mode = "a"
            for path in path_to_save.all_paths():
                self.paths.delete(path)
            ts = te
            te = ts + horizon
        self.map_matching.run()
        self.task_step_done("Map matching completed")

    def step(
        self,
        t_start: Union[str, int, datetime] = None,
        t_end: Union[str, int, datetime] = None,
        horizon: Union[str, int, timedelta] = None,
        share_on_ipc: bool = True,
        clean: bool = True,
    ):
        t_step = self.tic.get().info("Performing step...")
        if t_start is not None:
            t_start = self.to_datetime(t_start)
        if t_end is not None:
            t_end = self.to_datetime(t_end)
        if horizon is not None:
            horizon = self.to_timedelta(horizon)

        if t_start is None and t_end is None:
            t_end = datetime.now()
            horizon = horizon or timedelta(minutes=self.parser.ini.FCD_SERVER_FCD_HORIZON)
            t_start = t_end - horizon
        elif t_start is None and t_end is not None:
            t_end = t_end
            horizon = horizon or timedelta(minutes=self.parser.ini.FCD_SERVER_FCD_HORIZON)
            t_start = t_end - horizon
        elif t_start is not None and t_end is None:
            horizon = horizon or timedelta(minutes=self.parser.ini.FCD_SERVER_FCD_HORIZON)
            t_end = t_start + horizon
        elif t_start is not None and t_end is not None:
            if t_start >= t_end:
                raise ValueError("t_start must be less than t_end")
            horizon = t_end - t_start

        self.tic.info(
            "Step from {t_start} to {t_end} with horizon {horizon}",
            t_start=t_start,
            t_end=t_end,
            horizon=horizon,
        )
        self.t = int((t_start - t_start.replace(hour=0, minute=0, second=0, microsecond=0)).total_seconds() // 60)
        self.load_graph(share_on_ipc=share_on_ipc)

    def load_graph(self, share_on_ipc: bool = True) -> None:
        """
        Load the road network graph from the database.
        """
        self.tic.info("Loading graph data...").tic()
        load_from_ipc = self.ipc is not None and share_on_ipc
        if load_from_ipc:
            if self.ipc.get("_df_links") is not None:
                self.tic.info("Loading df_links from IPC...")
                self.df_links = self.ipc.get("_df_links")
                self.df_links = gpd.GeoDataFrame(self.df_links, crs=self.parser.ini.CRS_CALC)
            if self.ipc.get("_df_nodes") is not None:
                self.tic.info("Loading df_nodes from IPC...")
                self.df_nodes = self.ipc.get("_df_nodes")
                self.df_nodes = gpd.GeoDataFrame(self.df_nodes, crs=self.parser.ini.CRS_CALC)
            if self.ipc.get("_df_turns") is not None:
                self.tic.info("Loading df_turns from IPC...")
                self.df_turns = self.ipc.get("_df_turns")

        if self.df_links is None or self.df_nodes is None or self.df_turns is None:
            self.df_links, self.df_nodes, self.df_turns = self.loader.load_df_graph()
        self.graph = self.loader.load_graph(df_links=self.df_links, df_nodes=self.df_nodes, df_turns=self.df_turns)
        id_links = set(l["idx"] for l in self.graph.get_all_links())
        self.df_links = self.df_links[self.df_links["id"].isin(id_links)]
        id_nodes = set(self.df_links["from_node"].unique()).union(set(self.df_links["to_node"].unique()))
        self.df_nodes = self.df_nodes[self.df_nodes["id"].isin(id_nodes)]

        self.tic.info("Loaded graph data in {et} seconds")

    def to_datetime(self, t: Union[str, int, datetime]) -> datetime:
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
        elif isinstance(t, (float, int)):
            t = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(minutes=t)
        return t

    def to_timedelta(self, t: Union[str, int, datetime]) -> timedelta:
        """
        Convert a string or int to a datetime object.
        """
        if isinstance(t, str):
            if t.isnumeric():
                t = timedelta(minutes=float(t))
            else:
                raise ValueError("Invalid timedelta format. Use a number.")
        elif isinstance(t, (float, int)):
            t = timedelta(minutes=t)
        return t
