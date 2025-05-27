import pandas as pd
import uuid
from ... import remove_path
import os
from typing import Optional, List, Union
from . import BaseDriver
from datetime import datetime
from os import getpid

from uuid import uuid4
from typing import Generator, Any
import geopandas as gpd
from geopandas import GeoDataFrame
import warnings

class GeoPandasDriver(BaseDriver):

    @property
    def name(self) -> str:
        return "geopandas"

    @property
    def pattern(self) -> List[str]:
        return [
            r"\.shp$",
            r"\.gpkg$",
            r"\.geoparquet$",
        ]

    def import_dataframe(
        self,
        path: str,
        filters: Optional[dict] = None,
        dtype: Optional[dict] = None,
        **kwargs
    ) -> pd.DataFrame:
        crs = kwargs.pop("crs", None)
        if path.lower().endswith(".shp"):
            df = BaseDriver.reduce_folder(path, lambda path: gpd.read_file(path, **kwargs))
            df = BaseDriver.adapt_dtype(df, dtype)
            df = BaseDriver.apply_filters(df, filters)
        elif path.lower().endswith(".gpkg"):
            df = BaseDriver.reduce_folder(path, lambda path: gpd.read_file(path, **kwargs))
            df = BaseDriver.adapt_dtype(df, dtype)
            df = BaseDriver.apply_filters(df, filters)
        elif path.lower().endswith(".geoparquet"):
            df = gpd.read_parquet(path, filters=filters, **kwargs)
            df = BaseDriver.adapt_dtype(df, dtype)
        else:
            raise ValueError(f"Formato file non supportato: {path}")
        df = BaseDriver.to_geodataframe(df, crs)
        return df

    def export_dataframe(
        self,
        df: gpd.GeoDataFrame,
        path: str,
        mode: str = "w",
        partitionby: Optional[List[str]] = None,
        **kwargs
    ):
        crs = kwargs.pop("crs", None)
        df = BaseDriver.to_geodataframe(df, crs)
        index = kwargs.pop("index", False)
        if partitionby is None or len(partitionby)==0:
            if mode in ("wa","aw"):
                mode = "a"
        if mode == "w":
            remove_path(path)
        if partitionby is None or len(partitionby)==0:            
            if path.lower().endswith(".geoparquet"):
                df.to_parquet(path, index=index, **kwargs)
            else:
                if path.lower().endswith(".shp"):
                    df.to_file(path, index=index, mode=mode, **kwargs)
                elif path.lower().endswith(".gpkg"):
                    df.to_file(path, index=index, **kwargs)
                else:
                    raise ValueError(f"Formato file non supportato: {path}")
        else:
            def fn(grp, path, **kwargs):
                partition_values, partitionBy, df = grp
                if path.lower().endswith(".geoparquet"):
                    for partition in partitionby:
                        df.drop(partition, axis=1, inplace=True)
                filename = os.path.basename(path)
                extension = os.path.splitext(filename)[1]
                partitions_hive = [str(p) + "=" + str(v) for p,v in zip(partitionBy, partition_values)]
                uid = str(int(datetime.now().timestamp())) + "_" + str(uuid4()) + "_" + str(getpid()) + extension
                path= os.path.join(path,*partitions_hive)
                os.makedirs(path, exist_ok=True)
                new_file = os.path.join(path, uid)
                self.export_dataframe(
                    df=df,
                    path=new_file,
                    mode="a",
                    partitionby=None, 
                    **kwargs
                )
            for partition in partitionby:
                if partition not in df.columns:
                    raise ValueError(f"Colonna '{partition}' non trovata nel DataFrame.")
            BaseDriver.map_partitioned_dataframe(
                df,
                partitionby,
                fn,
                path=path,
                **kwargs
            )
