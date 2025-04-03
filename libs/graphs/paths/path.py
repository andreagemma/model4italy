from __future__ import annotations
from typing import Hashable, List, Optional, Tuple
from numbers import Number
from copy import deepcopy
import dill


class Path(dict):

    def __init__(
        self, source: Hashable, target: Hashable, t_start: Number, links: Optional[List[Hashable]] = None, costs: Optional[List[Number]] = None, tot_cost: Number = 0.0, mode: Optional[str]=None, t_base: Number=0, **kwargs
    ):
        super().__init__()
        self.update(**kwargs)
        dict.__setitem__(self, "source", source)
        dict.__setitem__(self, "target", target)
        dict.__setitem__(self, "t_start", t_start)
        dict.__setitem__(self, "t_base", t_base)
        dict.__setitem__(self, "t", t_base+t_start)
        dict.__setitem__(self, "mode", mode)
        dict.__setitem__(self, "tot_cost", tot_cost if costs is None or len(costs) == 0 else costs[-1])
        dict.__setitem__(self, "links", tuple() if links is None else tuple(links))
        dict.__setitem__(self, "costs", tuple() if costs is None else tuple(costs))

    def key(self):
        return (dict.__getitem__(self,"source"),dict.__getitem__(self,"target"),dict.__getitem__(self,"t_start"),dict.__getitem__(self,"mode"))
    
    def copy(self):
        return deepcopy(self)

    def get_links(self) -> Tuple[Hashable]:
        return dict.get(self, "links", tuple())

    def get_costs(self) -> Tuple[Hashable]:
        return dict.get(self, "costs", tuple())

    def has_link(self, id_link: Hashable) -> bool:
        return id_link in dict.get(self, "links", tuple())

    def counts_link(self, id_link: Hashable) -> int:
        return dict.get(self, "links", tuple()).count(id_link)

    def save(self, filename: str):
        with open(filename, "wb") as f:
            dill.dump(self, f, dill.HIGHEST_PROTOCOL)

    @staticmethod
    def load(filename: str) -> Path:
        with open(filename, "rb") as f:
            d = dill.load(f)            
        return d