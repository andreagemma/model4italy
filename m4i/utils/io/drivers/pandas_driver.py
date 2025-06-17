import geopandas
import pandas as pd
import uuid
from ... import remove_path
import os
from typing import Optional, List, Union
from ..drivers import BaseDriver
from datetime import datetime
from os import getpid

from uuid import uuid4
from typing import Generator, Any
from pathlib import Path
import polars as pl
import glob
class PandasDriver(BaseDriver):

    @property
    def name(self) -> str:
        return "pandas"

    @property
    def pattern(self) -> List[str]:
        return [
            r"\.csv$",
            r"\.xlsx?$",
            r"\.parquet$",
            r"\.feather$",
            r"\.pkl$",
            r"\.pickle$",
        ]

    def import_dataframe(
        self,
        path: str,
        filters: Optional[dict] = None,
        dtype: Optional[dict] = None,
        **kwargs
    ) -> pd.DataFrame:        
        pathg: Path = Path(path)
        files = pathg.glob("**/*") if pathg.is_dir() else [pathg]
        files = [file for file in files if file.is_file() and file.suffix.lower() in pathg.suffix.lower()]
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
        elif path.lower().endswith(".pkl") or path.lower().endswith(".pickle"):
            df = pd.concat([pd.read_pickle(file, **kwargs) for file in files])
            #df = BaseDriver.reduce_folder(path, lambda x,y: pd.concat([x,y]), lambda path:  pd.read_pickle(path, **kwargs))
            df = BaseDriver.adapt_dtype(df, dtype)
            df = BaseDriver.apply_filters(df, filters)
        elif path.lower().endswith(".parquet"):
            df = pd.concat([pd.read_parquet(file, filters=filters, **kwargs) for file in files])
            #df = pd.read_parquet(path, filters=filters, **kwargs)
            df = BaseDriver.adapt_dtype(df, dtype)
        else:
            raise ValueError(f"Formato file non supportato: {path}")
        df = BaseDriver.to_dataframe(df)
        return df

    def export_dataframe(
        self,
        df: pd.DataFrame,
        path: str,
        mode: str = "w",
        partitionby: Optional[List[str]] = None,
        template: str = "{filename}-{partition}-{i}",
        **kwargs
    ):
        if isinstance(df, geopandas.GeoDataFrame):
            tmp = pd.DataFrame(df.drop("geometry", axis=1, errors="ignore"))
            tmp["geometry"] = df.geometry.to_wkt()
            kwargs.pop("crs")
            df = tmp
        index = kwargs.pop("index", False)
        if partitionby is None or len(partitionby)==0:
            if mode in ("wa","aw"):
                mode = "a"
        if mode == "w":
            remove_path(path)
            mode="a"
        if partitionby is None or len(partitionby)==0:
            if path.lower().endswith(".parquet"):
                for col in df.columns:
                    if df[col].dtype.name.startswith("datetime64"):
                        df[col] = df[col].dt.strftime("%Y-%m-%d %H:%M:%S")
                df.to_parquet(path, index=index, **kwargs)
            else:
                if path.lower().endswith(".csv"):
                    df.to_csv(path, index=index, mode=mode)
                elif path.lower().endswith(".xlsx") or path.lower().endswith(".xls"):
                    df.to_excel(path, index=index)
                elif path.lower().endswith(".feather"):
                    df.to_feather(path)
                elif path.lower().endswith(".pkl") or path.lower().endswith(".pickle"):
                    df.to_pickle(path)
                else:
                    raise ValueError(f"Formato file non supportato: {path}")
        else:
            def fn(grp, path, **kwargs):
                partition_values, partitionBy, df = grp
                if path.lower().endswith(".parquet"):
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
