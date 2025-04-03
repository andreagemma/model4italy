from __future__ import annotations
import os, csv

import numpy as np
import pandas as pd
from pandas import read_csv
from typing import List, Callable, Dict, Optional, Union

from .matrix_od import MatrixOD, _convert_to_dict

class MatrixODT:

    def __init__(self, rows: List, cols: List, timestamps: List, init: Optional[Dict[MatrixOD, MatrixODT]] = None, copy: bool = False, mode:Optional[str]=None) -> None:
        if isinstance(init, MatrixODT):
            if copy:
                self.ods = {t: od.copy() for t,od in init.ods.items()}
                
                self.rows = init.rows.copy()
                self.cols = init.cols.copy()
                self.timestamps = init.timestamps.copy()
            else:
                self.ods = init.ods
                self.rows = init.rows
                self.cols = init.cols
                self.timestamps = init.timestamps
        else:
            self.rows = _convert_to_dict(rows)
            self.cols = _convert_to_dict(cols)
            self.timestamps = set(sorted(timestamps))
            if init is not None and isinstance(init, dict):
                self.ods = {}
                for t, od in init.items():
                    if isinstance(od, MatrixOD):
                        if copy:
                            self.ods[t] = od.copy()
                        else:
                            self.ods[t] = od
                    else:
                        self.ods[t] = MatrixOD(self.rows, self.cols, od, copy=copy)
                for t in self.timestamps-set(self.ods.keys()):
                    self.ods[t] = MatrixOD(self.rows, self.cols)
            else:
                self.ods = {}
                for t in self.timestamps:
                    self.ods[t] = MatrixOD(rows=self.rows, cols=self.cols)
    
        self.mode = mode

    def copy(self, copy_data: bool = True) -> 'MatrixODT':
        return MatrixODT(self.rows, self.cols, self.timestamps, init=self, copy=copy_data)

    def __getitem__(self, pos: Union[tuple, int]) -> Union[MatrixOD, float]:
        if isinstance(pos, int):
            return self.ods.get(pos, MatrixOD(self.rows, self.cols))
        else:
            o, d, t = pos
            if t in self.ods:
                return self.ods[t][o, d]
            else:
                return 0

    def __setitem__(self, pos: Union[tuple, int], value: Union[MatrixOD, float]) -> None:
        if isinstance(pos, int):
            self.ods[pos] = value
        else:
            o, d, t = pos
            self.ods[t][o, d] = value

    def sum(self, axis: Optional[int] = None) -> Union[float, 'MatrixOD', 'MatrixODT']:
        if axis is None:
            total_sum = 0
            for od in self.ods.values():
                total_sum+=od.sum()
            return total_sum
        elif axis == 0:            
            summed_cols = MatrixODT(["sum"], self.cols, self.timestamps)
            for t, od in self.ods.items():
                summed_cols[t] = od.sum(axis=0)
            return summed_cols
        elif axis == 1:            
            summed_rows = MatrixODT(self.rows,["sum"], self.timestamps)
            for t, od in self.ods.items():
                summed_rows[t] = od.sum(axis=1)
            return summed_rows
        elif axis == 2:            
            summed_timestamps = MatrixOD(self.rows,self.cols)
            for t, od in self.ods.items():
                summed_timestamps += od
            return summed_timestamps
        else:
            raise ValueError("Axis must be 0, 1, 2, or None.")  
        

    def __add__(self, other: Union[int,float,"MatrixODT"]) -> "MatrixODT":
        ret = self.copy()
        ret += other
        return ret
    
    def __iadd__(self, other: Union[int,float,"MatrixODT"]) -> "MatrixODT":
        if isinstance(other, MatrixODT):
            if self.rows != other.rows or self.cols != other.cols:
                raise ValueError("Matrices must have the same dimensions.")
            for ts,mat in other.ods.items():
                if ts in self.timestamps:
                    self.ods[ts] += mat
                else:
                    self.ods[ts] = mat.copy()
        elif isinstance(other, (int, float)):
            for ts, mat in self.ods.items():
                mat += other
        else:
            raise TypeError("Unsupported operand type for addition.")
        return self

    def __sub__(self, other: Union[int,float,"MatrixODT"]) -> "MatrixODT":
        ret = self.copy()
        ret -= other
        return ret
    
    def __isub__(self, other: Union[int,float,"MatrixODT"]) -> "MatrixODT":
        if isinstance(other, MatrixODT):
            if self.rows != other.rows or self.cols != other.cols:
                raise ValueError("Matrices must have the same dimensions.")
            for ts,mat in other.ods.items():
                if ts in self.timestamps:
                    self.ods[ts] -= mat
                else:
                    self.ods[ts] = -mat.copy()
        elif isinstance(other, (int, float)):
            for ts, mat in self.ods.items():
                mat -= other
        else:
            raise TypeError("Unsupported operand type for subtraction.")
        return self
              
    def __mul__(self, other: Union[int,float,"MatrixODT"]) -> "MatrixODT":
        ret = self.copy()
        ret *= other
        return ret
    
    def __imul__(self, other: Union[int,float,"MatrixODT"]) -> "MatrixODT":
        if isinstance(other, MatrixODT):
            if self.rows != other.rows or self.cols != other.cols:
                raise ValueError("Matrices must have the same dimensions.")
            for ts,mat in other.ods.items():
                if ts in self.timestamps:
                    self.ods[ts] *= mat
                else:
                    self.ods[ts] = mat*0
        elif isinstance(other, (int, float)):
            for ts, mat in self.ods.items():
                mat *= other
        else:
            raise TypeError("Unsupported operand type for multiplication.")
        return self
        
    def __truediv__(self, other: Union[int,float,"MatrixODT"]) -> "MatrixODT":
        ret = self.copy()
        ret /= other
        return ret
    
    def __itruediv__(self, other: Union[int,float,"MatrixODT"]) -> "MatrixODT":
        if isinstance(other, MatrixODT):
            if self.rows != other.rows or self.cols != other.cols:
                raise ValueError("Matrices must have the same dimensions.")
            mat: MatrixOD
            for ts,mat in other.ods.items():
                if ts in self.timestamps:
                    self.ods[ts] /= mat
                else:
                    self.ods[ts] = MatrixOD(rows=self.rows, cols=self.cols, init=0)/mat
        elif isinstance(other, (int, float)):
            for ts, mat in self.ods.items():
                mat -= other
        else:
            raise TypeError("Unsupported operand type for division.")
        return self
    
    @staticmethod
    def read_df(rows: List, cols: List, timestamps:List, df: pd.DataFrame, o_field:str ="o", d_field:str ="d", timestamp_field:str ="timestamp", value_field:str ="value") -> 'MatrixODT':
        ods = {}
        grouped = df[[o_field,d_field,value_field,timestamp_field]].rename(columns={o_field: "o", d_field: "d", value_field: "value"}).groupby(timestamp_field,
                                                                                                                                                group_keys=False,
                                                                                                                                                observed=False)
        for t, group in grouped:
            od = MatrixOD.read_df(rows, cols, df=group)
            ods[t] = od
        return MatrixODT(rows, cols, timestamps=timestamps, init=ods)

    def nan_to_num(self, copy=True, nan=0.0, posinf=None, neginf=None):
        for mat_od in self.ods.values():
            mat_od.nan_to_num(copy=copy, nan=nan, posinf=posinf, neginf=neginf)

    @staticmethod
    def read_csv(rows: List, cols: List, file: str, o_field:str ="o", d_field:str ="d", timestamp_field:str ="timestamp", value_field:str ="value") -> 'MatrixODT':
        df = pd.read_csv(file, usecols=[o_field, d_field, value_field, timestamp_field])
        return MatrixODT.read_df(rows, cols, df)

    def write_df(self) -> pd.DataFrame:
        data = []
        for t_key, od_matrix in self.ods.items():
            for o_key, o_index in od_matrix.rows.items():
                for d_key, d_index in od_matrix.cols.items():
                    data.append({'timestamp': t_key, 'o': o_key, 'd': d_key, 'value': od_matrix.mat[o_index, d_index]})
        return pd.DataFrame(data).sort_values(["timestamp","o","d"])

    def write_csv(self, file: str) -> None:
        df = self.write_df()
        df.to_csv(file, index=False)
