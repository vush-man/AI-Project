"""Rule-based incident dispatch and small CSP batch assignment."""
from __future__ import annotations

from collections import Counter

from engine.agents import Fleet
from engine.costs import edge_cost, make_heuristic_fn
from engine.incidents import Incident
from engine.notifications import NotificationLog
from engine.search import search

REQUIREMENTS = {
    "medical": {1: {"ambulance": 1}, 2: {"ambulance": 1}, 3: {"ambulance": 2}},
    "fire": {1: {"fire": 1, "ambulance": 1}, 2: {"fire": 1, "ambulance": 1}, 3: {"fire": 2, "ambulance": 1}},
    "accident": {1: {"police": 1, "ambulance": 1}, 2: {"police": 1, "ambulance": 1}, 3: {"police": 1, "ambulance": 1, "fire": 1}},
    "crime": {1: {"police": 1}, 2: {"police": 1}, 3: {"police": 2}},
}


def requirements(kind: str, priority: int) -> Counter:
    return Counter(REQUIREMENTS[kind][priority])


class Dispatcher:
    def __init__(self, fleet: Fleet, notifications: NotificationLog):
        self.fleet, self.notifications = fleet, notifications

    def _eta(self, vehicle, incident: Incident, mode: str, now: float) -> float:
        result = search(self.fleet.graph, vehicle.node_id, incident.node_id, "A*", lambda e, t, v: edge_cost(mode, e, t, v), make_heuristic_fn(self.fleet.graph, incident.node_id, mode), now, vehicle)
        return result.eta_s if result.found else float("inf")

    def choose_batch(self, incident: Incident, mode: str, now: float):
        needs = requirements(incident.kind, incident.priority)
        slots = [kind for kind, count in needs.items() for _ in range(count)]
        idle = [v for v in self.fleet.vehicles if v.idle]
        domains = {i: [v for v in idle if v.type == kind] for i, kind in enumerate(slots)}
        eta_cache = {(slot, v.id): self._eta(v, incident, mode, now) for slot, candidates in domains.items() for v in candidates}
        best, best_score = None, (float("inf"), float("inf"))
        def backtrack(remaining, chosen, used):
            nonlocal best, best_score
            if not remaining:
                etas = [eta_cache[(slot, v.id)] for slot, v in chosen.items()]
                score = (max(etas, default=0), sum(etas))
                if score < best_score:
                    best_score, best = score, dict(chosen)
                return
            slot = min(remaining, key=lambda i: sum(v.id not in used for v in domains[i]))
            for vehicle in sorted(domains[slot], key=lambda v: v.id):
                if vehicle.id in used:
                    continue
                if eta_cache[(slot, vehicle.id)] == float("inf"):
                    continue
                chosen[slot] = vehicle
                backtrack([i for i in remaining if i != slot], chosen, used | {vehicle.id})
                chosen.pop(slot)
        backtrack(list(range(len(slots))), {}, set())
        if best is None:
            return None
        return [(slots[index], vehicle, eta_cache[(index, vehicle.id)]) for index, vehicle in best.items()]

    def tick(self, incidents: list[Incident], mode: str, now: float) -> None:
        pending = sorted((i for i in incidents if i.status == "PENDING"), key=lambda i: (-i.priority, i.created_t, i.id))
        for incident in pending:
            batch = self.choose_batch(incident, mode, now)
            if batch is None:
                if not incident.pending_notified:
                    self.notifications.add(now, "PENDING", f"Waiting for available units: {incident.id}", incident.priority, incident_id=incident.id)
                    incident.pending_notified = True
                break
            units = []
            for _slot, vehicle, eta in batch:
                vehicle.state, vehicle.incident_id, vehicle.priority = "DISPATCHED", incident.id, incident.priority
                vehicle.algorithm = "A*"
                self.fleet.plan(vehicle, incident.node_id, mode, now)
                incident.assigned.append(vehicle.id)
                units.append(f"{vehicle.id} ETA {eta:.0f}s")
            incident.status = "ASSIGNED"
            self.notifications.add(now, "DISPATCH", f"{incident.id}: " + ", ".join(units), incident.priority, incident_id=incident.id)

