from __future__ import annotations

import warnings

from .connectors.state_manager import StateManager
from .connectors import Writer
from .connectors import Loader
from . import ParamsParser
from .utils import IPC
from .log import Logger
from .database import Execution
from .taskbase import TaskBase
from .utils.tictoc import TicToc
from .iniclass import IniClass


class BaseM4IModel(TaskBase):
    def __init__(
        self,
        parser: ParamsParser = None,
        loader: Loader = None,
        writer: Writer = None,
        ipc: IPC = None,
        state_manager: StateManager = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        if parser is None and loader is not None:
            self.parser: ParamsParser = loader.parser
        else:
            self.parser: ParamsParser = parser
        if parser is None and writer is not None:
            self.parser: ParamsParser = writer.parser
        else:
            self.parser: ParamsParser = parser

        if loader is None and self.parser is not None:
            self.loader = Loader(parser=self.parser)
        else:
            self.loader: Loader = loader
        if writer is None and self.parser is not None:
            self.writer = Writer(parser=self.parser)
        else:
            self.writer: Writer = writer
        if state_manager is None and self.parser is not None:
            self.state_manager: StateManager = StateManager(parser=self.parser)
        else:
            self.state_manager: StateManager = state_manager

        if self.parser is not None:
            self.ini: IniClass = self.parser.ini
        else:
            self.ini: IniClass = None

        self._ipc: IPC = ipc
        if self.loader is not None:
            self.execution_id: int = self.loader.execution_id
        else:
            self.execution_id: int = None

        self.task_on_progress = lambda _, m, p: BaseM4IModel.update_progress(self, m, p)
        module_name = IniClass.environ.get("LOG_NAME", self.__class__.__module__)
        log_name = f"{module_name}.{self.__class__.__name__}"
        if self.execution_id is None:
            self.log = Logger.getLogger(log_name)
        else:
            self.log = Logger.getLogger(log_name, execution_id=self.execution_id)
        self.tic: TicToc = TicToc(logger=self.log)

    @property
    def ipc(self) -> IPC:
        if self._ipc is None and self.parser is not None:
            if self.parser.ini.IPC_USE:
                self._ipc = IPC(
                    bucket=self.parser.ini.IPC_BUCKET,
                    backend=self.parser.ini.IPC_BACKEND,
                    host=self.parser.ini.IPC_HOST,
                    port=self.parser.ini.IPC_PORT,
                    db=self.parser.ini.IPC_DB,
                    compression=self.parser.ini.IPC_COMPRESSION,
                    compression_level=self.parser.ini.IPC_COMPRESSION_LEVEL,
                )
            else:
                self._ipc = None
        elif self.parser is not None and self._ipc is None:
            if self.parser.ini.IPC_USE:
                warnings.warn(
                    "IPC is not initialized. Please provide a valid settings parameters file.",
                    UserWarning,
                )
        return self._ipc

    def run():
        pass

    @staticmethod
    def update_progress(
        self: BaseM4IModel, message: str = None, progress: float = None
    ):
        tp = self.task_total_progress
        if message is None:
            message = f"({tp:.1f}%) Processing..."
        if self.execution_id is not None:
            Execution.set_progress(self.execution_id, tp, message=message)
        self.log.info(f"({tp:.1f}%) {message}")
