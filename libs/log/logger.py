# libs/log/logger.py

import os
import logging
import logging.config
import time
from .mem_formatter import MemFormatter
from .time_formatter import TimeFormatter
from .m4i_formatter import M4IFormatter

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from .execution_logger import ExecutionLogger




class Logger:

    dir_log = "log"
    OUTPUT_LOG = ['default', 'file']
    engine: Engine = None
    log_name = ''
    format = '%(asctime)s | %(levelname)s | %(name)s | %(message)s'
    execution_format = '%(execution_id)s - %(asctime)s | %(last_elapsed).2f/%(elapsed).2fs | %(levelname)s | %(name)s | %(message)s'

    info = logging.info
    error = logging.error
    warning = logging.warning
    debug = logging.debug

    params = []

    loggers = {}
    @staticmethod
    def getLogger(name=None, execution_id=None):        
        """Return a logger with the specified name."""
        #execution_id_str=f"({execution_id})" if execution_id is not None else ''
        name = name or Logger.log_name
        if name in Logger.loggers:
            ret = Logger.loggers[name]
            return ret
        
        ret =  ExecutionLogger(name, execution_id=execution_id)
        Logger.loggers[name] = ret

        if Logger.log_name == '':
            l = logging.getLogger()
        else:
            l = logging.getLogger(Logger.log_name)
        if l.level != logging.NOTSET:
            ret.setLevel(l.level)
        else:
            ret.setLevel(l.parent.level)
        if len(l.handlers)>0:
            for h in l.handlers:
                ret.addHandler(h)
        else:
            if l.parent is not None:
                for h in l.parent.handlers:
                    ret.addHandler(h)
        return ret
    
    @staticmethod
    def setEngine(engine: Engine):
        from ..database import DBHandler
        """Set the engine to be used for logging."""
        Logger.engine = engine
        if engine is not None:
            formatter = M4IFormatter(
                fmt=Logger.format,
                execution_format=Logger.format,
                start_time=time.time(),
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler = DBHandler(Logger.engine)
            handler.setFormatter(formatter)
            handler.setLevel(Logger.level)
            for logger in Logger.loggers.values():                
                for h in logger.handlers:
                    if isinstance(h, DBHandler):
                        logger.removeHandler(h)                
                logger.addHandler(handler)
            logging.getLogger(Logger.log_name).addHandler(handler)
        else:
            for logger in Logger.loggers.values():                
                for h in logger.handlers:
                    if isinstance(h, DBHandler):
                        logger.removeHandler(h)                

    @staticmethod
    def initLogger(level=logging.DEBUG, console=True, file=False, db=False, dir_log=None, engine: Engine=None, log_name='', format=None, execution_format=None):
        Logger.loggers.clear()
        Logger.format = format if format is not None else Logger.format
        Logger.execution_format = execution_format if execution_format is not None else Logger.execution_format
        Logger.dir_log = Logger.dir_log if dir_log is None else dir_log
        Logger.OUTPUT_LOG = []
        if console:
            Logger.OUTPUT_LOG.append('default')
        if file:
            Logger.OUTPUT_LOG.append('file')
        if db:
            Logger.engine = Logger.engine if engine is None else engine
        else:
            Logger.engine = None
        
        Logger.level = logging.DEBUG if level is not None else level
        Logger.log_name = log_name
        logging.getLogger("filelock").setLevel(logging.WARNING)
        Logger.params = {
            'version': 1,
            'disable_existing_loggers': True,
            "formatters": {
                "m4iformatter": {
                    '()': M4IFormatter,  # Usa il formatter personalizzato
                    'format': Logger.format,
                    'execution_format': Logger.execution_format,                    
                    'start_time': time.time(),
                    'datefmt': '%Y-%m-%d %H:%M:%S'
                },
                "memory": {
                    '()': MemFormatter,  # Usa il formatter personalizzato
                    'format': '%(asctime)s | %(last_elapsed).2f/%(elapsed).2fs | %(memory_usage).2fMB/%(max_memory_usage).2fMB | %(message)s',
                    'start_time': time.time(),
                    'datefmt': '%Y-%m-%d %H:%M:%S'
                },
                "timing": {
                    '()': TimeFormatter,  # Usa il formatter personalizzato
                    'format': '%(asctime)s | %(last_elapsed).2f/%(elapsed).2fs | %(levelname)s | %(name)s | %(message)s',
                    'start_time': time.time(),
                    'datefmt': '%Y-%m-%d %H:%M:%S'
                },
                "standard": {
                    'format': '%(asctime)s | %(levelname)s | %(name)s | %(message)s',
                    'datefmt': '%Y-%m-%d %H:%M:%S'
                },
                "multithread": {
                    'format': '%(asctime)s | th:%(threadName)s %(thread)d | %(levelname)s | %(name)s | %(message)s',
                    'datefmt': '%Y-%m-%d %H:%M:%S'
                },
                "debug": {
                    '()': MemFormatter,  # Usa il formatter personalizzato
                    'format': '%(asctime)s | [%(last_elapsed).2f/%(elapsed).2fs] | %(levelname)s | %(name)s | %(module)s | %(lineno)d | %(memory_usage).2fMB | %(message)s',
                    'datefmt': '%Y-%m-%d %H:%M:%S'
                },
                "plain": {
                    '()': MemFormatter,  # Usa il formatter personalizzato
                    "format": '%(message)s | Memoria: %(memory_usage).2f MB'
                }
            },
            'handlers': {
                'default': {
                    'formatter': 'm4iformatter',
                    'class': 'logging.StreamHandler',
                },
                'file': {
                    'formatter': 'timing',
                    'class': 'logging.handlers.RotatingFileHandler',
                    'filename': os.path.join(Logger.dir_log, "traffic_simulator.log"),
                    'maxBytes': 10485760,
                    'backupCount': 10
                }
            },
            'loggers': {
                Logger.log_name: {  # valido per tutti i logger
                    'handlers': Logger.OUTPUT_LOG,
                    'level': Logger.level  # si puo usare 'DEBUG,INFO,WARNING,ERROR'
                }                
            }
        }
        if Logger.engine:
            Logger.params['handlers']['db'] = {
                'formatter': 'm4iformatter',
                'class': 'libs.database.DBHandler',
                'engine': Logger.engine
            }
            Logger.OUTPUT_LOG.append('db')
            
        if 'file' in Logger.OUTPUT_LOG and not os.path.exists(Logger.dir_log):
            os.makedirs(Logger.dir_log)

        logging.config.dictConfig(Logger.params)
        logging.debug("Logger configured correctly")

