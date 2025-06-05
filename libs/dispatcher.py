import time
from .simulators import BaseSimulator, MicroSimulator, StaticSimulator
from .connectors import Loader, Writer
from . import Logger
from . import MSA
from .database import Execution
from datetime import datetime
from .params_parser import ParamsParser
from .utils.ipc import IPC
from .fcd.rt_server import RTServer
from .utils import Parallel

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
            self.log = Logger.getLogger(self.__class__.__name__)

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

        # Initialize the simulator
        simulator: BaseSimulator = MicroSimulator(loader=self.loader)

        # Initialize the MSA
        msa = MSA(
            loader=self.loader,
            writer=self.writer,
            max_k=self.loader.ini.MSA_K,
            max_ite=self.loader.ini.MSA_MAX_ITE,
            max_rel_gap=self.loader.ini.MSA_RGAP,
            simulator=simulator,
            save_state_graph=self.loader.ini.SAVE_GRAPH,
            load_state_graph=self.loader.ini.LOAD_GRAPH,
            save_state_paths=self.loader.ini.SAVE_PATHS,
            load_state_paths=self.loader.ini.LOAD_PATHS)

        # Run the calculation
        msa.run()        

    def run_static_assignment(self):        
        # Initialize the simulator
        simulator: BaseSimulator = StaticSimulator(loader=self.loader, links_vdf="vdf")

        # Initialize the MSA
        msa = MSA(
            loader=self.loader,
            writer=self.writer,
            max_k=self.loader.ini.MSA_K,
            max_ite=self.loader.ini.MSA_MAX_ITE,
            max_rel_gap=self.loader.ini.MSA_RGAP,
            simulator=simulator,
            save_state_graph=self.loader.ini.SAVE_GRAPH,
            load_state_graph=self.loader.ini.LOAD_GRAPH,
            save_state_paths=self.loader.ini.SAVE_PATHS,
            load_state_paths=self.loader.ini.LOAD_PATHS)

        # Run the calculation
        msa.run() 

    def run_dynamic_simulation(self):        

        # Initialize the simulator
        simulator: BaseSimulator = MicroSimulator(loader=self.loader)

        # Initialize the MSA
        msa = MSA(
            loader=self.loader,
            writer=self.writer,
            max_k=self.loader.ini.MSA_K,
            max_ite=1,
            max_rel_gap=self.loader.ini.MSA_RGAP,
            simulator=simulator,
            save_state_graph=False,
            load_state_graph=False,
            save_state_paths=False,
            load_state_paths=False)

        # Run the calculation
        msa.run()     

    def run_online(self):        
        # Initialize the simulator
        simulator: BaseSimulator = MicroSimulator(loader=self.loader)

        # Initialize the MSA
        msa = MSA(
            loader=self.loader,
            writer=self.writer,
            max_k=self.loader.ini.MSA_K,
            max_ite=1,
            max_rel_gap=self.loader.ini.MSA_RGAP,
            simulator=simulator,
            save_state_graph=False,
            load_state_graph=True,
            save_state_paths=False,
            load_state_paths=True,
            ipc=self.ipc,
            )

        # Run the calculation
        msa.run()  

    def run_save_state(self):        

        # Initialize the simulator
        simulator: BaseSimulator = MicroSimulator(loader=self.loader)

        # Initialize the MSA
        msa = MSA(
            loader=self.loader,
            writer=self.writer,
            max_k=self.loader.ini.MSA_K,
            max_ite=self.loader.ini.MSA_MAX_ITE,
            max_rel_gap=self.loader.ini.MSA_RGAP,
            simulator=simulator,
            save_state_graph=True,
            load_state_graph=False,
            save_state_paths=True,
            load_state_paths=False)

        # Run the calculation
        msa.run()                  

    def run_rt_server(self):
        rt_server: RTServer = RTServer(parser=self.parser, ipc=self.ipc, loader=self.loader, writer=self.writer) 
        rt_server.run()

    def run_rt_server_period(self):
        rt_server: RTServer = RTServer(parser=self.parser, ipc=self.ipc, loader=self.loader, writer=self.writer) 
        rt_server.elaborate_period(self.parser.get("date_start"), self.parser.get("date_end"), self.parser.ini.FCD_HORIZON)

    def run_ipc_client(self):
        if self.ipc is None:
            raise ValueError("IPC not initialized")
        self.ipc.run_client()
