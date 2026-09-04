import geopandas as gpd
import pandas as pd
import numpy as np
import shapely
from shapely.geometry import LineString
from sklearn.cluster import AgglomerativeClustering, DBSCAN
from ..utils.parallel import Parallel
from ..base_m4i_model import BaseM4IModel
from ..connectors import Loader, Writer
from ..utils.ipc import IPC
from typing import Union


def hausdorff_matrix(geoms):
    n = len(geoms)
    D = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            d = geoms[i].hausdorff_distance(geoms[j])
            D[i, j] = D[j, i] = d
    return D


def clustering(df, crs_data, crs_calc, eps=100):
    if not isinstance(df, gpd.GeoDataFrame):
        if df.geometry.dtype == "object":
            # Convert WKB to shapely geometries
            df.geometry = df.geometry.apply(shapely.from_wkb)
        elif df.geometry.dtype == "bytes":
            # Convert bytes to shapely geometries
            df.geometry = df.geometry.apply(shapely.from_wkb)
        elif df.geometry.dtype == "str":
            # Convert WKT to shapely geometries
            df.geometry = df.geometry.apply(shapely.from_wkt)
        elif df.geometry.dtype == "geometry":
            # Already in shapely geometry format
            pass
        df = gpd.GeoDataFrame(df, crs=crs_data, geometry=df.geometry).to_crs(crs_calc)
    else:
        if df.crs is None:
            df.set_crs(crs_data, inplace=True)
        df = df.to_crs(crs_calc)
    # Calcola la matrice di Hausdorff
    D = hausdorff_matrix(df.geometry.values)

    # Esegui il clustering
    model = DBSCAN(min_samples=1, eps=eps, metric="precomputed")

    # Aggiungi le etichette al GeoDataFrame
    df["cluster"] = model.fit_predict(D)
    df["_geometry"] = df.geometry.to_crs(crs_data)
    # per ogni gruppo prendo quello con tot_cost minimo
    agg = {c: (c, "first") for c in df.columns if c in {"source", "target", "mode", "links", "_geometry"}}
    if "tot_cost" in df.columns:
        agg["tot_cost"] = ("tot_cost", "mean")
    agg["n_paths"] = ("source", "count")
    df = df.sort_values(by=["tot_cost"])
    df = df.groupby("cluster").agg(**agg).reset_index(drop=False)
    df = df.rename(columns={"_geometry": "geometry"})
    df.drop(columns=["id_trip"], errors="ignore", inplace=True)
    df["k"] = df.groupby(["source", "target", "mode", "links"]).cumcount()
    return df


class PathsClustering(BaseM4IModel):
    def __init__(self, loader: Loader, writer: Writer, ipc: IPC, n_workers=-1, **kwargs):
        super().__init__(loader=loader, writer=writer, ipc=ipc, **kwargs)
        self.n_workers = Parallel.get_num_min_cpus(n_workers)
        self.log.info(f"Initializing Parallel...")
        Parallel.initialize_parallel(
            engine=self.parser.ini.PARALLEL_ENGINE,
            num_cpus=self.n_workers,
            address=self.parser.ini.PARALLEL_CLUSTER_ADDRESS,
        )
        self.log.info(f"Parallel initialized with {Parallel.num_cpus} workers")

    def run(self, df: Union[gpd.GeoDataFrame], eps=100, mode=None, **kwargs) -> gpd.GeoDataFrame:
        if df is None:
            self
        """
        ddf: dd.DataFrame = dd.from_pandas(df, npartitions=1)
        meta = make_meta(ddf)
        meta=meta.assign(k=0)
        cols = meta.columns.tolist()
        crs_calc = self.loader.parser.ini.CRS_CALC
        crs_data = self.loader.parser.ini.CRS
        def fn(df):
            df = clustering(df, crs_calc=crs_calc, crs_data=crs_data)
            return df[cols]
        df = ddf.groupby(["source", "target"]).apply(fn, meta=meta, include_groups=True).compute()      
        df = df.reset_index(drop=False)
        self.writer.write(df, "params.fcd_paths_clustered", mode="w")    
        return df
        """

        crs_calc = self.loader.parser.ini.CRS_CALC
        crs_data = self.loader.parser.ini.CRS
        eps = eps if eps is not None else self.loader.parser.ini.FCD_ROUTING_CLUSTERING_EPS

        def fn(tasks):
            ret = None
            for name, df_group in tasks:
                tmp = clustering(df_group, crs_calc=crs_calc, crs_data=crs_data, eps=eps)
                if ret is None and tmp is not None and not tmp.empty:
                    ret = tmp
                else:
                    ret = pd.concat([ret, tmp], ignore_index=True)
            if ret is not None and not ret.empty:
                try:
                    import dask.dataframe as dd

                    if isinstance(ret, dd.DataFrame):
                        ret = ret.compute()
                except ImportError:
                    raise ImportError("Dask is not installed. Please install dask to use this feature.")
                if isinstance(ret, pd.DataFrame):
                    ret = gpd.GeoDataFrame(ret, crs=crs_calc, geometry=ret.geometry)
            if ret is not None and ret.crs is None:
                ret.set_crs(crs_calc, inplace=True)
            ret.to_crs(crs_data, inplace=True)
            return ret

        if mode == "a":
            df_prev = self.loader.load("params.fcd_paths_clustered", from_output=True)
            df_prev["links"] = df_prev["links"].map(np.ndarray.tolist).map(tuple)
            df = pd.concat([df_prev, df], ignore_index=True)
        grp = df.groupby(["source", "target"])
        ret = None
        total_tasks = list(grp)
        counts = 0
        for i, tmp in enumerate(Parallel.execute(fn, total_tasks, n_workers=self.n_workers)):
            if ret is None and tmp is not None and not tmp.empty:
                ret = tmp
            else:
                ret = pd.concat([ret, tmp], ignore_index=True)
            if tmp is not None and not tmp.empty:
                counts += tmp[["source", "target"]].drop_duplicates().shape[0]
            if ret is not None and not ret.empty:
                self.log.debug(f"Processed {counts}/{len(total_tasks)} tasks")
                pass
        ret.reset_index(drop=True, inplace=True)
        if ret is not None:
            ret = gpd.GeoDataFrame(ret, crs=crs_calc, geometry=ret["geometry"])
        if ret.crs is None:
            ret.set_crs(crs_calc, inplace=True)
        ret.to_crs(crs_data, inplace=True)
        self.writer.write(ret, "params.fcd_paths_clustered", mode="w", first_query=True)
        return ret
