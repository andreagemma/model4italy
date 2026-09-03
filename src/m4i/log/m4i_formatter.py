import time
from datetime import datetime, timedelta
from ..utils.util import memory_usage
from .time_formatter import TimeFormatter
import logging

class M4IFormatter(TimeFormatter):
    

    def __init__(self, fmt=None, datefmt=None, elapsed_dfmt="%H:%M:%S", start_time=None, execution_format=None):
        super().__init__(fmt=fmt, datefmt=datefmt, elapsed_dfmt=elapsed_dfmt, start_time=start_time)
        self.execution_format = execution_format or self._fmt

    def format(self, record):
        if hasattr(record, 'execution_id') and record.execution_id is not None:
            self._style._fmt = self.execution_format
        else:
            self._style._fmt = self._fmt
        return super().format(record)

