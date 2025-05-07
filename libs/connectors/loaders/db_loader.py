# -*- coding: utf-8 -*-
"""
Created on Thu Jun 24 19:11:39 2021

@author: andge
"""
import pandas as pd
import geopandas as gpd
from typing import Union
import sqlalchemy as sa


from .base_loader import BaseLoader

class DBLoader(BaseLoader):

    def __init__(self):
        super().__init__()

    
    def load_dataset(self, parameters, filters=None, dtype=None,  **kwargs) -> Union[pd.DataFrame, gpd.GeoDataFrame]:
        location = parameters.get("location")
        src = parameters.get("src")
                
        if location is None:
            raise Exception("'location' not defined")
        if src is None:
            raise Exception("'src' not defined")
        
        engine = sa.create_engine(location)
        sql = f"select * from {src}"
        if filters:
            filters = BaseLoader.filters_to_query_expression(filters=filters)
            sql += f" WHERE {filters}"

        with engine.connect() as conn:
            df = pd.read_sql(sql,con=conn)
        
        df = BaseLoader.apply_dtype(df, dtype=dtype)
        return df
    
