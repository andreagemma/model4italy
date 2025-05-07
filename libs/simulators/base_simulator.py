import pandas as pd

from ..connectors import Loader
from ..graphs import KPathList
from abc import ABC, abstractmethod
from .. import Logger

class BaseSimulator():

    log = Logger.getLogger("SIM")
    
    def __init__(self,loader: Loader) -> None:
        self.loader: Loader = loader        
    
    @abstractmethod
    def update_performance(self, k: int, tstart: int, tend: int):
        pass
        
    @abstractmethod
    def initialize_assignment(self,time_start: int,time_end: int):
        pass
    
    @abstractmethod
    def finalize_assignment(self,time_start: int,time_end: int):
        pass
    
    @abstractmethod
    def set_paths(self,paths: KPathList):
        pass
    
    @abstractmethod
    def agg_results(self, tstart: int, tend: int, agg_int: int) -> pd.DataFrame:
        pass
    