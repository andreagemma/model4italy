from threading import Thread
from functools import lru_cache, wraps
from time import process_time, time, sleep
from inspect import getmodule
import logging
from dataclasses import fields, is_dataclass
from typing import Type, Any
from datetime import datetime

stat_results = {}


def stat_calls(func):
    """
    The `stat_calls` function is a decorator that tracks the number of times a decorated function is
    called.
    
    :param func: The `func` parameter is a function that we want to wrap with the `stat_calls` decorator
    :return: The function `wrapper` is being returned.
    """
    def wrapper(*args, **kwargs):
        wrapper.results[wrapper.name]["calls"] += 1
        return func(*args, **kwargs)

    wrapper.name = f"{getmodule(func).__name__}.{func.__name__}"
    wrapper.results = stat_results
    if wrapper.name in stat_results:
        wrapper.results[wrapper.name]["calls"] = 0
    else:
        wrapper.results[wrapper.name] = {"calls": 0}
    return wrapper


def stat_timing(func):
    """
    The `stat_timing` function is a decorator that measures the execution time of a function and stores
    the results in a dictionary.
    
    :param func: The `func` parameter is a function that you want to time
    :return: The function `stat_timing` is returning the wrapper function.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        tic = time()
        ret = func(*args, **kwargs)
        toc = time()
        wrapper.results[wrapper.name]["timinig"] += toc - tic
        return ret

    wrapper.name = f"{getmodule(func).__name__}.{func.__name__}"
    wrapper.results = stat_results
    if wrapper.name in stat_results:
        wrapper.results[wrapper.name]["timinig"] = 0
    else:
        wrapper.results[wrapper.name] = {"timinig": 0}
    wrapper.num_calls = 0
    return wrapper


def run_in_thread(func):
    """
    The `run_in_thread` function is a decorator that allows a function to be run in a separate thread.
    
    :param func: The `func` parameter is the function that you want to run in a separate thread
    :return: The function `run_in_thread` returns a wrapper function that starts a new thread and
    returns the thread object.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        t = Thread(target=func, args=args, kwargs=kwargs)
        t.start()
        return t

    return wrapper


def log_execution(logger=None, log_args=False, log_result=False):
    """
    The `log_execution` function is a decorator that logs the execution of a function, including its
    arguments and result, if specified.
    
    :param logger: The `logger` parameter is an instance of a logging object that is used to log the
    execution details of the decorated function
    :param log_args: The `log_args` parameter is a boolean flag that determines whether the arguments
    passed to the decorated function should be logged. If `log_args` is set to `True`, the arguments
    will be logged; otherwise, they will not be logged, defaults to False (optional)
    :param log_result: The `log_result` parameter is a boolean flag that determines whether or not to
    log the result of the function execution. If set to `True`, the result will be logged; if set to
    `False`, the result will not be logged, defaults to False (optional)
    :return: The function `log_execution` returns a decorator function.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            log = logger or logging.getLogger()
            wrapper.id += 1
            t, pt = time(), process_time()
            if log_args:
                log.debug(f"Executing {getmodule(func).__name__}.{func.__name__} (id:{wrapper.id}) with args: {args} and kwargs: {kwargs}")
            else:
                log.debug(f"Executing {getmodule(func).__name__}.{func.__name__} (id:{wrapper.id})")
            results = func(*args, **kwargs)
            if log_result:
                log.debug(
                    f"Execution of {getmodule(func).__name__}.{func.__name__} (id:{wrapper.id}) completed in {time() - t} s (process_time = {process_time() - pt} s) - results = {results}")
            else:
                log.debug(f"Execution of {getmodule(func).__name__}.{func.__name__} (id:{wrapper.id}) completed in {time() - t} s (process_time = {process_time() - pt} s)")
            return results

        wrapper.id = 0
        return wrapper

    return decorator


def retry(max_tries=3, delay_seconds=1):
    """
    The `retry` function is a decorator that allows a function to be retried a specified number of times
    with a delay between each retry.
    
    :param max_tries: The max_tries parameter specifies the maximum number of times the decorated
    function will be retried if it raises an exception. By default, it is set to 3, defaults to 3
    (optional)
    :param delay_seconds: The `delay_seconds` parameter specifies the number of seconds to wait before
    retrying the function after an exception is caught, defaults to 1 (optional)
    :return: The function `retry` returns a decorator function `decorator_retry`.
    """
    def decorator_retry(func):
        @wraps(func)
        def wrapper_retry(*args, **kwargs):
            tries = 0
            while tries < max_tries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    tries += 1
                    if tries == max_tries:
                        raise e
                    sleep(delay_seconds)

        return wrapper_retry

    return decorator_retry


def cached(func):
    """
    The `cached` function is a decorator that caches the results of a function call to improve
    performance by avoiding redundant computations.
    
    :param func: The `func` parameter is a function that will be wrapped with caching functionality
    :return: The function `cached` returns the wrapper function `wrapper`.
    """
    cache = {}

    def wrapper(*args):
        if args in cache:
            return cache[args]
        else:
            result = func(*args)
            cache[args] = result
            return result

    return wrapper

def add_dict_methods(cls: Type[Any]) -> Type[Any]:
    """
    Decoratore che aggiunge metodi to_dict e from_dict a una dataclass.
    - to_dict: restituisce un dizionario dei suoi campi.
    - from_dict: aggiorna i campi della classe con i valori dal dizionario, convertendo
      i valori nel tipo appropriato.
    """
    if not is_dataclass(cls):
        raise TypeError("add_dict_methods decorator should be applied to dataclasses only.")

    def to_dict(self) -> dict:
        return {field.name: getattr(self, field.name) for field in fields(self)}

    cls.to_dict = to_dict    
    return cls

def print_constructor_params(cls):
    """
    Decoratore di classe che stampa i parametri passati al costruttore.
    """
    # Memorizza il costruttore originale
    orig_init = cls.__init__

    # Definisci un nuovo costruttore che stampa i parametri
    @wraps(orig_init)
    def new_init(self, *args, **kwargs):
        print(f"Costruendo {cls.__name__} con args={args} e kwargs={kwargs}")
        orig_init(self, *args, **kwargs)

    # Sostituisci il costruttore originale con quello nuovo
    cls.__init__ = new_init

    return cls