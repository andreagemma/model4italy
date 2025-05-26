from __future__ import annotations
import datetime
from typing import Union, Any, Iterable, Callable
import json
import ast
import pandas as pd
import geopandas as gpd
from shapely.geometry import LineString, MultiLineString, Point, Polygon, MultiPolygon, MultiPoint
from shapely.geometry.base import BaseGeometry
import os
from collections import namedtuple
from .utils import util
from .iniclass import IniClass

class ParamsParser:
    """
    A class to parse parameters from a string.
    """
    @staticmethod
    def params_to_dict(params: Union[str,dict, list,tuple]) -> dict:
        if isinstance(params, str):
            try:
                if os.path.exists(params):
                    with open(params, "r") as f:
                        params = json.load(f)
                else:            
                    params = json.loads(params)
            except Exception as ex:
                raise ValueError(f"Invalid parameters: {params}") from ex
        elif isinstance(params, (list,tuple)):
            ret = {}
            for p in params:
                if p:
                    ret.update(ParamsParser.params_to_dict(p))
            params = ret
        if not isinstance(params, dict):    
            raise ValueError("Invalid parameters: %s" % params)        
        return params
    def __init__(self, params: Union[str,dict, list,tuple], settings: IniClass=None):
        self.params:dict = ParamsParser.params_to_dict(params)
        self.fields:dict = self.init_fields()
        self.ini:IniClass = settings
        self.update_params()

    @staticmethod
    def from_file(params_path: str="params.ini", settings_path: str="settings.ini") -> ParamsParser:
        """
        Load parameters from a JSON file.
        """
        with open(params_path, "r") as f:
            params = json.load(f)
        ini = IniClass(settings_path)
        parser = ParamsParser(params=params, settings=ini)
        return parser
    
    def update_params(self):
        if "start" in self.params:
            self.set_value("start",util.min2hhmm(util.hhmm2min(self.get("start"))))
            self.set_value("t_start",util.hhmm2min(self.get("start")))
        if "end" in self.params:
            self.set_value("end",util.min2hhmm(util.hhmm2min(self.get("end"))))
            self.set_value("t_end",util.hhmm2min(self.get("end")))
        
        if "date" not in self.params:
            self.set_value("date",datetime.datetime.now().strftime("%Y-%m-%d"))
            

        settings = self.get("settings",copy=False)
        if settings:
            if isinstance(settings,dict):
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
            if isinstance(x, (list,tuple)):
                return pd.isna(x).all()
            else:
                return pd.isna(x)
        def is_int(series: pd.Series) -> bool:
            return pd.api.types.is_integer_dtype(series) or pd.api.types.is_integer(series)

        def is_float(series: pd.Series) -> bool:
            return pd.api.types.is_float_dtype(series) or pd.api.types.is_float(series)

        def is_number(series: pd.Series) -> bool:
            return pd.api.types.is_numeric_dtype(series) or pd.api.types.is_number(series)

        def is_str(series: pd.Series) -> bool:
            return pd.api.types.is_string_dtype(series) or isinstance(series, str)

        def is_dict(series: pd.Series) -> bool:
            if isinstance(series, dict) or series is None:
                return True
            return all([is_null(x) or isinstance(x, dict) or isinstance(ast.literal_eval(x),dict) for x in series])

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
            return all([is_null(x) or isinstance(x, (LineString, MultiLineString)) for x in series])

        def is_point(series: pd.Series) -> bool:
            if isinstance(series, (Point, MultiPoint)) or series is None:
                return True
            return all([is_null(x) or isinstance(x, (Point, MultiPoint)) for x in series])

        def is_polygon(series: pd.Series) -> bool:
            if isinstance(series, (Polygon, MultiPolygon)) or series is None:
                return True
            return all([is_null(x) or isinstance(x, (Polygon, MultiPolygon)) for x in series])

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
                return series[pd.notna(series)].str.lower().isin({"true", "false", "1", "0", "t", "f"}).all()
            elif pd.api.types.is_numeric_dtype(series):
                return series[pd.notna(series)].isin((0,1)).all()
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
                    pd.to_datetime(series[pd.notna(series)], format="%H:%M", errors="raise")
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
                    pd.to_datetime(series[pd.notna(series)], format="%Y-%m-%d %H:%M:%S", errors="raise")
                    return True
                except ValueError:
                    return False
            if pd.api.types.is_datetime64_any_dtype(series):
                return True
            return False
        def parse_json(series):
            if pd.api.types.is_string_dtype(series):
                try:
                    return pd.Series(map(lambda x: json.loads(x) if pd.notna(x) else None,series))
                except json.JSONDecodeError:
                    raise ValueError(f"Invalid JSON string: {series}")
            return series
        
        def parse_set(series):
            if pd.api.types.is_string_dtype(series):
                try:
                    return pd.Series(map(lambda x: set(x.split(',')) if pd.notna(x) else None,series))
                except ValueError:
                    raise ValueError(f"Invalid set string: {series}")
            return series
        


        fields = {
            "modes": [
                {"name": "id", "type": is_str, "dtype": "string", "required": True},
                {"name": "description", "type": is_str, "dtype": "string", "required": False, "default": ""},
                {"name": "eq_factor", "type": is_number, "dtype": "Float32", "required": False, "default": 1.0},                
                
            ],
            "detectors": [
                {"name": "id", "type": is_int, "dtype": "Int64", "required": True},
                {"name": "id_link", "type": is_int, "dtype": "Int64", "required": True}
            ],
            "counts": [
                {"name": "id", "type": is_int, "dtype": "Int64", "required": True},
                {"name": "timestamp", "type": is_int, "dtype": "Int16", "required": True},
                {"name": "mode", "type": is_set, "dtype": "string", "required": False, "default": None},
                {"name": "counts", "type": is_number, "dtype": "Float32", "required": True},                
            ],
            "matrices": [
                {"name": "o", "type": is_int, "dtype": "Int64", "required": True},
                {"name": "d", "type": is_int, "dtype": "Int64", "required": True},
                {"name": "value", "type": is_number, "dtype": "Float32", "required": True},
                {"name": "timestamp", "type": is_int, "dtype": "Int16", "required": True},
            ],
            "zones": [
                {"name": "id", "type": is_int, "dtype": "Int64", "required": True},
                {"name": "geometry", "type": is_polygon, "dtype": "geometry", "required": False},
            ],
            "links": [
                {"name": "id", "type": is_int, "dtype": "Int64", "required": True},
                {"name": "from_node", "type": is_int, "dtype": "Int64", "required": True},
                {"name": "to_node", "type": is_int, "dtype": "Int64", "required": True},
                {"name": "v0", "type": is_float, "dtype": "Float32", "required": True},
                {"name": "connector", "type": is_bool, "dtype": "boolean", "required": True},
                {"name": "lanes", "type": is_number, "dtype": "Float32", "required": True},
                {"name": "alpha", "type": is_number, "dtype": "Float32", "required": True, "default": 1.6},
                {"name": "rcr", "type": is_number, "dtype": "Float32", "required": True, "default": 30},
                {"name": "capacity", "type": is_number, "dtype": "Float32", "required": True},
                {"name": "length", "type": is_number, "dtype": "Float32", "required": True},
                {"name": "modes", "type": is_set, "dtype": "string", "required": True, "default": None, "parser": parse_set},
                {"name": "geometry", "type": is_line, "dtype": "geometry", "required": True},
            ],
            "nodes": [
                {"name": "id", "type": is_int, "dtype": "Int64", "required": True},
                {"name": "modes", "type": is_set, "dtype": "string", "required": True, "default": None, "parser": parse_set},
                {"name": "geometry", "type": is_point, "dtype": "geometry", "required": False},
            ],
            "turns": [
                {"name": "from_node", "type": is_int, "dtype": "Int64", "required": True},
                {"name": "to_node", "type": is_int, "dtype": "Int64", "required": True},
                {"name": "via_node", "type": is_int, "dtype": "Int64", "required": True},
                {"name": "modes", "type": is_set, "dtype": "string", "required": False, "default": None, "parser": parse_set},                
                {"name": "penalty", "type": is_number, "dtype": "Float64", "required": False, "default": float("inf")},                
            ],
            "links_sets": [
                {"name": "set", "type": is_str, "dtype": "string", "required": True},
                {"name": "id_link", "type": is_int, "dtype": "Int64", "required": True},
            ],
            "events": [
                {"name": "id_link_set", "type": is_str, "dtype": "string", "required": True},
                {"name": "type", "type": is_str, "dtype": "string", "required": True},
                {"name": "start", "type": is_str_hhmm, "dtype": "string", "required": True},
                {"name": "end", "type": is_str_hhmm, "dtype": "string", "required": True},
                {"name": "params", "type": is_dict, "dtype": "string", "required": True, "parser": parse_json},

            ],
            "traffic_lights": [
                {"name": "id", "type": is_int, "dtype": "Int64", "required": True},
                {"name": "cycle", "type": is_number, "dtype": "Float32", "required": True},
                {"name": "offset", "type": is_number, "dtype": "Float32", "required": True, "default": 0},
                {"name": "phases", "type": [is_str, is_list], "dtype": "string", "required": True, "parser": parse_json},
                
            ],
            "aggregated_results": [
                {"name": "time", "type": is_str_datetime, "dtype": "datetime64[ns]", "required": True},
                {"name": "mode", "type": is_int, "dtype": "string", "required": True},
                {"name": "id_link", "type": is_int, "dtype": "Int64", "required": True},
                {"name": "flow_in", "type": is_number, "dtype": "Float32", "required": True},
                {"name": "flow_out", "type": is_number, "dtype": "Float32", "required": True},
                {"name": "max_q", "type": is_number, "dtype": "Float32", "required": True},
                {"name": "mov_vehs", "type": is_number, "dtype": "Float32", "required": True},
                {"name": "que_vehs", "type": is_number, "dtype": "Float32", "required": True},
                {"name": "speed", "type": is_number, "dtype": "Float32", "required": True},
                {"name": "density", "type": is_number, "dtype": "Float32", "required": True},
                {"name": "tt", "type": is_number, "dtype": "Float32", "required": True},
                {"name": "geometry", "type": is_line, "dtype": "geometry", "required": True},
            ],
            "paths": [
                {"name": "source", "type": is_int, "dtype": "Int64", "required": True},
                {"name": "target", "type": is_int, "dtype": "Int64", "required": True},
                {"name": "t_start", "type": is_int, "dtype": "Int16", "required": True},
                {"name": "t_base", "type": is_int, "dtype": "Int16", "required": True},
                {"name": "t", "type": is_int, "dtype": "Int64", "required": True},
                {"name": "mode", "type": is_int, "dtype": "string", "required": True},
                {"name": "tot_cost", "type": is_number, "dtype": "Float32", "required": True},
                {"name": "links", "type": is_list, "dtype": "string", "required": True},
                {"name": "costs", "type": is_list, "dtype": "string", "required": True},
                {"name": "k", "type": is_number, "dtype": "Int8", "required": True},
                {"name": "path_flow", "type": is_number, "dtype": "Float32", "required": True},
                {"name": "geometry", "type": is_line, "dtype": "geometry", "required": True},
            ],
            "fcd": [
                {"name": "id_fcd", "type": is_str, "dtype": "string", "required": True},
                {"name": "id_veh", "type": is_str, "dtype": "string", "required": True},
                {"name": "timestamp", "type": is_str_datetime, "dtype": "datetime64[ns]", "required": True},
                {"name": "engine", "type": is_int, "dtype": "Int8", "required": True},
                {"name": "speed", "type": is_float, "dtype": "Float32", "required": True},
                {"name": "heading", "type": is_float, "dtype": "Float32", "required": True},
                {"name": "lon", "type": is_float, "dtype": "Float64", "required": False, "default": lambda row: row["geometry"].coords[0] if pd.notna(row["geometry"]) else None},
                {"name": "lat", "type": is_float, "dtype": "Float64", "required": False, "default": lambda row: row["geometry"].coords[1] if pd.notna(row["geometry"]) else None},
                {"name": "geometry", "type": is_point, "dtype": "geometry", "required": False, "default": lambda row: Point(row["lon"], row["lat"]) if pd.notna(row["lon"]) and pd.notna(row["lat"]) else None},
            ],
        }
        return fields
    
    def check_fields(self, name: str, df: Union[pd.DataFrame,gpd.GeoDataFrame, dict]) -> str:
        params = self.fields.get(name, None)
        if params is None:
            raise ValueError(f"Unknown name: {name}")
        if isinstance(df, dict):
            df = pd.DataFrame.from_dict(df)
        for field in params:
            if field.get("required",False) and field["name"] not in df.columns:
                raise ValueError(f"Missing required field: {field['name']} in {name} layer")            
            if "default" in field:
                if field["name"] not in df.columns:
                    if isinstance(field["default"], Callable):
                        df[field["name"]] = df.apply(field["default"](df), axis=1)
                    else:
                        df[field["name"]] = field["default"]
                else:
                    if field["default"] is not None:
                        if isinstance(field["default"], Callable):
                            df[field["name"]] = df.apply(field["default"](df), axis=1).infer_objects(copy=False)
                        else:
                            df.loc[pd.isnull(df[field["name"]]),field["name"]]=field["default"]
                            df[field["name"]] = df[field["name"]].infer_objects(copy=False)
                    else:
                        df.loc[pd.isnull(df[field["name"]]),field["name"]] = None
                
            if field["name"] in df.columns:
                fields_type = field["type"]
                if not isinstance(fields_type, list):
                    fields_type = [fields_type]
                ok = False
                types = []
                for field_type in fields_type:
                    types.append(field['dtype'])
                    if not field_type(df[field["name"]]):
                        ok |=False
                    else:
                        ok |= True
                        break
                if not ok:
                    raise ValueError(f"Invalid type for field: {field['name']} in {name} layer. Expected {types}, got {df[field['name']].dtype}")
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

    def get_dtype(self, name: str) -> dict:
        if name in self.fields:
            fields = self.fields[name]
            return {field["name"]: field["dtype"] for field in fields}
        else:
            raise ValueError(f"Unknown name: {name}")
        
    def get_input_parameters(self, name_or_params: str, index: int = None) -> dict:
        if isinstance(name_or_params, dict):
            parameters = name_or_params
        elif isinstance(name_or_params, str):
            parameters = self.get(name_or_params, index)
        if parameters is None:
            return None
        elif isinstance(parameters, str):
            parameters = {"src": parameters}
        base_param = self.get("params.input")
        if isinstance(base_param, dict):
            base_param.update(parameters)
        elif isinstance(parameters, str):
            base_param["src"] = parameters
        base_param.setdefault("location", None)
        base_param.setdefault("mapping", {})
        base_param.setdefault("op", None)

        name_category = name_or_params.split(".")[-1]
        if name_category in self.fields:
            mapping = self.get_mapping(name_category, base_param["mapping"])
            base_param["mapping"] = mapping

        return base_param

    def get_output_parameters(self, name_or_params: str = None, index: int = None) -> dict:
        if isinstance(name_or_params, dict):
            parameters = name_or_params
        elif isinstance(name_or_params, str):
            parameters = self.get(name_or_params, index)
        if parameters is None:
            return None
        elif isinstance(parameters, str):
            parameters = {"src": parameters}
        base_param = self.get("params.output")
        if isinstance(base_param, dict):
            base_param.update(parameters)
        elif isinstance(parameters, str):
            base_param["src"] = parameters
        base_param.setdefault("location", None)
        base_param.setdefault("mapping", {})
        base_param.setdefault("op", None)

        name_category = name_or_params.split(".")[-1]
        if name_category in self.fields:
            mapping = self.get_mapping(name_category, base_param["mapping"])
            base_param["mapping"] = mapping

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
                return default
        if copy and isinstance(value, (dict, list)):
            if isinstance(value, dict):
                value = value.copy()
            elif isinstance(value, list):
                value = value.copy()
        if value is None:
            return default
        return value

    def get_parametric_name(self, name, **kwargs):
        kwargs = kwargs or self.params
        if isinstance(name, str):
            kwargs = kwargs.copy()
            for k, v in self.params.items():
                if isinstance(v, (float, int, str)):
                    kwargs.setdefault(k, v)
            name = name.format(**kwargs)
        elif isinstance(name, dict):
            name = {k: self.get_parametric_name(v, **kwargs) for k, v in name.items()}
        return name

    @staticmethod
    def apply_mapping(df, mapping, reverse=False):
        if reverse:
            mapping = {v: k for k, v in mapping.items()}
        ret = pd.DataFrame()
        assigned = set()
        for k, v in mapping.items():    
            if v in df.columns:
                if v in assigned:
                    ret[k] = df[v].copy()
                else:
                    ret[k] = df[v]
                assigned.add(v)
            else:
                ret[k] = None
        return ret
    
    @staticmethod
    def apply_dtype(df, dtype, copy=False):
        if dtype is None:
            return df
        try:
            if isinstance(dtype, dict):
                dtype = {k: v for k, v in dtype.items() if k in df.columns}
                df=df.astype(dtype, copy=copy)
            else:
                df = df.astype(dtype, copy=copy)
        except Exception as e:
            raise ValueError(f"Invalid dtype: {dtype}") from e
        return df