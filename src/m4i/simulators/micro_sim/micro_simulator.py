# -*- coding: utf-8 -*-
"""
Created on Wed Oct 27 11:27:43 2021

@author: Natalia
"""

import copy
import typing
from .particle import car
from ...graphs import AbstractGraph, KPathList
from .. import BaseSimulator
from ...connectors import Loader
from ...utils import min2hhmm

import math
import numpy as np
import pandas as pd
from operator import itemgetter
import random
import logging
import time
import geopandas as gpd
from shapely import LineString
from shapely.ops import substring


unroll_results = False

from operator import attrgetter

sort_fun = attrgetter("c_l_ti")  # use operator since it's faster than lambda


class SigNode:
    def __init__(self, graph, id, node, simustep, lim=None):
        self.G: AbstractGraph = graph
        self.id = id
        self.Cycle = node["cycle"]
        self.phases = {}
        self.res = []

        for phase in node["phases"]:
            self.G.get_link(phase["from_link"])["signalized"] = True

            key = (
                (phase["from_link"], phase["via_link"], phase["to_link"])
                if "via_link" in phase
                else (phase["from_link"], phase["to_link"])
            )

            self.phases[key] = phase
            self.G["signalized_links"].add(phase["from_link"])
            self.G["signalized_turns"][key] = {}
            self.G["signalized_turns"][key]["state"] = "green"
            self.G["signalized_turns"][key]["type"] = phase["type"]

            if phase["t_start"] % simustep != 0:
                phase["t_start"] = -(-phase["t_start"] // simustep) * simustep
            if phase["t_end"] % simustep != 0:
                phase["t_end"] = -(-phase["t_end"] // simustep) * simustep

            if phase["type"] == "left_turn":
                if phase["permitted"] == True:
                    self.G["signalized_turns"][key]["permitted"] = True
                    self.G["signalized_turns"][key]["opposite_turn"] = phase["opposite_turn"]
                    self.G["signalized_turns"][key]["permitted_movs"] = 2

    def update_cap(self, t, t1):
        "Signalized node model"
        tt = t1 * 60 % self.Cycle
        for key, phase in self.phases.items():
            self.res.append(
                [
                    phase["from_link"],
                    phase["to_link"],
                    t1,
                    self.G["signalized_turns"][key]["state"],
                    phase["type"],
                ]
            )

            if tt == phase["t_start"]:
                self.G["signalized_turns"][key]["state"] = "green"

            elif tt == phase["t_end"]:
                self.G["signalized_turns"][key]["state"] = "red"

    def update_graph(self, new_graph):
        for k, v in self.G["signalized_turns"].items():
            new_graph["signalized_turns"][k] = v
        self.G = new_graph


class YieldNode:
    def __init__(self, graph, node, lim=None, filt=None):
        self.G = graph
        self.idx = node
        bws = graph["bwsl"][node]
        fws = graph["fwsl"][node]

        bws_links = sorted(bws, key=lambda link: link["v0"])

        self.main_links = [bws_links[1]]
        self.yield_links = [bws_links[0]]
        self.lim = lim if lim else 1
        self.filt = filt if filt else 10

    def update_cap(self):
        "Yield capacity model"
        main_cap = sum([ix["inflow_cap"] * self.filt for ix in self.main_links])
        main_flow = sum([ix["ent_veh_f"] * self.filt for ix in self.main_links])
        perc = (1 - self.lim) * math.exp(-5.4 / main_cap * main_flow) + self.lim

        for link in self.yield_links:
            link["inflow_cap"] = link["inflow_cap"] * perc

        p = sum([link["l_queue"] / link["length"] for link in self.yield_links])
        if p > 0.3:
            for link in self.main_links:
                link["inflow_cap"] = link["inflow_cap"] * 0.85


class MicroSimulator(BaseSimulator):
    def __init__(self, loader: Loader, monitored_links=None, yield_nodes=None, **kwargs):
        super().__init__(loader=loader, **kwargs)
        self.simustep = self.loader.ini.SIMU_STEP  # [s] simulation step in seconds
        self.G: AbstractGraph = self.loader.G
        # TODO: sostiture con OUTPUT_AGG_INT
        if hasattr(self.loader.ini, "AGG_INT"):
            self.agg_int = self.loader.ini.AGG_INT  # [m] aggregation of results
        elif hasattr(self.loader.ini, "OUTPUT_AGG_INT"):
            self.agg_int = self.loader.ini.OUTPUT_AGG_INT  # [m] aggregation of results

        self.deltat = self.simustep / 60  # [min] simulation delta t
        self.t_slice = self.G["delta_t"]  # [min] duration of a simulation slice
        # self.ints_agg = 1
        self.ints_agg = int(self.agg_int * 60 / self.simustep)  # number of simusteps within agg_int
        self.G["q_trace"] = []
        self.G["signalized_turns"] = {}
        self.G["signalized_links"] = set()
        self.ODs = self.loader.OD
        self.origini: list[int] = self.loader.origins.copy()
        self.destinazioni: list[int] = self.loader.destinations.copy()
        self.paths: KPathList = None
        self.monitored_links = monitored_links
        self.yield_nodes: list[YieldNode] = yield_nodes
        self.ind_res = kwargs.get("ind_res", self.loader.ini.OUTPUT_IND_RES)
        self.mon_veh = kwargs.get("mon_veh", self.loader.ini.MONITORED_VEH)
        self.signalized_nodes = [
            SigNode(id=1, node=s_n, graph=self.G, simustep=self.simustep) for s_n in self.loader.sign_nodes
        ]

        self.monitored_flows = []
        self.filt = 10

        self.l_car = self.loader.ini.CAR_LENGTH / 1000
        self.k_jam = 1 / self.l_car
        self.min_speed = self.loader.ini.MIN_SPEED
        self.coef = self.loader.coefficients
        self.links_list = [l["idx"] for l in self.G.get_all_links()]  # list of the links
        self.preload = False

        self.ass_results = []
        self.t = 1
        self.heavy_vehicles_ass = False
        self.heavy_preload = False
        self.conv_table = self.loader.conv_tbl
        self.params = self.set_params()
        self.OD = self.loader.OD
        self.heavy_perc = self.loader.get_perc("h")
        self.vehs: list["car"] = []
        car.ini = loader.ini
        car.ind_res = self.ind_res
        car.mon_veh = self.mon_veh

        self.ini = loader.ini
        self.res = None

    def set_params(self):
        "Set parameters for the simulation"
        if unroll_results:
            links_dict = dict(zip(self.conv_table.id_orig, self.conv_table.id_simpl))
        else:
            links_dict = dict(zip(self.links_list, self.links_list))

        pars = {}
        for mes_type in [
            "lanes",
            "weather",
            "heavy_vehicles_ban",
            "speed_limits",
            "ramps",
        ]:
            measures = self.loader.get_events(mes_type)
            mm = []
            pars[mes_type] = mm
            for measure in measures:
                start_t = measure["start"]
                end_t = measure["end"]
                m = measure.copy()
                arc_list = measure["arc_list"]
                arc_list_agg = list(set([links_dict[link] for link in arc_list if link in links_dict]))
                m["start_t"] = start_t
                m["end_t"] = end_t
                m["arc_list"] = arc_list_agg
                mm.append(m)

        return pars

    def set_closures(self, time_start, time_end):
        "Set closure for the ramps"

        closures = ["ramps", "heavy_vehicles_ban"]
        for event in closures:
            for measure in self.params.get(event, []):
                if (measure["start_t"] >= time_start) & (measure["start_t"] <= time_end):
                    ints = self.G["num_intervals"]
                    for interval in range(ints):
                        t_start = time_start + interval * self.t_slice
                        t_end = t_start + self.t_slice
                        if (measure["start_t"] <= t_start) & (measure["end_t"] >= t_end):
                            for l in measure["arc_list"]:
                                link = self.G.get_link(l)
                                link["time"].set_value(t=interval * self.t_slice, value=9999999)

    def update_network(self, t):
        "Update network based on the parameters"
        self.close_lanes(t)
        self.set_speedlims(t)
        self.update_meteo(t)
        self.close_link(t)

    def close_link(self, t):
        "Close links"
        for measure in self.loader.get_events("closures"):
            if t == measure["start"]:
                for l in measure["arc_list"]:
                    link = self.G.get_link(l)
                    link["storage_cap"] = 0
                    link["disabled"] = True

            elif t == measure["end"] - self.deltat:
                for l in measure["arc_list"]:
                    link = self.G.get_link(l)
                    link["storage_cap"] = max(1, (link["length"] * link["numlanes"]) / self.l_car)
                    link["disabled"] = False

    def set_speedlims(self, t):
        "Update speed limits"
        for measure in self.params["speed_limits"]:
            if t == measure["start_t"]:
                speed = measure["params"]["speed"]
                for l in measure["arc_list"]:
                    link = self.G.get_link(l)
                    link["v0"] = speed
                    link["speed_limit"] = speed
            elif t == measure["end_t"]:
                for l in measure["arc_list"]:
                    link = self.G.get_link(l)
                    link["v0"] = link["default_v0"]
                    link["speed_limit"] = link["default_v0"]

    def update_meteo(self, t):
        "Update meteo events"
        for measure in self.params["weather"]:
            if t == measure["start_t"]:
                params = measure["params"]
                alpha_pioggia = self.coef["Pioggia"][str(params["rain"])]
                alpha_nebbia = self.coef["Nebbia"][str(params["fog"])]
                alpha_vento = self.coef["Vento"][str(params["wind"])]
                alpha_neve = self.coef["Neve"][str(params["snow"])]
                alpha_comb = (
                    alpha_pioggia
                    + alpha_nebbia
                    + alpha_vento
                    + alpha_neve
                    + alpha_nebbia * alpha_pioggia
                    + alpha_nebbia * alpha_neve
                )

                F = max(0.5, 1 - alpha_comb)
                for l in measure["arc_list"]:
                    link = self.G.get_link(l)
                    link["v0"] = link["v0"] * F

            elif t == measure["end_t"]:
                for l in measure["arc_list"]:
                    link = self.G.get_link(l)
                    link["v0"] = link["speed_limit"]

    def close_lanes(self, t):
        "Update lanes closures"
        for measure in self.loader.get_events("lanes"):
            if t == measure["start"]:
                for l in measure["arc_list"]:
                    link = self.G.get_link(l)
                    tl = measure["params"]["type_lanes"]
                    if isinstance(link, str):  # per gestire paramatri tipo ["S","C"]
                        tl = [tl]
                    num_lanes = [self.coef["Corsia"][l] for l in tl]
                    num_lanes = max(num_lanes)  # i caso multiplo allora prende il massimo (veirificare se ha senso)
                    default_capacity = (
                        (link["capacity"] / 60 * self.deltat) / link["default_numlanes"]
                        if link["default_numlanes"] > 0
                        else 0
                    )  # UPDATE: Gemma
                    link["cap_dt"] = link["cap_dt"] - num_lanes * default_capacity
                    link["numlanes"] -= max(num_lanes, 0)  # UPDATE: Gemma
                    link["storage_cap"] = max(1, (link["length"] * link["numlanes"]) / self.l_car)
                    link["n_cl_lanes"] += 1

                    if link["n_cl_lanes"] == link["default_numlanes"]:
                        link["disabled"] = True
                        link["storage_cap"] = 0

            elif t == measure["end_t"]:
                for l in measure["arc_list"]:
                    link = self.G.get_link(l)
                    num_lanes = self.coef["Corsia"][measure["params"]["type_lanes"]]
                    default_capacity = (
                        (link["capacity"] / 60 * self.deltat) / link["default_numlanes"]
                        if link["default_numlanes"] > 0
                        else 0
                    )  # UPDATE: Gemma
                    link["n_cl_lanes"] -= 1
                    link["cap_dt"] = link["cap_dt"] + num_lanes * default_capacity
                    link["numlanes"] += num_lanes
                    link["storage_cap"] = max(1, (link["length"] * link["numlanes"]) / self.l_car)

                    if link["n_cl_lanes"] == 0:
                        link["disabled"] = False
                        link["numlanes"] = link["default_numlanes"]
                        link["storage_cap"] = max(1, (link["length"] * link["numlanes"]) / self.l_car)
                        link["cap_dt"] = link["capacity"] / 60 * self.deltat

    def initialize_graph(self, graph):
        "Initialize graph for the simulation"
        self.G = graph
        self.inx_update = 0
        self.t_slice = graph["delta_t"]

        self.results = []

        self.G.apply_links(self.ini_links)

        if (self.preload) or (self.heavy_preload):
            self.vehs = self.preload_vehs
            print("preload %d vehs" % (len(self.vehs)))
            [veh.update_graph(self.G) for veh in self.vehs]
            [sign.update_graph(self.G) for sign in self.preload_signalized_nodes]
            self.signalized_nodes = self.preload_signalized_nodes
            if self.preload_yield_nodes:
                [yn.update_graph(self.G) for yn in self.preload_yield_nodes]
                self.yield_nodes = self.preload_yield_nodes

            self.res_flow = self.preload_res_flow
            self.num = self.preload_num
            self.preload = False

        else:
            self.vehs = []
            self.num = 0
            self.res_flow = {}
            self.G = graph
            for o in self.origini:
                for d in self.destinazioni:
                    if o != d:
                        self.res_flow[o, d] = 0

    def update_performance(self, tstart, tend):

        self.results = []
        self.ass_results = []

        self.initialize_graph(self.G)

        if self.heavy_vehicles_ass:
            for t in self.int_update:
                self.emission_model(self.OD, self.heavy_perc, tstart, tend)
                self.inx_update += 1
            self.heavy_preload = True
            self.preload_vehs = copy.copy(self.vehs)
            self.preload_signalized_nodes = self.signalized_nodes
            self.preload_graph = self.G
            self.preload_num = self.num
            self.preload_res_flow = {}
            for o in self.origini:
                for d in self.destinazioni:
                    if o != d:
                        self.preload_res_flow[o, d] = 0

            self.heavy_vehicles_ass = False

        else:
            self.run_simulation(tstart, tend)

        return

    def initialize_assignment(self, time_start, time_end):

        self.sim_duration = time_end - time_start  # [min] duration of
        self.simint = int(self.sim_duration / self.deltat)  # number of simulation steps
        self.t = int(time_start * self.simustep)
        self.t_i = self.t
        self.t_f = self.t_i + self.simint
        self.set_closures(time_start, time_end)
        if self.loader.dparams.get("heavy_vehicles_ban", False):
            self.heavy_vehicles_ass = True
        else:
            self.heavy_vehicles_ass = False

        return

    def finalize_assignment(self, time_start, time_end):

        self.preload = True
        self.preload_vehs = self.vehs
        self.preload_res_flow = self.res_flow
        self.preload_graph = self.G
        self.preload_signalized_nodes = self.signalized_nodes
        self.preload_yield_nodes = self.yield_nodes
        self.preload_num = self.num
        self.ass_results += self.results
        self.t = self.t_f

        return

    def set_paths(self, paths):
        self.paths = paths

    def agg_results(self, tstart, tend, agg_int=None):
        "Aggregates results to a GeoDataframe"

        df_aggregated = pd.DataFrame()
        if self.ass_results:
            id_link = "id"
            light_flow_in = "light_flow_in"
            heavy_flow_in = "heavy_flow_in"
            light_flow_out = "light_flow_out"
            heavy_flow_out = "heavy_flow_out"
            max_q = "max_q"
            avg_mov_vehs = "avg_mov_vehs"
            avg_que_vehs = "avg_que_vehs"
            avg_density = "avg_density"
            avg_speed = "avg_speed"
            avg_tt = "avg_tt"
            length = "length"
            v_max = "v0"

            freq = str(self.agg_int) + "min" if self.agg_int >= 1 else str(int(self.agg_int * 60)) + "s"
            # UPDATE: GEMMA - Corretto il time che ora usa date_simulation
            times = pd.date_range(
                start=self.loader.parser.get("start", default=min2hhmm(tstart)),
                end=self.loader.parser.get("end", default=min2hhmm(tend)),
                freq=freq,
            )
            ints = [tstart + i * self.agg_int for i in range(int((tend + 1 - tstart) / self.agg_int))]

            col = [
                "time",
                id_link,
                light_flow_in,
                light_flow_out,
                heavy_flow_in,
                heavy_flow_out,
                max_q,
                avg_mov_vehs,
                avg_que_vehs,
                avg_speed,
                avg_density,
                avg_tt,
                "n_updates",
            ]
            df_aggregated = pd.DataFrame(data=self.ass_results, columns=col)
            df_aggregated[[avg_mov_vehs, avg_que_vehs, avg_speed, avg_density, avg_tt]] = df_aggregated[
                [avg_mov_vehs, avg_que_vehs, avg_speed, avg_density, avg_tt]
            ].div(df_aggregated.n_updates, axis=0)
            dic = {i: time for (i, time) in zip(ints, times)}

            df_aggregated["time"] = df_aggregated.time.map(dic)
            df_aggregated[[light_flow_in, heavy_flow_in, light_flow_out, heavy_flow_out]] = df_aggregated[
                [light_flow_in, heavy_flow_in, light_flow_out, heavy_flow_out]
            ] * (60 / self.agg_int)

            df_aggregated = df_aggregated.astype(
                {
                    id_link: int,
                    light_flow_in: int,
                    heavy_flow_in: int,
                    light_flow_out: int,
                    heavy_flow_out: int,
                    max_q: int,
                    avg_mov_vehs: float,
                    avg_que_vehs: float,
                    avg_speed: float,
                    avg_density: float,
                    avg_tt: float,
                    "n_updates": int,
                    "time": "datetime64[ns]",
                }
            )

            if unroll_results:
                self.conv_table[id_link] = self.conv_table["id_simpl"]
                mapped_result = pd.merge(df_aggregated, self.conv_table, how="outer", on=[id_link, id_link])
                mapped_result[id_link] = mapped_result["id_orig"]
                result = mapped_result[col[:-1]]
                result = result[~result["time"].isna()]
            else:
                result = df_aggregated[col[:-1]]
                result = result[~result["time"].isna()]

        from ...utils import ST_Multi

        links_l = pd.DataFrame(
            [
                [
                    id_link,
                    ST_Multi(self.G.get_link(id_link).get_value("geometry")),
                    self.G.get_link(id_link).get_value(v_max),
                    self.G.get_link(id_link).get_value(length),
                    self.G.get_link(id_link).get_value("numlanes"),
                    self.G.get_link(id_link).get_value("connector"),
                ]
                for id_link in self.loader.df_links[id_link]
            ],
            columns=["id_link", "geometry", v_max, "length", "lanes", "connector"],
        )
        result = pd.merge(result, links_l, left_on=id_link, right_on="id_link", suffixes=("", ""))
        result = gpd.GeoDataFrame(result, geometry="geometry", crs=self.loader.ini.CRS_CALC)

        result[avg_speed] = result[length] / result[avg_tt] * 60
        result[avg_speed] = np.minimum(result[avg_speed], result[v_max])
        result[max_q] = result[max_q].clip(lower=0)
        result["q_length"] = (result["max_q"] / result["lanes"]) * (self.ini.CAR_LENGTH / 1000) / result[length] * 100
        result["q_length"] = result["q_length"].clip(upper=100)

        result = result[
            [
                id_link,
                light_flow_in,
                heavy_flow_in,
                light_flow_out,
                heavy_flow_out,
                max_q,
                avg_mov_vehs,
                avg_que_vehs,
                avg_speed,
                avg_density,
                avg_tt,
                length,
                v_max,
                "geometry",
                "time",
                "q_length",
                "connector",
            ]
        ]

        # TODO: Fare assegnazione multi-classe
        result["mode"] = "all"
        result.rename(
            columns={
                avg_mov_vehs: "mov_vehs",
                avg_que_vehs: "que_vehs",
                avg_speed: "speed",
                avg_density: "density",
                avg_tt: "tt",
                id_link: "id_link",
            },
            inplace=True,
        )
        result_light = result[
            [
                "time",
                "mode",
                "id_link",
                light_flow_in,
                light_flow_out,
                max_q,
                "mov_vehs",
                "que_vehs",
                "speed",
                "density",
                "tt",
                "geometry",
                "q_length",
                "connector",
            ]
        ].copy()
        result_light["mode"] = "c"
        result_light.rename(columns={light_flow_in: "flow_in", light_flow_out: "flow_out"}, inplace=True)

        result_heavy = result[
            [
                "time",
                "mode",
                "id_link",
                heavy_flow_in,
                heavy_flow_out,
                max_q,
                "mov_vehs",
                "que_vehs",
                "speed",
                "density",
                "tt",
                "geometry",
                "q_length",
                "connector",
            ]
        ].copy()
        result_heavy["mode"] = "h"
        result_heavy.rename(columns={heavy_flow_in: "flow_in", heavy_flow_out: "flow_out"}, inplace=True)

        result["flow_in"] = result["light_flow_in"] + result["heavy_flow_in"]
        result["flow_out"] = result["light_flow_out"] + result["heavy_flow_out"]
        result.drop(
            columns=[
                "light_flow_in",
                "heavy_flow_in",
                "light_flow_out",
                "heavy_flow_out",
            ],
            inplace=True,
        )
        result_all = pd.concat([result, result_light, result_heavy], ignore_index=True)
        self.res = result_all
        return result_all[
            [
                "time",
                "mode",
                "id_link",
                "flow_in",
                "flow_out",
                max_q,
                "mov_vehs",
                "que_vehs",
                "speed",
                "density",
                "tt",
                "geometry",
                "q_length",
                "connector",
            ]
        ]

    def agg_stats(self, tstart, tend):
        "Calculate statistics from the results"
        avg_density = "density"
        avg_speed = "speed"
        avg_tt = "tt"
        length = "length"
        v_max = "v0"
        light_flow_out = "flow_out"
        stats = None

        if self.res is None:
            self.agg_results(tstart, tend, agg_int=None)

        try:
            result_stats = self.res.copy().drop(columns="geometry")
            cong_levels = self.ini.OUTPUT_CONG_LEVELS
            deltat = self.agg_int / 60

            def f_stat(dat):
                d = {}
                tot_distance = sum(dat[avg_density] * dat.length)
                if tot_distance == 0:
                    tot_distance = 1
                d["v_avg"] = sum(dat[avg_density] * dat[avg_speed] * dat[length]) / tot_distance  # velocita' media
                d["p_tot"] = sum(dat[avg_density] * dat[avg_speed] * dat[length] * deltat)  # vehi x km
                d["t_tot"] = sum(dat[avg_density] * dat[length] * deltat)  # Tempo veicoli x km
                for i, v0 in enumerate(cong_levels[:-1]):
                    v1 = cong_levels[i + 1]
                    mask = (
                        (dat[avg_speed] > v0 * dat[v_max])
                        & (dat[avg_speed] <= v1 * dat[v_max])
                        & (dat[light_flow_out] > 0)
                    )
                    tot_distance = sum(dat[length][dat[light_flow_out] > 0])
                    if tot_distance == 0:
                        tot_distance = 1
                    perc = sum(dat[length][mask]) / tot_distance
                    d[f"cong_{int(v0 * 100)}"] = perc

                mask = (
                    (dat[avg_speed] > 0)
                    & (dat[avg_speed] <= self.ini.LOS_CRITICO * dat[v_max])
                    & (dat[light_flow_out] > 0)
                )
                d[f"avg_t_cong"] = len(dat["time"][mask].unique()) * self.agg_int
                d[f"max_avg_tt"] = dat.groupby("time").sum().max()["tt"]
                d[f"min_avg_tt"] = dat.groupby("time").sum().min()["tt"]
                d[f"arrived"] = sum([1 for veh in self.vehs if veh.status == "arrived"])

                return pd.Series(d)

            # """
            segment = self.loader.links_sets

            stat = []
            for seg, links in segment.items():
                mask = result_stats["id_link"].isin(links)
                if mask.any():
                    _ = f_stat(result_stats[mask])
                    _["segment_id"] = seg
                    stat.append(_)
            if stat:
                stats = pd.concat(stat, axis=1).T

            return stats
        except Exception as e:
            print(f"Exception calc_stats {e} ")
            return None

    def get_trace_res(self, tstart, tend):
        "Get vehicles trace results"
        geo_trace = None

        if self.ind_res:
            geo_result = None
            geo_trace = None

            shape = self.loader.df_links.copy()
            if not isinstance(shape, gpd.GeoDataFrame):
                from shapely import wkb

                if "geom" in shape.columns:
                    try:
                        shape["geometry"] = shape["geom"].apply(lambda x: wkb.loads(bytes.fromhex(x)))
                    except:
                        shape["geometry"] = shape["geom"].apply(wkb.loads)

                    shape = gpd.GeoDataFrame(shape, geometry="geometry", crs=self.loader.ini.CRS_CALC)
                else:
                    raise ValueError("DataFrame does not contain a 'geom' column for geometry conversion.")

            id_link = "id"
            shape.set_index(id_link, inplace=True)

            shape = shape.to_crs(epsg=int(self.ini.CRS_CALC.split(":")[-1]))

            agg_trace = int(self.simustep)
            tot_data = []
            for veh in self.vehs:
                if veh.monitored_veh:
                    tot_data.extend(veh.trace)

            if len(tot_data) > 0:
                trace_res = pd.DataFrame(tot_data, columns=["t", "p", "id_link", "status", "id"])
            else:
                trace_res = pd.DataFrame(columns=["t", "p", "id_link", "status", "id"])

            trace_res = trace_res.astype({"t": float, "p": float, "id_link": int, "status": str, "id": int})
            # UPDATE: GEMMA - Corretto il time che ora usa date_simulation
            times = pd.date_range(
                start=self.loader.parser.get("start", default=min2hhmm(tstart)),
                end=self.loader.parser.get("end", default=min2hhmm(tend)),
                freq=str(agg_trace) + "s",
            )
            # times = pd.date_range(start=min2hhmm(tstart), end=min2hhmm(tend), freq=str(agg_trace)+'s')
            dic = {tstart + i / 60: time for (i, time) in zip(range(0, (tend - tstart) * 60, agg_trace), times)}

            trace_res["time"] = trace_res.t.map(dic)
            trace_res = trace_res[~trace_res["time"].isna()]
            trace_res = trace_res[trace_res["status"].isin(["mov", "queue"])]
            trace_res = trace_res.astype({"id_link": int, "p": float, "id_link": int, "time": "datetime64[ns]"})
            trace_res = trace_res.join(shape, on="id_link")

            def point(geo, p):
                return geo.line_interpolate_point(p, normalized=True)

            def angle(geom, p, eps=1e-4):
                if p <= 0:
                    p1 = geom.interpolate(0, normalized=True)
                    p2 = geom.interpolate(eps, normalized=True)
                elif p >= 1:
                    p1 = geom.interpolate(1 - eps, normalized=True)
                    p2 = geom.interpolate(1, normalized=True)
                else:
                    p1 = geom.interpolate(p, normalized=True)
                    p2 = geom.interpolate(min(p + eps, 1), normalized=True)
                dx = p2.x - p1.x
                dy = p2.y - p1.y

                return math.degrees(math.atan2(dy, dx))

            def azimuth_tangent_robust(geom, p, delta=0.01):
                start = max(p - delta, 0)
                end = min(p + delta, 1)

                seg = substring(geom, start, end, normalized=True)
                coords = list(seg.coords)

                x1, y1 = coords[0]
                x2, y2 = coords[-1]

                az = math.degrees(math.atan2(x2 - x1, y2 - y1))
                return (az + 360) % 360

            if trace_res.empty:
                trace_res = trace_res.assign(point=None, rotation=None)
            else:
                trace_res["point"] = trace_res.apply(lambda row: point(row.geometry, row.p), axis=1)
                trace_res["rotation"] = trace_res.apply(lambda row: azimuth_tangent_robust(row.geometry, row.p), axis=1)
            geo_trace = gpd.GeoDataFrame(
                data=trace_res[["id", "id_link", "time", "status", "p", "rotation"]],
                geometry=trace_res["point"],
                crs=self.ini.CRS_CALC,
            )

            geo_trace = geo_trace.to_crs(crs=self.loader.ini.CRS_CALC)

            geo_trace = geo_trace.astype({"id": int, "id_link": int, "rotation": float, "time": "datetime64[ns]"})

            return geo_trace

    def get_signalized_res(self, tstart, tend):
        "Get signalized nodes results"
        sign_res = pd.DataFrame(columns=["id_from", "id_to", "t", "type", "status"]).astype(
            {"id_from": int, "id_to": int, "t": int, "type": str, "status": str}
        )
        agg_trace = int(self.simustep)
        # UPDATE: GEMMA - Corretto il time che ora usa date_simulation
        times = pd.date_range(
            start=self.loader.parser.get("start", default=min2hhmm(tstart)),
            end=self.loader.parser.get("end", default=min2hhmm(tend)),
            freq=str(agg_trace) + "s",
        )
        # times = pd.date_range(start=min2hhmm(tstart), end=min2hhmm(tend), freq=str(agg_trace)+'s')#range(0, self.simint);
        dic = {tstart + i / 60: time for (i, time) in zip(range(0, (tend - tstart) * 60, agg_trace), times)}

        if self.signalized_nodes:
            for node in self.signalized_nodes:
                sig_res = pd.DataFrame(data=node.res, columns=sign_res.columns)
                sign_res = pd.concat([sign_res, sig_res], axis=0)

            sign_res.columns = ["id_from", "id_to", "t", "type", "status"]
            sign_res["time"] = sign_res.t.map(dic)
            sign_res.t.map(dic)

            shape = self.loader.df_links.copy()
            if not isinstance(shape, gpd.GeoDataFrame):
                from shapely import wkb

                if "geom" in shape.columns:
                    try:
                        shape["geometry"] = shape["geom"].apply(lambda x: wkb.loads(bytes.fromhex(x)))
                    except:
                        shape["geometry"] = shape["geom"].apply(wkb.loads)

                    shape = gpd.GeoDataFrame(shape, geometry="geometry", crs=self.loader.ini.CRS_CALC)
                else:
                    raise ValueError("DataFrame does not contain a 'geom' column for geometry conversion.")

            id_link = "id"
            shape = shape.to_crs(crs=self.loader.ini.CRS_CALC)
            sign_res = shape.merge(sign_res, left_on=id_link, right_on="id_from").to_crs(epsg=4326)

            return sign_res

    def emission_model(self, od, heavy_perc, tstart, tend):
        "Emission model"

        ints = self.G["num_intervals"]
        n = self.inx_update
        if n < ints:
            for o in self.origini:
                for d in self.destinazioni:
                    if o != d:
                        fod = (
                            od[o, d, tstart + n * self.t_slice] * (self.t_slice / 60) + self.res_flow[o, d]
                        )  # sum the residual flow from previous int

                        if fod > 0.5:  # at least one vehicle is created
                            heavy_p = heavy_perc[(o, d, tstart + n * self.t_slice)]

                            fod_out = int(round(fod))
                            p = [
                                path["path_flow"] / fod
                                for path in self.paths.paths(
                                    source=o,
                                    target=d,
                                    t_start=n * self.t_slice,
                                    mode="c",
                                )
                            ]
                            k = len(p)
                            tot_flow = sum(p)
                            if k == 0:
                                self.log.warning(
                                    "No paths available for origin %d and destination %d at time %s",
                                    o,
                                    d,
                                    min2hhmm(tstart + n * self.t_slice),
                                )
                                continue
                            if tot_flow > 0:
                                f = random.choices(range(int(k)), p, k=fod_out)
                            else:
                                f = random.choices(range(int(k)), k=fod_out)

                            heavy_toss = random.choices([True, False], weights=[heavy_p, 1 - heavy_p], k=fod_out)
                            delta_emi = self.t_slice / fod_out
                            self.res_flow[o, d] = fod - fod_out

                            for veh in range(len(f)):
                                path = self.paths.path(
                                    source=o,
                                    target=d,
                                    t_start=n * self.t_slice,
                                    mode="c",
                                    k=f[veh],
                                )

                                if (not path) or len(path["links"]) == 0:
                                    # print("no path available for %d-%d "%(o,d))
                                    continue

                                self.num += 1

                                if len(path["links"]) > 1:
                                    veh1 = car(
                                        self.num,
                                        tstart + n * self.t_slice + delta_emi * veh,
                                        path,
                                        self.G,
                                        self.deltat,
                                        heavy=heavy_toss[veh],
                                    )
                                    self.vehs.append(veh1)
                        else:
                            self.res_flow[o, d] = fod

    def run_simulation(self, tstart, tend):
        "Run simulation without tracking"
        self.tstart = tstart
        self.tend = tend
        time_ = time.time()
        self.emission_model(self.OD, self.heavy_perc, tstart, tend)

        ini_t = self.t_i
        fin_t = self.t_f

        int_update = int(self.t_slice / self.deltat)  # number of simulation steps within t_slice
        for t in range(ini_t, fin_t):
            t1 = tstart + (t - ini_t) * self.deltat
            self.update_network(t1)
            self.vehs = self.sim_step(t1, self.vehs)

            if t > ini_t and (t - ini_t) % self.ints_agg == 0:
                self.update_res(t1 - self.ints_agg * self.deltat)
                self.G.apply_links(self.reset_flags)
                self.reset_turns()

            if t > ini_t and (t - ini_t) % int_update == 0:
                # print("moving vehicles %d" % (len(self.vehs)))
                self.G.apply_links(self.t_compute)

                self.inx_update += 1
                self.emission_model(self.OD, self.heavy_perc, tstart, tend)
                self.log.info("updated time for t=%s", min2hhmm(t1))

            self.update_ta(t, t1)
        t = fin_t
        t1 = tstart + (t - ini_t) * self.deltat
        if t > ini_t and (t - ini_t) % self.ints_agg == 0:
            self.update_res(t1 - self.ints_agg * self.deltat)
            self.G.apply_links(self.reset_flags)

        if t > ini_t and (t - ini_t) % int_update == 0:
            # print("moving vehicles %d" % (len(self.vehs)))
            self.G.apply_links(self.t_compute)

            self.inx_update += 1
            self.emission_model(self.OD, self.heavy_perc, tstart, tend)
            self.log.info("update timed for t=%s", min2hhmm(t1))

        elapsed = time.time() - time_

        self.log.info("Tempo caricamento: %2.f secondi" % elapsed)
        self.log.info("Veicoli totali caricati: %d" % self.num)

    def update_nodes(self, t, t1):
        "Update capacities of links of Yeild and Signalized Junctions"
        if self.yield_nodes:
            [node.update_cap() for node in self.yield_nodes]  # update yield nodes
        if self.signalized_nodes:
            [node.update_cap(t, t1) for node in self.signalized_nodes]  # update yield nodes
        # ts_cap() #update signalized nodes

    def yield_cap(self, yield_nodes, G):
        "Yeild capacity model"
        for node in yield_nodes:
            main_flow = sum([G.get_link(ix)["ent_veh"] for ix in node["main_links"]]) * 60 / self.deltat
            main_cap = sum([G.get_link(ix)["cap_dt"] for ix in node["main_links"]]) * 60 / self.deltat
            perc = (1 - node["lim"]) * math.exp(-5.4 / main_cap * main_flow) + node["lim"]

            for link in node["yield_links"]:
                G.get_link(link)["inflow_cap"] = G.get_link(link)["cap_dt"] * perc

            p = sum([G.get_link(ix)["l_queue"] / G.get_link(ix)["length"] for ix in node["yield_links"]])
            if p > 0.3:
                for link in node["main_links"]:
                    G.get_link(link)["inflow_cap"] = G.get_link(link)["cap_dt"] * 0.85

    def order_positions(self, t, vehs):
        "FIFO rule ensured"
        # vehs = [veh for veh in vehs if veh.status!="arrived"]

        vehs = sorted(vehs, key=sort_fun)
        return vehs

    def update_ta(self, t, t1):
        "Update speeds on links based on observed vehicles"
        self.update_nodes(t, t1)
        # self.G.apply_links(self.update_capacities)
        self.G.apply_links(self.update_times)
        # self.G.apply_onset_links(self.G["links_set"], self.update_times)

    def update_res(self, t):
        "Update results vectors with simulated times"

        res = [
            [t]
            + list(
                itemgetter(
                    "idx",
                    "ent_veh",
                    "ex_veh",
                    "ent_veh_h",
                    "ex_veh_h",
                    "max_que",
                    "cum_mov_vehs",
                    "cum_que_vehs",
                    "cum_speed",
                    "cum_density",
                    "cum_tt",
                    "n_updates",
                )(link)
            )
            for link in self.G.get_all_links()
        ]
        self.results += res

    def t_compute(self, link):
        "Compute average of the travel time during time interval"
        link["time"].set_value(
            t=int(self.inx_update * self.t_slice),
            value=link["cum_tt_delta"] / link["n_updates_delta"],
        )
        link["cum_tt_delta"] = link["t0"]
        link["n_updates_delta"] = 1

    def sim_step(self, t, vehs):
        "Simulation step"

        vehs = self.order_positions(t, vehs)
        vehs = list(filter(lambda v: v.move(t), vehs))

        return vehs

    def ini_links(self, link):

        if self.preload:
            if link["length"] == 0:
                link["length"] = 0.1

            if link["v0"] == 0:
                link["v0"] = 80

            if link["t0"] == 0:
                link["t0"] = 0.001

            if math.isnan(link["t0"]):
                link["t0"] = 0.001
                link["v0"] = 80

            link["cap_dt"] = link["capacity"] / 60 * self.deltat  # [veh/deltat]
            link["ex_veh"] = 0
            link["ex_veh_h"] = 0
            link["ent_veh"] = 0
            link["ent_veh_h"] = 0
            pre_link = self.preload_graph.get_link(link["idx"])
            link["storage_cap"] = pre_link["storage_cap"]
            link["inflow_cap"] = link["cap_dt"]
            link["que_vehs"] = pre_link["que_vehs"]
            link["mov_vehs"] = pre_link["mov_vehs"]

            link["speed"] = pre_link["speed"]
            link["cum_density"] = pre_link["cum_density"]
            link["ta"] = pre_link["ta"]
            link["l_queue"] = pre_link["l_queue"]
            link["tt"] = pre_link["tt"]
            link["cum_tt"] = pre_link["cum_tt"]
            link["cum_que_vehs"] = pre_link["cum_que_vehs"]
            link["cum_mov_vehs"] = pre_link["cum_mov_vehs"]
            link["max_que"] = pre_link["max_que"]

            link["n_updates"] = pre_link["n_updates"]
            link["cum_tt_delta"] = pre_link["cum_tt_delta"]
            link["n_updates_delta"] = pre_link["n_updates_delta"]
            link["disabled"] = False
            link["ksi"] = link["ta"] / self.deltat

            if link["ta"] < 6 / 60:
                link["ta"] = 0.0001
                link["t0"] = 0.0001
                link["cap_dt"] = 9999999

        else:
            if link["length"] == 0:
                link["length"] = 0.1
            if link["connector"] == 1:
                link["lanes"] = 100

            if math.isnan(link["v0"]):
                link["v0"] = 80

            if link["v0"] == 0:
                link["v0"] = 80

            if link["t0"] == 0:
                link["t0"] = 0.001

            if math.isnan(link["t0"]):
                link["t0"] = 0.001
                link["v0"] = 80

            link["sp"] = []
            link["cap_dt"] = link["capacity"] / 60 * self.deltat  # [veh/deltat]
            link["flow"].reset(0)
            link["ex_veh_h"] = 0
            link["ex_veh"] = 0
            link["storage_cap"] = max(1, (link["length"] * link["numlanes"]) / self.l_car)
            link["inflow_cap"] = link["cap_dt"]
            link["que_vehs"] = 0
            link["mov_vehs"] = 0

            link["cum_cap"] = 0
            link["cum_veh"] = 0
            link["ent_veh"] = 0
            link["ent_veh_h"] = 0
            link["density"] = 0

            link["speed"] = link["v0"]
            link["last_speed"] = link["speed"]
            link["cum_speed"] = link["v0"]
            link["cum_density"] = 0
            link["t0"] = link["length"] / link["speed"] * 60
            link["ta"] = link["t0"]
            link["l_queue"] = 0
            link["tt"] = link["t0"]
            link["cum_tt"] = link["t0"]
            link["cum_que_vehs"] = 0
            link["cum_mov_vehs"] = 0
            link["max_que"] = 0
            link["ex_q_veh"] = 0
            link["n_updates"] = 1
            link["cum_tt_delta"] = link["t0"]
            link["n_updates_delta"] = 1
            link["default_numlanes"] = link["numlanes"]
            link["default_v0"] = link["v0"]
            link["speed_limit"] = link["v0"]
            link["n_cl_lanes"] = 0
            link["disabled"] = False

            if self.ini.DEBUG:
                link["ex_vehs"] = []
                link["ent_vehs"] = []
                link["storage"] = []
                link["movs_vehs"] = []
                link["speed_obs"] = []

            link["ksi"] = min(1, link["ta"] / self.deltat)

            if link["ta"] < 6 / 60:
                link["ta"] = 0.0001
                link["t0"] = 0.0001
                link["cap_dt"] = 9999999

    def reset_flags(self, link):
        "Reset aggregated values"
        link["ex_veh"] = 0
        link["ent_veh"] = 0
        link["ex_veh_h"] = 0
        link["ent_veh_h"] = 0
        link["speed"] = link["v0"]
        link["cum_speed"] = link["v0"]
        link["cum_que_vehs"] = 0
        link["max_que"] = link["que_vehs"]
        link["cum_mov_vehs"] = 0
        link["cum_density"] = 0
        link["cum_tt"] = link["t0"]
        link["n_updates"] = 1

    def reset_turns(self):
        "Reset aggregated values"
        for turn in self.G["signalized_turns"].values():
            if turn["type"] == "left_turn":
                turn["permitted_movs"] = 2

    def update_capacities(self, link):
        "Update capacity for next time interval"
        if link["inflow_cap"] < 1:
            link["inflow_cap"] += link["cap_dt"]
        else:
            link["inflow_cap"] = link["cap_dt"]

    def update_times(self, link):
        "Update capacity for next time interval"
        link["ex_q_veh"] = 0
        if self.ini.DEBUG:
            link["ex_vehs"].append(link["ex_veh"])
            link["ent_vehs"].append(link["ent_veh"])
            link["storage"].append(link["storage_cap"])

        if link["inflow_cap"] < 1:
            link["inflow_cap"] += link["cap_dt"]
        else:
            link["inflow_cap"] = link["cap_dt"]

        if ((link["disabled"]) or (link["mov_vehs"] > 0) or (link["que_vehs"] > 0)) & (not (link["connector"] == 1)):
            "Update times on links"

            free_link = link["length"] - link["l_queue"]
            if not link["disabled"]:
                if free_link > 0:
                    ff_speed = link["v0"]
                    nv = link["mov_vehs"]
                    if nv >= 0:  # UPDATE: GEMMA
                        density = (nv) / (free_link * link["numlanes"]) if link["numlanes"] > 0 else float("inf")
                    else:
                        density = (nv) / (free_link * link["numlanes"]) if link["numlanes"] > 0 else 0
                    speed = ff_speed * math.exp(-(1 / link["alpha"]) * (density / link["r_cr"]) ** link["alpha"])

                else:
                    density = self.k_jam
                    speed = self.min_speed

                speed = max(self.min_speed, speed)

            if link["disabled"]:
                speed = 0.0000001
                link["storage_cap"] = 0
                density = 0

            link["density"] = density
            speed = link["last_speed"] * (self.filt - 1) / self.filt + speed * (1) / self.filt
            link["last_speed"] = speed

            link["speed"] = speed
            link["cum_speed"] += speed
            link["cum_density"] += density
            link["ta"] = (link["length"] / speed) * 60
            link["ksi"] = min(1, link["ta"] / self.deltat)
            link["l_queue"] = (
                min(link["length"], (link["que_vehs"] * self.l_car / link["numlanes"])) if link["numlanes"] > 0 else 0
            )  # UPDATE: GEMMA
            link["tt"] = link["ta"] + link["que_vehs"] / link["cap_dt"]
            link["cum_tt"] += link["tt"]
            link["cum_que_vehs"] += link["que_vehs"]
            link["cum_mov_vehs"] += link["mov_vehs"]
            link["max_que"] = max(link["max_que"], link["que_vehs"])

            link["n_updates"] += 1
            link["cum_tt_delta"] += link["tt"]
            link["n_updates_delta"] += 1

            if link["ta"] < 6 / 60:
                link["ta"] = 0.0001
                link["cap_dt"] = 9999999
        if self.ini.DEBUG:
            link["movs_vehs"].append(link["mov_vehs"])
            link["speed_obs"].append(link["speed"])
