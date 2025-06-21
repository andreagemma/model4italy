import ast
import json
from typing import Union, Optional, List, Generator, Tuple, Any, Callable, Iterable
from numbers import Number
from uuid import uuid4
from math import ceil, inf
import warnings
from datetime import datetime, timedelta, MAXYEAR, date, time, tzinfo
from dateutil import parser

import sys
from types import ModuleType, FunctionType
from gc import get_referents
import threading
from os import getpid
import logging
import psutil
import pkgutil
import sys
from urllib.parse import urlparse, parse_qs, urlencode
import os

import re
from pathlib import Path
import shutil
from re import sub


try:
    from psutil import Process, NoSuchProcess
except ImportError:
    pass

try:
    import dill as pickle
except ImportError:
    import pickle


def chunks(lst: Union[List, Tuple], chunk_size: int = None, bins: int = 1) -> Generator:
    """
    Split a list in multiple chunks
    :param lst: list to devide
    :param chunk_size: size of chunk
    :param bins: number of bins to split the list. bins is ignored if chunk_size is defined
    :return:
    """
    if len(lst) == 0:
        return lst
    if chunk_size is None:
        chunk_size = ceil(len(lst) / bins)
    for i in range(0, len(lst), chunk_size):
        yield i, lst[i : i + chunk_size]


def save_dict(data: dict, file_name: str, compression=None, clevel: int=5) -> None:
    """
    Save a dictionary in a pickle file name
    :param data: data to save
    :param file_name: file name
    :return: None
    """
    from .serializer import Serializer

    if compression is None:
        if file_name.endswith(".gz") or file_name.endswith(".gzip"):
            compression = Serializer.CNAME_GZIP
        elif file_name.endswith(".bz2"):
            compression = Serializer.CNAME_BZ2
        elif file_name.endswith(".zip"):
            compression = Serializer.CNAME_ZIP
        elif file_name.endswith(".xz"):
            compression = Serializer.CNAME_LZMA
        elif file_name.endswith(".lz4"):        
            compression = Serializer.CNAME_LZ4
        elif file_name.endswith(".blz"):        
            compression = Serializer.CNAME_BLOSCLZ            
        elif file_name.endswith(".fast"):        
            compression = Serializer.CNAME_BLOSCLZ           
        elif file_name.endswith(".snappy"):        
            compression = Serializer.CNAME_SNAPPY
        elif file_name.endswith(".pickle"):        
            compression = None
    pickled = Serializer.serialize(data, compression=compression, clevel=clevel)
    with open(file_name, "wb") as f:
        f.write(pickled)
    

def load_dict(file_name: str, compression=None) -> dict:
    """
    Load dictionary from a file name
    :param file_name:
    :return:
    """
    from .serializer import Serializer
    if compression is None:
        if file_name.endswith(".gz") or file_name.endswith(".gzip"):
            compression = Serializer.CNAME_GZIP
        elif file_name.endswith(".bz2"):
            compression = Serializer.CNAME_BZ2
        elif file_name.endswith(".zip"):
            compression = Serializer.CNAME_ZIP
        elif file_name.endswith(".xz"):
            compression = Serializer.CNAME_LZMA
        elif file_name.endswith(".lz4"):        
            compression = Serializer.CNAME_LZ4
        elif file_name.endswith(".blz"):        
            compression = Serializer.CNAME_BLOSCLZ            
        elif file_name.endswith(".fast"):        
            compression = Serializer.CNAME_BLOSCLZ           
        elif file_name.endswith(".snappy"):        
            compression = Serializer.CNAME_SNAPPY
        elif file_name.endswith(".pickle"):        
            compression = None
    with open(file_name, "rb") as f:
        data = f.read()
        data = Serializer.deserialize(data, compression=compression)
    return data


def create_unique_name(prefix: Optional[str] = None) -> str:
    return ("T" if prefix is None else prefix) + str(
        "".join([str(x) for x in uuid4().fields])
    )


def serialize(obj: Any, compression: str=None, clevel=5) -> bytes:
    """
    compression = ‘blosclz’, ‘lz4’, ‘lz4hc’, ‘snappy’, ‘zlib’, ‘zstd'
    """
    import dill
    if compression is None:
        return pickle.dumps(obj, pickle.HIGHEST_PROTOCOL)
    if compression in ("blosclz", "lz4", "lz4hc", "snappy", "zlib", "zstd"):
        import blosc
        ser = pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)
        data = blosc.compress(ser, typesize=8, cname=compression, clevel=clevel)
        return pickle.dumps(data, pickle.HIGHEST_PROTOCOL)

def deserialize(data: bytes, compression: str = None) -> Any:
    import dill
    """
    compression = ‘blosclz’, ‘lz4’, ‘lz4hc’, ‘snappy’, ‘zlib’, ‘zstd'
    """
    
    data = pickle.loads(data)
    if compression is None:
        return data
    if compression in ("blosclz", "lz4", "lz4hc", "snappy", "zlib", "zstd"):
        import blosc
        obj = dill.loads(blosc.decompress(data))
    return obj

def json_serialize(obj: Any, file_name: str, indent: int = 4):
    import jsonpickle
    with open(file_name, "w") as f:
        json_obj = jsonpickle.encode(obj, make_refs=False,indent=indent)
        f.write(json_obj)
        f.close()


def json_load_file(file_name: str):
    import jsonpickle
    with open(file_name) as f:
        json_str = f.read()
        obj = jsonpickle.decode(json_str)
    return obj


def normalize_name(
    name: Union[str, Iterable[str]],
    replace=(
        {"à": "a", "é": "e", "è": "e", "ì": "i", "ò": "o", "ù": "u", "\n": ""},
        {"[^a-zA-Z0-9]": "_"},
        {"__": "_"},
    ),
    str_fun: Iterable[Callable] = (str.lower, str.strip),
    recursive=True,
):
    if isinstance(name, str):
        original = name
        for fn in str_fun:
            name = fn(name)

        if isinstance(replace, dict):
            replace = [replace]
        for r in replace:
            for k, v in r.items():
                name = sub(k, v, name)

        if recursive and original != name:
            return normalize_name(
                name, replace=replace, str_fun=str_fun, recursive=recursive
            )
        return name

    elif isinstance(name, Iterable):
        return [
            normalize_name(c, replace=replace, str_fun=str_fun, recursive=recursive)
            for c in name
        ]
    else:
        return normalize_name(
            str(name), replace=replace, str_fun=str_fun, recursive=recursive
        )


    
def generate_series(
    start: Union[Number, datetime],
    stop: Optional[Union[Number, datetime]] = None,
    step: Optional[Union[Number, datetime]] = None,
    n_elements: Optional[Number] = None,
    included: str = "left",
) -> Generator :
    """
    The function `generate_series` creates a generator that yields a series of numbers or datetimes
    based on the specified start, stop, step, and inclusion parameters.
    
    :param start: The `start` parameter is the starting value of the series. It can be either a number
    (int, float, complex) or a datetime object. This value determines where the series will begin
    :type start: Union[Number, datetime]
    :param stop: The `stop` parameter in the `generate_series` function is used to specify the endpoint
    of the series. It indicates where the series should stop generating values. If this parameter is not
    provided, the default value is set to `None`, which means the series will continue indefinitely
    unless the `n_elements
    :type stop: Optional[Union[Number, datetime]]
    :param n_elements: The `n_elements` parameter in the `generate_series` function specifies the number
    of elements to generate in the series. If this parameter is not provided, the function will generate
    elements until the stopping condition is met based on the `stop` parameter or other conditions
    :type n_elements: Optional[Number]
    :param step: The `step` parameter in the `generate_series` function determines the increment between
    consecutive elements in the generated series. It can be a numerical value (int, float, complex) or a
    datetime.timedelta object if the `start` parameter is a datetime object. If the `step` is not
    provided
    :type step: Optional[Union[Number, datetime]]
    :param included: The `included` parameter in the `generate_series` function determines whether the
    start or stop value should be included in the generated series. It can take one of three values:,
    defaults to left
    :type included: str (optional)
    """
    if isinstance(start, (int, float, complex)):
        if step is None:
            step = 1
        if stop is None:
            stop = inf
    elif isinstance(start, datetime):
        if step is None:
            step = timedelta(days=1)
        elif isinstance(step, (int, float, complex)):
            step = timedelta(days=step)
        if stop is None:
            stop = datetime(MAXYEAR, 12, 31, 23, 59, 59, 999999)
    if included == "left":
        value = start
        cmp = type(start).__lt__
    elif included == "right":
        value = start + step
        cmp = type(start).__le__
    elif included == "both":
        value = start
        cmp = type(start).__le__
    if n_elements is None:
        n_elements = inf

    i = 0
    while cmp(value, stop):
        yield value
        i += 1
        if i >= n_elements:
            break
        value += step

def coalesce(*args):
    for x in args:
        if x is not None:
            return x
    return x

def remove_sequence_of_duplicates(l):
    """
    The function removes consecutive duplicates from a list.
    
    :param l: The function `remove_sequence_of_duplicates` takes a list `l` as input and removes
    consecutive duplicates from the list. If the list is empty, it returns an empty list. Otherwise, it
    iterates through the list and appends elements to a new list `result` only if they are different
    :return: The function `remove_sequence_of_duplicates` takes a list `l` as input and removes
    consecutive duplicates from the list. It returns a new list with consecutive duplicates removed.
    """
    if len(l)==0:
        return []
    result = []  
    last_e = None
    for i,e in enumerate(l):
        if last_e is None:
            result.append(e)
            last_e = e
            continue
        if e != last_e:
            result.append(e)
        last_e = e        
    return result


BLACKLIST = type, ModuleType, FunctionType


def getsize(obj):
    """
    This function is designed to return the size of an object in Python.
    
    :param obj: The `getsize` function you provided seems to be incomplete. It looks like you were about
    to define a function that takes an object as a parameter. If you need help completing the function
    or have any specific requirements, feel free to ask!
    """
    """sum size of object & members."""
    if isinstance(obj, BLACKLIST):
        raise TypeError('getsize() does not take argument of type: '+ str(type(obj)))
    seen_ids = set()
    size = 0
    objects = [obj]
    while objects:
        need_referents = []
        for obj in objects:
            if not isinstance(obj, BLACKLIST) and id(obj) not in seen_ids:
                seen_ids.add(id(obj))
                size += sys.getsizeof(obj)
                need_referents.append(obj)
        objects = get_referents(*need_referents)
    return size


def interpolate_none_values(values, v0):
    # Sostituisci None iniziale e finale con v0
    if values[0] is None:
        values[0] = v0
    if values[-1] is None:
        values[-1] = v0

    # Interpolazione dei valori None
    i = 0
    while i < len(values):
        if values[i] is None:
            # Trova l'indice del prossimo valore non None
            j = i
            while j < len(values) and values[j] is None:
                j += 1

            if j < len(values):
                # Interpolazione lineare
                start_value = values[i - 1]
                end_value = values[j]
                step = (end_value - start_value) / (j - i + 1)
                for k in range(i, j):
                    values[k] = start_value + step * (k - i + 1)
            else:
                # Se tutti i restanti valori sono None, usa v0 come end_value
                end_value = v0
                step = (end_value - values[i - 1]) / (j - i + 1)
                for k in range(i, j):
                    values[k] = values[i - 1] + step * (k - i + 1)
            i = j
        else:
            i += 1
    return values

def run_in_thread(fn):
    def run(*k, **kw):
        t = threading.Thread(target=fn, args=k, kwargs=kw)
        t.start()
        return t

    return run

def min2hhmm(m):
    return "%s:%s" % (str(int(m / 60)).zfill(2), str(int(m % 60)).zfill(2))

def hhmm2min(timestr):
    if timestr is None:
        return None
    h1, m1 = timestr.split(":")
    return int(h1) * 60 + int(m1)

def min_from_midnight(date: Union[datetime, str], date_base: Optional[Union[datetime, str]]=None) -> Optional[int]:
    """
    Convert a time string in the format HH:MM to the number of minutes from midnight.
    
    :param timestr: A string representing time in the format "HH:MM".
    :return: The number of minutes from midnight as an integer.
    """
    date = to_datetime_auto(date)
    date_base = to_datetime_auto(date_base) if date_base else date.replace(hour=0, minute=0, second=0, microsecond=0)
    if date is None or date_base is None:
        return None
    return (date - date_base).total_seconds() // 60  # Restituisce i minuti come intero

# Formati noti data e orari
DATETIME_KNOWN_FORMATS = [
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y%m%d",
    "%Y-%m-%d %H:%M:%S",
    "%Y/%m/%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y/%m/%dT%H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y/%m/%d %H:%M",
    "%Y-%m-%dT%H:%M",
    "%Y/%m/%dT%H:%M",
    "%-H:%M",
    "%H:%M",
    "%H:%M:%S"
]

TIMEDELTA_KNOWN_FORMATS = [
    "%-H:%M",
    "%H:%M",
    "%H:%M:%S"
    "%H%M",
    "%H%M%S"
    "%H:%M.%f",
    "%H:%M:%S.%f"
    "%H%M.%f",
    "%H%M%S%f"
]

import psutil
import re
from typing import Optional, Union, Iterable
import warnings
import pytz

def to_datetime_auto(t: Union[str,int, float,datetime, time, date], 
                     date_default: date=None, 
                     time_default: time=None, 
                     on_error:str='ignore',
                     tz_localize: Optional[Union[str,tzinfo]] = None,
                     tz_convert: Optional[Union[str,tzinfo]] = None,
                     unit = "seconds") -> Optional[datetime]:
    """
    Convert a string, number, datetime, time, or date to a datetime object.
    :param t: The input value to convert, can be a string, number, datetime, time, or date.
    :param date_default: Default date to use if only time is provided (default is epoch date 1970-01-01).
    :param time_default: Default time to use if only date is provided (default is midnight 00:00:00).
    :param on_error: Action to take on error ('raise', 'warn', 'ignore').
    :param unit: Unit of the number if t is a number (default is "seconds").
    :return: A datetime object or None if conversion fails.
    """
    if date_default is None:
        date_default = datetime.fromtimestamp(0).date()  # Default to epoch date (1970-01-01)
    if time_default is None:
        time_default = datetime.fromtimestamp(0).time()  # Default to midnight (00:00:00)

    def refine(dt: datetime):    
        if dt is None:
            return None
        
        if tz_localize is not None:
            # if if naive
            if dt.tzinfo is None:
                if isinstance(tz_localize, str):
                    tz = pytz.timezone(tz_localize)
                else:
                    tz = tz_localize
                tz.localize(dt)
        if tz_convert is not None:
            if isinstance(tz_convert, str):
                tz = pytz.timezone(tz_convert)
            else:
                tz = tz_convert
            dt = dt.astimezone(tz)
        return dt
    if isinstance(t, str) and t.strip():
            t=t.strip()
            if t.isnumeric():
                _kwargs = {unit: float(t)}
                t = datetime.combine(date_default, time_default) + timedelta(**_kwargs)
            else:
                try:
                    # Prova con dateutil (include anche orari puri)
                    return refine(parser.parse(t, fuzzy=True, default=datetime.combine(date_default, time_default)))
                except (ValueError, OverflowError):
                    pass

                # Prova con formati espliciti
                for fmt in DATETIME_KNOWN_FORMATS:
                    try:
                        return refine(datetime.strptime(t, fmt))
                    except ValueError:
                        continue

                # Tentativo numerico compatto (solo data)
                digits = re.sub(r"[^\d]", "", t)
                if len(digits) == 8:
                    for fmt in ("%Y%m%d", "%d%m%Y", "%m%d%Y"):
                        try:
                            return refine(datetime.strptime(digits, fmt))
                        except ValueError:
                            continue
                if on_error:
                    if on_error == 'raise':
                        raise ValueError(f"Cannot parse date string: {t}")
                    elif on_error == 'warn':
                        warnings.warn(f"Cannot parse date string: {t}")
                    elif on_error == 'ignore':
                        return None
    elif isinstance(t, (int, float)):
        # Se è un numero, lo interpretiamo come timestamp (secondi dall'epoca)
        _kwargs = {unit: float(t)}
        return refine(datetime.combine(date_default, time_default) + timedelta(**_kwargs))
    elif isinstance(t, datetime):
        return refine(t)
    elif isinstance(t, date):
        # Se è una data, la combiniamo con l'orario predefinito
        return refine(datetime.combine(t, time_default))
    elif isinstance(t, time):
        # Se è un orario, lo combiniamo con la data predefinita
        return refine(datetime.combine(date_default, t))
    if on_error == 'raise':
        raise ValueError("Cannot parse {t} as a date")
    elif on_error == 'warn':
        warnings.warn("Cannot parse {t} as a date")
        return None
    elif on_error == 'ignore': 
        return None
        
def to_timedelta_auto(t: Union[str,int, float,datetime, time, date], unit='seconds', on_error='raise', 
                        base_date: Optional[datetime] = None) -> Optional[timedelta]:
    """
    Convert a string, number, datetime, time, or date to a timedelta object.
    :param t: The input value to convert, can be a string, number, datetime, time, or date.
    :param unit: Unit of the number if t is a number (default is "seconds").
    :param on_error: Action to take on error ('raise', 'warn', 'ignore').
    :param base_date: Base date to use for timedelta calculation (default is epoch date 1970-01-01).
    :return: A timedelta object or None if conversion fails.
    """
    if isinstance(t, str) and t.strip():
        t = t.strip()
        if t.isnumeric():
            _kwargs = {unit: float(t)}
            return timedelta(**_kwargs)
        else:
            parts = t.split('.')    
            if len(parts) >= 2:
                days = int(parts[0])
                time_part = '.'.join(parts[1:])
            else:
                days = 0
                time_part = parts[0]

            # Prova con formati espliciti
            for fmt in TIMEDELTA_KNOWN_FORMATS:
                try:
                    dt= datetime.strptime(time_part, fmt)
                    return timedelta(days=days, hours=dt.hour, minutes=dt.minute, seconds=dt.second, microseconds=dt.microsecond)
                except ValueError:
                    continue
    elif isinstance(t, (int, float)):
        # Se è un numero, lo interpretiamo come secondi
        _kwargs = {unit: float(t)}
        return timedelta(**_kwargs)
    elif isinstance(t, timedelta):
        return t
    elif isinstance(t, datetime):
        if base_date is None:
            return t - datetime.fromtimestamp(0)
        else:
            if not isinstance(base_date, datetime):
                base_date = to_datetime_auto(base_date, 
                                             date_default=datetime.fromtimestamp(0).date(), 
                                             time_default=datetime.fromtimestamp(0).time())            
            return t - base_date
    elif isinstance(t, date):
        if base_date is None:
            base_date = datetime.fromtimestamp(0).date()
        else:
            if not isinstance(base_date, date):
                base_date = to_datetime_auto(base_date, 
                                             date_default=datetime.fromtimestamp(0).date(), 
                                             time_default=datetime.fromtimestamp(0).time()).date()
        return timedelta(days=(t - base_date).days)
    elif isinstance(t, time):
        if base_date is None:
            base_date = datetime.fromtimestamp(0).time()
        else:
            if not isinstance(base_date, time):
                base_date = to_datetime_auto(base_date, 
                                             date_default=datetime.fromtimestamp(0).date(), 
                                             time_default=datetime.fromtimestamp(0).time()).time()
        return timedelta(hours=t.hour - base_date.hour, minutes=t.minute - base_date.minute, seconds=t.second - base_date.second, microseconds=t.microsecond - base_date.microsecond)
       
        
    

def memory_usage(
    process_filter: Optional[Union[Iterable[Union[str, int]], int, str]] = ["python", "ray", "dask"],
    recursive=True
) -> float:
    """
    Calcola la memoria totale usata dai processi filtrati per nome (con regex) e/o PID.

    :param process_filter: Lista di nomi (regex) o PID di processo da cercare (None per ignorare il filtro).
    :param recursive: Se True, include la memoria dei processi figli.
    :return: Memoria totale utilizzata dai processi filtrati (in MB).
    """
    total_mem = 0  # Memoria totale in MB

    # Normalizza i parametri (None diventa una lista vuota)
    if isinstance(process_filter, (str, bytes, int)):
        process_filter = [process_filter]
    
    process_names = [name.lower() for name in process_filter if isinstance(name, str)]
    pids = set(pid for pid in process_filter if isinstance(pid, int))

    tot_pids = set()
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            process_name = proc.info['name']
            pid = proc.info['pid']

            # Controlla se il processo soddisfa almeno uno dei filtri
            matches_name = (
                any(re.search(pattern, process_name.lower()) for pattern in process_names)
                if process_name and process_names
                else False
            )
            matches_pid = pid in pids if pids else False

            if matches_name or matches_pid:
                try:
                    process = psutil.Process(pid)
                    tot_pids.add(pid)
                # Memoria del processo principale
                
                    # Memoria dei processi figli
                    if recursive:
                        children = process.children(recursive=True)
                        for child in children:
                            try:
                                tot_pids.add(child.pid)
                            except psutil.NoSuchProcess:
                                continue
                except psutil.NoSuchProcess:
                    continue
            
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            # Ignora processi non accessibili o che sono terminati
            continue

    for pid in tot_pids:
        try: 
            process = psutil.Process(pid)
            total_mem += process.memory_info().rss / (1024 ** 2)  # Memoria in MB

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            # Ignora processi non accessibili o che sono terminati
            continue

    return total_mem

def fast_memory_usage(recursive=True, pid=None):
    pid = pid or getpid()
    process = Process(pid)

    # Uso della memoria del processo principale
    mem = process.memory_info().rss / (1024 ** 2)  # Memoria in MB
    # Uso della memoria dei processi figli
    if recursive:
        children = process.children(recursive=True)
        for child in children:
            try:
                mem += child.memory_info().rss / (1024 ** 2)  # Memoria in MB            
            except NoSuchProcess:
                # Ignora il processo figlio se non esiste più
                continue
    return mem

def dataframe_to_markdown(df):
    # Estrarre le colonne
    headers = "| " + " | ".join(df.columns) + " |"
    separator = "| " + " | ".join(['---'] * len(df.columns)) + " |"
    rows = [f"| {' | '.join(map(str, row))} |" for row in df.values]

    # Unire tutto
    markdown_table = "\n".join([headers, separator] + rows)
    return markdown_table


def print_loaded_modules():

    # Ottieni la lista dei pacchetti della libreria standard di Python
    standard_modules = {module.name for module in pkgutil.iter_modules()}

    # Ottieni i moduli effettivamente caricati durante l'esecuzione
    loaded_modules = set(sys.modules.keys())

    # Ottieni solo i pacchetti che non fanno parte della libreria standard di Python
    custom_loaded_modules = loaded_modules - standard_modules

    # Filtra ulteriormente per escludere i moduli built-in (che iniziano con "_")
    custom_loaded_modules = {mod for mod in custom_loaded_modules if not mod.startswith("_")}

    # Stampa i pacchetti caricati che non sono standard
    for package in sorted(custom_loaded_modules):
        print(package)

def export_dataframe(df, file_path, mode="w", **kwargs):
    """
    Exports a DataFrame to a file with the format determined by the extension.
    
    Parameters:
        df (pd.DataFrame): The DataFrame to export.
        file_path (str): The path to the file, including the name and extension (for example, 'data.csv').
        **kwargs: Additional parameters for export methods (e.g. sep for to_csv).
    
    Raises:
        ValueError: If the extension is not supported.
    """
    # Determina l'estensione del file
    #file_path = file_path.lower()
    extension = file_path.split('.')[-1]#.lower()
    extension = f".{extension}"  # Aggiunge il punto

    append = mode == "a" 
    index = kwargs.pop("index", False)
    

    not_appendable = False
    if append and extension.lower() in (".excel", ".xls", ".xlsx"):
        logging.error("Append mode is not supported for Excel files.")
        not_appendable = True
    if append and extension.lower() in (".html"):
        logging.error("Append mode is not supported for HTML files.")
        not_appendable = True

    if append and extension.lower() in (".feather"):
        logging.error("Append mode is not supported for Feather files.")
        not_appendable = True
    if append and extension.lower() in (".pickle"):
        logging.error("Append mode is not supported for Feather files.")
        not_appendable = True        
    if not_appendable:
        i=1
        while True:
            new_file_path = file_path.replace(extension,f"_{i}{extension}")
            if not os.path.exists(file_path):
                file_path = new_file_path
                break

    partition_cols=kwargs.pop("partition_cols", None)

    def to_parquet(df, base_dir, partition_cols=None, append=False, index=None):
        import pyarrow as pa
        import pyarrow.dataset as ds

        table = pa.Table.from_pandas(df, preserve_index=index)
        # genrete unuique name for the partition
        uid = str(int(datetime.now().timestamp())) + "_" + str(uuid4()) + "_" + str(getpid())+"_{i}" + extension
        existing_data_behavior = "delete_matching" if not append else "overwrite_or_ignore"
        schema = pa.Schema.from_pandas(df[partition_cols], preserve_index=index) if partition_cols else None
        ds.write_dataset(
            table,
            base_dir=base_dir,
            format="parquet",
            basename_template=uid,
            partitioning=ds.partitioning(schema = schema, flavor="hive") if partition_cols else None,
            existing_data_behavior=existing_data_behavior
        )


    def to_geoparquet(df, base_dir, partition_cols=None, append=False, index=False, crs=None):
        import pyarrow as pa
        import pyarrow.dataset as ds
        import pandas as pd
        """
        df.to_parquet(base_dir,
                       engine="auto",
                       index=index, 
                       partition_cols=partition_cols, 
                       dataset=True,
                       append=append, **kwargs)"""

        # Salva metadato CRS se specificato
        df = df.copy()
        warnings.filterwarnings("ignore", category=UserWarning, module="geopandas")
        s = df.geometry.apply(lambda geom: geom.wkb if geom else None)   
        df = pd.DataFrame(df.drop(columns=["geometry"]))     
        df.loc[:, "geometry"] = s
        warnings.filterwarnings("default", category=UserWarning, module="geopandas")        
        table = pa.Table.from_pandas(df, preserve_index=index)

        existing_data_behavior = "delete_matching" if not append else "overwrite_or_ignore"
        uid = str(int(datetime.now().timestamp())) + "_" + str(uuid4()) + "_" + str(getpid())+"_{i}" + extension
        schema = pa.Schema.from_pandas(df[partition_cols], preserve_index=index) if partition_cols else None
        ds.write_dataset(
            table,
            base_dir=base_dir,
            format="parquet",
            basename_template=uid,
            partitioning=ds.partitioning(schema = schema, flavor="hive") if partition_cols else None,
            existing_data_behavior=existing_data_behavior
        )

        if crs:
            import json, os
            metadata_path = os.path.join(base_dir, "_metadata_crs.json")
            with open(metadata_path, "w") as f:
                json.dump({"crs": crs}, f)

    # Mappa estensioni a metodi di esportazione
    export_methods_gpd = {
        '.shp': lambda df, x,**kwargs: df.to_file(x, index=index, mode=mode)  if hasattr(df,"to_file") else None,
        '.parquet': lambda df, x,**kwargs: to_geoparquet(df, x, partition_cols=partition_cols, append=append, index=index),
        '.geoparquet': lambda df, x,**kwargs: to_geoparquet(df, x, partition_cols=partition_cols, append=append, index=index),
        '.gpkg': lambda df, x,**kwargs: df.to_file(x, driver="GPKG", layer=kwargs.get("layer",os.path.basename(x)), index=index, mode=mode) if hasattr(df,"to_file") else None,        
    }
    

    export_methods_pd= {
        '.csv': lambda df, x,**kwargs: df.to_csv(x,mode=mode, index=index) if hasattr(df,"to_csv") else None,
        '.excel': lambda df, x,**kwargs: df.to_excel(x, index=index) if hasattr(df,"to_excel") else None,
        '.xls': lambda df, x,**kwargs: df.to_excel(x, index=index) if hasattr(df,"to_excel") else None,
        '.xlsx': lambda df, x,**kwargs: df.to_excel(x, index=index) if hasattr(df,"to_excel") else None,
        '.parquet': lambda df, x,**kwargs: to_parquet(df, x, partition_cols=partition_cols, append=append, index=index),
        '.json': lambda df, x,**kwargs: df.to_json(x, mode=mode) if hasattr(df,"to_json") else None,
        '.html': lambda df, x,**kwargs: df.to_html(x, index=index, **kwargs) if hasattr(df,"to_html") else None,
        '.feather': lambda df, x,**kwargs: df.to_feather(x, index=index, **kwargs) if hasattr(df,"to_feather") else None,
        '.pickle': lambda df, x, **kwargs: x.to_pickle if hasattr(df,"to_pickle") else None,
    }

    try:
        import geopandas as gpd
        if extension in export_methods_gpd and "geometry" in df.columns:
            crs = kwargs.pop("crs", None)
            if crs is not None:
                df = df.to_crs(crs, inplace=True)
            export_methods_gpd[extension](df, file_path, **kwargs)
            return True
    except:
        pass

    import pandas as pd
    if extension in export_methods_pd:            
        if isinstance(df, dict):
            df = pd.DataFrame(df)
        try:
            if isinstance(df, gpd.GeoDataFrame):
                crs = kwargs.pop("crs", None)
                if crs is not None:
                    df.to_crs(crs, inplace=True)
                df = pd.DataFrame(df.to_wkt())
        except:
            pass
        if isinstance(df, pd.DataFrame):
            export_methods_pd[extension](df, file_path, **kwargs)
            return True

    
    export_methods_pd['.csv'](df, file_path+".csv", **kwargs)
    return False

def inner_filter_to_query_expression(filters, rename=None, quoting='"',  op_boolean_symbols=False):
    expressions = []
    if isinstance(filters, (tuple,list)): 
        if len(filters) == 3 and isinstance(filters[0], str) and isinstance(filters[1], str):
            column, operator, value = filters            
            if isinstance(value, str):
                value = f"'{value}'"                
            expressions.append(f"({quoting}{column}{quoting} {operator} {value})")
        else:
            for filter in filters:
                if len(filter) == 3 and isinstance(filter[0], str) and isinstance(filter[1], str):
                    column, operator, value = filter
                    if isinstance(value, str):
                        value = f"'{value}'"
                    expressions.append(f"({quoting}{column}{quoting} {operator} {value})")
                else:
                    raise ValueError("Invalid filter format. The inner filter must be a list of tuple with 3 elements (column,operator,value).")
    else:
        raise ValueError("Invalid filter format. The inner filter must be a tuple with 3 elements (column,operator,value).")
    if op_boolean_symbols:
        return " | ".join(expressions)
    else:
        return " OR ".join(expressions)
    
def filters_to_query_expression(filters, quoting='"',  op_boolean_symbols=False):
    if isinstance(filters, str):
        return filters
    # Altrimenti, filters è una lista di gruppi, e bisogna trattarla ricorsivamente
    group_expressions = []
    
    for group in filters:
        group_expressions.append(inner_filter_to_query_expression(group, quoting=quoting, op_boolean_symbols=op_boolean_symbols))  # Chiamata ricorsiva per gestire gruppi e tuple

    # Unisci i gruppi con 'or'
    if op_boolean_symbols:
        return ' & '.join(group_expressions)
    else:
        return ' AND '.join(group_expressions)

def rename_filters(filters, rename):
    for i, group in enumerate(filters):
        if isinstance(group, (tuple,list)) and len(group)>0:
            if isinstance(group[0], str):                
                column, operator, value = group
                if column in rename:
                    filters[i] = (rename[column], operator, value)
            else:
                filters[i] = rename_filters(group, rename)                
        else:
            raise ValueError("Invalid filter format. The inner filter must be a list of tuple with 3 elements (column,operator,value).")
    return filters
    
def import_dataframe(file_path, filters=None, dtype={}, driver=None,**kwargs):    
    if os.path.exists(file_path) is False:
        raise FileNotFoundError(f"File {file_path} does not exist.")
    where = None
    # Determina l'estensione del file
    if driver is not None:
        extension = driver
        if not extension.startswith("."):
            extension = f".{extension}"
    else:
        extension = file_path.split('.')[-1].lower()
        extension = f".{extension}"  # Aggiunge il punto

    if filters is not None:
        if isinstance(filters, str):
            where = filters
            filters = None
        elif isinstance(filters, (tuple,list)):
            if extension not in ("parquet","geoparquet"):
                where = filters_to_query_expression(filters, quoting="", op_boolean_symbols=True) 
    import_methods_pd = {}
    import_methods_gpd = {}
    try:
        import pandas
        import_methods_pd.update({
            '.csv': lambda x: pandas.read_csv(x),
            '.excel': lambda x: pandas.read_excel(x),
            '.xls': lambda x: pandas.read_excel(x),
            '.xlsx': lambda x: pandas.read_excel(x),
            '.parquet': lambda x: pandas.read_parquet(x, filters=filters),
            '.json': lambda x: pandas.read_json(x),
            '.html': lambda x: pandas.read_html(x),
            '.feather': lambda x: pandas.read_feather(x),
            '.pickle': lambda x: pandas.read_pickle(x),
        })
    except:
        pass
    try:
        import geopandas
        import_methods_gpd.update({
            '.shp': lambda x: geopandas.read_file(x),
            '.gpkg': lambda x: geopandas.read_file(x, driver="GPKG", layer=geopandas.list_layers(x)["name"].iloc[0]),
            '.geoparquet': lambda x: geopandas.read_parquet(x, filters=filters),
        })
    except:
        pass
        

    
  
    # Cerca il metodo corrispondente
    if extension in import_methods_pd:
        df = import_methods_pd[extension](file_path, **kwargs) 
    elif extension in import_methods_gpd:
        df = import_methods_gpd[extension](file_path, **kwargs) 
    else:
        df = import_methods_pd['.csv'](file_path, **kwargs)

    if dtype:
        dtype = {k: v for k, v in dtype.items() if k in df.columns}
        df = df.astype(dtype, copy=True)       
    if where:
        df = df.query(where)
    return df


def generate_sqlalchemy_url(db_host=None, db_port=None, db_user=None, db_password=None, db_name=None, db_type='sqlite', db_driver=None, query=None):
    if db_driver:
        db_type = f'{db_type}+{db_driver}'
    
    if db_port:
        port_part = f':{db_port}'
    else:
        port_part = ''
    
    if db_user:
        if db_password:
            user_part = f'{db_user}:{db_password}@'
        else:
            user_part = f'{db_user}@'
    else:
        user_part = ''
    
    if db_host:
        host_part = f'{db_host}'
    else:
        host_part = ''
    
    if query:
        query_part = '?' + urlencode(query)
    else:
        query_part = ''
    return f'{db_type}://{user_part}{host_part}{port_part}/{db_name}{query_part}'


def parse_sqlalchemy_url(url):
    result = urlparse(url)
    components = {
        'db_type': result.scheme.split('+')[0] if '+' in result.scheme else result.scheme,
        'db_driver': result.scheme.split('+')[1] if '+' in result.scheme else None,
        'db_user': result.username,
        'db_password': result.password,
        'db_host': result.hostname,
        'db_port': result.port,
        'db_name': result.path.lstrip('/'),
        'query': parse_qs(result.query)
    }
    return components

def generate_postgres_dns(db_host=None, db_port=None, db_user=None, db_password=None, db_name=None, **kwargs):
    return f'host={db_host} port={db_port} dbname={db_name} user={db_user} password={db_password}'

def parse_postgres_dns(dns):
    components = {}
    for part in dns.split(' '):
        key, value = part.split('=')
        components[key.strip()] = value.strip()
    components['db_type'] = 'postgresql'
    components['db_driver'] = "psycopg"
    components['db_name'] = components['dbname']
    components.pop('dbname')
    components["db_host"] = components["host"]  
    components.pop("host")
    components["db_port"] = components["port"]
    components.pop("port")
    components["db_user"] = components["user"]
    components.pop("user")
    components["db_password"] = components["password"]
    components.pop("password")
    components["query"] = {}
    
    return components

def remove_path(path):
    if os.path.exists(path):            
        path = Path(path)
        if path.is_file():
            path.unlink() # Rimuove un file
        else:
            shutil.rmtree(path)

def to_namedtuple(dict_obj):
    import json
    from collections import namedtuple
    return json.loads(json.dumps(dict_obj), object_hook=lambda d: namedtuple("X", d.keys())(*d.values()) if isinstance(d, dict) else d)        


from string import Formatter
def get_parametric_name(name, **kwargs):
    if isinstance(name, str):
        keys=[i[1] for i in Formatter().parse(name)  if i[1] is not None and i[1] not in kwargs]
        #print(keys)
        if keys:
            kwargs=kwargs.copy()
            for k in keys:
                kwargs[k]="{"+k+"}"            
        new_name=None
        while True:
            new_name = name.format(**kwargs)
            if name==new_name:
                break
            name=new_name
    elif isinstance(name, dict):
        name = {k: get_parametric_name(v, **kwargs) for k, v in name.items()}
    elif isinstance(name, list):
        name = [get_parametric_name(n, **kwargs) for n in name]
    elif isinstance(name, tuple):
        name = tuple(get_parametric_name(n, **kwargs) for n in name)
    elif isinstance(name, set):
        name = {get_parametric_name(n, **kwargs) for n in name}
    return name

def ravel_dict(d, parent_key='', sep='_'):
    """
    Flatten a nested dictionary into a single-level dictionary with concatenated keys.
    
    :param d: The dictionary to flatten.
    :param parent_key: The base key to use for the flattened keys.
    :param sep: The separator to use between concatenated keys.
    :return: A flattened dictionary.
    """
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(ravel_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)

def nested_dict_from_key_value_list(pairs):
    """
    Convert a list of key-value pairs into a nested dictionary.
        data = [
        ("a", 1),
        ("b:c", 2),
        ("b:d", 3),
        ("e:f:g", 4)
    ]

    output = nested_dict_from_key_value_list(data)

    print(output)
    {
        'a': 1,
        'b': {
            'c': 2,
            'd': 3
        },
        'e': {
            'f': {
                'g': 4
            }
        }
    }

    """
    result = {}
    for key, value in pairs.items():
        parts = key.split(":")
        current = result
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        current[parts[-1]] = value
    return result

def deep_update(d, u):
    """
    Update a dictionary recursively with another dictionary.
    if a key in the second dictionary is a dictionary itself, it will merge it with the corresponding key in the first dictionary.
    If the key is not present in the first dictionary, it will be added.
    :param d: The original dictionary to update.
    :param u: The dictionary with updates.
    :return: The updated dictionary.
    """
    if not isinstance(d, dict) or not isinstance(u, dict):
        raise ValueError("Both arguments must be dictionaries.")
    if u is None or len(u) == 0:
        return d
    for k, v in u.items():
        if isinstance(v, dict) and isinstance(d.get(k), dict):
            deep_update(d[k], v)
        else:
            d[k] = v

def pd_concat(df_list, ignore_index=True, sort=False, **kwargs):
    import pandas as pd
    import numpy as np
    def get_extended_dtype(dtype):
        """
        Mappa i dtype numpy standard nei corrispettivi pandas estesi.
        """
        if np.issubdtype(dtype, np.integer):
            return "Int64"
        elif np.issubdtype(dtype, np.floating):
            return "Float64"
        elif np.issubdtype(dtype, np.bool_):
            return "boolean"
        elif np.issubdtype(dtype, np.object_):
            return "string"
        else:
            return "object"
    dfs = [df for df in df_list if df is not None]
    if not dfs:
        return None

    non_empty = [df for df in dfs if not df.empty]
    empty = [df for df in dfs if df.empty]

    if not non_empty:
        return empty[0].copy() if empty else None

    all_cols = []
    for df in non_empty:
        for col in df.columns:
            if col not in all_cols:
                all_cols.append(col)
    resolved_dtypes = {}

    for col in all_cols:
        candidate_types = []
        for df in non_empty:
            if col in df.columns:
                series = df[col]
                if series.notna().any():
                    try:
                        candidate_types.append(series.dropna().iloc[0])
                    except IndexError:
                        pass

        if candidate_types:
            result_dtype = np.result_type(*[type(val) for val in candidate_types])
            resolved_dtypes[col] = get_extended_dtype(result_dtype)
        else:
            resolved_dtypes[col] = "string"

    casted = []
    for df in non_empty:
        df = df.copy()
        for col in set(all_cols) - set(df.columns):
            df[col] = pd.NA
        df = df[list(all_cols)]

        for col in df.columns:
            try:
                df[col] = df[col].astype(resolved_dtypes[col], copy=False)
            except Exception:
                df[col] = df[col].astype("string")
        casted.append(df)

    return pd.concat(casted, ignore_index=ignore_index, sort=sort, **kwargs)

def file_ordered_list(cartella, estensioni=None, reverse=False):
    p = Path(cartella)
    files = [
        f for f in p.rglob('*')
        if f.is_file() and (estensioni is None or f.suffix.lower() in estensioni)
    ]
    return sorted(files, key=lambda x: x.stat().st_mtime, reverse=reverse)