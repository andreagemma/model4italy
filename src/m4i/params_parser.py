from __future__ import annotations
import copy
import datetime
import operator
import time
from typing import Union, Any, Iterable, Callable, Optional
import json
import ast
import pandas as pd
import geopandas as gpd
from shapely.geometry import (
    LineString,
    MultiLineString,
    Point,
    Polygon,
    MultiPolygon,
    MultiPoint,
)
from shapely.geometry.base import BaseGeometry
import os
from collections import namedtuple
from m4i.utils.util import get_parametric_name
from .utils import util, deep_update
from .iniclass import IniClass
from datetime import datetime, timedelta
from .utils import to_datetime_auto
from .functions.day_type import day_type
import pytz


class ParamsParser:
    """
    A class to parse parameters from a string.
    """

    def __init__(
        self,
        params: Union[str, dict, list, tuple],
        settings: Optional[IniClass] = None,
        options: Optional[dict] = None,
    ):
        self.params: dict | None = ParamsParser.params_to_dict(params)
        deep_update(self.params, options)
        self.fields: dict = self.init_fields()
        self.ini: IniClass | None = settings
        self.update_params()

    def update_date(
        self, dt=None, name="simulation", override=True, time=True, date=True
    ) -> None:
        if dt:
            dt = to_datetime_auto(dt)
        now = dt or datetime.now()
        if override:
            if date:
                self.set_value(f"date_{name}", now.strftime("%Y-%m-%d"))
                self.set_value(f"day_type_{name}", ParamsParser.day_type(now))
                self.set_value(f"dow_{name}", now.isoweekday() % 7)
            if time:
                self.set_value(f"time_{name}", now.strftime("%H:%M:%S"))
            if date and time:
                self.set_value(f"datetime_{name}", now.strftime("%Y-%m-%d %H:%M:%S"))
            self.set_value(f"ts_{name}", int(round(now.timestamp() / 60)))
            self.set_value(f"t_{name}", now.hour * 60 + now.minute)
            self.set_value(f"{name}", now.strftime("%Y-%m-%d %H:%M:%S"))
        else:
            if date:
                self.set_default(f"date_{name}", now.strftime("%Y-%m-%d"))
                self.set_default(f"day_type_{name}", ParamsParser.day_type(now))
                self.set_default(f"dow_{name}", now.isoweekday() % 7)
            if time:
                self.set_default(f"time_{name}", now.strftime("%H:%M:%S"))
            if date and time:
                self.set_default(f"datetime_{name}", now.strftime("%Y-%m-%d %H:%M:%S"))
            self.set_default(f"ts_{name}", int(round(now.timestamp() / 60)))
            self.set_default(f"t_{name}", now.hour * 60 + now.minute)
            self.set_default(f"{name}", now.strftime("%Y-%m-%d %H:%M:%S"))

    @staticmethod
    def day_type(dt: Union[str, datetime]) -> str:
        dt = to_datetime_auto(dt)
        return day_type(dt)

    @staticmethod
    def params_to_dict(params: Union[str, dict, list, tuple]) -> dict | None:
        from .utils.util import deep_update

        if isinstance(params, str):
            if os.path.exists(params):
                with open(params, "r") as f:
                    params = json.load(f)
            else:
                params = {}
                return params  # raise FileNotFoundError(f"Parameters file not found: {params}")
        elif isinstance(params, (list, tuple)):
            ret: dict | None = None
            for p in params:
                if ret is None:
                    ret = ParamsParser.params_to_dict(p)
                else:
                    d: dict | None = ParamsParser.params_to_dict(p)
                    if d:
                        deep_update(d, ret)
                        ret = d
            params = ret
        if not isinstance(params, dict):
            raise ValueError("Invalid parameters: %s" % params)

        if "data_file" in params:
            data_file = params.pop("data_file")
            if not isinstance(data_file, (list, tuple)):
                data_file = [data_file]
            for df in data_file:
                df_path = get_parametric_name(df, **params)
                d = ParamsParser.params_to_dict(df_path)
                if d:
                    deep_update(d, params)
                    params = d
        return params

    def get_dict(self) -> dict:
        from copy import deepcopy

        settings = self.ini.get_dict()
        settings.update(deepcopy(self.params.get("settings", {})))
        params = deepcopy(self.params)
        params["settings"] = settings
        return params

    def clone(self):
        ini = self.ini
        params = copy.deepcopy(self.params)
        parser = ParamsParser(params=params, settings=ini)
        return parser

    @staticmethod
    def from_file(
        params: Union[str, dict, list, tuple], settings: str = "settings.ini"
    ) -> ParamsParser:
        """
        Load parameters from a JSON file.
        """

        ini = IniClass(settings)
        parser = ParamsParser(params=params, settings=ini)
        return parser

    def update_params(self):
        if "date_simulation" not in self.params:
            date_simulation = datetime.now()
            # self.set_value("date",datetime.datetime.now().strftime("%Y-%m-%d"))
        else:
            date_simulation = to_datetime_auto(
                self.get("date_simulation"), tz_localize=self.ini.TZ_LOCAL
            )
        if "start" not in self.params:
            time_start = datetime.now(tz=pytz.timezone(self.ini.TZ_LOCAL))
            # discretizza time_start al passo di delta_t
            time_start = time_start.replace(second=0, microsecond=0)
            time_start_min = (
                (time_start.hour * 60 + time_start.minute)
                // self.ini.DELTA_T
                * self.ini.DELTA_T
            )
            time_start = time_start.replace(
                hour=time_start_min // 60, minute=time_start_min % 60
            )
        else:
            time_start = to_datetime_auto(
                self.get("start"),
                date_default=date_simulation,
                tz_localize=self.ini.TZ_LOCAL,
            )

        if "end" not in self.params:
            time_end = time_start + timedelta(minutes=60)
            time_end = time_end.replace(second=0, microsecond=0)
            time_end_min = (
                (time_end.hour * 60 + time_end.minute)
                // self.ini.DELTA_T
                * self.ini.DELTA_T
            )
            time_end = time_end.replace(
                hour=time_end_min // 60, minute=time_end_min % 60
            )
        else:
            time_end = to_datetime_auto(
                self.get("end"),
                date_default=date_simulation,
                tz_localize=self.ini.TZ_LOCAL,
            )

        dt = datetime.combine(
            date_simulation.date(),
            time_start.time(),
            tzinfo=pytz.timezone(self.ini.TZ_LOCAL),
        )
        self.update_date(dt=dt, name="simulation", override=True, time=True, date=True)
        self.update_date(
            dt=time_start, name="start", override=True, time=True, date=True
        )
        self.update_date(dt=time_end, name="end", override=True, time=True, date=True)
        self.set_default(
            "total_time", int((time_end - time_start).total_seconds() / 60)
        )
        self.set_default("delta_t", self.ini.DELTA_T)
        self.set_default("num_intervals", self.get("total_time") // self.get("delta_t"))
        """
        #if "start" in self.params:
            #self.set_value("start",util.min2hhmm(util.hhmm2min(self.get("start"))))
            #self.set_value("t_start",util.hhmm2min(self.get("start")))
        if "end" in self.params:
            
            #self.set_value("end",util.min2hhmm(util.hhmm2min(self.get("end"))))
            #self.set_value("t_end",util.hhmm2min(self.get("end")))
        """

        settings = self.get("settings", copy=False)
        if settings:
            if isinstance(settings, dict):
                for k, v in settings.items():
                    if hasattr(self.ini, k):
                        setattr(self.ini, k, v)
            else:
                raise TypeError("settings key in params defintion must be a dictionary")

    def set_value(self, path: str, value: Any) -> None:
        """
        Set a value in the params dictionary using a dot-separated path.
        """
        keys = path.split(".")
        d = self.params
        for key in keys[:-1]:
            if key not in d:
                d[key] = {}
            d = d[key]
        d[keys[-1]] = value

    def set_default(self, path: str, value: Any) -> None:
        """
        Set a value in the params dictionary using a dot-separated path.
        """
        keys = path.split(".")
        d = self.params
        for key in keys[:-1]:
            if key not in d:
                d[key] = {}
            d = d[key]
        d.setdefault(keys[-1], value)

    def __contains__(self, key: str) -> bool:
        """
        Check if a key exists in the params dictionary using a dot-separated path.
        """
        keys = key.split(".")
        d = self.params
        for k in keys:
            if k not in d:
                return False
            d = d[k]
        return True

    def init_fields(self):
        def is_null(x: Iterable) -> bool:
            if x is None:
                return True
            if isinstance(x, str):
                return x.strip() == ""
            if isinstance(x, (list, tuple)):
                return pd.isna(x).all()
            else:
                return pd.isna(x)

        def is_int(series: pd.Series) -> bool:
            return pd.api.types.is_integer_dtype(series) or pd.api.types.is_integer(
                series
            )

        def is_float(series: pd.Series) -> bool:
            return pd.api.types.is_float_dtype(series) or pd.api.types.is_float(series)

        def is_number(series: pd.Series) -> bool:
            return pd.api.types.is_numeric_dtype(series) or pd.api.types.is_number(
                series
            )

        def is_str(series: pd.Series) -> bool:
            return pd.api.types.is_string_dtype(series) or isinstance(series, str)

        def is_dict(series: pd.Series) -> bool:
            if isinstance(series, dict) or series is None:
                return True
            return all(
                [
                    is_null(x)
                    or isinstance(x, dict)
                    or isinstance(ast.literal_eval(x), dict)
                    for x in series
                ]
            )

        def is_list(series: pd.Series) -> bool:
            if isinstance(series, list) or series is None:
                return True
            return all([is_null(x) or isinstance(x, list) for x in series])

        def is_set(series: pd.Series) -> bool:
            if isinstance(series, set) or series is None:
                return True
            if isinstance(series, str):
                s = series.strip().split(",")
                try:
                    set(x)
                except TypeError:
                    return False
                return True

            if all([pd.isna(x) or isinstance(x, set) for x in series]):
                return True
            if pd.api.types.is_string_dtype(series):
                s = series.str.strip().str.split(",")
                for x in s:
                    if is_null(x) or len(x) == 0 or pd.isna(x).all():
                        continue
                    try:
                        set(x)
                    except TypeError:
                        return False
                return True
            return False

        def is_geometry(series: pd.Series) -> bool:
            if isinstance(series, BaseGeometry) or series is None:
                return True
            return all([is_null(x) or isinstance(x, (BaseGeometry)) for x in series])

        def is_line(series: pd.Series) -> bool:
            if isinstance(series, (LineString, MultiLineString)) or series is None:
                return True
            return all(
                [
                    is_null(x) or isinstance(x, (LineString, MultiLineString))
                    for x in series
                ]
            )

        def is_point(series: pd.Series) -> bool:
            if isinstance(series, (Point, MultiPoint)) or series is None:
                return True
            return all(
                [is_null(x) or isinstance(x, (Point, MultiPoint)) for x in series]
            )

        def is_polygon(series: pd.Series) -> bool:
            if isinstance(series, (Polygon, MultiPolygon)) or series is None:
                return True
            return all(
                [is_null(x) or isinstance(x, (Polygon, MultiPolygon)) for x in series]
            )

        def is_bool(series: pd.Series) -> bool:
            if isinstance(series, bool) or series is None:
                return True
            elif isinstance(series, str):
                return series.lower() in {"true", "false", "1", "0", "t", "f"}
            elif isinstance(series, (int, float)):
                return series in {0, 1}
            elif pd.api.types.is_bool_dtype(series):
                return True
            elif pd.api.types.is_string_dtype(series):
                return (
                    series[pd.notna(series)]
                    .str.lower()
                    .isin({"true", "false", "1", "0", "t", "f"})
                    .all()
                )
            elif pd.api.types.is_numeric_dtype(series):
                return series[pd.notna(series)].isin((0, 1)).all()
            return False

        def is_str_hhmm(series: pd.Series) -> bool:
            if series is None:
                return True
            if isinstance(series, str):
                try:
                    pd.to_datetime(series, format="%H:%M", errors="raise")
                    return True
                except ValueError:
                    return False
            if pd.api.types.is_string_dtype(series):
                try:
                    pd.to_datetime(
                        series[pd.notna(series)], format="%H:%M", errors="raise"
                    )
                    return True
                except ValueError:
                    return False
            return False

        def is_str_datetime(series: pd.Series) -> bool:
            if series is None:
                return True
            if isinstance(series, str):
                try:
                    pd.to_datetime(series, format="%Y-%m-%d %H:%M:%S", errors="raise")
                    return True
                except ValueError:
                    return False
            if pd.api.types.is_string_dtype(series):
                try:
                    pd.to_datetime(
                        series[pd.notna(series)],
                        format="%Y-%m-%d %H:%M:%S",
                        errors="raise",
                    )
                    return True
                except ValueError:
                    return False
            if pd.api.types.is_datetime64_any_dtype(series):
                return True
            return False

        def parse_json(series):
            if pd.api.types.is_string_dtype(series):
                try:
                    return pd.Series(
                        map(
                            lambda x: json.loads(x) if pd.notna(x) and x else None,
                            series,
                        )
                    )
                except json.JSONDecodeError:
                    raise ValueError(f"Invalid JSON string: {series}")
            return series

        def parse_set(series):
            if pd.api.types.is_string_dtype(series):
                try:
                    return pd.Series(
                        map(
                            lambda x: set(x.split(",")) if pd.notna(x) else None, series
                        )
                    )
                except ValueError:
                    raise ValueError(f"Invalid set string: {series}")
            return series

        fields = {
            "modes": [
                {"name": "code", "type": is_str, "dtype": "string", "required": True},
                {
                    "name": "description",
                    "type": is_str,
                    "dtype": "string",
                    "required": False,
                    "default": "",
                },
                {
                    "name": "eq_factor",
                    "type": is_number,
                    "dtype": "Float32",
                    "required": False,
                    "default": 1.0,
                },
            ],
            "detectors": [
                {"name": "id", "type": is_int, "dtype": "Int64", "required": True},
                {"name": "id_link", "type": is_int, "dtype": "Int64", "required": True},
            ],
            "counts": [
                {"name": "id", "type": is_int, "dtype": "Int64", "required": True},
                {
                    "name": "timestamp",
                    "type": is_int,
                    "dtype": "Int16",
                    "required": True,
                },
                {
                    "name": "mode",
                    "type": is_str,
                    "dtype": "string",
                    "required": False,
                    "default": None,
                },
                {
                    "name": "counts",
                    "type": is_number,
                    "dtype": "Float32",
                    "required": True,
                },
            ],
            "matrices": [
                {"name": "o", "type": is_int, "dtype": "Int64", "required": True},
                {"name": "d", "type": is_int, "dtype": "Int64", "required": True},
                {
                    "name": "value",
                    "type": is_number,
                    "dtype": "Float32",
                    "required": True,
                },
                {
                    "name": "timestamp",
                    "type": is_int,
                    "dtype": "Int16",
                    "required": True,
                },
            ],
            "zones": [
                {"name": "id", "type": is_int, "dtype": "Int64", "required": True},
                {
                    "name": "geometry",
                    "type": is_polygon,
                    "dtype": "geometry",
                    "required": False,
                },
            ],
            "links": [
                {"name": "id", "type": is_int, "dtype": "Int64", "required": True},
                {
                    "name": "from_node",
                    "type": is_int,
                    "dtype": "Int64",
                    "required": True,
                },
                {"name": "to_node", "type": is_int, "dtype": "Int64", "required": True},
                {"name": "v0", "type": is_float, "dtype": "Float32", "required": True},
                {
                    "name": "connector",
                    "type": is_bool,
                    "dtype": "bool",
                    "required": True,
                },
                {
                    "name": "lanes",
                    "type": is_number,
                    "dtype": "Float32",
                    "required": True,
                },
                {
                    "name": "alpha",
                    "type": is_number,
                    "dtype": "Float32",
                    "required": True,
                    "default": 1.6,
                },
                {
                    "name": "rcr",
                    "type": is_number,
                    "dtype": "Float32",
                    "required": True,
                    "default": 30,
                },
                {
                    "name": "capacity",
                    "type": is_number,
                    "dtype": "Float32",
                    "required": True,
                },
                {
                    "name": "length",
                    "type": is_number,
                    "dtype": "Float32",
                    "required": True,
                },
                {
                    "name": "modes",
                    "type": is_set,
                    "dtype": "string",
                    "required": True,
                    "default": None,
                    "parser": parse_set,
                },
                {
                    "name": "geometry",
                    "type": is_line,
                    "dtype": "geometry",
                    "required": True,
                },
            ],
            "nodes": [
                {"name": "id", "type": is_int, "dtype": "Int64", "required": True},
                {"name": "centroid", "type": is_int, "dtype": "Int8", "required": True},
                {
                    "name": "modes",
                    "type": is_set,
                    "dtype": "string",
                    "required": True,
                    "default": None,
                    "parser": parse_set,
                },
                {
                    "name": "geometry",
                    "type": is_point,
                    "dtype": "geometry",
                    "required": False,
                },
            ],
            "turns": [
                {
                    "name": "from_link",
                    "type": is_int,
                    "dtype": "Int64",
                    "required": True,
                },
                {"name": "to_link", "type": is_int, "dtype": "Int64", "required": True},
                {
                    "name": "from_node",
                    "type": is_int,
                    "dtype": "Int64",
                    "required": True,
                },
                {"name": "to_node", "type": is_int, "dtype": "Int64", "required": True},
                {
                    "name": "via_node",
                    "type": is_int,
                    "dtype": "Int64",
                    "required": True,
                },
                {
                    "name": "modes",
                    "type": is_set,
                    "dtype": "string",
                    "required": False,
                    "default": None,
                    "parser": parse_set,
                },
                {
                    "name": "penalty",
                    "type": is_number,
                    "dtype": "Float64",
                    "required": False,
                    "default": float("inf"),
                },
            ],
            "links_sets": [
                {"name": "id_set", "type": is_str, "dtype": "string", "required": True},
                {"name": "id_link", "type": is_int, "dtype": "Int64", "required": True},
            ],
            "events": [
                {
                    "name": "id_link_set",
                    "type": is_str,
                    "dtype": "string",
                    "required": True,
                },
                {"name": "type", "type": is_str, "dtype": "string", "required": True},
                {
                    "name": "start",
                    "type": is_str_hhmm,
                    "dtype": "string",
                    "required": True,
                },
                {
                    "name": "end",
                    "type": is_str_hhmm,
                    "dtype": "string",
                    "required": True,
                },
                {
                    "name": "params",
                    "type": is_dict,
                    "dtype": "string",
                    "required": True,
                    "parser": parse_json,
                },
            ],
            "traffic_lights": [
                {"name": "id", "type": is_int, "dtype": "Int64", "required": True},
                {
                    "name": "cycle",
                    "type": is_number,
                    "dtype": "Float32",
                    "required": True,
                },
                {
                    "name": "offset",
                    "type": is_number,
                    "dtype": "Float32",
                    "required": True,
                    "default": 0,
                },
                {
                    "name": "phases",
                    "type": [is_str, is_list],
                    "dtype": "string",
                    "required": True,
                    "parser": parse_json,
                },
                {
                    "name": "geometry",
                    "type": is_point,
                    "dtype": "geometry",
                    "required": True,
                },
            ],
            "aggregated_results": [
                {
                    "name": "time",
                    "type": is_str_datetime,
                    "dtype": "datetime64[ns]",
                    "required": True,
                },
                {"name": "mode", "type": is_int, "dtype": "string", "required": True},
                {"name": "id_link", "type": is_int, "dtype": "Int64", "required": True},
                {
                    "name": "flow_in",
                    "type": is_number,
                    "dtype": "Float32",
                    "required": True,
                },
                {
                    "name": "flow_out",
                    "type": is_number,
                    "dtype": "Float32",
                    "required": True,
                },
                {
                    "name": "max_q",
                    "type": is_number,
                    "dtype": "Float32",
                    "required": True,
                },
                {
                    "name": "mov_vehs",
                    "type": is_number,
                    "dtype": "Float32",
                    "required": True,
                },
                {
                    "name": "que_vehs",
                    "type": is_number,
                    "dtype": "Float32",
                    "required": True,
                },
                {
                    "name": "speed",
                    "type": is_number,
                    "dtype": "Float32",
                    "required": True,
                },
                {
                    "name": "density",
                    "type": is_number,
                    "dtype": "Float32",
                    "required": True,
                },
                {"name": "tt", "type": is_number, "dtype": "Float32", "required": True},
                {
                    "name": "geometry",
                    "type": is_line,
                    "dtype": "geometry",
                    "required": True,
                },
            ],
            "paths": [
                {"name": "source", "type": is_int, "dtype": "Int64", "required": True},
                {"name": "target", "type": is_int, "dtype": "Int64", "required": True},
                {"name": "t_start", "type": is_int, "dtype": "Int16", "required": True},
                {"name": "t_base", "type": is_int, "dtype": "Int16", "required": True},
                {"name": "t", "type": is_int, "dtype": "Int64", "required": True},
                {"name": "mode", "type": is_int, "dtype": "string", "required": True},
                {
                    "name": "tot_cost",
                    "type": is_number,
                    "dtype": "Float32",
                    "required": True,
                },
                {"name": "links", "type": is_list, "dtype": "string", "required": True},
                {"name": "costs", "type": is_list, "dtype": "string", "required": True},
                {"name": "k", "type": is_number, "dtype": "Int8", "required": True},
                {
                    "name": "path_flow",
                    "type": is_number,
                    "dtype": "Float32",
                    "required": True,
                },
                {
                    "name": "geometry",
                    "type": is_line,
                    "dtype": "geometry",
                    "required": True,
                },
            ],
            "fcd": [
                {"name": "id_fcd", "type": is_str, "dtype": "string", "required": True},
                {
                    "name": "id_trip",
                    "type": is_str,
                    "dtype": "string",
                    "required": True,
                },
                {"name": "id_veh", "type": is_str, "dtype": "string", "required": True},
                {
                    "name": "timestamp",
                    "type": is_str_datetime,
                    "dtype": "datetime64[ns]",
                    "required": True,
                },
                {"name": "engine", "type": is_int, "dtype": "Int8", "required": True},
                {
                    "name": "speed",
                    "type": is_float,
                    "dtype": "Float32",
                    "required": True,
                },
                {
                    "name": "heading",
                    "type": is_float,
                    "dtype": "Float32",
                    "required": True,
                },
                {
                    "name": "progr",
                    "type": is_float,
                    "dtype": "Float32",
                    "required": True,
                },
                {
                    "name": "lon",
                    "type": is_float,
                    "dtype": "Float64",
                    "required": False,
                    "default": lambda row: (
                        row["geometry"].coords[0] if pd.notna(row["geometry"]) else None
                    ),
                },
                {
                    "name": "lat",
                    "type": is_float,
                    "dtype": "Float64",
                    "required": False,
                    "default": lambda row: (
                        row["geometry"].coords[1] if pd.notna(row["geometry"]) else None
                    ),
                },
                {
                    "name": "geometry",
                    "type": is_point,
                    "dtype": "geometry",
                    "required": False,
                    "default": lambda row: (
                        Point(row["lon"], row["lat"])
                        if pd.notna(row["lon"]) and pd.notna(row["lat"])
                        else None
                    ),
                },
            ],
            "fcd_paths": [
                {"name": "source", "type": is_int, "dtype": "Int64", "required": True},
                {"name": "target", "type": is_int, "dtype": "Int64", "required": True},
                {"name": "t_start", "type": is_int, "dtype": "Int16", "required": True},
                {"name": "t_base", "type": is_int, "dtype": "Int16", "required": True},
                {"name": "t", "type": is_int, "dtype": "Int64", "required": True},
                {"name": "mode", "type": is_int, "dtype": "string", "required": True},
                {
                    "name": "tot_cost",
                    "type": is_number,
                    "dtype": "Float32",
                    "required": True,
                },
                {"name": "links", "type": is_list, "dtype": "string", "required": True},
                {
                    "name": "id_trip",
                    "type": is_int,
                    "dtype": "string",
                    "required": True,
                },
                {
                    "name": "geometry",
                    "type": is_line,
                    "dtype": "geometry",
                    "required": True,
                },
            ],
        }
        return fields

    def check_fields(
        self, name: str, df: Union[pd.DataFrame, gpd.GeoDataFrame, dict]
    ) -> str:
        params = self.fields.get(name, None)

        if params is None:
            raise ValueError(f"Unknown name: {name}")
        if len(df) == 0:
            return
        if isinstance(df, dict):
            df = pd.DataFrame.from_dict(df)
        for field in params:
            if field.get("required", False) and field["name"] not in df.columns:
                raise ValueError(
                    f"Missing required field: {field['name']} in {name} layer"
                )
            if "default" in field:
                if field["name"] not in df.columns:
                    if isinstance(field["default"], Callable):
                        df[field["name"]] = df.apply(field["default"](df), axis=1)
                    else:
                        df[field["name"]] = field["default"]
                else:
                    if field["default"] is not None:
                        if isinstance(field["default"], Callable):
                            df[field["name"]] = df.apply(
                                field["default"](df), axis=1
                            ).infer_objects(copy=False)
                        else:
                            df.loc[pd.isnull(df[field["name"]]), field["name"]] = field[
                                "default"
                            ]
                            df[field["name"]] = df[field["name"]].infer_objects(
                                copy=False
                            )
                    else:
                        df.loc[pd.isnull(df[field["name"]]), field["name"]] = None

            if field["name"] in df.columns:
                fields_type = field["type"]
                if not isinstance(fields_type, list):
                    fields_type = [fields_type]
                ok = False
                types = []
                for field_type in fields_type:
                    types.append(field["dtype"])
                    if not field_type(df[field["name"]]):
                        ok |= False
                    else:
                        ok |= True
                        break
                if not ok:
                    raise ValueError(
                        f"Invalid type for field: {field['name']} in {name} layer. Expected {types}, got {df[field['name']].dtype}"
                    )
                if "parser" in field:
                    df[field["name"]] = field["parser"](df[field["name"]])

    def get_mapping(self, name: str, mapping=None) -> dict:

        if name in self.fields:
            fields = self.fields[name]
            base_mapping = {field["name"]: field["name"] for field in fields}
            if mapping:
                base_mapping.update(mapping)
            return base_mapping
        else:
            raise ValueError(f"Unknown name: {name}")

    def get_additional_field(self, name: str, mapping) -> dict:

        if name in self.fields:
            fields = set(f["name"] for f in self.fields[name])
            additional_fields = {k: v for k, v in mapping.items() if k not in fields}
            return additional_fields
        else:
            raise ValueError(f"Unknown name: {name}")

    def get_dtype(self, name: str, default=None) -> dict:
        if name in self.fields:
            fields = self.fields[name]
            return {field["name"]: field["dtype"] for field in fields}
        else:
            return default

    def get_output_parameters(
        self,
        name_or_params: str = None,
        index: int = None,
        df: pd.DataFrame = None,
        from_input=False,
    ) -> dict:
        if from_input:
            base = "params.input"
        else:
            base = "params.output"
        ret = self.get_parameters(
            name_or_params=name_or_params, index=index, df=df, base=base
        )
        if ret is None:
            return ret
        if connector := ret.get("connector", None):
            if connector.endswith("Loader"):
                ret["connector"] = connector.replace("Loader", "Writer")
        return ret

    def get_input_parameters(
        self, name_or_params: str, index: int = None, from_output=False
    ) -> dict:
        if from_output:
            base = "params.output"
        else:
            base = "params.input"
        ret = self.get_parameters(
            name_or_params=name_or_params, index=index, df=None, base=base
        )
        if ret is None:
            return ret
        if connector := ret.get("connector", None):
            if connector.endswith("Writer"):
                ret["connector"] = connector.replace("Writer", "Loader")
        return ret

    def get_parameters(
        self,
        name_or_params: str = None,
        index: int = None,
        df: pd.DataFrame = None,
        base="params.input",
    ) -> dict:
        if isinstance(name_or_params, dict):
            parameters = name_or_params
        elif isinstance(name_or_params, str):
            parameters = self.get(name_or_params, index)
        if parameters is None:
            return None
        elif isinstance(parameters, str):
            parameters = {"src": parameters}
        base_param = self.get(base)
        if isinstance(base_param, dict):
            base_param.update(parameters)
        elif isinstance(parameters, str):
            base_param["src"] = parameters
        base_param.setdefault("location", None)
        base_param.setdefault("mapping", {})
        additional_fields = base_param.get("additional_fields", {})
        base_param.setdefault("op", None)
        base_param.setdefault("tz_data", self.ini.TZ_LOCAL)
        if df is not None and isinstance(df, (pd.DataFrame, gpd.GeoDataFrame)):
            mapping = base_param.get("mapping", {})
            for c in df.columns:
                if c not in mapping:
                    pass
                elif c == "geometry" and isinstance(df, gpd.GeoDataFrame):
                    pass
            for k, v in mapping.items():
                if k == "geometry" and isinstance(df, gpd.GeoDataFrame):
                    pass
                elif k not in df.columns:
                    additional_fields[k] = v
        # base_param["additional_fields"] = additional_fields
        name_category = name_or_params.split(".")[-1]
        if name_category in self.fields:
            mapping = self.get_mapping(name_category, base_param["mapping"])
            # additional_fields = self.get_additional_field(name_category, mapping)
            base_param["mapping"] = mapping
            for k in mapping.keys():
                if k in additional_fields:
                    additional_fields.pop(k)
            # base_param["additional_fields"].update(additional_fields)
        base_param["additional_fields"] = additional_fields
        for k, v in additional_fields.items():
            if k not in base_param["mapping"]:
                base_param["mapping"][k] = k

        return base_param

    def get(self, path: str, *args, copy=True, default=None) -> Any:
        """
        Get a parameter from the params dictionary using a dot-separated path.
        """
        keys = path.split(".")
        if args:
            keys = keys + [str(arg) for arg in args if arg is not None]
        value = self.params
        for key in keys:
            if isinstance(value, (dict)) and key in value:
                value = value[key]
            elif isinstance(value, (list, tuple)) and key.isdigit():
                value = value[int(key)]
            else:
                return self.get_parametric_name(default)
        if copy and isinstance(value, (dict, list)):
            if isinstance(value, dict):
                value = value.copy()
            elif isinstance(value, list):
                value = value.copy()
        if value is None:
            return self.get_parametric_name(default)
        return self.get_parametric_name(value)

    def get_parametric_name(self, name, **kwargs):
        from .utils import ravel_dict, get_parametric_name

        kwargs = kwargs or self.params
        name = get_parametric_name(name, **kwargs)
        return name

    @staticmethod
    def apply_mapping(df, mapping, writing=False):
        or_mapping = mapping.copy()
        if writing:
            mapping = {v: k for k, v in mapping.items()}
            ret = df.rename(columns=mapping)
            if isinstance(df, gpd.GeoDataFrame):
                geom_col = or_mapping.get("geometry", "geometry")
                if geom_col != ret.geometry.name:
                    ret.rename_geometry(geom_col, inplace=True)
            return ret

        ret = pd.DataFrame(index=df.index)
        assigned = set()
        for k, v in mapping.items():
            if v in df.columns:
                if v in assigned:
                    ret[k] = df[v].copy()
                else:
                    ret[k] = df[v]
                assigned.add(v)
            else:
                if not isinstance(v, dict):
                    d = {"value": v}
                else:
                    d = v
                v = d.get("value", None)
                t = d.get("type", None)
                if isinstance(v, str) and v.startswith("expression:"):
                    v = v.replace("expression:", "")
                    ret[k] = df.eval(v)
                elif isinstance(v, str) and v.startswith("lambda:"):
                    v = v.replace("lambda:", "")
                    ret[k] = df.apply(lambda x: eval(v), axis=1)
                else:
                    ret[k] = None
                if t is not None:
                    ret[k] = ret[k].astype(t)
        if isinstance(df, gpd.GeoDataFrame):
            geom_col = or_mapping.get("geometry", "geometry")
            ret = gpd.GeoDataFrame(
                ret.drop(columns=geom_col, errors="ignore"),
                geometry=ret[geom_col],
                crs=df.crs,
            )
            if geom_col != ret.geometry.name:
                ret.rename_geometry(geom_col, inplace=True)
        return ret

    def apply_dtype(self, df, dtype, copy=False, tz_src=None, tz_dest=None):
        if dtype is None:
            return df
        try:
            if isinstance(dtype, dict):
                dtype = {k: v for k, v in dtype.items() if k in df.columns}
                # remove dtype definition if dtype is a datetime
                for col in df.columns:
                    if pd.api.types.is_datetime64_any_dtype(df[col]) and col in dtype:
                        del dtype[col]
                df = df.astype(dtype, copy=copy)
            else:
                df = df.astype(dtype, copy=copy)
            for col in df.columns:
                if pd.api.types.is_datetime64_any_dtype(df[col]):
                    if df[col].dt.tz is None:
                        df[col] = df[col].dt.tz_localize(tz_src or self.ini.TZ_LOCAL)
                    df[col] = df[col].dt.tz_convert(tz_dest or self.ini.TZ_CALC)
        except Exception as e:
            raise ValueError(f"Invalid dtype: {dtype}") from e
        return df
