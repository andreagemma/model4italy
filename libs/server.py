from flask import Flask, request, jsonify
from libs import Logger
import time
import traceback
import uuid
import json
from threading import Thread
from sqlalchemy.exc import SQLAlchemyError
from .simulators import BaseSimulator, MicroSimulator, StaticSimulator
from .connectors import Loader, FileLoader
from .connectors import FileWriter, BaseWriter
from . import MSA
from .database.database import DB, Execution
from .status import Status

from .utils.util import run_in_thread
from . import simulation
app = Flask(__name__)

# Configure the logger
log = Logger.getLogger("M4I_Server")


@app.route('/execute', methods=['POST'])
def execute_simulation():
    log.info("Received request to execute simulation")

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
    run_simulation_thread(params=params, execution_id=new_execution.id)

    # Immediately return the execution ID
    return Status(status=Status.REQ_SUCCESS, execution_id=new_execution.id).jsonify(), 200

@run_in_thread
def run_simulation_thread(params, execution_id=None):
    try:
        from libs import IniClass
        ini = IniClass()
        
        simulation.run_assignment(params, ini, execution_id)
        
        Execution.set_execution_success(execution=execution_id)


    except Exception as ex:
        traceback.print_exc()
        log.error("Execution terminated abnormally", exc_info=True)

        # Update the database with status "failed"
        Execution.set_execution_failed(execution = execution_id, ex=ex, raise_exception=False)

@app.route('/status/<execution_id>', methods=['GET'])
def get_status(execution_id):
    """Returns the status of a specific execution."""
    session = DB.get_session()
    try:
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
    finally:
        session.close()

def start_server(host, port, debug, config):
    app.run(debug=debug, host=host, port=port)