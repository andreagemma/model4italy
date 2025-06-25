import geopandas as gpd
import numpy as np
import shapely
from shapely.geometry import LineString
from sklearn.cluster import AgglomerativeClustering, DBSCAN
from dask.dataframe.utils import make_meta
from ..base_m4i_model import BaseM4IModel
import dask.dataframe
import dask.dataframe as dd
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

def clustering(df):
    df = gpd.GeoDataFrame(df, crs=4326, geometry=df.geometry.apply(shapely.from_wkb)).to_crs(epsg=6875)    
    print("Clustering...")
    # Calcola la matrice di Hausdorff
    D = hausdorff_matrix(df.geometry.values)
    
    # Esegui il clustering
    model = DBSCAN(min_samples=1, eps=100, metric='precomputed')

    # Aggiungi le etichette al GeoDataFrame
    df["k"] = model.fit_predict(D)
    # per ogni gruppo prendo quello con tot_cost minimo
    df = df.sort_values(by=['k', 'tot_cost'])
    df = df.groupby('k').first().reset_index(drop=False)    
    return df

class PathsClustering(BaseM4IModel):

    def __init__(self, loader: Loader, writer: Writer, ipc: IPC, **kwargs):
        super().__init__(loader=loader, writer=writer, ipc=ipc, **kwargs)

    def run(self, df: Union[gpd.GeoDataFrame, dd.DataFrame]) -> gpd.GeoDataFrame:
        self.log.info("Starting paths clustering...")
        if df is None:
            self
        ddf: dd.DataFrame = dd.DataFrame(df)
        meta = make_meta(ddf)
        meta=meta.assign(k=0)
        cols = meta.columns.tolist()

        def fn(df):
            df = clustering(df)
            return df[cols]
        df = ddf.groupby(["source", "target"]).apply(fn, meta=meta, include_groups=True).compute()          
        return df
    

