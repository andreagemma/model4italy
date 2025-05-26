import pandas as pd
import re
from typing import Optional, List, Union
from ..drivers import BaseDriver

class PandasDriver(BaseDriver):

    @property
    def name(self) -> str:
        return "pandas"

    @property
    def pattern(self) -> List[str]:
        return [
            r"\.csv$",
            r"\.json$",
            r"\.xlsx?$",
            r"\.html$",
            r"\.feather$",
            r"\.pkl$",
            r"\.pickle$",
            r"\.parquet$",
        ]

    def import_dataframe(
        self,
        path: str,
        filters: Optional[dict] = None,
        dtype: Optional[dict] = None,
        **kwargs
    ) -> pd.DataFrame:
        if path.lower().endswith(".csv"):
            df = pd.read_csv(path, dtype=dtype, **kwargs)
            BaseDriver.apply_filters(df, filters)
        elif path.lower().endswith(".json"):
            df = pd.read_json(path, dtype=dtype, **kwargs)
            BaseDriver.apply_filters(df, filters)
        elif path.lower().endswith(".xlsx") or path.lower().endswith(".xls"):
            df = pd.read_excel(path, dtype=dtype, **kwargs)
            BaseDriver.apply_filters(df, filters)
        elif path.lower().endswith(".html"):
            dfs = pd.read_html(path, **kwargs)
            BaseDriver.adapt_dtype(df, dtype)
            BaseDriver.apply_filters(df, filters)
            df = dfs[0] if dfs else pd.DataFrame()
        elif path.lower().endswith(".feather"):
            df = pd.read_feather(path, **kwargs)
            BaseDriver.adapt_dtype(df, dtype)
            BaseDriver.apply_filters(df, filters)
        elif path.lower().endswith(".pkl") or path.lower().endswith(".pickle"):
            df = pd.read_pickle(path, **kwargs)
            BaseDriver.adapt_dtype(df, dtype)
            BaseDriver.apply_filters(df, filters)
        elif path.lower().endswith(".parquet"):
            df = pd.read_parquet(path, filters=filters, **kwargs)
            BaseDriver.adapt_dtype(df, dtype)
        else:
            raise ValueError(f"Formato file non supportato: {path}")
        return df

    def export_dataframe(
        self,
        df: pd.DataFrame,
        path: str,
        mode: str = "w",
        partitionby: Optional[List[str]] = None,
        **kwargs
    ):
        if path.lower().endswith(".parquet"):
            df.to_parquet(path, partition_cols=partitionby, **kwargs)
        else:
            if path.lower().endswith(".csv"):
                df.to_csv(path, index=False, mode=mode, **kwargs)
            elif path.lower().endswith(".json"):
                df.to_json(path, **kwargs)
            elif path.lower().endswith(".xlsx") or path.lower().endswith(".xls"):
                df.to_excel(path, index=False, **kwargs)
            elif path.lower().endswith(".html"):
                df.to_html(path, index=False, **kwargs)
            elif path.lower().endswith(".feather"):
                df.to_feather(path, **kwargs)
            elif path.lower().endswith(".pkl") or path.lower().endswith(".pickle"):
                df.to_pickle(path, **kwargs)
            elif path.lower().endswith(".parquet"):
                df.to_parquet(path, partition_cols=partitionby, **kwargs)
            else:
                raise ValueError(f"Formato file non supportato: {path}")
