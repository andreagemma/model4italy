# -*- coding: utf-8 -*-
"""
Created on Thu Jun 24 19:11:39 2021

@author: andge
"""
import pandas as pd
import geopandas as gpd
import json
import sqlite3
from typing import Union
import ast

from . import BaseLoader
from ..utils import import_dataframe

class GpkgLoader(BaseLoader):

    def __init__(self, params, settings=None):
        super().__init__(params, settings)


    def _load(self, src: str, mapping: dict[str,str] = None, **kwargs) -> Union[pd.DataFrame, gpd.GeoDataFrame, dict]:
        location, src = self.get_location_src(src, **kwargs)
        
        if location is None:
            raise Exception("'location' not defined")
        if src is None:
            raise Exception("'src' not defined")
        
        if location.lower().endswith("gpkg"):
            df = gpd.read_file(filename=location, layer=src)
            if not "geometry" in df.columns:
                df = pd.DataFrame(df)
        else:
            with sqlite3.connect(location) as conn:
                sql = f"select * from {src} as t"
                df = pd.read_sql_query(sql=sql,con=conn)
        if mapping:
            df = BaseLoader.apply_mapping(df=df,mapping=mapping)    
        return df

    def load_detectors(self, src: Union[str,dict], mapping: dict[str,str], **kwargs) -> pd.DataFrame:
        df = self._load(src=src, mapping=mapping, **kwargs)
        df = df[df["timestamp"].between(self.start,self.end)]
        return df            
    
    def load_matrix(self, src: Union[str,dict], mapping: dict[str,str], **kwargs) -> pd.DataFrame:
        df = self._load(src=src, mapping=mapping, **kwargs)
        df = df[df["timestamp"].between(self.start,self.end)]
        return df            
    
    def load_nodes(self, src: Union[str,dict], mapping: dict[str,str], **kwargs) -> pd.DataFrame:
        df = self._load(src=src, mapping=mapping, **kwargs)
        df= pd.DataFrame(df)
        return df

    def load_links(self, src: Union[str,dict], mapping: dict[str,str], **kwargs) -> pd.DataFrame:
        df = self._load(src=src, mapping=mapping, **kwargs)
        df= pd.DataFrame(df)
        return df

    def load_turns(self, src: Union[str,dict], mapping: dict[str,str], **kwargs) -> pd.DataFrame:
        df = self._load(src=src, mapping=mapping, **kwargs)
        df= pd.DataFrame(df)
        return df

    def load_zones(self, src: Union[str,dict], mapping: dict[str,str], **kwargs) -> pd.DataFrame:
        df = self._load(src=src, mapping=mapping, **kwargs)
        df = pd.DataFrame(df)
        return df

    def load_sets(self, src: Union[str,dict], mapping: dict[str,str], **kwargs) -> pd.DataFrame:
        df = self._load(src=src, mapping=mapping, **kwargs)
        df = pd.DataFrame(df)
        return df

    def load_events(self, src: Union[str,dict], mapping: dict[str,str], **kwargs) -> pd.DataFrame:
        df = self._load(src=src, mapping=mapping, **kwargs)
        df = pd.DataFrame(df)
        return df

    def load_traffic_ligths(self, src: Union[str,dict], **kwargs) -> dict:
        df = self._load(src=src, **kwargs)
        ret = []
        for idx, row in df.iterrows():
            content = json.loads(row["info"])
            content["id"]=row["id"]
            ret.append(content)
        return ret        
    
    