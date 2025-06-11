import pandas as pd
from ..log import Logger
from ..connectors import Loader
from ..graphs import KPathContainer, DynamicGraph as Graph, DynamicTimeArrayAttribute, DynamicLink as Link, DynamicNode as Node, DynamicTurn as Turn
from . import BaseSimulator
class QuasiDynamicSimulator(BaseSimulator):

    log = Logger.getLogger("SIM")

    def __init__(self,loader: Loader, links_vdf: str,nodes_vdf: str,turns_vdf: str) -> None:
        self.loader: Loader = loader
        self.paths:KPathContainer = None
        self.G: Graph = loader.G
        self.links_vdf: str = links_vdf
        self.nodes_vdf: str = nodes_vdf
        self.turns_vdf: str = turns_vdf

    def update_performance(self, k, tstart, tend):
        # for each path adds the path flow to the
        delta_t = self.G.delta_t
        total_time = self.G.total_time
        for path in self.paths.all_paths():
            prev_link = None
            for link_idx, cost in zip(path.get_links(), path.get_costs()):
                link: Link = self.G.get_link(link_idx)
                node: Node = self.G.get_node(link["i"])
                turns: list[Turn] = self.G.get_turns(in_link=prev_link["idx"], out_link=link_idx)

                link.add_value(name="flow", t=cost, value=path["path_flow"])
                node.add_value(name="flow", t=cost, value=path["path_flow"])

                for turn in turns:
                    node.add_value(name="flow", t=cost, value=path["path_flow"])

                prev_link = link

        for link in self.G.get_all_links():
            link.add_attribute("n_paths",DynamicTimeArrayAttribute(0, total_time=total_time, delta_t=delta_t))
            link.add_attribute("time",DynamicTimeArrayAttribute(0, total_time=total_time, delta_t=delta_t))
        for node in self.G.get_all_nodes():
            node.add_attribute("n_paths",DynamicTimeArrayAttribute(0, total_time=total_time, delta_t=delta_t))
            node.add_attribute("time",DynamicTimeArrayAttribute(0, total_time=total_time, delta_t=delta_t))
        for turn in self.G.get_all_turns():
            turn.add_attribute("n_paths",DynamicTimeArrayAttribute(0, total_time=total_time, delta_t=delta_t))
            turn.add_attribute("time",DynamicTimeArrayAttribute(0, total_time=total_time, delta_t=delta_t))

        for path in self.paths.all_paths():
            prev_link = None
            for link_idx, cost in zip(path.get_links(), path.get_costs()):
                link = self.G.get_link(link_idx)
                link.set_value("n_paths", value=link.get_value("n_paths",t=cost)+1, t=cost)
                link_time = link.get_value(name=self.links_vdf, t=cost, in_link=prev_link, graph=self.G, default=0)
                if link_time!=0:
                    link.set_value("time", value=link.get_value("time",t=cost)+link_time, t=cost)

                node = self.G.get_node(link["i"])
                node.set_value("n_paths", value=node.get_value("n_paths",t=cost)+1, t=cost)
                node_time = node.get_value(name=self.nodes_vdf, t=cost, in_link=prev_link, out_link=link, graph=self.G, default=0)
                if node_time!=0:
                    node.set_value("time", value=node.get_value("time",t=cost)+node_time, t=cost)

                turns = self.G.get_turns(in_link=prev_link, out_link=link)

                for turn in turns:
                    turn.set_value("n_paths", value=turn.get_value("n_paths",t=cost)+1, t=cost)
                    turn_time = turn.get_value(name=self.nodes_vdf, t=cost, graph=self.G, default=0)
                    if turn_time!=0:
                        turn.set_value("time", value=turn.get_value("time",t=cost)+turn_time, t=cost)

                prev_link = link

        for link in self.G.get_all_links():
            link["time"] /= link["n_paths"]

        pass

    def initialize_assignment(self,time_start,time_end):
        pass

    def finalize_assignment(self,time_start,time_end):
        pass

    def set_paths(self,paths: KPathContainer):
        self.paths = paths

    def agg_results(self, tstart, tend, agg_int) -> pd.DataFrame:
        pass

    def run_simulation(self, k, tstart, tend):
        pass