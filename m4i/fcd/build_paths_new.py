
from ..graphs import AbstractGraph, AbstractNode, PathContainer, Path, PathList, AbstractLink, PathList, AbstractTurn
from ..params_parser import ParamsParser
from ..connectors import Loader
from ..fcd.map_matching import MapMatching
from ..log import Logger
from ..utils import Parallel
from numbers import Number
from shapely import Point, LineString, frechet_distance, remove_repeated_points
import pandas as pd
import geopandas as gpd

from datetime import datetime

from typing import Optional, Union, Iterable, Hashable, Tuple   
import geopandas as gpd
from shapely.geometry import Point, MultiLineString
from shapely.ops import substring
from shapely.validation import make_valid
from heapq import heappush, heappop
from typing import Optional, Iterable, Any
import math

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

def safe_makevalid(geom):
    try:
        g = makevalid(geom)
        if g is None or g.is_empty:
            return None
        return g
    except Exception:
        return None

def safe_hausdorff(a: LineString, b: LineString, densify: Optional[float] = None) -> float:
    if a is None or b is None or a.is_empty or b.is_empty:
        return float("inf")
    try:
        if densify is None:
            return a.hausdorff_distance(b)
        return a.hausdorff_distance(b, densify=densify)
    except Exception:
        try:
            return a.hausdorff_distance(b, densify=0.5)
        except Exception:
            return float("inf")
        
def point_on_trip_distance(trip: LineString, p: Point) -> float:
    """Ascissa curvilinea del punto proiettato su trip."""
    try:
        return trip.project(p)
    except Exception:
        return 0.0        
            
def line_from_list(line: Optional[LineString], link_geom: LineString) -> Optional[LineString]:
    link_geom = safe_makevalid(link_geom)
    if link_geom is None:
        return line

    if line is None:
        return link_geom

    try:
        coords1 = list(line.coords)
        coords2 = list(link_geom.coords)
        if not coords1 or not coords2:
            return line

        if coords1[-1] == coords2[0]:
            coords2 = coords2[1:]

        if not coords2:
            return line

        return safe_makevalid(LineString(coords1 + coords2))
    except Exception:
        return line

def cut_trip_between_distances(trip: LineString, d0: float, d1: float) -> Optional[LineString]:
    if trip is None or trip.is_empty:
        return None

    length = trip.length
    d0 = max(0.0, min(float(d0), length))
    d1 = max(0.0, min(float(d1), length))

    if d1 < d0:
        d0, d1 = d1, d0

    if d0 == d1:
        eps = min(0.5, max(0.05, 0.001 * length))
        d0 = max(0.0, d0 - eps)
        d1 = min(length, d1 + eps)

    try:
        sub = substring(trip, d0, d1)
        sub = safe_makevalid(sub)
        return sub
    except Exception:
        return None

def nearest_forward_gps_index(
    line: LineString,
    trip_points: list[Point],
    start_idx: int,
    look_ahead: int = 20,
    max_snap_dist: float = 80.0,
) -> int:
    """
    Cerca in avanti il punto GPS che meglio 'spiega' il nuovo arco.
    Serve a costruire uno stato (link_idx, k) monotono.
    """
    if line is None or line.is_empty or not trip_points:
        return start_idx

    end_idx = min(len(trip_points) - 1, start_idx + look_ahead)
    if end_idx <= start_idx:
        return start_idx

    best_idx = start_idx
    best_dist = float("inf")

    dist_fun = line.distance
    for k in range(start_idx, end_idx + 1):
        d = dist_fun(trip_points[k])
        if d < best_dist:
            best_dist = d
            best_idx = k

    # Evita salti irrealistici se il nuovo arco non è vicino a nessun punto GPS futuro
    if best_dist > max_snap_dist:
        return start_idx

    # Forza il progresso minimo di almeno un punto se possibile
    if best_idx == start_idx and start_idx < len(trip_points) - 1:
        return start_idx + 1

    return best_idx

def local_trip_segment_from_indices(
    trip: LineString,
    trip_proj: list[float],
    k0: int,
    k1: int
) -> Optional[LineString]:
    if not trip_proj:
        return None

    k0 = max(0, min(k0, len(trip_proj) - 1))
    k1 = max(0, min(k1, len(trip_proj) - 1))

    d0 = trip_proj[k0]
    d1 = trip_proj[k1]

    return cut_trip_between_distances(trip, d0, d1)

def local_trip_segment_from_link_geometry(
    trip: LineString,
    link_geom: LineString,
) -> Optional[LineString]:
    """
    Taglia la traiettoria tra le proiezioni degli estremi del link
    sulla geometria della traiettoria osservata.
    """
    if trip is None or trip.is_empty or link_geom is None or link_geom.is_empty:
        return None

    try:
        coords = list(link_geom.coords)
        if len(coords) < 2:
            return None

        p0 = Point(coords[0])
        p1 = Point(coords[-1])

        d0 = trip.project(p0)
        d1 = trip.project(p1)

        return cut_trip_between_distances(trip, d0, d1)
    except Exception:
        return None
    
def calc_local_geom_cost(
    link_geom: LineString,
    trip_sub: Optional[LineString],
    normalize_by_length: bool = False,
) -> float:
    if link_geom is None or trip_sub is None:
        return float("inf")

    c = safe_hausdorff(link_geom, trip_sub)
    if not math.isfinite(c):
        return float("inf")

    if normalize_by_length:
        ll = max(link_geom.length, 1.0)
        c = c / ll

    return c


def calc_local_point_penalty(
    link_geom: LineString,
    local_points: list[Point],
    dist_thr: float = 30.0,
    agg: str = "sum",
) -> float:
    """
    Penalizza i punti GPS che restano lontani dal nuovo arco.
    Usa solo i punti locali coerenti col progresso.
    """
    if link_geom is None or link_geom.is_empty or not local_points:
        return 0.0

    dist_fun = link_geom.distance
    vals = [max(0.0, dist_fun(p) - dist_thr) for p in local_points]

    if not vals:
        return 0.0

    if agg == "max":
        return max(vals)
    if agg == "mean":
        return sum(vals) / len(vals)
    if agg == "p90":
        s = sorted(vals)
        idx = min(len(s) - 1, int(round(0.9 * (len(s) - 1))))
        return s[idx]
    return sum(vals)


def calc_remaining_trip_heuristic(
    next_k: int,
    trip_proj: list[float],
    v_ref_mps: float = 13.89,  # 50 km/h
    w_time: float = 1.0,
) -> float:
    """
    Euristica semplice e prudente.
    Se vuoi comportamento tipo Dijkstra, mettila a 0.
    """
    if not trip_proj or next_k >= len(trip_proj) - 1:
        return 0.0

    remaining_m = trip_proj[-1] - trip_proj[next_k]
    remaining_m = max(0.0, remaining_m)

    # Convertiamo i metri residui in "secondi equivalenti" usando una velocità di riferimento.
    # Moltiplicato per w_time per mantenere la scala compatibile col costo temporale.
    return (remaining_m / max(v_ref_mps, 0.1)) * w_time

def reconstruct_state_path(pred_state: dict, end_state: tuple) -> list[int]:
    links = []
    s = end_state
    while s in pred_state and pred_state[s] is not None:
        prev_s, link_idx = pred_state[s]
        links.append(link_idx)
        s = prev_s
    links.reverse()
    return links
            
def trip_dijkstra(
        graph: AbstractGraph,
        source: Union[AbstractNode, Hashable],
        targets: Optional[Union[Iterable[Hashable], Hashable]] = None,
        trip: LineString = None,
        t_start: float = 0,
        t_base: float = 0,        
        cost_field: Optional[str] = "time",
        # pesi
        w_geom: float = 1.0,
        w_pts: float = 0,
        w_time: float = 0,
        w_turn: float = 0,        
        # GPS / matching locale
        gps_dist_thr: float = 30.0,
        gps_agg: str = "sum",
        look_ahead: int = 2,
        max_snap_dist: float = 80.0,
        # geometria
        normalize_geom_by_length: bool = False,
        # euristica
        use_heuristic: bool = False,
        heuristic_weight: float = 0.0,        
) -> Union[PathContainer]:
    if isinstance(source, AbstractNode):        
        source = source["idx"]

    targets = set(targets) if targets is not None else set(graph["nodes"].keys())

    use_geom_cost = (w_geom != 0)
    use_pts_cost = (w_pts != 0)
    use_time_cost = (w_time != 0)
    use_turn_cost = (w_turn != 0)
    use_time_acc = use_time_cost or use_turn_cost
    use_heuristic_cost = use_heuristic and (heuristic_weight != 0) and (w_time != 0)
    use_gps_progress = use_geom_cost or use_pts_cost or use_heuristic_cost

    trip_points: list[Point] = []
    trip_proj: list[float] = []
    
    if use_gps_progress:
        trip = safe_makevalid(trip)
        if trip is None or trip.is_empty:
            warnings.warn("Trip geometry is invalid or empty but required by current weights/heuristic.")
            return PathList()

        try:
            trip_coords = list(trip.coords)
        except Exception:
            warnings.warn("Unable to extract trip coordinates but required by current weights/heuristic.")
            return PathList()

        if len(trip_coords) < 2:
            warnings.warn("Trip geometry has less than 2 points but required by current weights/heuristic.")
            return PathList()

        trip_points = [Point(x, y) for x, y in trip_coords]
        trip_proj = [point_on_trip_distance(trip, p) for p in trip_points]

        if any("geometry" not in l for l in graph.get_all_links()):
            warnings.warn("Graph links are missing geometry but required by current weights/heuristic.")
            return PathList()

    pl = PathList()

    # stato: (current_link_idx, gps_idx)
    g_cost: dict[tuple, float] = {}
    g_time: dict[tuple, float] = {}
    pred_state: dict[tuple, Optional[tuple]] = {}

    # per scegliere il miglior target raggiunto
    best_target_state: dict[int, tuple] = {}
    best_target_cost: dict[int, float] = {}

    pq = []

    # inizializzazione sugli archi uscenti dal nodo sorgente
    for l in graph.get_fws(source):
        l_idx = l["idx"]
        l_i = l["i"]
        l_j = l["j"]
        k0 = 0
        k1 = 0
        geom = None
        c_geom = 0.0
        c_pts = 0.0

        if use_gps_progress:
            geom = safe_makevalid(l["geometry"])
            if geom is None:
                continue

            # indice GPS coperto dal primo arco
            k1 = nearest_forward_gps_index(
                geom,
                trip_points,
                start_idx=k0,
                look_ahead=look_ahead,
                max_snap_dist=max_snap_dist,
            )

            if use_geom_cost:
                #trip_sub = local_trip_segment_from_indices(trip, trip_proj, k0, k1)
                trip_sub = local_trip_segment_from_link_geometry(trip, geom)
                c_geom = calc_local_geom_cost(
                    geom,
                    trip_sub,
                    normalize_by_length=normalize_geom_by_length,
                )
                if not math.isfinite(c_geom):
                    continue

            if use_pts_cost:
                local_pts = trip_points[k0:k1 + 1] if k1 >= k0 else []
                c_pts = calc_local_point_penalty(
                    geom,
                    local_pts,
                    dist_thr=gps_dist_thr,
                    agg=gps_agg,
                )

        c_time = float(l.get_value(cost_field, 0.0)) if use_time_acc else 0.0
        full_g = (
            (w_geom * c_geom if use_geom_cost else 0.0)
            + (w_pts * c_pts if use_pts_cost else 0.0)
            + (w_time * c_time if use_time_cost else 0.0)
        )

        state = (l_idx, k1)
        g_cost[state] = full_g
        g_time[state] = c_time
        pred_state[state] = None

        if use_heuristic_cost:
            h = heuristic_weight * calc_remaining_trip_heuristic(
                k1,
                trip_proj,
                w_time=w_time,
            )
        else:
            h = 0.0

        heappush(pq, (full_g + h, full_g, c_time, state, l_i, l_j, l))

        if l_j in targets:
            if full_g < best_target_cost.get(l_j, float("inf")):
                best_target_cost[l_j] = full_g
                best_target_state[l_j] = state

    # ricerca
    while pq:
        f_curr, curr_g, curr_time, state, current_l_i, current_l_j, current_l = heappop(pq)

        # stale entry
        if curr_g > g_cost.get(state, float("inf")):
            continue

        current_l_idx, current_k = state

        for next_l in graph.get_fws(current_l_j):
            next_l_idx = next_l["idx"]
            next_l_i = next_l["i"]
            next_l_j = next_l["j"]
            next_k = 0
            c_geom = 0.0
            c_pts = 0.0

            if use_gps_progress:
                next_geom = safe_makevalid(next_l["geometry"])
                if next_geom is None:
                    continue

                # stima del progresso GPS usando SOLO il nuovo arco
                next_k = nearest_forward_gps_index(
                    next_geom,
                    trip_points,
                    start_idx=current_k,
                    look_ahead=look_ahead,
                    max_snap_dist=max_snap_dist,
                )

                # monotonicità stretta
                if next_k < current_k:
                    continue

                # almeno un piccolo progresso quando possibile
                if next_k == current_k and current_k < len(trip_points) - 1:
                    next_k = current_k + 1

                if use_geom_cost:
                    #trip_sub = local_trip_segment_from_indices(trip, trip_proj, current_k, next_k)
                    trip_sub = local_trip_segment_from_link_geometry(trip, next_geom)
                    c_geom = calc_local_geom_cost(
                        next_geom,
                        trip_sub,
                        normalize_by_length=normalize_geom_by_length,
                    )
                    if not math.isfinite(c_geom):
                        continue

                if use_pts_cost:
                    local_pts = trip_points[current_k:next_k + 1] if next_k >= current_k else []
                    c_pts = calc_local_point_penalty(
                        next_geom,
                        local_pts,
                        dist_thr=gps_dist_thr,
                        agg=gps_agg,
                    )
            else:
                next_k = 0

            # tempo reale separato
            edge_time = float(next_l.get_value(cost_field, 0.0)) if use_time_acc else 0.0
            new_time = curr_time + edge_time if use_time_acc else curr_time

            c_turn = 0.0
            if use_turn_cost:
                act_t = t_start + new_time
                turn = graph.get_turn(current_l_idx, next_l_idx)
                if turn is not None:
                    try:
                        kwargs = {
                            "t": act_t,
                            "t_base": t_base,
                            "in_link": current_l,
                            "out_link": next_l,
                            "graph": graph,
                        }
                        c_turn = float(turn.get_value(cost_field, default=0, **kwargs))
                    except Exception:
                        c_turn = 0.0

            edge_cost = (
                (w_geom * c_geom if use_geom_cost else 0.0)
                + (w_pts * c_pts if use_pts_cost else 0.0)
                + (w_time * edge_time if use_time_cost else 0.0)
                + (w_time * w_turn * c_turn if use_turn_cost else 0.0)
            )

            new_g = curr_g + edge_cost
            next_state = (next_l_idx, next_k)

            # relax
            if new_g < g_cost.get(next_state, float("inf")):
                g_cost[next_state] = new_g
                g_time[next_state] = new_time
                pred_state[next_state] = (state, next_l_idx)

                if use_heuristic_cost:
                    h = heuristic_weight * calc_remaining_trip_heuristic(
                        next_k,
                        trip_proj,
                        w_time=w_time,
                    )
                else:
                    h = 0.0

                heappush(
                    pq,
                    (new_g + h, new_g, new_time, next_state, next_l_i, next_l_j, next_l)
                )

                if next_l_j in targets:
                    if new_g < best_target_cost.get(next_l_j, float("inf")):
                        best_target_cost[next_l_j] = new_g
                        best_target_state[next_l_j] = next_state

    # costruzione output
    for target in targets:
        end_state = best_target_state.get(target)
        if end_state is None:
            continue

        links = reconstruct_state_path(pred_state, end_state)
        if not links:
            continue

        path = Path(
            source=source,
            target=target,
            t_start=t_start,
            links=links,
            tot_cost=best_target_cost[target],
            t_base=t_base,
        )
        pl.add_path(path)

    return pl

def nearest_point_row(df_links: gpd.GeoDataFrame, fcd: gpd.GeoDataFrame,pt: Point) -> tuple:
    neareset_node = None

    df_l = None
    if fcd is not None and not fcd.empty:
        if "all_matches" in fcd:
            mm_links = [d.get("mm_id_link")  for d in fcd["all_matches"]]
            df_l = df_links[df_links["id"].isin(mm_links)]
            if df_l.shape[0] == 0:
                df_l = df_links
        if "mm_id_link" in fcd:
            df_l = df_links[df_links["id"] == fcd["mm_id_link"]]
            if df_l.shape[0] == 0:
                df_l = df_links
    df_l = df_links if df_l is None or df_l.empty else df_l

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
        #self.mm = MapMatching(links_gdf=self.df_links, links_id_col="id", links_direction_col=None)
        #self.log.info(f"Loaded {self.df_links.shape[0]} links")
            
    def calculate_paths(self, df_links, df_fcd, df_trips, G, cost_field="time"):                
        DEBUG = False
        def fn(tasks, df_links, G):
            #warnings.filterwarnings("ignore", category=RuntimeWarning, append=True)
            tot_paths = PathList()
            for trip, df_fcd in tasks:
                try:
                    if hasattr(trip,"id_zone_o") and pd.notna(trip.id_zone_o):
                        source= int(trip.id_zone_o)
                    else:
                        pto = Point(trip.geometry.coords[0])
                        if df_fcd is None:                            
                            source = nearest_point_row(df_links=df_links, fcd=None, pt=pto)
                        else:
                            source = nearest_point_row(df_links=df_links, fcd=df_fcd.iloc[0], pt= pto)
                    if hasattr(trip,"id_zone_d") and pd.notna(trip.id_zone_d):
                        target = int(trip.id_zone_d)
                    else:
                        ptd = Point(trip.geometry.coords[-1])
                        if df_fcd is None:
                            target = nearest_point_row(df_links=df_links, fcd=None, pt=ptd)
                        else:
                            target = nearest_point_row(df_links=df_links, fcd=df_fcd.iloc[-1], pt= ptd)
                    
                    #print(f"Calculating path for trip {trip.id_trip} from {source} to {target}")
                    paths: PathContainer = trip_dijkstra(
                        graph=G,
                        source=source,
                        targets={target},
                        trip=trip.geometry,
                        cost_field=cost_field)
                    for path in paths.all_paths():
                        path["id_trip"] = trip.id_trip
                        path["dt_o"] = trip.dt_o
                        path["dt_d"] = trip.dt_d
                        path["t"] = int((trip.dt_o.timestamp() - trip.dt_o.replace(hour=0,minute=0,second=0, microsecond=0).timestamp()) / 60)
                    tot_paths.merge(paths)
                except Exception as ex:
                    print(f"Error: {ex}")
                    import traceback, sys
                    traceback.print_exc()
                    

            return tot_paths
        old_crs = df_trips.crs
        if df_links.crs != self.crs_calc:
            self.log.info(f"Reprojecting links and graph from {df_links.crs} to {self.crs_calc}")
            G=G.st_transform(df_links.crs,self.crs_calc)
            df_links = df_links.to_crs(self.crs_calc)
            
        if df_trips.crs != self.crs_calc:
            self.log.info(f"Reprojecting trips from {df_trips.crs} to {self.crs_calc}")
            df_trips = df_trips.to_crs(self.crs_calc)
        
        df_trips["geometry"] = df_trips.geometry
        tasks = list(df_trips.itertuples())     
        tot_paths = PathList()
        if df_fcd is not None:
            grp = df_fcd.groupby("id_trip")
            tasks = [(trip, grp.get_group(trip.id_trip).iloc[[0,-1],:]) for trip in tasks]
        else:
            tasks = [(trip, None) for trip in tasks]
        for paths in Parallel.execute(fn, tasks=tasks,df_links=df_links, G=G, n_workers=1 if DEBUG else self.n_workers_pm):
            if paths is not None and len(paths) > 0:
                tot_paths.merge(paths)
        return tot_paths

    def __del__(self):
        try:
            Parallel.shutdown_parallel()
        except Exception as ex:
            pass
        
