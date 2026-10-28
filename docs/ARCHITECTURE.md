# Architecture Reference

## Boundaries

- `engine/` is headless and imports no Pygame code.
- `ui/pygame_app.py` owns drawing and input, and calls the engine through `Simulation`, `Graph`, and search APIs.
- `config.py` contains tunable model, fleet, display, and timing values.
- `data/city_graph.json` is the hand-authored two-way graph. Edge IDs follow source-file order.

## Engine modules

| Module | Main API | Responsibility |
|---|---|---|
| `engine.graph` | `Graph.load`, `Graph.neighbors` | Nodes, roads, adjacency, derived curve/risk fields |
| `engine.costs` | `edge_cost`, `heuristic`, `make_cost_fn` | Five route cost modes and geometric lower bounds |
| `engine.search` | `search` | BFS, DFS, UCS, Greedy Best-First, A*, trace and metrics |
| `engine.traffic` | `TrafficModel` | Seeded initial road levels and hourly-period updates |
| `engine.incidents` | `IncidentManager` | Incident lifecycle, road blocking, clearance |
| `engine.agents` | `Vehicle`, `Fleet` | Movement, arrival, waiting, return routes, replanning |
| `engine.dispatch` | `Dispatcher`, `requirements` | Priority ordering, rule-based unit needs, MRV backtracking CSP |
| `engine.notifications` | `NotificationLog` | In-memory event feed and CSV output |
| `engine.sim` | `Simulation.step` | Seeded clock and coordinated tick lifecycle |

## Tick order

Each `Simulation.step(dt)` advances simulation time, applies all due traffic updates, clears expired roads, generates due random incidents, dispatches the priority-queue head, moves vehicles, starts or completes on-scene service, applies the police clearance reduction, and flushes configured logs.

Vehicle movement integrates effective speed over road distance. When a vehicle is between nodes, it completes its current segment before replanning. At a node, a blocked route may be recomputed immediately; otherwise periodic replanning occurs when a new route improves estimated remaining cost by at least `REPLAN_GAIN`.

## Search result

`search(graph, start, goal, algorithm, cost_fn, heuristic_fn, now, vehicle)` returns a `SearchResult` containing:

- `found`, ordered `path_nodes`, `path_edges`, and `path_actions` (`WAIT`/`MOVE` where applicable)
- mode cost, ETA estimate, physical distance, expanded-node and frontier counts, runtime
- `steps`, with the expanded node, `g`, `h`, `f`, open-set snapshot, and closed set

The generic search module accepts cost and heuristic functions. The cost model decides whether blocked roads are forbidden or may be waited out.
`cost` uses the selected objective; `eta_s` always estimates travel time in seconds, even for distance, traffic, and risk modes.

## Data and logs

Every edge stores source/destination IDs, distance, speed, hazard, derived Euclidean distance, curve ratio, base risk, and road class. Runtime fields add traffic level, blocked state, clear time, and incident risk.

Notification CSV columns are `t,type,priority,vehicle_id,incident_id,message`. Path CSV columns are defined in `engine.notifications` and record movement, wait, and reroute actions.

