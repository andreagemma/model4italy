import time
import traceback
from .simulators import BaseSimulator, MicroSimulator, StaticSimulator
from .loaders import BaseLoader, FileLoader
from .writers import FileWriter, BaseWriter
from . import Logger
from . import MSA
from .database import Execution
import json
import os

def run_assignment(params, ini, execution_id=None):
    t_start = time.time()
    if isinstance(params, str):
        if os.path.exists(params):
            with open(params, "r") as f:
                params = json.load(f)
        else:            
            params = json.loads(params)
    if not isinstance(params, dict):    
        raise ValueError("Invalid 'params' parameter")

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
        params["execution_id"] = execution_id

        # Load the network
        cls_name = params.get("params", {}).get("input", {}).get("loader", "FileLoader")
        ClassLoader = BaseLoader.get_cls_by_name(cls_name)
        cls_name = params.get("params", {}).get("output", {}).get("writer", "FileWriter")
        ClassWriter = BaseWriter.get_cls_by_name(cls_name)

        loader: BaseLoader = ClassLoader(params=params, settings=ini)
        writer: BaseWriter = ClassWriter(params=params, settings=ini, loader=loader)
        loader.load()

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
