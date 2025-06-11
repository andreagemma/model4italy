import time
from .ops import *
from .simulators import BaseSimulator, MicroSimulator, StaticSimulator
from .connectors import Loader, Writer
from .log import Logger
from .assignment_models import *
from .database import Execution
from .params_parser import ParamsParser
from .utils.ipc import IPC
from .fcd.rt_server import RTServer
from .utils import Parallel

from datetime import datetime

class Dispatcher():
    
    def __init__(self, params, ini, op:str = None, execution: Execution=None):
        self.t_start: int = time.time()
        self.parser: ParamsParser = ParamsParser(params=params, settings=ini)
        if op:
            self.parser.set_value("op", op)
        self.execution: Execution = execution
        self.execution_id: int = execution.id if execution else None
        self.log: Logger = None

        params = self.parser.params
        if self.execution_id is None:
            self.execution = Execution.create_execution(params=params)        
            self.execution_id = self.execution.id
            self.log = Logger.getLogger(self.__class__.__name__, execution_id=self.execution_id)
            self.log.info("Execution created")
        else:
            self.log = Logger.getLogger(self.__class__.__name__, execution_id=self.execution_id)

        if self.execution_id is None:
            self.log.info(f"Executing...")
        else:
            self.log.info(f"Executing ({self.execution_id})")
        self.parser.set_value("execution_id", self.execution_id)
        self.parser.set_default("date_simulation",datetime.now().strftime("%Y-%m-%d"))
        self.parser.set_default("time_simulation",datetime.now().strftime("%H:%M:%S"))

        self.op = self.parser.get("op")
        self._ipc = None
        if self.parser.ini.PARALLEL_USE:
            Parallel.initialize_parallel(
                engine=self.parser.ini.PARALLEL_ENGINE,
                num_cpus=self.parser.ini.PARALLEL_NUMCPUS,  
                address=self.parser.ini.PARALLEL_CLUSTER_ADDRESS
            )
        else:
            Parallel.initialize_parallel(
                engine=Parallel.ENGINE_NONE,
                num_cpus=1, 
                address=None
            )
        self.loader: Loader = Loader(parser=self.parser)
        self.writer: Writer = Writer(parser=self.parser)
    @property
    def ipc(self) -> IPC:
        if self._ipc is None:
            if self.parser.ini.IPC_USE:
                self._ipc = IPC(
                    bucket=self.parser.ini.IPC_BUCKET,
                    backend=self.parser.ini.IPC_BACKEND,
                    host=self.parser.ini.IPC_HOST,
                    port=self.parser.ini.IPC_PORT,
                    db=self.parser.ini.IPC_DB,
                    compression=self.parser.ini.IPC_COMPRESSION,
                    compression_level=self.parser.ini.IPC_COMPRESSION_LEVEL
                )
            else:
                self._ipc = None
        return self._ipc
    
    def run(self):
        try:
            if self.execution_id is None:
                self.log.info(f"Running op:{self.op}...")
            else:
                self.log.info(f"Running op:{self.op} (id: {self.execution_id})")            
            if self.op == "assignment":
                self.run_dynamic_assignment()
            elif self.op == "static_assignment":
                self.run_static_assignment()
            elif self.op == "simulation":
                self.run_dynamic_simulation()
            elif self.op == "online":
                self.run_online()                
            elif self.op == "save_state":
                self.run_save_state()
            elif self.op == "rt_server":
                self.run_rt_server()
            elif self.op == "rt_server_period":
                self.run_rt_server_period()
            elif self.op == "ipc":
                self.run_ipc_client()                
            else:
                raise ValueError(f"Operation {self.op} not recognized")
            
            if self.execution_id is None:
                self.log.info("Execution finished in %.2f seconds", time.time() - self.t_start)
            else:
                Execution.set_execution_success(self.execution_id)
                self.log.info(f"Execution ({self.execution_id}) finished in %.2f seconds", time.time() - self.t_start)            
        except Exception as ex:
            if self.execution_id is None:
                self.log.info("Execution terminated abnormally in %.2f seconds", time.time() - self.t_start)  
            else:    
                Execution.set_execution_failed(self.execution_id, ex=ex, raise_exception=False)
                self.log.info(f"Execution ({self.execution_id}) terminated abnormally in %.2f seconds", time.time() - self.t_start)
            raise ex       
         
    def run_dynamic_assignment(self):        
        op: OP = DynamicAssignment(loader=self.loader, writer=self.writer)  
        op.run()        

    def run_static_assignment(self):        
        op: OP = StaticAssignment(loader=self.loader, writer=self.writer)  
        op.run()        

    def run_dynamic_simulation(self):        

        op: OP = DynamicSimulation(loader=self.loader, writer=self.writer)  
        op.run()         

    def run_online(self):        
        op: OP = OnlineSimulator(loader=self.loader, writer=self.writer)  
        op.run()   

    def run_save_state(self):        
        op: OP = OfflineSaveState(loader=self.loader, writer=self.writer)  
        op.run()                     

    def run_rt_server(self):
        op: OP = OnlineRTServer(loader=self.loader, writer=self.writer, ipc=self.ipc)  
        op.run()                     

    def run_rt_server_period(self):
        op: OP = OfflineRTServer(loader=self.loader, writer=self.writer, ipc=self.ipc)  
        op.run()                     
        
    def run_ipc_client(self):
        if self.ipc is None:
            raise ValueError("IPC not initialized")
        self.ipc.run_client()
