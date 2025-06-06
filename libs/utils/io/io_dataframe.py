import re
import importlib
import pkgutil
import warnings
from typing import Dict, List, Optional, Type, Union, Tuple
import pandas as pd
import geopandas as gpd
from .drivers import BaseDriver

class IO_DataFrame:
    def __init__(self):
        self._patterns: Dict[str, re.Pattern] = {}
        self._pattern_to_driver: Dict[str, BaseDriver] = {}
        self._load_all_drivers()

    def register_driver(self, driver_cls: Type[BaseDriver], pattern: Union[str, List[Union[str, Tuple[str, dict]]]], kwargs: Optional[dict] = None):
        kwargs = kwargs or {}
        driver = driver_cls(**kwargs)

        patterns = pattern if isinstance(pattern, list) else [pattern]
        for pat in patterns:
            if isinstance(pat, re.Pattern):
                if pat in self._pattern_to_driver:
                    warnings.warn(f"Il pattern '{pat}' è già registrato. Il driver precedente verrà sovrascritto.")
                self._pattern_to_driver[pat] = driver
                self._patterns[pat] = pat
            elif isinstance(pat, tuple):
                regex, pat_kwargs = pat
                self.register_driver(driver_cls, regex, {**kwargs, **pat_kwargs})
            else:
                compiled = re.compile(pat)
                if pat in self._pattern_to_driver:
                    warnings.warn(f"Il pattern '{pat}' è già registrato. Il driver precedente verrà sovrascritto.")
                self._pattern_to_driver[pat] = driver
                self._patterns[pat] = compiled

    def _load_all_drivers(self):
        from . import drivers
        for _, modname, ispkg in pkgutil.iter_modules(drivers.__path__):
            if not ispkg:
                module = importlib.import_module(f".drivers.{modname}", package=__package__)
                for attr in dir(module):
                    obj = getattr(module, attr)
                    if isinstance(obj, type) and issubclass(obj, BaseDriver) and obj is not BaseDriver:
                        pattern = obj().pattern
                        self.register_driver(obj, pattern)

    def _detect_driver(self, path: str) -> BaseDriver:
        path = path.lower()
        for pat, regex in self._patterns.items():
            if regex.search(path):
                return self._pattern_to_driver[pat]
        raise ValueError(f"Nessun driver corrispondente al file '{path}'.")

    def import_dataframe(
        self,
        path: str,
        driver: Optional[str] = None,
        filters: Optional[Union[dict,str]] = None,
        dtype: Optional[dict] = None,
        kwargs_driver: Optional[dict] = None,
        force_geodataframe: Optional[bool] = None,
        **kwargs
    ) -> Union[pd.DataFrame, gpd.GeoDataFrame]:

        if not driver:
            driver = self._detect_driver(path)

        if not driver:
            raise ValueError(f"Driver non registrato per '{path}'.")
        if kwargs_driver is None:
            kwargs_driver = {}   
        if not isinstance(kwargs_driver, dict):
            raise ValueError(f"kwargs_driver deve essere un dizionario.")     
        kwargs_driver.update(kwargs)
        kwargs.pop("path", None)
        kwargs.pop("filters", None)
        kwargs.pop("dtype", None)
        df = driver.import_dataframe(path, filters=filters, dtype=dtype, **kwargs)
        if force_geodataframe is not None:
            if force_geodataframe and not isinstance(df, gpd.GeoDataFrame):
                df = gpd.GeoDataFrame(df)
            elif not force_geodataframe and isinstance(df, gpd.GeoDataFrame):
                df = pd.DataFrame(df)
        return df

    def export_dataframe(
        self,
        df: Union[pd.DataFrame, gpd.GeoDataFrame],
        path: str,
        driver: str=None,
        mode: str = "w",
        partitionby: Optional[List[str]] = None,
        kwargs_driver: Optional[dict] = None,
        **kwargs
    ):
        if not driver:
            driver = self._detect_driver(path)

        if not driver:
            raise ValueError(f"Driver non registrato per '{path}'.")
        if kwargs_driver is None:
            kwargs_driver = {}
        if not isinstance(kwargs_driver, dict):
            raise ValueError(f"kwargs_driver deve essere un dizionario.")
        kwargs.pop("path", None)
        kwargs.pop("mode", None)
        kwargs.pop("partitionby", None)
        kwargs_driver.update(kwargs)
        driver.export_dataframe(df, path, mode=mode, partitionby=partitionby, **kwargs_driver)
