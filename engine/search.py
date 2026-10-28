"""Deterministic graph search: BFS, DFS, UCS, Greedy Best-First and A*."""
from __future__ import annotations

from dataclasses import dataclass, field
import heapq
import time
from collections import deque
from typing import Callable

from engine.graph import Edge, Graph

ALGORITHMS = ("BFS", "DFS", "UCS", "Greedy", "A*")


@dataclass
class Step:
    node: int
    g: float
    h: float
    f: float
    open_list: list[tuple[int, float, float, float]]
    closed: list[int]


@dataclass
class SearchResult:
    found: bool
    path_nodes: list[int] = field(default_factory=list)
    path_edges: list[int] = field(default_factory=list)
    cost: float = float("inf")
    eta_s: float = float("inf")
    distance_km: float = 0.0
    nodes_expanded: int = 0
    max_frontier: int = 0
    runtime_ms: float = 0.0
    steps: list[Step] = field(default_factory=list)
    path_actions: list[str] = field(default_factory=list)


def search(graph: Graph, start: int, goal: int, algorithm: str = "A*",
           cost_fn: Callable | None = None, heuristic_fn: Callable | None = None,
           now: float = 0.0, vehicle=None) -> SearchResult:
    if start not in graph.nodes or goal not in graph.nodes:
        raise KeyError("start and goal must exist in graph")
    if algorithm not in ALGORITHMS:
        raise ValueError(f"unknown algorithm: {algorithm}")
    cost_fn = cost_fn or (lambda edge, _now, _vehicle: 1.0)
    heuristic_fn = heuristic_fn or (lambda _node: 0.0)
    began = time.perf_counter()
    g_score = {start: 0.0}
    parents: dict[int, tuple[int, int]] = {}
    closed: set[int] = set()
    steps: list[Step] = []
    serial = 0

    def priority(node: int, g: float) -> tuple[float, int, int]:
        h = heuristic_fn(node)
        if algorithm in ("BFS", "DFS"):
            return (0.0, node, serial)
        if algorithm == "UCS":
            return (g, node, serial)
        if algorithm == "Greedy":
            return (h, node, serial)
        return (g + h, node, serial)

    # Heap is used for informed and cost-based searches; FIFO/LIFO retain their syllabus ordering.
    frontier = deque([start])
    heap = [(priority(start, 0.0), start)]
    expanded = 0
    max_frontier = 1
    found = False
    while (frontier if algorithm == "BFS" else frontier if algorithm == "DFS" else heap):
        if algorithm == "BFS":
            current = frontier.popleft()
        elif algorithm == "DFS":
            current = frontier.pop()
        else:
            _, current = heapq.heappop(heap)
        if current in closed:
            continue
        closed.add(current)
        expanded += 1
        h = heuristic_fn(current)
        if current == goal:
            snapshot = ([(n, g_score.get(n, 0), heuristic_fn(n), g_score.get(n, 0) + heuristic_fn(n)) for n in frontier]
                        if algorithm in ("BFS", "DFS") else
                        [(n, g_score.get(n, 0), heuristic_fn(n), g_score.get(n, 0) + heuristic_fn(n)) for _, n in sorted(heap)])
            steps.append(Step(current, g_score[current], h, g_score[current] + h, snapshot, sorted(closed)))
            found = True
            break
        neighbors = graph.neighbors(current)
        if algorithm == "DFS":
            neighbors = list(reversed(neighbors))
        for neighbor, edge in neighbors:
            edge_cost = cost_fn(edge, now, vehicle)
            if edge_cost is None:
                continue
            candidate = g_score[current] + float(edge_cost)
            if algorithm in ("BFS", "DFS"):
                if neighbor in closed or neighbor in g_score:
                    continue
                g_score[neighbor] = candidate
                parents[neighbor] = (current, edge.id)
                frontier.append(neighbor)
                serial += 1
            elif candidate + 1e-12 < g_score.get(neighbor, float("inf")):
                g_score[neighbor] = candidate
                parents[neighbor] = (current, edge.id)
                if neighbor in closed:
                    closed.remove(neighbor)
                heapq.heappush(heap, (priority(neighbor, candidate), neighbor))
                serial += 1
        snapshot = ([(n, g_score.get(n, 0), heuristic_fn(n), g_score.get(n, 0) + heuristic_fn(n)) for n in frontier]
                    if algorithm in ("BFS", "DFS") else
                    [(n, g_score.get(n, 0), heuristic_fn(n), g_score.get(n, 0) + heuristic_fn(n)) for _, n in sorted(heap)])
        steps.append(Step(current, g_score[current], h, g_score[current] + h, snapshot, sorted(closed)))
        max_frontier = max(max_frontier, len(frontier) if algorithm in ("BFS", "DFS") else len(heap))
    elapsed = (time.perf_counter() - began) * 1000.0
    if not found:
        return SearchResult(False, nodes_expanded=expanded, max_frontier=max_frontier, runtime_ms=elapsed, steps=steps)
    nodes = [goal]
    edge_ids = []
    while nodes[-1] != start:
        previous, edge_id = parents[nodes[-1]]
        edge_ids.append(edge_id)
        nodes.append(previous)
    nodes.reverse()
    edge_ids.reverse()
    distance = sum(graph.edges[eid].distance_km for eid in edge_ids)
    cost = g_score[goal]
    from engine.costs import travel_time_s
    priority_level = getattr(vehicle, "priority", 1)
    eta = sum((max(0.0, graph.edges[eid].clear_at - now) if graph.edges[eid].blocked and graph.edges[eid].clear_at is not None else 0.0)
              + travel_time_s(graph.edges[eid], priority_level) for eid in edge_ids)
    actions = [action for eid in edge_ids for action in ((["WAIT", "MOVE"] if graph.edges[eid].blocked else ["MOVE"]))]
    return SearchResult(True, nodes, edge_ids, cost, eta, distance, expanded, max_frontier, elapsed, steps, actions)
