from flask import Flask, request, jsonify
from libs import Logger
import traceback
import json
from .database.database import DB, Execution
from .status import Status

from .utils.util import run_in_thread
from .dispatcher import Dispatcher
from sqlalchemy.orm import Session

app = Flask(__name__)

# Configure the logger
log = Logger.getLogger("M4I_Server")


@app.route('/execute', methods=['POST'])
def execute():
    log.info("Received request to execute elaboration")

    # Read the `params` parameter from the request
    try:
        params = request.json
        if not params:
            return Status(status=Status.REQ_ERROR, error="Invalid or missing 'params' in request").jsonify(), 400
    except Exception as ex:
        log.error("Error reading params: %s", ex)
        return Status(status=Status.REQ_ERROR, error="Error reading 'params'", details= str(ex)).jsonify(), 400

    # Save the execution in the database with status "pending"
    
    try:
        new_execution = Execution.create_execution(params)
    except Exception as ex:
        return Status(status=Status.REQ_ERROR, error="Database error", details=str(ex)).jsonify(), 500

    # Launch the calculation asynchronously
    run_execution_in_thread(params=params, execution_id=new_execution.id)

    # Immediately return the execution ID
    return Status(status=Status.REQ_SUCCESS, execution_id=new_execution.id).jsonify(), 200

@run_in_thread
def run_execution_in_thread(params, execution_id=None):
    try:
        from libs import IniClass
        ini = IniClass()
        
        Dispatcher(params=params, ini=ini, execution_id=execution_id).run()
        
        Execution.set_execution_success(execution=execution_id)


    except Exception as ex:
        traceback.print_exc()
        log.error("Execution terminated abnormally", exc_info=True)

        # Update the database with status "failed"
        Execution.set_execution_failed(execution = execution_id, ex=ex, raise_exception=False)

@app.route('/status/<execution_id>', methods=['GET'])
def get_status(execution_id):
    """Returns the status of a specific execution."""
    with Session(DB.get_engine(), autoflush=False, autobegin=False) as session:       
        try:
            session.begin()
            execution = session.query(Execution).filter_by(id=execution_id).first()
            
            if not execution:
                return Status(status=Status.REQ_ERROR, error=f"Execution ID={execution_id} not found").jsonify(), 404

            # Build the response
            response = Status(
                status=execution.status,
                start_time=execution.start_time,
                end_time=execution.end_time,
                params=json.loads(execution.params),
                result=execution.result,
                execution_id=execution.id,
                execution_uuid=execution.uuid
            )
            return response.jsonify(), 200
        except Exception as ex:
            log.error("Error fetching execution status: %s", ex)
            return Status(status=Status.REQ_ERROR, error="Database error", details=str(ex)).jsonify(), 500

def start_server(host, port, debug, config):
    app.run(debug=debug, host=host, port=port)