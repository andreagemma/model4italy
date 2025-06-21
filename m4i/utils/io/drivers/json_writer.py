import geopandas
import json
import pandas as pd
import uuid
from ...util import json_load_file, load_dict, file_ordered_list
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
import shutil
import tempfile
from pathlib import Path

class JsonWriter(BaseDriver):

    @classmethod
    def name(cls) -> str:
        return "json"

    @classmethod
    def pattern(cls) -> List[str]:
        return [
            r"\.json$",
        ]
    
    def import_dataframe(
        self,
        path: str,
        **kwargs
    ) -> Union[dict,list]:                
        from ... import json_load_file
        if os.path.isdir(path):
            files = file_ordered_list(path, estensioni={".json"})
            if not files:
                raise ValueError(f"Nessun file JSON trovato nella cartella '{path}'.")
            data = None
            for file in files:
                file_path = os.path.join(path, file)
                json_data = json_load_file(file_path)
                if isinstance(json_data, list):
                    if data is None:
                        data = []
                    elif not isinstance(data, list):
                        raise ValueError(f"File JSON non consistenti tra di loro")
                    data.extend(json_data)
                elif isinstance(json_data, dict):
                    if data is None:
                        data = {}
                    elif not isinstance(data, data):
                        raise ValueError(f"File JSON non consistenti tra di loro")
                    data.update(json_data)
                else:
                    raise ValueError(f"Il file JSON '{file_path}' non contiene un oggetto o una lista di oggetti.")
            return data
        return json_load_file(path)

    def export_dataframe(
        self,
        df: Union[dict,list],
        path: str,
        mode: str = "w",
        template: str = "{filename}-{i}",
        **kwargs
    ):
        from ... import json_load_file, json_serialize

        if mode in ("wa", "aw", "a"):
            if os.path.exists(path):
                if not os.path.isfile(path):
                    file = Path(path)
                    temp_dir = tempfile.TemporaryDirectory()
                    destinazione = temp_dir / file.name
                    shutil.move(str(file), destinazione)
                    remove_path(path)
                    path = os.path.join(path, os.path.basename(path))
                    shutil.move(destinazione, path)
                filename = os.path.basename(path)
                extension = os.path.splitext(filename)[1]
                file_name = template.format(
                    filename=os.path.splitext(path)[0],
                    i="*",
                )
                i = len(glob.glob(os.path.join(path,f"{file_name}{extension}")))
                file_name = template.format(
                    filename=os.path.splitext(filename)[0],
                    i=str(int(i) + 1),
                )
                json_serialize.save(df, os.path.join(os.path.dirname(path), f"{file_name}{extension}"))
            else:
                json_serialize(df,path)
        else:
            remove_path(path)
            json_serialize(df,path)

