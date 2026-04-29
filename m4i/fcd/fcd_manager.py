from collections import defaultdict, namedtuple
import time
from .map_matching import MapMatching
from ..connectors import Loader
from ..connectors import Writer
from .. import ParamsParser
from .. import IniClass
from ..log import Logger
from ..utils import IPC, to_datetime_auto, to_timedelta_auto, to_namedtuple
from ..utils.parallel import Parallel
from ..base_m4i_model import BaseM4IModel
from typing import Union, Optional, List, Generator, Tuple
import datetime
import pandas as pd
import geopandas as gpd
import numpy as np
from math import hypot
import json
from shapely.geometry import LineString
import shapely
from pytz import timezone
from math import ceil
from datetime import timedelta, datetime


class FCDManager(BaseM4IModel):

    def __init__(self, loader: Loader, writer: Writer, ipc: IPC, **kwargs):
        super().__init__(loader=loader, writer=writer, ipc=ipc, **kwargs)
        self.fcd_parameters = self.parser.get_input_parameters("params.fcd")
        self.tz_data = self.fcd_parameters.get("tz_data", self.ini.TZ_LOCAL)
        self.tz_local = self.ini.TZ_LOCAL

        self.mm: MapMatching  = None
        self.segments_gdf = None
        

    def load_fcd_by_timestamp(self, t_start: datetime, t_end: datetime) -> gpd.GeoDataFrame:
        t_start = to_datetime_auto(t_start, tz_localize=self.tz_data)
        t_end = to_datetime_auto(t_end,tz_localize=self.tz_data)
        self.log.info(f"Loading fcd data between {t_start} and {t_end}")
        dtype = self.parser.get_dtype("fcd")
        df_fcd = self.loader.load(
                    path="params.fcd",
                    filters=[[["timestamp",">=",t_start.strftime("%Y-%m-%d %H:%M:%S%z")], ["timestamp","<",t_end.strftime("%Y-%m-%d %H:%M:%S%z")]]],
                    dtype=dtype,                    
                    )        
        # if geomertry is empty build with x and y and crs_data
        if df_fcd is None or df_fcd.empty:                        
            return df_fcd
        if "geometry" not in df_fcd.columns or df_fcd["geometry"].isnull().all():
            if "x" in df_fcd.columns and "y" in df_fcd.columns:
                df_fcd["geometry"] = gpd.points_from_xy(df_fcd["x"], df_fcd["y"])
            else:
                raise ValueError("No geometry or x/y columns found in FCD data.")
        #df_fcd = gpd.GeoDataFrame(df_fcd, crs=crs_data)
        ts = pd.to_datetime(df_fcd["timestamp"],errors="coerce")
        if ts.dt.tz is None:
            df_fcd["timestamp"] = ts.dt.tz_localize(self.tz_data)
        df_fcd["timestamp"] = ts.dt.tz_convert(self.tz_local)
        #if crs_data != crs_calc:
        #    df_fcd = df_fcd.to_crs(crs_calc)
        df_fcd["new"]=True
        df_fcd["x"] = df_fcd.geometry.x
        df_fcd["y"] = df_fcd.geometry.y
        return df_fcd
    
    def build_trips(self, 
                 df_fcd: Union[pd.DataFrame, gpd.GeoDataFrame], 
                 crs_calc: Optional[str] = None,
                 signal_break_max_dt: Optional[float] = None, signal_break_dt: Optional[float] = None, 
                 signal_break_v: Optional[float] = None,
                 stop_o_ds: Optional[float] = None, stop_d_ds: Optional[float] = None,
                 signal_cont_dt: Optional[float] = None, signal_cont_v: Optional[float] = None,
                 max_v3: Optional[float] = None,
                 max_distance_override: Optional[float] = None,
                 min_length: Optional[float] = None,
                 min_time:Optional[float] = None,
                 remove_stops:Optional[float] = None,
                 max_distance_between_data:Optional[float] = None,
                 max_delta_progr:Optional[float] = None,
                 limited_to: Optional[List[str]] = None,
                 t_begin: Optional[datetime] = None,
                 t_finish: Optional[datetime] = None,
                 add_truncated_trips: bool = True,
                 t_end: Optional[datetime] = None,
               ) -> Generator[Tuple[pd.DataFrame,pd.DataFrame], None, None]:
        self.df_fcd = df_fcd
        self.crs_calc = crs_calc or self.ini.CRS_CALC        
        self.signal_break_max_dt = signal_break_max_dt if signal_break_max_dt is not None else self.ini.FCD_TRIPS_SIGNAL_BREAK_MAX_DT 
        self.signal_break_dt = signal_break_dt if signal_break_dt is not None else self.ini.FCD_TRIPS_SIGNAL_BREAK_DT
        self.signal_break_v = signal_break_v if signal_break_v is not None else self.ini.FCD_TRIPS_SIGNAL_BREAK_V
        self.stop_o_ds = stop_o_ds if stop_o_ds is not None else self.ini.FCD_TRIPS_STOP_O_DS
        self.stop_d_ds = stop_d_ds if stop_d_ds is not None else self.ini.FCD_TRIPS_STOP_D_DS
        self.signal_cont_dt = signal_cont_dt if signal_cont_dt is not None else self.ini.FCD_TRIPS_SIGNAL_CONT_DT
        self.signal_cont_v = signal_cont_v if signal_cont_v is not None else self.ini.FCD_TRIPS_SIGNAL_CONT_V
        self.max_v3 = max_v3 if max_v3 is not None else self.ini.FCD_TRIPS_MAX_V3
        self.max_distance_override = max_distance_override if max_distance_override is not None else self.ini.FCD_TRIPS_MAX_DISTANCE_OVERRIDE_POSITION_FIRST_POINT
        self.min_length = min_length if min_length is not None else self.ini.FCD_TRIPS_MIN_LENGTH
        self.min_time = min_time if min_time is not None else self.ini.FCD_TRIPS_MIN_TIME
        self.remove_stops = remove_stops if remove_stops is not None else self.ini.FCD_TRIPS_REMOVE_STOPS
        self.max_distance_between_data = max_distance_between_data if max_distance_between_data is not None else self.ini.FCD_TRIPS_MAX_DISTANCE_BETWEEN_DATA
        self.max_delta_progr = max_delta_progr if max_delta_progr is not None else self.ini.FCD_TRIPS_MAX_DELTA_PROGR
        self.limited_to = limited_to
        self.t_begin = to_datetime_auto(t_begin) if t_begin is not None else None
        self.t_finish = to_datetime_auto(t_finish) if t_finish is not None else None
        self.add_truncated_trips = add_truncated_trips
        self.t_end = to_datetime_auto(t_end) if t_end is not None else df_fcd["timestamp"].max()

        DEBUG = False
        class NTuple:
            def __init__(self, **kwargs):
                for k,v in kwargs.items():
                    if isinstance(v,dict):
                        self.__dict__[k]=NTuple(**v)
                    else:
                        self.__dict__[k]=v
        params = NTuple(**{k:v for k,v in self.__dict__.items() if (not k.startswith("_")) and (v is None or isinstance(v, (int, float, str, bool, datetime, timedelta)))})
        
        
        def process_single_vehicle(tasks: list[pd.DataFrame]) -> Tuple[pd.DataFrame, pd.DataFrame]:
            ret_df_trips = None
            ret_df_fcd_truncated = None
            for vehicle_df in tasks:
                df_trips, df_fcd_truncated = FCDManager._process_single_vehicle(params, vehicle_df, DEBUG)
                if df_trips is not None and len(df_trips) > 0:
                    if ret_df_trips is None:
                        ret_df_trips = df_trips
                    elif df_trips is not None and len(ret_df_trips) > 0:
                        ret_df_trips = pd.concat([ret_df_trips, df_trips], ignore_index=True)

                if df_fcd_truncated is not None and len(df_fcd_truncated) > 0:    
                    if ret_df_fcd_truncated is None:
                        ret_df_fcd_truncated = df_fcd_truncated
                    elif df_fcd_truncated is not None and len(df_fcd_truncated) > 0:
                        ret_df_fcd_truncated = pd.concat([ret_df_fcd_truncated, df_fcd_truncated], ignore_index=True)
            return ret_df_trips, ret_df_fcd_truncated
                

        df_fcd = df_fcd.copy()
        if "x" not in df_fcd.columns or "y" not in df_fcd.columns:
            df_fcd["x"] = df_fcd.geometry.x
            df_fcd["y"] = df_fcd.geometry.y
        df_fcd = pd.DataFrame(df_fcd)
        df_fcd["geometry"] = shapely.to_wkt(df_fcd["geometry"])
        #df_fcd.drop(columns=["geometry"], inplace=True, errors="ignore")
        #df_fcd["timestamp"] = df_fcd["timestamp"].dt.tz_convert("UTC")
        
        tasks = [df for _,df in df_fcd.groupby("id_veh")]
        df_trips:pd.DataFrame = None
        df_fcd_truncated:pd.DataFrame = None
        ret_df_trips:pd.DataFrame = None
        ret_df_fcd_truncated:pd.DataFrame = None
        
        for df_trips, df_fcd_truncated in Parallel.execute(process_single_vehicle, tasks, n_workers=1 if DEBUG else self.parser.ini.FCD_TRIPS_CPUS):
            if df_trips is not None and len(df_trips) > 0:
                #df_trips["dt_o"] = df_trips["dt_o"].dt.tz_convert(self.ini.FCD_SERVER_TZ_DATA)
                #df_trips["dt_d"] = df_trips["dt_d"].dt.tz_convert(self.ini.FCD_SERVER_TZ_DATA)
                if ret_df_trips is None:
                    ret_df_trips = df_trips
                else:
                    ret_df_trips = pd.concat([ret_df_trips, df_trips], ignore_index=True)
            if df_fcd_truncated is not None and len(df_fcd_truncated) > 0:
                #if df_fcd_truncated["timestamp"].dt.tz is None:
                #    df_fcd_truncated["timestamp"] = df_fcd_truncated["timestamp"].dt.tz_localize(self.ini.FCD_SERVER_TZ_DATA)
                #else:
                #    df_fcd_truncated["timestamp"] = df_fcd_truncated["timestamp"].dt.tz_convert(self.ini.FCD_SERVER_TZ_DATA)
                if ret_df_fcd_truncated is None:
                    ret_df_fcd_truncated = df_fcd_truncated
                else:
                    ret_df_fcd_truncated = pd.concat([ret_df_fcd_truncated, df_fcd_truncated], ignore_index=True)
            
        if ret_df_trips is not None:
            ret_df_trips=gpd.GeoDataFrame(ret_df_trips, crs=self.crs_calc, geometry=shapely.from_wkt(ret_df_trips["geometry"]))
        if ret_df_fcd_truncated is not None:
            ret_df_fcd_truncated=gpd.GeoDataFrame(ret_df_fcd_truncated, crs=self.crs_calc, geometry=shapely.from_wkt(ret_df_fcd_truncated["geometry"]))
        return ret_df_trips, ret_df_fcd_truncated
        

    def set_fcd(self, fcd):
        self.fcd = fcd

    def update_fcd(self, new_fcd):
        self.fcd.update(new_fcd)
    
    @staticmethod
    def _process_single_vehicle(params: namedtuple, vehicle_df: pd.DataFrame, DEBUG:bool = False) -> Tuple[pd.DataFrame,pd.DataFrame]:    
        start_cols = [c for c in vehicle_df.columns]
        vehicle_df["ts"]=vehicle_df["timestamp"].dt.as_unit("s").astype("int64")
        vehicle_df = vehicle_df.sort_values(["id_veh","ts"])
        if "progr" not in vehicle_df.columns or vehicle_df["progr"].isnull().all():
            # calculate euclidean progression if not present respect to previous point
            vehicle_df["progr"] = np.sqrt((vehicle_df["x"].diff() ** 2) + (vehicle_df["y"].diff() ** 2)).fillna(0).cumsum()

            
        ret: list = []  # results
        trip_fcds: list = []  # list of FCDs in a trip

        fcd_prev = None  # previous FCD of vehicle
        fcd_next = None  # next FCD of vehicle
        new_trip: bool = False

        i_mobile: int = -1
        skip_fcd_prev=False
        fcds = list(vehicle_df.itertuples(index=False))
        checkstate = {}
        error_in_max_distance = False
        truncated_fcds = []
        for i, fcd in enumerate(fcds):
            new_trip = False

            if not skip_fcd_prev:
                fcd_prev = fcds[i - 1] if i > 0 and len(trip_fcds) > 0 else None
            fcd_next = fcds[i + 1] if i < len(fcds) - 1 else None
            fcd_next = fcd_next if fcd_next is not None and fcd_next.id_veh == fcd.id_veh else None

            if fcd_prev is not None:
                # conditions of outlier or wrong samples
                if fcd_prev.ts == fcd.ts:#and fcd_prev.progr == fcd.progr and fcd_prev.x == fcd.x and fcd_prev.y == fcd.y:  # delete 2 samples with same timestamp
                    checkstate.setdefault("duplicate",defaultdict(int))
                    checkstate["duplicate"]["ts"] += 1
                    skip_fcd_prev = True
                    continue
                elif fcd_prev.x == fcd.x and fcd_prev.y == fcd.y:  # delete 2 samples with same posizion:
                    skip_fcd_prev = True
                    checkstate.setdefault("duplicate",defaultdict(int))
                    checkstate["duplicate"]["pos"] += 1
                    continue
                else:
                    skip_fcd_prev = False

                #assert fcd_prev.dt < fcd.dt, "Data are not sorted chronologically"

                # calculation of euclidean speed between 2 successive samples
                euc_dist = hypot(fcd_prev.x - fcd.x, fcd_prev.y - fcd.y)
                tt = float(fcd.ts - fcd_prev.ts)
                v_euc = euc_dist / tt

                # conditions of starting a new trip
                if fcd_prev.id_veh != fcd.id_veh:  # changed vehicle
                    if DEBUG:
                        print("new_trip: changed vehicle: %s -> %s", fcd_prev.id_veh, fcd.id_veh)
                        print("Start procedure to reconstruction of trajectory for id_vehicle '%s' id %s", fcd.id_veh, fcd.id_fcd)
                    checkstate["start"] = "new_vehicle"
                    new_trip = True
                elif fcd.engine == 0:  # engine ignition
                    if DEBUG:
                        print("new_trip: engine ignition in %s", fcd.id_fcd)
                    checkstate["start"] = "engine_0"
                    new_trip = True
                elif fcd_prev.engine == 2:  # engine shutdown in previous fcd
                    if DEBUG:
                        print("new_trip: engine shutdown in %s", fcd.id_fcd)
                    checkstate["start"] = "prev_engine_2"
                    new_trip = True
                elif fcd.progr < fcd_prev.progr:
                    if DEBUG:
                        print("new_trip: negative progr in %s", fcd.id_fcd)
                    checkstate["start"] = "progr_reverse"
                    new_trip = True
                elif fcd.progr - fcd_prev.progr > params.max_delta_progr:
                    if DEBUG:
                        print("new_trip: maximum delta progr between 2 fcd %s", fcd.id_fcd)
                    checkstate["start"] = "max_delta_progr"
                    new_trip = True
                elif tt > params.signal_break_max_dt:
                    if DEBUG:
                        print("new_trip: max-t signal interruption  (t=%d, v=%.2f, d=%.1f) in %s", tt, v_euc, euc_dist, fcd.id_fcd)
                    checkstate["start"] = "signal_break_max_dt"
                    new_trip = True
                elif tt > params.signal_break_dt and v_euc < params.signal_break_v:  # signal interruption and very low speed
                    if DEBUG:
                        print("new_trip: signal interruption (t=%d, v=%.2f, d=%.1f) in %s", tt, v_euc, euc_dist, fcd.id_fcd)
                    checkstate["start"] = "signal_break_v"
                    new_trip = True
                elif fcd_next is not None:
                    euc_dist2 = hypot(fcd_next.x - fcd.x, fcd_next.y - fcd.y)
                    tt2 = float(fcd_next.ts - fcd.ts)
                    if tt2 > 0:
                        v_euc2 = euc_dist2 / tt2
                        if v_euc > params.max_v3 and v_euc2 > params.max_v3:  # exclude current fcd
                            if DEBUG:
                                print("exclude fcd: max_v3 (v-ab=%.2f, v-bc=%.2f) in %s", v_euc, v_euc2, fcd.id_fcd)
                            checkstate.setdefault("ignore",set())
                            checkstate["ignore"].add("max_v3")
                            continue
                        # exclude first fcd
                        elif v_euc > params.max_v3 > v_euc2 and len(trip_fcds) == 1:
                            if DEBUG:
                                print("remove first fcd: max_v3 (v-ab=%.2f, v-bc=%.2f) in %s", v_euc, v_euc2, fcd.id_fcd)
                            trip_fcds = []
                            checkstate.clear()
                            checkstate["start"] = "max_v3"
                            new_trip = True

                if not new_trip:
                    if euc_dist>params.max_distance_between_data:
                        error_in_max_distance = True
                    # conditions on the calculated speed in a point interval
                    # used to identify a stop in the presence of a continuous and uninterrupted signal
                    euc_dist_mobile = hypot(trip_fcds[i_mobile].x - fcd.x, trip_fcds[i_mobile].y - fcd.y)
                    tt_mobile = float(fcd.ts - trip_fcds[i_mobile].ts)
                    v_euc_mobile = euc_dist_mobile / tt_mobile

                    if tt_mobile > params.signal_cont_dt:
                        if v_euc_mobile < params.signal_cont_v:  # uninterrupted signal and very slow speed
                            if DEBUG:
                                print("new_trip: uninterrupted signal (t=%d, v=%.2f, d=%.1f) in %s-%s", tt_mobile, v_euc_mobile, euc_dist_mobile, trip_fcds[i_mobile].id_fcd,fcd.id_fcd)
                            checkstate["start"] = "signal_cont_v"
                            new_trip = True
                            # remove all intermediate FCDs
                            trip_fcds = trip_fcds[:i_mobile]
                        else:
                            while i_mobile < len(trip_fcds) and float(fcd.ts - trip_fcds[i_mobile].ts) > params.signal_cont_dt:
                                i_mobile += 1

            else:
                error_in_max_distance = False
                checkstate["start"] = "first_fcd"
                new_trip = True

            # the last FCD is added if records has finished.
            if fcd_next is None and not new_trip:
                new_trip = True
                trip_fcds.append(fcd)
                if params.add_truncated_trips and fcd.timestamp > params.t_end - timedelta(seconds=params.signal_break_max_dt):
                    truncated_fcds.extend([f for f in trip_fcds])
                    trip_fcds=[]

            if not new_trip:  # if no new_trip add fcd to current list
                trip_fcds.append(fcd)
            elif len(trip_fcds) > 0:
                id_trip = trip_fcds[0].id_fcd
                if DEBUG:
                    print("saving trip %s", id_trip)

                i_mobile = 0
                id_trip = trip_fcds[0].id_fcd
                # checks if the vehicle is stopped at the start
                # and removes the stopping points at the start
                if params.remove_stops:
                    n = len(trip_fcds)
                    if len(trip_fcds) >= 2:
                        o = trip_fcds[0]
                        while len(trip_fcds) >= 2:
                            # checks the distance from origin
                            euc_dist = hypot(
                                o.x - trip_fcds[1].x, o.y - trip_fcds[1].y)
                            if euc_dist < params.stop_o_ds:
                                checkstate.setdefault("remove_start",0)
                                checkstate["remove_start"] += 1
                                trip_fcds = trip_fcds[1:]
                            else:
                                break
                    if n > len(trip_fcds):
                        if DEBUG:
                            print("removed %s records at start in trip %s->%s", n - len(trip_fcds), id_trip, trip_fcds[0].id_fcd)
                        id_trip = trip_fcds[0].id_fcd

                    # checks if the vehicle is stopped at the end
                    # and removes the stopping points at the end
                    n = len(trip_fcds)
                    if len(trip_fcds) >= 2:
                        d = trip_fcds[-1]
                        last_ele = None
                        while len(trip_fcds) >= 2:
                            # checks the distance from destination
                            euc_dist = hypot(trip_fcds[-2].x - d.x, trip_fcds[-2].y - d.y)
                            if euc_dist < params.stop_d_ds:
                                checkstate.setdefault("remove_end",0)
                                checkstate["remove_end"] += 1
                                last_ele = trip_fcds.pop()
                            else:
                                if last_ele is not None:
                                    trip_fcds.append(last_ele)
                                break
                    if n > len(trip_fcds):
                        if DEBUG:
                            print("removed %s records at end in trip %s", n - len(trip_fcds), id_trip)
                        pass

                if error_in_max_distance:
                    lons = [x.x for x in trip_fcds]
                    lon_5 = np.percentile(lons, 5)
                    lon_95 = np.percentile(lons, 95)

                    lats = [x.y for x in trip_fcds]
                    lat_5 = np.percentile(lats, 5)
                    lat_95 = np.percentile(lats, 95)

                    lat_iqr = lat_95 - lat_5
                    lon_iqr = lon_95 - lon_5

                    lat_upper_bound = lat_95 + 1.5 * lat_iqr
                    lat_lower_bound = lat_5 - 1.5 * lat_iqr
                    lon_upper_bound = lon_95 + 1.5 * lon_iqr
                    lon_lower_bound = lon_5 - 1.5 * lon_iqr
                    ilen = len(trip_fcds)
                    trip_fcds = [x for x in trip_fcds if lat_lower_bound <= x.y <= lat_upper_bound and lon_lower_bound <= x.x <= lon_upper_bound]            
                    removed = ilen - len(trip_fcds)
                    if removed>0:
                        if DEBUG:
                            print("removed %s records for max_distance in trip %s", removed, id_trip)
                        checkstate["remove_outliers"] = removed
                    else:
                        new_trip_fcds = [trip_fcds[0]]
                        trip_compare = trip_fcds[0]
                        for ii, f in enumerate(trip_fcds[1:]):
                            if not hypot(f.x - trip_compare.x, f.y - trip_compare.y) > params.max_distance_between_data:
                                new_trip_fcds.append(f)
                                trip_compare = f
                            else:
                                continue
                        trip_fcds = new_trip_fcds
                        removed = ilen - len(trip_fcds)
                        if removed>0:
                            if DEBUG:
                                print("removed %s records for max_distance in trip %s", removed, id_trip)
                            checkstate["remove_outliers"] = removed                            

                first_fcd = trip_fcds[0]
                last_fcd = trip_fcds[-1]

                if len(trip_fcds) < 2:  # remove trips with less than 2 points
                    if DEBUG:
                        print("trip %s with less than 2 points", id_trip)
                    checkstate.clear()
                    checkstate["start"] = "prev_less_than_2_points"
                    trip_fcds = [fcd]  # initiating a new trip
                elif last_fcd.progr - first_fcd.progr < params.min_length:
                    if DEBUG:
                        print("trip %s too short in length", id_trip)
                    checkstate.clear()
                    checkstate["start"] = "prev_less_than_min_length"
                    trip_fcds = [fcd]  # initiating a new trip
                elif last_fcd.ts - first_fcd.ts < params.min_time:
                    if DEBUG:
                        print("trip %s too short in time", id_trip)
                    checkstate.clear()
                    checkstate["start"] = "prev_less_than_min_time"
                    trip_fcds = [fcd]  # initiating a new trip
                else:
                    # create the trip to save                

                    tr = {
                        "id_trip": first_fcd.id_fcd,
                        "id_veh": first_fcd.id_veh,                        
                        "dt_o": first_fcd.timestamp,
                        "dt_d": last_fcd.timestamp,
                        "t_o": first_fcd.ts,    
                        "t_d": last_fcd.ts,
                        "tt": last_fcd.ts - first_fcd.ts,
                        "dist": last_fcd.progr - first_fcd.progr,
                        "avg_speed": np.average([f.speed for f in trip_fcds]),
                        "fcds": [[f.x,f.y] for f in trip_fcds],
                        "id_fcds": [f.id_fcd for f in trip_fcds],
                        "progr_o": first_fcd.progr                   
                    }
                    #print(tr)
                    # calculate connection with previous trip and initialize fields for connection with next trip
                    tr["id_next"] = None
                    tr["p_after"] = params.t_finish - tr["t_d"] if params.t_finish is not None else None
                    if len(ret) > 0 and ret[-1]["id_veh"] == tr["id_veh"]:
                        tr["id_prev"] = ret[-1]["id_trip"]
                        tr["p_before"] = tr["t_o"] - ret[-1]["t_d"]
                        ret[-1]["p_after"] = tr["p_before"]
                        ret[-1]["id_next"] = tr["id_trip"]
                        # connection between with last trip.
                        # the best position of the destination of the last trip is assumed 
                        # to be the first position of the new trip
                        euc_dist = hypot(tr["fcds"][0][0] - ret[-1]["fcds"][-1][0], tr["fcds"][0][1] - ret[-1]["fcds"][-1][1])
                        if euc_dist <= params.max_distance_override:
                            tr["fcds"][0][0] = ret[-1]["fcds"][-1][0]
                            tr["fcds"][0][1] = ret[-1]["fcds"][-1][1]
                            checkstate["override"] = True
                    else:
                        tr["id_prev"] = None
                        tr["p_before"] = tr["t_o"] - params.t_begin if params.t_begin is not None else None
                    tr["geometry"] = f"LINESTRING({','.join([str(f[0]) + ' ' + str(f[1]) for f in tr['fcds']])})"
                    keys = list(checkstate.keys())
                    for key in keys:
                        if isinstance(checkstate[key],set):
                            l = sorted(list(checkstate[key]))
                            del checkstate[key]
                            for x in l:
                                checkstate[key + "_" + x] = True
                        elif isinstance(checkstate[key],list):
                            l = sorted(list(checkstate[key]))
                            del checkstate[key]
                            for x in l:
                                checkstate[key + "_" + x] = True
                    tr["checkstate"] = json.dumps(checkstate)
                    ret.append(tr)  # add the trip ad the result      
                    error_in_max_distance = False
                    checkstate = {}
                    if len(ret)>2:
                        ret[-2]["fcds"] = None    
                    trip_fcds = [fcd]  # initiating a new trip
                    if DEBUG:
                        print("saved trip %s", tr["id_trip"])
            else:
                trip_fcds.append(fcd)
        if len(ret)==0:
            if trip_fcds is not None:
                truncated_fcds.extend([f for f in trip_fcds])
            df = pd.DataFrame(columns=["id_trip", "id_veh", 
                                    "dt_o", "dt_d", "tt", "dist", "avg_speed", 
                                    "id_fcds", "progr_o", "id_prev", "id_next", 
                                    "p_before", "p_after", "checkstate", "geometry"])
        else:
            df = pd.DataFrame(ret).drop(columns=["t_o", "t_d","fcds"])
            numeric_columns = df.select_dtypes(include=[np.number]).columns
            df[numeric_columns] = df[numeric_columns].fillna(np.nan)
            tzname = df["dt_o"].dt.tz.zone
            df = df.astype({"id_trip": 'Int64', "id_veh": str, 
                "dt_o": f"datetime64[ns, {tzname}]", "dt_d": f"datetime64[ns, {tzname}]", "tt": np.float64,
                "dist": np.float64,"avg_speed": np.float64,
                "id_fcds": object, "progr_o": np.float64, "id_prev": 'Int64', "id_next": 'Int64',
                "p_before": np.float64, "p_after": np.float64, "checkstate": str, "geometry": str})        
            df = df[['id_trip', 'id_veh', 
                    'dt_o', 'dt_d', 'tt', 'dist', 'avg_speed', 
                    'id_fcds', 'progr_o', 'id_prev', 'id_next', 
                    'p_before', 'p_after', "checkstate", 'geometry']]        
        if params.add_truncated_trips and len(truncated_fcds) > 0:
            df_truncated_fcds = pd.DataFrame(truncated_fcds, columns=truncated_fcds[0]._fields)
        else:
            df_truncated_fcds = pd.DataFrame(columns=vehicle_df.columns).astype(vehicle_df.dtypes.to_dict())
        df_truncated_fcds = df_truncated_fcds[start_cols]
        return df, df_truncated_fcds
    
    def map_matching_fcd(self, df_fcd: gpd.GeoDataFrame, df_links, links_id_col, links_direction_col, segments_gdf=None) -> gpd.GeoDataFrame:        
        chunksize = chunksize = ceil(len(df_fcd) / Parallel.get_num_cpus(self.parser.ini.FCD_MAP_MATCHING_CPUS))
        tasks = [df_fcd.iloc[i:i + chunksize] for i in range(0, len(df_fcd), chunksize)]
        self.mm = MapMatching(links_gdf=df_links.query("connector==0"), links_id_col=links_id_col, links_direction_col=links_direction_col, segments_gdf=segments_gdf)
        
        def fn(tasks, mm, max_distance, max_angle):

            ret = None
            if len(tasks) == 0:
                return None
            for df in tasks:
                tmp = mm.match(gps_gdf=df,
                        max_distance=max_distance, 
                        max_angle=max_angle, 
                        fcd_id_col="id_fcd",
                        fcd_dir_col="heading",
                        fcd_state_col="engine", 
                        all_matches=True)
                tmp = tmp.merge(df, on="id_fcd", how="left")                
                if ret is None:
                    if tmp is not None and tmp.shape[0] > 0:
                        ret = tmp
                else:
                    if tmp is not None and tmp.shape[0] > 0:
                        ret = pd.concat([ret, tmp], ignore_index=True)        
            if ret is None or ret.shape[0] == 0:
                return None
  
            ret = gpd.GeoDataFrame(ret)
            return ret
        

        ret_mm = None
        for df_mm in Parallel.execute(fn, 
                                      tasks=tasks,
                                      mm=self.mm,
                                      max_distance=self.parser.ini.FCD_MAP_MATCHING_MAX_DISTANCE, 
                                      max_angle=self.parser.ini.FCD_MAP_MATCHING_MAX_ANGLE,
                                      n_workers=self.parser.ini.FCD_MAP_MATCHING_CPUS):
            if ret_mm is None:
                if df_mm is not None and df_mm.shape[0] > 0:
                    ret_mm = df_mm                
            else:
                if ret_mm is not None and ret_mm.shape[0] > 0:
                    ret_mm = pd.concat([ret_mm, df_mm], ignore_index=True)      
        return ret_mm

    def match_fcd(self, fcd_data: pd.DataFrame, old_fcd_data: pd.DataFrame) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
        """
        Match FCD data to the road network using Map Matching algorithm.
        """
        #estraggo i nuovi fcd e li matcho unendonli con i vecchi e ricalcolo i trips
        if old_fcd_data is not None:
            old_fcd_data["new"] = False
        fcd_data["new"] = True
        df_fcd, df_trips = self.build_paths.match_fcd(fcd_data, old_fcd_data)
        if df_fcd is None or df_trips is None:
            self.tic.info("No FCDs or trips to match")
            return None, None
        self.df_fcd = df_fcd 
        # se i trips sono cambiati (dt_d diverso) allora li inserisco tra i trip da calcolare
        df_trips["new"] = True
        n_trips = df_trips.shape[0]        
        if self.df_trips is not None:
            df_trips.set_index('id_trip', inplace=True, drop=True)            
            merged = df_trips.merge(self.df_trips.set_index('id_trip', drop=True), on="id_trip", how='left', suffixes=('_new','_old'))
            changed_ids = merged.loc[merged['dt_d_new'] != merged['dt_d_old']].index
            updated_rows = df_trips.loc[changed_ids].reset_index(drop=False)            
            self.df_trips = pd.concat([self.df_trips,updated_rows]).drop_duplicates(subset=["id_trip"], keep="last")
            #self.df_trips.reset_index(inplace=True)
        else:
            self.df_trips = df_trips
        return self.df_fcd, self.df_trips    