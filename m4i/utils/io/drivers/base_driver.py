import re
import typing
import pandas as pd
import geopandas as gpd
from typing import Dict, List, Optional, Union, Tuple, Generator, Any, Callable
from functools import reduce
import glob
from pathlib import Path
import os
from shapely import wkt
import shapely.wkb
from shapely.wkt import dumps as wkt_dumps
import polars as pl

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
        if dtype is not None:
            dtype = {k: v for k, v in dtype.items() if k in df.columns}
            df = df.astype(dtype, copy=copy)
        return df
    
    @staticmethod
    def apply_filters(df, filters: Optional[Union[dict,str]] = None) -> Union[pd.DataFrame, gpd.GeoDataFrame]:
        if filters is not None:
            if isinstance(filters, str):
                query = filters
            else:
                query = filters_to_query_expression(filters)
            df = df.query(query)
        return df
    
    @staticmethod
    def map_partitioned_dataframe(
        df: Union[pd.DataFrame, gpd.GeoDataFrame],
        partitionby: List[str],
        func,
        *args,
        **kwargs
    ) -> Generator[Any, None, None]:
        """
        Applica una funzione a ogni partizione del DataFrame.
        
        :param df: DataFrame o GeoDataFrame da partizionare.
        :param partitionby: Colonne su cui partizionare.
        :param func: Funzione da applicare a ogni partizione.
        :param args: Argomenti posizionali per la funzione.
        :param kwargs: Argomenti keyword per la funzione.
        :return: DataFrame o GeoDataFrame con le partizioni elaborate.
        """
        grp = df.groupby(partitionby)
        for name, group in grp:
            func((name, partitionby, group), *args, **kwargs)

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
    def to_geodataframe(df: Union[pd.DataFrame, gpd.GeoDataFrame], crs: Union[str, int] = "EPSG:4326") -> gpd.GeoDataFrame:
        if isinstance(df, gpd.GeoDataFrame):
            if df.geometry.name in df.columns:
                return df.set_crs(crs, allow_override=True) if df.crs is None else df

        geometry_column = None
        for col in ['geometry', 'geom']:
            if col in df.columns:
                geometry_column = col
                break

        if geometry_column is None:
            raise ValueError("DataFrame non contiene una colonna 'geometry' o 'geom'.")

        # Determina il tipo di geometria e converte se necessario
        sample = df[geometry_column].dropna().iloc[0]
        if isinstance(sample, (bytes, bytearray)):
            geometries = df[geometry_column].apply(lambda x: shapely.wkb.loads(x) if pd.notnull(x) else None)
        elif isinstance(sample, str):
            geometries = df[geometry_column].apply(lambda x: wkt.loads(x) if pd.notnull(x) else None)
        else:
            geometries = df[geometry_column]

        gdf = gpd.GeoDataFrame(df.copy(), geometry=geometries)
        if crs is not None:
            if gdf.crs is None:
                gdf.set_crs(crs, inplace=True)
            else:
                gdf.to_crs(crs, inplace=True)
        

        return gdf    
    
    @staticmethod
    def to_dataframe(df: Union[pd.DataFrame, gpd.GeoDataFrame]) -> pd.DataFrame:
        """
        Converte un GeoDataFrame o DataFrame in DataFrame.
        Se esiste una colonna geometrica, viene convertita in WKT.
        """
        if isinstance(df, gpd.GeoDataFrame):
            df = df.copy()
            if df.geometry.name in df.columns:
                df[df.geometry.name] = df.geometry.apply(lambda geom: wkt_dumps(geom) if geom is not None else None)
            return pd.DataFrame(df)
        elif isinstance(df, pd.DataFrame):
            return df
        else:
            raise TypeError("Input non valido: atteso pd.DataFrame o gpd.GeoDataFrame")