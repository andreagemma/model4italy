
from .op import OP
from ..connectors import Loader, Writer
from ..simulators import BaseSimulator, MicroSimulator, StaticSimulator
from ..assignment_models import MSA
from ..assignment_models import AssignmentModel

class StaticAssignment(OP):

    def __init__(self, loader: Loader, writer: Writer):
        super().__init__(loader, writer)
        # Initialize the simulator
        simulator: BaseSimulator = StaticSimulator(loader=self.loader, links_vdf="vdf")

        # Initialize the MSA
        self.msa = MSA(
            loader=self.loader,
            writer=self.writer,
            max_k=self.loader.ini.MSA_K,
            max_ite=self.loader.ini.MSA_MAX_ITE,
            max_rel_gap=self.loader.ini.MSA_RGAP,
            simulator=simulator,
            save_state_graph=self.loader.ini.SAVE_GRAPH,
            load_state_graph=self.loader.ini.LOAD_GRAPH,
            save_state_paths=self.loader.ini.SAVE_PATHS,
            load_state_paths=self.loader.ini.LOAD_PATHS)

    def run(self):
        self.msa.run()