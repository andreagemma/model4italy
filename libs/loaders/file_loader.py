# -*- coding: utf-8 -*-
"""
Created on Thu Jun 24 19:11:39 2021

@author: andge
"""
import pandas as pd
import geopandas as gpd
from os.path import join
import time
from typing import Any
import json
from typing import Union

from . import BaseLoader
from ..utils import import_dataframe

class FileLoader(BaseLoader):

    def __init__(self, params, settings=None):
        super().__init__(params, settings)

    def _load(self,src: str, mapping: dict[str,str]=None, filters = None, dtype=None, **kwargs) -> Union[pd.DataFrame, gpd.GeoDataFrame, dict]:
        location, src = self.get_location_src(src, **kwargs)
        
        if location:
            src = join(location, src)
        if src.lower().endswith(".json"):
            with open(src,'r') as f:
                content = json.load(f)
            return content
        else:        
            df = import_dataframe(src, filters=filters, dtype=dtype)
        if mapping:
            df = BaseLoader.apply_mapping(df=df,mapping=mapping)    
        
        return df

    def load_detectors(self, src: Union[str,dict], mapping: dict[str,str], **kwargs) -> pd.DataFrame:
        timestamp_into_filename = mapping.get("timestamp", False)
        df = self._load(src=src, mapping=mapping, filters = [[(timestamp_into_filename,">=",self.start),(timestamp_into_filename,"<",self.end)]],
                        dtype={timestamp_into_filename: "Int16"}, **kwargs)
        df = pd.DataFrame(df)
        #df = df[df["timestamp"].astype(float).between(self.start,self.end)]
        return df            

    def load_matrix(self, src: str, mapping: dict[str,str], **kwargs) -> pd.DataFrame:
        timestamp_into_filename = mapping.get("timestamp", False)
        df = self._load(src=src, mapping=mapping, filters = [[(timestamp_into_filename,">=",self.start),(timestamp_into_filename,"<",self.end)]],
                        dtype={timestamp_into_filename: "Int16"}, **kwargs)
        df = pd.DataFrame(df)
        #df = df[df["timestamp"].astype(float).between(self.start,self.end)]
        return df            
    
    def load_nodes(self, src: Any, mapping: dict[str,str], **kwargs) -> pd.DataFrame:
        df = self._load(src=src, mapping=mapping, **kwargs)
        df = pd.DataFrame(df)
        return df

    def load_links(self, src: Any, mapping: dict[str,str], **kwargs) -> pd.DataFrame:
        df = self._load(src=src, mapping=mapping, **kwargs)
        df = pd.DataFrame(df)
        return df

    def load_turns(self, src: Any, mapping: dict[str,str], **kwargs) -> pd.DataFrame:
        df = self._load(src=src, mapping=mapping, **kwargs)
        df = pd.DataFrame(df)
        return df

    def load_zones(self, src: Any, mapping: dict[str,str], **kwargs) -> pd.DataFrame:
        df = self._load(src=src, mapping=mapping, **kwargs)
        df = pd.DataFrame(df)
        return df

    def load_sets(self, src: Any, mapping: dict[str,str], **kwargs) -> pd.DataFrame:
        df = self._load(src=src, mapping=mapping, **kwargs)
        df = pd.DataFrame(df)
        return df

    def load_events(self, src: Any, mapping: dict[str,str], **kwargs) -> pd.DataFrame:
        df = self._load(src=src, mapping=mapping, **kwargs)
        df = pd.DataFrame(df)
        return df

    def load_traffic_ligths(self, src: Any, **kwargs) -> dict:
        content = self._load(src=src, **kwargs)
        return content
    
