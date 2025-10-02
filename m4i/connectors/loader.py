# -*- coding: utf-8 -*-
"""
Created on Thu Jun 24 19:11:39 2021

@author: andge
"""
from __future__ import annotations


import operator
import pandas as pd
import numpy as np
import geopandas as gpd
import re
import shapely
import time
from typing import Union, Any
from collections import namedtuple, defaultdict
import json
from datetime import datetime, date
import ast
from abc import ABC, abstractmethod
from itertools import product
from importlib import import_module
from os.path import join

import warnings
import websockets.sync.client

from ..utils.util import to_datetime_auto, hhmm2min, min2hhmm, normalize_name
from ..matrix import MatrixODT, MatrixOD
from ..graphs import DynamicGraph, DynamicTimeArrayAttribute, DynamicCallableAttribute, KPathList, Path, KPathContainer
from ..utils import util
from .. import IniClass
from ..log import Logger
from ..utils import import_dataframe, filters_to_query_expression, rename_filters
from ..utils.ipc.ipc import IPC
from ..params_parser import ParamsParser
from .loaders.base_loader import BaseLoader
from shapely import from_wkb, from_wkt, from_geojson

import copy

class Loader(BaseLoader):

    def __init__(self, parser: ParamsParser, logger: Logger = None, tstart:int = None, tend:int = None):    
        self.execution_id = parser.get("execution_id")
        logger_name = f"{parser.ini.LOG_NAME}.{self.__class__.__name__}"
        if self.execution_id is None:
            self.log = logger or Logger.getLogger(logger_name)
        else:
            self.log = logger or Logger.getLogger(logger_name, execution_id=self.execution_id)

        self._origins: list[int] = None
        self._destinations: list[int] = None
        self._zones: list[int] = None
        self._sign_nodes: list[dict] = None
        self._OD: MatrixODT = None  # dict[VehicleClass,Matrix]
        self._ODs: dict[Any, MatrixODT] = None  # dict[VehicleClass,Matrix]
        self._detectors: pd.DataFrame = None
        self._counts: dict[str,pd.DataFrame] = None
        self._G: DynamicGraph = None
        self._links_sets: dict[str, list[int]] = None
        self._perc: dict[int, MatrixODT] = None
        self._events: dict[str, list[dict]] = None
        self._coefficients: dict = None
        self._modes: dict = None
        self._m_paths:KPathContainer = None
        self._bounds: shapely.geometry.Polygon = None
        self._zonization: gpd.GeoDataFrame = None
        self._df_links: pd.DataFrame = None
        self._df_nodes: pd.DataFrame = None
        self._df_turns: pd.DataFrame = None
        
        self.ini: IniClass = parser.ini
        self.params: namedtuple
        self.dparams: dict = None
        self.delta_t: int = self.ini.DELTA_T
        self.conv_tbl: pd.DataFrame = None
        self.parser = parser
        self.update_params(tstart = tstart, tend = tend)

        self.attr_to_share = ["_origins", "_destinations", "_zones", "_sign_nodes", "_OD", "_ODs",
                              "_detectors", "_counts", "_G", "_links_sets", "_perc", "_events", "_coefficients", "_modes", "_m_paths", "_bounds", "_zonization",
                              "_df_links", "_df_nodes", "_df_turns",
                              "dparams", "delta_t", "conv_tbl", "timestamps"]
        
    def recreate(self, tstart:int=None, tend:int = None) -> Loader:
        """
        Create a clone of the current Loader instance.
        :return: A new Loader instance with the same parameters and state.
        """
        new_loader = Loader(parser=self.parser.clone(), logger=self.log, tstart=tstart, tend=tend)
        return new_loader
    
    def reset(self, tstart:int=None, tend:int = None):
        for attr in self.attr_to_share:
            setattr(self, attr, None)
        self.delta_t = self.ini.DELTA_T
        self.update_params(tstart=tstart, tend=tend)
    

    def set_start_end(self, start: int = None, end: int = None):
        """
        Set the timestamps for the loader.
        :param start: Start time in minutes from midnight.
        :param end: End time in minutes from midnight.
        :param delta_t: Time step in minutes.
        """
        self.parser.params = copy.deepcopy(self.parser.params)
        self.parser.params["start"] = min2hhmm(start) if start is not None else self.start
        self.parser.params["end"] = min2hhmm(end) if end is not None else self.end
        self.reset()
        
    def filters_to_query_expression(filters: list[list[tuple[str, str, Any]]]) -> str:
        return filters_to_query_expression(filters=filters)

    def _load_dataset(self, parameters: dict, filters=None, dtype=None, geometry:str = None) -> Union[pd.DataFrame, gpd.GeoDataFrame]:
        """
        Load a dataset based on the provided parameters.
        """
        if "connector" not in parameters or parameters["connector"] is None:
            raise ValueError("Missing 'connector' parameter")
        cls_name = parameters.get("connector")
        ClassLoader = Loader.get_cls_by_name(cls_name)
        loader = ClassLoader()
        parameters = copy.deepcopy(parameters)
        """
        for k, v in parameters.items():
            if isinstance(v, (str, int, float)):
                parameters[k] = self.parser.get_parametric_name(v)
        """
        mapping = parameters.get("mapping")
        if filters is not None:
            filters = rename_filters(filters=filters, rename=mapping)
        if dtype is not None:
            dtype_inverse = {mapping.get(k, k): v for k, v in dtype.items()}
        else:
            dtype_inverse = None
        kwargs = copy.deepcopy(parameters)
        kwargs.pop("connector", None)
        kwargs.pop("mapping", None)
        kwargs.pop("filters", None)
        kwargs.pop("partition_cols", None)
        kwargs.pop("additional_fields", None)
        kwargs.pop("src", None)
        kwargs.pop("location", None)
        kwargs.pop("source", None)
        df = loader.load_dataset(parameters=parameters, filters=filters, dtype=dtype_inverse,**kwargs)
        if df is None:
            return None
        if mapping:            
            df = self.parser.apply_mapping(df=df, mapping=mapping)
        if additional_fields := parameters.get("additional_fields", None):
            if isinstance(additional_fields, dict):                
                for k, v in additional_fields.items():
                    if k in df.columns:
                        continue
                    if isinstance(v, str) and v.startswith("expression:"):
                        v = v.replace("expression:", "")
                        df[k] = df.eval(v)
                    elif isinstance(v, str) and v.startswith("lambda:"):
                        v = v.replace("lambda:", "")
                        df[k] = df.apply(lambda x: eval(v), axis=1)
                    else:
                        df[k] = v
            elif isinstance(additional_fields, list):
                for field in additional_fields:
                    if isinstance(field, str):
                        if field in df.columns:
                            continue
                        df[field] = None
                    elif isinstance(field, dict):
                        for k, v in field.items():
                            if k in df.columns:
                                continue
                            df[k] = v
        if isinstance(df, gpd.GeoDataFrame): # se geodataframe trasforma o setta CRS e rinomina geometria
            crs = parameters.get("crs", None)
            if crs is not None:                
                if df.crs is None:                    
                    df.set_crs(crs, inplace=True)                    
                elif df.crs != crs:
                    warnings.warn(f"CRS of dataframe {df.crs} does not match expected CRS {crs}. Converting CRS for {parameters}.")
            if df.crs is None:
                warnings.warn(f"CRS of dataframe is None. Setting CRS to {self.ini.CRS} for {parameters}.")
                df.set_crs(self.ini.CRS, inplace=True)                
            df.to_crs(self.ini.CRS_CALC, inplace=True)
            if geometry:
                if geometry != df.geometry.name:
                    df.rename_geometry(geometry, inplace=True)
        elif isinstance(df, pd.DataFrame): # se dataframe ma esiste una colonna geometrica allora trasforma in geodataframe
            if geometry is None:
                geometry = parameters.get("mapping",{}).pop("geometry", None)
            if geometry is None:
                if "geometry" in df.columns:
                    geometry = "geometry"
            if geometry and geometry in df.columns:
                # check if is WKB type (bytes) or WKT type (text) or GeoJSON type  (text bwith json format)
                if pd.api.types.is_string_dtype(df[geometry]):
                    if df[geometry].str.startswith("{").any():
                        df["geometry"] = df[geometry].apply(from_geojson)
                    else:
                        df["geometry"] = df[geometry].apply(from_wkt)
                elif pd.api.types.is_object_dtype(df[geometry]) and df[geometry].apply(lambda x: isinstance(x, bytes)).any():
                    df["geometry"] = df[geometry].apply(from_wkb)
                crs = parameters.get("crs", self.ini.CRS)
                df = gpd.GeoDataFrame(df, geometry=geometry, crs=self.ini.CRS)
                df.to_crs(self.ini.CRS_CALC, inplace=True)
            else:
                df = pd.DataFrame(df)

        df=self.parser.apply_dtype(df=df, dtype=dtype, copy=False, 
                                   tz_src=parameters.get("tz_data", self.ini.TZ_LOCAL),
                                   tz_dest=self.ini.TZ_CALC)  
                              
        return df
            

    @staticmethod
    def get_cls_by_name(class_name) -> BaseLoader:                
        module = import_module("m4i.connectors")
        cls = getattr(module, class_name)
        return cls

    def update_params(self, tstart: int = None, tend: int = None):
        if tstart is not None:
            self.parser.params["start"] = min2hhmm(tstart)
        if tend is not None:
            self.parser.params["end"] = min2hhmm(tend)

        self.dparams = self.parser.params        
        try:
            self.params = json.loads(json.dumps(self.dparams), object_hook=lambda d: namedtuple("X", d.keys())(*d.values()) if isinstance(d, dict) else d)
        except Exception as e:
            raise Exception(f"Error parsing params definition: {e}")

        if "params" not in self.dparams:
            raise KeyError("key 'params' not found in execution parameters")

        if self.ini.SRC_CONV_TBL:
            self.conv_tbl = pd.read_csv(self.ini.SRC_CONV_TBL)
        else:
            self.conv_tbl = None

        date_default  = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        date_default = util.to_datetime_auto(self.parser.params.get("date_simulation", None),  
                                             date_default = date_default.date(),
                                             time_default = date_default.time(),
                                             unit='minutes')
        start = util.to_datetime_auto(self.parser.params.get("start", None), date_default=date_default,unit='minutes')
        end = util.to_datetime_auto(self.parser.params.get("end", None), date_default=date_default,unit='minutes')
        if start is not None and end is not None and end<start:
            end += datetime.timedelta(days=1)
        if start is not None:
            self.start = int(util.min_from_midnight(start))
        else:
            self.start = None
        if end is not None:
            self.end = int(util.min_from_midnight(end))
        else:
            self.end = None

        if self.start is not None and self.end is not None and self.delta_t is not None:
            self.timestamps = list(np.arange(self.start, self.end, self.delta_t))
        else:
            self.timestamps = None            
        
    def has(self, name):
        return self.parser.get(name) is not None

    def load_dataset(self, parameters: dict, filters=None, dtype = None)-> Union[pd.DataFrame, gpd.GeoDataFrame, dict]:
        pass

    def load(self, path: str=None, parameters: dict=None, filters=None, dtype=None, from_output=False,**kwargs) -> Union[pd.DataFrame, gpd.GeoDataFrame]:
        """
        Carica un dataset in base ai parametri forniti, ai filtri e al tipo di dato specificato.

        Argomenti:
            name (opzionale): Il nome del dataset da caricare. Se non fornito, verrà utilizzato il parametro 'parameters'.
            parameters (opzionale): Un dizionario contenente i parametri necessari per caricare il dataset.
            filters (opzionale): Criteri per filtrare il dataset. I filtri devono essere specificati in forma di lista di tuple, seguendo la sintassi: 
                                          filters = [[('colonna', 'operatore', valore), ...], ...]
                                 * Operatori supportati: ==, =, !=, >, >=, <, <=, in, not in​
                                 * AND logico: le tuple all'interno di una lista interna sono combinate con un AND logico.​
                                 * OR logico: le liste interne sono combinate con un OR logico.
                                 es: filters = [('col1', '==', 10), ('col2', '>', 5)] 
                                     corrisponde a col1 == 10 AND col2 > 5
                                 es: filters = [[('col1', '==', 10), ('col2', '>', 5)], [('col3', '<', 20)]] 
                                     corrisponde a (col1 == 10 AND col2 > 5) OR (col3 < 20)
                                 es: filters = [[('col1', '==', 10), ('col2', '>', 5)], [('col3', '<', 20), ('col4', '!=', 30)]] 
                                     corrisponde a (col1 == 10 AND col2 > 5) OR (col3 < 20 AND col4 != 30)
            dtype (opzionale): Il tipo di dato desiderato per il dataset caricato. Può essere utilizzato per specificare formati come pandas DataFrame o GeoDataFrame.
            **kwargs: Argomenti aggiuntivi per la personalizzazione o per casi d'uso specifici.

        Restituisce:
            Union[pd.DataFrame, gpd.GeoDataFrame]: Il dataset caricato, che può essere un pandas DataFrame o un GeoPandas GeoDataFrame, a seconda dell'esistenza di un campo geometrico.
        """        
        if parameters is None:
            parameters = self.parser.get_input_parameters(path, from_output=from_output)
            
        df = self._load_dataset(parameters=parameters, filters=filters, dtype=dtype, **kwargs)
        if df is None:
            raise Exception(f"load({parameters}) function return None value")
        else:            
            return df

    def load_detectors(self, parameters: dict, **kwargs) -> pd.DataFrame:
        dtype = self.parser.get_dtype("detectors")
        df = self._load_dataset(parameters=parameters, dtype=dtype, **kwargs)
        if df is None:
            raise Exception(f"load_detectors({parameters}) function return None value")
        
        self.parser.check_fields("detectors", df)
        df = pd.DataFrame(df)
        return df

    def load_counts_df(self, parameters: dict, **kwargs) -> pd.DataFrame:
        end = kwargs.pop("end", self.end)
        start = kwargs.pop("start", self.start)
        end = self.end if end is None else end
        start = self.start if start is None else start
        if end%1440<start%1440:
            filters = [(("timestamp","<",end%1440),("timestamp",">=",start%1440))]
        else:
            filters = [("timestamp",">=",start%1440),("timestamp","<",end%1440)]
        dtype = self.parser.get_dtype("counts")
        df = self._load_dataset(parameters=parameters, filters = filters, dtype=dtype, **kwargs)
        if df is None:
            raise Exception(f"load_counts({parameters}) function return None value")
        self.parser.check_fields("counts", df)
        df = pd.DataFrame(df)
        return df
    
    def load_matrix(self, parameters: dict, **kwargs) -> pd.DataFrame:
        end = kwargs.pop("end", self.end)
        start = kwargs.pop("start", self.start)
        if end%1440<start%1440:
            filters = [(("timestamp","<",end%1440),("timestamp",">=",start%1440))]
        else:
            filters = [("timestamp",">=",start%1440),("timestamp","<",end%1440)]
        dtype = self.parser.get_dtype("matrices")
        df = self._load_dataset(parameters=parameters, filters = filters, dtype=dtype, **kwargs)
        if df is None:
            raise Exception(f"load_matrix({parameters}) function return None value")
        self.parser.check_fields("matrices", df)
        df = pd.DataFrame(df)
        return df

    def load_nodes(self, parameters: dict, **kwargs) -> pd.DataFrame:
        dtype = self.parser.get_dtype("nodes")
        df = self._load_dataset(parameters=parameters, dtype=dtype, geometry="geometry", **kwargs)        
        if df is None:
            raise Exception(f"load_nodes({parameters}) function return None value")
        self.parser.check_fields("nodes", df)
        #df = pd.DataFrame(df)
        return df


    def load_links(self, parameters: dict, **kwargs) -> pd.DataFrame:
        dtype = self.parser.get_dtype("links")
        df = self._load_dataset(parameters=parameters, dtype=dtype, geometry="geometry", **kwargs)
        if df is None:
            raise Exception(f"load_links({parameters}) function return None value")
        self.parser.check_fields("links", df)
        #df = pd.DataFrame(df)
        return df

    def load_turns(self, parameters: dict, **kwargs) -> pd.DataFrame:
        dtype = self.parser.get_dtype("turns")
        df = self._load_dataset(parameters=parameters, dtype=dtype, **kwargs)
        if df is None:
            raise Exception(f"load_turns({parameters}) function return None value")
        self.parser.check_fields("turns", df)
        #df = pd.DataFrame(df)
        return df

    def load_zones(self, parameters: dict, **kwargs) -> pd.DataFrame:
        dtype = self.parser.get_dtype("zones")
        df = self._load_dataset(parameters=parameters, dtype=dtype, geometry="geometry", **kwargs)
        if df is None:
            raise Exception(f"load_zones({parameters}) function return None value")
        self.parser.check_fields("zones", df)
        #df = pd.DataFrame(df)
        return df

    

    def load_links_sets(self, parameters: dict, **kwargs) -> pd.DataFrame:
        dtype = self.parser.get_dtype("links_sets")
        df = self._load_dataset(parameters=parameters, dtype=dtype, **kwargs)
        if df is None:
            raise Exception(f"load_links_sets({parameters}) function return None value")
        self.parser.check_fields("links_sets", df)
        df = pd.DataFrame(df)
        return df

    def load_events(self, parameters: dict, **kwargs) -> pd.DataFrame:
        dtype = self.parser.get_dtype("events")
        df = self._load_dataset(parameters=parameters, dtype=dtype, **kwargs)
        if df is None:
            raise Exception(f"load_events({parameters}) function return None value")
        self.parser.check_fields("events", df)
        df = pd.DataFrame(df)
        return df

    def load_traffic_lights(self, parameters: dict, **kwargs) -> pd.DataFrame:
        dtype = self.parser.get_dtype("traffic_lights")
        df = self._load_dataset(parameters=parameters, dtype=dtype, **kwargs)
        if df is None:
            raise Exception(f"load_traffic_lights({parameters}) function return None value")
        self.parser.check_fields("traffic_lights", df)
        df = pd.DataFrame(df)
        return df

    
    def get_od(self, cls) -> MatrixODT:
        if cls in self.ODs:
            return self.ODs[cls]
        else:
            od = MatrixODT(rows=self.origins, cols=self.destinations, timestamps=self.timestamps)
            self.ODs[cls]= od
            return od

    def get_perc(self, cls) -> MatrixODT:
        if cls in self.perc:
            return self.perc[cls]
        else:
            od = MatrixODT(rows=self.origins, cols=self.destinations, timestamps=self.timestamps)
            self.perc[cls]= od
            return od

    def get_traffic_lights(self) -> list[dict]:
        return self.sign_nodes

    def get_events(self, event_type: str) -> list[dict]:
        return self.events.get(event_type, [])

    def save_to_ipc(self, ipc: IPC):        
        if ipc is None:
            return
        key_to_save = {}
        for att in self.attr_to_share:
            if hasattr(self, att):
                v = getattr(self, att)
                key_to_save[att] = v

        for k,v in key_to_save.items():
            if v is not None:
                ipc.set(k, v)

    def load_from_ipc(self, ipc: IPC):        
        if ipc is None:
            return
        ipc_keys =set(ipc.keys())
        for k in self.attr_to_share:
            if k in ipc_keys:
                setattr(self, k, ipc.get(k))
    
    @property
    def origins(self) -> list[int]:
        if self._origins is None:
            self._load_zones()
        return self._origins
    
    @property
    def destinations(self) -> list[int]:
        if self._destinations is None:
            self._load_zones()
        return self._destinations

    @property
    def zones(self) -> list[int]:
        if self._zones is None:
            self._load_zones()
        return self._zones
    
    @property
    def modes(self) -> dict:
        if self._modes is None:
            self._load_modes()
        return self._modes
    
    @property
    def sign_nodes(self) -> list[dict]:
        if self._sign_nodes is None:
            self._load_traffic_ligths()
        return self._sign_nodes
    
    @property
    def OD(self) -> MatrixODT:
        if self._OD is None:
            self.load_demand()
        return self._OD
    
    @property
    def ODs(self) -> dict[Any, MatrixODT]:
        if self._ODs is None:
            self.load_demand()
        return self._ODs

    @property
    def detectors(self) -> list:
        if self._detectors is None:
            self._load_detectors()
        return self._detectors
    
    @property
    def counts(self) -> dict[str,pd.DataFrame]:
        if self._counts is None:
            self.load_counts()
        return self._counts
        
    @property
    def G(self) -> DynamicGraph:
        if self._G is None:
            self.load_graph()
        return self._G
    
    @property
    def links_sets(self) -> dict[str, list[int]]:
        if self._links_sets is None:
            self._load_links_sets()
        return self._links_sets
    
    @property
    def events(self) -> dict[str, list[dict]]:
        if self._events is None:
            self._load_events()
        return self._events
    
    @property
    def coefficients(self) -> dict:
        if self._coefficients is None:
            self._load_coefficients()
        return self._coefficients
    
    @property
    def perc(self) -> dict[int, MatrixODT]:
        if self._perc is None:
            self.load_demand()
        return self._perc
    
    @property
    def modes(self) -> dict:
        if self._modes is None:
            self._load_modes()
        return self._modes
    
    @property
    def m_paths(self) -> KPathContainer:
        if self._m_paths is None:
            self._load_paths()
        return self._m_paths

    @property
    def bounds(self) -> shapely.geometry.Polygon:
        if self._bounds is None:
            self.load_graph()
        return self._bounds

    @property
    def zonization(self) -> gpd.GeoDataFrame:
        if self._zonization is None:
            self._zonization = self._load_zonization()
        return self._zonization

    @property
    def df_links(self) -> pd.DataFrame:
        if self._df_links is None:
            self._df_links, self._df_nodes, self._df_turns = self.load_df_graph()
        return self._df_links

    @property
    def df_nodes(self) -> pd.DataFrame:
        if self._df_nodes is None:
            self._df_links, self._df_nodes, self._df_turns = self.load_df_graph()
        return self._df_nodes
    
    @property
    def df_turns(self) -> pd.DataFrame:
        if self._df_turns is None:
            self._df_links, self._df_nodes, self._df_turns = self.load_df_graph()
        return self._df_turns

    def load_df_graph(self, name="params.supply"):
        self.log.info("Loading Data Graph...")
        parameters = self.parser.get(name)
        if parameters is None:
            raise KeyError("key 'supply' not found in execution parameters['params']")
        df_links = None
        df_nodes = None
        df_turns = None
        for id_net, net_param in enumerate(parameters):
            self.log.info(f"Loading Net {id_net}")
            if "links" in net_param:
                links_parameters = self.parser.get_input_parameters(f"params.supply.{id_net}.links")
                tmp = self.load_links(links_parameters)
                if tmp is None:
                    raise Exception(f"load_links({links_parameters}) function return None value")
                tmp.set_index("id")
                if df_links is None:
                    df_links = tmp
                else:
                    df_links = df_links.combine_first(tmp)
            if "nodes" in net_param:
                nodes_parameters = self.parser.get_input_parameters(f'params.supply.{id_net}.nodes')    
                tmp = self.load_nodes(nodes_parameters)
                if tmp is None:
                    raise Exception(f"load_nodes({nodes_parameters}) function return None value")
                tmp.set_index("id")
                if df_nodes is None:
                    df_nodes = tmp
                else:
                    df_nodes = df_nodes.combine_first(tmp)
            if "turns" in net_param:
                turns_parameters = self.parser.get_input_parameters(f'params.supply.{id_net}.turns')
                tmp = self.load_turns(turns_parameters)
                if tmp is None:
                    raise Exception(f"load_turns({turns_parameters}) function return None value")
                tmp.drop_duplicates(subset=["from_node", "via_node", "to_node"], keep="last").set_index(["from_node", "via_node", "to_node"])
                if df_turns is None:
                    df_turns = tmp
                else:
                    df_turns = df_turns.combine_first(tmp)
        df_nodes.reset_index(inplace=True)
        df_links.reset_index(inplace=True)
        df_turns.reset_index(inplace=True)
        return df_links, df_nodes, df_turns
    
    def _load_coefficients(self)-> dict:        
        if self.ini.SRC_COEFS:
            with open(self.ini.SRC_COEFS) as json_file:
                self._coefficients =  json.load(json_file)
            
    def _load_zones(self):
        self.log.info("Loading Zones...")
        parameters = self.parser.get_input_parameters("params.zones")
        if parameters is None:
            raise KeyError("key 'zones' not found in execution parameters['params']")
        if "src" not in parameters:
            raise KeyError("key 'src' required in zones parameters")

        df_zones = self.load_zones(parameters)
        if df_zones is None:
            raise Exception(f"load_zones({parameters}) function return None value")

        self._zones = df_zones["id"].values.tolist()
        self._origins = self.zones.copy()
        self._destinations = self.zones.copy()
        self.log.info(f"Zones identified {len(self.zones)}")

    def _load_zonization(self, **kwargs) -> gpd.GeoDataFrame:
        self.log.info("Loading Zonization...")
        parameters = self.parser.get_input_parameters("params.zones")
        if parameters is None:
            raise KeyError("key 'zones' not found in execution parameters['params']")
        if "src" not in parameters:
            raise KeyError("key 'src' required in zones parameters")

        df = self.load_zones(parameters)
        if df is None:
            raise Exception(f"load_zones({parameters}) function return None value")
        ret=None
        if "geometry" in df.columns and df.geometry.iloc[0] is not None:
            df = gpd.GeoDataFrame(df)
            if df.geom_type.iloc[0] in ('Point'):
                df.geometry = df.geometry.voronoi_polygons(extend_to=self.bounds)
            elif df.geom_type.iloc[0] not in ('Polygon','MultiPolygon'):
                raise TypeError(f"geometry type {df.geom_type.iloc[0]} not supported")   
            ret = df                         
        else:
            nodes = gpd.GeoDataFrame(self.G.get_all_nodes())
            if "geometry" in nodes and nodes.geometry.iloc[0] is not None:
                df = df.merge(nodes[["idx","geometry"]].rename(columns={"idx":"id"}), on="id", how="left", suffixes=("", "_y"))
                df=df.drop(columns=["geometry"]).rename(columns={"geometry_y": "geometry"})
                df = gpd.GeoDataFrame(df)
                df.geometry = df.geometry.voronoi_polygons(extend_to=self.bounds)
                ret = df
            else:
                links = gpd.GeoDataFrame(self.G.get_all_links())
                if "geometry" in links and links.geometry.iloc[0] is not None:
                    from_node = links[["from_node","geometry"]].rename(columns={"from_node":"id"}).drop_duplicates(subset=["id"], keep="last")
                    to_node = links[["to_node","geometry"]].rename(columns={"to_node":"id"}).drop_duplicates(subset=["id"], keep="last")
                    nodes = pd.concat([from_node, to_node], ignore_index=True).drop_duplicates(subset=["id"], keep="last")
                    df = df.merge(nodes[["id","geometry"]], on="id", how="left", suffixes=("", "_y"))
                    df=df.drop(columns=["geometry"]).rename(columns={"geometry_y": "geometry"})
                    df = gpd.GeoDataFrame(df)
                    df.geometry = df.geometry.voronoi_polygons(extend_to=self.bounds)
                    ret = df
        if ret is None:
            raise KeyError("geometry column not found in zones dataset, nodes dataset and links dataset")
        return ret
        
    def _load_paths(self) -> KPathList:
        self.log.info("Loading Paths...")
        parameters = self.parser.get("params.paths")
        if parameters is None:
            raise KeyError("key 'paths' not found in execution parameters['params']")
        
        pl: KPathList = KPathList()
        for id_paths, paths_params in enumerate(parameters):
            self.log.info(f"Loading Paths Set {id_paths}...")
            paths_params = self.parser.get_output_parameters("params.paths", id_paths)
            if "src" not in paths_params:
                raise KeyError("key 'src' required in paths parameters")

            df = self.load_paths(paths_params)
            if df is None:
                raise Exception(f"load_paths({paths_params}) function return None value")
            for path_record in df.to_dict(orient="records"):
                path = Path(source=path_record["source"],target=path_record["target"],t_start=path_record["t_start"])
                path.update(path_record)
                pl.add_path(path)
        self._m_paths = pl
        self.log.info(f"Paths identified {len(pl)}")
        return pl
    
    def _load_modes(self):
        self.log.info("Loading Modes...")
        self._modes = {}
        parameters = self.parser.get("params.modes")
        if parameters is None:
            raise KeyError("key 'modes' not found in execution parameters['params']")
        for mode in parameters:
            if not isinstance(mode,dict):
                raise KeyError("a single mode must to be a dictionary in parameters['params']['modes']")
            if "id" not in mode:
                raise KeyError("a single mode must to contains 'id' key")
            key=str(mode.pop("id").lower())
            if key == "all":
                raise KeyError(f"mode '{key}' is reserved")
            
            mode.setdefault("description","")
            eq = self.ini.CLASS_EQ_FACT.get(key,1)
            mode.setdefault("eq_factor",eq)
            self._modes[key] = mode
        self.log.info(f"Modes identified {list(self.modes.keys())}")

    
    def _load_traffic_ligths(self):
        self.log.info("Loading Traffic Ligths...")
        parameters = self.parser.get("params.traffic_lights")
        
        if parameters is None:
            self._sign_nodes = []
            self.log.warning("key 'traffic_lights' not found in execution parameters['params']")
        else:
            self._sign_nodes = []
            for id_tl, tl_params in enumerate(self.dparams["params"]["traffic_lights"]):
                self.log.info(f"Loading Traffic Light {id_tl}...")
                tl_params = self.parser.get_input_parameters("params.traffic_lights", id_tl)                
                if "src" not in tl_params:
                    raise KeyError("key 'src' required in traffic_lights parameters")                
                tmp = self.load_traffic_lights(tl_params)
                if tmp is None:
                    raise Exception(f"load_traffic_lights({tl_params}) function return None value")
                for new_tl in tmp.to_dict(orient='records'):
                    if isinstance(new_tl["phases"], str):
                        new_tl["phases"] = json.loads(new_tl["phases"])
                    if "id" not in new_tl:
                        self._sign_nodes.append(new_tl)
                    for i, tl in enumerate(self._sign_nodes):
                        if "id" in tl and tl["id"] == new_tl["id"]:
                            self._sign_nodes[i] = new_tl
                            break
                    else:
                        self._sign_nodes.append(new_tl)
        self.log.info(f"Traffic Ligths identified {len(self._sign_nodes)}")

    def _load_events(self):
        self._load_links_sets()
        self.log.info(f"Loading Events...")
        parameters = self.parser.get("params.events")
        if parameters is None:
            self._events = {}
            self.log.warning("key 'events' not found in execution parameters['params']")
        else:
            df_events = pd.DataFrame()
            for id_set, event_params in enumerate(parameters):
                self.log.info(f"Loading Events {id_set}...")
                event_params = self.parser.get_input_parameters("params.events", id_set)
                if "src" not in event_params:
                    raise KeyError("key 'src' required in events parameters")
                tmp = self.load_events(event_params)
                if tmp is None:
                    raise Exception(f"load_events({event_params['src']}) function return None value")
                df_events = df_events.combine_first(tmp)

            self._events = defaultdict(list)
            for row in df_events.to_dict(orient='records'):
                id_links = self._get_links_sets(row["id_link_set"])
                try:
                    if pd.isna(row["params"]):
                        params = None
                    else:
                        if not isinstance(row["params"], dict):
                            params = json.loads(row["params"])
                        else:
                            params = row["params"]
                except:
                    raise Exception(f"Failed to interpret event parameters:\n{row}")
                event = {"arc_list": id_links, "type": row["type"], "start": hhmm2min(row["start"]), "end": hhmm2min(row["end"]), "params": params}
                row.update(event)
                self._events[event["type"]].append(row)
            self._events = dict(self.events)
            self.log.info(f"Event types identified {list(self.events.keys())}")
            self.log.info(f"Events identified {len(df_events)}")

    def _get_links_sets(self, name: str):
        if pd.isna(name) or not name:
            return list([l["idx"] for l in self.G.get_all_links()])

        id_links = []
        try:
            if isinstance(name, str):
                if name.isdigit():
                    id_links = [int(name)]
                else:
                    id_links = self._links_sets.get(name, [])
            else:
                tmp = ast.literal_eval(str(name))
                if isinstance(tmp, (tuple, list)):
                    id_links = list(tmp)
                elif isinstance(tmp, str):
                    id_links = self._links_sets.get(tmp, [])
        except:
            try:
                id_links = self._links_sets.get(name, [])
            except:
                raise Exception(f"The links_sets {name} could not be identified")
        if len(id_links) == 0:
            self.log.warning(f"The links_sets {name} is empty")
        return id_links

    def _load_links_sets(self):
        self.log.info(f"Loading Links Sets...")
        parameters = self.parser.get("params.links_sets")
        if parameters is None:
            self._links_sets = {}
            self.log.warning("key 'links_sets' not found in execution parameters['params']")
        else:
            df_links_sets = pd.DataFrame()
            for id_set, set_params in enumerate(parameters):                
                self.log.info(f"Loading Links Set {id_set}...")
                set_params = self.parser.get_input_parameters("params.links_sets", id_set)
                if "src" not in set_params:
                    raise KeyError("key 'src' required in links_sets parameters")
                tmp = self.load_links_sets(set_params)
                if tmp is None:
                    raise Exception(f"load_links_sets({set_params}) function return None value")
                df_links_sets = df_links_sets.combine_first(tmp)
            if df_links_sets.shape[0] == 0:
                self._links_sets = {}
            else:
                self._links_sets = df_links_sets.groupby("id_set").agg(list).to_dict()["id_link"]
            self.log.info(f"Links Sets identified {len(self.links_sets)}")
            
    def _load_detectors(self):
        self.log.info("Loading Detectors...")
        parameters = self.parser.get("params.detectors")
        if parameters is None:            
            self.log.warning("key 'detectors' not found in execution parameters['params']")
            self._detectors = []
        else:
            detectors = pd.DataFrame()
            for id_det, set_detect in enumerate(parameters):                
                self.log.info(f"Loading Detectors {id_det}...")
                set_detect = self.parser.get_input_parameters("params.detectors", id_det)
                if "src" not in set_detect:
                    raise KeyError("key 'src' required in links_sets parameters")
                tmp = self.load_detectors(set_detect)
                if tmp is None:
                    raise Exception(f"load_detectors({set_detect}) function return None value")
                detectors = detectors.combine_first(tmp)
        self._detectors = detectors

    def load_counts(self, tstart:int=None, tend:int=None):
        self.log.info("Loading Counts...")
        parameters = self.parser.get("params.counts")
        self._counts = {}
        if parameters is None:            
            self.log.warning("key 'counts' not found in execution parameters['params']")            
            return
        counts =pd.DataFrame()
        for id_count, set_counts in enumerate(parameters):                
            self.log.info(f"Loading Counts {id_count}...")
            set_counts = self.parser.get_input_parameters("params.counts", id_count).copy()
            if "src" not in set_counts:
                raise KeyError("key 'src' required in counts parameters")
            tmp = self.load_counts_df(set_counts, start=tstart, end=tend)
            if tmp is None:
                raise Exception(f"load_counts({set_counts}) function return None value")
            counts = counts.combine_first(tmp)      

        counts["eq_counts"] = 0.0
        counts_by_mode = counts.groupby("mode")
        for mode, df_mode in counts_by_mode:
            b=df_mode.index
            if mode in self.modes:
                df_mode["eq_counts"] = df_mode["counts"] * df_mode["mode"].apply(lambda x: self.modes.get(x,{}).get("eq_factor",1))
                counts.loc[b, "eq_counts"] = df_mode["eq_counts"]
                self._counts[mode] = df_mode["counts"].reset_index(drop=True)
            elif mode is None or mode == "all":
                df_mode["eq_counts"] = df_mode["counts"]
                df_mode["mode"] = "all"
                counts.loc[b, ["eq_counts","mode"]] = df_mode[["eq_counts","mode"]]                
            else:
                self.log.warning(f"Mode '{mode}' not defined in modes parameter, counts will not be aggregated by mode")
                df_mode["eq_counts"] = df_mode["counts"]
                df_mode["mode"] = "all"
                counts.loc[b, ["eq_counts","mode"]] = df_mode[["eq_counts","mode"]]
        # TODO: Group by class of timestamps
        self._counts["all"] = counts.groupby(["id", "timestamp"]).agg(counts=("eq_counts", "sum"))["counts"].reset_index()

    def load_demand(self, timestamps: list[int] = None):
        self.log.info("Loading OD Matrices...")
        parameters = self.parser.get("params.demand")
        if parameters is None:
            self.log.warning("key 'demand' not found in execution parameters['params']")
        modes = set()
        self._perc = {}
        self._ODs = {}
        timestamps = timestamps or self.timestamps
        self._OD = MatrixODT(rows=self.origins, cols=self.destinations, timestamps=timestamps, init=0, mode=None)
        for id_mat, od_param in enumerate(parameters):
            self.log.info(f"Loading OD Matrix '{id_mat}'...")
            mode = od_param.get("mode", "c")            
            if mode not in self.modes:
                raise KeyError("mode '{mode}' not defined in modes parameter")
            if "matrices" not in od_param:
                raise KeyError("key 'matrices' required in demand element")
            modes.add(mode)
            if mode in self._ODs:
                OD = self._ODs[mode]
            else:
                OD = MatrixODT(rows=self.origins, cols=self.destinations, timestamps=timestamps, init=0, mode=mode)
                self._ODs[mode] = OD

            tot_od_pairs=0
            for id_m, mat_params in enumerate(od_param["matrices"]):
                tmp = None
                self.log.info(f"Loading OD Sub Matrix '{id_mat}'-'{id_m}'...")
                if "scalar" in mat_params:
                    if not isinstance(mat_params["scalar"], (int, float)):
                        raise TypeError("key 'scalar' must be a number")
                    current_od = MatrixODT(rows=self.origins, cols=self.destinations, timestamps=timestamps, init=mat_params["scalar"], mode=mode)
                else:
                    mat_params = self.parser.get_input_parameters(f"params.demand.{id_mat}.matrices", id_m)
                    if "src" not in mat_params:
                        raise KeyError("key 'src' required in matrices element")
                    tmp = self.load_matrix(mat_params, start = min(timestamps), end = max(timestamps))
                    if tmp is None:
                        raise Exception(f"load_matrix({mat_params}) function return None value")
                    tot_od_pairs += tmp.shape[0]                    
                    current_od = MatrixODT.read_df(rows=self.origins,cols=self.destinations, timestamps=timestamps, df=tmp)
                if id_m==0:                    
                    OD += current_od
                else:
                    op = mat_params.get("op", "+")                    
                    if op == "merge":
                        if tmp:  # merge con dataframe
                            OD=MatrixODT.read_df(rows=self.origins, cols=self.destinations, timestamps=timestamps, df=tmp, od=OD)
                        else: # merge con scalar
                            OD *= 0
                            OD += current_od
                    else:
                        if op == "+":
                            OD += current_od
                        elif op == "-":
                            OD -= current_od
                        elif op == "*":
                            OD *= current_od
                        elif op == "/":
                            OD /= current_od
                        else:
                            raise ValueError(f"Unknown operation '{op}'")                            
                                        
            self._OD += OD * self.modes.get(mode,{}).get("eq_factor",1)

        for id_mat, OD in self._ODs.items():
            tmp = OD / self._OD
            tmp.nan_to_num(copy=False)
            self._perc[id_mat] = tmp
        self.log.info(f"OD Matrices identified {len(self.ODs)}. Read OD Pairs : {tot_od_pairs}")
            
            
    def load_graph(self, df_links=None, df_nodes=None, df_turns=None):
        self.log.info("Loading Graph...")
        if self.ini.LOAD_GRAPH and (df_links is None or df_nodes is None):
            self.log.info("Loading State (Graph)...")
            from .state_manager import StateManager
            sm = StateManager(parser=self.parser)
            self._G = sm.load_state("graph")
            if self._G is not None:
                self.log.info("State loaded (Graph)")
                return
            else:
                self.log.info("State not found (Graph)")
                self._G = None
        if df_links is None or df_nodes is None:
            df_links, df_nodes, df_turns = self.df_links, self.df_nodes, self.df_turns


        assert df_nodes is not None, "nodes not loaded"
        assert df_links is not None, "links not loaded"

        G = DynamicGraph(total_time=0, delta_t=self.delta_t, modes=self.modes)
        self.log.info("Transforming to graph")

        self._bounds = None
        if self._bounds is None and "geometry" in df_links.columns:
            tb = gpd.GeoDataFrame(df_links, geometry="geometry").total_bounds
            self._bounds = shapely.geometry.box(*tb)
        if self._bounds is None and "geometry" in df_nodes.columns:
            tb = gpd.GeoDataFrame(df_nodes, geometry="geometry").total_bounds
            self._bounds = shapely.geometry.box(*tb)

        for _, row in df_nodes.iterrows():
            kwargs = {k: row[k] for k in df_nodes.columns if k not in {"id"}}
            if "modes" in row:
                if pd.isna(row["modes"]) is None:
                    row["modes"] = set(self.modes.keys())
                elif isinstance(row["modes"], str):
                    if row["modes"].strip().lower() == "all":
                        row["modes"] = set(self.modes.keys())
                    if row["modes"].strip().lower() == "none":
                        row["modes"] = set()
                    elif row["modes"].strip() == "":
                        row["modes"] = set(self.modes.keys())
                    else:
                        row["modes"] = set([m.strip() for m in row["modes"].split(",")])
                kwargs["modes"]=row["modes"]            
            kwargs["idx"]=int(row["id"])
            kwargs["is_centroid"]=int(row["id"]) in self.zones
            kwargs["time"]=DynamicTimeArrayAttribute(0)

            #[kwargs.pop(k,None) for k in set(mapping_nodes.values())]
            G.add_node(**kwargs)

        """
        t = df_links[df_links.duplicated(["from_node", "to_node"])][["from_node", "to_node"]]
        t = t.astype(int)
        if t.shape[0] > 0:
            self.log.warning("Duplicated links in the network")
            self.log.debug("| " + " | ".join(t.columns) + " |")
            self.log.debug("| " + " | ".join(["-" * len(str(c)) for c in t.columns]) + " |")
            for row in t.values:
                self.log.debug(f"| {' | '.join(map(str, row))} |")
            self.log.warning(f"Drop {len(t.values)} duplicated links")
            df_links = df_links.sort_values(by="length").drop_duplicates(subset=["from_node", "to_node"], keep="first")
        """
        self.log.debug("Adding links to graph...")
        for _, row in df_links.iterrows():

            kwargs = {k: row[k] for k in df_links.columns  if k not in {"id", "from_node", "to_node", "lanes", "rcr"}}
            kwargs["idx"]=int(row["id"])
            kwargs["i"]=int(row["from_node"])
            kwargs["j"]=int(row["to_node"])
            kwargs["length"]=float(row["length"])
            kwargs["v0"]=float(row["v0"])
            kwargs["numlanes"]=float(row["lanes"])
            kwargs["connector"]=int(row["connector"])
            kwargs["capacity"]=float(row["capacity"])
            kwargs["alpha"]=float(row["alpha"])
            kwargs["r_cr"]=float(row["rcr"])
            if "modes" in row:
                if pd.isna(row["modes"]) is None:
                    row["modes"] = set(self.modes.keys())
                elif isinstance(row["modes"], str):
                    if row["modes"].strip().lower() == "all":
                        row["modes"] = set(self.modes.keys())
                    if row["modes"].strip().lower() == "none":
                        row["modes"] = set()
                    elif row["modes"].strip() == "":
                        row["modes"] = set(self.modes.keys())
                    else:
                        row["modes"] = set([m.strip() for m in row["modes"].split(",")])
                kwargs["modes"]=row["modes"]      
            kwargs["t0"]=float(row["length"] / row["v0"] * 60)
            kwargs["time"]=DynamicTimeArrayAttribute(float(row["length"] / row["v0"] * 60))
            kwargs["flow"]=DynamicTimeArrayAttribute(0)
            #[kwargs.pop(k,None) for k in set(mapping_links.values())]
            G.add_link(**kwargs)            

        self.log.debug("Loading Turns...")
        id_turn = 0
        for in_link in G.get_all_links():
            if in_link["connector"] == 1 and G.get_node(in_link["j"])["is_centroid"]:
                for out_link in G.get_fws(in_link["j"]):
                    if in_link["connector"] == 1 and in_link["idx"] != out_link["idx"]:
                        id_turn += 1
                        G.add_turn(idx=id_turn, in_link=in_link["idx"], out_link=out_link["idx"], time=float("inf"), type="connector")

        if df_turns is not None:
            for _, row in df_turns.iterrows():
                kwargs = {k: row[k] for k in df_turns.columns}
                from_link = to_link = None

                for l in G.get_fws(row["from_node"]):
                    if int(row["via_node"]) == int(l["j"]):
                        from_link = int(l["idx"])
                        break

                if from_link is None:
                    continue

                for l in G.get_fws(row["via_node"]):
                    if int(row["to_node"]) == int(l["j"]):
                        to_link = int(l["idx"])
                        break

                if to_link:
                    id_turn += 1
                    kwargs["idx"]=id_turn
                    kwargs["in_link"]=from_link
                    kwargs["out_link"]=to_link                    
                    kwargs["time"]=float("inf") if "penalty" not in row or pd.isna(row["penalty"]) else float(row["penalty"])
                    if "modes" in row:
                        if pd.isna(row["modes"]) is None:
                            row["modes"] = set(self.modes.keys())
                        elif isinstance(row["modes"], str):
                            if row["modes"].strip().lower() == "all":
                                row["modes"] = set(self.modes.keys())
                            if row["modes"].strip().lower() == "none":
                                row["modes"] = set()
                            elif row["modes"].strip() == "":
                                row["modes"] = set(self.modes.keys())
                            else:
                                row["modes"] = set([m.strip() for m in row["modes"].split(",")])
                        kwargs["modes"]=row["modes"]      

                    G.add_turn(**kwargs)

        G["origins"] = list(self.origins)
        G["destinations"] = list(self.destinations)
        G["zones"] = list(self.zones)        
        self._G = G
        self.log.info("Links identified {0}".format(G.n_links))
        self.log.info("Nodes identified {0}".format(G.n_nodes))
        self.log.info("Turns identified {0}".format(G.n_turns))
        return G

