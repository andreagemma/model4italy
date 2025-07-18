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
import copy

from ..matrix import MatrixODT
from ..graphs import DynamicGraph, DynamicTimeArrayAttribute, DynamicCallableAttribute, KPathContainer
from ..utils import util
from .. import ParamsParser
from .. import IniClass
from ..log import Logger

from ..utils import save_dict, load_dict


class StateManager(object):
    def __init__(self, parser: ParamsParser):
        self.parser = parser
        self.execution_id = self.parser.get("execution_id")
        self.log = Logger.getLogger(self.__class__.__name__, execution_id=self.execution_id)
        self.ini: IniClass = self.parser.ini
        self.default_ext = f".pickle.{self.parser.ini.OUTPUT_STATE_COMPRESSION}" if self.parser.ini.OUTPUT_STATE_COMPRESSION else ".pickle"
        self.compression = self.parser.ini.OUTPUT_STATE_COMPRESSION
        self.clevel = self.parser.ini.OUTPUT_STATE_LEVEL_COMPRESSION
    
    
    def has_write_state(self):
        return self.parser.get("params.state") is not None
        
    
    def load_state(self, name, partition=None, **kwargs) -> dict:
        parameters = self.parser.get_input_parameters("params.state")
        location = parameters.get("location", None)
        src = parameters.get("src", None)
        if location:
            src = join(location, src) if src else location
        if src is None:
            raise Exception("'state' not defined")
        if not isinstance(src, str):
            raise Exception("'state' hase to be a string indicating the folder location")

        src = join(src,name)
        if partition is not None:
            src = join(src,partition)
        kwargs.setdefault("index",False)
        kwargs.setdefault("partition",partition)
        src = self.parser.get_parametric_name(src, **kwargs)
        src = join(src, name+self.default_ext)
        if not os.path.exists(src):
            return None
        return load_dict(src, compression=self.compression)
        

    def write_state(self, object,  name, mode="w", partition=None,**kwargs) ->bool:
        if object is None:
            self.log.warning(f"No state {name} to write")
            return
        
        parameters = self.parser.get_input_parameters("params.state")
        location = parameters.get("location", None)
        src = parameters.get("src", None)
        if location:
            src = join(location, src) if src else location
        if src is None:
            raise Exception("'state' not defined")
        if not isinstance(src, str):
            raise Exception("'state' hase to be a string indicating the folder location")
        
        if partition is not None:
            src = join(src,partition)        
        if mode=="w":
            if os.path.exists(src):
                if os.path.isdir(src):
                    shutil.rmtree(src, ignore_errors=True)
                else:
                    os.remove(src)
        kwargs.setdefault("index",False)
        kwargs.setdefault("partition",partition)
        
        #location = self.parser.get_parametric_name(location, **kwargs)

        os.makedirs(src, exist_ok=True)
        src = join(src, name+self.default_ext)
        save_dict(object, src, compression=self.compression, clevel=self.clevel)