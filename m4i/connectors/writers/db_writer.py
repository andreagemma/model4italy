# -*- coding: utf-8 -*-
"""
Created on Thu Jun 24 19:11:39 2021

@author: andge
"""

import pandas as pd
import numpy as np
import geopandas as gpd
from typing import *
import os
import sqlite3
from shapely import MultiLineString, get_geometry
from ast import literal_eval
from shapely import wkt
from ast import literal_eval

from ...utils import export_dataframe, multi_line_to_line
from . import BaseWriter
from ...graphs import KPathContainer
from .. import Loader
from ... import IniClass
import sqlalchemy as sa

from ...log import Logger

class DBWriter(BaseWriter):

    def __init__(self, params: Union[str, dict], settings: IniClass=None, loader: Loader=None):
        super().__init__(params=params, settings=settings, loader=loader, default_ext=".gpkg")

    def write_dataset(self, df: Union[pd.DataFrame, gpd.GeoDataFrame], 
                      parameters, 
                      **kwargs) -> bool:

        if df is None:
            warnings.warn(f"No dataset to write for {parameters}")
            return False
        
        location = parameters.get("location")
        src = parameters.get("src")
        
        if location is None:
            raise Exception("'location' not defined")
        if src is None:
            raise Exception("'src' not defined")
        
        engine = sa.create_engine(location)
        with engine.connect() as conn:
            pre_query = src.get("pre_query")   
            if pre_query:
                conn.execute(sa.text(pre_query))
            table_schema = src.split(".")             
            if len(table_schema) == 2:
                schema, table = table_schema
            elif len(table_schema) == 1:
                schema, table = "public", table_schema[0]
            else:
                raise ValueError(f"Invalid src format: {src}")
            if isinstance(df, gpd.GeoDataFrame):  
                df.to_postgis(src, schema=schema, con=conn, if_exists="append", chunksize=100, index=False)
            else:
                df.to_sql(table, schema=schema, con=conn, if_exists="append",method="multi", chunksize=1000, index=False)

            conn.commit()
            

 
