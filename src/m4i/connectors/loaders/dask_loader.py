# -*- coding: utf-8 -*-
"""
Created on Thu Jun 24 19:11:39 2021

@author: andge
"""

import pandas as pd
import geopandas as gpd
from os.path import join
from typing import Any
import json
from typing import Union

from .base_loader import BaseLoader
from ...utils.io.io_daskdataframe import IO_DaskDataFrame


class DaskLoader(BaseLoader):
    def __init__(self):
        super().__init__()

    def load_dataset(
        self, parameters, filters=None, dtype=None, **kwargs
    ) -> Union[pd.DataFrame, gpd.GeoDataFrame, dict]:
        location = parameters.get("location")
        src = parameters.get("src")

        if location:
            src = join(location, src)

        df = IO_DaskDataFrame.import_dataframe(src, filters=filters, dtype=dtype, kwargs_driver=kwargs)
        return df
