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
