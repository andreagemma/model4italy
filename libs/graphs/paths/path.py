from __future__ import annotations
from typing import Hashable, List, Optional, Tuple, Generator
from numbers import Number
from copy import deepcopy
import dill


class Path(dict):

    def __init__(
        self, source: Hashable, target: Hashable, t_start: Number, links: Optional[List[Hashable]] = None, tot_cost: Number = 0.0, mode: Optional[str]=None, t_base: Number=0, **kwargs
    ):
        super().__init__()
        self.update(**kwargs)
        dict.__setitem__(self, "source", source)
        dict.__setitem__(self, "target", target)
        dict.__setitem__(self, "t_start", t_start)
        dict.__setitem__(self, "t_base", t_base)
        dict.__setitem__(self, "t", t_base+t_start)
        dict.__setitem__(self, "mode", mode)
        dict.__setitem__(self, "tot_cost", tot_cost)
        dict.__setitem__(self, "links", tuple() if links is None else tuple(links))

    def key(self):
        return (dict.__getitem__(self,"source"),dict.__getitem__(self,"target"),dict.__getitem__(self,"t_start"),dict.__getitem__(self,"mode"))
    
    def copy(self):
        return deepcopy(self)

    def get_links(self) -> Tuple[Hashable]:
        return dict.get(self, "links", tuple())

    def get_costs(self, G, 
                  update_links: bool=True, update_nodes: bool=True, update_turns: bool=True, 
                  links_cost:str="time", nodes_cost:str="time", turns_cost:str="time") -> Generator[Number,None,None]:
        if len(self["links"]) == 0:
            return None
        cost = 0
        yield cost
        prev_l = None
        for i, l_idx in enumerate(self.get_links()):
            t = self["t"] + cost
            l = G.get_link(l_idx)
            if update_turns and i > 0:
                turn = G.get_turn(prev_l["idx"], l["idx"])
                if turn:
                    cost += turn.get_value(turns_cost, t=t, graph=G, default=0)
            if update_nodes:
                cost += G.get_node(l["i"]).get_value(name=nodes_cost, t=t, in_link=prev_l, out_link=l, graph=G, default=0)
            if update_links:
                cost += l.get_value(name=links_cost, t=t, in_link=prev_l, graph=G, default=0)
            yield cost
            prev_l = l

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