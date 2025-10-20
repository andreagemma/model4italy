import duckdb
import pandas as pd
import geopandas as gpd
from pathlib import Path
import numpy as np
from shapely.geometry import Point
from shapely import from_wkb, to_wkt, from_wkt
import shutil
import os
import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds
from pyarrow.parquet import write_to_dataset
import pyarrow.parquet as pq
import polars as pl 
import json

from typing import Optional, Union, List, Tuple, Sequence, Callable
import warnings

from ... import remove_path
from . import BaseDriver, filters_to_query_expression
from ...util import pandas_query_to_sql, sql_where_to_pandas
import warnings

class FileDriver(BaseDriver):

    @classmethod
    def name(cls) -> str:
        return "file"

    @classmethod
    def pattern(cls) -> List[str]:
        return [
            r"\.shp$",
            r"\.gpkg$",
            r"\.geoparquet$",
            r"\.csv$",
            r"\.xlsx?$",
            r"\.parquet$",
            r"\.feather$",
        ]

    def import_dataframe(
        self,
        path: str,
        filters: Optional[dict] = None,
        dtype: Optional[dict] = None,
        **kwargs
    ) -> pd.DataFrame:
        crs = kwargs.pop("crs", None)
        pathg: Path = Path(path)
        df = None
        ext = pathg.suffix.lower()
        #print(f"Load: {pathg.as_posix()}")
        if filters:
            #print(f"Filters: {filters}")
            if isinstance(filters, str):
                df_filters = filters
            else:
                df_filters = filters_to_query_expression(filters,quoting='', op_boolean_symbols=True)
            sql_filters = pandas_query_to_sql(df_filters)
                                    
        else:
            filters = ''
            df_filters = ''
            sql_filters = ''
        if ext in (".csv",):
            if pathg.is_file():
                #print("Uso Polars")
                if filter:
                    df = pl.scan_csv(pathg.as_posix()).sql(f"select * from self {sql_filters}").collect().to_pandas()
                else:
                    df = pl.scan_csv(pathg.as_posix()).collect().to_pandas()         
            else:
                #print("Uso DuckDB")
                con = duckdb.connect()
                query = f"SELECT * FROM '{pathg.as_posix()}' {sql_filters}"
                df = con.execute(query).df()            
        elif ext in (".parquet",):
            if sql_filters == '':
                #print("Uso Pandas")
                df = pd.read_parquet(pathg)
            else:
                #print("Uso DuckDB")
                con = duckdb.connect()
                query = f"SELECT * FROM '{pathg.as_posix()}' {sql_filters}"
                df = con.execute(query).df()            
        elif ext in (".geoparquet",):
            if sql_filters == '' and pathg.is_file():
                #print("Uso GeoPandas")
                df = gpd.read_parquet(pathg)
            else:
                #print("Uso DuckDB")
                con = duckdb.connect()
                query = f"SELECT * FROM parquet_scan('{pathg.as_posix()}') {sql_filters}"
                #print(query)
                df = con.execute(query).df() 
                geom = from_wkb(df.pop("geometry").apply(bytes))
                df = gpd.GeoDataFrame(df,geoemtry=geom, crs=crs) if crs else gpd.GeoDataFrame(df,geometry=geom)
        elif ext in (".shp",".gpkg"):
            if pathg.is_file():
                layer = kwargs.pop("layer", None)
                df = gpd.read_file(pathg.as_posix(), layer=layer)
            else:
                files = pathg.glob(os.path.join("*","*"+pathg.suffix))
                df = None
                for f in files:
                    tmp = gpd.read_file(f) 
                    if tmp is None:
                        warnings.warn(f"File {f} not valid")
                    df = tmp if df is None else pd.concat([df,tmp])   
            if df_filters and df is not None:
                df = df.query(df_filters)
        else:
            warnings.warn("Formato file non supportato")
            return None
        if df is None:
            if pathg.is_file():
                warnings.warn(f"File {pathg.as_posix()} is not readable")
            elif pathg.is_dir():
                warnings.warn(f"Folder {pathg.as_posix()} is not readable")
            return None
        else:        
            df = BaseDriver.adapt_dtype(df, dtype)
            return df        
        crs = kwargs.pop("crs", None)
        pathg: Path = Path(path)

    def export_dataframe(
        self,
        df: Union[pd.DataFrame, gpd.GeoDataFrame, dict],
        path: str,
        mode: str = "w",
        partitionby: Optional[List[str]] = None,
        geometry_col: Optional[str] = None,
        index: bool = False,
        crs: Optional[str] = None,        
        **kwargs
    ):
        with warnings.catch_warnings(record=True) as w:
            partition_cols=partitionby
            
            pathg: Path = Path(path)
            ext = pathg.suffix.lower()        

            # rimuovo i file se "w"
            if mode == "t":
                mode = "w"
            if mode == "w" and not (ext in (".gpkg", ".geopackage")):
                if ext == ".shp":
                    files = pathg.glob(os.path.join("*", pathg.with_suffix(".*").name))
                    files = [f for f in files if f.is_file() and f.suffix.lower() in (".shp", ".shx", ".dbf", ".prj", ".cpg", ".sbn", ".sbx", ".fbn", ".fbx", ".ain", ".aih", ".atx") or str(f).endswith(".shp.xml")]
                else:
                    files = [pathg]
                for f in files:
                    remove_path(str(f))      
                # rimuovo eventuale cartella principale
                remove_path(pathg)
            
            
            if partition_cols:
                sql_partition_by = f", PARTITION_BY ({','.join(partition_cols)})"
            else:
                sql_partition_by = ''
            if ext==".csv":
                #geometry_col = BaseDriver.get_geometry_col(df=df, geometry_col=geometry_col, errors="ignore")
                df = BaseDriver.to_dataframe(df, geometry_col=geometry_col, crs=crs)
                if df is None:
                    raise ValueError ("Impossible to export. The data is not a dataframe or geodataframe")
                if partition_cols:
                    if index:
                        df = df.reset_index()
                    con = duckdb.connect()
                    con.register("df",df)
                    con.execute(f"""
                        COPY (SELECT * FROM df)
                        TO '{pathg.as_posix()}'
                        (FORMAT CSV {sql_partition_by}{", APPEND true" if mode=="a" else ""}, FILENAME_PATTERN '{{uuidv7}}-{{i}}');
                    """)
                else:
                    header = kwargs.pop("header",True)
                    if header:
                        if pathg.exists() and mode=="a":
                            header=False
                    df.to_csv(pathg,index=index, mode=mode, header = header, **kwargs)
            elif ext == '.parquet':
                geometry_col = BaseDriver.get_geometry_col(df=df, geometry_col=geometry_col, errors="ignore")    
                df = BaseDriver.to_dataframe(df, geometry_col=geometry_col, crs=crs)
                if df is None:
                    raise ValueError ("Impossible to export. The data is not a dataframe or geodataframe")
                write_parquet(df, path=pathg, partition_cols=partition_cols, mode=mode, index=index)        
            elif ext == '.geoparquet':    
                geometry_col = BaseDriver.get_geometry_col(df=df, geometry_col=geometry_col, errors="warn")    
                df = BaseDriver.to_geodataframe(df, geometry_col=geometry_col, crs=crs)
                if df is None:
                    raise ValueError ("Impossible to export. The data is not a dataframe or geodataframe")
                write_geoparquet(df, path=pathg, geom_col=geometry_col, partition_cols=partition_cols, mode=mode, index=index)
            elif ext == '.shp':
                geometry_col = BaseDriver.get_geometry_col(df=df, geometry_col=geometry_col, errors="warn")    
                df = BaseDriver.to_geodataframe(df, geometry_col=geometry_col, crs=crs)
                if df is None:
                    raise ValueError ("Impossible to export. The data is not a dataframe or geodataframe")
                if index:
                    df = df.reset_index()
                if partition_cols:
                    BaseDriver.write_partitioned(df, file=pathg, partition_cols=partition_cols, support_append=True, 
                                    fn_save=lambda x,f: gpd.GeoDataFrame.to_file(x, Path(f).as_posix(), driver="ESRI Shapefile", mode="a"))
                else:
                    df.to_file(pathg.as_posix(), driver="ESRI Shapefile", mode=mode)
            elif ext in ('.gpkg', '.geopackage'):        
                geometry_col = BaseDriver.get_geometry_col(df=df, geometry_col=geometry_col, errors="warn")    
                df = BaseDriver.to_geodataframe(df, geometry_col=geometry_col, crs=crs)
                if df is None:
                    raise ValueError ("Impossible to export. The data is not a dataframe or geodataframe")
                if index:
                    df = df.reset_index()
                if partition_cols:
                    BaseDriver.write_partitioned(df, file=pathg, partition_cols=partition_cols, support_append=True, 
                                    fn_save=lambda x,f: gpd.GeoDataFrame.to_file(x, Path(f).as_posix(), driver="GPKG", mode="a",layer = kwargs.get("layer", Path(f).stem)))
                else:
                    layer = kwargs.get("layer", pathg.stem)
                    df.to_file(pathg.as_posix(), driver="GPKG", mode=mode, layer=layer)
        for warning in w:
            warnings.warn(f"Warning for file {pathg}: {warning.message}")

def write_geoparquet(
    gdf: gpd.GeoDataFrame,
    path: Path | str,
    geom_col: str = "geometry",
    partition_cols: Optional[List[str]] = None,
    mode: str = "w",          # 'w' = overwrite, 'a' = append
    index: bool = False,      # True = materializza l'indice come colonne
) -> None:
    """
    Scrive un GeoParquet (file o cartella partizionata) da un GeoDataFrame.

    - partition_cols=None  -> file singolo .geoparquet
    - partition_cols=list  -> cartella partizionata stile Hive
    - mode: 'w' sovrascrive, 'a' appende
    - index: se True include le colonne dell'indice (anche MultiIndex) nel file/cartella
    """

    path = Path(path)

    # ---------- Utility ----------
    def _materialize_index(df: pd.DataFrame, index_flag: bool) -> Tuple[pd.DataFrame, List[str]]:
        """Se index_flag=True, resetta l'indice e restituisce i nomi colonna creati.
        Gestisce indici senza nome e MultiIndex."""
        if not index_flag:
            return df, []

        idx = df.index
        if getattr(idx, "nlevels", 1) == 1:
            name = idx.name if idx.name is not None else "__index__"
            out = df.reset_index(names=name)
            return out, [name]
        else:
            names = list(idx.names)
            # assegna nomi mancanti
            names = [n if n is not None else f"__index_level_{i}__" for i, n in enumerate(names)]
            out = df.reset_index(names=names)
            return out, names

    def _gdf_to_arrow_with_wkb(_gdf: gpd.GeoDataFrame, _geom: str, _index: bool) -> Tuple[pa.Table, List[str]]:
        # costruisci DataFrame tabellare
        base_df = pd.DataFrame(_gdf.drop(columns=_geom))
        base_df, index_cols = _materialize_index(base_df, _index)
        # aggiungi geometria in WKB
        base_df = base_df.assign(**{_geom: _gdf[_geom].to_wkb()})
        table = pa.Table.from_pandas(base_df, preserve_index=False)
        return table, index_cols

    def _geo_meta_from_gdf(_gdf: gpd.GeoDataFrame, _geom: str) -> bytes:
        geom_types = sorted(x for x in set(_gdf[_geom].geom_type) if x is not None)
        bbox = list(map(float, _gdf.total_bounds))
        crs_obj = _gdf.crs.to_json_dict() if _gdf.crs is not None else None
        geo_meta = {
            "version": "1.0.0",
            "primary_column": _geom,
            "columns": {
                _geom: {
                    "encoding": "WKB",
                    "geometry_types": geom_types,
                    "crs": crs_obj,
                    "bbox": bbox
                }
            }
        }
        return json.dumps(geo_meta).encode("utf-8")

    def _attach_geo_metadata(table: pa.Table, geo_meta_bytes: bytes) -> pa.Table:
        existing = table.schema.metadata or {}
        new_meta = {**existing, b"geo": geo_meta_bytes}
        return table.replace_schema_metadata(new_meta)

    def _read_existing_geo_metadata(_path: Path) -> Optional[bytes]:
        try:
            pf = pq.ParquetFile(_path)
            md = pf.metadata.metadata or {}
            return md.get(b"geo", None)
        except Exception:
            return None

    def _ensure_columns(df: pd.DataFrame, column_order: List[str]) -> pd.DataFrame:
        """Aggiunge colonne mancanti come None e riordina secondo column_order."""
        for col in column_order:
            if col not in df.columns:
                df[col] = None
        return df[column_order]

    def _ensure_arrow_table(obj) -> pa.Table:
        if isinstance(obj, pa.Table):
            return obj
        if isinstance(obj, pa.RecordBatchReader):
            return pa.Table.from_batches(list(obj))
        if isinstance(obj, pa.RecordBatch):
            return pa.Table.from_batches([obj])
        # DuckDB può anche restituire pandas DataFrame con alcune API
        try:
            import pandas as pd
            if isinstance(obj, pd.DataFrame):
                return pa.Table.from_pandas(obj, preserve_index=False)
        except Exception:
            pass
        raise TypeError(f"Tipo non gestito per conversione in pyarrow.Table: {type(obj)}")

    # ---------- Validazioni ----------
    if mode not in ("w", "a"):
        raise ValueError("mode deve essere 'w' o 'a'")
    if geom_col not in gdf.columns:
        raise ValueError(f"Colonna geometrica '{geom_col}' non trovata nel GeoDataFrame.")

    # ---------- Scrittura FILE ----------
    if not partition_cols:
        path.parent.mkdir(parents=True, exist_ok=True)

        # Metadati geo: preferisci quelli esistenti in append, altrimenti derivali dal nuovo gdf
        geo_meta_bytes = _read_existing_geo_metadata(path) if path.exists() else None
        if geo_meta_bytes is None:
            geo_meta_bytes = _geo_meta_from_gdf(gdf, geom_col)

        if mode == "w" or not path.exists():
            table, _ = _gdf_to_arrow_with_wkb(gdf, geom_col, index)
            table = _attach_geo_metadata(table, geo_meta_bytes)
            pq.write_table(table, path)
            return

        # mode == 'a' e file esistente: append con DuckDB
        existing_schema = pq.read_schema(path)
        existing_cols = list(existing_schema.names)

        # prepara df_new materializzando l'indice se richiesto
        df_new = pd.DataFrame(gdf.drop(columns=geom_col))
        df_new, index_cols = _materialize_index(df_new, index)
        df_new = df_new.assign(**{geom_col: gdf[geom_col].to_wkb()})
        df_new = _ensure_columns(df_new, existing_cols)

        con = duckdb.connect()
        try:
            con.register("new_df", df_new)
            rel = con.sql(f"""
                SELECT * FROM read_parquet('{str(path).replace("'", "''")}')
                UNION ALL
                SELECT * FROM new_df
            """)
            arrow_tab = _ensure_arrow_table(rel.arrow())
        finally:
            con.close()

        arrow_tab = _attach_geo_metadata(arrow_tab, geo_meta_bytes)
        pq.write_table(arrow_tab, path)
        return
    
    # ---------- Scrittura CARTELLA PARTIZIONATA ----------
    out_dir = path
    out_dir.mkdir(parents=True, exist_ok=True)

    # Metadati geo: se esistono file, riusa quelli, altrimenti deriva dal gdf corrente
    existing_geo_meta = None
    for p in out_dir.rglob("*.parquet"):
        existing_geo_meta = _read_existing_geo_metadata(p)
        if existing_geo_meta:
            break
    geo_meta_bytes = existing_geo_meta or _geo_meta_from_gdf(gdf, geom_col)

    # Gestione overwrite/append
    if mode == "w":
        shutil.rmtree(out_dir, ignore_errors=True)
        out_dir.mkdir(parents=True, exist_ok=True)
        behavior = "overwrite_or_ignore"
    else:  # mode == 'a'
        # Seleziona le partizioni toccate, anche se sono colonne d'indice materializzate
        temp_df = pd.DataFrame(gdf.drop(columns=geom_col))
        temp_df, idx_cols = _materialize_index(temp_df, index)
        # le partition_cols devono essere presenti in temp_df
        missing_parts = [c for c in (partition_cols or []) if c not in temp_df.columns]
        if missing_parts:
            raise ValueError(f"Le colonne di partizione {missing_parts} non sono presenti nel DataFrame risultante. "
                             f"Se provengono dall'indice, usa index=True o rinomina opportunamente.")
        keys = temp_df[partition_cols].drop_duplicates()
        """
        for _, row in keys.iterrows():
            sub = "/".join(f"{c}={row[c]}" for c in partition_cols)
            for folder in out_dir.glob(sub):
                if folder.is_dir():
                    shutil.rmtree(folder)
        """
        behavior = "overwrite_or_ignore"

    # Costruisci tabella finale da scrivere
    table, _ = _gdf_to_arrow_with_wkb(gdf, geom_col, index)
    visited_paths = []

    def file_visitor(written_file):
        visited_paths.append(written_file.path)

    # Scrivi dataset partizionato
    write_to_dataset(
        table,
        root_path=str(out_dir),
        partition_cols=partition_cols,
        existing_data_behavior=behavior,
        file_visitor=file_visitor,
        #basename_template="guid-{i}.parquet.tmp"  # scrivi su .tmp per post-process
    )

    # Post-process: aggiungi metadati 'geo' a ogni file creato
    for p in visited_paths:
        tab = pq.read_table(p)
        tab = _attach_geo_metadata(tab, geo_meta_bytes)
        pq.write_table(tab, p)
        #shutil.move(p, p.with_suffix(""))  # rimuovi .tmp

def write_parquet(
    df: pd.DataFrame,
    path: Path | str,
    mode: str = "w",            # 'w' overwrite, 'a' append
    index: bool = False,       # scrivere o no l'indice
    partition_cols: Optional[List[str]] = None  # opzionale
):
    """
    Scrive un DataFrame in formato Parquet (file o cartella partizionata).
    
    - Se partition_cols=None -> path è un file .parquet
    - Se partition_cols è una lista -> path è una CARTELLA
    - mode='w' -> sovrascrivi
    - mode='a' -> append (concatenate in caso di file, nuovi file in caso di folder)
    - index=True -> materializza l'indice
    """

    path = Path(path)

    # --- Gestione indice ---
    if index:
        df = df.reset_index()

    # --- Conversione in Arrow ---
    table_new = pa.Table.from_pandas(df, preserve_index=False)

    # --- Scrittura partizionata (folder) ---
    if partition_cols:
        folder = path
        folder.mkdir(parents=True, exist_ok=True)

        if mode == "w":
            shutil.rmtree(folder, ignore_errors=True)
            folder.mkdir(parents=True, exist_ok=True)
            behavior = "overwrite_or_ignore"
        else:  # append su folder
            behavior = "overwrite_or_ignore"  # aggiunge nuovi file senza toccare quelli esistenti

        write_to_dataset(
            table_new,
            root_path=str(folder),
            partition_cols=list(partition_cols),
            existing_data_behavior=behavior
        )

    # --- Scrittura singolo file ---
    else:
        file = path
        file.parent.mkdir(parents=True, exist_ok=True)

        if mode == "w" or not file.exists():
            pq.write_table(table_new, file.as_posix())
        else:  # append su file
            table_old = pq.read_table(file.as_posix())
            table_out = pa.concat_tables([table_old, table_new], promote=True)
            pq.write_table(table_out, file.as_posix())

