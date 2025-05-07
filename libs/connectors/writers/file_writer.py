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


from ...utils import export_dataframe, import_dataframe, multi_line_to_line
from ...graphs import KPathContainer
from . import BaseWriter
from .. import Loader
from ... import IniClass
from ... import Logger
class FileWriter(BaseWriter):

    def __init__(self):
        super().__init__()

    def write_dataset(self, df: Union[pd.DataFrame, gpd.GeoDataFrame], parameters, mode=None, partition=None, **kwargs) -> bool:
        if df is None:
            self.log.warning(f"No dataset to write for {parameters}")
            return False
        
        location = parameters.get("location")
        src = parameters.get("src")
        
        kwargs.setdefault("index",False)
        filename = os.path.normpath(join(location,src))        
        if partition is not None:
            location = join(filename,partition)
            filename = os.path.basename(filename)
            filename = join(location,filename)

        location = os.path.dirname(filename)
            
        if os.path.exists(location) and os.path.isfile(location):
            os.remove(location)
        os.makedirs(location, exist_ok=True)
        export_dataframe(df, filename, mode=mode, **kwargs)
        return True
        


    
