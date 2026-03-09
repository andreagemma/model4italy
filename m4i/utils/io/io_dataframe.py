import re
import importlib
import pkgutil
import warnings
from typing import Dict, List, Optional, Type, Union, Tuple
import pandas as pd
import geopandas as gpd
from .drivers import BaseDriver
from ..util import remove_path

class IO_DataFrame:

    remove_path = remove_path
    
    def __init__(self, **kwargs):
        self._patterns: Dict[re.Pattern, re.Pattern] = {}
        self._pattern_to_driver: Dict[re.Pattern, BaseDriver] = {}
        self._drivers: Dict[str, BaseDriver] = {}
        self._load_all_drivers(**kwargs)


    def register_driver(self, driver_cls: Type[BaseDriver], kwargs: Optional[dict] = None):
        pattern: Union[str,re.Pattern, List[Union[str, Tuple[str, dict],re.Pattern]]] = driver_cls.pattern()
        name: str = driver_cls.name()
        kwargs = kwargs or {}
        if name in kwargs:
            driver = driver_cls(**kwargs["name"])
        else:
            driver = driver_cls()
        self._drivers[name] = driver
        patterns = pattern if isinstance(pattern, list) else [pattern]
        for pat in patterns:
            if isinstance(pat, str):
                pat = re.compile(pat)
            if isinstance(pat, re.Pattern):
                if pat in self._pattern_to_driver:
                    warnings.warn(f"Il pattern '{pat}' è già registrato. Il driver precedente verrà sovrascritto.")
                self._pattern_to_driver[pat] = driver
                self._patterns[pat] = pat
            else:
                warnings.warn(f"Il pattern '{pat}' non è una stringa o un oggetto re.Pattern valido. Ignorato.")
                
    def _load_all_drivers(self, **kwargs):
        from . import drivers
        # estrae i pacakges dei driver
        modules = [modname for _, modname, ispkg in pkgutil.iter_modules(drivers.__path__) if not ispkg]        
        # li importa dinamicamente
        modules = [importlib.import_module(f".drivers.{modname}", package=__package__) for modname in modules]
        # estrae le classi dai moduli importati
        classes = [getattr(module, attr) for module in modules for attr in dir(module) if isinstance(getattr(module, attr), type)]
        # filtra le classi per quelle che sono sottoclassi di BaseDriver
        classes = [c for c in classes if issubclass(c, BaseDriver) and c is not BaseDriver]   
        # ordina le classi in base alla priorità     
        classes = sorted(classes, key=lambda x: x.priority, reverse=True)
        for cls in classes:
            self.register_driver(cls, **kwargs)

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
    ) -> Union[pd.DataFrame, gpd.GeoDataFrame, object]:

        if not driver:
            driver = self._detect_driver(path)
        else:            
            if isinstance(driver, str):
                driver = self._drivers.get(driver, None)
            elif isinstance(driver, BaseDriver):
                driver = driver
            else:
                raise ValueError(f"Il driver deve essere una stringa o un'istanza di BaseDriver, ma è di tipo {type(driver)}.")
            if driver is None:
                raise ValueError(f"Driver is None.")
            
        if not driver:
            raise ValueError(f"Driver non registrato per '{path}'.")
        if kwargs_driver is None:
            kwargs_driver = {}   
        if not isinstance(kwargs_driver, dict):
            raise ValueError(f"kwargs_driver deve essere un dizionario.")     
        kwargs_driver.update(kwargs)
        kwargs_driver.pop("path", None)
        kwargs_driver.pop("filters", None)
        kwargs_driver.pop("dtype", None)
        df = driver.import_dataframe(path, filters=filters, dtype=dtype, **kwargs_driver)
        if force_geodataframe is not None and isinstance(df, pd.DataFrame):
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
        else:            
            if isinstance(driver, str):
                driver = self._drivers.get(driver, None)
            elif isinstance(driver, BaseDriver):
                driver = driver
            else:
                raise ValueError(f"Il driver deve essere una stringa o un'istanza di BaseDriver, ma è di tipo {type(driver)}.")
            if driver is None:
                raise ValueError(f"Driver is None.")

        if not driver:
            raise ValueError(f"Driver non registrato per '{path}'.")
        if kwargs_driver is None:
            kwargs_driver = {}
        if not isinstance(kwargs_driver, dict):
            raise ValueError(f"kwargs_driver deve essere un dizionario.")
        kwargs_driver.update(kwargs)
        kwargs_driver.pop("path", None)
        kwargs_driver.pop("mode", None)
        kwargs_driver.pop("partitionby", None)
        kwargs_driver.pop("force_partitioning", None)
        driver.export_dataframe(df, path, mode=mode, partitionby=partitionby, **kwargs_driver)
