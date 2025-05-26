# -*- coding: utf-8 -*-
"""
Created on Thu Jun 24 19:11:39 2021

@author: andge
"""
from __future__ import annotations


import pandas as pd
import numpy as np
import geopandas as gpd
from typing import Union, Any
from collections import namedtuple, defaultdict
import json
from datetime import datetime
import ast
from importlib import import_module
from abc import ABC, abstractmethod

from ...matrix_od import MatrixODT
from ...graphs import DynamicGraph, TimeArrayAttribute, CallableAttribute, KPathContainer
from ...utils import util
from .. import Loader
from ... import IniClass
from ... import Logger

class BaseWriter(ABC):

    def __init__(self, params: Union[str, dict], settings: IniClass=None, loader: Loader=None, default_ext=".dat"):
        self.log = Logger.getLogger(self.__class__.__name__, execution_id=params.get("execution_id"))
        self.ini: IniClass = settings
        self.loader: Loader = loader
        self.default_ext = default_ext

    def get_parametric_name(self, name, **kwargs):
        return self.loader.get_parametric_name(name, **kwargs)
        
    def get_location_src(self, param, **kwargs):
        params = self.loader.dparams.get("params",{}).get("output",{}).copy()
        src = params.get(param)

        try:
            if src is None:
                return None, None
            elif isinstance(src, str):
                params["src"] = src
            elif isinstance(src, dict):
                params.update(src)
            else:            
                self.log.error(f"source {src} not found. String and dictionary {{'location': ... 'src': ... }} required")
                return None, None
        except Exception as e:
            self.log.error(f"Error getting location and source: {e}")
            return None, None
        location, src = params.get("location"), params.get("src")

        if src is not None:
            src = self.get_parametric_name(src, **kwargs)
        if location is not None:
            location = self.get_parametric_name(location, **kwargs)

        return location, src

    def has_write_agg_results(self):
        location, src = self.get_location_src("aggregated_results")
        return (location is not None) and (src is not None)

    def has_write_sim_results(self):
        location, src = self.get_location_src("sim_results")
        return (location is not None) and (src is not None)
            
    def has_write_stat_results(self):
        location, src = self.get_location_src("stat_results")
        return (location is not None) and (src is not None)

    def has_write_paths(self):
        location, src = self.get_location_src("paths")
        return (location is not None) and (src is not None)

    def has_write_state(self):
        location, src = self.get_location_src("state")
        return (location is not None) and (src is not None)
    
    @staticmethod
    def get_cls_by_name(class_name) -> BaseWriter:                
        module = import_module("libs.connectors")
        cls = getattr(module, class_name)
        return cls

    @abstractmethod    
    def write_agg_results(self, results: gpd.GeoDataFrame, **kwargs):
        self.log.warning("write_agg_results doesn't implemented")
    
    @abstractmethod
    def write_sim_results(self, results: pd.DataFrame, **kwargs):
        self.log.warning("write_sim_results doesn't implemented")
    
    @abstractmethod
    def write_stat_results(self, results: pd.DataFrame, **kwargs):
        self.log.warning("write_stat_results doesn't implemented")

    @abstractmethod
    def write_paths(self, results: gpd.GeoDataFrame, **kwargs):
        self.log.warning("write_agg_results doesn't implemented")

    @abstractmethod
    def load_agg_results(self, src: Any) -> gpd.GeoDataFrame:
        self.log.warning("write_agg_results doesn't implemented")

    @abstractmethod
    def load_sim_results(self, src: Any) -> gpd.GeoDataFrame:
        self.log.warning("write_agg_results doesn't implemented")

    @abstractmethod
    def load_stat_results(self, src: Any) -> gpd.GeoDataFrame:
        self.log.warning("write_agg_results doesn't implemented")

    @abstractmethod
    def load_paths(self, src: Any) -> gpd.GeoDataFrame:
        self.log.warning("write_agg_results doesn't implemented")

    def debug(self, *args, **kwargs):
        self.log.debug(*args, **kwargs)

    def info(self, *args, **kwargs):
        self.log.info(*args, **kwargs)

    def warning(self, *args, **kwargs):
        self.log.warning(*args, **kwargs)

    def error(self, *args, **kwargs):
        self.log.error(*args, **kwargs)

    def state(self, *args, **kwargs):
        self.log.info(*args, **kwargs)

    def write_convergence(self, *args, **kwargs):
        self.log.info(*args, **kwargs)
