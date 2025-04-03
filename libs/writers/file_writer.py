# -*- coding: utf-8 -*-
"""
Created on Thu Jun 24 19:11:39 2021

@author: andge
"""
import pandas as pd
import numpy as np
import geopandas as gpd
from ast import literal_eval
from typing import *
import os
import json
from os.path import join
from shapely import MultiLineString


from ..utils import export_dataframe, import_dataframe, multi_line_to_line
from ..graphs import KPathContainer
from . import BaseWriter
from ..loaders import BaseLoader
from .. import IniClass
from .. import Logger
class FileWriter(BaseWriter):

    def __init__(self, params: Union[str, dict], settings: IniClass=None, loader: BaseLoader=None):
        super().__init__(params=params, settings=settings, loader=loader, default_ext=".csv")

    def _write(self, param, results, mode="w", partition=None, **kwargs):
        if results is None:
            self.log.warning(f"No {param} to write")
            return
        kwargs.setdefault("index",False)
        location, src = self.get_location_src(param, **kwargs)
        
        if location is None:
            raise Exception("'location' not defined")
        if src is None:
            raise Exception("'src' not defined")

        filename = os.path.normpath(join(location,src))        
        if partition is not None:
            location = join(filename,partition)
            filename = os.path.basename(filename)
            filename = join(location,filename)

        location = os.path.dirname(filename)
            
        os.makedirs(location, exist_ok=True)
        export_dataframe(results, filename, mode=mode, **kwargs)

    def _load(self, param,  mapping: dict[str,str]=None, partition=None, **kwargs) -> Union[pd.DataFrame, gpd.GeoDataFrame, dict]:
        location, src = self.get_location_src(param, **kwargs)
        if location:
            if partition:
                location = join(location,partition)
            src = join(location, src)
        if src.lower().endswith(".json"):
            with open(src,'r') as f:
                content = json._load(f)
            return content
        else:        
            df = import_dataframe(src)
            if mapping:
                df = BaseLoader.apply_mapping(df=df,mapping=mapping)
            return df
        
    def write_agg_results(self, results: pd.DataFrame, mode=None, partition=None, **kwargs):
        self._write("aggregated_results", results, mode=mode, partition=partition, **kwargs)
          
    def write_sim_results(self, results: pd.DataFrame, mode=None, partition=None, **kwargs):
        self._write("sim_results", results,mode=mode, partition=partition, **kwargs)

    def write_stat_results(self, results: pd.DataFrame, mode=None, partition=None, **kwargs):
        self._write("stat_results", results,mode=mode, partition=partition, **kwargs)

    def write_paths(self, results: gpd.GeoDataFrame, mode=None, partition=None, **kwargs):
        self._write("paths", results, mode=mode, partition=partition, **kwargs)

    def load_paths(self, mapping: dict[str,str]=None, partition=None, **kwargs) -> gpd.GeoDataFrame:
        df = self._load("paths", mapping=mapping, partition=partition, **kwargs)
        return df
        
    def load_agg_results(self, partition=None, **kwargs) -> Union[pd.DataFrame,gpd.GeoDataFrame]:
        df = self._load("aggregated_results", partition=partition, **kwargs)
        return df
    
    def load_sim_results(self, partition=None, **kwargs) -> Union[pd.DataFrame,gpd.GeoDataFrame]:
        df = self._load("sim_results", partition=partition, **kwargs)
        return df
    
    def load_stat_results(self, partition=None, **kwargs) -> Union[pd.DataFrame,gpd.GeoDataFrame]:
        df = self._load("stat_results", partition=partition, **kwargs)
        return df


    
