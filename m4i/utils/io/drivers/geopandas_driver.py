import pandas as pd
import shapely
import time
import uuid
from ... import remove_path
import os
from typing import Optional, List, Union
from ..drivers import BaseDriver
from datetime import datetime
from os import getpid

from uuid import uuid4
from typing import Generator, Any
import geopandas as gpd
from geopandas import GeoDataFrame
import warnings
from pathlib import Path
import polars as pl
import glob
import shutil, tempfile
class GeoPandasDriver(BaseDriver):

    @classmethod
    def name(cls) -> str:
        return "geopandas"

    @classmethod
    def pattern(cls) -> List[str]:
        return [
            r"\.shp$",
            r"\.gpkg$",
            r"\.geoparquet$",
            r"\.csv$",
            r"\.xlsx?$",
            r"\.parquet$",
            r"\.feather$",
        ]

    def import_dataframe(
        self,
        path: str,
        filters: Optional[dict] = None,
        dtype: Optional[dict] = None,
        **kwargs
    ) -> pd.DataFrame:
        crs = kwargs.pop("crs", None)
        pathg: Path = Path(path)
        files = pathg.glob("**/*") if pathg.is_dir() else [pathg]
        files = [file for file in files if file.is_file() and file.suffix.lower() in pathg.suffix.lower()]
        files = sorted(files, key=lambda f: f.stat().st_ctime)
        if pathg.suffix.lower()==".csv":
            df = pl.scan_csv(files).collect().to_pandas()
            #df = BaseDriver.reduce_folder(path, lambda x,y: pd.concat([x,y]), lambda path: pd.read_csv(path, dtype=dtype, **kwargs))
            df = BaseDriver.apply_filters(df, filters)
        elif path.lower().endswith(".xlsx") or path.lower().endswith(".xls"):
            df = pl.concat([pl.read_excel(file, engine="openpyxl", **kwargs) for file in files]).to_pandas()
            #df = BaseDriver.reduce_folder(path, lambda x,y: pd.concat([x,y]), lambda path: pd.read_excel(path, dtype=dtype, **kwargs))
            df = BaseDriver.apply_filters(df, filters)
        elif path.lower().endswith(".feather"):
            df = pl.scan_ipc(files).collect().to_pandas()
            #df = BaseDriver.reduce_folder(path, lambda x,y: pd.concat([x,y]), lambda path: pd.read_feather(path, **kwargs))
            df = BaseDriver.adapt_dtype(df, dtype)
            df = BaseDriver.apply_filters(df, filters)
        elif path.lower().endswith(".parquet"):
            kwargs={}
            df = pd.concat([pd.read_parquet(file, filters=filters) for file in files])
            df = BaseDriver.adapt_dtype(df, dtype)
        elif path.lower().endswith(".shp"):
            df = pd.concat([gpd.read_file(file) for file in files])
            df = BaseDriver.adapt_dtype(df, dtype)
            df = BaseDriver.apply_filters(df, filters)
        elif path.lower().endswith(".gpkg"):
            df = BaseDriver.reduce_folder(path, lambda path: gpd.read_file(path))
            df = BaseDriver.adapt_dtype(df, dtype)
            df = BaseDriver.apply_filters(df, filters)
        elif path.lower().endswith(".geoparquet"):
            df = gpd.read_parquet(path, filters=filters)
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
        template: str = "{filename}-{i}",
        **kwargs
    ):
        if isinstance(df, dict):
            df = pd.DataFrame.from_dict(df)
        crs = kwargs.pop("crs", None)        
        index = kwargs.pop("index", False)
        file = Path(path)
        if file.suffix.lower() == ".shp":
            files = file.parent.glob(file.with_suffix(".*").name)
            files = [f for f in files if f.is_file() and f.suffix.lower() in (".shp", ".shx", ".dbf", ".prj", ".cpg", ".sbn", ".sbx", ".fbn", ".fbx", ".ain", ".aih", ".atx") or str(f).endswith(".shp.xml")]
        else:
            files = [file]
        if partitionby is None or len(partitionby)==0:
            if mode in ("wa","aw"):
                mode = "a"
        if mode == "w":
            for f in files:
                remove_path(str(f))            
        append_directly = file.suffix.lower() in (".shp", ".gpkg", ".csv")
        if partitionby is None or len(partitionby)==0:
            if file.exists():
                if file.is_file() and not append_directly:
                    temp_dir = Path(tempfile.TemporaryDirectory().name)
                    temp_dir.mkdir(exist_ok=True)
                    #destinazione = os.path.join(temp_dir , file.name)
                    dest_files = []
                    for f in files:
                        dest_file = Path(os.path.join(temp_dir, f.name))
                        dest_files.append(dest_file)
                        shutil.move(f, str(dest_file))
                        remove_path(str(f))
                    file = file / file.name
                    file.parent.mkdir(exist_ok=True)

                    d = datetime.now()
                    date = d.strftime("%Y%m%d%H%M%S")
                    timestamp = d.timestamp()
                    uid = str(uuid4())
                    pid = getpid()
                    file_name = template.format(
                        filename=file.stem,
                        date = date, uid=uid,pid=pid, timestamp=timestamp,
                        partition='',
                        partitions_hive="",
                        i="0",
                    )
                    new_file = file.with_stem(file_name)
                    new_file.parent.mkdir(exist_ok=True)
                    for f in dest_files:
                        shutil.move(f, new_file.with_suffix(f.suffix))
                    file_name = template.format(
                        filename=file.stem,
                        date = date, uid=uid,pid=pid, timestamp=timestamp,
                        partition='',
                        partitions_hive="",
                        i="1",
                    )
                    file = new_file.with_stem(file_name)                    

                elif file.is_dir():
                    file = file / file.name

                    d = datetime.now()
                    date = d.strftime("%Y%m%d%H%M%S")
                    timestamp = d.timestamp()
                    uid = str(uuid4())
                    pid = getpid()
                    file_name = template.format(
                        filename=file.stem,
                        date = date, uid=uid,pid=pid, timestamp=timestamp,
                        partition='',
                        partitions_hive="",
                        i="*",
                    )
                    i = len(list(file.parent.glob(file.with_stem(file_name).name)))
                    file_name = template.format(
                        filename=file.stem,
                        date = date, uid=uid,pid=pid, timestamp=timestamp,
                        partition='',
                        partitions_hive="",
                        i=str(int(i) + 1),
                    )
                    file = file.with_stem(file_name)
            file.parent.mkdir(exist_ok=True)
            if file.suffix.lower()==".geoparquet":
                df = BaseDriver.to_geodataframe(df, crs)
                for col in df.columns:
                    if df[col].dtype.name.startswith("datetime64"):
                        df[col] = df[col].dt.strftime("%Y-%m-%d %H:%M:%S")                
                df.to_parquet(str(file), index=index, **kwargs)
            elif file.suffix.lower()==".parquet":
                df = BaseDriver.to_dataframe(df)
                for col in df.columns:
                    if df[col].dtype.name.startswith("datetime64"):
                        df[col] = df[col].dt.strftime("%Y-%m-%d %H:%M:%S")
                df.to_parquet(str(file), index=index, **kwargs)
            elif file.suffix.lower()==".shp":
                df = BaseDriver.to_geodataframe(df, crs)
                for col in df.columns:
                    if df[col].dtype.name.startswith("datetime64"):
                        df[col] = df[col].dt.strftime("%Y-%m-%d %H:%M:%S")
                df.to_file(str(file), index=index, mode=mode, **kwargs)
            elif file.suffix.lower()==".gpkg":
                df = BaseDriver.to_geodataframe(df, crs)
                df.to_file(str(file), index=index, mode=mode, **kwargs)
            elif file.suffix.lower()==".csv":
                df = BaseDriver.to_dataframe(df)
                df.to_csv(str(file), index=index, mode=mode, header=mode=="w")
            elif file.suffix.lower() in (".xlsx", ".xls"):
                df = BaseDriver.to_dataframe(df)
                df.to_excel(str(file), index=index)
            elif file.suffix.lower()==".feather":
                df = BaseDriver.to_dataframe(df)
                df.to_feather(str(file))
            elif file.suffix.lower() in (".pkl", ".pickle"):
                df.to_pickle(str(file))                
            else:
                raise ValueError(f"Formato file non supportato: {path}")
        else:
            def fn(grp, path, **kwargs):
                partition_values, partitionBy, df = grp
                if path.lower().endswith(".geoparquet") or path.lower().endswith(".parquet"):
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
