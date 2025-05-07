from __future__ import annotations
from typing import *
from numbers import Number

from copy import deepcopy
import dill  # Importa dill per la serializzazione
import numpy as np
from ..abstract_graph import AbstractGraphElement, AbstractNode, AbstractLink, AbstractTurn, AbstractGraph


class StaticGraphElement(AbstractGraphElement):
    """Base class for graph elements."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        dict.__setitem__(self, "type", self.__class__.__name__)


    def get_value(self, name: str, default: Optional[Any] = None,**kwargs):
        return dict.get(self, name, default)

    def set_value(self, name: str, value: Any):
        dict.__setitem__(self, name, value)

    def reset_attribute(self, name: str, value: Any):
        dict.__setitem__(self, name, value)

    def save(self, filename: str):
        """
        Save the attribute to a file.

        :param filename: Filename to save the attribute
        """
        with open(filename, "wb") as f:
            dill.dump(self, f, dill.HIGHEST_PROTOCOL)

    @staticmethod
    def load(filename: str) -> StaticGraphElement:
        """
        Load an graph element from a file.

        :param filename: Filename to load the attribute from
        :return: GraphElement object
        """
        with open(filename, "rb") as f:
            ret = dill.load(f)
        return ret


class StaticNode(AbstractNode, StaticGraphElement):
    """Node element of a graph."""

    def __init__(
        self,
        idx: Hashable,
        **kwargs,
    ):
        StaticGraphElement.__init__(self, **kwargs)
        dict.__setitem__(self, "idx", idx)
        self["type"] = self.__class__.__name__

    @property
    def idx(self):
        return dict.__getitem__(self, "idx")
    


class StaticLink(AbstractLink, StaticGraphElement):
    """Link element of a graph."""

    def __init__(
        self,
        idx: Hashable,
        i: Hashable,
        j: Hashable,
        **kwargs,
    ):
        StaticGraphElement.__init__(self, **kwargs)
        dict.__setitem__(self, "idx", idx)
        dict.__setitem__(self, "i", i)
        dict.__setitem__(self, "j", j)

    @property
    def idx(self):
        return dict.__getitem__(self, "idx")
    
    @property
    def i(self):
        return dict.__getitem__(self, "i")
    
    @property
    def j(self):
        return dict.__getitem__(self, "j")
    
class StaticTurn(AbstractTurn, StaticGraphElement):
    """Turn element of a graph."""

    def __init__(
        self,
        idx: Hashable,
        in_link: Hashable,
        out_link: Hashable,
        **kwargs,
    ):
        StaticGraphElement.__init__(self, **kwargs)
        dict.__setitem__(self, "idx", idx)
        dict.__setitem__(self, "in_link", in_link)
        dict.__setitem__(self, "out_link", out_link)

    @property
    def idx(self):
        return dict.__getitem__(self, "idx")
    
    @property
    def in_link(self):
        return dict.__getitem__(self, "in_link")
    
    @property
    def out_link(self):
        return dict.__getitem__(self, "out_link")
    


class StaticGraph(AbstractGraph, dict):
    """Graph structure to manage nodes, links, and turns."""

    def __init__(
        self,
        **kwargs,
    ):
        super().__init__()
        self.update(**kwargs)

        dict.__setitem__(self, "links", {})
        dict.__setitem__(self, "nodes", {})
        dict.__setitem__(self, "turns", {})
        dict.__setitem__(self, "bws", {})
        dict.__setitem__(self, "fws", {})
        dict.__setitem__(self, "turns_fws", {})

    def copy(self) -> StaticGraph:
        return deepcopy(self)
    
    @property
    def n_links(self) -> int:
        return len(dict.__getitem__(self, "links"))

    @property
    def n_nodes(self) -> int:
        return len(dict.__getitem__(self, "nodes"))
    
    @property
    def n_turns(self) -> int:
        return len(dict.__getitem__(self, "turns"))
    
    def add_link(self, idx: Hashable, i: Hashable, j: Hashable, **kwargs) -> StaticLink:
        """
        Add a link to the graph.

        :param idx: Link identifier
        :param i: Start node identifier
        :param j: End node identifier
        :return: Link object
        """
        l = StaticLink(idx=idx, i=i, j=j, **kwargs)
        links = dict.__getitem__(self, "links")
        dict.__setitem__(links, idx, l)

        fws = dict.__getitem__(self,"fws")
        bws = dict.__getitem__(self,"bws")
        if l["j"] in bws:
            bws[l["j"]][l["i"]] = l
        else:
            bws[l["j"]] = {l["i"]: l}

        if l["i"] in fws:
            fws[l["i"]][l["j"]] = l
        else:
            fws[l["i"]] = {l["j"]: l}

    def add_node(self, idx: Hashable, **kwargs) -> StaticNode:
        """
        Add a node to the graph.

        :param idx: Node identifier
        :return: Node object
        """
        n = StaticNode(idx=idx, **kwargs)
        nodes = dict.__getitem__(self, "nodes")
        dict.__setitem__(nodes, idx, n)
        return n

    def add_turn(self, idx: Hashable, in_link: Hashable, out_link: Hashable, **kwargs) -> StaticTurn:
        """
        Add a turn to the graph.

        :param idx: Turn identifier
        :param in_link: Incoming link identifier
        :param out_link: Outgoing link identifier
        :return: Turn object
        """
        t = StaticTurn(idx=idx, in_link=in_link, out_link=out_link, **kwargs)

        turns = dict.__getitem__(self, "turns")
        dict.__setitem__(turns, idx, t)

        turns_fws:dict = dict.__getitem__(self,"turns_fws")
        for t in dict.__getitem__(self, "turns").values():
            in_link = dict.__getitem__(t,"in_link")
            out_link = dict.__getitem__(t,"out_link")
            if in_link in turns_fws:
                if out_link in turns_fws[in_link]:
                    turns_fws[in_link][out_link]=t
            else:
                turns_fws[in_link] = {out_link: t}

    def apply_links(self, fn: Callable = None):
        """
        Esegue una funzione su tutti gli archi
        :param fn: funzione da applicare altrimenti viene applicata quella associata all'arco
        """
        for link in self.get_all_links():
            fn(link)
    

    def get_all_links(self) -> Generator[StaticLink]:
        for l in self["links"].values():
            yield l

    def get_all_nodes(self) -> Generator[StaticNode]:
        for n in self["nodes"].values():
            yield n

    def get_all_turns(self) -> Generator[StaticTurn]:
        for t in self["turns"].values():
            yield t

    def get_link(self, idx: Hashable) -> Optional[StaticLink]:
        """
        Get a link by its identifier.

        :param idx: Link identifier
        :return: Link object or None
        """
        return dict.__getitem__(self,"links").get(idx)

    def get_node(self, idx: Hashable) -> Optional[StaticNode]:
        """
        Get a node by its identifier.

        :param idx: Node identifier
        :return: Node object or None
        """
        return dict.__getitem__(self,"nodes").get(idx)


    def get_fws(self, i: Hashable) -> Iterable[StaticLink]:
        """
        Get forward star links for a node.

        :param i: Node identifier
        :return: Iterable of links
        """
        return dict.__getitem__(self,"fws").get(i, {}).values()

    def get_bws(self, j: Hashable) -> Iterable[StaticLink]:
        """
        Get backward star links for a node.

        :param j: Node identifier
        :return: Iterable of links
        """
        return dict.__getitem__(self,"bws").get(j, {}).values()

    def get_turn(self, idx_or_in_link: Hashable, out_link: Optional[Hashable]=None) -> StaticTurn:
        """
        Get turns for given incoming and outgoing links.

        :param in_link: Incoming link identifier
        :param out_link: Outgoing link identifier
        :return: List of turns
        """
        if out_link is None:
            return dict.__getitem__(self,"turns").get(idx_or_in_link)
        else:
            return dict.__getitem__(self,"turns_fws").get(idx_or_in_link, {}).get(out_link)

    def save(self, filename: str):
        """
        Save the graph to a file.

        :param filename: Filename to save the graph
        """
        with open(filename, "wb") as f:
            dill.dump(self, f, dill.HIGHEST_PROTOCOL)

    @staticmethod
    def load(filename: str) -> StaticGraph:
        """
        Load a graph from a file.

        :param filename: Filename to load the graph from
        :return: Graph object
        """
        with open(filename, "rb") as f:
            d = dill.load(f)
        return d
