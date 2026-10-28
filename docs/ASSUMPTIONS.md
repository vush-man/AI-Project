# Assumptions and Simplifications

This project models a fictional city and simulated response process. Its outputs are intended for an AI search and multi-agent demonstration, not real emergency dispatch.

## Graph and routes

- Roads are undirected. A road has one shared traffic level and block state in both directions.
- Coordinates and road distances are kilometres. `distance_km` may exceed the coordinate distance to model a curved road.
- Heuristics are geometric lower bounds. Time uses the maximum road speed multiplied by the emergency speed factor; other modes use straight-line kilometres.
- A supplied `h_override` is validated against the cheapest distance route. It is interpreted as the active heuristic value for that goal; use values in the appropriate mode's cost units if adding overrides.
- Search treats a short known road closure as a combined wait-and-move transition for Minimum Travel Time. The returned action trace represents this as `WAIT`, then `MOVE`.

## Traffic and incidents

- Traffic is generated with the configured seeded random generator. It is not observed traffic data.
- Rush hours are 08:00–10:30 and 17:00–20:30. The per-road transition probabilities and initial distributions are configurable in `config.py`.
- Random incidents begin after 180 simulated seconds and recur after a seeded interval between 180 and 420 seconds. Turn them off with `Simulation(auto_incidents=False)` for a manual run without generated incidents.
- An accident blocks a random adjacent road with probability 0.5, raises adjacent traffic by one level, and adds incident risk. These effects are illustrative.
- A vehicle that has entered a road completes that segment before replanning. A blocked road ahead is replanned from the next node. In Minimum Travel Time mode, a blocked road with a known clearance time of at most `MAX_WAIT_S` can be waited out.
- The police cooperation rule halves the remaining clearance time once when an assigned police unit reaches an accident scene.

## Dispatch and service

- Pending incidents are ordered by priority (3 first), then creation time and ID. If the head incident lacks all required unit types, lower-priority incidents wait.
- The CSP minimizes the maximum ETA, then total ETA, among complete assignments. ETAs use A* in the selected route mode.
- Service begins after every assigned unit reaches the scene. The configured service duration is then applied; all units return to their home station.
- The interface creates medical incidents by default after `I`; press `M`, `F`, `A`, or `C` to set kind, and `1`–`3` to set priority before clicking a node.
- Clicking `B` and then a road blocks it for `CLEAR_TIME_S`.

## UI and logs

- The Pygame window shows a map viewport and a compact status sidebar. Some historical path-log values are estimates based on the road state at the time an edge is completed.
- The viewer writes CSV logs under `logs/run_<timestamp>/`. `NotificationLog` can also be used without disk output.
