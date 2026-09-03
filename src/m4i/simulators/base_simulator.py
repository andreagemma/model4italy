import pandas as pd

from ..connectors import Loader
from ..graphs import KPathList
from abc import ABC, abstractmethod
from ..log import Logger
from ..base_m4i_model import BaseM4IModel


class BaseSimulator(BaseM4IModel):
    def __init__(self, loader: Loader, **kwargs) -> None:
        super().__init__(loader=loader, **kwargs)

    @abstractmethod
    def update_performance(self, tstart: int, tend: int):
        pass

    @abstractmethod
    def initialize_assignment(self, time_start: int, time_end: int):
        pass

    @abstractmethod
    def finalize_assignment(self, time_start: int, time_end: int):
        pass

    @abstractmethod
    def set_paths(self, paths: KPathList):
        pass

    def agg_results(self, tstart: int, tend: int, agg_int: int) -> pd.DataFrame:
        pass

    def agg_stats(self, tstart: int, tend: int):
        pass

    def get_signalized_res(self, tstart: int, tend: int):
        pass

    def get_trace_res(self, tstart: int, tend: int):
        pass
