from __future__ import annotations
import copy
import dill
from typing import *
from numbers import Number
from .. import AbstractGraph
from .path import Path
import numpy as np
from abc import ABC, abstractmethod

class PathContainer(ABC, dict):

    def __init__(self, **kwargs):
        super().__init__()
        self.update(**kwargs)
        self["type"] = self.__class__.__name__

    def get_paths_by_t_start(self, t_start) -> Generator[Path,None,None]:
        for path in self.all_paths():
            if path["t_start"] == t_start:
                yield path

    def get_paths_by_t(self, t) -> Generator[Path,None,None]:
        for path in self.all_paths():
            if path["t"] == t:
                yield path

    def get_paths_by_filter(self, function) -> Generator[Path,None,None]:
        for path in filter(function, self.all_paths()):
            yield path

    def add_path(self, to_add: Path, **kwargs):
        raise NotImplementedError()

    def merge(self,to_add: Union[Path,PathContainer], **kwargs):
        if isinstance(to_add, Path):
            self.add_path(to_add, **kwargs)
        elif isinstance(to_add, PathContainer):
            for path in to_add.all_paths(**kwargs):
                self.add_path(path)
    	
    @abstractmethod
    def get_sources(self, target: Optional[Hashable]=None, t_start: Optional[Number] = None, mode:Optional[str]=None, **kwargs) -> Tuple[Hashable]:
        raise NotImplementedError()

    @abstractmethod
    def get_targets(self, source: Optional[Hashable]=None, t_start: Optional[Number]=None, mode:Optional[str]=None, **kwargs) -> Optional[Tuple[Hashable]]:
        raise NotImplementedError()
    
    @abstractmethod
    def get_t_starts(self, source: Optional[Hashable] = None, target: Optional[Hashable]=None, mode:Optional[str]=None, **kwargs) -> Tuple[Number]:
        raise NotImplementedError()
        
    @abstractmethod
    def get_modes(self, source: Optional[Hashable]=None, target: Optional[Hashable]=None, t_start: Optional[Number] = None, **kwargs) -> Tuple[Hashable]:
        raise NotImplementedError()

    @abstractmethod
    def path(self, source: Hashable, 
             target: Hashable=None, 
             t_start: Optional[Number]=0, 
             mode: Optional[str]= None,
             graph: Optional[AbstractGraph]=None,
             **kwargs) -> Optional[Path]:
        raise NotImplementedError()

    @abstractmethod
    def all_paths(self, **kwargs) -> Generator[Path]:
        raise NotImplementedError()

    def counts_tot_links(self,**kwargs) -> int:
        return sum([len(path.get_links()) for path in self.all_paths(**kwargs)])

    def counts_link(self, id_link: Hashable,**kwargs) -> int:
        return sum([int(path.has_link(id_link)) for path in self.all_paths(**kwargs)])

    def n_paths(self, **kwargs) -> int:
        return len(self.all_paths(**kwargs))

    def save(self, filename: str):
        with open(filename, "wb") as f:
            dill.dump(self, f, dill.HIGHEST_PROTOCOL)

    @staticmethod
    def load(filename: str) -> PathContainer:
        with open(filename, "rb") as f:
            d = dill.load(f)  
        return d
    