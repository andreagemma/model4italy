from __future__ import annotations
from typing import *
from numbers import Number
from heapq import heappush as push
from heapq import heappop as pop
from ..log import Logger
from math import isnan
import itertools

from . import *
from ..utils import Parallel


class SPP:
    @staticmethod
    def dijkstra(
        graph: AbstractGraph,
        source: Union[AbstractNode, Hashable],
        targets: Optional[Union[Iterable[Hashable], Hashable]] = None,
        t_start: Number = 0,
        t_base: Number = 0,
        modes: Optional[Union[str, set[str]]] = None,
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
            # paths_links = {}
            paths_costs = {}

            node_costs = {}
            node_preds = {}

            pq = []
            # calcolo dei costi a partire dalla sorgente
            for l in graph.get_fws(source):
                kwargs = {
                    "t": t_base + t_start,
                    "in_link": None,
                    "out_link": l,
                    "graph": graph,
                    "mode": mode,
                }
                if node_mode is not None:
                    available_modes: set = source_node.get_value(
                        name=node_mode, default=set(), **kwargs
                    )
                    if not (modes & available_modes or "all" in available_modes):
                        continue

                if link_mode is not None:
                    available_modes: set = l.get_value(
                        name=link_mode, default=set(), **kwargs
                    )
                    if not (modes & available_modes or "all" in available_modes):
                        continue

                l_i, l_j, l_idx = l["i"], l["j"], l["idx"]
                initial_cost = l.get_value(name=link_cost, default=0, **kwargs)
                initial_cost += graph.get_node(l_i).get_value(
                    name=node_cost, default=0, **kwargs
                )

                paths_costs[l_idx] = initial_cost
                paths_links[l_idx] = [l_idx]
                node_preds[l_j] = l_idx
                node_costs[l_j] = initial_cost
                push(pq, (initial_cost, l_idx, l_i, l_j, l))

            # The code snippet you provided is part of the Dijkstra's algorithm implementation within the
            # `dijkstra` method of the `SPP` class. Let's break down what this part of the code is doing:
            while pq:
                current_cost, current_l_idx, current_l_i, current_l_j, current_l = pop(
                    pq
                )
                if current_l_idx in visited:
                    continue
                visited.add(current_l_idx)

                if node_mode is not None:
                    kwargs = {
                        "t": t_start + current_cost,
                        "t_base": t_base,
                        "in_link": current_l,
                        "out_link": None,
                        "graph": graph,
                        "mode": mode,
                    }
                    current_l_j_node = graph.get_node(current_l_j)
                    available_modes: set = current_l_j_node.get_value(
                        name=node_mode, default=set(), **kwargs
                    )
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
                    kwargs = {
                        "t": act_t,
                        "t_base": t_base,
                        "in_link": current_l,
                        "out_link": next_l,
                        "graph": graph,
                        "mode": mode,
                    }
                    if link_mode is not None:
                        available_modes: set = next_l.get_value(
                            name=link_mode, default=set(), **kwargs
                        )
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
                            available_modes: set = turn.get_value(
                                name=turn_mode, default={}, **kwargs
                            )
                            if not (
                                modes & available_modes or "all" in available_modes
                            ):
                                continue
                        new_cost += turn.get_value(name=turn_cost, default=0, **kwargs)

                    if new_cost < node_costs.get(next_l_j, float("inf")):
                        node_costs[next_l_j] = new_cost
                        node_preds[next_l_j] = next_l_idx
                    if new_cost < paths_costs.get(next_l_idx, float("inf")):
                        push(pq, (new_cost, next_l_idx, next_l_i, next_l_j, next_l))
                        # assert len(paths_links[next_l_idx])==0, 'li'
                        paths_links[next_l_idx] = paths_links[current_l_idx] + [
                            next_l_idx
                        ]
                        paths_costs[next_l_idx] = new_cost
            for target in targets:
                target_link = node_preds.get(target, None)
                if target_link is None:
                    continue
                links = paths_links.get(target_link, [])
                if len(links) > 0:
                    path = Path(
                        source=source,
                        target=target,
                        t_start=t_start,
                        links=links,
                        tot_cost=paths_costs[links[-1]],
                        mode=mode,
                        t_base=t_base,
                    )
                    pl.add_path(path)
        return pl

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
                t_base=t_base,
                **kwargs,
            )
            ret.merge(paths)

        return ret

    @staticmethod
    def __multiple_tasks_single_processor(
        graph: AbstractGraph, tasks: Iterable[dict], **kwargs
    ) -> PathList:
        ret = PathList()
        if len(tasks) == 0:
            return ret

        for task in tasks:
            paths = SPP.dijkstra(graph=graph, **task, **kwargs)
            ret.merge(paths)

        return ret

    @staticmethod
    def multiple_paths(
        graph: AbstractGraph,
        origins: List[Hashable],
        targets: List[Hashable],
        t_starts: Iterable[Number],
        modes: Union[str, set[str]] = None,
        n_workers: Optional[int] = None,
        t_base: Number = 0,
        **kwargs,
    ) -> PathList:

        def generate_combinations(origins, destinations, t_starts, modes):
            for o, d, t_start, mode in itertools.product(
                origins, destinations, t_starts, modes
            ):
                yield {
                    "source": o,
                    "targets": d,
                    "t_start": t_start,
                    "modes": mode,
                    "t_base": t_base,
                }

        tasks = list(generate_combinations(origins, [targets], t_starts, modes))
        ret = PathList()

        for paths in Parallel.execute(
            SPP.__multiple_tasks_single_processor,
            tasks=tasks,
            n_workers=n_workers,
            graph=graph,
            **kwargs,
        ):
            ret.merge(paths)
        return ret
