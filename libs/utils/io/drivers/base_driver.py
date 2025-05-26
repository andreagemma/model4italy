import re
from typing import Dict, List, Optional, Type, Union, Tuple
import pandas as pd
import geopandas as gpd

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

    @property
    def name(self) -> str:
        raise NotImplementedError("Il driver deve implementare 'name'.")

    @property
    def pattern(self) -> Union[str, List[Union[str, Tuple[str, dict]]]]:
        raise NotImplementedError("Il driver deve implementare 'pattern'.")

    def import_dataframe(
        self,
        path: str,
        filters: Optional[dict] = None,
        dtype: Optional[dict] = None
    ) -> Union[pd.DataFrame, gpd.GeoDataFrame]:
        raise NotImplementedError("Il driver deve implementare 'import_dataframe'.")

    def export_dataframe(
        self,
        df: Union[pd.DataFrame, gpd.GeoDataFrame],
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