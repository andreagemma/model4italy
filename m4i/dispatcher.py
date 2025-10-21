import os
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
from .base_m4i_model import BaseM4IModel

class Dispatcher(BaseM4IModel):
    
    def __init__(self, params, ini, options:dict = None, execution: Execution=None):
        self.t_start: int = time.time()
        self.parser: ParamsParser = ParamsParser(params=params, settings=ini, options=options)
        self.execution: Execution = execution
        self.execution_id: int = execution.id if execution else None

        if self.execution_id is None:
            try:
                self.execution = Execution.create_execution(params=params)        
            except Exception as ex:
                import sys
                appname = os.path.basename(sys.argv[0]) if len(sys.argv) > 0 else ""
                if appname:
                    raise Exception(f"Error creating execution in database. Try to initialize the database with {appname} init_db") from ex
                else:
                    parent_module_name = __name__.split(".")[0]
                    raise Exception(f"Error creating execution in database. Try to initialize the database with '{parent_module_name}.init_db()' command") from ex                    
            self.execution_id = self.execution.id

        self.parser.set_value("execution_id", self.execution_id)
        self.parser.update_date(dt=datetime.now(), name="execution")
        

        super().__init__(parser=self.parser, execution=execution)

        if self.execution_id is None:
            self.log.info(f"Executing...")
        else:
            self.log.info(f"Executing ({self.execution_id})")


        self.op = self.parser.get("op")
        self._ipc = None
        if self.parser.ini.PARALLEL_USE:
            self.log.debug(f"Initializing parallel engine {self.parser.ini.PARALLEL_ENGINE} with {self.parser.ini.PARALLEL_NUMCPUS} cpus...")
            Parallel.initialize_parallel(
                engine=self.parser.ini.PARALLEL_ENGINE,
                num_cpus=self.parser.ini.PARALLEL_NUMCPUS,  
                address=self.parser.ini.PARALLEL_CLUSTER_ADDRESS
            )
            self.log.info(f"Parallel engine {Parallel.parallel_engine} initialized with {Parallel.num_cpus} cpus")
        else:
            Parallel.initialize_parallel(
                engine=Parallel.ENGINE_NONE,
                num_cpus=1, 
                address=None
            )
        self.loader: Loader = Loader(parser=self.parser)
        self.writer: Writer = Writer(parser=self.parser)
        if self.writer.has("params.params"):            
            try:
                import pandas as pd
                import json
                df = pd.DataFrame({
                    "execution_id": [self.execution_id],
                    "params": [json.dumps(self.parser.get_dict())]
                })
                p = self.parser.get_output_parameters("params.params")
                if "src" in p and p["src"].lower().endswith(".json"):
                    with open(os.path.join(p["location"], p["src"]), 'w') as f:
                        json.dump(self.parser.get_dict(), f, indent=4)
                else:
                    self.writer.write(df, "params.params", mode="w")
            except Exception as ex:
                self.log.error(f"Error writing params.json: {ex}")
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
    
    def run(self) -> "Dispatcher":
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
            elif self.op == "od_estimation":
                self.run_od_estimation()
            elif self.op == "save_state":
                self.run_save_state()
            elif self.op == "fcd_server_online":
                self.run_rt_server()
            elif self.op == "fcd_server_offline":
                self.run_rt_server_period()
            elif self.op == "fcd_server_paths_clustering":
                self.run_rt_server_clustering()
            elif self.op == "ipc":
                self.run_ipc_client()                
            elif self.op == "init":
                self.log.info("System initialized")
            else:
                raise ValueError(f"Operation {self.op} not recognized")
            
            if self.execution_id is None:
                self.log.info("Execution finished in %.2f seconds", time.time() - self.t_start)
            else:
                Execution.set_execution_success(self.execution_id)
                self.log.info(f"Execution ({self.execution_id}) finished in %.2f seconds", time.time() - self.t_start)          
            return self  
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

    def run_od_estimation(self):        
        op: OP = ODEstimation(loader=self.loader, writer=self.writer)  
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

    def run_rt_server_clustering(self):
        op: OP = PathsClustering(loader=self.loader, writer=self.writer, ipc=self.ipc)  
        op.run()   

    def run_ipc_client(self):
        if self.ipc is None:
            raise ValueError("IPC not initialized")
        self.ipc.run_client()
