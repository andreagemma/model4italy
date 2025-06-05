from flask import jsonify

class Status(dict):
    REQ_SUCCESS = "success"
    REQ_ERROR = "error"


    SIM_COMPLETED = "completed"
    SIM_RUNNING = "running"
    SIM_PENDING = "pending"
    SIM_FAILED = "failed"

    def __init__(self, status, error=None, details=None, execution_id=None, execution_uuid=None, **kwargs):
        self.status = status
        self.error = error
        self.details = details
        self.execution_id = execution_id
        self.execution_uuid = execution_uuid
        self.__dict__.update(kwargs)

    def to_dict(self):
        ret = self.__dict__.copy()
        for k, v in ret.copy().items():
            if v is None:
                del ret[k]
        return ret

    def jsonify(self):
        return jsonify(self.to_dict())