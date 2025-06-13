from abc import ABC, abstractmethod
from typing import Union
import pandas as pd
import geopandas as gpd

class BaseWriter(ABC):

    @abstractmethod
    def write_dataset(self,df: Union[pd.DataFrame,gpd.GeoDataFrame], parameters, mode=None, partition=None, **kwargs) -> bool:
        """
        Write a dataset based on the provided parameters and mode.
        Arguments:
            df (Union[pd.DataFrame, gpd.GeoDataFrame]): The dataset to be written.
            parameters (dict): A dictionary containing the dataset parameters.
            mode (str, optional): The mode in which the dataset should be written ('w' for write, 'a' for append). Default is None.
            **kwargs: Additional arguments for customization.
        Returns:
            bool: True if the dataset was successfully written, False otherwise.
        """
        pass
    
