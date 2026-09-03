from .op import OP
from ..connectors import Loader, Writer
from ..utils import IPC
from ..simulators import BaseSimulator, MicroSimulator
from ..fcd import RTServer


class OnlineRTServer(OP):
    def __init__(self, loader: Loader, writer: Writer, ipc: IPC = None):
        super().__init__(loader, writer, ipc=ipc)
        self.rt_server: RTServer = RTServer(
            parser=self.loader.parser,
            ipc=self.ipc,
            loader=self.loader,
            writer=self.writer,
        )

    def run(self):
        self.rt_server.run()
