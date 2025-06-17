
from .op import OP
from ..connectors import Loader, Writer
from ..utils.ipc import IPC
from ..fcd import RTServer

class OfflineRTServer(OP):

    def __init__(self, loader: Loader, writer: Writer, ipc: IPC = None):
        super().__init__(loader, writer, ipc=ipc)
        self.rt_server: RTServer = RTServer(parser=self.parser, ipc=self.ipc, loader=self.loader, writer=self.writer)         

    def run(self):
        self.rt_server.elaborate_period(
            t_start=self.parser.get("date_start"), 
            t_end=self.parser.get("date_end"), 
            timeslice = self.ini.FCD_SERVER_FCD_TIMESLICE_OFFLINE,
            horizon=self.ini.FCD_SERVER_FCD_HORIZON)