# -*- coding: utf-8 -*-
"""
Created on Thu Jun  3 17:38:38 2021

@author: andge
"""

from typing import Dict
import numpy as np
import matplotlib.pyplot as plt
import logging
import pandas as pd
from datetime import timedelta
from ...log import Logger


class Simulator:
    def __init__(self):
        log = Logger.getLogger("SIM")
        log.info("Simulatore Inizializzato: modello del secondo ordine di deflusso autostradale")
        np.random.seed(0)

    def aggiorna_tempi(self, graph, mpaths):

        # funzione per aumantare casualemente i tempi
        def modifica_tempi(l):
            return (np.random.rand(4) * [1.4, 1.5, 1.6, 1.7] * l["time"]).tolist()

        # per ogni arco assegno i tempi calcolati
        # risultato finale [{i:?, j:?, t: [?1,?2,...?k] }]
        tempi = []
        for l in graph["linksl"]:
            ltmp = {"i": l["i"], "j": l["j"], "t": modifica_tempi(l)}
            tempi.append(ltmp)

        return tempi

    def spec_demand(self, flows):
        "costruisce, la matrici di flussi in entrata, in uscita e le percentuali di svolta data la domanda"
        (preload, Inflow, R_mod_tot, Beta_out_tot, Beta_div_tot) = read_od.get_demand_profile(
            flows,
            self.sim_duration,
            self.Ramps,
            self.Stars,
            self.Topology,
            self.SimuGraph,
        )
        return (preload, Inflow, R_mod_tot, Beta_out_tot, Beta_div_tot)

    def agg_results(self, agg_int="5T"):
        "aggrega i risultati in un pd.dataframe a 5 min"
        if len(self.results) > 0:
            q = self.results[0]
            v = self.results[1]
            r = self.results[2]
            links = self.results[3]
            start_date = pd.DatetimeIndex([self.parameters.header.date_simulation + " " + self.parameters.header.start])
            end_date = pd.DatetimeIndex([self.parameters.header.date_simulation + " " + self.parameters.header.end])
            datevec = np.arange(
                start_date[0],
                end_date[0],
                timedelta(seconds=self.parameters.header.time_step_s),
            )
            datevec_repeat = np.concatenate([np.tile(datevec[ix], len(links)) for ix in range(len(datevec))]).ravel()
            d = np.vstack(
                [
                    np.tile(links, self.sim_duration),
                    q[:-1, :].flatten(),
                    r[:-1, :].flatten(),
                    v[:-1, :].flatten(),
                ]
            ).T
            df = pd.DataFrame(index=datevec_repeat, data=d, columns=["id_cav", "q", "r", "v"])
            df_grouped = df.groupby("id_cav").resample(agg_int).mean()
            df_grouped = df_grouped.reset_index(level=0, drop=True).round(2)
            df_grouped["time"] = df_grouped.index
        else:
            df_grouped = None

        return df_grouped
