import time
from datetime import datetime, timedelta
from ..utils.util import memory_usage
import logging

class TimeFormatter(logging.Formatter):
    

    def __init__(self, fmt=None, datefmt=None, elapsed_dfmt="%H:%M:%S", start_time=None):
        super().__init__(fmt, datefmt)
        self.elapsed_dfmt = elapsed_dfmt or datetime.isoformat()
        self.start_time = time.time()
        self.last_log_time = self.start_time if start_time is None else start_time
    def format(self, record):

        t = time.time()
        elapsed_seconds = t - self.start_time

        record.elapsed = elapsed_seconds
        record.last_elapsed = t - self.last_log_time
        self.last_log_time = t

        elapsed_time = timedelta(seconds=elapsed_seconds)
        elapsed_datetime = (datetime.min + elapsed_time)

        if self.elapsed_dfmt:
            record.elapsed_datetime = elapsed_datetime.strftime(self.elapsed_dfmt)
        else:
            record.elapsed_datetime = elapsed_datetime.strftime(datetime.isoformat())

        return super().format(record)    