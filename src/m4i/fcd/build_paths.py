from ..graphs import (
    AbstractGraph,
    AbstractNode,
    PathContainer,
    Path,
    PathList,
    AbstractLink,
    PathList,
    AbstractTurn,
)
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


def trip_dijkstra(
    graph: AbstractGraph,
    source: Union[AbstractNode, Hashable],
    targets: Optional[Union[Iterable[Hashable], Hashable]] = None,
    trip: LineString = None,
    t_start: Number = 0,
    t_base: Number = 0,
    cost_field: Optional[str] = "time",
) -> Union[PathContainer]:
    warnings.filterwarnings("error", category=RuntimeWarning, append=True)

    def line_from_list(line: LineString, link: AbstractLink):
        if line is None:
            return makevalid(link)

        coords1 = list(line.coords)
        coords2 = list(link.coords)

        # se l’ultimo punto di line1 == primo di line2, evito duplicazione:
        if coords1[-1] == coords2[0]:
            coords2 = coords2[1:]

        # concateno e ricreo la LineString
        return makevalid(LineString(coords1 + coords2))

    trip_points = [Point(x[0], x[1]) for x in trip.coords]

    def calc_distance(line1: LineString, trip: LineString):
        if not line1 or not trip:
            return float("inf")
        coords = line1.coords
        p0 = Point(coords[0])
        p1 = Point(coords[-1])

        trip_coords = trip.coords
        if len(trip_coords) < 2:
            return max(trip.distance(p0), trip.distance(p1))

        proj = trip.project
        d0 = proj(p0)
        d1 = proj(p1)
        if d0 > d1:
            d0, d1 = d1, d0

        if d0 == d1:
            eps = 0.1
            length = trip.length
            d1 = min(d1 + eps, length)
            d0 = max(d0 - eps, 0)

        cut_trip = substring(trip, d0, d1)

        try:
            return line1.hausdorff_distance(cut_trip)  # / line1.length
            # return line1.frechet_distance(cut_trip) # / line1.length
        except Exception as ex:
            try:
                return line1.hausdorff_distance(cut_trip, densify=0.5)  # / line1.length
                # return line1.frechet_distance(cut_trip, densify=0.5) # / line1.length
            except Exception as ex:
                return float("inf")

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
    link_distance_cache = {}

    node_costs = {}
    node_preds = {}

    pq = []
    # calcolo dei costi a partire dalla sorgente
    for l in graph.get_fws(source):
        l_i, l_j, l_idx = l["i"], l["j"], l["idx"]

        paths_links[l_idx] = [l_idx]
        paths_geoms[l_idx] = line_from_list(paths_geoms.get(l_idx, None), l["geometry"])
        initial_cost = calc_distance(paths_geoms[l_idx], trip)
        paths_costs[l_idx] = initial_cost
        node_preds[l_j] = l_idx
        node_costs[l_j] = initial_cost
        push(pq, (0, initial_cost, l_idx, l_i, l_j, l))

    # The code snippet you provided is part of the Dijkstra's algorithm implementation within the
    # `dijkstra` method of the `SPP` class. Let's break down what this part of the code is doing:
    while pq:
        _, current_cost, current_l_idx, current_l_i, current_l_j, current_l = pop(pq)
        if current_l_idx in visited:
            continue
        visited.add(current_l_idx)

        residual_targets.discard(current_l_j)
        if not residual_targets:
            break
        for next_l in graph.get_fws(current_l_j):
            next_l_idx = next_l["idx"]
            if next_l_idx in visited:
                continue

            next_l_i, next_l_j = next_l["i"], next_l["j"]
            # costo attuale
            new_cost = current_cost  # * len(paths_links[current_l_idx])
            act_t = t_start + new_cost
            new_line = line_from_list(
                paths_geoms.get(current_l_idx, None), next_l["geometry"]
            )
            link_distance = link_distance_cache.get(next_l_idx)
            if link_distance is None:
                link_distance = calc_distance(next_l["geometry"], trip)
                link_distance_cache[next_l_idx] = link_distance
            new_cost += link_distance
            # new_cost /= (len(paths_links[current_l_idx]) + 1)
            # costo manovre
            turn: AbstractTurn = graph.get_turn(current_l_idx, next_l_idx)
            if turn is not None:
                kwargs = {
                    "t": act_t,
                    "t_base": t_base,
                    "in_link": current_l,
                    "out_link": next_l,
                    "graph": graph,
                }
                new_cost += turn.get_value(name=cost_field, default=0, **kwargs)
            if new_cost < node_costs.get(next_l_j, float("inf")):
                node_costs[next_l_j] = new_cost
                node_preds[next_l_j] = next_l_idx
            if new_cost < paths_costs.get(next_l_idx, float("inf")):
                push(pq, (new_cost, new_cost, next_l_idx, next_l_i, next_l_j, next_l))
                paths_links[next_l_idx] = paths_links[current_l_idx] + [next_l_idx]
                paths_geoms[next_l_idx] = new_line
                paths_costs[next_l_idx] = new_cost

    for target in targets:
        target_link = node_preds.get(target, None)
        if target_link is None:
            continue
        links = paths_links.get(target_link, [])
        if len(links) > 0:
            path = Path(
                source=source,
                target=target,
                t_start=0,
                links=links,
                tot_cost=paths_costs[links[-1]],
                t_base=0,
            )
            pl.add_path(path)
    return pl


def nearest_point_row(
    df_links: gpd.GeoDataFrame, fcd: gpd.GeoDataFrame, pt: Point
) -> tuple:
    neareset_node = None

    df_l = None
    if fcd is not None and not fcd.empty:
        if "all_matches" in fcd:
            mm_links = [d.get("mm_id_link") for d in fcd["all_matches"]]
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
        if isinstance(nearest_link.geometry, LineString):
            # calcolo il punto più vicino tra quello iniziale e quello finale della linestring
            coords = list(nearest_link.geometry.coords)
            pt0 = Point(coords[0])
            pt1 = Point(coords[-1])
        elif isinstance(nearest_link.geometry, MultiLineString):
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
    def __init__(
        self,
        parser: ParamsParser,
        loader: Loader = None,
        crs_calc="EPSG:6875",
        crs_data="EPSG:4326",
        n_workers_mm=-1,
        n_workers_pm=-1,
        max_distance=50,
        max_angle=45,
        logger=None,
    ):
        self.log = logger or Logger.getLogger(self.__class__.__name__)
        self.parser: ParamsParser = parser
        self.loader: Loader = loader if loader else Loader(parser=self.parser)
        self.crs_calc = crs_calc
        self.crs_data = crs_data
        self.n_workers_mm = Parallel.get_num_min_cpus(n_workers_mm)
        self.n_workers_pm = Parallel.get_num_min_cpus(n_workers_pm)
        self.max_distance = max_distance
        self.max_angle = max_angle
        self.n_cpus = max(self.n_workers_mm, self.n_workers_pm)
        self.log.info(f"Initializing Parallel...")
        Parallel.initialize_parallel(
            engine=self.parser.ini.PARALLEL_ENGINE,
            num_cpus=self.n_cpus,
            address=self.parser.ini.PARALLEL_CLUSTER_ADDRESS,
        )
        self.log.info(f"Parallel initialized with {Parallel.num_cpus} workers")

    def load_graph(self, df_links=None):
        # self.log.info(f"Loading graph data")
        if df_links is None:
            df_links, _, _ = self.loader.load_df_graph()
            self.df_links = gpd.GeoDataFrame(df_links, crs=self.crs_data)
            if self.crs_calc != self.crs_data:
                self.df_links = self.df_links.to_crs(self.crs_calc)
        else:
            self.df_links = df_links
        # self.mm = MapMatching(links_gdf=self.df_links, links_id_col="id", links_direction_col=None)
        # self.log.info(f"Loaded {self.df_links.shape[0]} links")

    def calculate_paths(self, df_links, df_fcd, df_trips, G):
        DEBUG = False

        def fn(tasks, df_links, G):
            # warnings.filterwarnings("ignore", category=RuntimeWarning, append=True)
            tot_paths = PathList(key=lambda p: p["id_trip"])
            for trip, df_fcd in tasks:
                try:
                    if hasattr(trip, "id_zone_o") and pd.notna(trip.id_zone_o):
                        source = int(trip.id_zone_o)
                    else:
                        pto = Point(trip.geometry.coords[0])
                        if df_fcd is None:
                            source = nearest_point_row(
                                df_links=df_links, fcd=None, pt=pto
                            )
                        else:
                            source = nearest_point_row(
                                df_links=df_links, fcd=df_fcd.iloc[0], pt=pto
                            )
                    if hasattr(trip, "id_zone_d") and pd.notna(trip.id_zone_d):
                        target = int(trip.id_zone_d)
                    else:
                        ptd = Point(trip.geometry.coords[-1])
                        if df_fcd is None:
                            target = nearest_point_row(
                                df_links=df_links, fcd=None, pt=ptd
                            )
                        else:
                            target = nearest_point_row(
                                df_links=df_links, fcd=df_fcd.iloc[-1], pt=ptd
                            )

                    print(
                        f"Calculating path for trip {trip.id_trip} from {source} to {target}"
                    )
                    paths: PathContainer = trip_dijkstra(
                        graph=G, source=source, targets={target}, trip=trip.geometry
                    )
                    if len(paths) == 0:
                        print(
                            f"No path found for trip {trip.id_trip} from {source} to {target}"
                        )
                        continue
                    for path in paths.all_paths():
                        path["id_trip"] = trip.id_trip
                        path["dt_o"] = trip.dt_o
                        path["dt_d"] = trip.dt_d
                        path["t"] = int(
                            (
                                trip.dt_o.timestamp()
                                - trip.dt_o.replace(
                                    hour=0, minute=0, second=0, microsecond=0
                                ).timestamp()
                            )
                            / 60
                        )
                    tot_paths.merge(paths)
                except Exception as ex:
                    print(f"Error: {ex}")
                    import traceback, sys

                    traceback.print_exc()

            return tot_paths

        old_crs = df_trips.crs
        if df_links.crs != self.crs_calc:
            self.log.info(
                f"Reprojecting links and graph from {df_links.crs} to {self.crs_calc}"
            )
            G = G.st_transform(df_links.crs, self.crs_calc)
            df_links = df_links.to_crs(self.crs_calc)

        if df_trips.crs != self.crs_calc:
            self.log.info(f"Reprojecting trips from {df_trips.crs} to {self.crs_calc}")
            df_trips = df_trips.to_crs(self.crs_calc)

        df_trips = df_trips.assign(geometry=df_trips.geometry.copy())

        tasks = list(df_trips.itertuples())
        tot_paths = PathList(key=lambda p: p["id_trip"])
        if df_fcd is not None:
            grp = df_fcd.groupby("id_trip")
            tasks = [
                (trip, grp.get_group(trip.id_trip).iloc[[0, -1], :]) for trip in tasks
            ]
        else:
            tasks = [(trip, None) for trip in tasks]
        for paths in Parallel.execute(
            fn,
            tasks=tasks,
            df_links=df_links,
            G=G,
            n_workers=1 if DEBUG else self.n_workers_pm,
        ):
            if paths is not None and len(paths) > 0:
                tot_paths.merge(paths)
        return tot_paths

    def __del__(self):
        try:
            Parallel.shutdown_parallel()
        except Exception as ex:
            pass
