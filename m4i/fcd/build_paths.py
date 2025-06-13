
from ..graphs import AbstractGraph, AbstractNode, PathContainer, Path, PathList, AbstractLink, PathList, AbstractTurn
from ..params_parser import ParamsParser
from ..connectors import Loader
from ..fcd.map_matching import MapMatching
from ..log import Logger
from ..utils import Parallel
from numbers import Number
from shapely import Point, LineString, frechet_distance, remove_repeated_points
from shapely.ops import substring
from shapely.validation import make_valid
import pandas as pd
import geopandas as gpd

from datetime import datetime

from typing import Optional, Union, Iterable, Hashable, Tuple   
from heapq import heappush as push
from heapq import heappop as pop
import geopandas as gpd
from shapely.geometry import Point, MultiLineString

import warnings
def makevalid(link):
    try:
        return make_valid(remove_repeated_points(link))
    except Exception as ex:
        pass
    try:
        return make_valid(link)
    except Exception as ex:
        pass
    try:
        return remove_repeated_points(link)
    except Exception as ex:
        pass
    return link
def trip_dijkstra(graph: AbstractGraph,
    source: Union[AbstractNode, Hashable],
    targets: Optional[Union[Iterable[Hashable], Hashable]] = None,
    trip: LineString = None,
    t_start: Number = 0,
    t_base: Number = 0,
    turn_cost: Optional[str] = "time",
) -> Union[PathContainer]:
    warnings.filterwarnings("error", category=RuntimeWarning, append=True)
    def line_from_list(line:LineString, link: AbstractLink):
        if line is None:
            return makevalid(link)

        coords1 = list(line.coords)
        coords2 = list(link.coords)

        # se l’ultimo punto di line1 == primo di line2, evito duplicazione:
        if coords1[-1] == coords2[0]:
            coords2 = coords2[1:]

        # concateno e ricreo la LineString
        return makevalid(LineString(coords1 + coords2))
    
    def calc_distance(line1:LineString, trip:LineString):
        if line1 is None or trip is None:
            return float("inf")
        #dist = line1.hausdorff_distance(line2)
        p0 = Point(line1.coords[0])
        p1 = Point(line1.coords[-1])
        if len(trip.coords) < 2:
            return max(trip.distance(p0) , trip.distance(p1))
        d0 = trip.project(p0)
        d1 = trip.project(p1)
        if d0 > d1:
            d0, d1 = d1, d0
        if d0 == d1:
            d1+=0.1
            if d1>trip.length:
                d1 = trip.length
                d0-=0.1
        if d0<0:
            d0 = 0
            
        
        cut_trip = substring(trip, d0, d1)
       # import warnings
        
        try:
            dist = line1.hausdorff_distance(cut_trip) # / line1.length
        except Exception as ex:
            #print(f"Error: {ex}")
            dist = float("inf")

        return dist
    
    if isinstance(source, AbstractNode):
        source = source["idx"]

    targets = set(targets) if targets is not None else set(graph["nodes"].keys())

    trip = makevalid(trip)
    if trip is None or trip.is_empty or len(trip.coords) < 2:
        return PathList()
    pl = PathList()
    
    residual_targets = targets.copy()

    l: Optional[AbstractLink] = None
    next_l: Optional[AbstractLink] = None
    current_l: Optional[AbstractLink] = None

    visited = set()

    paths_links = {l["idx"]: [] for l in graph.get_all_links()}
    paths_geoms = {}
    paths_costs = {}

    node_costs = {}
    node_preds = {}

    
    pq = []
    # calcolo dei costi a partire dalla sorgente
    for l in graph.get_fws(source):
        
        l_i, l_j, l_idx = l["i"], l["j"], l["idx"]

        paths_links[l_idx] = [l_idx]
        paths_geoms[l_idx] = line_from_list(paths_geoms.get(l_idx,None), l["geometry"])
        initial_cost = calc_distance(paths_geoms[l_idx], trip)
        paths_costs[l_idx] = initial_cost
        node_preds[l_j] = l_idx
        node_costs[l_j] = initial_cost
        push(pq, (initial_cost, l_idx, l_i, l_j, l))

    # The code snippet you provided is part of the Dijkstra's algorithm implementation within the
    # `dijkstra` method of the `SPP` class. Let's break down what this part of the code is doing:
    while pq:
        current_cost, current_l_idx, current_l_i, current_l_j, current_l = pop(pq)
        if current_l_idx in visited:
            continue
        visited.add(current_l_idx)

        residual_targets.discard(current_l_i)
        if not residual_targets:
            break
        for next_l in graph.get_fws(current_l_j):
            next_l_idx = next_l["idx"]
            if next_l_idx in visited:
                continue

            next_l_i, next_l_j = next_l["i"], next_l["j"]
            # costo attuale
            new_cost = current_cost #* len(paths_links[current_l_idx])
            act_t = t_start + new_cost
            new_line =line_from_list(paths_geoms.get(current_l_idx,None), next_l["geometry"])
            new_cost += calc_distance(next_l["geometry"], trip) 
            #new_cost /= (len(paths_links[current_l_idx]) + 1)       
            # costo manovre
            turn: AbstractTurn = graph.get_turn(current_l_idx, next_l_idx)
            if turn is not None:
                kwargs = {"t": act_t, "t_base": t_base, "in_link": current_l,"out_link": next_l, "graph": graph}
                new_cost += turn.get_value(name=turn_cost,default=0, **kwargs)                          
            if new_cost < node_costs.get(next_l_j, float("inf")):
                node_costs[next_l_j] = new_cost
                node_preds[next_l_j] = next_l_idx
            if new_cost < paths_costs.get(next_l_idx, float("inf")):
                push(pq, (new_cost, next_l_idx, next_l_i, next_l_j, next_l))                        
                paths_links[next_l_idx] = paths_links[current_l_idx] + [next_l_idx]
                paths_geoms[next_l_idx] = new_line
                paths_costs[next_l_idx] = new_cost
    for target in targets:
        target_link = node_preds.get(target, None)
        if target_link is None:
            continue
        links = paths_links.get(target_link, [])
        if len(links) > 0:
            path = Path(source=source, target=target, t_start=0, links=links, tot_cost=paths_costs[links[-1]], t_base=0)
            pl.add_path(path)
    return pl

def nearest_point_row(df_links: gpd.GeoDataFrame, fcd: gpd.GeoDataFrame,pt: Point) -> tuple:
    neareset_node = None

    mm_links = [d.get("mm_id_link")  for d in fcd["all_matches"]]
    df_l = df_links[df_links["id"].isin(mm_links)]
    if df_l.shape[0] == 0:
        df_l = df_links

    sidx = df_l.sindex
    nearest_idx = list(sidx.nearest(pt))[1]
    nearest_link = df_l.iloc[nearest_idx]
    
    if nearest_link is not None:
        nearest_link = nearest_link.iloc[0]            
        if isinstance(nearest_link.geometry,LineString):
            # calcolo il punto più vicino tra quello iniziale e quello finale della linestring
            coords = list(nearest_link.geometry.coords)
            pt0 = Point(coords[0])
            pt1 = Point(coords[-1])
        elif isinstance(nearest_link.geometry,MultiLineString):
            # calcolo il punto più vicino tra quello iniziale e quello finale della
            # linestring
            coords = list(nearest_link.geometry[0].coords)
            pt0 = Point(coords[0])
            coords = list(nearest_link.geometry[-1].coords)
            pt1 = Point(coords[-1])

        dist0 = pt.distance(pt0)
        dist1 = pt.distance(pt1)
        if dist0 < dist1:
            neareset_node = nearest_link["from_node"]
        else:
            neareset_node = nearest_link["to_node"]
    return neareset_node    

class BuildPaths:

    def __init__(self, parser:ParamsParser, loader:Loader=None, crs_calc="EPSG:6875", crs_data="EPSG:4326", n_workers_mm=-1, n_workers_pm=-1, max_distance=50, max_angle=45, logger=None):
        self.log = logger or Logger.getLogger(self.__class__.__name__)
        self.parser: ParamsParser = parser
        self.loader:Loader = loader if loader else Loader(parser=self.parser)
        self.crs_calc = crs_calc
        self.crs_data = crs_data
        self.n_workers_mm = Parallel.get_num_min_cpus(n_workers_mm)
        self.n_workers_pm = Parallel.get_num_min_cpus(n_workers_pm)
        self.max_distance = max_distance
        self.max_angle = max_angle
        self.n_cpus = max(self.n_workers_mm, self.n_workers_pm)
        self.log.info(f"Initializing Parallel...")
        Parallel.initialize_parallel(engine=self.parser.ini.PARALLEL_ENGINE, num_cpus=self.n_cpus, address=self.parser.ini.PARALLEL_CLUSTER_ADDRESS)
        self.log.info(f"Parallel initialized with {Parallel.num_cpus} workers")


    def load_graph(self, df_links=None):
        #self.log.info(f"Loading graph data")
        if df_links is None:
            df_links, _, _ = self.loader.load_df_graph()
            self.df_links = gpd.GeoDataFrame(df_links, crs=self.crs_data)
            if self.crs_calc != self.crs_data:
                self.df_links = self.df_links.to_crs(self.crs_calc)
        else:
            self.df_links = df_links
        self.mm = MapMatching(links_gdf=self.df_links, links_id_col="id", link_direction_col=None)
        #self.log.info(f"Loaded {self.df_links.shape[0]} links")
    
    def load_fcd_by_timestamp(self, t_start: datetime, t_end: datetime, crs_data=None):
        #self.log.info(f"Loading fcd data")
        dtype = self.parser.get_dtype("fcd")
        df_fcd = self.loader.load(path="params.fcd",
                     filters=[("timestamp",">=",t_start.strftime("%Y-%m-%d %H:%M:%S")), ("timestamp","<=",t_end.strftime("%Y-%m-%d %H:%M:%S")),
                              #("id_trip","=", "c6495aa3d08d936a5ae4e6bc89a7606df924b68e")
                              #"id_trip" = '9aec771c30c102d77a039efcee6b72bdcc85ef9a'
                              ],
                     dtype=dtype,
                     )
        
        df_fcd = gpd.GeoDataFrame(df_fcd, crs=crs_data or self.crs_data)
        if (crs_data or self.crs_data) != self.crs_calc:
            df_fcd = df_fcd.to_crs(self.crs_calc)
        return df_fcd

    def match_fcd(self, df_fcd: gpd.GeoDataFrame, df_fcd_old: gpd.GeoDataFrame) -> Tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:        
        grp = df_fcd.groupby("id_trip")
        tasks = [(id_trip, df, None) for id_trip, df in grp if len(df) > 0]
        if df_fcd_old is not None and df_fcd_old.shape[0] > 0:
            grp1 = df_fcd_old.groupby("id_trip")
            tasks = [(id_trip, df, grp1.get_group(id_trip) if id_trip in grp1.groups else None) for id_trip, df, _ in tasks]

        #self.log.info(f"Loaded {df_fcd.shape[0]} FCD records")
        #self.log.info(f"Loaded {len(tasks)} trips")
                
        def fn(tasks, crs, mm, max_distance, max_angle):

            ret = None
            if len(tasks) == 0:
                return None, None
            for id_trip,df,df_fcd_old in tasks:
                tmp = mm.match(gps_gdf=df,
                        max_distance=max_distance, 
                        max_angle=max_angle, 
                        fcd_id_col="id_fcd",
                        fcd_dir_col="heading",
                        fcd_state_col="engine", 
                        all_matches=True)
                tmp = tmp.merge(df, on="id_fcd", how="left")                
                #print(tmp.head())
                if ret is None:
                    if tmp is not None and tmp.shape[0] > 0:
                        ret = tmp
                else:
                    if tmp is not None and tmp.shape[0] > 0:
                        ret = pd.concat([ret, tmp], ignore_index=True)        
            if ret is None or ret.shape[0] == 0:
                return None, None              
            #print(ret.head())          
  
            ret = gpd.GeoDataFrame(ret)
            if df_fcd_old is not None and df_fcd_old.shape[0] > 0:
                #print("ret", ret.shape[0])
                #print("df_fcd_old", df_fcd_old.shape[0])
                ret = pd.concat([ret, df_fcd_old], ignore_index=True).drop_duplicates(subset=["id_fcd"], keep="last")
                #print("ret1", ret.shape[0])
                #ret = ret[~ret.duplicated(subset=["id_fcd"], keep="last")]
            #print(ret.head())
            ret.sort_values(by=["id_trip","timestamp"], ascending=[True,True], inplace=True)      
            def make_line(points):
                coords =[pt.coords[0] for pt in points]
                if len(coords) == 1:
                    # duplico la singola coordinata per avere almeno 2 punti
                    coords = coords * 2
                return coords
            def make_tt(x):
                return (x.max() - x.min()).total_seconds()
            grouped = (
                ret.groupby("id_trip").agg(
                    geometry = ('geometry', make_line),
                    dt_o = ('timestamp', 'min'),
                    dt_d = ('timestamp', 'max'),
                    tt = ('timestamp', make_tt),
                )
            )
            grouped["geometry"] = grouped["geometry"].apply(lambda x: LineString(x))
            df_line = gpd.GeoDataFrame(grouped, geometry='geometry', crs=crs).reset_index()
            df_line['length'] = df_line.geometry.length
            return ret, df_line
        

        ret_mm = None
        ret_line = None
        for df_mm, df_line in Parallel.execute(fn, tasks=tasks,crs=self.crs_data, mm=self.mm, 
                                               max_distance=self.max_distance, max_angle=self.max_angle,
                                               n_workers=self.n_workers_mm):
            if ret_mm is None:
                if df_mm is not None and df_mm.shape[0] > 0:
                    ret_mm = df_mm                
            else:
                if ret_mm is not None and ret_mm.shape[0] > 0:
                    ret_mm = pd.concat([ret_mm, df_mm], ignore_index=True)      
            if ret_line is None:
                if df_line is not None and df_line.shape[0] > 0:
                    ret_line = df_line
            else:
                if ret_line is not None and ret_line.shape[0] > 0:
                    ret_line = pd.concat([ret_line, df_line], ignore_index=True)      
        if df_fcd_old is not None and df_fcd_old.shape[0] > 0:   
            ret_mm = pd.concat([df_fcd_old, ret_mm], ignore_index=True).drop_duplicates(subset=["id_fcd"], keep="last")
        return ret_mm, ret_line
        
    def calculate_paths(self, df_links, df_fcd, df_trips, G):                
        
        def fn(tasks, df_links, G):
            #warnings.filterwarnings("ignore", category=RuntimeWarning, append=True)
            tot_paths = PathList()
            for trip, df_fcd in tasks:
                try:
                    if hasattr(trip,"id_zone_o") and trip.id_zone_o is not None:
                        source= int(trip.id_zone_o)
                    else:
                        pto = Point(trip.geometry.coords[0])
                        source = nearest_point_row(df_links=df_links, fcd=df_fcd.iloc[0], pt= pto)
                    if hasattr(trip,"id_zone_d") and trip.id_zone_d is not None:
                        target = int(trip.id_zone_d)
                    else:
                        ptd = Point(trip.geometry.coords[-1])
                        target = nearest_point_row(df_links=df_links, fcd=df_fcd.iloc[-1], pt= ptd)
                    
                    
                    paths: PathContainer = trip_dijkstra(
                        graph=G,
                        source=source,
                        targets={target},
                        trip=trip.geometry)
                    for path in paths.all_paths():
                        path["id_trip"] = trip.id_trip
                        path["t"] = int(int(trip.dt_o.timestamp()) - datetime.timestamp(trip.dt_o.replace(hour=0,minute=0,second=0, microsecond=0)) /60)
                    tot_paths.merge(paths)
                except Exception as ex:
                    print(f"Error: {ex}")
                    import traceback, sys
                    traceback.print_exc()
                    

            return tot_paths
            
        tasks = list(df_trips.itertuples())
        tot_paths = PathList()
        grp = df_fcd.groupby("id_trip")
        tasks = [(trip, grp.get_group(trip.id_trip).iloc[[0,-1],:]) for trip in tasks]
        for paths in Parallel.execute(fn, tasks=tasks,df_links=df_links, G=G, n_workers=self.n_workers_pm):
            if paths is not None and len(paths) > 0:
                tot_paths.merge(paths)
        return tot_paths

    def __del__(self):
        try:
            Parallel.shutdown_parallel()
        except Exception as ex:
            pass
        
