# -*- coding: utf-8 -*-
"""
Created on Thu Jun 24 19:11:39 2021

@author: andge
"""
import pandas as pd
import geopandas as gpd
import sqlite3
from typing import Union

from .base_loader import BaseLoader

class GpkgLoader(BaseLoader):

    def __init__(self):
        super().__init__()


    def load_dataset(self,parameters, filters=None, dtype=None, **kwargs) -> Union[pd.DataFrame, gpd.GeoDataFrame, dict]:
        location = parameters.get("location")
        src = parameters.get("src")
        
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
        df = BaseLoader.apply_dtype(df, dtype=dtype)
        if filters:
            filters = BaseLoader.filters_to_query_expression(filters=filters)
            df = df.query(filters)
        return df
    

    