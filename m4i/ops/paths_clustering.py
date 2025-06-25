from ..fcd.paths_clustering import PathsClustering as BasePathsClustering
from .op import OP
from ..connectors import Loader, Writer
from ..simulators import BaseSimulator, MicroSimulator
from ..assignment_models import MSA
from ..assignment_models import AssignmentModel

class PathsClustering(OP):

    def __init__(self, loader: Loader, writer: Writer, **kwargs):
        super().__init__(loader, writer, **kwargs)
        self.paths_clustering: BasePathsClustering = BasePathsClustering(
            loader=self.loader,
            writer=self.writer,
            ipc=self.ipc
        )

    def run(self):
        self.log.info("Starting paths clustering...")
        df = self.loader.load("params.fcd_paths")
        df = self.paths_clustering.run(df)
        self.writer.write(df, "params.paths_clustered", mode="w")
        self.log.info("Paths clustering completed.")