import pandas as pd
import time
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
import glob
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
        df: Union[pd.DataFrame, gpd.GeoDataFrame, dict],
        path: str,
        mode: str = "w",
        partitionby: Optional[List[str]] = None,
        template: str = "{filename}-{partition}-{i}",
        **kwargs
    ):
        if isinstance(df, dict):
            df = pd.DataFrame.from_dict(df)
        crs = kwargs.pop("crs", None)
        df = BaseDriver.to_geodataframe(df, crs)
        index = kwargs.pop("index", False)
        if partitionby is None or len(partitionby)==0:
            if mode in ("wa","aw"):
                mode = "a"
        if mode == "w":
            remove_path(path)
            mode="a"
        if partitionby is None or len(partitionby)==0:            
            
            if path.lower().endswith(".geoparquet"):
                df.to_parquet(path, index=index, **kwargs)
            elif path.lower().endswith(".shp"):
                for col in df.columns:
                    if df[col].dtype.name.startswith("datetime64"):
                        df[col] = df[col].dt.strftime("%Y-%m-%d %H:%M:%S")
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
                path= os.path.join(path,*partitions_hive)
                os.makedirs(path, exist_ok=True)

                d = datetime.now()
                date = d.strftime("%Y%m%d%H%M%S")
                timestamp = d.timestamp()
                uid = str(uuid4())
                pid = getpid()
                file_name = template.format(
                    filename=os.path.splitext(filename)[0],
                    date = date, uid=uid,pid=pid, timestamp=timestamp,
                    partition='-'.join((str(x) for x in partition_values)),
                    partitions_hive='-'.join(partitions_hive),
                    i="*",
                )
                i = len(glob.glob(os.path.join(path,f"{file_name}{extension}")))
                file_name = file_name = template.format(
                    filename=os.path.splitext(filename)[0],
                    date = date, uid=uid,pid=pid, timestamp=timestamp,
                    partition='-'.join((str(x) for x in partition_values)),
                    partitions_hive='-'.join(partitions_hive),
                    i=str(int(i) + 1),
                )
                new_file = os.path.join(path, file_name + extension)
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
