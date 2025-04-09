from __future__ import annotations
import pickle
from typing import *
from numbers import Number
from . import Path, KPathContainer
import numpy as np


class KPathList(KPathContainer):

    def __init__(self, **kwargs):
        super().__init__()
        self.update(**kwargs)
        self["type"] = self.__class__.__name__
        self.setdefault("paths", {})
        self.setdefault("ull", {}) # Unique Link List

    def add_path(self, to_add: Path, k: Optional[int] = None, **kwargs):
        to_add["links"] = self["ull"].setdefault(to_add["links"], to_add["links"])
        key = to_add.key()
        l = self["paths"].setdefault(key, [])
        if k is None:
            l.append(to_add)
            to_add["k"] = len(l) - 1
        else:
            l.extend([None] * (k + 1 - len(l))) if len(l) < k + 1 else l
            l[k] = to_add
            to_add["k"] = k

    def get_sources(self, target: Optional[Hashable]=None, t_start: Optional[Number] = None, mode:Optional[str]=None, **kwargs) -> Tuple[Hashable]:
        return tuple(set([s for (s,t,ts,m) in map(lambda x: x.key(), self.all_paths()) if (t_start is None or ts==t_start) and (target is None or t==target) and (mode is None or m==mode)]))

    def get_targets(self, source: Optional[Hashable]=None, t_start: Optional[Number]=None, mode:Optional[str]=None, **kwargs) -> Optional[Tuple[Hashable]]:
        return tuple(set([t for (s,t,ts,m) in map(lambda x: x.key(), self.all_paths())  if (source is None or s==source) and (t_start is None or ts==t_start) and (mode is None or m==mode)]))
    
    def get_t_starts(self, source: Optional[Hashable] = None, target: Optional[Hashable]=None, mode:Optional[str]=None, **kwargs) -> Tuple[Number]:
        return tuple(set([ts for (s,t,ts,m) in map(lambda x: x.key(), self.all_paths())  if (source is None or s==source) and (target is None or t==target) and (mode is None or m==mode)]))
        
    def get_modes(self, source: Optional[Hashable]=None, target: Optional[Hashable]=None, t_start: Optional[Number] = None, **kwargs) -> Tuple[Hashable]:
        return tuple(set([m for (s,t,ts,m) in map(lambda x: x.key(), self.all_paths()) if (source is None or s==source) and (t_start is None or ts==t_start) and (target is None or t==target)]))

    def paths(self, source: Hashable, target: Hashable, t_start: Number, **kwargs) -> Generator[Path]:
        for path in self["paths"].get((source, target, t_start), []):
            yield path

    def path(self, 
             source: Hashable, 
             target: Hashable, 
             t_start: Optional[Number]=None, 
             mode: Optional[str]=None, 
             k: int =0, **kwargs) -> Path:
        paths = self["paths"].get((source, target, t_start, mode))
        if paths and len(paths) > k:
            return paths[k]
        else:
            return None

    def all_paths(self, **kwargs) -> Generator[Path]:
        for paths in self["paths"].values():
            for path in paths:
                yield path

    def all_kpaths(self, **kwargs) -> Generator[Tuple[Tuple[Hashable, Hashable, int], List[Path]]]:
        for (source, target, t_start, mode), paths in self["paths"].items():
            yield (source, target, t_start, mode), paths

    def n_paths(self, **kwargs) -> int:
        n = 0
        for paths in self["paths"].values():
            n += len(paths)
        return n
    
    def n_unique_paths(self, **kwargs) -> int:
        return len(self["ull"])
    
    def k_paths(self, **kwargs) -> int:
        k = 0
        for paths in self["paths"].values():
            k = max(k, len(paths))
        return k
    
    def is_empty(self) -> bool:
        return len(self["paths"]) == 0

