import geopandas
import json
import pandas as pd
import pickle
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
from ...serializer import Serializer
import shutil
import tempfile
from pathlib import Path

class PickleWriter(BaseDriver):

    @classmethod
    def name(cls) -> str:
        return "pickle"

    @classmethod
    def pattern(cls) -> List[str]:
        return [
            r"\.pkl$",
            r"\.pikle$",
        ]

    def import_dataframe(
        self,
        path: str,
        **kwargs
    ) -> object:
        Serializer.load(path)

    def export_dataframe(
        self,
        df: object,
        path: str,
        mode: str = "w",
        partitionby: Optional[List[str]] = None,
        template: str = "{filename}-{i}",
        **kwargs
    ):
        if mode == "w":
            remove_path(path)
            mode = "a"
        if partitionby is not None:
            subdir = []
            for partition in partitionby:
                if hasattr(df,"__contains__") and hasattr(df,"__getitem__") and partition in df:
                    subdir.append(f"{partition}={df[partition]}")
            if subdir:
                path = os.path.join(path, *subdir, os.path.basename(path))
                if mode in ("wa","aw"):
                    remove_path(os.path.dirname(path))
                    mode = "a"
                os.makedirs(os.path.dirname(path), exist_ok=True)
        if os.path.exists(path):
            if os.path.isfile(path):
                file = Path(path)
                temp_dir = tempfile.TemporaryDirectory().name              
                os.makedirs(temp_dir, exist_ok=True)      
                destinazione = os.path.join(temp_dir , file.name)
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
            Serializer.save(df, os.path.join(os.path.dirname(path), f"{file_name}{extension}"))
        else:
            Serializer.save(df, path)
        
