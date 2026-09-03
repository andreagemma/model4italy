# -*- coding: utf-8 -*-
"""
Created on Fri Oct  1 17:32:40 2021

@author: Natalia
"""

from ... import *
from ...connectors import Loader
import logging, time, traceback
import pandas as pd
from datetime import datetime
import random
import pdb

transfer_condition = {"mov", "queue", "arrived", "sleeping"}
node_conditions = {"queueing", "at node"}


class car:
    ini: IniClass
    loader: Loader
    ind_res: bool
    mon_veh: int

    def __init__(self, id_n, t, path, G, deltat, heavy=None):
        self.deltat = deltat
        self.ID = id_n  # vehicle ID
        self.path_links = path["links"]  # path of vehicle
        self.ent_time = t  # [m] entrance on the network
        self.status = "sleeping"  # status of vehicle
        self.G = G  # graph
        self.signalized_links = G["signalized_links"]
        self.o = path["source"]
        self.d = path["target"]

        self.signalized_turns = G["signalized_turns"]

        self.c_l = 0  # current link
        self.n_l = 1  # next link
        self.s_t = None
        self.q_trace = G["q_trace"]
        self.same_link = False

        if self.ind_res:
            # self.monitored_veh = True if (self.ID%self.mon_veh) == 0 else False # UPDATE: Gemma
            self.monitored_veh = self.ini.rnd.random() < self.mon_veh / 100
        self.trace = []

        self.current_link = self.G.get_link(self.path_links[self.c_l])
        try:
            self.next_link = self.G.get_link(self.path_links[self.n_l])
        except:
            pdb.set_trace()
        self.last_link = self.G.get_link(self.path_links[-1])

        self.current_link["mov_vehs"] += 1  # add one vehicle on the current link link

        self.c_l_ti = self.ent_time  # [m] entrance time on current link

        self.heavy = heavy
        if not self.heavy:
            self.field_ent = "ent_veh"
            self.field_out = "ex_veh"
        elif self.heavy:
            self.field_ent = "ent_veh_h"
            self.field_out = "ex_veh_h"

        self.current_link[self.field_ent] += 1

        self.lt1 = car.ini.LT1 / 60
        self.lt2 = car.ini.LT2 / 60
        self.critical_gap = 5 / 3600

    def update_graph(self, graph):
        self.G = graph
        self.current_link = self.G.get_link(self.path_links[self.c_l])
        self.last_link = self.G.get_link(self.path_links[-1])
        if self.status == "sleeping":
            self.current_link["mov_vehs"] += (
                1  # add one vehicle on the current link link
            )
            self.current_link[self.field_ent] += 1

    def link_transfer(self, t):

        tt = t + self.deltat
        dt = self.c_l_tf - self.c_l_ti

        if dt == 0:
            s_t = 1
        else:
            s_t = (tt - self.c_l_ti) / dt  # space traveled on link

        # if self.monitored_veh and self.next_link["idx"] == 67940:

        #     pdb.set_trace()
        self.tt = tt
        self.s_t = s_t
        free_link = (
            1 - self.current_link["l_queue"] / self.current_link["length"]
        )  # space link free of queue

        if (self.c_l_tf > tt) & (s_t < free_link):  # still traveling
            self.status = "mov"
            self.current_link["storage_cap"] -= 1 - self.current_link["ksi"]
            self.same_link = True

        elif (self.c_l_tf <= tt) & (s_t >= free_link):  # should exit
            self.status = "at node"
            self.current_link["mov_vehs"] -= 1
            self.current_link["que_vehs"] += 1

        elif (self.c_l_tf > tt) & (
            s_t >= free_link
        ):  # encountred queue but would not have exited, need to update exit time
            self.status = "queueing"
            self.c_l_tf = max(
                tt + self.deltat, free_link * (self.c_l_tf - self.c_l_ti) + self.c_l_ti
            )
            self.current_link["mov_vehs"] -= 1
            self.current_link["que_vehs"] += 1
            self.current_link["storage_cap"] -= 1 - self.current_link["ksi"]
            self.same_link = True

    def node_transfer(self, t):
        permitted_turn = True
        # if self.status in node_conditions: #  implementato a livello superiore per evitare la chiamata
        if (
            self.status == "queueing"
        ):  # if it just encountred the queue, update exit time and put it as queuing vehicle
            self.status = "queue"

        else:  # the vehicle arrived to a node and needs to check capacity constraints
            if (
                self.current_link is self.last_link
            ):  # arrived at the end of the last link
                self.status = "arrived"
                self.current_link["que_vehs"] -= 1
                self.current_link["storage_cap"] += 1

            else:
                self.next_link = self.G.get_link(
                    self.path_links[self.n_l]
                )  # assign new next link

                l = self.current_link["idx"]
                nl = self.next_link["idx"]

                try:
                    nnl = (
                        None
                        if self.n_l + 1 >= len(self.path_links)
                        else self.path_links[self.n_l + 1]
                    )
                except:
                    nnl = None

                if l in self.signalized_links:
                    key = (l, nl) if (l, nl) in self.signalized_turns else None
                    key = (l, nl, nnl) if (l, nl, nnl) in self.signalized_turns else key

                    if key:
                        permitted_turn = self.signalized_turns[key]["state"] == "green"
                        # pdb.set_trace()

                        if self.signalized_turns[key]["type"] == "left_turn":
                            if self.signalized_turns[key]["permitted"] & permitted_turn:
                                # pdb.set_trace()

                                fl = self.G["signalized_turns"][key]["opposite_turn"][
                                    "from_link"
                                ]
                                fl = self.G.get_link(fl)  # match opposite direction
                                mv = fl["mov_vehs"]

                                if mv > 0:
                                    dmv = fl["length"] / (fl["mov_vehs"] * fl["speed"])
                                else:
                                    dmv = 100000

                                if (
                                    dmv > self.critical_gap
                                    or self.signalized_turns[key]["permitted_movs"] == 0
                                ):
                                    permitted_turn = False

                if (
                    (self.current_link["inflow_cap"] >= 1)
                    & (self.next_link["storage_cap"] >= 1)
                    & permitted_turn
                ):  # capacity of next link and on current link
                    self.update_cap(self.current_link, self.next_link)

                    ex = self.current_link["ex_q_veh"]
                    if ex:
                        lost_time = self.lt1 + ex * self.lt2
                    else:
                        lost_time = 0

                    if self.current_link["l_queue"]:
                        self.current_link["ex_q_veh"] += 1

                    self.status = "moving"  # transfer the vehicle on next link, update the capacities, detectors, enter and exit time and counter of the vehicles on next link
                    self.c_l_ti = self.c_l_tf + lost_time
                    self.c_l_tf = self.c_l_ti + self.next_link["ta"]
                    self.c_l += 1
                    self.n_l += 1
                    self.current_link = self.G.get_link(self.path_links[self.c_l])

                else:
                    self.status = "queue"  # put vehicle as a queuing vehicle and update its exit time (CHECK THIS!!!.)
                    self.c_l_tf = t + self.deltat
                    if self.same_link:
                        pass
                    else:
                        self.current_link["storage_cap"] -= 1 - self.current_link["ksi"]
                        self.same_link = True

    def move(self, t):

        if self.status == "arrived" and not self.monitored_veh:
            return False

        if self.status == "sleeping":
            if t >= self.ent_time:
                self.status = "moving"
                self.c_l_tf = (
                    self.c_l_ti + self.current_link["ta"]
                )  # exit time on current link

        test = 0
        while self.status not in transfer_condition:
            test += 1
            if test == 1000:
                print(
                    "Vehicle locked",
                    str(self.ID),
                    self.status,
                    self.current_link["idx"],
                    self.next_link["idx"],
                )
            if self.status == "moving":
                self.link_transfer(t)
            if self.status in node_conditions:
                self.node_transfer(t)
        if test >= 1000:
            print("Vehicle unlocked", test)

        if self.monitored_veh:
            ss = self.s_t if self.s_t else 0
            self.trace.append((t, ss, self.current_link["idx"], self.status, self.ID))

        if self.status == "mov":
            self.status = "moving"
        elif self.status == "queue":
            self.status = "at node"

        return self.status != "arrived" if not self.monitored_veh else True

    def update_cap(self, current_link, next_link):
        # update variable when transfering from current link to next link
        current_link["que_vehs"] -= 1
        current_link["inflow_cap"] -= 1

        ksi = 1 if self.same_link else current_link["ksi"]

        current_link["storage_cap"] += ksi

        current_link[self.field_out] += 1
        next_link[self.field_ent] += 1

        next_link["mov_vehs"] += 1
        next_link["storage_cap"] -= next_link["ksi"]

        self.same_link = False
