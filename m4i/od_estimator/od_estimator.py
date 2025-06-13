# -*- coding: utf-8 -*-
"""
Created on Fri Jun 11 16:16:31 2021

@author: andge
"""
import copy
import dateutil
import numpy as np
import pandas as pd
from libs.iniclass import IniClass
from ..matrix import MatrixODT, MatrixOD, MatrixAss
from .. import Loader

class ODEstimator:


    def __init__(self, loader:Loader=None, ODSeed:MatrixODT=None, **kwargs):
        # inizializzazione #load
        # load file e memorizzi in dict counts
        self.loader:Loader = loader
        self.ini: IniClass= self.loader.ini
        self.counts: pd.DataFrame = self.loader.counts
        self.detectors: pd.DataFrame = self.loader.detectors
        self.ODseed: MatrixODT = ODSeed.copy()


    def update(self, OD:MatrixODT, M: MatrixAss, tstart:int, tend:int, **kwargs) -> MatrixODT:
        raise NotImplementedError("The method is not implemented")
    
    
