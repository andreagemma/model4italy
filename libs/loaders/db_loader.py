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
import shapely.wkb
import sqlalchemy as sa
from shapely import from_wkb, Geometry, GeometryCollection

from . import BaseLoader
from ..utils import import_dataframe, generate_postgres_dns, parse_sqlalchemy_url

class DBLoader(BaseLoader):

    def __init__(self, params, settings=None):
        super().__init__(params, settings)


    def _load(self, src: str, mapping: dict[str,str] = None, **kwargs) -> Union[pd.DataFrame, gpd.GeoDataFrame, dict]:
        location, src = self.get_location_src(src, **kwargs)
        
        if location is None:
            raise Exception("'location' not defined")
        if src is None:
            raise Exception("'src' not defined")
        
        engine = sa.create_engine(location)
        with engine.connect() as conn:
            df = pd.read_sql(f"select * from ({src}) fooooooooooooooo1o1o1oo1o",con=conn)
            if df.shape[0]>0:
                for geom in ("geom","geometry"):
                    if geom in df.columns:
                        if isinstance(df[geom].iloc[0], str):                
                            df[geom]=from_wkb(df[geom])
                        df = gpd.GeoDataFrame(df, geometry=geom, crs="EPSG:4326")
                        break
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
        df["params"]=df["params"].apply(lambda x: x if isinstance(x,dict) else json.loads(x))
        df = pd.DataFrame(df)
        return df
    

    def load_traffic_ligths(self, src: Union[str,dict], **kwargs) -> dict:
        df = self._load(src=src, **kwargs)
        ret = []
        for idx, row in df.iterrows():
            if not isinstance(row["info"],dict):
                row["info"]=json.loads(row["info"])
            row["info"]["id"]=row["id"]
            ret.append(dict(row))
        return ret        
    
    