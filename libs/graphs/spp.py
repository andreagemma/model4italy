from __future__ import annotations
from typing import *
from numbers import Number
from heapq import heappush as push
from heapq import heappop as pop
from .. import Logger
import copy
from math import isnan
from itertools import product
 

import multiprocessing, threading
from concurrent.futures import ThreadPoolExecutor, as_completed, ProcessPoolExecutor
import dill
from multiprocessing import get_context, reduction

from . import *

try:
    import ray
    ray.util.register_serializer(dict, serializer=dill.dumps, deserializer=dill.loads)
except Exception as ex:
    print(ex)
    pass

try:
    import dask
    from dask.distributed import Client
except Exception as ex:
    print(ex)
    pass

class SPP:

    ENGINE_RAY = "ray"
    ENGINE_DASK = "dask"
    ENGINE_DASK_MULTITHREADING = "dask_multithreading"
    ENGINE_NONE = "none"
    ENGINE_MULTITHREADING = "threading"

    ray_initialized = False  # Variabile di classe per tracciare l'inizializzazione di Ray
    dask_initialized = False  # Variabile di classe per tracciare l'inizializzazione di Dask
    num_cpus = multiprocessing.cpu_count()  # Parametro di classe per il numero di CPU
    parallel_engine = "none"  # Parametro per selezionare il motore parallelo ('ray' o 'dask','dask_treahding','none')


    @staticmethod
    def dijkstra(
        graph: AbstractGraph,
        source: Union[AbstractNode, Hashable],
        targets: Optional[Union[Iterable[Hashable], Hashable]] = None,
        t_start: Number = 0,
        t_base: Number = 0,
        modes: Optional[Union[str,set[str]]] = None,
        link_cost: Optional[str] = "time",
        node_cost: Optional[str] = None,
        turn_cost: Optional[str] = None,
        link_mode: Optional[str] = None,
        node_mode: Optional[str] = None,
        turn_mode: Optional[str] = None,
        **kwargs,
    ) -> Union[PathContainer]:


        if isinstance(source, AbstractNode):
            source_node = source
            source = source["idx"]
        else:
            source_node = graph.get_node(source)

        if modes is None:
            modes = set(None)
        if isinstance(modes, str):
            modes = set([modes])
        targets = set(targets) if targets is not None else set(graph["nodes"].keys())
        pl = PathList()
        
        for mode in modes:
            residual_targets = targets.copy()

            l: Optional[AbstractLink] = None
            next_l: Optional[AbstractLink] = None
            current_l: Optional[AbstractLink] = None

            visited = set()

            paths_links = {l["idx"]: [] for l in graph.get_all_links()}
            #paths_links = {}
            paths_costs = {}

            node_costs = {}
            node_preds = {}

            pq = []
            # calcolo dei costi a partire dalla sorgente
            for l in graph.get_fws(source):
                kwargs = {"t": t_base + t_start, "in_link": None, "out_link": l, "graph": graph, "mode": mode}
                if node_mode is not None:
                    available_modes: set = source_node.get_value(name=node_mode, default=set(), **kwargs)
                    if not (modes & available_modes or "all" in available_modes):
                        continue

                if link_mode is not None:
                    available_modes: set = l.get_value(name=link_mode, default=set(), **kwargs)
                    if not (modes & available_modes or "all" in available_modes):
                        continue
                
                l_i, l_j, l_idx = l["i"], l["j"], l["idx"]
                initial_cost = l.get_value(name=link_cost, default=0, **kwargs)
                initial_cost += graph.get_node(l_i).get_value(name=node_cost,default=0, **kwargs)

                paths_costs[l_idx] = initial_cost
                paths_links[l_idx] = [l_idx]
                node_preds[l_j] = l_idx
                node_costs[l_j] = initial_cost
                push(pq, (initial_cost, l_idx, l_i, l_j, l))

            # The code snippet you provided is part of the Dijkstra's algorithm implementation within the
            # `dijkstra` method of the `SPP` class. Let's break down what this part of the code is doing:
            while pq:
                current_cost, current_l_idx, current_l_i, current_l_j, current_l = pop(pq)
                if current_l_idx in visited:
                    continue
                visited.add(current_l_idx)

                if node_mode is not None:
                    kwargs = {"t": t_start + current_cost, "t_base": t_base, "in_link": current_l, "out_link": None, "graph": graph, "mode": mode}
                    current_l_j_node = graph.get_node(current_l_j)
                    available_modes: set = current_l_j_node.get_value(name=node_mode, default=set(), **kwargs)
                    if not (modes & available_modes or "all" in available_modes):
                        continue

                """
                if len(residual_targets) == 0:
                    break
                residual_targets.discard(current_l_i)
                """
                residual_targets.discard(current_l_i)
                if not residual_targets:
                    break
                for next_l in graph.get_fws(current_l_j):
                    next_l_idx = next_l["idx"]
                    if next_l_idx in visited:
                        continue

                    next_l_i, next_l_j = next_l["i"], next_l["j"]
                    # costo attuale
                    new_cost = current_cost
                    # tempo di ingresso all'arco
                    act_t = t_start + new_cost

                    # modaltà e costo d'arco 
                    kwargs = {"t": act_t, "t_base": t_base, "in_link": current_l,"out_link": next_l, "graph": graph, "mode": mode}
                    if link_mode is not None:
                        available_modes: set = next_l.get_value(name=link_mode, default=set(), **kwargs)
                        if not (modes & available_modes or "all" in available_modes):
                            continue
                    new_cost += next_l.get_value(name=link_cost, default=0, **kwargs)
                    # modaltà e costo di nodo

                    n: AbstractNode = graph.get_node(current_l_j)
                    new_cost += n.get_value(name=node_cost, default=0, **kwargs)

                    # costo manovre
                    turn: AbstractTurn = graph.get_turn(current_l_idx, next_l_idx)
                    if turn is not None:
                        if turn_mode is not None:
                            available_modes: set = turn.get_value(name=turn_mode,default={}, **kwargs)
                            if not (modes & available_modes or "all" in available_modes):
                                continue
                        new_cost += turn.get_value(name=turn_cost,default=0, **kwargs)
                    
                    if new_cost < node_costs.get(next_l_j, float("inf")):
                        node_costs[next_l_j] = new_cost
                        node_preds[next_l_j] = next_l_idx
                    if new_cost < paths_costs.get(next_l_idx, float("inf")):
                        push(pq, (new_cost, next_l_idx, next_l_i, next_l_j, next_l))
                        # assert len(paths_links[next_l_idx])==0, 'li'
                        paths_links[next_l_idx] = paths_links[current_l_idx] + [next_l_idx]
                        paths_costs[next_l_idx] = new_cost
            for target in targets:
                target_link = node_preds.get(target, None)
                if target_link is None:
                    continue
                links = paths_links.get(target_link, [])
                if len(links) > 0:
                    path = Path(source=source, target=target, t_start=t_start, links=links, costs=[paths_costs[link] for link in links], mode=mode, t_base=t_base)
                    pl.add_path(path)
        return pl

    @staticmethod
    def initialize_parallel(num_cpus: Optional[int] = None, engine: Optional[str] = None):
        n = SPP.num_cpus if num_cpus is None else num_cpus
        if engine is not None:
            SPP.parallel_engine = engine

        if n < 0:  # se <0 allora lascia libero il numero di processori indicato
            num_cpus = max(1, multiprocessing.cpu_count() + n)
        else:  # se >0 allora usa il numero di processori indicato
            num_cpus = max(1, min(multiprocessing.cpu_count(), n))
        SPP.num_cpus = num_cpus
        if num_cpus==1:
            return num_cpus
        if SPP.parallel_engine == SPP.ENGINE_RAY and num_cpus>1:
            if not SPP.ray_initialized:
                try:
                    ray.init(num_cpus=num_cpus)
                    SPP.ray_initialized = True
                except:
                    SPP.ray_initialized = False
                return num_cpus
            else:
                return ray.available_resources()["CPU"]
        elif SPP.parallel_engine == SPP.ENGINE_DASK and num_cpus>1:
            if not SPP.dask_initialized:
                SPP.dask_client = Client(n_workers=num_cpus)
                SPP.dask_initialized = True
                return num_cpus
            else:
                return len(SPP.dask_client.nthreads())
        elif SPP.parallel_engine == SPP.ENGINE_DASK_MULTITHREADING and num_cpus>1:
            if not SPP.dask_initialized:
                SPP.dask_client = Client(processes=False, threads_per_worker=num_cpus, n_workers=1)
                SPP.dask_initialized = True
                return num_cpus
            else:
                return len(SPP.dask_client.nthreads())
        elif SPP.parallel_engine == SPP.ENGINE_MULTITHREADING and num_cpus>1:
            return num_cpus
        else:
            return 1       

    @staticmethod
    def shutdown_parallel():
        if SPP.parallel_engine == SPP.ENGINE_RAY and SPP.ray_initialized:
            try:
                if SPP.ray_initialized:
                    ray.shutdown()
                SPP.ray_initialized = False
            except Exception as ex:
                Logger.error("Errore durante lo spegnimento di Ray.", exc_info=True)

        elif SPP.parallel_engine in [SPP.ENGINE_DASK, SPP.ENGINE_DASK_MULTITHREADING] and SPP.dask_initialized:
            try:
                SPP.dask_client.close()
                SPP.dask_initialized = False
            except Exception as ex:
                Logger.error("Errore durante lo spegnimento di Dask.", exc_info=True)

    @staticmethod
    def __multiple_source_single_processor(
        graph: AbstractGraph,
        sources: List[Hashable],
        targets: List[Hashable],
        t_start: Number = 0,
        t_base: Number = 0,
        **kwargs,
    ) -> Union[PathList]:
        """
        Calculate a PathForest using Dijkstra's algorithm for each source-target pair.

        :param graph: The graph to run the algorithm on
        :param sources: List of source nodes
        :param targets: List of target nodes
        :param kwargs: Additional arguments for the dijkstra method
        :return: PathForest object containing all paths from sources to targets
        """

        ret = PathList()

        for source in sources:
            paths = SPP.dijkstra(
                graph=graph,
                source=source,
                targets=targets,
                t_start=t_start,
                t_base = t_base,
                **kwargs,
            )
            ret.merge(paths)

        return ret

    @staticmethod
    def __multiple_tasks_single_processor(graph: AbstractGraph, 
                                        tasks: Iterable[dict], 
                                        **kwargs) -> PathList:
        ret = PathList()
        if len(tasks) == 0:
            return ret

        for task in tasks:
            paths = SPP.dijkstra(graph=graph, **task, **kwargs)
            ret.merge(paths)

        return ret

    @staticmethod
    def execute(fn:Callable, tasks: Iterable[dict], engine: Optional[str] = None, n_workers: Optional[int]=None, chunk_size:Optional[int]=None, **kwargs) ->Generator:
        tasks = list(tasks)
        chunk_size = int(max(1, len(tasks) // (num_cpus) ))  if chunk_size is None else chunk_size # divide sulle CPU
        pair_chunks = [tasks[i : i + chunk_size] for i in range(0, len(tasks), chunk_size)]

        engine = engine or SPP.parallel_engine
        num_cpus = SPP.initialize_parallel(n_workers, engine=engine)            
        if engine == SPP.ENGINE_RAY and num_cpus>1:    
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

        elif engine in [SPP.ENGINE_DASK, SPP.ENGINE_DASK_MULTITHREADING]:

            @dask.delayed
            def calculate(*args, **kwargs):
                return fn(*args, **kwargs)

            delayed_results = [calculate(tasks=chunk,  **kwargs) for chunk in pair_chunks]
            results = dask.compute(*delayed_results)
            for paths in results:
                yield paths

        elif engine == SPP.ENGINE_MULTITHREADING and num_cpus>1:

            def calculate(*args, **kwargs):
                return fn(*args, **kwargs)
            
            with ThreadPoolExecutor(max_workers=num_cpus) as executor:
                futures = {executor.submit(calculate, tasks=chunk, **kwargs): chunk for chunk in pair_chunks}

                # Attendi i risultati
                for future in as_completed(futures):
                    yield future.result()
        
        else:
            ret = fn(tasks=tasks, **kwargs)
            yield ret
        

    @staticmethod
    def multiple_paths(graph: AbstractGraph, tasks: Iterable[dict], engine: Optional[str] = None, n_workers: Optional[int]=None, **kwargs) -> PathList:

        ret = PathList()
        tasks = list(tasks)

        ret = PathList()
        engine = engine or SPP.parallel_engine
        num_cpus = SPP.initialize_parallel(n_workers, engine=engine)            
        if engine == SPP.ENGINE_RAY and num_cpus>1:

            chunk_size = int(max(1, len(tasks) // (num_cpus) ))  # cerca di dividere in quattro compiti per CPU
            pair_chunks = [tasks[i : i + chunk_size] for i in range(0, len(tasks), chunk_size)]
            pair_chunks_refs = [ray.put(chunk) for chunk in pair_chunks]

            @ray.remote
            def calculate_for_chunk_ray(*args, **kwargs):
                return SPP.__multiple_tasks_single_processor(*args, **kwargs)

            graph_ref = ray.put(graph)
            result_ids = [calculate_for_chunk_ray.remote(graph=graph_ref, tasks=chunk_ref, **kwargs) for chunk_ref in pair_chunks_refs]

            while result_ids:
                done_ids, result_ids = ray.wait(result_ids)
                for done_id in done_ids:
                    paths = ray.get(done_id)
                    ret.merge(paths)
        elif engine in [SPP.ENGINE_DASK, SPP.ENGINE_DASK_MULTITHREADING]:
            chunk_size = int(max(1, len(tasks) // (num_cpus)))  # cerca di dividere in quattro compiti per CPU
            pair_chunks = [tasks[i : i + chunk_size] for i in range(0, len(tasks), chunk_size)]

            @dask.delayed
            def calculate_for_chunk_dask(*args, **kwargs):
                return SPP.__multiple_tasks_single_processor(*args, **kwargs)

            delayed_results = [calculate_for_chunk_dask(graph=graph, tasks=chunk,  **kwargs) for chunk in pair_chunks]
            results = dask.compute(*delayed_results)
            for paths in results:
                ret.merge(paths)
        elif engine == SPP.ENGINE_MULTITHREADING and num_cpus>1:
            chunk_size = int(max(1, len(tasks) // (num_cpus)))  # cerca di dividere in quattro compiti per CPU
            pair_chunks = [tasks[i : i + chunk_size] for i in range(0, len(tasks), chunk_size)]

            def calculate_for_chunk_mt(*args, **kwargs):
                return SPP.__multiple_tasks_single_processor(*args, **kwargs)
            
            with ThreadPoolExecutor(max_workers=num_cpus) as executor:
                futures = {executor.submit(calculate_for_chunk_mt, 
                                           graph=graph, tasks=chunk, **kwargs): chunk for chunk in pair_chunks}

                # Attendi i risultati
                for future in as_completed(futures):
                    ret.merge(future.result())
        
        else:
            ret = SPP.__multiple_tasks_single_processor(graph=graph, tasks=tasks, **kwargs)
        return ret

    @staticmethod
    def multiple_sources_multiple_targets(
        graph: AbstractGraph,
        sources: List[Hashable],
        targets: List[Hashable],
        t_start: Number=0,
        t_base: Number = 0,
        engine: Optional[str] = None,
        n_workers: Optional[int] = None,
        **kwargs,
    ) -> PathList:
        """
        Calculate a PathForest using Dijkstra's algorithm for each source-target pair in parallel.

        :param graph: The graph to run the algorithm on
        :param sources: List of source nodes
        :param targets: List of target nodes
        :param kwargs: Additional arguments for the dijkstra method
        :return: PathForest object containing all paths from sources to targets
        """
        ret = PathList()
        engine = engine or SPP.parallel_engine
        num_cpus = SPP.initialize_parallel(n_workers, engine=engine)            
        if engine == SPP.ENGINE_RAY and num_cpus>1:
            #ray.util.register_serializer(graph, serializer=dill.dumps, deserializer=dill.loads)
            graph_ref = ray.put(graph)
            targets_ref = ray.put(targets)

            # Use ray.put to optimize the passing of large objects

            @ray.remote
            def calculate_for_chunk_ray(*args, **kwargs):
                return SPP.__multiple_source_single_processor(*args, **kwargs)

            # Put source ids into the object store
            chunk_size = int(max(1, len(sources) // (num_cpus)))

            sources_chunks = [sources[i : i + chunk_size] for i in range(0, len(sources), chunk_size)]
            sources_chunks_refs = [ray.put(chunk) for chunk in sources_chunks]

            result_ids = [
                calculate_for_chunk_ray.remote(
                    graph=graph_ref,
                    sources=chunk_ref,
                    targets=targets_ref,
                    t_start=t_start,
                    t_base=t_base,
                    **kwargs,
                )
                for chunk_ref in sources_chunks_refs
            ]

            while result_ids:
                done_ids, result_ids = ray.wait(result_ids)
                for done_id in done_ids:
                    paths = ray.get(done_id)
                    ret.merge(paths)
        elif engine in [SPP.ENGINE_DASK, SPP.ENGINE_DASK_MULTITHREADING] and num_cpus>1:
            chunk_size = int(max(1, len(sources) // num_cpus))
            sources_chunks = [sources[i : i + chunk_size] for i in range(0, len(sources), chunk_size)]

            @dask.delayed
            def calculate_for_chunk_dask(*args, **kwargs):
                return SPP.__multiple_source_single_processor(*args, **kwargs)

            delayed_results = [calculate_for_chunk_dask(graph=graph, sources=chunk, targets=targets, **kwargs) for chunk in sources_chunks]
            results = dask.compute(*delayed_results)
            for paths in results:
                ret.merge(paths)
        elif engine == SPP.ENGINE_MULTITHREADING and num_cpus>1:
            chunk_size = int(max(1, len(sources) // num_cpus))
            sources_chunks = [sources[i : i + chunk_size] for i in range(0, len(sources), chunk_size)]

            def calculate_for_chunk_mt(*args, **kwargs):
                return SPP.__multiple_source_single_processor(*args, **kwargs)
            
            with ThreadPoolExecutor(max_workers=num_cpus) as executor:
                # Sottomettiamo i lavori

                futures = {executor.submit(calculate_for_chunk_mt, 
                                           graph=graph, sources=chunk, targets=targets, **kwargs): chunk for chunk in sources_chunks}

                # Attendi i risultati
                for future in as_completed(futures):
                    ret.merge(future.result())
        
        else:
            ret = SPP.__multiple_source_single_processor(
                graph=graph,
                sources=sources,
                targets=targets,
                t_start=t_start,
                t_base=t_base,
                **kwargs,
            )
        return ret
