# -*- coding: utf-8 -*-
"""
Created on Thu Jun 24 19:11:39 2021

@author: andge
"""
import copy
import pandas as pd
import geopandas as gpd
from os.path import join
from typing import Any
import json
from typing import Union
from ...utils.io import IO_DataFrame

from .base_loader import BaseLoader

class FileLoader(BaseLoader):

    def __init__(self):
        super().__init__()

    def load_dataset(self,parameters, filters=None, dtype=None, **kwargs) -> Union[pd.DataFrame, gpd.GeoDataFrame, dict]:
        location = parameters.get("location")
        src = parameters.get("src")
        
        if location:
            src = join(location, src)
        if src.lower().endswith(".json"):
            with open(src,'r') as f:
                content = json.load(f)
            for i,row in enumerate(content):
                for k,v in row.items():
                    if isinstance(v,(list,dict)):
                        content[i][k] = json.dumps(v)
            return pd.DataFrame(content)
        iod = IO_DataFrame()
        df = iod.import_dataframe(src, filters=filters, dtype=dtype, **kwargs)
        #df = BaseLoader.import_dataframe_from_file(src, filters=filters, dtype=dtype, **kwargs)
        return df
    
    
