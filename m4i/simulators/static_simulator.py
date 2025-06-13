import pandas as pd

from ..log import Logger
from ..connectors import Loader
from . import BaseSimulator
from ..graphs import *
from ..graphs import DynamicGraph as Graph, DynamicLink as Link
from ..utils import min2hhmm

class StaticSimulator(BaseSimulator):

    log = Logger.getLogger("SIM")
    
    def __init__(self,loader: Loader, links_vdf: str = "vdf") -> None:
        self.loader: Loader = loader   
        self.paths:KPathContainer = None     
        self.G: Graph = loader.G
        self.links_vdf: str = links_vdf
    
    def update_performance(self, k, tstart, tend):        
        modes = self.G["modes"]

        for link in self.G.get_all_links():
            link["flow"].reset(0)
            for mode in modes.keys():
                if f"flow_{mode}" not in link:
                    link[f"flow_{mode}"] = link["flow"].copy()
                else:
                    link[f"flow_{mode}"].reset(0)

        from collections import defaultdict
        # for each path adds the path flow to the
        def calc(tasks,G):
            flows = defaultdict(int)
            mode_flows = defaultdict(int)
            for path in tasks:
                mode = path["mode"]

                for link_idx in path.get_links():
                    flows[(link_idx,path["t_start"])] += path["path_flow"]
                    mode_flows[(mode,link_idx,path["t_start"])] += path["path_flow"]
            return flows, mode_flows

        from ..utils.parallel import Parallel
        for flows, mode_flows in Parallel.execute(calc, tasks=self.paths.all_paths(), G=self.G, n_workers=4):
            for (link_idx,t_start), flow in flows.items():
                link = self.G.get_link(link_idx)
                link["flow"] += flow,t_start
            for (mode,link_idx,t_start), flow in mode_flows.items():
                link = self.G.get_link(link_idx)
                link[f"flow_{mode}"] += flow,t_start
        
        for link in self.G.get_all_links():
            t0 = link["length"] / link["v0"]
            time = link.get_value("vdf", q=link.get_value("flow"),t0=t0,a=link.get_value("vdf_a"), b=link.get_value("vdf_b"), c=link.get_value("capacity"))
            link.set_value("time", time)            

        
    def initialize_assignment(self,time_start,time_end):
        pass
    
    def finalize_assignment(self,time_start,time_end):
        pass
    
    def set_paths(self,paths: KPathContainer):
        self.paths = paths
    
    def agg_results(self, tstart, tend, agg_int) -> pd.DataFrame:

        agg_int = str(agg_int)+"min"
        
        times = pd.date_range(start=min2hhmm(tstart), end=min2hhmm(tend), freq=agg_int)[:-1]
        ret = {
            "time": [],
            "mode": [],
            "id_link": [],
            "flow_in": [],
            "flow_out": [],
            "speed": [],
            "density": [],
            "travel_time": [],
            "queue": [],
            #"geometry": []
        }
        list_time = ret["time"]
        list_mode = ret["mode"]
        list_id_link = ret["id_link"]
        list_flow_in = ret["flow_in"]
        list_flow_out = ret["flow_out"]
        list_speed = ret["speed"]
        list_density = ret["density"]
        list_travel_time = ret["travel_time"]
        list_queue = ret["queue"]
        #list_geometry = ret["geometry"]
        modes = self.G["modes"]

        for time in times:
            for link in self.G.get_all_links():
                flow = link.get_value("flow")
                travel_time = link.get_value("time")
                speed = link.get_value("length")/travel_time
                density = flow/speed
                queue = None
                
                list_time.append(time)
                list_mode.append("all")        
                list_id_link.append(link["idx"])
                list_flow_in.append(flow)
                list_flow_out.append(flow)                                
                list_speed.append(speed)
                list_density.append(density)
                list_travel_time.append(travel_time)
                list_queue.append(queue)

                for mode in modes.keys():
                    flow = link.get_value("flow_"+mode)
                    travel_time = link.get_value("time")
                    speed = link.get_value("length")/travel_time
                    density = flow/speed
                    queue = None # flow/link.get_value("capacity")
                    
                    list_time.append(time)
                    list_mode.append(mode)        
                    list_id_link.append(link["idx"])
                    list_flow_in.append(flow)
                    list_flow_out.append(flow)                                
                    list_speed.append(speed)
                    list_density.append(density)
                    list_travel_time.append(travel_time)
                    list_queue.append(queue)
                    
                
        return pd.DataFrame(ret).astype({
            "time":"datetime64[ns]", 
            "mode":str,
            "id_link":int,                                            
            "flow_in":float, 
            "flow_out":float, 
            "speed":float, 
            "density":float, 
            "travel_time":float, 
            "queue":float
            }, copy=False)
    