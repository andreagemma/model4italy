import re
import importlib
import pkgutil
import warnings
from typing import Dict, List, Optional, Type, Union, Tuple
import pandas as pd
import geopandas as gpd
import dask.dataframe as dd
from m4i.database.database import Base
from m4i.utils.io.drivers.base_driver import BaseDriver


class IO_DaskDataFrame:
    def __init__(self, **kwargs):
        pass

    def detect_driver(self, path: str):
        re_file_formats = {
            "csv": re.compile(r"\.csv$"),
            "parquet": re.compile(r"\.parquet$"),
            "sql": re.compile(r"^(postgresql|mysql|sqlite|oracle|mssql)://"),
        }
        for driver, pattern in re_file_formats.items():
            if pattern.search(path):
                return driver
        raise ValueError(f"Nessun driver corrispondente all'url '{path}'.")

    def import_dataframe(
        self,
        path: str,
        driver: Optional[str] = None,
        filters: Optional[Union[dict, str]] = None,
        dtype: Optional[dict] = None,
        kwargs_driver: Optional[dict] = None,
        force_geodataframe: Optional[bool] = None,
        **kwargs,
    ) -> Union[pd.DataFrame, gpd.GeoDataFrame]:

        if not driver:
            driver = self._detect_driver(path)
        if not driver:
            raise ValueError(f"Driver non registrato per '{path}'.")
        if driver == "csv":
            df = dd.read_csv(path, **kwargs_driver)
            df = BaseDriver.apply_filters(df, filters)
        elif driver == "parquet":
            df = dd.read_parquet(path, filters=filters, **kwargs_driver)
        elif driver == "sql":
            from sqlalchemy import create_engine

            engine = create_engine(path)
            df = dd.read_sql(
                path,
                con=engine,
                index_col=kwargs.get("index_col", "id"),
                **kwargs_driver,
            )
            df = BaseDriver.apply_filters(df, filters)
        else:
            raise ValueError(f"Driver per '{path}' non supportato per l'importazione di DataFrame.")

        df = BaseDriver.adapt_dtype(df, dtype)
        return df
