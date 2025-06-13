from __future__ import annotations
from typing import Optional, Iterable, Generator, Callable
import multiprocessing
import importlib
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import dill
import os

class Parallel:
    ENGINE_RAY = "ray"
    ENGINE_DASK = "dask"
    ENGINE_DASK_MULTITHREADING = "dask_multithreading"
    ENGINE_NONE = "none"
    ENGINE_MULTITHREADING = "threading"

    ray_initialized = False  # Class variable to trace Ray's initialization
    dask_initialized = False  # Class variable to trace Dask's initialization
    dask_client = None  # Class variable to trace Dask's client
    num_cpus = 1  # Class variable to trace the number of CPUs
    parallel_engine = ENGINE_NONE  # Class variable to trace the parallel engine
    initialzations = 0  # Class variable to trace the initialization of the parallel engine
    dask_cluster = None  # Class variable to trace the Dask cluster
    log = None

    @staticmethod
    def get_num_cpus(num_cpus) -> int:
        if Parallel.initialzations > 0:
            return Parallel.num_cpus
        if num_cpus is None:
            num_cpus = multiprocessing.cpu_count() - 1
        elif num_cpus <= 0:  # If <0 then leaves the number of processors free
            num_cpus = max(1, multiprocessing.cpu_count() + num_cpus)
        else:  # If> 0 then use the number of processors indicated
            num_cpus = max(1, min(multiprocessing.cpu_count(), num_cpus))        
        return num_cpus
    
    @staticmethod
    def get_num_min_cpus(num_cpus) -> int:        
        if Parallel.initialzations > 0:
            max_cpus = Parallel.num_cpus
        else:
            max_cpus = multiprocessing.cpu_count()
        if num_cpus is None:
            num_cpus = max_cpus - 1
        elif num_cpus <= 0:  # If <0 then leaves the number of processors free
            num_cpus = max(1, max_cpus + num_cpus)
        else:  # If> 0 then use the number of processors indicated
            num_cpus = max(1, min(max_cpus, num_cpus))  
        return min(max_cpus, num_cpus)        
        #return num_cpus
    
    @staticmethod
    def initialize_parallel(num_cpus: Optional[int] = None, engine: Optional[str] = None,
                            **kwargs) -> int:
        if Parallel.log is None:
            try:
                from ..log import Logger
                Parallel.log = Logger.getLogger(Parallel.__class__.__name__)
            except ImportError:
                Parallel.log = logging.log.getLogger(Parallel.__class__.__name__)
                Parallel.log.setLevel(logging.log.INFO)
                ch = logging.log.StreamHandler()
                ch.setLevel(logging.log.INFO)
                formatter = logging.log.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                ch.setFormatter(formatter)
                logging.log.addHandler(ch)
        if Parallel.initialzations > 0:
            Parallel.log.warning(f"Parallel engine already initialized ({Parallel.num_cpus} CPUs available with {Parallel.parallel_engine} engine).")
            Parallel.initialzations += 1
            return Parallel.num_cpus
        num_cpus = Parallel.get_num_cpus(num_cpus)  # Get the number of CPUs
        Parallel.num_cpus = num_cpus # parameter for the number of CPUs
        Parallel.initialzations += 1
        if engine is None:
            engine = Parallel.ENGINE_NONE
        
        
        if engine == Parallel.ENGINE_RAY:
            try:
                import ray
                ray.util.register_serializer(dict, serializer=dill.dumps, deserializer=dill.loads)
                os.environ["RAY_COLOR_PREFIX"] = "1"
            except ImportError:
                pass
            if importlib.util.find_spec("ray") is None:
                Parallel.log.warning("Ray is not installed. Please install it using 'pip install ray'")
                engine = Parallel.ENGINE_MULTITHREADING
                Parallel.log.warning("Switching to multi-threaded mode.")
        if engine in (Parallel.ENGINE_DASK, Parallel.ENGINE_DASK_MULTITHREADING):
            try:
                import dask
                from dask.distributed import Client    
            except ImportError:
                pass
            if importlib.util.find_spec("dask") is None:
                Parallel.log.warning("Dask is not installed. Please install it using 'pip install dask'")
                engine = Parallel.ENGINE_MULTITHREADING
                Parallel.log.warning("Switching to multi-threaded mode.")
        Parallel.parallel_engine = engine or "none"  # Parameter to select the parallel engine ('Ray' O 'dask', 'dask_treahding', 'none')
        
        
        if Parallel.num_cpus==1:
            Parallel.parallel_engine = Parallel.ENGINE_NONE
            return Parallel.num_cpus
        if Parallel.parallel_engine == Parallel.ENGINE_RAY and Parallel.num_cpus>1:
            if importlib.util.find_spec("ray") is None:
                raise ImportError("Ray is not installed. Please install it using 'pip install ray'")
            if not Parallel.ray_initialized:
                try:
                    import ray
                    ray.util.register_serializer(dict, serializer=dill.dumps, deserializer=dill.loads)
                    kwargs["ignore_reinit_error"] = True
                    address = kwargs.pop("address", None)
                    if address and address.lower() != "local":
                        try:
                            ray.init(address=address,**kwargs) 
                        except ConnectionError:
                            Parallel.log.error("Ray is not initialized. Please check the address and try again.")
                            kwargs.pop("address")
                            ray.init(address="local", num_cpus=num_cpus, **kwargs)
                            Parallel.log.warning("Ray is initialized with default settings.")
                    else:
                        ray.init(address="local", num_cpus=num_cpus)
                    Parallel.num_cpus = int(ray.cluster_resources()["CPU"])
                    Parallel.ray_initialized = True
                    Parallel.initialzed = True
                except Exception as ex:
                    Parallel.parallel_engine = Parallel.ENGINE_MULTITHREADING
                    Parallel.log.error("Error during ray initialization. {ex}", exc_info=True)
                    Parallel.log.warning("Ray is not initialized. Switching to multi-threaded mode.")
                    Parallel.ray_initialized = False
                return Parallel.num_cpus
            else:
                return ray.available_resources()["CPU"]
        elif Parallel.parallel_engine == Parallel.ENGINE_DASK and Parallel.num_cpus>1:
            if importlib.util.find_spec("dask") is None:
                raise ImportError("Dask is not installed. Please install it using 'pip install dask'")
            if not Parallel.dask_initialized:
                try:
                    import dask
                    from dask.distributed import Client
                    Parallel.dask_cluster = dask.distributed.LocalCluster(n_workers=num_cpus, threads_per_worker=1, memory_limit="auto")
                    Parallel.dask_client = Parallel.dask_cluster.get_client()
                    Parallel.dask_initialized = True
                except:
                    Parallel.parallel_engine = Parallel.ENGINE_MULTITHREADING
                    Parallel.log.error("Error during dask initialization.", exc_info=True)
                    Parallel.log.warning("Dask is not initialized. Switching to multi-threaded mode.")
                    Parallel.dask_initialized = False
                return Parallel.num_cpus
            else:
                return len(Parallel.dask_client.nthreads())
        elif Parallel.parallel_engine == Parallel.ENGINE_DASK_MULTITHREADING and Parallel.num_cpus>1:
            if importlib.util.find_spec("dask") is None:
                raise ImportError("Dask is not installed. Please install it using 'pip install dask'")
            if not Parallel.dask_initialized:
                try:
                    import dask
                    from dask.distributed import Client
                    Parallel.dask_client = Client(processes=False, threads_per_worker=num_cpus, n_workers=1)
                    Parallel.dask_initialized = True
                except:
                    Parallel.parallel_engine = Parallel.ENGINE_MULTITHREADING
                    Parallel.log.error("Error during dask initialization.", exc_info=True)
                    Parallel.log.warning("Dask is not initialized. Switching to multi-threaded mode.")
                    Parallel.dask_initialized = False
                return Parallel.num_cpus
            else:
                return len(Parallel.dask_client.nthreads())
        elif Parallel.parallel_engine == Parallel.ENGINE_MULTITHREADING and Parallel.num_cpus>1:
            return Parallel.num_cpus
        else:
            Parallel.num_cpus=1
            return 1
        
    @staticmethod
    def shutdown_parallel(force=False):
        Parallel.initialzations -= 1
        if Parallel.initialzations > 0 and not force:
            Parallel.log.warning("Parallel engine not shutdown. Parallel engine is still in use.")
            return
        if Parallel.parallel_engine == Parallel.ENGINE_RAY and Parallel.ray_initialized:
            try:
                import ray
                if Parallel.ray_initialized:
                    ray.shutdown()
                Parallel.ray_initialized = False
            except Exception as ex:
                pass#Parallel.log.error("Error during ray shutdown.")

        elif Parallel.parallel_engine in [Parallel.ENGINE_DASK, Parallel.ENGINE_DASK_MULTITHREADING] and Parallel.dask_initialized:
            try:
                Parallel.dask_client.close()
                Parallel.dask_initialized = False
            except Exception as ex:
                pass#Parallel.log.error("Error during dask shutdown.", exc_info=True)

    @staticmethod
    def execute(fn:Callable, tasks: Iterable[dict], engine: Optional[str] = None, n_workers: Optional[int]=None, chunk_size:Optional[int]=None, **kwargs) ->Generator:
        tasks = list(tasks)

        if engine is not None or n_workers is not None:
            if Parallel.initialzations == 0:
                Parallel.initialize_parallel(num_cpus=n_workers, engine=engine)
            
        
        engine = Parallel.parallel_engine
        if engine is None or engine == Parallel.ENGINE_NONE:
            n_workers=None
        if n_workers is not None:
            num_cpus = Parallel.get_num_min_cpus(n_workers)
            if num_cpus!= Parallel.num_cpus:
                if num_cpus == 1:
                    Parallel.log.warning("n_workers = 1. Using single CPU in a single thread mode.")
                else:
                    Parallel.log.debug(f"Using {num_cpus} on {Parallel.num_cpus} workers with {Parallel.parallel_engine} engine.")
        else:
            num_cpus = Parallel.num_cpus
        
          
        chunk_size = int(max(1, len(tasks) // (num_cpus) ))  if chunk_size is None else chunk_size # Divides on the CPUs
        pair_chunks = [tasks[i : i + chunk_size] for i in range(0, len(tasks), chunk_size)]

        if engine == Parallel.ENGINE_RAY and num_cpus>1 and Parallel.ray_initialized:    
            import ray
            ray.util.register_serializer(dict, serializer=dill.dumps, deserializer=dill.loads)
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

        elif engine in [Parallel.ENGINE_DASK, Parallel.ENGINE_DASK_MULTITHREADING] and num_cpus>1 and Parallel.dask_initialized:
            import dask
            from dask.distributed import Client
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
  
    @staticmethod
    def run(fn:Callable, params: dict, engine: Optional[str] = None, **kwargs) ->Generator:
        tasks = [params]
        Parallel.execute(fn, tasks, engine=engine, n_workers=None, chunk_size=1, **kwargs)
