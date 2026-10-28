"""Mode-specific road costs and admissible geometric heuristics."""
from __future__ import annotations

import math
from typing import Callable

from config import (CURVE_SLOW_CAP, CURVE_SLOW_GAIN, EMERGENCY_SPEED_FACTOR,
                    MAX_WAIT_S, PRIORITY_RELIEF, SAFETY_GAIN,
                    TRAFFIC_MULT, TRAFFIC_RISK_PER_LEVEL, TRAFFIC_WEIGHT)
from engine.graph import Edge, Graph

MODES = ("Minimum Travel Time", "Minimum Distance", "Minimum Traffic", "Safest Route", "Avoid Blocked Roads")


def risk(edge: Edge) -> float:
    return min(1.0, max(0.0, edge.base_risk + TRAFFIC_RISK_PER_LEVEL * edge.traffic + edge.incident_risk))


def travel_time_s(edge: Edge, priority: int = 1) -> float:
    priority = min(3, max(1, priority))
    relief = PRIORITY_RELIEF[priority]
    eff_mult = 1.0 + (TRAFFIC_MULT[edge.traffic] - 1.0) * (1.0 - relief)
    effective_speed = effective_speed_kph(edge, priority)
    curve_slow = 1.0 + CURVE_SLOW_GAIN * min(max(edge.curve_ratio - 1.0, 0.0), CURVE_SLOW_CAP)
    return edge.distance_km / effective_speed * 3600.0 * curve_slow


def effective_speed_kph(edge: Edge, priority: int = 1) -> float:
    priority = min(3, max(1, priority))
    relief = PRIORITY_RELIEF[priority]
    eff_mult = 1.0 + (TRAFFIC_MULT[edge.traffic] - 1.0) * (1.0 - relief)
    return edge.speed_kph * EMERGENCY_SPEED_FACTOR / eff_mult


def edge_cost(mode: str, edge: Edge, now: float = 0.0, vehicle=None) -> float | None:
    priority = getattr(vehicle, "priority", 1)
    if edge.blocked:
        wait = edge.clear_at - now if edge.clear_at is not None else None
        if mode == "Minimum Travel Time" and wait is not None and 0 <= wait <= MAX_WAIT_S:
            return wait + travel_time_s(edge, priority)
        return None
    if mode in ("Minimum Travel Time", "Avoid Blocked Roads"):
        return travel_time_s(edge, priority)
    if mode == "Minimum Distance":
        return edge.distance_km
    if mode == "Minimum Traffic":
        return edge.distance_km * TRAFFIC_WEIGHT[edge.traffic]
    if mode == "Safest Route":
        return edge.distance_km * (1.0 + SAFETY_GAIN * risk(edge))
    raise ValueError(f"unknown route mode: {mode}")


def heuristic(graph: Graph, node_id: int, goal_id: int, mode: str) -> float:
    override = graph.h_override.get(goal_id, {})
    if node_id in override:
        return override[node_id]
    node, goal = graph.nodes[node_id], graph.nodes[goal_id]
    straight = math.hypot(node.x - goal.x, node.y - goal.y)
    if mode == "Minimum Travel Time":
        vmax = max(edge.speed_kph * EMERGENCY_SPEED_FACTOR for edge in graph.edges.values())
        return straight / vmax * 3600.0
    return straight


def make_cost_fn(mode: str) -> Callable:
    return lambda edge, now=0, vehicle=None: edge_cost(mode, edge, now, vehicle)


def make_heuristic_fn(graph: Graph, goal_id: int, mode: str) -> Callable:
    return lambda node_id: heuristic(graph, node_id, goal_id, mode)
