# -*- coding: utf-8 -*-
"""
Created on Fri Jun 11 16:16:31 2021

@author: andge
"""

import copy
import dateutil
import numpy as np
import pandas as pd
from m4i.connectors.writer import Writer
from ..matrix import MatrixODT, MatrixOD, MatrixAss
from ..connectors import Loader, Writer
from ..base_m4i_model import BaseM4IModel


class ODEstimator(BaseM4IModel):
    def __init__(
        self,
        loader: Loader = None,
        writer: Writer = None,
        ODSeed: MatrixODT = None,
        **kwargs,
    ):
        super().__init__(loader=loader, writer=writer, **kwargs)
        # inizializzazione #load
        # load file e memorizzi in dict counts
        self.counts: pd.DataFrame = self.loader.counts["all"].copy()
        self.detectors: pd.DataFrame = self.loader.detectors
        self.ODseed: MatrixODT = ODSeed.copy()

    def update(self, OD: MatrixODT, M: MatrixAss, tstart: int, tend: int, **kwargs) -> MatrixODT:
        raise NotImplementedError("The method is not implemented")
