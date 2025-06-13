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
import sqlalchemy as sa

from ...log import Logger

class DBWriter(BaseWriter):

    def __init__(self, params: Union[str, dict], settings: IniClass=None, loader: Loader=None):
        super().__init__(params=params, settings=settings, loader=loader, default_ext=".gpkg")

    def _write(self, param, results, mode="w", **kwargs):          

        if results is None:
            self.log.warning(f"No {param} to write")
            return
        
        location, src = self.get_location_src(param, **kwargs)
        
        if location is None:
            raise Exception("'location' not defined")
        if src is None:
            raise Exception("'src' not defined")
        
        engine = sa.create_engine(location)
        with engine.connect() as conn:
            simulation_id = self.loader.dparams.get("simulation_id")
            results["simulation_id"] = simulation_id    
            table = src.get("table")
            mapping = src.get("mapping")        
            if simulation_id is not None:
                conn.execute(sa.text(f"delete from {table} where simulation_id = {simulation_id}"))
            results = results.rename(columns=mapping)

            geom = mapping.get("geometry")
            if isinstance(results, gpd.GeoDataFrame):                
                if geom not in results.columns:
                    results = pd.DataFrame(results)
                else:
                    results.set_geometry(geom, inplace=True)
            elif isinstance(results, pd.DataFrame):
                if geom in results.columns:
                    results[geom] = results[geom].apply(lambda x: wkt.loads(x) if isinstance(x, str) else x)
                    results = gpd.GeoDataFrame(results, geometry=geom, crs=self.loader)                
            

            schema_table = table.split(".")
            if len(schema_table) == 2:
                schema, table = schema_table
            else:
                schema = None
                table = schema_table[0]
            if mode=="w":
                conn.execute(sa.text(f"delete from {schema}.{table} where simulation_id = {simulation_id}"))
                
            if isinstance(results, gpd.GeoDataFrame):  
                results.to_postgis(table, schema=schema, con=conn, if_exists="append", chunksize=100, index=False)
            else:
                results.to_sql(table, schema=schema, con=conn, if_exists="append",method="multi", chunksize=1000, index=False)

            conn.commit()
            

    def _load(self, param,  mapping: dict[str,str]=None, **kwargs) -> Union[pd.DataFrame, gpd.GeoDataFrame, dict]:
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
                df = pd.read_sql_query(sql=sql,con=conn)

        if mapping:
            df = Loader.apply_mapping(df=df,mapping=mapping)

        return df
 
    def write_agg_results(self, results: gpd.GeoDataFrame, **kwargs):
        self._write("aggregated_results", results, **kwargs)        
                
    def write_sim_results(self, results: pd.DataFrame, **kwargs):
        self._write("sim_results", results, **kwargs)
        
    def write_stat_results(self, results: pd.DataFrame, **kwargs):
        self._write("stat_results", results, **kwargs)
        
    def write_paths(self, results: gpd.GeoDataFrame, **kwargs):
        self._write("paths", results, **kwargs)
        
    def load_paths(self, mapping: dict[str,str]=None, **kwargs) -> gpd.GeoDataFrame:
        df = self._load(param="paths", mapping=mapping, **kwargs)

        df["links"] = df["links"].apply(literal_eval)
        if "costs" in df.columns:
            df["costs"] = df["costs"].apply(literal_eval)        
        return df
        
    def load_agg_results(self, mapping: dict[str,str], **kwargs) ->gpd.GeoDataFrame:
        df = self._load(param="aggregated_results", mapping=mapping, **kwargs)
        return df           
    
    def load_stat_results(self, mapping: dict[str,str], **kwargs) ->gpd.GeoDataFrame:
        df = self._load(param="stat_results", mapping=mapping, **kwargs)
        return df           

    def load_sim_results(self, mapping: dict[str,str], **kwargs) ->gpd.GeoDataFrame:
        df = self._load(param="sim_results", mapping=mapping, **kwargs)
        return df           
