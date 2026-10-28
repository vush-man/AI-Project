"""Validate a city graph JSON file and print a concise report."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.graph import Graph  # noqa: E402


def validate_data(data: dict) -> list[str]:
    errors: list[str] = []
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    ids = [n.get("id") for n in nodes]
    if len(ids) != len(set(ids)):
        errors.append("duplicate node IDs")
    node_by_id = {n.get("id"): n for n in nodes}
    seen: set[tuple[int, int]] = set()
    valid_edges = []
    for i, edge in enumerate(edges):
        u, v = edge.get("u"), edge.get("v")
        if u not in node_by_id or v not in node_by_id:
            errors.append(f"edge {i} refers to missing node")
            continue
        pair = (min(u, v), max(u, v))
        if u == v:
            errors.append(f"edge {i} is a self-loop")
        if pair in seen:
            errors.append(f"duplicate road {pair[0]}-{pair[1]}")
        seen.add(pair)
        try:
            distance, speed, hazard = float(edge["distance_km"]), float(edge["speed_kph"]), float(edge["hazard"])
            euclid = math.hypot(float(node_by_id[u]["x"]) - float(node_by_id[v]["x"]), float(node_by_id[u]["y"]) - float(node_by_id[v]["y"]))
            if not all(math.isfinite(x) for x in (distance, speed, hazard, euclid)):
                errors.append(f"edge {i} has non-finite values")
            if distance < euclid - 1e-9:
                errors.append(f"edge {i} distance is shorter than straight-line distance")
            if not 5 <= speed <= 100:
                errors.append(f"edge {i} speed_kph must be in [5, 100]")
            if not 0 <= hazard <= 1:
                errors.append(f"edge {i} hazard must be in [0, 1]")
            valid_edges.append(edge)
        except (KeyError, TypeError, ValueError):
            errors.append(f"edge {i} has missing or invalid numeric fields")
    if nodes:
        reached = set()
        stack = [ids[0]]
        while stack:
            current = stack.pop()
            if current in reached:
                continue
            reached.add(current)
            for edge in valid_edges:
                if edge["u"] == current:
                    stack.append(edge["v"])
                elif edge["v"] == current:
                    stack.append(edge["u"])
        if len(reached) != len(ids):
            errors.append("graph is disconnected")
    else:
        errors.append("graph has no nodes")
    for station_type in ("hospital", "fire", "police"):
        count = sum(n.get("type") == station_type for n in nodes)
        if count < 2:
            errors.append(f"at least 2 {station_type} stations are required (found {count})")
    # Validate supplied heuristic overrides against true UCS distance.
    for goal_key, values in data.get("h_override", {}).items():
        try:
            goal = int(goal_key)
            if goal not in node_by_id:
                errors.append(f"h_override goal {goal} does not exist")
                continue
            distances = {goal: 0.0}
            frontier = [(0.0, goal)]
            import heapq
            while frontier:
                cost, current = heapq.heappop(frontier)
                if cost != distances[current]:
                    continue
                for edge in valid_edges:
                    if edge["u"] == current:
                        nxt = edge["v"]
                    elif edge["v"] == current:
                        nxt = edge["u"]
                    else:
                        continue
                    candidate = cost + float(edge["distance_km"])
                    if candidate < distances.get(nxt, math.inf):
                        distances[nxt] = candidate
                        heapq.heappush(frontier, (candidate, nxt))
            for node_key, value in values.items():
                node, h = int(node_key), float(value)
                if node not in distances or not math.isfinite(h) or h < 0 or h > distances[node] + 1e-9:
                    errors.append(f"h_override[{goal}][{node}] exceeds true cheapest distance or is invalid")
        except (TypeError, ValueError):
            errors.append(f"invalid h_override for goal {goal_key}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", default="data/city_graph.json")
    args = parser.parse_args()
    path = Path(args.graph)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 1
    errors = validate_data(data)
    if errors:
        print("Graph validation failed:")
        for error in errors:
            print(f" - {error}")
        return 1
    counts = {kind: sum(n.get("type") == kind for n in data["nodes"]) for kind in ("hospital", "fire", "police")}
    print(f"Valid graph: {len(data['nodes'])} nodes, {len(data['edges'])} roads; stations: {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
