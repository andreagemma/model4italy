import requests, json, time
from libs.utils import run_in_thread
from libs.status import Status
url = "http://localhost:5000/execute"
with open("params.json") as f:
    params = f.read()
params = json.loads(params)
response = requests.post(url, json=params)

ret = response.json()
if response.status_code == 200:    
    print("Success:", ret)
    execution_id = ret["execution_id"]
else:
    print("Error:", ret)


url = f"http://localhost:5000/status/{execution_id}"
while True:
    time.sleep(1)
    response = requests.get(url)
    ret = response.json()
    if response.status_code == 200:    
        #print("Success:", ret)
        status = ret["status"]
        print(f"Status: {status}")
        if status in (Status.SIM_PENDING,):
            continue
        elif status in (Status.SIM_COMPLETED, ):
            print(f"Completed")
            break
        elif status in (Status.SIM_FAILED, ):
            print(f"Failed", ret["result"] )
            break
    else:
        print("Error:", ret)
        break

import json
import time
import requests
from datetime import datetime, timedelta

def load_config(path="config.json"):
    with open(path, "r") as f:
        return json.load(f)

def build_payload(config, sim_id, start_time_str):
    end_time = (datetime.strptime(start_time_str, "%H:%M") +
                timedelta(minutes=config["simulation"]["interval_minutes"])).strftime("%H:%M")

    # Copia profonda per evitare side effects
    params = json.loads(json.dumps(config["params"]))
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

def controlla_stato(execution_id, status_uri_base):
    url = f"{status_uri_base}/{execution_id}"
    while True:
        try:
            response = requests.get(url)
            response.raise_for_status()
            result = response.json()
            stato = result.get("status")
            if stato == "completed":
                visualizza_risultati(execution_id)
                return
            elif stato == "error":
                print(f"[{execution_id}] ❌ Errore nella simulazione:")
                print(f"  Dettagli: {result.get('details')}")
                return
            elif stato in ("pending", "running"):
                print(f"[{execution_id}] ⏳ Stato: {stato}. Attendo 5 secondi...")
                time.sleep(5)
        except Exception as e:
            print(f"[{execution_id}] ⚠️ Errore nella richiesta di stato: {e}")
            time.sleep(5)

def rolling_horizon():
    config = load_config()
    url_execute = config["server_uri"].replace("ws://", "http://").replace("/ws/execute", "/execute")
    url_status_base = config["status_uri_base"]

    start = datetime.strptime(config["simulation"]["start_time"], "%H:%M")
    end = datetime.strptime(config["simulation"]["end_time"], "%H:%M")
    sim_id = config["simulation"]["initial_simulation_id"]
    step = config["simulation"]["interval_minutes"]

    while start < end:
        start_str = start.strftime("%H:%M")
        payload = build_payload(config, sim_id, start_str)

        try:
            print(f"[{start_str}] 🚀 Invio richiesta POST /execute")
            r = requests.post(url_execute, json=payload)
            r.raise_for_status()
            data = r.json()
            execution_id = data.get("execution_id")

            if execution_id:
                print(f"[{start_str}] 🆔 Simulazione ID: {execution_id}")
                controlla_stato(execution_id, url_status_base)
            else:
                print(f"[{start_str}] ⚠️ Nessun execution_id ricevuto. Risposta: {data}")

        except Exception as e:
            print(f"[{start_str}] ❌ Errore nella POST /execute: {e}")

        sim_id += 1
        start += timedelta(minutes=step)

if __name__ == "__main__":
    rolling_horizon()
