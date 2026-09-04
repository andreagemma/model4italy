import logging


class ExecutionLogger(logging.Logger):
    def __init__(self, name, level=logging.INFO, execution_id=None):
        super().__init__(name, level)
        self.execution_id = execution_id

    def _log(self, level, msg, args, exc_info=None, extra=None, stack_info=False, stacklevel=1):
        if extra is None:
            extra = {}
        extra["execution_id"] = self.execution_id
        super()._log(level, msg, args, exc_info, extra, stack_info, stacklevel)
