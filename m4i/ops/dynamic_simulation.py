
from .op import OP
from ..connectors import Loader, Writer
from ..simulators import BaseSimulator, MicroSimulator
from ..assignment_models import MSA
from ..assignment_models import AssignmentModel

class DynamicSimulation(OP):

    def __init__(self, loader: Loader, writer: Writer, **kwargs):
        super().__init__(loader, writer, **kwargs)
        w1 = 10
        w2 = 40 

        self.simulator: BaseSimulator = MicroSimulator(loader=self.loader)
        self.simulator.task_steps = 1
        self.simulator.task_parent = self
        self.simulator.task_weight = w1

        # Initialize the MSA
        self.msa:AssignmentModel = MSA(
            task_parent = self,
            task_weight = w2,
            task_steps = 4,
            loader=self.loader,
            writer=self.writer,
            max_k=self.ini.MSA_K,
            max_ite=1,
            max_rel_gap=self.ini.MSA_RGAP,
            simulator=self.simulator,
            save_state_graph=self.ini.SAVE_GRAPH,
            load_state_graph=self.ini.LOAD_GRAPH,
            save_state_paths=self.ini.SAVE_PATHS,
            load_state_paths=self.ini.LOAD_PATHS)
        n_steps = self.msa.calc_task_steps()
        if n_steps:
            self.msa.task_set_steps(n_steps)

    def run(self):
        self.simulator.task_step_done("Data loaded")
        self.msa.run()
