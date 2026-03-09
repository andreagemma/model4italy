
from m4i.graphs.paths.path import Path
from .op import OP
from ..connectors import Loader, Writer
from ..simulators import BaseSimulator, MicroSimulator
from ..graphs.spp import SPP
from ..graphs import PathList
import numpy as np

class PathsCalculation(OP):

    def __init__(self, loader: Loader, writer: Writer, **kwargs):
        super().__init__(loader, writer, **kwargs)
        self.G=self.loader.load_graph().resize_attributes(new_total_time=self.parser.get("total_time", default=self.ini.DELTA_T))
        self.origin_nodes = self.loader.load("params.origin_nodes")
        self.destination_nodes = self.loader.load("params.destination_nodes")
        self.modes = self.loader.modes
        self.link_cost = self.parser.get("link_cost", "time")
        self.node_cost = self.parser.get("node_cost", "time")
        self.turn_cost = self.parser.get("turn_cost", "time")
        self.paths = PathList()
        
    def run(self):
        self.log.info("Starting paths calculation...")
        paths = SPP.multiple_paths(self.G,origins=self.origin_nodes["id"].tolist(),targets=self.destination_nodes["id"].tolist(),
                                   t_starts=np.arange(0,self.G["total_time"],self.G["delta_t"]).tolist(),
                                   modes = set(self.modes.keys()),
                                   link_cost=self.link_cost,
                                   node_cost=self.node_cost,
                                   turn_cost=self.turn_cost)
        self.log.info(f"Paths calculation completed. {len(self.paths)} paths found.")
        df_paths = paths.to_pandas(G=self.G, crs_link=self.ini.CRS_CALC)
        self.log.info(f"Path conversion to DataFrame completed. {len(df_paths)} paths ready for output.")
        self.log.info(f"Writing paths to output...")
        self.writer.write_paths(df_paths,mode="w")
    