"""Incident lifecycle and shared road block state."""
from __future__ import annotations

from dataclasses import dataclass, field
import random

from config import ACCIDENT_BLOCK_PROBABILITY, ACCIDENT_INCIDENT_RISK, CLEAR_TIME_S
from engine.graph import Graph
from engine.notifications import NotificationLog


@dataclass
class Incident:
    id: str
    kind: str
    priority: int
    node_id: int
    created_t: float
    status: str = "PENDING"
    assigned: list[str] = field(default_factory=list)
    blocked_edge: int | None = None
    service_ends: float | None = None
    police_cooperation_applied: bool = False
    pending_notified: bool = False


class IncidentManager:
    def __init__(self, graph: Graph, rng: random.Random, notifications: NotificationLog):
        self.graph, self.rng, self.notifications = graph, rng, notifications
        self.incidents: list[Incident] = []
        self._next_id = 1

    def create(self, kind: str, priority: int, node_id: int, now: float, block: bool | None = None) -> Incident:
        if kind not in {"accident", "fire", "medical", "crime"}:
            raise ValueError(f"unknown incident type {kind}")
        if priority not in (1, 2, 3) or node_id not in self.graph.nodes:
            raise ValueError("priority must be 1..3 and node must exist")
        incident = Incident(f"I{self._next_id:03d}", kind, priority, node_id, now)
        self._next_id += 1
        self.incidents.append(incident)
        if kind == "accident" and (block if block is not None else self.rng.random() < ACCIDENT_BLOCK_PROBABILITY):
            adjacent = self.graph.adjacency[node_id]
            if adjacent:
                edge = self.rng.choice(adjacent)
                edge.blocked, edge.clear_at = True, now + CLEAR_TIME_S
                incident.blocked_edge = edge.id
                for near in adjacent:
                    near.traffic = min(2, near.traffic + 1)
                    near.incident_risk = ACCIDENT_INCIDENT_RISK
                self.notifications.add(now, "ROAD_BLOCKED", f"Road {edge.u}-{edge.v} blocked", priority, incident_id=incident.id)
        self.notifications.add(now, "INCIDENT_ALERT", f"{kind.title()} at {self.graph.nodes[node_id].name}", priority, incident_id=incident.id)
        return incident

    def block_edge(self, edge_id: int, now: float, clear_in: float = CLEAR_TIME_S) -> None:
        edge = self.graph.edges[edge_id]
        edge.blocked, edge.clear_at = True, now + max(0.0, clear_in)
        self.notifications.add(now, "ROAD_BLOCKED", f"Road {edge.u}-{edge.v} blocked until {edge.clear_at:.0f}s")

    def tick(self, now: float) -> None:
        for edge in self.graph.edges.values():
            if edge.blocked and edge.clear_at is not None and edge.clear_at <= now:
                edge.blocked, edge.clear_at, edge.incident_risk = False, None, 0.0
                self.notifications.add(now, "ROAD_CLEARED", f"Road {edge.u}-{edge.v} cleared")

