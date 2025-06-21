from __future__ import annotations
import dill
import logging
import os
from typing import *
from types import FunctionType
from numbers import Number
from .path_container import PathContainer
from .path import Path
import numpy as np


class PathList(PathContainer):

    def __init__(self, key: Callable=None,  **kwargs):
        super().__init__()
        self.update(**kwargs)
        dict.__setitem__(self,"class_name", self.__class__.__name__)
        dict.__setitem__(self,"key", key)
        dict.__setitem__(self,"paths", {})

    def add_path(self, to_add: Path, **kwargs):        
        self["paths"][to_add.key() if self["key"] is None else self["key"](to_add)] = to_add
	
    def get_sources(self, target: Optional[Hashable]=None, t_start: Optional[Number] = None, mode:Optional[str]=None, **kwargs) -> Tuple[Hashable]:
        return tuple(set([s for (s,t,ts,m) in self["paths"].keys() if (t_start is None or ts==t_start) and (target is None or t==target) and (mode is None or m==mode)]))

    def get_targets(self, source: Optional[Hashable]=None, t_start: Optional[Number]=None, mode:Optional[str]=None, **kwargs) -> Optional[Tuple[Hashable]]:
        return tuple(set([t for (s,t,ts,m) in self["paths"].keys() if (source is None or s==source) and (t_start is None or ts==t_start) and (mode is None or m==mode)]))
    
    def get_t_starts(self, source: Optional[Hashable] = None, target: Optional[Hashable]=None, mode:Optional[str]=None, **kwargs) -> Tuple[Number]:
        return tuple(set([ts for (s,t,ts,m) in self["paths"].keys() if (source is None or s==source) and (target is None or t==target) and (mode is None or m==mode)]))
        
    def get_modes(self, source: Optional[Hashable]=None, target: Optional[Hashable]=None, t_start: Optional[Number] = None, **kwargs) -> Tuple[Hashable]:
        return tuple(set([m for (s,t,ts,m) in self["paths"].keys() if (source is None or s==source) and (t_start is None or ts==t_start) and (target is None or t==target)]))

    def path(self, source: Hashable, 
             target: Hashable=None, 
             t_start: Optional[Number]=0, 
             mode: Optional[str]= None,
             **kwargs) -> Optional[Path]:
        return self["paths"].get((source,target,t_start,mode), None)
    
    def path_by_key(self, key: Hashable, **kwargs) -> Optional[Path]:
        return self["paths"].get(key, None)

    def all_paths(self, **kwargs) -> Generator[Path]:
        for path in self["paths"].values():
            yield path

    def n_paths(self, **kwargs) -> int:
        return len(self["paths"])
    
    def filter(self, filter: Callable[[Path], bool] = None, inplace=False, **kwargs) -> None:
        if inplace:
            if filter is None:
                self["paths"] = {}
            else:
                for key in list(self["paths"].keys()):
                    if not filter(self["paths"][key]):
                        del self["paths"][key]
            return self
        else:
            if filter is None:
                return PathList(self["key"])
            else:
                new_paths = PathList(key=self["key"])
                for key in list(self["paths"].keys()):
                    if filter(self["paths"][key]):
                        new_paths.add_path(self["paths"][key])
                return new_paths
        
    def delete(self, path: Path, raise_error = False, **kwargs) -> None:
        key = path.key() if self["key"] is None else self["key"](path)
        if key in self["paths"]:
            del self["paths"][key]
        else:
            if raise_error:
                raise KeyError(f"Path not found in PathList.")
            else:
                logging.warning(f"Path not found in PathList. Key: {key}.")
            
    def clear(self):
        self["paths"].clear()
    