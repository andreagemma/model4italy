import datetime
import re
import typing
import pandas as pd
import geopandas as gpd
from typing import Dict, List, Optional, Union, Tuple, Generator, Any, Callable, Sequence
from functools import reduce
import glob
from pathlib import Path
import os
from shapely import wkt
import shapely.wkb
from shapely.wkt import dumps as wkt_dumps
from shapely import from_wkb, to_wkt, from_wkt
import polars as pl
import warnings


def inner_filter_to_query_expression(filters, rename=None, quoting='"', op_boolean_symbols=False):
    """
    Converte un filtro interno (tupla o lista di triple) in un'espressione booleana.

    Esempio:
    filters = [('age', '>', 18), ('country', '==', 'Italy')]
    → "(\"age\" > 18) OR (\"country\" == 'Italy')"
    """
    expressions = []
    if isinstance(filters, (tuple, list)):
        filter_list = filters if (len(filters) != 3 or not isinstance(filters[0], str)) else [filters]
        for f in filter_list:
            if not (isinstance(f, (tuple, list)) and len(f) == 3):
                raise ValueError("Ogni filtro deve essere una tupla/lista con 3 elementi (colonna, operatore, valore).")
            column, operator, value = f
            if rename and column in rename:
                column = rename[column]
            if isinstance(value, str):
                value = f"'{value}'"
            expressions.append(f"({quoting}{column}{quoting} {operator} {value})")
    else:
        raise ValueError("Il filtro interno deve essere una tupla o lista di filtri.")
    
    return (" | " if op_boolean_symbols else " OR ").join(expressions)


def filters_to_query_expression(filters, rename=None, quoting='"', op_boolean_symbols=False):
    """
    Converte una lista di gruppi di filtri in un'unica espressione booleana.

    Esempio:
    filters = [
        [('age', '>', 18)],
        [('country', '==', 'Italy'), ('city', '==', 'Rome')]
    ]
    → "((\"age\" > 18)) AND ((\"country\" == 'Italy') OR (\"city\" == 'Rome'))"
    """
    if isinstance(filters, str):
        return filters  # già una stringa di query

    if not isinstance(filters, (list, tuple)):
        raise ValueError("Il parametro filters deve essere una stringa o una lista di gruppi di filtri.")

    group_expressions = [
        inner_filter_to_query_expression(group, rename=rename, quoting=quoting, op_boolean_symbols=op_boolean_symbols)
        for group in filters
    ]
    
    return (" & " if op_boolean_symbols else " AND ").join(f"({g})" for g in group_expressions)


class BaseDriver:
    
    def __init__(self, **kwargs):
        self._init_kwargs = kwargs
    
    priority: int = 0

    @classmethod
    def name(cls) -> str:
        raise NotImplementedError("Il driver deve implementare 'name'.")

    @classmethod
    def pattern(cls) -> List[Union[str, re.Pattern]]:
        raise NotImplementedError("Il driver deve implementare 'pattern'.")
        

    def import_dataframe(
        self,
        path: str,
        filters: Optional[dict] = None,
        dtype: Optional[dict] = None
    ) -> Union[pd.DataFrame, gpd.GeoDataFrame, dict]:
        raise NotImplementedError("Il driver deve implementare 'import_dataframe'.")

    def export_dataframe(
        self,
        df: Union[pd.DataFrame, gpd.GeoDataFrame, dict],
        path: str,
        mode: str = "w",
        partitionby: Optional[List[str]] = None
    ):
        raise NotImplementedError("Il driver deve implementare 'export_dataframe'.")
    
    @staticmethod
    def adapt_dtype(df, dtype: Optional[dict] = None, copy=True) -> Union[pd.DataFrame, gpd.GeoDataFrame]:
        if dtype is None:
            return df
        try:
            if isinstance(dtype, dict):
                dtype = {k: v for k, v in dtype.items() if k in df.columns}
                #remove dtype definition if dtype is a datetime
                for col in df.columns:
                    if col not in dtype:
                        dtype[col] = 'string'
                    if pd.api.types.is_datetime64_any_dtype(df[col]) and col in dtype:
                        del dtype[col]
                    

                df=df.astype(dtype, copy=copy)            
            else:
                df = df.astype(dtype, copy=copy)
        except Exception as e:
            raise ValueError(f"Invalid dtype: {dtype}") from e
        return df
    
    @staticmethod
    def apply_filters(df, filters: Optional[Union[dict,str]] = None) -> Union[pd.DataFrame, gpd.GeoDataFrame]:
        if filters is not None:
            if isinstance(filters, str):
                query = filters.replace("==","=").replace("=","").replace("<>","!=")
            else:
                query = filters_to_query_expression(filters,quoting='', op_boolean_symbols=True)
            df = df.query(query)
        return df
    
    @staticmethod
    def write_partitioned(
        df: Union[pd.DataFrame,gpd.GeoDataFrame],
        file: Union[str,Path],
        partition_cols: Sequence[str],
        support_append=False,
        fn_save:Callable=None
        ):
        file = Path(file)
        grp = df.groupby(partition_cols)    
        for gname, grdf in grp:
            if not isinstance(gname, Tuple):
                gname = (gname,)
            partition_dirs = [''.join([str(y) for y in x]) for x in zip(partition_cols,["="*len(partition_cols)],gname)]
            part_folder = file / Path(*partition_dirs)
            part_folder.mkdir(exist_ok=True, parents=True)
            fname = part_folder / (file.stem + '_' + '_'.join(partition_dirs) + file.suffix)
            if not support_append:
                while (i:=0) is not None:
                    if not fname.exists():
                        break
                    fname = part_folder / f"{file.stem}_{i}{file.suffix}"
                    i+=1

            fn_save(grdf, fname)

    @staticmethod            
    def reduce_folder(
        path: str,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        Applica una funzione di riduzione a ogni partizione del DataFrame e restituisce i risultati.
        
        :param df: DataFrame o GeoDataFrame da partizionare.
        :param partitionby: Colonne su cui partizionare.
        :param func: Funzione di riduzione da applicare a ogni partizione.
        :param args: Argomenti posizionali per la funzione.
        :param kwargs: Argomenti keyword per la funzione.
        :return: Generatore con i risultati della riduzione.
        """       
        if os.path.exists(path):            
            path = Path(path)
            if path.is_file():
                return func(path, *args, **kwargs)
            else:
                files = list(path.glob("**/*"))
                files = [file for file in files if file.is_file() and file.suffix.lower() in os.path.splitext(path)[1].lower()]
                return pd.concat([func(file, *args, **kwargs) for file in files])
                
        else:
            raise FileNotFoundError(f"Il percorso '{path}' non esiste.")
   
    @staticmethod
    def is_geo(df: Union[pd.DataFrame, gpd.GeoDataFrame]) -> bool:
        if isinstance(df, gpd.GeoDataFrame):
            # Verifica che la colonna geometry esista e non sia None
            return df.geometry.name in df.columns and not df.geometry.isna().all()
        elif isinstance(df, pd.DataFrame):
            return any(col in df.columns for col in ['geometry', 'geom'])
        return False
    
    @staticmethod
    def to_geodataframe(df: Union[pd.DataFrame, gpd.GeoDataFrame], crs: Union[str, int] = "EPSG:4326", geometry_col=None, raise_error=False) -> Union[gpd.GeoDataFrame, pd.DataFrame]:
        
        if isinstance(df, gpd.GeoDataFrame):            
            geometry_col = BaseDriver.get_geometry_col(df=df, geometry_col=geometry_col, errors="raise")              
            if geometry_col in df.columns:
                return df.set_crs(crs, allow_override=True) if df.crs is None else df
        if isinstance(df, pd.DataFrame):
            geometry_col = BaseDriver.get_geometry_col(df=df, geometry_col=geometry_col, errors="warn")              
            if geometry_col in df.columns:
                sample = df[geometry_col].dropna().iloc[0]
                if isinstance(sample, (bytes, bytearray)):
                    geometries = from_wkb(df.pop(geometry_col), on_invalid='fix')
                elif isinstance(sample, str):
                    geometries = from_wkt(df.pop(geometry_col), on_invalid='fix')
                else:
                    geometries = df.pop(geometry_col)
                gdf = gpd.GeoDataFrame(df, geometry=geometries, crs=crs)
            else:
                gdf = gpd.GeoDataFrame(df)
                if crs:
                    if gdf.crs is None:
                        gdf.set_crs(crs, inplace=True)
                    else:
                        gdf.to_crs(crs, inplace=True)
        elif isinstance(df, dict):
            df = pd.DataFrame.from_dict(df)
            geometry_col = BaseDriver.get_geometry_col(df=df, geometry_col=geometry_col, errors="warn")
            if geometry_col is not None:
                geoemtries = df.pop(geometry_col)
                gdf = gpd.GeoDataFrame(df, geometry=geometries, crs=crs)
            else:            
                gdf = gpd.GeoDataFrame(df)
                if crs:
                    if gdf.crs is None:
                        gdf.set_crs(crs, inplace=True)
                    else:
                        gdf.to_crs(crs, inplace=True)
        else:
            warnings.warn("Data is not a dataframe or geodataframe")
            return None
        return gdf    

    @staticmethod
    def get_geometry_col(df: Union[pd.DataFrame, gpd.GeoDataFrame], geometry_col: str = None, errors='ignore'):
        original = geometry_col
        if df is not None:
            if geometry_col is None:
                if isinstance(df, gpd.GeoDataFrame):
                    if df.geometry is None or df.geometry.name:
                        geometry_col=df.geometry.name
                elif isinstance(df, pd.DataFrame):
                    for col in ['geometry', 'geom']:
                        if col in df.columns:
                            geometry_col = col
                            break  
        if errors.lower() == 'ignore':
            return geometry_col if geometry_col in df.columns else None
        if geometry_col is None or geometry_col not in df.columns:
            if errors.lower() == "warn":     
                warnings.warn("Geometry column not found")
            elif errors.lower() == "raise":
                raise KeyError("Geometry column not found")
        else:
            return geometry_col

    
    @staticmethod
    def to_dataframe(df: Union[pd.DataFrame, gpd.GeoDataFrame], geometry_col: str = "geometry", crs: str = None) -> pd.DataFrame:
        if isinstance(df, gpd.GeoDataFrame):
            geometry_col = BaseDriver.get_geometry_col(df=df, geometry_col=geometry_col, errors="raise")              
            if geometry_col in df.columns:
                if df.crs is not None:
                    df.to_crs(crs, inplace=True) if crs else None
                else:
                    df.set_crs(crs, inplace=True) if crs else None
                geometries_wkt = df[geometry_col].to_wkt()
                df = df.drop(columns=geometry_col)
                df[geometry_col] = geometries_wkt
                
        elif isinstance(df, dict):
            df = pd.DataFrame.from_dict(df)
        elif isinstance(df, pd.DataFrame):
            return df
        else:
            warnings.warn("Data is not a dataframe or geodataframe")
            return None
        return df
        

    def get_filename(path, 
                     partitionBy=None,
                     partition_values=None, 
                     mode="w",
                     template="{filename}-{i}") -> str:
        import shutil
        import tempfile
        from pathlib import Path
        from ... import remove_path
        from datetime import datetime
        from uuid import uuid4
        from os import getpid
        import glob

        filename = os.path.basename(path)
        extension = os.path.splitext(filename)[1]
        if partitionBy and partition_values:
            partitions_hive = [str(p) + "=" + str(v) for p,v in zip(partitionBy, partition_values)]
        else:
            partitions_hive = []
        if partitions_hive:
            path= os.path.join(path,*partitions_hive)

        d = datetime.now()
        date = d.strftime("%Y%m%d%H%M%S")
        timestamp = d.timestamp()
        uid = str(uuid4())
        pid = getpid()

        if not os.path.exists(path):
            file_name = template.format(
                filename=os.path.splitext(filename)[0],
                date = date, 
                uid=uid,pid=pid, 
                timestamp=timestamp,
                partition='-'.join((str(x) for x in partition_values)) if partition_values else "",
                partitions_hive='-'.join(partitions_hive) if partitions_hive else "",
                i="0",
            )            
            return os.path.join(path, file_name + extension)


        file_name = template.format(
            filename=os.path.splitext(filename)[0],
            date = date, 
            uid=uid,pid=pid, 
            timestamp=timestamp,
            partition='-'.join((str(x) for x in partition_values)) if partition_values else "",
            partitions_hive='-'.join(partitions_hive) if partitions_hive else "",
            i="*",
        )
        i = len(glob.glob(os.path.join(path,f"{file_name}{extension}")))
        file_name = file_name = template.format(
            filename=os.path.splitext(filename)[0],
            date = date, uid=uid,pid=pid, timestamp=timestamp,
            partition='-'.join((str(x) for x in partition_values)) if partition_values else "",
            partitions_hive='-'.join(partitions_hive) if partitions_hive else "",
            i=str(int(i) + 1),
        )
        new_file = os.path.join(path, file_name + extension)
        return new_file