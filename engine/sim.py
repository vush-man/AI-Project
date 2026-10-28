"""Deterministic tick loop coordinating traffic, incidents, dispatch and units."""
from __future__ import annotations

import random

from config import (AUTO_INCIDENT_INTERVAL_S, AUTO_INCIDENT_PRIORITY_WEIGHTS,
                    FLEET, REPLAN_INTERVAL_S, SEED, SERVICE_TIME_S,
                    START_TIME, TRAFFIC_UPDATE_S)
from engine.agents import Fleet, Vehicle
from engine.dispatch import Dispatcher
from engine.incidents import IncidentManager
from engine.notifications import NotificationLog
from engine.traffic import TrafficModel


def parse_hour(value: str) -> float:
    hour, minute = map(int, value.split(":"))
    return hour + minute / 60


class Simulation:
    def __init__(self, graph, seed: int = SEED, mode: str = "Minimum Travel Time", log_dir=None, auto_incidents: bool = True, replanning: bool = True):
        self.graph, self.rng, self.mode = graph, random.Random(seed), mode
        self.now = 0.0
        self.hour = parse_hour(START_TIME)
        self.notifications = NotificationLog(log_dir)
        self.traffic = TrafficModel(graph, self.rng)
        self.incidents = IncidentManager(graph, self.rng, self.notifications)
        self.fleet = Fleet(graph, self.notifications, replanning=replanning)
        for kind, stations in FLEET.items():
            for station, count in stations.items():
                for index in range(count):
                    self.fleet.add(Vehicle(f"{kind[:1].upper()}{station}-{index + 1}", kind, station, station))
        self.dispatcher = Dispatcher(self.fleet, self.notifications)
        self.auto_incidents = auto_incidents
        self._traffic_elapsed = 0.0
        self._next_auto_incident = AUTO_INCIDENT_INTERVAL_S[0]

    def set_mode(self, mode: str) -> None:
        from engine.costs import MODES
        if mode not in MODES:
            raise ValueError(f"unknown route mode: {mode}")
        self.mode = mode
        for vehicle in self.fleet.vehicles:
            if vehicle.state not in ("DISPATCHED", "RETURNING") or vehicle.goal_node is None:
                continue
            vehicle.mode = mode
            if vehicle.road_progress_km <= 0:
                self.fleet.plan(vehicle, vehicle.goal_node, mode, self.now)
            else:
                vehicle.last_replan_t = self.now - REPLAN_INTERVAL_S

    def add_incident(self, kind: str, priority: int, node_id: int):
        return self.incidents.create(kind, priority, node_id, self.now)

    def step(self, dt: float = 1.0) -> None:
        if dt < 0:
            raise ValueError("dt must be non-negative")
        self.now += dt
        self.hour = (self.hour + dt / 3600.0) % 24
        self._traffic_elapsed += dt
        while self._traffic_elapsed >= TRAFFIC_UPDATE_S:
            self._traffic_elapsed -= TRAFFIC_UPDATE_S
            self.traffic.update(self.hour)
        self.incidents.tick(self.now)
        if self.auto_incidents and self.now >= self._next_auto_incident:
            kinds = ("medical", "fire", "accident", "crime")
            self.add_incident(self.rng.choice(kinds), self.rng.choices((1, 2, 3), weights=AUTO_INCIDENT_PRIORITY_WEIGHTS)[0], self.rng.choice(sorted(self.graph.nodes)))
            self._next_auto_incident = self.now + self.rng.uniform(*AUTO_INCIDENT_INTERVAL_S)
        self.dispatcher.tick(self.incidents.incidents, self.mode, self.now)
        self.fleet.tick(self.now, dt)
        for incident in self.incidents.incidents:
            if incident.status != "ASSIGNED":
                continue
            units = [next((v for v in self.fleet.vehicles if v.id == vid), None) for vid in incident.assigned]
            units = [v for v in units if v is not None]
            if units and all(v.state == "ON_SCENE" for v in units) and incident.service_ends is None:
                incident.service_ends = self.now + SERVICE_TIME_S[incident.priority]
            if incident.service_ends is not None and self.now >= incident.service_ends:
                incident.status = "RESOLVED"
                if incident.blocked_edge is not None:
                    edge = self.graph.edges[incident.blocked_edge]
                    edge.blocked, edge.clear_at, edge.incident_risk = False, None, 0.0
                    self.notifications.add(self.now, "ROAD_CLEARED", f"Road {edge.u}-{edge.v} cleared after response", incident.priority, incident_id=incident.id)
                    # Accident risk applies to roads at the scene and clears with service.
                    for adjacent in self.graph.adjacency[incident.node_id]:
                        adjacent.incident_risk = 0.0
                for vehicle in units:
                    self.fleet.return_home(vehicle, self.mode, self.now)
                self.notifications.add(self.now, "RESOLVED", f"{incident.id} resolved", incident.priority, incident_id=incident.id)
        # Police arrival at a blocked accident cuts remaining clearance time in half.
        for incident in self.incidents.incidents:
            if incident.kind == "accident" and incident.status == "ASSIGNED" and incident.blocked_edge is not None:
                police_arrived = any(v.type == "police" and v.state == "ON_SCENE" for v in self.fleet.vehicles if v.incident_id == incident.id)
                edge = self.graph.edges[incident.blocked_edge]
                if police_arrived and not incident.police_cooperation_applied and edge.blocked and edge.clear_at is not None and edge.clear_at > self.now:
                    edge.clear_at = self.now + (edge.clear_at - self.now) / 2
                    incident.police_cooperation_applied = True
        self.notifications.flush()

