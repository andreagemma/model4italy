
from .op import OP
from .. import Loader, Writer, IPC
from ..import BaseSimulator, MicroSimulator
from ..fcd import RTServer

class OfflineRTServer(OP):

    def __init__(self, loader: Loader, writer: Writer, ipc: IPC = None):
        super().__init__(loader, writer, ipc=ipc)
        self.rt_server: RTServer = RTServer(parser=self.parser, ipc=self.ipc, loader=self.loader, writer=self.writer)         

    def run(self):
        self.rt_server.elaborate_period(self.parser.get("date_start"), self.parser.get("date_end"), self.ini.FCD_HORIZON)