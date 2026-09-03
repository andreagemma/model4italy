from flask import Flask, request, jsonify
from ..log import Logger
import traceback
import json
from ..database.database import DB, Execution, Session

from ..utils.util import run_in_thread


app = Flask(__name__)

# Configure the logger
log = Logger.getLogger("M4I_Server")


@app.route("/execute", methods=["POST"])
def execute():
    from .status import Status

    log.info("Received request to execute elaboration")

    # Read the `params` parameter from the request
    try:
        execution_params = request.get_json(silent=True)
        if not execution_params:
            return Status(
                status=Status.REQ_ERROR,
                error="Missing JSON body",
                details="The request must include a JSON body matching ExecutionParams",
            ).jsonify(), 400
    except Exception as ex:
        log.error("Error reading request body: %s", ex)
        return Status(
            status=Status.REQ_ERROR, error="Invalid JSON body", details=str(ex)
        ).jsonify(), 400

    # Save the execution in the database with status "pending"

    try:
        # Salva l'intero ExecutionParams nel campo execution.params
        new_execution = Execution.create_execution(execution_params)
    except Exception as ex:
        return Status(
            status=Status.REQ_ERROR, error="Database error", details=str(ex)
        ).jsonify(), 500

    # Launch the calculation asynchronously
    run_execution_in_thread(params=execution_params, execution=new_execution)

    # Immediately return the execution ID
    # Ritorna execution_id, più gli ExecutionParams ricevuti, e Location verso lo status
    resp = Status(
        status=Status.REQ_SUCCESS,
        execution_id=new_execution.id,
        params=execution_params,
    ).jsonify()
    return resp, 200, {"Location": f"/status/{new_execution.id}"}


@run_in_thread
def run_execution_in_thread(params, execution=None):
    from .status import Status
    from .. import Dispatcher

    try:
        from .. import IniClass

        ini = IniClass()

        Dispatcher(params=params, ini=ini, execution=execution).run()

        Execution.set_execution_success(execution_id=execution.id)

    except Exception as ex:
        traceback.print_exc()
        log.error("Execution terminated abnormally", exc_info=True)

        # Update the database with status "failed"
        Execution.set_execution_failed(
            execution_id=execution.id, ex=ex, raise_exception=False
        )


@app.route("/status/<execution_id>", methods=["GET"])
def get_status(execution_id):
    from .status import Status

    """Returns the status of a specific execution."""
    with Session(DB.get_engine(), autoflush=False, autobegin=False) as session:
        try:
            session.begin()
            execution: Execution = (
                session.query(Execution).filter_by(id=execution_id).first()
            )
            if not execution:
                return Status(
                    status=Status.REQ_ERROR,
                    error=f"Execution ID={execution_id} not found",
                ).jsonify(), 404

            # Build the response
            response = Status(
                id=execution.id,
                uuid=execution.uuid,
                status=execution.status,
                start_time=execution.start_time,
                end_time=execution.end_time,
                params=json.loads(execution.params),
                result=execution.result,
                progress=execution.progress,
                last_message=execution.last_message,
                last_message_time=execution.last_message_time,
            )
            return response.jsonify(), 200
        except Exception as ex:
            log.error("Error fetching execution status: %s", ex)
            return Status(
                status=Status.REQ_ERROR, error="Database error", details=str(ex)
            ).jsonify(), 500


def start_server(host, port, debug, config):
    try:
        from ..utils.parallel import Parallel

        Parallel.initialize_parallel(
            num_cpus=config.PARALLEL_NUMCPUS, engine=config.PARALLEL_ENGINE
        )
        app.run(debug=debug, host=host, port=port)
    except Exception as ex:
        log.error("Error running server: %s", ex)
