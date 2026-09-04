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
from ...utils.util import filters_to_query_expression
from ...utils.util import pandas_query_to_sql, sql_where_to_pandas


class DBLoader(BaseLoader):
    def __init__(self):
        super().__init__()

    def load_dataset(self, parameters, filters=None, dtype=None, **kwargs) -> Union[pd.DataFrame, gpd.GeoDataFrame]:
        location = parameters.get("location")
        src = parameters.get("src")

        if location is None:
            raise Exception("'location' not defined")
        if src is None:
            raise Exception("'src' not defined")

        engine = sa.create_engine(location)
        # if sqlite then load extension
        sql = f"select * from {src}"
        if filters:
            if isinstance(filters, str):
                df_filters = filters
            else:
                df_filters = filters_to_query_expression(filters, quoting="", op_boolean_symbols=True)
            sql_filters = pandas_query_to_sql(df_filters)
            sql = f"{sql} {sql_filters}"

        if engine.dialect.name == "sqlite":
            import sqlite3

            @sa.event.listens_for(engine, "connect")
            def load_spatialite(dbapi_conn, connection_record):
                if isinstance(dbapi_conn, sqlite3.Connection):
                    dbapi_conn.enable_load_extension(True)
                    dbapi_conn.load_extension("mod_spatialite")
                    dbapi_conn.enable_load_extension(False)

        with engine.connect() as conn:
            schema = parameters.get("schema", None)
            if schema:
                conn.execute(sa.text(f"SET LOCAL search_path TO {schema}"))
            try:
                df = pd.read_sql(sql, con=conn)
            except Exception as e:
                raise e

        df = BaseLoader.apply_dtype(df, dtype=dtype)
        return df
