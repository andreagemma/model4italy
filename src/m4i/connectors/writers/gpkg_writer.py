# -*- coding: utf-8 -*-
"""
Created on Thu Jun 24 19:11:39 2021

@author: andge
"""

import pandas as pd
import numpy as np
import geopandas as gpd
from typing import *
import os
import sqlite3
from shapely import MultiLineString, get_geometry
from ast import literal_eval
from shapely import wkt
from ast import literal_eval

from ...utils import export_dataframe, multi_line_to_line
from . import BaseWriter
from ...graphs import KPathContainer
from .. import Loader
from ... import IniClass

from ...log import Logger


class GpkgWriter(BaseWriter):
    def __init__(
        self, params: Union[str, dict], settings: IniClass = None, loader: Loader = None
    ):
        super().__init__(
            params=params, settings=settings, loader=loader, default_ext=".gpkg"
        )

    def _write(self, param, results, mode="w", **kwargs):
        if results is None:
            self.log.warning(f"No {param} to write")
            return

        location, src = self.get_location_src(param, **kwargs)

        if location is None:
            raise Exception("'location' not defined")
        if src is None:
            raise Exception("'src' not defined")

        if location.lower().endswith("gpkg") or isinstance(results, gpd.GeoDataFrame):
            if "geometry" in results.columns:
                results = gpd.GeoDataFrame(results, crs="EPSG:4326")
            else:
                results = gpd.GeoDataFrame(results)
            results.to_file(location, layer=src, driver="GPKG", index=False, mode=mode)
        else:
            with sqlite3.connect(location) as conn:
                results.to_sql(
                    src,
                    con=conn,
                    if_exists="replace" if mode == "w" else "append",
                    index=False,
                )

    def _load(
        self, param, mapping: dict[str, str] = None, **kwargs
    ) -> Union[pd.DataFrame, gpd.GeoDataFrame, dict]:
        location, src = self.get_location_src(param, **kwargs)

        if location is None:
            raise Exception("'location' not defined")
        if src is None:
            raise Exception("'src' not defined")

        if src.lower().endswith("gpkg"):
            df = gpd.read_file(filename=location, layer=src)
            if not "geometry" in df.columns:
                df = pd.DataFrame(df)
        else:
            with sqlite3.connect(location) as conn:
                sql = f"select * from {src} as t"
                df = pd.read_sql_query(sql=sql, con=conn)

        if mapping:
            df = Loader.apply_mapping(df=df, mapping=mapping)

        return df

    def write_agg_results(self, results: gpd.GeoDataFrame, **kwargs):
        self._write("aggregated_results", results, **kwargs)

    def write_sim_results(self, results: pd.DataFrame, **kwargs):
        self._write("sim_results", results, **kwargs)

    def write_stat_results(self, results: pd.DataFrame, **kwargs):
        self._write("stat_results", results, **kwargs)

    def write_paths(self, results: gpd.GeoDataFrame, **kwargs):
        self._write("paths", results, **kwargs)

    def load_paths(self, mapping: dict[str, str] = None, **kwargs) -> gpd.GeoDataFrame:
        df = self._load(param="paths", mapping=mapping, **kwargs)

        df["links"] = df["links"].apply(literal_eval)
        if "costs" in df.columns:
            df["costs"] = df["costs"].apply(literal_eval)
        return df

    def load_agg_results(self, mapping: dict[str, str], **kwargs) -> gpd.GeoDataFrame:
        df = self._load(param="aggregated_results", mapping=mapping, **kwargs)
        return df

    def load_stat_results(self, mapping: dict[str, str], **kwargs) -> gpd.GeoDataFrame:
        df = self._load(param="stat_results", mapping=mapping, **kwargs)
        return df

    def load_sim_results(self, mapping: dict[str, str], **kwargs) -> gpd.GeoDataFrame:
        df = self._load(param="sim_results", mapping=mapping, **kwargs)
        return df
