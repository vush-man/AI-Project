"""Vehicle agents with tick-based road movement and route replanning."""
from __future__ import annotations

from dataclasses import dataclass, field

from config import CURVE_SLOW_CAP, CURVE_SLOW_GAIN, REPLAN_GAIN, REPLAN_INTERVAL_S
from engine.costs import MODES, edge_cost, effective_speed_kph, make_heuristic_fn, travel_time_s
from engine.graph import Graph
from engine.notifications import NotificationLog
from engine.search import search


@dataclass
class Vehicle:
    id: str
    type: str
    home_node: int
    node_id: int
    priority: int = 1
    state: str = "IDLE"
    incident_id: str | None = None
    goal_node: int | None = None
    path_nodes: list[int] = field(default_factory=list)
    path_edges: list[int] = field(default_factory=list)
    path_index: int = 0
    road_progress_km: float = 0.0
    mode: str = MODES[0]
    algorithm: str = "A*"
    last_replan_t: float = 0.0
    service_started: float | None = None
    waiting_edge: int | None = None
    cost_so_far: float = 0.0

    @property
    def idle(self) -> bool:
        return self.state == "IDLE"


class Fleet:
    def __init__(self, graph: Graph, notifications: NotificationLog, replanning: bool = True):
        self.graph, self.notifications = graph, notifications
        self.replanning = replanning
        self.vehicles: list[Vehicle] = []

    def add(self, vehicle: Vehicle) -> None:
        self.vehicles.append(vehicle)

    def plan(self, vehicle: Vehicle, goal: int, mode: str, now: float) -> bool:
        result = search(self.graph, vehicle.node_id, goal, "A*", lambda e, t, v: edge_cost(mode, e, t, v), make_heuristic_fn(self.graph, goal, mode), now, vehicle)
        if not result.found:
            self.notifications.add(now, "NO_ROUTE", f"No route for {vehicle.id}", vehicle.priority, vehicle.id, vehicle.incident_id)
            vehicle.path_nodes, vehicle.path_edges = [], []
            return False
        vehicle.mode, vehicle.goal_node = mode, goal
        vehicle.path_nodes, vehicle.path_edges, vehicle.path_index = result.path_nodes, result.path_edges, 0
        vehicle.last_replan_t = now
        return True

    def _remaining_cost(self, vehicle: Vehicle, now: float) -> float:
        if not vehicle.path_edges:
            return 0.0
        return sum((edge_cost(vehicle.mode, self.graph.edges[eid], now, vehicle) or 0.0) for eid in vehicle.path_edges[vehicle.path_index:])

    def _remaining_eta(self, vehicle: Vehicle, now: float) -> float:
        eta = 0.0
        for eid in vehicle.path_edges[vehicle.path_index:]:
            edge = self.graph.edges[eid]
            if edge.blocked and edge.clear_at is not None:
                eta += max(0.0, edge.clear_at - now)
            eta += travel_time_s(edge, vehicle.priority)
        return eta

    def _replan_if_needed(self, vehicle: Vehicle, now: float) -> None:
        if (not self.replanning or vehicle.goal_node is None or vehicle.node_id == vehicle.goal_node
                or vehicle.road_progress_km > 0):
            return
        route_edges = vehicle.path_edges[vehicle.path_index:]
        blocked = any(self.graph.edges[e].blocked for e in route_edges)
        if blocked and vehicle.waiting_edge is not None and self.graph.edges[vehicle.waiting_edge].blocked:
            if now - vehicle.last_replan_t < REPLAN_INTERVAL_S:
                return
        if not blocked and now - vehicle.last_replan_t < REPLAN_INTERVAL_S:
            return
        old_cost = self._remaining_cost(vehicle, now)
        old_eta = self._remaining_eta(vehicle, now)
        old_path = list(vehicle.path_nodes[vehicle.path_index:])
        # The vehicle cannot reverse in mid-road. Replanning only happens at nodes.
        result = search(self.graph, vehicle.node_id, vehicle.goal_node, "A*", lambda e, t, v: edge_cost(vehicle.mode, e, t, v), make_heuristic_fn(self.graph, vehicle.goal_node, vehicle.mode), now, vehicle)
        vehicle.last_replan_t = now
        if not result.found:
            if blocked:
                self.notifications.add(now, "NO_ROUTE", f"No route for {vehicle.id}; retrying", vehicle.priority, vehicle.id, vehicle.incident_id)
                vehicle.waiting_edge = next((eid for eid in route_edges if self.graph.edges[eid].blocked), None)
            return
        if (blocked and result.path_edges != route_edges) or result.cost <= old_cost * (1.0 - REPLAN_GAIN):
            prior_edge = route_edges[0] if route_edges else None
            vehicle.path_nodes, vehicle.path_edges, vehicle.path_index = result.path_nodes, result.path_edges, 0
            self.notifications.add(now, "REROUTE", f"{vehicle.id}: {old_path} -> {result.path_nodes}; ETA {old_eta:.0f}s -> {result.eta_s:.0f}s, cost {old_cost:.1f} -> {result.cost:.1f}", vehicle.priority, vehicle.id, vehicle.incident_id)
            if prior_edge is not None:
                edge = self.graph.edges[prior_edge]
                self.notifications.path(t=now, vehicle_id=vehicle.id, incident_id=vehicle.incident_id, mode=vehicle.mode, algorithm=vehicle.algorithm, edge=f"{edge.u}-{edge.v}", from_node=vehicle.node_id, to_node=vehicle.node_id, traffic_level=edge.traffic, action="REROUTE", cost_so_far=vehicle.cost_so_far, eta_remaining=result.eta_s)

    def tick(self, now: float, dt: float) -> None:
        for vehicle in self.vehicles:
            if vehicle.state not in ("DISPATCHED", "RETURNING"):
                continue
            self._replan_if_needed(vehicle, now)
            budget = max(0.0, dt)
            while budget > 1e-9 and vehicle.path_index < len(vehicle.path_edges):
                edge = self.graph.edges[vehicle.path_edges[vehicle.path_index]]
                if edge.blocked and vehicle.road_progress_km <= 0:
                    if vehicle.mode == MODES[0] and edge.clear_at is not None:
                        if vehicle.waiting_edge != edge.id:
                            self.notifications.add(now, "WAIT", f"{vehicle.id} waiting for road {edge.u}-{edge.v}", vehicle.priority, vehicle.id, vehicle.incident_id)
                            self.notifications.path(t=now, vehicle_id=vehicle.id, incident_id=vehicle.incident_id, mode=vehicle.mode, algorithm=vehicle.algorithm, edge=f"{edge.u}-{edge.v}", from_node=vehicle.node_id, to_node=vehicle.node_id, traffic_level=edge.traffic, action="WAIT", cost_so_far=vehicle.cost_so_far, eta_remaining=self._remaining_eta(vehicle, now))
                        vehicle.waiting_edge = edge.id
                    break
                vehicle.waiting_edge = None
                # Integrate a segment using the same speed model used by route costs.
                speed = effective_speed_kph(edge, vehicle.priority)
                speed /= 1.0 + CURVE_SLOW_GAIN * min(max(edge.curve_ratio - 1.0, 0.0), CURVE_SLOW_CAP)
                available = speed * budget / 3600.0
                remaining_dist = edge.distance_km - vehicle.road_progress_km
                if available + 1e-12 < remaining_dist:
                    vehicle.road_progress_km += available
                    budget = 0
                else:
                    spent = remaining_dist / speed * 3600.0
                    budget -= spent
                    from_node = vehicle.node_id
                    vehicle.cost_so_far += float(edge_cost(vehicle.mode, edge, now, vehicle) or 0.0)
                    vehicle.node_id = edge.v if edge.u == from_node else edge.u
                    vehicle.path_index += 1
                    vehicle.road_progress_km = 0.0
                    self.notifications.path(t=now + dt - budget, vehicle_id=vehicle.id, incident_id=vehicle.incident_id, mode=vehicle.mode, algorithm=vehicle.algorithm, edge=f"{edge.u}-{edge.v}", from_node=from_node, to_node=vehicle.node_id, traffic_level=edge.traffic, action="MOVE", cost_so_far=vehicle.cost_so_far, eta_remaining=self._remaining_eta(vehicle, now))
            if vehicle.goal_node is not None and vehicle.node_id == vehicle.goal_node and vehicle.path_index >= len(vehicle.path_edges):
                if vehicle.state == "DISPATCHED":
                    vehicle.state = "ON_SCENE"
                    self.notifications.add(now, "ARRIVAL", f"{vehicle.id} arrived at scene", vehicle.priority, vehicle.id, vehicle.incident_id)
                elif vehicle.state == "RETURNING":
                    vehicle.state, vehicle.incident_id, vehicle.goal_node = "IDLE", None, None
                    vehicle.path_nodes, vehicle.path_edges = [], []
                    vehicle.cost_so_far = 0.0
                    self.notifications.add(now, "ARRIVAL", f"{vehicle.id} returned to base", vehicle.priority, vehicle.id)

    def return_home(self, vehicle: Vehicle, mode: str, now: float) -> None:
        vehicle.state, vehicle.goal_node = "RETURNING", vehicle.home_node
        self.plan(vehicle, vehicle.home_node, mode, now)

