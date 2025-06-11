
from __future__ import annotations
from ..connectors import Writer
from ..connectors import Loader
from ..utils import IPC
from .. import ParamsParser
from .. import TaskBase
from ..log import Logger
from ..database import Execution
from ..taskbase import TaskBase
class OP(TaskBase):

    def __init__(self, loader:Loader, writer:Writer, ipc: IPC=None, **kwargs):
        super().__init__(**kwargs)
        self.loader: Loader = loader
        self.writer: Writer = writer
        self.ipc: IPC = ipc
        self.execution_id: int = self.loader.execution_id
        self.parser: ParamsParser = self.loader.parser
        self.ini = self.loader.ini
        self.task_on_progress = lambda _, m, p : OP.update_progress(self,m,p)
        if self.execution_id is None:
            self.execution = Execution.create_execution(params=self.parser.params)        
            self.execution_id = self.execution.id
            self.log = Logger.getLogger(self.__class__.__name__, execution_id=self.execution_id)
            self.log.info("Execution created")
        else:
            self.log = Logger.getLogger(self.__class__.__name__, execution_id=self.execution_id)

    def run():
        pass

    @staticmethod
    def update_progress(self: OP, message:str = None, progress: float = None):
        tp = self.task_total_progress
        if message is None:
            message = f"({tp:.1f}%) Processing..."
        Execution.set_progress(self.execution_id, tp, message=message)
        self.log.info(f"({tp:.1f}%) {message}")
