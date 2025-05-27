from __future__ import annotations
from abc import ABC, abstractmethod
from typing import *
from numbers import Number
import dill
from copy import deepcopy
from types import MappingProxyType


class AbstractGraphElement(ABC, dict):
    """
    Abstract base class for graph elements.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        dict.__setitem__(self, "type", self.__class__.__name__)


    @property
    def type(self):
        return dict.__getitem__(self, "type")
    
    
    @abstractmethod
    def get_value(self, name: str, default: Optional[Any] = None, **kwargs) -> Any:
        """
        Get the value of an attribute at a specific time.
        """
        pass

    @abstractmethod
    def set_value(self, name: str, value: Any, **kwargs) -> None:
        """
        Set the value of an attribute at a specific time.
        """
        pass

    def save(self, filename: str):
        """
        Save the attribute to a file.

        :param filename: Filename to save the attribute
        """
        with open(filename, "wb") as f:
            dill.dump(self, f, dill.HIGHEST_PROTOCOL)

    @staticmethod
    def load(filename: str) -> AbstractGraphElement:
        """
        Load a graph element from a file.

        :param filename: Filename to load the attribute from
        :return: AbstractGraphElement object
        """
        with open(filename, "rb") as f:
            return dill.load(f)

    def copy(self) -> AbstractGraphElement:
        return deepcopy(self)


class AbstractNode(AbstractGraphElement):
    """
    Abstract base class for nodes in a graph.
    """
    
    def __init__(self, idx: Hashable, **kwargs):
        super().__init__(**kwargs)
        dict.__setitem__(self, "idx", idx)
        self["type"] = self.__class__.__name__

    @property
    @abstractmethod
    def idx(self):
        return dict.__getitem__(self, "idx")


class AbstractLink(AbstractGraphElement):
    """
    Abstract base class for links in a graph.
    """

    def __init__(self, idx: Hashable, i: Hashable, j: Hashable, **kwargs):
        super().__init__(**kwargs)
        dict.__setitem__(self, "idx", idx)
        dict.__setitem__(self, "i", i)
        dict.__setitem__(self, "j", j)
   
    @property
    @abstractmethod
    def idx(self):
        return dict.__getitem__(self, "idx")

    @property
    @abstractmethod
    def i(self) -> Tuple[Hashable, Hashable]:
        pass

    @property
    @abstractmethod
    def j(self) -> Tuple[Hashable, Hashable]:
        pass

    
class AbstractTurn(AbstractGraphElement):
    """
    Abstract base class for turns in a graph.
    """

    def __init__(self, idx: Hashable, in_link: Hashable, out_link: Hashable, **kwargs):
        super().__init__(**kwargs)
        dict.__setitem__(self, "idx", idx)
        dict.__setitem__(self, "in_link", in_link)
        dict.__setitem__(self, "out_link", out_link)
    
    @property
    @abstractmethod
    def idx(self):
        return dict.__getitem__(self, "idx")

    @property
    @abstractmethod
    def in_link(self) -> Hashable:
        pass

    @property
    @abstractmethod
    def out_link(self) -> Hashable:
        pass


class AbstractGraph(ABC, dict):
    """
    Abstract base class for the graph structure.
    """

    def __init__(self, **kwargs):
        super().__init__()
        self.update(**kwargs)

    @property
    @abstractmethod
    def n_links(self) -> int:
        pass

    @property
    @abstractmethod
    def n_nodes(self) -> int:
        pass

    @property
    @abstractmethod
    def n_turns(self) -> int:
        pass

    @abstractmethod
    def apply_links(self, fn: Callable = None):
        pass
    
    @abstractmethod
    def add_link(self, idx: Hashable, i: Hashable, j: Hashable, **kwargs) -> AbstractLink:
        """
        Add a link to the graph.
        """
        pass

    @abstractmethod
    def add_node(self, idx: Hashable, **kwargs) -> AbstractNode:
        """
        Add a node to the graph.
        """
        pass

    @abstractmethod
    def add_turn(self, idx: Hashable, in_link: Hashable, out_link: Hashable, **kwargs) -> AbstractTurn:
        """
        Add a turn to the graph.
        """
        pass

    @abstractmethod
    def get_link(self, idx: Hashable) -> Optional[AbstractLink]:
        """
        Get a link by its identifier.
        """
        pass

    @abstractmethod
    def get_node(self, idx: Hashable) -> Optional[AbstractNode]:
        """
        Get a node by its identifier.
        """
        pass

    @abstractmethod
    def get_turn(self, idx_or_in_link: Hashable, out_link: Optional[Hashable] = None) -> Optional[AbstractTurn]:
        """
        Get turns for given incoming and outgoing links.
        """
        pass

    def save(self, filename: str) -> None:
        """
        Save the graph to a file.
        """
        with open(filename, "wb") as f:
            dill.dump(self, f, dill.HIGHEST_PROTOCOL)

    @staticmethod
    def load(filename: str) -> AbstractGraph:
        """
        Load a graph from a file.
        """
        with open(filename, "rb") as f:
            return dill.load(f)

    def copy(self) -> AbstractGraph:
        return deepcopy(self)