# Data and Configuration Reference

## City graph JSON

```json
{
  "nodes": [{"id": 0, "name": "City Hospital", "x": 1, "y": 7, "type": "hospital"}],
  "edges": [{"u": 0, "v": 1, "distance_km": 2, "speed_kph": 40, "hazard": 0.1}]
}
```

Node types are `junction`, `hospital`, `fire`, and `police`. Coordinates and road distances are kilometres. Roads are two-way. Optional `h_override` maps a goal ID to node heuristic values; `scripts/validate_graph.py` checks that values do not exceed the true distance cost.

At load time each road derives `euclid_km`, `curve_ratio`, `base_risk`, and `road_class`. At runtime it also holds `traffic` (0–2), `blocked`, `clear_at`, and `incident_risk`.

## Route modes

| Mode | Edge cost | Closed road behavior |
|---|---|---|
| Minimum Travel Time | Effective travel seconds | Wait only when clearance is known and within `MAX_WAIT_S` |
| Minimum Distance | Kilometres | Forbidden |
| Minimum Traffic | Kilometres × configured traffic weight | Forbidden |
| Safest Route | Kilometres × (1 + safety gain × risk) | Forbidden |
| Avoid Blocked Roads | Effective travel seconds | Forbidden |

See `config.py` for speed, traffic, wait, risk, service, fleet, and replan settings.

## Runtime files

- `logs/<run_id>/notifications.csv`: event feed history.
- `logs/<run_id>/path_log.csv`: one row for movement, wait, or reroute.

