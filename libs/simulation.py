import time
import traceback
from .simulators import BaseSimulator, MicroSimulator, StaticSimulator
from .connectors import Loader, Writer
from . import Logger
from . import MSA
from .database import Execution
import json
import os
from datetime import datetime
from .params_parser import ParamsParser

def run_assignment(params, ini, execution_id=None):
    t_start = time.time()
    parser = ParamsParser(params=params, settings=ini)
    params = parser.params

    if execution_id is None:
        execution = Execution.create_execution(params=params)        
        execution_id = execution.id
        log = Logger.getLogger("M4I", execution_id=execution_id)
        log.info("Execution created")
    else:
        log = Logger.getLogger("M4I")
    
    if execution_id is None:
        log.info(f"Executing assignment...")
    else:
        log.info(f"Executing assignment ({execution_id})")
    try:
        parser.set_value("execution_id", execution_id)
        parser.set_default("date_simulation",datetime.now().strftime("%Y-%m-%d"))
        parser.set_default("time_simulation",datetime.now().strftime("%H:%M:%S"))
        # Load the network

        loader: Loader = Loader(parser=parser)
        writer: Writer = Writer(parser=parser)

        # Initialize the simulator
        simulator: BaseSimulator = MicroSimulator(loader=loader)
        #simulator: BaseSimulator = StaticSimulator(loader=loader, links_vdf="vdf")

        # Initialize the MSA
        msa = MSA(
            loader=loader,
            writer=writer,
            max_k=loader.ini.MSA_K,
            max_ite=loader.ini.MSA_MAX_ITE,
            max_rel_gap=loader.ini.MSA_RGAP,
            simulator=simulator,
            save_state_graph=loader.ini.SAVE_GRAPH,
            load_state_graph=loader.ini.LOAD_GRAPH,
            save_state_paths=loader.ini.SAVE_PATHS,
            load_state_paths=loader.ini.LOAD_PATHS)

        # Run the calculation
        msa.run()        
        if execution_id is None:
            log.info("Execution finished in %.2f seconds", time.time() - t_start)
        else:
            Execution.set_execution_success(execution_id)
            log.info(f"Execution ({execution_id}) finished in %.2f seconds", time.time() - t_start)
        
    except Exception as ex:
        if execution_id is None:
            log.info("Execution terminated abnormally in %.2f seconds", time.time() - t_start)  
        else:    
            Execution.set_execution_failed(execution_id, ex=ex, raise_exception=False)
            log.info(f"Execution ({execution_id}) terminated abnormally in %.2f seconds", time.time() - t_start)
        raise ex


