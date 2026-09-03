# -*- coding: utf-8 -*-
"""
Created on Thu Jun 24 19:11:39 2021

@author: andge
"""

from __future__ import annotations


import operator
import pandas as pd
import numpy as np
import geopandas as gpd
import shapely.ops
from typing import Union, Any
from collections import namedtuple, defaultdict
import json
from datetime import datetime
import ast
from importlib import import_module
from abc import ABC, abstractmethod

import warnings
from ..params_parser import ParamsParser
from ..utils.util import serialize
from ..utils.decorators import stat_results
from ..utils import util
from . import BaseWriter
from .. import IniClass
from ..log import Logger
from shapely import to_wkb, to_wkt, to_geojson
import copy


class Writer(ABC):
    def __init__(self, parser: ParamsParser):
        self.parser = parser
        self.execution_id = self.parser.get("execution_id")
        self.log = Logger.getLogger(
            self.__class__.__name__, execution_id=self.execution_id
        )
        self.ini: IniClass = self.parser.ini

    def _write_dataset(
        self,
        df: Union[pd.DataFrame, gpd.GeoDataFrame],
        parameters,
        mode=None,
        dtype=None,
        check_definition=None,
        **kwargs,
    ) -> bool:
        """
        Write a dataset based on the provided parameters and mode.
        Arguments:
            df (Union[pd.DataFrame, gpd.GeoDataFrame]): The dataset to be written.
            parameters (dict): A dictionary containing the dataset parameters.
            mode (str, optional): The mode in which the dataset should be written ('w' for write, 'a' for append). Default is None.
            dtype (dict, optional): A dictionary specifying the data types for the columns. Default is None.
            partition (str, optional): The partition name for the dataset. Default is None.
            **kwargs: Additional arguments for customization.
        """
        try:
            if df is None:
                self.log.warning(f"No dataset to write for {parameters}")
                return False

            if "connector" not in parameters or parameters["connector"] is None:
                raise ValueError("Missing 'connector' parameter")
            cls_name = parameters.get("connector")
            ClassWriter = Writer.get_cls_by_name(cls_name)
            writer: BaseWriter = ClassWriter()

            parameters = copy.deepcopy(parameters)
            if isinstance(df, (pd.DataFrame, gpd.GeoDataFrame, dict)):
                if additional_fields := parameters.get("additional_fields", None):
                    tmp = {}
                    if isinstance(additional_fields, list):
                        for field in additional_fields:
                            if isinstance(field, str):
                                tmp[field] = {"value": None}
                            elif isinstance(field, dict):
                                if "name" not in field:
                                    raise ValueError(
                                        f"Missing 'name' key in additional field definition: {field}"
                                    )
                                tmp[field["name"]] = field
                        additional_fields = tmp

                    if isinstance(additional_fields, dict):
                        for additional_field, p in additional_fields.items():
                            if not isinstance(p, dict):
                                p = {"value": p}
                            t = p.get("dtype", None)
                            v = p.get("value", None)
                            if v.startswith("expression:"):
                                s = df.eval(v.replace("expression:", ""))
                            elif isinstance(p, str) and p.startswith("lambda:"):
                                v = p.replace("lambda:", "")
                                s = df.apply(lambda x: eval(v), axis=1)
                            else:
                                s = v
                            df[additional_field] = s
                            if t is not None:
                                if isinstance(df, (pd.DataFrame, gpd.GeoDataFrame)):
                                    df[additional_field] = df[additional_field].astype(
                                        t
                                    )
                                elif isinstance(df, dict):
                                    df[additional_field] = (
                                        pd.Series([v]).astype(t).tolist()[0]
                                    )
                    else:
                        raise ValueError(
                            f"Invalid 'additional_fields' definition: {additional_fields}. Must be a list of field {{name: <name>[, value: <value>][, dtype: <dtype>]}} or a dict {{<name>: {{value: <value>, dtype: <dtype>}}}}."
                        )

                """
                for k, v in parameters.items():
                    if isinstance(v, (str, int, float)):
                        parameters[k] = self.parser.get_parametric_name(v)
                """
                if dtype is None and check_definition is not None:
                    dtype = self.parser.get_dtype(check_definition, None)
                if dtype is not None and isinstance(
                    df, (pd.DataFrame, gpd.GeoDataFrame)
                ):
                    df = self.parser.apply_dtype(
                        df=df,
                        dtype=dtype,
                        copy=False,
                        tz_src=self.ini.TZ_CALC,
                        tz_dest=parameters.get("tz_data", self.ini.TZ_LOCAL),
                    )

                mapping = parameters.get("mapping")

                if mapping is not None and isinstance(
                    df, (pd.DataFrame, gpd.GeoDataFrame)
                ):
                    df = self.parser.apply_mapping(df=df, mapping=mapping, writing=True)

                if isinstance(df, gpd.GeoDataFrame):
                    crs = parameters.get("crs", self.ini.CRS)
                    if crs is not None:
                        if df.crs is None:
                            df.set_crs(crs, inplace=True)
                        elif df.crs != crs:
                            df.to_crs(crs, inplace=True)

                partition_cols = parameters.get("partition_cols", None)

            if mode is None:
                m = parameters.get("mode", "w")
            else:
                m = parameters.get("mode", "w")
                if mode == "a" and m == "w":
                    m = "a"
                else:
                    m = mode
            if m not in ["a", "t", "w"]:
                raise ValueError(f"Invalid mode {mode} for dataset {parameters}")
            ret = writer.write_dataset(
                df,
                parameters=parameters,
                mode=m,
                partition_cols=partition_cols,
                **kwargs,
            )
            if ret == False:
                self.log.warning(f"Failed to write dataset for {parameters}")
                return False
            return True
        except Exception as e:
            self.log.error(f"Error writing dataset for {parameters}: {e}")
            raise e

    to_wkb = to_wkb
    to_wkt = to_wkt
    to_geojson = to_geojson

    @staticmethod
    def get_cls_by_name(class_name) -> BaseWriter:
        module = import_module("m4i.connectors")
        cls = getattr(module, class_name)
        return cls

    def has_write_agg_results(self):
        return self.parser.get("params.aggregated_results") is not None

    def has_write_agg_results_stats(self):
        return self.parser.get("params.aggregated_results_stats") is not None

    def has_write_trace_results(self):
        return self.parser.get("params.trace_results") is not None

    def has_write_signal_results(self):
        return self.parser.get("params.signal_results") is not None

    def has_write_paths(self):
        return self.parser.get("params.paths") is not None

    def has(self, name):
        return self.parser.get(name) is not None

    def write_agg_results(
        self, results: gpd.GeoDataFrame, mode=None, params=None, **kwargs
    ):
        kwargs["df"] = results
        kwargs["dtype"] = self.parser.get_dtype("aggregated_results")
        kwargs["parameters"] = self.parser.get_output_parameters(
            params if params is not None else "params.aggregated_results", df=results
        )
        kwargs["mode"] = mode
        kwargs["check_definition"] = "aggregated_results"
        return self._write_dataset(**kwargs)

    def write_agg_results_stats(
        self, results: gpd.GeoDataFrame, mode=None, params=None, **kwargs
    ):
        kwargs["df"] = results
        # kwargs["dtype"] = self.parser.get_dtype("aggregated_results_stats")
        kwargs["parameters"] = self.parser.get_output_parameters(
            params if params is not None else "params.aggregated_results_stats",
            df=results,
        )
        kwargs["mode"] = mode
        kwargs["check_definition"] = "aggregated_results_stats"
        return self._write_dataset(**kwargs)

    def write_trace_results(
        self, results: gpd.GeoDataFrame, mode=None, params=None, **kwargs
    ):
        kwargs["df"] = results
        # kwargs["dtype"] = self.parser.get_dtype("trace_results")
        kwargs["parameters"] = self.parser.get_output_parameters(
            params if params is not None else "params.trace_results", df=results
        )
        kwargs["mode"] = mode
        kwargs["check_definition"] = "trace_results"
        return self._write_dataset(**kwargs)

    def write_signal_results(
        self, results: gpd.GeoDataFrame, mode=None, params=None, **kwargs
    ):
        kwargs["df"] = results
        # kwargs["dtype"] = self.parser.get_dtype("signal_results")
        kwargs["parameters"] = self.parser.get_output_parameters(
            params if params is not None else "params.signal_results", df=results
        )
        kwargs["mode"] = mode
        kwargs["check_definition"] = "signal_results"
        return self._write_dataset(**kwargs)

    def write_paths(self, results: gpd.GeoDataFrame, mode=None, params=None, **kwargs):
        kwargs["df"] = results
        kwargs["dtype"] = self.parser.get_dtype("paths")
        params_ = params if params is not None else "params.paths"
        kwargs["parameters"] = self.parser.get_output_parameters(params_, df=results)
        kwargs["check_definition"] = "paths"
        kwargs["mode"] = mode
        """
        kwargs["partition"] = partition
        try:
            kwargs["partition_cols"] = [s.split("=")[0] for s in partition.split(",")] if partition is not None else None
        except Exception as e:
            kwargs["partition_cols"] = None
        """
        return self._write_dataset(**kwargs)

    def write(
        self,
        results: gpd.GeoDataFrame,
        path: str = None,
        parameters: dict = None,
        mode=None,
        from_input=False,
        check_definition=None,
        **kwargs,
    ):
        """
        Carica un dataset in base ai parametri forniti, ai filtri e al tipo di dato specificato.

        Argomenti:
            name (opzionale): Il nome del dataset da caricare. Se non fornito, verrà utilizzato il parametro 'parameters'.
            parameters (opzionale): Un dizionario contenente i parametri necessari per caricare il dataset.
            filters (opzionale): Criteri per filtrare il dataset. I filtri devono essere specificati in forma di lista di tuple, seguendo la sintassi:
                                          filters = [[('colonna', 'operatore', valore), ...], ...]
                                 * Operatori supportati: ==, =, !=, >, >=, <, <=, in, not in​
                                 * AND logico: le tuple all'interno di una lista interna sono combinate con un AND logico.​
                                 * OR logico: le liste interne sono combinate con un OR logico.
                                 es: filters = [('col1', '==', 10), ('col2', '>', 5)]
                                     corrisponde a col1 == 10 AND col2 > 5
                                 es: filters = [[('col1', '==', 10), ('col2', '>', 5)], [('col3', '<', 20)]]
                                     corrisponde a (col1 == 10 AND col2 > 5) OR (col3 < 20)
                                 es: filters = [[('col1', '==', 10), ('col2', '>', 5)], [('col3', '<', 20), ('col4', '!=', 30)]]
                                     corrisponde a (col1 == 10 AND col2 > 5) OR (col3 < 20 AND col4 != 30)
            dtype (opzionale): Il tipo di dato desiderato per il dataset caricato. Può essere utilizzato per specificare formati come pandas DataFrame o GeoDataFrame.
            **kwargs: Argomenti aggiuntivi per la personalizzazione o per casi d'uso specifici.

        Restituisce:
            Union[pd.DataFrame, gpd.GeoDataFrame]: Il dataset caricato, che può essere un pandas DataFrame o un GeoPandas GeoDataFrame, a seconda dell'esistenza di un campo geometrico.
        """
        if parameters is None:
            if path:
                parameters = self.parser.get_output_parameters(
                    path, df=results, from_input=from_input
                )
            else:
                raise KeyError("key 'parameters' not found in execution parameters")
        kwargs["df"] = results
        kwargs["parameters"] = parameters
        kwargs["mode"] = mode
        kwargs.setdefault("check_definition", check_definition)
        """
        if partition is not None:
            if isinstance(partition, str):
                kwargs["partition"] = partition
                try:
                    kwargs["partition_cols"] = [s.split("=")[0] for s in partition.split(",")] if partition is not None else None
                except Exception as e:
                    kwargs["partition_cols"] = None
            elif isinstance(partition, list):
                kwargs["partition"] = ",".join(partition)
                try:
                    kwargs["partition_cols"] = [s.split("=")[0] for s in partition] if partition is not None else None
                except Exception as e:
                    kwargs["partition_cols"] = None
        """
        return self._write_dataset(**kwargs)
