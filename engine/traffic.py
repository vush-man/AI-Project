"""Seedable three-level traffic model."""
from __future__ import annotations

import random

from config import TRAFFIC_INITIAL_SHARE, TRAFFIC_RUSH_HOURS, TRAFFIC_UPDATE_PERIODS
from engine.graph import Graph


class TrafficModel:
    def __init__(self, graph: Graph, rng: random.Random):
        self.graph, self.rng = graph, rng
        for edge in graph.edges.values():
            edge.traffic = self.rng.choices((0, 1, 2), weights=TRAFFIC_INITIAL_SHARE[edge.road_class])[0]

    @staticmethod
    def is_rush_hour(hour: float) -> bool:
        return any(start <= hour < end for start, end in TRAFFIC_RUSH_HOURS)

    def update(self, hour: float) -> None:
        period = TRAFFIC_UPDATE_PERIODS["rush" if self.is_rush_hour(hour) else "offpeak"]
        for edge in self.graph.edges.values():
            p_up, p_down = period[edge.road_class]
            draw = self.rng.random()
            if draw < p_up and edge.traffic < 2:
                edge.traffic += 1
            elif draw >= p_up and draw < p_up + p_down and edge.traffic > 0:
                edge.traffic -= 1

