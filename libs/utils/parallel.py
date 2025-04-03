from __future__ import annotations
from typing import Optional, Iterable, Generator, Callable
import multiprocessing
import importlib
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed, ProcessPoolExecutor

try:
    import ray
except ImportError:
    pass

try:
    import dask
    from dask.distributed import Client    
except ImportError:
    pass



class Parallel:
    ENGINE_RAY = "ray"
    ENGINE_DASK = "dask"
    ENGINE_DASK_MULTITHREADING = "dask_multithreading"
    ENGINE_NONE = "none"
    ENGINE_MULTITHREADING = "threading"

    ray_initialized = False  # Class variable to trace Ray's initialization
    dask_initialized = False  # Class variable to trace Dask's initialization
    num_cpus = multiprocessing.cpu_count()  # Class parameter for the number of CPUs
    parallel_engine = "none"  # Parameter to select the parallel engine ('Ray' O 'dask', 'dask_treahding', 'none')


    @staticmethod
    def initialize_parallel(num_cpus: Optional[int] = None, engine: Optional[str] = None):
        n = Parallel.num_cpus if num_cpus is None else num_cpus
        if engine is not None:
            Parallel.parallel_engine = engine

        if n < 0:  # If <0 then leaves the number of processors free
            num_cpus = max(1, multiprocessing.cpu_count() + n)
        else:  # If> 0 then use the number of processors indicated
            num_cpus = max(1, min(multiprocessing.cpu_count(), n))
        Parallel.num_cpus = num_cpus
        if num_cpus==1:
            return num_cpus
        if Parallel.parallel_engine == Parallel.ENGINE_RAY and num_cpus>1:
            if importlib.util.find_spec("ray") is None:
                raise ImportError("Ray is not installed. Please install it using 'pip install ray'")
            if not Parallel.ray_initialized:
                try:
                    ray.init(num_cpus=num_cpus)
                    Parallel.ray_initialized = True
                except:
                    Parallel.ray_initialized = False
                return num_cpus
            else:
                return ray.available_resources()["CPU"]
        elif Parallel.parallel_engine == Parallel.ENGINE_DASK and num_cpus>1:
            if importlib.util.find_spec("dask") is None:
                raise ImportError("Dask is not installed. Please install it using 'pip install dask'")
            if not Parallel.dask_initialized:
                Parallel.dask_client = Client(n_workers=num_cpus)
                Parallel.dask_initialized = True
                return num_cpus
            else:
                return len(Parallel.dask_client.nthreads())
        elif Parallel.parallel_engine == Parallel.ENGINE_DASK_MULTITHREADING and num_cpus>1:
            if importlib.util.find_spec("dask") is None:
                raise ImportError("Dask is not installed. Please install it using 'pip install dask'")
            if not Parallel.dask_initialized:
                Parallel.dask_client = Client(processes=False, threads_per_worker=num_cpus, n_workers=1)
                Parallel.dask_initialized = True
                return num_cpus
            else:
                return len(Parallel.dask_client.nthreads())
        elif Parallel.parallel_engine == Parallel.ENGINE_MULTITHREADING and num_cpus>1:
            return num_cpus
        else:
            return 1       

    @staticmethod
    def shutdown_parallel():
        if Parallel.parallel_engine == Parallel.ENGINE_RAY and Parallel.ray_initialized:
            try:
                if Parallel.ray_initialized:
                    ray.shutdown()
                Parallel.ray_initialized = False
            except Exception as ex:
                logging.error("Error during ray shutdown.", exc_info=True)

        elif Parallel.parallel_engine in [Parallel.ENGINE_DASK, Parallel.ENGINE_DASK_MULTITHREADING] and Parallel.dask_initialized:
            try:
                Parallel.dask_client.close()
                Parallel.dask_initialized = False
            except Exception as ex:
                logging.error("Error during dask shutdown.", exc_info=True)

    @staticmethod
    def execute(fn:Callable, tasks: Iterable[dict], engine: Optional[str] = None, n_workers: Optional[int]=None, chunk_size:Optional[int]=None, **kwargs) ->Generator:
        tasks = list(tasks)

        engine = engine or Parallel.parallel_engine
        num_cpus = Parallel.initialize_parallel(n_workers, engine=engine)            
        chunk_size = int(max(1, len(tasks) // (num_cpus) ))  if chunk_size is None else chunk_size # Divides on the CPUs
        pair_chunks = [tasks[i : i + chunk_size] for i in range(0, len(tasks), chunk_size)]

        if engine == Parallel.ENGINE_RAY and num_cpus>1:    
            pair_chunks_refs = [ray.put(chunk) for chunk in pair_chunks]

            @ray.remote
            def calculate(*args, **kwargs):
                return fn(*args, **kwargs)

            ref_kwargs = {}
            for k, v in kwargs.items():
                if isinstance(v, (float, int, str, bool, complex)):
                    ref_kwargs[k] = v
                else:                
                    ref_kwargs[k] = ray.put(v)

            result_ids = [calculate.remote(tasks=chunk_ref, **ref_kwargs) for chunk_ref in pair_chunks_refs]

            while result_ids:
                done_ids, result_ids = ray.wait(result_ids)
                for done_id in done_ids:
                    paths = ray.get(done_id)
                    yield paths

        elif engine in [Parallel.ENGINE_DASK, Parallel.ENGINE_DASK_MULTITHREADING]:

            @dask.delayed
            def calculate(*args, **kwargs):
                return fn(*args, **kwargs)

            delayed_results = [calculate(tasks=chunk,  **kwargs) for chunk in pair_chunks]
            results = dask.compute(*delayed_results)
            for paths in results:
                yield paths

        elif engine == Parallel.ENGINE_MULTITHREADING and num_cpus>1:

            def calculate(*args, **kwargs):
                return fn(*args, **kwargs)
            
            with ThreadPoolExecutor(max_workers=num_cpus) as executor:
                futures = {executor.submit(calculate, tasks=chunk, **kwargs): chunk for chunk in pair_chunks}

                # Attend results
                for future in as_completed(futures):
                    yield future.result()
        
        else:
            ret = fn(tasks=tasks, **kwargs)
            yield ret
  