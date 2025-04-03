from __future__ import annotations


import pandas as pd
import numpy as np
import geopandas as gpd
from typing import Union, Any
from collections import namedtuple, defaultdict
import json
from datetime import datetime
import ast, os, shutil
from os import path
from os.path import join
from importlib import import_module
from abc import ABC, abstractmethod

from ..matrix_od import MatrixODT
from ..graphs import DynamicGraph, TimeArrayAttribute, CallableAttribute, KPathContainer
from ..utils import util
from ..loaders import BaseLoader
from .. import IniClass
from .. import Logger

from ..utils import save_dict, load_dict


class StateManager(object):
    def __init__(self, params: Union[str, dict], settings: IniClass=None, loader: BaseLoader=None, default_ext=".pickle.xz"):
        self.log = Logger.getLogger(self.__class__.__name__, execution_id=params.get("execution_id"))
        self.ini: IniClass = settings
        self.loader: BaseLoader = loader
        self.default_ext = default_ext
    
    
    def has_write_state(self):
        params = self.loader.dparams.get("params",{}).get("output",{}).copy()
        return params.get("state")
    
    def load_state(self, name, partition=None, **kwargs) -> dict:
        params = self.loader.dparams.get("params",{}).get("output",{}).copy()
        location = params.get("state")
        if location is None:
            raise Exception("'state' not defined")
        location = join(location,name)
        if partition is not None:
            location = join(location,partition)
        kwargs.setdefault("index",False)
        kwargs.setdefault("partition",partition)
        location = self.loader.get_name(location, **kwargs)
        location = join(location, name+self.default_ext)
        if not os.path.exists(location):
            return None
        return load_dict(location, compression="lzma")
        

    def write_state(self, object,  name, mode="w", partition=None,**kwargs):
        if object is None:
            self.log.warning(f"No state {name} to write")
            return
        
        params = self.loader.dparams.get("params",{}).get("output",{}).copy()
        location = params.get("state")
    
        if location is None:
            raise Exception("'state' not defined")

        location = join(location,name)

        if partition is not None:
            location = join(location,partition)        
        if mode=="w":
            if os.path.exists(location):
                if os.path.isdir(location):
                    shutil.rmtree(location, ignore_errors=True)
                else:
                    os.remove(location)
        kwargs.setdefault("index",False)
        kwargs.setdefault("partition",partition)
        
        location=self.loader.get_name(location, **kwargs)

        os.makedirs(location, exist_ok=True)
        location = join(location, name+self.default_ext)
        save_dict(object, location, compression="lzma")