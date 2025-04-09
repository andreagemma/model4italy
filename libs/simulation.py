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


import asyncio
import websockets
import json
import time
import requests
from datetime import datetime, timedelta

def load_config(path="config.json"):
    with open(path, "r") as f:
        return json.load(f)

def build_payload(config, sim_id, start_time_str):
    end_time = (datetime.strptime(start_time_str, "%H:%M") + timedelta(
        minutes=config["simulation"]["interval_minutes"])).strftime("%H:%M")
    params = config["params"].copy()
    params["aggregated_results"] = f"agg_{start_time_str.replace(':', '')}.csv"

    return {
        "simulation_id": sim_id,
        "start": start_time_str,
        "end": end_time,
        "op": "assignment",
        "settings": config["settings"],
        "params": params
    }

def visualizza_risultati(execution_id):
    print(f"[{execution_id}] ✅ Simulazione completata. Visualizzazione risultati...")

def controlla_stato(execution_id, base_url):
    status_url = f"{base_url}/{execution_id}"
    while True:
        try:
            r = requests.get(status_url)
            r.raise_for_status()
            data = r.json()
            stato = data.get("status")
            if stato == "completed":
                visualizza_risultati(execution_id)
                return
            elif stato == "error":
                print(f"[{execution_id}] ❌ Errore nella simulazione:")
                print(f"  Dettagli: {data.get('details')}")
                return
            elif stato in ["pending", "running"]:
                print(f"[{execution_id}] ⏳ Stato attuale: {stato}. Attesa 5 secondi...")
                time.sleep(5)
        except Exception as e:
            print(f"[{execution_id}] ⚠️ Errore nella richiesta di stato: {e}")
            time.sleep(5)

async def rolling_horizon():
    config = load_config()
    uri_ws = config["server_uri"]
    uri_status = config["status_uri_base"]

    start = datetime.strptime(config["simulation"]["start_time"], "%H:%M")
    end = datetime.strptime(config["simulation"]["end_time"], "%H:%M")
    step = config["simulation"]["interval_minutes"]
    sim_id = config["simulation"]["initial_simulation_id"]

    async with websockets.connect(uri_ws) as websocket:
        while start < end:
            start_str = start.strftime("%H:%M")
            payload = build_payload(config, sim_id, start_str)
            print(f"[{start_str}] 🚀 Invio simulazione rolling-horizon...")
            await websocket.send(json.dumps(payload))
            response = await websocket.recv()
            res_json = json.loads(response)
            execution_id = res_json.get("execution_id")

            if execution_id:
                print(f"[{start_str}] 🆔 ID simulazione: {execution_id}")
                controlla_stato(execution_id, uri_status)
            else:
                print(f"[{start_str}] ❌ Nessun ID ricevuto nella risposta: {response}")

            sim_id += 1
            start += timedelta(minutes=step)

# Avvio
if __name__ == "__main__":
    asyncio.run(rolling_horizon())
