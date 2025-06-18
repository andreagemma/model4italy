import geopandas
import json
import pandas as pd
import uuid
from m4i.utils.util import json_load_file, load_dict
from ... import remove_path
import os
from typing import Optional, List, Union
from ..drivers import BaseDriver
from datetime import datetime
from os import getpid

from uuid import uuid4
from typing import Generator, Any
from pathlib import Path
import polars as pl
import glob
class JsonWriter(BaseDriver):

    @property
    def name(self) -> str:
        return "json"

    @property
    def pattern(self) -> List[str]:
        return [
            r"\.json$",
        ]

    def import_dataframe(
        self,
        path: str,
        **kwargs
    ) -> Union[dict,list]:                
        from ... import json_load_file
        return json_load_file(path)

    def export_dataframe(
        self,
        df: Union[dict,list],
        path: str,
        mode: str = "w",
        **kwargs
    ):
        from ... import json_load_file, json_serialize
        if mode in ("wa", "aw", "a"):
            if os.path.exists(path):
                if not os.path.isfile(path):
                    raise ValueError(f"Il percorso specificato '{path}' non è un file valido.")                
                existing_data = json_load_file(path)
                if isinstance(existing_data, list):
                    if isinstance(df, list):
                        df = existing_data + df
                    elif isinstance(df, dict):
                        df = existing_data + [df]
                    else:
                        raise ValueError("Il file JSON esistente non contiene un oggetto o una lista di oggetti.")
                elif isinstance(existing_data, dict):
                    if isinstance(df, list):
                        df = [existing_data] + df
                    elif isinstance(df, dict):
                        df = existing_data.update(df)
                    else:
                        raise ValueError("Il file JSON esistente non contiene un oggetto o una lista di oggetti.")
        else:
            remove_path(path)
            json_serialize(df,path)
