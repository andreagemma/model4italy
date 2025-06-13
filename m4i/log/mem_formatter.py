import time
from datetime import datetime, timedelta
from ..utils.util import memory_usage
import logging
from .time_formatter import TimeFormatter

class MemFormatter(TimeFormatter):

    def __init__(self, fmt=None, datefmt=None, elapsed_dfmt="%H:%M:%S", start_time=None):
        super().__init__(fmt, datefmt, elapsed_dfmt=elapsed_dfmt)
        self.elapsed_dfmt = elapsed_dfmt or datetime.isoformat()
        self.last_log_time = time.time()
        self.start_time = time.time() if start_time is None else start_time

        self.max_memory_usage = 0
        self.avg_memory_usage = 0
        self.n_count = 0

    def format(self, record):
        # Aggiungi l'uso della memoria al record
        mem = memory_usage()
        self.max_memory_usage = max(mem, self.max_memory_usage)
        self.avg_memory_usage *= self.n_count
        self.avg_memory_usage += mem
        self.n_count += 1
        self.avg_memory_usage /= self.n_count

        record.max_memory_usage = self.max_memory_usage
        record.avg_memory_usage = self.avg_memory_usage
        record.memory_usage = mem
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
    