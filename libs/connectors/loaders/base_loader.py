from abc import ABC, abstractmethod
from typing import Union
import pandas as pd
import geopandas as gpd
from ...utils import filters_to_query_expression, import_dataframe
from shapely import from_wkb, from_wkt, from_geojson
class BaseLoader(ABC):

    @abstractmethod
    def load_dataset(self,parameters, filters=None, dtype=None, **kwargs) -> Union[pd.DataFrame, gpd.GeoDataFrame, dict]:
        """
        Carica un dataset in base ai parametri forniti, ai filtri e al tipo di dato specificato.

        Argomenti:
            parameters (dict): Un dizionario contenente i parametri necessari per caricare il dataset.
            filters (opzionale): Criteri per filtrare il dataset. I filtri devono essere specificati in forma di lista di tuple, seguendo la sintassi: 
                                          filters = [[('colonna', 'operatore', valore), ...], ...]
                                 * Operatori supportati: ==, =, !=, >, >=, <, <=, in, not in​
                                 * AND logico: le tuple all'interno di una lista interna sono combinate con un AND logico.​
                                 * OR logico: le liste interne sono combinate con un OR logico.
                                 es: filters = [('col1', '==', 10), ('col2', '>', 5)] 
                                     corrisponde a col1 == 10 AND col2 > 5
                                 es: filters = [[('col1', '==', 10), ('col2', '>', 5)], [('col3', '<', 20)]] 
                                     corrisponde a (col1 == 10 AND col2 > 5) OR (col3 < 20)
                                 es: filters = [[('col1', '==', 10), ('col2', '>', 5)], [('col3', '<', 20), ('col4', '!=', 30)]] 
                                     corrisponde a (col1 == 10 AND col2 > 5) OR (col3 < 20 AND col4 != 30)
            dtype (opzionale): Il tipo di dato desiderato per il dataset caricato. Può essere utilizzato per specificare formati come pandas DataFrame o GeoDataFrame.
            **kwargs: Argomenti aggiuntivi per la personalizzazione o per casi d'uso specifici.

        Restituisce:
            Union[pd.DataFrame, gpd.GeoDataFrame]: Il dataset caricato, che può essere un pandas DataFrame o un GeoPandas GeoDataFrame, a seconda dell'esistenza di un campo geometrico.
        """

        pass
    
    filters_to_query_expression = filters_to_query_expression
    import_dataframe_from_file = import_dataframe
    from_wkb = from_wkb
    from_wkt = from_wkt
    from_geojson = from_geojson
    initial_geometry = {'P','L','M','S','G'}
    def to_geom(x):
        if isinstance(x, gpd.array.GeometryArray):
            return x
        if isinstance(x, bytes):
            return BaseLoader.from_wkb(x)
        elif isinstance(x, str):
            if x.startswith("{"):
                return BaseLoader.from_geojson(x)
            else:
                if x[0].upper() in BaseLoader.initial_geometry: 
                    return BaseLoader.from_wkt(x)
                else:
                    return BaseLoader.from_wkb(bytes.fromhex(x))
                
        return x
    def apply_dtype(df: Union[pd.DataFrame,gpd.GeoDataFrame], dtype=None):
        if dtype:
            dtype = {k: v for k, v in dtype.items() if k in df.columns}  
            for k in dtype.keys():
                if dtype[k] == "geometry":
                    df[k] = df[k].apply(BaseLoader.to_geom)      
            df.astype(dtype, copy=False)
        return df