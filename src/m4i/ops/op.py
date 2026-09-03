from __future__ import annotations
from ..connectors import Writer
from ..connectors import Loader
from ..utils import IPC
from .. import ParamsParser
from ..log import Logger
from ..database import Execution
from ..base_m4i_model import BaseM4IModel


class OP(BaseM4IModel):
    def __init__(self, loader: Loader, writer: Writer, ipc: IPC = None, **kwargs):
        super().__init__(loader=loader, writer=writer, ipc=ipc, **kwargs)
        if self.execution_id is None:
            self.execution = Execution.create_execution(params=self.parser.params)
            self.execution_id = self.execution.id
            self.loader.execution_id = self.execution_id
            self.log.info("Execution created")
            super().__init__(loader=loader, writer=writer, ipc=ipc, **kwargs)

    def run():
        pass

    @staticmethod
    def update_progress(self: OP, message: str = None, progress: float = None):
        tp = self.task_total_progress
        if message is None:
            message = f"({tp:.1f}%) Processing..."
        Execution.set_progress(self.execution_id, tp, message=message)
        self.log.info(f"({tp:.1f}%) {message}")
