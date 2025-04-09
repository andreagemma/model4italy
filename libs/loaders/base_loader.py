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
from abc import ABC, abstractmethod
from itertools import product
from importlib import import_module
from os.path import join

from ..matrix_od import MatrixODT, MatrixOD
from ..graphs import DynamicGraph, TimeArrayAttribute, CallableAttribute, KPathList, Path, KPathContainer
from ..utils import util
from .. import IniClass
from .. import Logger
from ..utils import import_dataframe



class BaseLoader(ABC):

    def __init__(self, params: Union[str, dict], settings: IniClass=None):
        self.log = Logger.getLogger("Loader", execution_id=params.get("execution_id"))
        self.origins: list[int] = None
        self.destinations: list[int] = None
        self.zones: list[int] = None
        self.sign_nodes: list[dict] = None
        self.OD: MatrixODT = None  # dict[VehicleClass,Matrix]
        self.ODs: dict[Any, MatrixODT] = None  # dict[VehicleClass,Matrix]
        self.detectors: list[int] = None
        self._G: DynamicGraph = None
        self.links_sets: dict[str, list[int]] = None
        self.perc: dict[int, MatrixODT] = None
        self.ini: IniClass = settings
        self.params: namedtuple
        self.dparams: dict = None
        self.delta_t: int = self.ini.DELTA_T
        self.events: dict[str, list[dict]]
        self.coefficients: dict = None
        self.conv_tbl: pd.DataFrame = None
        self.update_params(params)
        self.timestamps = list(np.arange(self.start, self.end, self.delta_t))
        self.modes: dict = { "c": {"description": "car (default)", "eq_factor": 1} }
        self._m_paths:KPathContainer = None
        
    def get_name(self, name, **kwargs):
        if isinstance(name, str):
            kwargs=kwargs.copy()
            for k,v in self.dparams.items():
                if isinstance(v,(float,int,str)):
                    kwargs.setdefault(k,v)
            kwargs.setdefault("date_simulation",datetime.now().strftime("%Y-%m-%d"))
            kwargs.setdefault("time_simulation",datetime.now().strftime("%H:%M:%S"))
            name = name.format(**kwargs)
        elif isinstance(name, dict):
            name = {k: self.get_name(v, **kwargs) for k, v in name.items()}
        return name        
    
    def get_location_src(self, src, key_location='src', params_location='input', **kwargs):    
        params = self.dparams.get("params",{}).get(params_location,{}).copy()
        if isinstance(src, str):
            params[key_location] = src
        elif isinstance(src, dict):
            params.update(src)
        else:
            raise Exception(f"source {src} not found. String and dictionary {{'location': ...'{key_location}': ... }} required")
        
        location, src = params.get("location",''), params.get(key_location)

        if src is not None:
            src = self.get_name(src, **kwargs)
        
        return location, src    


    @staticmethod
    def get_cls_by_name(class_name) -> BaseLoader:                
        module = import_module("libs.loaders")
        cls = getattr(module, class_name)
        return cls

    def update_params(self, params):
        if isinstance(params, str):
            self.dparams = json.loads(params)
        elif isinstance(params, dict):
            self.dparams = params

        if "start" in self.dparams:
            self.dparams["start"] = util.min2hhmm(util.hhmm2min(self.dparams.get("start", "00:00")))
            self.dparams["t_start"] = util.hhmm2min(self.dparams.get("start", "00:00"))
        if "end" in self.dparams:
            self.dparams["end"] = util.min2hhmm(util.hhmm2min(self.dparams.get("end", "23:59")))
            self.dparams["t_end"] = util.hhmm2min(self.dparams.get("end", "23:59"))
        
        #self.dparams["datetime_start"] = self.dparams["date_simulation"] + " " + self.dparams["start"]
        #self.dparams["datetime_end"] = self.dparams["date_simulation"] + " " + self.dparams["end"]
        self.params = json.loads(json.dumps(self.dparams), object_hook=lambda d: namedtuple("X", d.keys())(*d.values()) if isinstance(d, dict) else d)

        if "settings" in self.dparams:
            for k, v in self.dparams["settings"].items():
                if hasattr(self.ini, k):
                    setattr(self.ini, k, v)
                

    @abstractmethod
    def load_detectors(self, src: Any, mapping: dict[str, str]) -> pd.DataFrame:
        pass

    @abstractmethod
    def load_matrix(self, src: Any, mapping: dict[str, str]) -> pd.DataFrame:
        pass

    @abstractmethod
    def load_nodes(self, src: Any, mapping: dict[str, str]) -> pd.DataFrame:
        pass

    @abstractmethod
    def load_links(self, src: Any, mapping: dict[str, str]) -> pd.DataFrame:
        pass

    @abstractmethod
    def load_turns(self, src: Any, mapping: dict[str, str]) -> pd.DataFrame:
        pass

    @abstractmethod
    def load_zones(self, src: Any, mapping: dict[str, str]) -> pd.DataFrame:
        pass

    @abstractmethod
    def load_sets(self, src: Any, mapping: dict[str, str]) -> pd.DataFrame:
        pass

    @abstractmethod
    def load_events(self, src: Any, mapping: dict[str, str]) -> pd.DataFrame:
        pass

    @abstractmethod
    def load_traffic_ligths(self, src: Any) -> dict:
        pass

    @property
    def start(self) -> int:
        "returns the start parameter in minutes since hh:mm format"
        return util.hhmm2min(self.params.start)

    @property
    def end(self) -> int:
        "returns the end parameter in minutes since hh:mm format"
        return util.hhmm2min(self.params.end)

    @property
    def G(self) -> DynamicGraph:
        if self._G is None:
            self._load_graph()
        return self._G
    @G.setter
    def G(self, value: DynamicGraph):
        self._G = value

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

    def get_traffic_ligths(self, type: str) -> list[dict]:
        return self.sign_nodes

    def get_events(self, event_type: str) -> list[dict]:
        return self.events.get(event_type, [])

    def load(self):
        if "params" not in self.dparams:
            raise KeyError("key 'params' not found in execution parameters")

        if self.ini.SRC_CONV_TBL:
            self.conv_tbl = pd.read_csv(self.ini.SRC_CONV_TBL)
        else:
            self.conv_tbl = None

        self._load_coefficients()
        self._load_modes()        
        self._load_zones()
        self._load_traffic_ligths()
        self._load_demand()
        self._load_graph()
        self._load_link_sets()
        self._load_events()
        self._load_detectors()


    @property
    def m_paths(self):
        if self._m_paths is None:
            self._m_paths = self._load_paths()
        return self._m_paths
        
    def _load_coefficients(self)-> dict:        
        if self.ini.SRC_COEFS is not None:
            with open(self.ini.SRC_COEFS) as json_file:
                self.coefficients =  json.load(json_file)
            
    def _load_paths(self) -> KPathList:
        self.log.info("Loading Modes...")
        if "paths" not in self.dparams["paths"]:
            raise KeyError("key 'modes' not found in execution parameters['params']")
        
        pl: KPathList = KPathList()
        for id_paths, paths_params in enumerate(self.dparams["params"].get("paths")):
            self.log.info(f"Loading Links Set {id_paths}...")
            if "src" not in paths_params:
                raise KeyError("key 'src' required in paths parameters")

            df = self.load_paths(paths_params["src"])
            for path_record in df.to_dict(orient="records"):
                path = Path(source=path_record["source"],target=path_record["target"],t_start=path_record["t_start"])
                path.update(path_record)
                pl.add_path(path)
        self.log.info(f"Paths identified {len(pl)}")
        return pl
    
    def _load_modes(self):
        self.log.info("Loading Modes...")
        if "modes" not in self.dparams["params"]:
            raise KeyError("key 'modes' not found in execution parameters['params']")
        if not isinstance(self.dparams["params"]["modes"],(list,tuple,set)):
            raise KeyError("key 'modes' must to be a list, tuple or set")
        for mode in self.dparams["params"].get("modes"):
            if not isinstance(mode,dict):
                raise KeyError("a single mode must to be a dictionary in parameters['params']['modes']")
            if "id" not in mode:
                raise KeyError("a single mode must to contains 'id' key")
            key=mode.pop("id").lower()
            if key == "all":
                raise KeyError(f"mode '{key}' is reserved")
            
            mode.setdefault("description","")
            eq = self.ini.CLASS_EQ_FACT.get(key,1)
            mode.setdefault("eq_factor",eq)
            self.modes[key] = mode
        self.log.info(f"Modes identified {list(self.modes.keys())}")

    @staticmethod
    def apply_mapping(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
        ret = pd.DataFrame()
        for k, v in mapping.items():
            if v in df.columns:
                ret[k] = df[v]
            else:
                ret[k] = None
        #cols = np.unique(list(mapping.values()) + list(mapping.keys()))
        #cols = [c for c in cols if c in df.columns]
        #df.drop(cols, axis="columns", inplace=True)
        #ret = pd.concat([ret, df], axis="columns")
        return ret

    def _load_zones(self):
        self.log.info("Loading Zones...")
        if "zones" not in self.dparams["params"]:
            raise KeyError("key 'zones' not found in execution parameters['params']")
        if "src" not in self.dparams["params"]["zones"]:
            raise KeyError("key 'src' required in zones parameters")

        params = self.dparams["params"]["zones"].copy()
        mapping = {"id": "id_zone"}
        if "mapping" in params:
            mapping.update(params["mapping"])

        params["mapping"] = mapping
        df_zones = self.load_zones(src=params["src"], mapping=params["mapping"])
        if df_zones is None:
            raise Exception(f"load_zones({params['src']}) function return None value")

        #df_zones = BaseLoader.apply_mapping(df=df_zones, mapping=mapping)

        self.zones = list(df_zones["id"].values)
        self.origins = self.zones.copy()
        self.destinations = self.zones.copy()
        self.log.info(f"Zones identified {len(self.zones)}")

    def _load_traffic_ligths(self):
        self.log.info("Loading Traffic Ligths...")
        if "traffic_lights" not in self.dparams["params"]:
            self.sign_nodes = []
            self.log.warning("key 'traffic_lights' not found in execution parameters['params']")
        else:
            self.sign_nodes = []
            for id_tl, tl_params in enumerate(self.dparams["params"]["traffic_lights"]):
                self.log.info(f"Loading Traffic Light {id_tl}...")
                if "src" not in tl_params:
                    raise KeyError("key 'src' required in traffic_lights parameters")
                tl_params = tl_params.copy()
                tmp = self.load_traffic_ligths(src=tl_params["src"])
                for new_tl in tmp:
                    if "id" not in new_tl:
                        self.sign_nodes.append(new_tl)
                    for i, tl in enumerate(self.sign_nodes):
                        if "id" in tl and tl["id"] == new_tl["id"]:
                            self.sign_nodes[i] = new_tl
                            break
                    else:
                        self.sign_nodes.append(new_tl)
        self.log.info(f"Traffic Ligths identified {len(self.sign_nodes)}")

    def _load_events(self):
        self.log.info(f"Loading Events...")
        if "events" not in self.dparams["params"]:
            self.events = {}
            self.log.warning("key 'events' not found in execution parameters['params']")
        else:
            df_events = pd.DataFrame()
            for id_set, event_params in enumerate(self.dparams["params"]["events"]):
                event_params = event_params.copy()
                self.log.info(f"Loading Events {id_set}...")
                if "src" not in event_params:
                    raise KeyError("key 'src' required in events parameters")
                mapping = {"id": "id", "type": "type", "start": "start", "end": "end", "params": "params"}
                if "mapping" in event_params:
                    mapping.update(event_params["mapping"])
                event_params["mapping"] = mapping
                tmp = self.load_events(src=event_params["src"], mapping=event_params["mapping"])
                if tmp is None:
                    raise Exception(f"load_events({event_params['src']}) function return None value")
                # tmp = BaseLoader._replace_mapping(df=tmp, mapping=mapping)
                df_events = df_events.combine_first(tmp)
            self.events = defaultdict(list)
            for row in df_events.to_dict(orient='records'):
                id_links = self._get_links_sets(row["id"])
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
                event = {"arc_list": id_links, "type": row["type"], "start": row["start"], "end": row["end"], "params": params}
                row.update(event)
                self.events[event["type"]].append(row)
            self.events = dict(self.events)
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
                    id_links = self.links_sets.get(name, [])
            else:
                tmp = ast.literal_eval(str(name))
                if isinstance(tmp, (tuple, list)):
                    id_links = list(tmp)
                elif isinstance(tmp, str):
                    id_links = self.links_sets.get(tmp, [])
        except:
            try:
                id_links = self.links_sets.get(name, [])
            except:
                raise Exception(f"The links_sets {name} could not be identified")
        if len(id_links) == 0:
            self.log.warning(f"The links_sets {name} is empty")
        return id_links

    def _load_link_sets(self):
        self.log.info(f"Loading Links Sets...")
        if "links_sets" not in self.dparams["params"]:
            self.links_sets = {}
            self.log.warning("key 'links_sets' not found in execution parameters['params']")
        else:
            df_links_sets = pd.DataFrame()
            for id_set, set_params in enumerate(self.dparams["params"]["links_sets"]):
                set_params = set_params.copy()
                self.log.info(f"Loading Links Set {id_set}...")
                if "src" not in set_params:
                    raise KeyError("key 'src' required in links_sets parameters")
                mapping = {"set": "set", "id_link": "id_link"}
                if "mapping" in set_params:
                    mapping.update(set_params["mapping"])
                set_params["mapping"] = mapping
                tmp = self.load_sets(src=set_params["src"], mapping=set_params["mapping"])
                if tmp is None:
                    raise Exception(f"load_sets({set_params['src']}) function return None value")
                # tmp = BaseLoader._replace_mapping(df=tmp, mapping=mapping)
                df_links_sets = df_links_sets.combine_first(tmp)
            if df_links_sets.shape[0] == 0:
                self.links_sets = {}
            else:
                self.links_sets = df_links_sets.groupby("set").agg(list).to_dict()["id_link"]
            self.log.info(f"Links Sets identified {len(self.links_sets)}")
            
    def _load_detectors(self):
        self.log.info("Loading Detectors...")
        if "detectors" not in self.dparams["params"]:
            self.log.warning("key 'detectors' not found in execution parameters['params']")
            self.detectors = []
            self.counts = {}            
            return
        self.detectors = []
        counts = None
        for id_count, count_param in enumerate(self.dparams["params"]["detectors"]):
            self.log.info(f"Loading Detector {id_count}...")
            mode = count_param.get("mode", "c")            
            if mode not in self.modes:
                raise KeyError("mode '{mode}' not defined in modes parameter")
            if "src" not in count_param:
                raise KeyError("key 'src' required in detectors parameters")
            self.counts[mode] = {}

            count_param = count_param.copy()
            mapping = {"id": "id", "timestamp": "timestamp", "coutns": "counts"}
            mapping.update(count_param.get("mapping", {}))
            count_param["mapping"] = mapping
            tmp = self.load_detectors(src=count_param["src"], mapping=count_param["mapping"])
            if tmp is None:
                raise Exception(f"load_detectors({count_param['src']}) function return None value")
            tmp = BaseLoader.apply_mapping(df=tmp, mapping=mapping)
            eq_factor = self.modes.get(mode,{}).get("eq_factor",1)
            tmp["counts"] = tmp["counts"] * eq_factor
            if counts is None:
                counts = tmp
            else:
                counts = pd.concat([counts, tmp], axis="rows")
        self.detectors = sorted(list(counts["id"].unique()))
        self.counts = dict(counts.groupby(["id", "timestamp"]).agg(counts=("counts", "sum"))["counts"].to_dict())
        
        if "src" not in self.dparams["params"]["detectors"]:
            raise KeyError("key 'src' required in detectors parameters")
    def _load_demand(self):
        self.log.info("Loading OD Matrices...")
        if "demand" not in self.dparams["params"]:
            raise KeyError("key 'demand' not found in execution parameters['params']")
        modes = set()
        self.perc = {}
        self.ODs = {}
        self.OD = MatrixODT(rows=self.origins, cols=self.destinations, timestamps=self.timestamps, init=0, mode=None)
        for id_mat, od_param in enumerate(self.dparams["params"]["demand"]):
            self.log.info(f"Loading OD Matrix '{id_mat}'...")
            mode = od_param.get("mode", "c")            
            if mode not in self.modes:
                raise KeyError("mode '{mode}' not defined in modes parameter")
            if "matrices" not in od_param:
                raise KeyError("key 'matrices' required in demand element")
            modes.add(mode)
            if mode in self.ODs:
                OD = self.ODs[mode]
            else:
                OD = MatrixODT(rows=self.origins, cols=self.destinations, timestamps=self.timestamps, init=0, mode=mode)
                self.ODs[mode] = OD

            tot_od_pairs=0
            for id_m, mat_params in enumerate(od_param["matrices"]):
                self.log.info(f"Loading OD Sub Matrix '{id_mat}'-'{id_m}'...")
                mat_params = mat_params.copy()
                #if id_m == 0 and "src" not in mat_params and "scalar" not in mat_params:
                #    raise KeyError("key 'src' required in first matrices element")
                if "src" not in mat_params and "scalar" not in mat_params:
                    raise KeyError("key 'src' or 'scalar' required in matrices element")
                if "src" in mat_params:
                    mapping = {"o": "o", "d": "d", "value": "value", "timestamp": "timestamp"}
                    mapping.update(mat_params.get("mapping", {}))
                    mat_params["mapping"] = mapping
                    tmp = self.load_matrix(src=mat_params["src"], mapping=mat_params["mapping"])
                    tot_od_pairs += tmp.shape[0]
                    if tmp is None:
                        raise Exception(f"load_matrix({mat_params['src']}) function return None value")
                    tmp = MatrixODT.read_df(rows=self.origins,cols=self.destinations, timestamps=self.timestamps, df=tmp)
                if id_m==0:
                    OD += tmp
                else:
                    op = mat_params.get("op", "+")
                    if "src" in mat_params:
                        if op == "+":
                            OD += tmp
                        elif op == "-":
                            OD -= tmp
                        elif op == "*":
                            OD *= tmp
                        elif op == "/":
                            OD /= tmp
                    elif "scalar" in mat_params:
                        if op == "+":
                            OD += mat_params["scalar"]
                        elif op == "-":
                            OD -= mat_params["scalar"]
                        elif op == "*":
                            OD *= mat_params["scalar"]
                        elif op == "/":
                            OD /= mat_params["scalar"]
            
            self.OD += OD * self.modes.get(mode,{}).get("eq_factor",1)

        for id_mat, OD in self.ODs.items():
            tmp = OD / self.OD
            tmp.nan_to_num(copy=False)
            self.perc[id_mat] = tmp
        self.log.info(f"OD Matrices identified {len(self.ODs)}. OD Pairs: {tot_od_pairs}")
            
        

    def _load_graph(self):
        self.log.info("Loading Graph...")
        if self.ini.LOAD_GRAPH:
            self.log.info("Loading State (Graph)...")
            from ..writers.state_manager import StateManager
            sm = StateManager(params=self.dparams, settings=self.ini, loader=self)
            self._G = sm.load_state("graph")
            self.log.info("State loaded (Graph)")
            if self._G is not None:
                return
        if "supply" not in self.dparams["params"]:
            raise KeyError("key 'supply' not found in execution parameters['params']")
        df_links = None
        df_nodes = None
        df_turns = None
        mapping_links = {
            "id": "id",
            "from_node": "from_node",
            "to_node": "to_node",
            "v0": "v0",
            "connector": "connector",
            "lanes": "lanes",
            "alpha": "alpha",
            "rcr": "rcr",
            "capacity": "capacity",
            "length": "length",
        }
        mapping_nodes = {"id": "id"}
        mapping_turns = {"from_node": "from_node", "via_node": "via_node", "to_node": "to_node"}
        G = DynamicGraph(total_time=0, delta_t=self.delta_t, modes=self.modes)
        for id_net, net_param in enumerate(self.dparams["params"]["supply"]):
            self.log.info(f"Loading Net {id_net}")
            if "links_src" in net_param:
                mapping_links.update(net_param.get("mapping", {}).get("links", {}))
                tmp = self.load_links(src=net_param["links_src"], mapping=mapping_links)
                if tmp is None:
                    raise Exception(f"load_links({net_param['links_src']}) function return None value")
                # tmp = BaseLoader._replace_mapping(df=tmp,mapping=mapping)
                tmp.set_index("id")
                if df_links is None:
                    df_links = tmp
                else:
                    df_links = df_links.combine_first(tmp)
            if "nodes_src" in net_param:
                mapping_nodes.update(net_param.get("mapping", {}).get("nodes", {}))
                tmp = self.load_nodes(src=net_param["nodes_src"], mapping=mapping_nodes)
                if tmp is None:
                    raise Exception(f"load_nodes({net_param['nodes_src']}) function return None value")
                # tmp = BaseLoader._replace_mapping(df=tmp,mapping=mapping)
                tmp.set_index("id")
                if df_nodes is None:
                    df_nodes = tmp
                else:
                    df_nodes = df_nodes.combine_first(tmp)
            if "turns_src" in net_param:
                mapping_turns.update(net_param.get("mapping", {}).get("turns", {}))
                tmp = self.load_turns(src=net_param["turns_src"], mapping=mapping_turns)
                if tmp is None:
                    raise Exception(f"load_turns({net_param['turns_src']}) function return None value")
                # tmp = BaseLoader._replace_mapping(df=tmp,mapping=mapping)
                tmp.drop_duplicates().set_index(["from_node", "via_node", "to_node"])
                if df_turns is None:
                    df_turns = tmp
                else:
                    df_turns = df_turns.combine_first(tmp)
        df_nodes.reset_index(inplace=True)
        df_links.reset_index(inplace=True)
        df_turns.reset_index(inplace=True)
        self.log.info("Trasforming to graph")

        assert df_nodes is not None, "nodes not loaded"
        assert df_links is not None, "links not loaded"

        #kwargs_key = [c for c in df_nodes.columns if c not in mapping_nodes and c not in ("id", "is_centroid")]
        for _, row in df_nodes.iterrows():
            kwargs = {k: row[k] for k in mapping_nodes.keys()}
            kwargs["idx"]=int(row["id"])
            kwargs["is_centroid"]=int(row["id"]) in self.zones
            kwargs["time"]=TimeArrayAttribute(0)
            #[kwargs.pop(k,None) for k in set(mapping_nodes.values())]
            G.add_node(**kwargs)

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

        self.log.debug("Adding links to graph...")
        for _, row in df_links.iterrows():
            kwargs = {k: row[k] for k in mapping_links.keys()}
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
            kwargs["t0"]=float(row["length"] / row["v0"] * 60)
            kwargs["time"]=TimeArrayAttribute(float(row["length"] / row["v0"] * 60))
            kwargs["flow"]=TimeArrayAttribute(0)
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
                kwargs = {k: row[k] for k in mapping_turns.keys()}
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
                    kwargs["time"]=float("inf")
                    #[kwargs.pop(k,None) for k in set(mapping_turns.values())]
                    G.add_turn(**kwargs)

        G["origins"] = list(self.origins)
        G["destinations"] = list(self.destinations)
        G["zones"] = list(self.zones)        
        self._G = G
        self.log.info("Links identified {0}".format(G.n_links))
        self.log.info("Nodes identified {0}".format(G.n_nodes))
        self.log.info("Turns identified {0}".format(G.n_turns))

