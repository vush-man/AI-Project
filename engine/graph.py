"""Headless city graph model and JSON loader."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
from pathlib import Path
from typing import Any

from config import ARTERIAL_MIN_SPEED_KPH, CURVE_RISK_DISTANCE, CURVE_RISK_GAIN


@dataclass
class Node:
    id: int
    name: str
    x: float
    y: float
    type: str = "junction"
    h_override: dict[int, float] = field(default_factory=dict)


@dataclass
class Edge:
    id: int
    u: int
    v: int
    distance_km: float
    speed_kph: float
    hazard: float
    euclid_km: float
    curve_ratio: float
    base_risk: float
    road_class: str
    traffic: int = 0
    blocked: bool = False
    clear_at: float | None = None
    incident_risk: float = 0.0


class Graph:
    """Undirected graph. Edge IDs are stable in source-file order."""

    def __init__(self, nodes: list[Node], edges: list[Edge], h_override: dict[int, dict[int, float]] | None = None):
        self.nodes = {node.id: node for node in nodes}
        self.edges = {edge.id: edge for edge in edges}
        self.h_override = h_override or {}
        self.adjacency: dict[int, list[Edge]] = {node_id: [] for node_id in self.nodes}
        for edge in edges:
            self.adjacency[edge.u].append(edge)
            self.adjacency[edge.v].append(edge)
        for adjacent in self.adjacency.values():
            adjacent.sort(key=lambda edge: (min(edge.u, edge.v), max(edge.u, edge.v), edge.id))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Graph":
        raw_nodes = data.get("nodes", [])
        node_ids = {row["id"] for row in raw_nodes}
        nodes = [Node(int(row["id"]), str(row["name"]), float(row["x"]), float(row["y"]), row.get("type", "junction")) for row in raw_nodes]
        edges: list[Edge] = []
        for edge_id, row in enumerate(data.get("edges", [])):
            u, v = int(row["u"]), int(row["v"])
            if u not in node_ids or v not in node_ids:
                # Preserve malformed references for validator diagnostics.
                continue
            euclid = math.hypot(next(n.x for n in nodes if n.id == u) - next(n.x for n in nodes if n.id == v), next(n.y for n in nodes if n.id == u) - next(n.y for n in nodes if n.id == v))
            distance = float(row["distance_km"])
            ratio = distance / euclid if euclid else math.inf
            curve_risk = min(1.0, max(0.0, (ratio - 1.0) / CURVE_RISK_DISTANCE))
            base_risk = min(1.0, max(0.0, float(row["hazard"]) + CURVE_RISK_GAIN * curve_risk))
            edges.append(Edge(edge_id, u, v, distance, float(row["speed_kph"]), float(row["hazard"]), euclid, ratio, base_risk, "arterial" if float(row["speed_kph"]) >= ARTERIAL_MIN_SPEED_KPH else "other"))
        overrides = {int(goal): {int(node): float(value) for node, value in values.items()} for goal, values in data.get("h_override", {}).items()}
        return cls(nodes, edges, overrides)

    @classmethod
    def load(cls, path: str | Path) -> "Graph":
        with Path(path).open(encoding="utf-8") as stream:
            return cls.from_dict(json.load(stream))

    def neighbors(self, node_id: int) -> list[tuple[int, Edge]]:
        if node_id not in self.nodes:
            raise KeyError(f"unknown node {node_id}")
        return [(edge.v if edge.u == node_id else edge.u, edge) for edge in self.adjacency[node_id]]

