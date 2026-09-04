from __future__ import annotations
from typing import *
from numbers import Number

from copy import deepcopy
import dill  # Importa dill per la serializzazione
import numpy as np
from ..abstract_graph import (
    AbstractGraphElement,
    AbstractNode,
    AbstractLink,
    AbstractTurn,
    AbstractGraph,
)

from .attribute import (
    DynamicTimeArrayAttribute,
    DynamicCallableAttribute,
    DynamicValueAttribute,
    DynamicAttribute,
)


class DynamicGraphElement(AbstractGraphElement):
    """Base class for graph elements."""

    def __init__(self, total_time: Number, delta_t: Number, **kwargs):
        super().__init__()
        dict.__setitem__(self, "type", self.__class__.__name__)
        for key, value in kwargs.items():
            self.add_attribute(key=key, value=value, total_time=total_time, delta_t=delta_t)

    def add_attribute(
        self,
        key: str,
        value: Any,
        total_time: Optional[Number] = None,
        delta_t: Optional[Number] = None,
    ):
        if isinstance(value, DynamicAttribute):
            attr = value
            attr.resize_attribute(new_total_time=value["total_time"], new_delta_t=value["delta_t"])
        elif isinstance(value, (list, tuple)) and not isinstance(value, str):
            assert total_time is not None and delta_t is not None, "total_time and delta_t required for iterable value"
            attr = DynamicTimeArrayAttribute(value, total_time=total_time, delta_t=delta_t)
            attr.resize_attribute(new_total_time=total_time, new_delta_t=delta_t)
        elif callable(value):
            assert total_time is not None and delta_t is not None, "total_time and delta_t required for callable value"
            attr = DynamicCallableAttribute(value, total_time=total_time, delta_t=delta_t)
            attr.resize_attribute(new_total_time=total_time, new_delta_t=delta_t)
        elif isinstance(value, str) and value.startswith("function.") and ":" in value:
            assert total_time is not None and delta_t is not None, "total_time and delta_t required for callable value"
            attr = DynamicCallableAttribute(value, total_time=total_time, delta_t=delta_t)
            attr.resize_attribute(new_total_time=total_time, new_delta_t=delta_t)
        else:
            attr = value

        dict.__setitem__(self, key, attr)

    def reset_attribute(self, name: str, value: Any):
        attr = dict.get(self, name)
        if isinstance(attr, DynamicAttribute):
            attr.reset(value)
        elif name is not None:
            dict.__setitem__(self, name, value)

    def get_value(self, name: str, default: Optional[Any] = None, **kwargs) -> Any:
        value = dict.get(self, name, default)
        if isinstance(value, DynamicAttribute):
            kwargs["elem"] = self
            return value.get_value(**kwargs)
        else:
            return value

    def get_values(self, name: str, list_t: Optional[Iterable[Number]] = None, **kwargs) -> List[Any]:
        value = dict.get(self, name)
        if isinstance(value, DynamicAttribute):
            kwargs["elem"] = self
            return value.get_values(list_t=list_t, **kwargs)
        else:
            return [value]

    def get_times(self, name: str, **kwargs) -> List[Number]:
        value = dict.get(self, name)
        if isinstance(value, DynamicAttribute):
            kwargs["elem"] = self
            return value.get_times(**kwargs)
        else:
            return []

    def get_items(self, name: str, list_t: Optional[Iterable[Number]] = None, **kwargs) -> List[Tuple[Number, Any]]:
        value = dict.get(self, name)
        if isinstance(value, DynamicAttribute):
            kwargs["elem"] = self
            return value.get_items(list_t=list_t, **kwargs)
        else:
            return [None, value]

    def set_value(self, name: str, value: Any, **kwargs) -> None:
        current_value = dict.get(self, name)
        if isinstance(current_value, DynamicAttribute):
            current_value.set_value(value, **kwargs)
        else:
            self[name] = value

    def save(self, filename: str):
        """
        Save the attribute to a file.

        :param filename: Filename to save the attribute
        """
        with open(filename, "wb") as f:
            dill.dump(self, f, dill.HIGHEST_PROTOCOL)

    @staticmethod
    def load(filename: str) -> DynamicGraphElement:
        """
        Load an graph element from a file.

        :param filename: Filename to load the attribute from
        :return: GraphElement object
        """
        with open(filename, "rb") as f:
            ret = dill.load(f)
        return ret


class DynamicNode(AbstractNode, DynamicGraphElement):
    """Node element of a graph."""

    def __init__(
        self,
        idx: Hashable,
        total_time: Optional[Number] = None,
        delta_t: Optional[Number] = None,
        **kwargs,
    ):
        DynamicGraphElement.__init__(self, total_time=total_time, delta_t=delta_t, **kwargs)
        dict.__setitem__(self, "idx", idx)
        self["type"] = self.__class__.__name__

    @property
    def idx(self):
        return dict.__getitem__(self, "idx")


class DynamicLink(AbstractLink, DynamicGraphElement):
    """Link element of a graph."""

    def __init__(
        self,
        idx: Hashable,
        i: Hashable,
        j: Hashable,
        total_time: Optional[Number] = None,
        delta_t: Optional[Number] = None,
        **kwargs,
    ):
        DynamicGraphElement.__init__(self, total_time=total_time, delta_t=delta_t, **kwargs)
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


class DynamicTurn(AbstractTurn, DynamicGraphElement):
    """Turn element of a graph."""

    def __init__(
        self,
        idx: Hashable,
        in_link: Hashable,
        out_link: Hashable,
        total_time: Optional[Number] = None,
        delta_t: Optional[Number] = None,
        **kwargs,
    ):
        DynamicGraphElement.__init__(self, total_time=total_time, delta_t=delta_t, **kwargs)
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


class DynamicGraph(AbstractGraph, dict):
    """Graph structure to manage nodes, links, and turns."""

    def __init__(
        self,
        total_time: Optional[Number] = 60,
        delta_t: Optional[Number] = 15,
        **kwargs,
    ):
        super().__init__()
        self.update(**kwargs)
        dict.__setitem__(self, "total_time", total_time)
        dict.__setitem__(self, "delta_t", delta_t)

        dict.__setitem__(self, "links", {})
        dict.__setitem__(self, "nodes", {})
        dict.__setitem__(self, "turns", {})
        dict.__setitem__(self, "bws", {})
        dict.__setitem__(self, "fws", {})
        dict.__setitem__(self, "turns_fws", {})
        dict.__setitem__(self, "num_intervals", total_time // delta_t)

    def copy(self) -> DynamicGraph:
        return deepcopy(self)

    @property
    def delta_t(self) -> Number:
        return dict.__getitem__(self, "delta_t")

    @property
    def total_time(self):
        return dict.__getitem__(self, "total_time")

    @property
    def n_links(self) -> int:
        return len(dict.__getitem__(self, "links"))

    @property
    def n_nodes(self) -> int:
        return len(dict.__getitem__(self, "nodes"))

    @property
    def n_turns(self) -> int:
        return len(dict.__getitem__(self, "turns"))

    def add_link(self, idx: Hashable, i: Hashable, j: Hashable, **kwargs) -> DynamicLink:
        """
        Add a link to the graph.

        :param idx: Link identifier
        :param i: Start node identifier
        :param j: End node identifier
        :return: Link object
        """
        kwargs["delta_t"] = dict.__getitem__(self, "delta_t")
        kwargs["total_time"] = dict.__getitem__(self, "total_time")
        l = DynamicLink(idx=idx, i=i, j=j, **kwargs)
        links = dict.__getitem__(self, "links")
        dict.__setitem__(links, idx, l)

        fws = dict.__getitem__(self, "fws")
        bws = dict.__getitem__(self, "bws")
        if l["j"] in bws:
            bws[l["j"]][l["i"]] = l
        else:
            bws[l["j"]] = {l["i"]: l}

        if l["i"] in fws:
            fws[l["i"]][l["j"]] = l
        else:
            fws[l["i"]] = {l["j"]: l}

    def add_node(self, idx: Hashable, **kwargs) -> DynamicNode:
        """
        Add a node to the graph.

        :param idx: Node identifier
        :return: Node object
        """
        kwargs["delta_t"] = dict.__getitem__(self, "delta_t")
        kwargs["total_time"] = dict.__getitem__(self, "total_time")
        n = DynamicNode(idx=idx, **kwargs)
        nodes = dict.__getitem__(self, "nodes")
        dict.__setitem__(nodes, idx, n)
        return n

    def add_turn(self, idx: Hashable, in_link: Hashable, out_link: Hashable, **kwargs) -> DynamicTurn:
        """
        Add a turn to the graph.

        :param idx: Turn identifier
        :param in_link: Incoming link identifier
        :param out_link: Outgoing link identifier
        :return: Turn object
        """
        kwargs["delta_t"] = dict.__getitem__(self, "delta_t")
        kwargs["total_time"] = dict.__getitem__(self, "total_time")

        t = DynamicTurn(idx=idx, in_link=in_link, out_link=out_link, **kwargs)

        turns = dict.__getitem__(self, "turns")
        dict.__setitem__(turns, idx, t)

        turns_fws: dict = dict.__getitem__(self, "turns_fws")
        for t in dict.__getitem__(self, "turns").values():
            in_link = dict.__getitem__(t, "in_link")
            out_link = dict.__getitem__(t, "out_link")
            if in_link in turns_fws:
                if out_link in turns_fws[in_link]:
                    turns_fws[in_link][out_link] = t
            else:
                turns_fws[in_link] = {out_link: t}

    """
    def compile(self):
        fws = self["fws"]
        bws = self["bws"]
        fws.clear()
        bws.clear()
        for l in self["links"].values():
            if l["j"] in bws:
                bws[l["j"]][l["i"]] = l
            else:
                bws[l["j"]] = {l["i"]: l}

            if l["i"] in fws:
                fws[l["i"]][l["j"]] = l
            else:
                fws[l["i"]] = {l["j"]: l}
            
        turns_fws:dict = dict.__getitem__(self,"turns_fws")
        turns_fws.clear()
        for t in dict.__getitem__(self, "turns").values():
            in_link = dict.__getitem__(t,"in_link")
            out_link = dict.__getitem__(t,"out_link")
            if in_link in turns_fws:
                if out_link in turns_fws[in_link]:
                    turns_fws[in_link][out_link]=t
            else:
                turns_fws[in_link] = {out_link: t}
    """

    def apply_links(self, fn: Callable = None):
        """
        Esegue una funzione su tutti gli archi
        :param fn: funzione da applicare altrimenti viene applicata quella associata all'arco
        """
        for link in self.get_all_links():
            fn(link)

    def resize_attributes(
        self,
        new_total_time: Optional[Number] = None,
        new_delta_t: Optional[Number] = None,
        offset=0,
    ) -> DynamicGraph:
        """
        Resize all time-dependent attributes.

        :param new_total_time: New total time
        :param new_delta_t: New delta time
        """
        new_total_time = new_total_time or dict.__getitem__(self, "total_time")
        new_delta_t = new_delta_t or dict.__getitem__(self, "delta_t")
        for link in self["links"].values():
            for attribute in link.values():
                if isinstance(attribute, DynamicAttribute):
                    (attribute.resize_attribute(new_total_time, new_delta_t, offset),)
        for node in self["nodes"].values():
            for attribute in node.values():
                if isinstance(attribute, DynamicAttribute):
                    attribute.resize_attribute(new_total_time, new_delta_t, offset)
        for turn in self["turns"].values():
            for attribute in turn.values():
                if isinstance(attribute, DynamicAttribute):
                    attribute.resize_attribute(new_total_time, new_delta_t, offset)
        dict.__setitem__(self, "total_time", new_total_time)
        dict.__setitem__(self, "delta_t", new_delta_t)
        dict.__setitem__(self, "num_intervals", new_total_time // new_delta_t)
        return self

    def get_all_links(self) -> Generator[DynamicLink]:
        for l in self["links"].values():
            yield l

    def get_all_nodes(self) -> Generator[DynamicNode]:
        for n in self["nodes"].values():
            yield n

    def get_all_turns(self) -> Generator[DynamicTurn]:
        for t in self["turns"].values():
            yield t

    def get_link(self, idx: Hashable) -> Optional[DynamicLink]:
        """
        Get a link by its identifier.

        :param idx: Link identifier
        :return: Link object or None
        """
        return dict.__getitem__(self, "links").get(idx)

    def get_node(self, idx: Hashable) -> Optional[DynamicNode]:
        """
        Get a node by its identifier.

        :param idx: Node identifier
        :return: Node object or None
        """
        return dict.__getitem__(self, "nodes").get(idx)

    def get_fws(self, i: Hashable) -> Iterable[DynamicLink]:
        """
        Get forward star links for a node.

        :param i: Node identifier
        :return: Iterable of links
        """
        return dict.__getitem__(self, "fws").get(i, {}).values()

    def get_bws(self, j: Hashable) -> Iterable[DynamicLink]:
        """
        Get backward star links for a node.

        :param j: Node identifier
        :return: Iterable of links
        """
        return dict.__getitem__(self, "bws").get(j, {}).values()

    def get_turn(self, idx_or_in_link: Hashable, out_link: Optional[Hashable] = None) -> DynamicTurn:
        """
        Get turns for given incoming and outgoing links.

        :param in_link: Incoming link identifier
        :param out_link: Outgoing link identifier
        :return: List of turns
        """
        if out_link is None:
            return dict.__getitem__(self, "turns").get(idx_or_in_link)
        else:
            return dict.__getitem__(self, "turns_fws").get(idx_or_in_link, {}).get(out_link)

    def save(self, filename: str):
        """
        Save the graph to a file.

        :param filename: Filename to save the graph
        """
        with open(filename, "wb") as f:
            dill.dump(self, f, dill.HIGHEST_PROTOCOL)

    @staticmethod
    def load(filename: str) -> DynamicGraph:
        """
        Load a graph from a file.

        :param filename: Filename to load the graph from
        :return: Graph object
        """
        with open(filename, "rb") as f:
            d = dill.load(f)
        return d
