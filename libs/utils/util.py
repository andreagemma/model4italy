import ast
from typing import Union, Optional, List, Generator, Tuple, Any, Callable, Iterable
from numbers import Number
from uuid import uuid4
import re
import re
from math import ceil, inf
from datetime import datetime, timedelta, MAXYEAR
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


def save_dict(data: dict, file_name: str, compression=None) -> None:
    """
    Save a dictionary in a pickle file name
    :param data: data to save
    :param file_name: file name
    :return: None
    """
    if compression == "gzip":
        import gzip

        with gzip.open(file_name, "wb") as f:
            pickle.dump(data, f, pickle.HIGHEST_PROTOCOL)
        return
    elif compression == "bz2":
        import bz2

        with bz2.BZ2File(file_name, "wb") as f:
            pickle.dump(data, f, pickle.HIGHEST_PROTOCOL)
        return
    elif compression == "zip":
        import zipfile

        with zipfile.ZipFile(file_name, "w") as zf:
            zf.writestr(file_name, pickle.dumps(data, pickle.HIGHEST_PROTOCOL))
        return
    elif compression == "lzma":
        import lzma

        with lzma.open(file_name, "wb") as f:
            pickle.dump(data, f, pickle.HIGHEST_PROTOCOL)
        return
    else:
        with open(file_name, "wb") as f:
            pickle.dump(data, f, pickle.HIGHEST_PROTOCOL)


def load_dict(file_name: str, compression=None) -> dict:
    """
    Load dictionary from a file name
    :param file_name:
    :return:
    """
    if compression == "gzip":
        import gzip

        with gzip.open(file_name, "rb") as f:
            return pickle.load(f)
    elif compression == "bz2":
        import bz2

        with bz2.BZ2File(file_name, "rb") as f:
            return pickle.load(f)
    elif compression == "zip":
        import zipfile

        with zipfile.ZipFile(file_name, "r") as zf:
            with zf.open(file_name) as f:
                return pickle.loads(f.read())
    elif compression == "lzma":
        import lzma

        with lzma.open(file_name, "rb") as f:
            return pickle.load(f)
    else:
        with open(file_name, "rb") as f:
            return pickle.load(f)


def create_unique_name(prefix: Optional[str] = None) -> str:
    return ("T" if prefix is None else prefix) + str(
        "".join([str(x) for x in uuid4().fields])
    )


def json_serialize(obj: Any, file_name: str):
    import jsonpickle
    f = open(file_name, "w")
    json_obj = jsonpickle.encode(obj, make_refs=False)
    f.write(json_obj)
    f.close()


def json_load_file(file_name: str):
    import jsonpickle
    f = open(file_name)
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
    return "%s:%s" % (str(int(m / 60)).zfill(2), str(m % 60).zfill(2))

def hhmm2min(timestr):
    h1, m1 = timestr.split(":")
    return int(h1) * 60 + int(m1)



import psutil
import re
from typing import Optional, Union, Iterable


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
    file_path = file_path.lower()
    extension = file_path.split('.')[-1].lower()
    extension = f".{extension}"  # Aggiunge il punto

    append = mode == "a" 
    index = kwargs.pop("index", False)
    

    not_appendable = False
    if append and extension in (".excel", ".xls", ".xlsx"):
        logging.error("Append mode is not supported for Excel files.")
        not_appendable = True
    if append and extension in (".html"):
        logging.error("Append mode is not supported for HTML files.")
        not_appendable = True

    if append and extension in (".feather"):
        logging.error("Append mode is not supported for Feather files.")
        not_appendable = True
    if append and extension in (".pickle"):
        logging.error("Append mode is not supported for Feather files.")
        not_appendable = True        
    if not_appendable:
        i=1
        while True:
            new_file_path = file_path.replace(extension,f"_{i}{extension}")
            if not os.path.exists(file_path):
                file_path = new_file_path
                break

    
    # Mappa estensioni a metodi di esportazione
    export_methods_gpd = {
        '.shp': lambda x: df.to_file(x, index=index, mode=mode)  if hasattr(df,"to_file") else None,
        '.parquet': lambda x: df.to_parquet(x, index=index) if hasattr(df,"to_parquet") else None,
        '.geoparquet': lambda x: df.to_parquet(x, index=index) if hasattr(df,"to_parquet") else None,        
        '.gpkg': lambda x: df.to_file(x, driver="GPKG", layer=os.path.basename(x), index=index, mode=mode) if hasattr(df,"to_file") else None,        
    }
    

    export_methods_pd= {
        '.csv': lambda x: df.to_csv(x,mode=mode, index=index) if hasattr(df,"to_csv") else None,
        '.excel': lambda x: df.to_excel(x, index=index) if hasattr(df,"to_excel") else None,
        '.xls': lambda x: df.to_excel(x, index=index) if hasattr(df,"to_excel") else None,
        '.xlsx': lambda x: df.to_excel(x, index=index) if hasattr(df,"to_excel") else None,
        '.parquet': lambda x: df.to_parquet(x, engine="fastparquet", append=append, index=index) if hasattr(df,"to_parquet") else None,
        '.json': lambda x: df.to_json(x, mode=mode) if hasattr(df,"to_json") else None,
        '.html': lambda x: df.to_html(x, index=index, **kwargs) if hasattr(df,"to_html") else None,
        '.feather': lambda x: df.to_feather(x, index=index, **kwargs) if hasattr(df,"to_feather") else None,
        '.pickle': df.to_pickle if hasattr(df,"to_pickle") else None,
    }

    try:
        import geopandas as gpd
        if extension in export_methods_gpd and "geometry" in df.columns:
            export_methods_gpd[extension](file_path, **kwargs)
            return True
    except:
        pass

    import pandas as pd
    if extension in export_methods_pd:            
        if isinstance(df, dict):
            df = pd.DataFrame(df)
        try:
            if isinstance(df, gpd.GeoDataFrame):
                df = pd.DataFrame(df.to_wkt())
        except:
            pass
        if isinstance(df, pd.DataFrame):
            export_methods_pd[extension](file_path, **kwargs)
            return True

    
    export_methods_pd['.csv'](file_path+".csv", **kwargs)
    return False

def inner_filter_to_query_expression(filters):
    expressions = []
    if isinstance(filters, (tuple,list)): 
        if len(filters) == 3 and isinstance(filters[0], str) and isinstance(filters[1], str):
            column, operator, value = filters
            expressions.append(f"({column} {operator} {value})")
        else:
            for filter in filters:
                if len(filter) == 3 and isinstance(filter[0], str) and isinstance(filter[1], str):
                    column, operator, value = filter
                    expressions.append(f"({column} {operator} {value})")
                else:
                    raise ValueError("Invalid filter format. The inner filter must be a list of tuple with 3 elements (column,operator,value).")
    else:
        raise ValueError("Invalid filter format. The inner filter must be a tuple with 3 elements (column,operator,value).")
    return " and ".join(expressions)
    
def filters_to_query_expression(filters):
    # Altrimenti, filters è una lista di gruppi, e bisogna trattarla ricorsivamente
    group_expressions = []
    
    for group in filters:
        group_expressions.append(inner_filter_to_query_expression(group))  # Chiamata ricorsiva per gestire gruppi e tuple

    # Unisci i gruppi con 'or'
    return ' or '.join(group_expressions)


def import_dataframe(file_path, filters=None, dtype={}, **kwargs):
    import_methods = {}
    where = None

    try:
        import pandas
        import_methods.update({
            '.csv': lambda x: pandas.read_csv(x, dtype=dtype),
            '.excel': lambda x: pandas.read_excel(x, dtype=dtype),
            '.xls': lambda x: pandas.read_excel(x, dtype=dtype),
            '.xlsx': lambda x: pandas.read_excel(x, dtype=dtype),
            '.parquet': lambda x: pandas.read_parquet(x, filters=filters),
            '.json': lambda x: pandas.read_json(x, dtype=dtype),
            '.html': lambda x: pandas.read_html(x),
            '.feather': lambda x: pandas.read_feather(x),
            '.pickle': lambda x: pandas.read_pickle(x),
        })
    except:
        pass
    try:
        import geopandas
        import_methods.update({
            '.shp': lambda x: geopandas.read_file(x),
            '.gpkg': lambda x: geopandas.read_file(x, driver="GPKG", layer=geopandas.list_layers(x)["name"].iloc[0]),
            '.geoparquet': lambda x: geopandas.read_parquet(x, filters=filters),
        })
    except:
        pass
        
    # Determina l'estensione del file
    extension = file_path.split('.')[-1].lower()
    extension = f".{extension}"  # Aggiunge il punto
    
    if filters is not None and extension not in ("parquet","geoparquet"):
        where = filters_to_query_expression(filters)   
    # Cerca il metodo corrispondente
    if extension in import_methods:
        df = import_methods[extension](file_path, **kwargs) 
        if dtype:
            df = df.astype(dtype, copy=False)       
        if where:
            df = df.query(where)
        return df
    else:
        df = import_methods['.csv'](file_path, **kwargs)
        if dtype:
            df.astype(dtype, copy=False)
        if where is not None:
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