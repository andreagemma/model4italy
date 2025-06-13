from __future__ import annotations

from .connectors import Writer
from .connectors import Loader
from . import ParamsParser
from .utils import IPC
from .log import Logger
from .database import Execution
from .taskbase import TaskBase

class BaseM4IModel(TaskBase):

    def __init__(self, loader:Loader, writer:Writer, ipc: IPC=None, **kwargs):
        super().__init__(**kwargs)
        self.loader: Loader = loader
        self.writer: Writer = writer
        self.ipc: IPC = ipc
        self.execution_id: int = self.loader.execution_id
        self.parser: ParamsParser = self.loader.parser
        self.ini = self.loader.ini
        self.task_on_progress = lambda _, m, p : BaseM4IModel.update_progress(self,m,p)        
        if self.execution_id is None:
            self.log = Logger.getLogger(self.__class__.__name__)
        else:
            self.log = Logger.getLogger(self.__class__.__name__, execution_id=self.execution_id)

    def run():
        pass

    @staticmethod
    def update_progress(self: BaseM4IModel, message:str = None, progress: float = None):
        tp = self.task_total_progress
        if message is None:
            message = f"({tp:.1f}%) Processing..."
        if self.execution_id is not None:
            Execution.set_progress(self.execution_id, tp, message=message)
        self.log.info(f"({tp:.1f}%) {message}")
