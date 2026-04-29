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
from sqlalchemy.orm import Session, sessionmaker
from ...log import Logger
import warnings
import json
import psycopg

class DBWriter(BaseWriter):

    def __init__(self):
        super().__init__()

    def write_dataset(self, df: Union[pd.DataFrame, gpd.GeoDataFrame], 
                      parameters, 
                      **kwargs) -> bool:

        if df is None:
            warnings.warn(f"No dataset to write for {parameters}")
            return False
        if isinstance(df, dict):
            df = pd.DataFrame(df)
        location = parameters.get("location")
        src = parameters.get("src")
        mode = parameters.get("mode")
        
        if location is None:
            raise Exception("'location' not defined")
        if src is None:
            raise Exception("'src' not defined")
        
        engine = sa.create_engine(location)
        with engine.begin() as conn:
            table_schema = src.split(".")             
            if len(table_schema) == 2:
                schema, table = table_schema
            elif len(table_schema) == 1:
                schema = parameters.get("schema", "public")
                table = table_schema[0]
            else:
                raise ValueError(f"Invalid src format: {src}")
            mode = parameters.get("mode","a")
            pre_query = parameters.get("pre_query")   
            first_query = kwargs.get("first_query", False)
            execute_pre_query = first_query and pre_query is not None and mode == "a"
            if execute_pre_query:
                if isinstance(pre_query, str):
                    pre_query = {
                        "query": pre_query
                    }
                
                if pre_query.get("query"):
                    errors = pre_query.get("errors", "raise")
                    try:
                        conn.execute(sa.text(f"SET LOCAL search_path TO {schema},public;"))
                        pre = conn.begin_nested()
                        try:
                            Logger.debug(f"Executing pre-query for {pre_query}...")
                            conn.execute(sa.text(pre_query.get("query")))
                            pre.commit()
                        except Exception as e:
                            pre.rollback()
                            if isinstance(e, sa.exc.ProgrammingError) and  isinstance(e.orig, psycopg.errors.UndefinedTable):
                                Logger.warning(f"Table not found in pre-query: {pre_query.get('query')}")    
                            else:
                                raise e                        
                    except Exception as e:
                        if errors=="raise":
                            raise e
                        elif errors == "ignore":
                            pass
                        elif errors == "warn":
                            Logger.warning(e.args[0])
                            warnings.warn(e.args[0])
            
            savepoint = conn.begin_nested()            
            rollback = False            
            if mode == "a":
                if_exists = "append"
            elif mode == "w":
                if_exists = "replace"
            elif mode == "t":                    
                try:                        
                    conn.execute(sa.text(f"TRUNCATE {schema}.{table}"))
                except:
                    savepoint.rollback()
                    rollback = True
                if_exists = "append"
            if isinstance(df, gpd.GeoDataFrame):  
                df.to_postgis(table, schema=schema, con=conn, if_exists=if_exists, chunksize=1000, index=False)
            else:
                df.to_sql(table, schema=schema, con=conn, if_exists=if_exists,method="multi", chunksize=1000, index=False)
            if not rollback:
                savepoint.commit()
            conn.commit()
            

 
