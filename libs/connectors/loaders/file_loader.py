# -*- coding: utf-8 -*-
"""
Created on Thu Jun 24 19:11:39 2021

@author: andge
"""
import pandas as pd
import geopandas as gpd
from os.path import join
from typing import Any
import json
from typing import Union

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
            return pd.DataFrame(content)
        df = BaseLoader.import_dataframe_from_file(src, filters=filters, dtype=dtype, **kwargs)
        return df
    
    
