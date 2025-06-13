import pandas as pd

from ..connectors import Loader
from ..graphs import KPathList
from abc import ABC, abstractmethod
from ..log import Logger
from ..taskbase import TaskBase

class BaseSimulator(TaskBase):
    
    
    def __init__(self,loader: Loader, **kwargs) -> None:
        super().__init__(**kwargs)
        self.loader: Loader = loader        
        self.log: Logger = Logger.getLogger("SIM", execution_id=self.loader.execution_id)
    
    @abstractmethod
    def update_performance(self, tstart: int, tend: int):
        pass
        
    @abstractmethod
    def initialize_assignment(self, time_start: int,time_end: int):
        pass
    
    @abstractmethod
    def finalize_assignment(self, time_start: int,time_end: int):
        pass
    
    @abstractmethod
    def set_paths(self,paths: KPathList):
        pass
    
    @abstractmethod
    def agg_results(self, tstart: int, tend: int, agg_int: int) -> pd.DataFrame:
        pass
    