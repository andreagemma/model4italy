import os, csv

import numpy as np
import pandas as pd
from typing import List, Callable, Dict, Union, Optional
from types import MappingProxyType


def _convert_to_dict(labels: Union[List, np.ndarray, Dict]) -> Dict:
    if isinstance(labels, (list, np.ndarray)):
        return {labels[i]: i for i in range(len(labels))}
    elif isinstance(labels, MappingProxyType):
        return labels
    elif isinstance(labels, dict):
        return MappingProxyType(labels)
    else:
        raise TypeError("Unsupported type for labels")


class MatrixOD:

    def __init__(
        self,
        rows: Union[List, np.ndarray, Dict],
        cols: Union[List, np.ndarray, Dict],
        init: Optional[Union[Dict, List, int, float, np.ndarray, "MatrixOD"]] = None,
        copy: bool = False,
        mode: Optional[str] = None,
    ) -> None:
        self.rows: Dict = _convert_to_dict(rows)  # Make rows immutable
        self.cols: Dict = _convert_to_dict(cols)  # Make cols immutable
        self.mat: np.ndarray = np.zeros((len(self.rows), len(self.cols)))

        if init is not None:
            if isinstance(init, Dict):
                for o, list_d in init.items():
                    for d, v in list_d.items():
                        self[o, d] = v
            elif isinstance(init, List):
                self.mat = np.array(init)
            elif isinstance(init, (int, float)):
                self.mat += init
            elif isinstance(init, np.ndarray):
                self.mat = init.copy() if copy else init
            elif isinstance(init, MatrixOD):
                self.mat = init.mat.copy() if copy else init.mat
        self.mode = mode 
        

    def copy(self, copy_data: bool = True) -> "MatrixOD":
        return MatrixOD(self.rows, self.cols, init=self.mat.copy() if copy_data else self.mat, copy=copy_data)

    def __getitem__(self, pos: tuple) -> float:
        i, j = pos
        vi = self.rows.get(i)
        vj = self.cols.get(j)
        if vi is None or vj is None:
            raise KeyError(f"Keys {i}, {j} not found in rows or columns.")
        return self.mat[vi, vj]

    def __setitem__(self, pos: tuple, v: float) -> None:
        i, j = pos
        vi = self.rows.get(i)
        vj = self.cols.get(j)
        #if vi is None or vj is None:
        #    raise KeyError(f"Keys {i}, {j} not found in rows or columns.")
        self.mat[vi, vj] = v

    def __repr__(self) -> str:
        return repr(self.mat)

    def __str__(self) -> str:
        row_labels = list(self.rows.keys())
        col_labels = list(self.cols.keys())

        # Limit rows and columns to first 5 and last 5 if they are too many
        if len(row_labels) > 10:
            row_labels = row_labels[:5] + ["..."] + row_labels[-5:]
        if len(col_labels) > 10:
            col_labels = col_labels[:5] + ["..."] + col_labels[-5:]

        header = "     " + " ".join(f"{col:>8}" for col in col_labels) + "\n"
        rows_str = ""
        for row in row_labels:
            if row == "...":
                rows_str += f"{row:>4} {'...':>8} {'...':>8} {'...':>8}\n"
            else:
                row_data = " ".join(f"{self[row, col]:>8.2f}" if col != "..." else "..." for col in col_labels)
                rows_str += f"{row:>4} {row_data}\n"
        return header + rows_str

    def __add__(self, other: Union[int,float,"MatrixOD"]) -> "MatrixOD":
        if isinstance(other, MatrixOD):
            if self.rows != other.rows or self.cols != other.cols:
                raise ValueError("Matrices must have the same dimensions.")
            return MatrixOD(self.rows, other.cols, init=self.mat+other.mat)
        elif isinstance(other, (int, float)):
            return MatrixOD(self.rows, self.cols, init=self.mat + other)
        else:
            raise TypeError("Unsupported operand type for addition.")

    def __sub__(self, other: Union[int,float,"MatrixOD"]) -> "MatrixOD":
        if isinstance(other, MatrixOD):
            if self.rows != other.rows or self.cols != other.cols:
                raise ValueError("Matrices must have the same dimensions.")
            return MatrixOD(self.rows, other.cols, init=self.mat-other.mat)
        elif isinstance(other, (int, float)):
            return MatrixOD(self.rows, self.cols, init=self.mat - other)
        else:
            raise TypeError("Unsupported operand type for subtraction.")

    def __iadd__(self, other: Union[int,float,"MatrixOD"]) -> "MatrixOD":
        if isinstance(other, MatrixOD):
            if self.rows != other.rows or self.cols != other.cols:
                raise ValueError("Matrices must have the same dimensions.")
            self.mat+=other.mat
        elif isinstance(other, (int, float)):
            self.mat += other
        else:
            raise TypeError("Unsupported operand type for addition.")
        return self

    def __isub__(self, other: Union[int,float,"MatrixOD"]) -> "MatrixOD":
        if isinstance(other, MatrixOD):
            if self.rows != other.rows or self.cols != other.cols:
                raise ValueError("Matrices must have the same dimensions.")
            self.mat += other.mat
        elif isinstance(other, (int, float)):
            self.mat += other
        else:
            raise TypeError("Unsupported operand type for subtraction.")
        return self

    def __mul__(self, other: Union["MatrixOD", int, float]) -> "MatrixOD":
        if isinstance(other, MatrixOD):
            if self.rows != other.rows or self.cols != other.cols:
                raise ValueError("Matrices must have the same dimensions.")
            return MatrixOD(self.rows, other.cols, init=self.mat*other.mat)
        elif isinstance(other, (int, float)):
            return MatrixOD(self.rows, self.cols, init=self.mat * other)
        else:
            raise TypeError("Unsupported operand type for multiplication.")

    def __imul__(self, other: Union[int, float]) -> "MatrixOD":
        if isinstance(other, MatrixOD):
            if self.rows != other.rows or self.cols != other.cols:
                raise ValueError("Matrices must have the same dimensions.")
            self.mat *= other.mat
        elif isinstance(other, (int, float)):
            self.mat *=  other
        else:
            raise TypeError("Unsupported operand type for addition.")
        return self
    
    def __truediv__(self, other: Union[int, float]) -> "MatrixOD":
        if isinstance(other, MatrixOD):
            if self.rows != other.rows or self.cols != other.cols:
                raise ValueError("Matrices must have the same dimensions.")
            return MatrixOD(self.rows, other.cols, init=self.mat/other.mat)
        elif isinstance(other, (int, float)):
            return MatrixOD(self.rows, self.cols, init=self.mat / other)
        else:
            raise TypeError("Unsupported operand type for division.")
        return self

    def __itruediv__(self, other: Union[int, float]) -> "MatrixOD":
        if isinstance(other, MatrixOD):
            if self.rows != other.rows or self.cols != other.cols:
                raise ValueError("Matrices must have the same dimensions.")
            self.mat /= other.mat
        elif isinstance(other, (int, float)):
            self.mat /= other
        else:
            raise TypeError("Unsupported operand type for addition.")
        return self

    def transpose(self) -> "MatrixOD":
        return MatrixOD(self.cols, self.rows, init=self.mat.T)

    def inverse(self) -> "MatrixOD":
        if self.mat.shape[0] != self.mat.shape[1]:
            raise ValueError("Matrix must be square to find its inverse.")
        return MatrixOD(self.rows, self.cols, init=np.linalg.inv(self.mat))

    def get_diagonal(self) -> np.ndarray:
        return np.diag(self.mat)

    def set_diagonal(self, values: List[float]) -> None:
        if len(values) != min(self.mat.shape):
            raise ValueError("Length of values must match the length of the matrix diagonal.")
        np.fill_diagonal(self.mat, values)

    def nan_to_num(self, copy=True, nan=0.0, posinf=None, neginf=None):
        np.nan_to_num(self.mat, copy=copy, nan=nan, posinf=posinf, neginf=neginf)

    def sum(self, axis: Optional[int] = None) -> Union[float, "MatrixOD"]:
        if axis is None:
            return np.sum(self.mat)
        elif axis == 0:
            # Sum over rows (return a matrix with one row)
            summed_cols = np.sum(self.mat, axis=0)
            return MatrixOD(["sum"], self.cols, init=summed_cols)
        elif axis == 1:
            # Sum over columns (return a matrix with one column)
            summed_rows = np.sum(self.mat, axis=1)
            return MatrixOD(self.rows, ["sum"], init=summed_rows[:, np.newaxis])
        else:
            raise ValueError("Axis must be 0, 1, or None.")

    @staticmethod
    def read_df(rows: List, cols: List, df: pd.DataFrame, o_field="o", d_field="d", value_field="value") -> "MatrixOD":

        # Grouping and transforming data into the desired nested dictionary format
        grouped = df[[o_field,d_field,value_field]].rename(columns={o_field: "o", d_field: "d", value_field: "value"}).groupby("o", group_keys=False).apply(lambda x: dict(zip(x["d"], x["value"])), include_groups=False).to_dict()
        return MatrixOD(rows=rows, cols=cols, init=grouped)

    @staticmethod
    def read_csv(rows: List, cols: List, file: str, o_field="o", d_field="d", value_field="value") -> "MatrixOD":
        df = pd.read_csv(file, usecols=[o_field, d_field, value_field])
        return MatrixOD.read_df(rows=rows, cols=cols, df=df, o_field=o_field, d_field=d_field, value_field=value_field)

    def write_df(self, o_field="o", d_field="d", value_field="value") -> pd.DataFrame:
        data = []
        for o_key, o_index in self.rows.items():
            for d_key, d_index in self.cols.items():
                data.append({o_field: o_key, d_field: d_key, value_field: self.mat[o_index, d_index]})
        return pd.DataFrame(data)

    def write_csv(self, file: str, o_field="o", d_field="d", value_field="value") -> None:
        df = self.write_df(o_field=o_field, d_field=d_field, value_field=value_field)
        df.to_csv(file, index=False)
