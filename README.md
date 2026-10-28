# Emergency Response & Rescue Agent (Simple Graph Version)

An AI agent system that dispatches ambulances, fire trucks and police cars to incidents on a **hand-made city graph**: nodes are places, edges are roads with path costs, and every node has a heuristic value toward the goal. Traffic, roadblocks and accidents change while vehicles are moving.

This is the **lean version**: every required feature of the project, with no real map and no complex extras. `README_FULL.md` holds the older, detailed real-map design (Dehradun, OpenStreetMap) for optional extensions.

---

## 0. Instructions for the implementing agent

1. Build **phase by phase** (Section 16). Do not start a phase until the previous one's acceptance checks pass.
2. **Python only.** UI is **Pygame**. No web frameworks, databases, JavaScript or map libraries.
3. **Only syllabus algorithms:** BFS, DFS, UCS, Greedy Best-First, A*, a CSP solver, and rule-based reasoning. No Hungarian algorithm, D* Lite, ML or similar.
4. `engine/` is **headless** (no pygame imports). `ui/` only draws and handles input.
5. All randomness uses one seeded generator (`random.Random(SEED)`), so runs are reproducible.
6. All tunable numbers live in `config.py`.
7. If something is ambiguous, pick the simplest option and note it in `docs/ASSUMPTIONS.md`.

---

## 1. What gets built

| # | Required task | File |
|---|---|---|
| 1 | City as a graph | `data/city_graph.json`, `engine/graph.py` |
| 2 | States and actions (incl. **Wait**) | `engine/search.py` (Section 7) |
| 3 | Multiple search algorithms | `engine/search.py` |
| 4 | Dynamic traffic (Low / Medium / High) | `engine/traffic.py`, `engine/incidents.py` |
| 5 | Dynamic path replanning | `engine/agents.py` |
| 6 | Emergency priority system | `engine/dispatch.py` |
| 7 | Multi-agent system | `engine/agents.py`, `engine/dispatch.py` |
| 8 | Display AI search information | `ui/pygame_app.py` |
| 9 | Environment classification | Section 14 |

**User-selectable modes:** Minimum Travel Time, Minimum Distance, Minimum Traffic, Safest Route, Avoid Blocked Roads.

**Also included:** path logs, a notification system (incident alerts, dispatches, reroutes), dispatch by priority, and vehicles working as a coordinated batch.

### What changed from the previous simple version

| Removed | Replaced by |
|---|---|
| OpenStreetMap download, `build_map.py`, `seed_maxspeed.py` | A hand-written graph file plus `scripts/validate_graph.py` |
| Real road geometry and projection | Node coordinates in km; a road's `distance` may exceed the straight line to represent **curved roads** |
| Heuristic from real coordinates only | Each node shows its heuristic value `h(n)` toward the current goal |
| `osmnx` / conda | Plain `pip install` |

---

## 2. Syllabus mapping

| Unit | Used for |
|---|---|
| I | Agents (vehicles, dispatcher), environment classification |
| II | BFS, DFS, UCS, Greedy, A*; CSP for choosing the best vehicle batch |
| III / IV | Rule-based knowledge: which units an incident needs |
| IV | Simple probabilistic traffic changes |
| V | Multi-agent planning and cooperation |

---

## 3. Tech stack and setup

| Concern | Choice |
|---|---|
| Language | Python 3.11 |
| UI | `pygame-ce` |
| Runtime dependencies | `pygame-ce` |

```bash
conda run -n rescue python ui/pygame_app.py
```

Under WSL2, Pygame needs WSLg to open a window. If it fails, run the UI from native Windows.

---

## 4. Repository layout

```
rescue-agent/
├── README.md
├── config.py
├── scripts/
│   ├── validate_graph.py    # checks the graph file (Section 6)
├── data/
│   └── city_graph.json      # nodes + edges (Section 5)
├── engine/                  # HEADLESS
│   ├── graph.py             # Node, Edge, Graph
│   ├── search.py            # states, actions, 5 algorithms, SearchResult
│   ├── costs.py             # 5 mode cost functions + heuristics
│   ├── traffic.py           # Low/Med/High model
│   ├── incidents.py         # incidents and roadblocks
│   ├── dispatch.py          # rules, priority queue, CSP
│   ├── agents.py            # Vehicle, mission states, replanning
│   ├── notifications.py     # notification list + CSV logging
│   └── sim.py               # clock and tick loop
├── ui/pygame_app.py
└── docs/ASSUMPTIONS.md
```

---

## 5. The city graph

### 5.1 Format (`data/city_graph.json`)

```json
{
  "nodes": [ {"id": 0, "name": "City Hospital", "x": 1.0, "y": 7.0, "type": "hospital"} ],
  "edges": [ {"u": 0, "v": 1, "distance_km": 2.0, "speed_kph": 40, "hazard": 0.1} ]
}
```

- `type` is `junction`, `hospital`, `fire` or `police`. Stations are nodes.
- Coordinates `x`, `y` are in **km** and are used for drawing and for the heuristic.
- Roads are **two-way**; both directions share one traffic level and one blocked state.
- Optional: `"h_override": {"<goal_id>": {"<node_id>": value}}` if you want hand-typed heuristic values for specific goals. If present they are used for those goals and must be admissible (the validator checks this). Otherwise `h` is computed (Section 7.3).

**Derived per edge (computed at load):**
- `euclid_km` = straight-line distance between the two nodes.
- `curve_ratio = distance_km / euclid_km` (always ≥ 1). A ratio above 1 means the road curves.
- `base_risk = clamp(hazard + 0.4 × curve_risk, 0, 1)` where `curve_risk = clamp((curve_ratio − 1) / 0.5, 0, 1)`.
- `road_class`: `arterial` if `speed_kph >= 50`, else `other`.

**Runtime state per edge (memory only):** `traffic` (0 LOW, 1 MED, 2 HIGH), `blocked`, `clear_at` (sim-time or `None`), `incident_risk`.

### 5.2 Sample city (20 nodes, 37 roads)

Create `data/city_graph.json` from this. The layout is a 5 × 4 grid at x = 1, 3, 5, 7, 9 km and y = 7, 5, 3, 1 km.

| id | name | x | y | type | | id | name | x | y | type |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | City Hospital | 1 | 7 | hospital | | 10 | West Fire Station | 1 | 3 | fire |
| 1 | Market | 3 | 7 | junction | | 11 | Riverside | 3 | 3 | junction |
| 2 | Old Town | 5 | 7 | junction | | 12 | Central Police HQ | 5 | 3 | police |
| 3 | Station Road | 7 | 7 | junction | | 13 | Tech Park | 7 | 3 | junction |
| 4 | North Police Post | 9 | 7 | police | | 14 | East Gate | 9 | 3 | junction |
| 5 | School Zone | 1 | 5 | junction | | 15 | Industrial Area | 1 | 1 | junction |
| 6 | Park Junction | 3 | 5 | junction | | 16 | Bus Terminal | 3 | 1 | junction |
| 7 | Central Square | 5 | 5 | junction | | 17 | South Fire Station | 5 | 1 | fire |
| 8 | Mall Road | 7 | 5 | junction | | 18 | Highway Exit | 7 | 1 | junction |
| 9 | East Hospital | 9 | 5 | hospital | | 19 | Airport Road | 9 | 1 | junction |

Edges as `u v distance_km speed_kph hazard`:

```
# horizontal
0 1 2.0 40 0.1     1 2 2.2 40 0.1     2 3 2.0 50 0.1     3 4 2.6 40 0.2
5 6 2.0 40 0.1     6 7 2.0 50 0.1     7 8 2.0 50 0.1     8 9 2.4 40 0.2
10 11 2.3 30 0.3   11 12 2.0 40 0.1   12 13 2.0 50 0.1   13 14 2.0 40 0.1
15 16 2.0 30 0.2   16 17 2.5 30 0.3   17 18 2.0 40 0.1   18 19 2.2 40 0.2
# vertical
0 5 2.0 40 0.1     5 10 2.4 30 0.3    10 15 2.0 30 0.2
1 6 2.0 50 0.1     6 11 2.0 40 0.1    11 16 2.6 30 0.3
2 7 2.0 50 0.1     7 12 2.0 50 0.1    12 17 2.0 40 0.1
3 8 2.0 40 0.1     8 13 2.0 50 0.1    13 18 2.4 30 0.3
4 9 2.0 40 0.2     9 14 2.0 40 0.1    14 19 2.0 30 0.2
# diagonal shortcuts (shorter in hops, but curvy and slower or riskier)
6 12 3.2 30 0.4    8 12 3.0 40 0.2    1 7 3.1 40 0.2
3 7 2.9 50 0.1     8 14 3.3 30 0.3    11 17 3.4 30 0.4
```

Stations: hospitals 0 and 9, fire stations 10 and 17, police 4 and 12. Starting fleet (`config.py`): ambulances 2 at node 0 and 1 at node 9; fire trucks 1 at node 10 and 1 at node 17; police 1 at node 4 and 2 at node 12.

The central column (nodes 2, 7, 12, 17) is fast; the diagonals are shortcuts that are slower or riskier. That gives the five modes different winning routes.

---

## 6. `scripts/validate_graph.py`

```bash
python scripts/validate_graph.py --graph data/city_graph.json
```

Checks and prints a report:
1. Every edge refers to existing nodes; no duplicate roads.
2. The graph is **connected**.
3. `distance_km >= euclid_km` for every edge (otherwise the straight-line heuristic would not be admissible).
4. `speed_kph` in [5, 100] and `hazard` in [0, 1].
5. At least 2 hospitals, 2 fire stations and 2 police stations.
6. If `h_override` exists, every value is ≤ the true cheapest distance (computed with UCS).

Print counts of nodes, edges and each station type. *Acceptance:* the sample graph passes; tests cover a deliberately broken graph for each check.

---

## 7. Search (`engine/search.py`)

### 7.1 States and actions

- **State:** the vehicle's current node.
- **Actions:** `MOVE(edge)` to an adjacent node, and `WAIT` at the node.
- **Transition model:** `MOVE` goes to the road's other end at the cost given by the active mode (Section 8).
- **Goal test:** node equals the destination.
- **Wait:** a currently blocked road with a known `clear_at` can still be taken in **Min Time** mode if the wait is at most `MAX_WAIT_S`. The road's cost then includes `clear_at − now` as a wait penalty, so the planner chooses wait vs detour by comparing costs. A vehicle following such a plan performs the `WAIT` action at the node until the road clears. In every other mode, blocked roads are forbidden.

### 7.2 One generic search function, five algorithms

```python
def search(graph, start, goal, algorithm, cost_fn, heuristic_fn, now) -> SearchResult
```

Only the frontier order differs:

| Algorithm | Frontier order |
|---|---|
| BFS | FIFO queue |
| DFS | LIFO stack |
| Uniform-Cost Search | lowest `g` |
| Greedy Best-First | lowest `h` |
| A* | lowest `g + h` |

BFS, DFS and Greedy are for comparison only; they may not return the cheapest route. Vehicles use **A\*** by default. Use `heapq`; break ties by node id for reproducibility.

```python
@dataclass
class SearchResult:
    found: bool
    path_nodes: list[int]; path_edges: list[int]
    cost: float; eta_s: float; distance_km: float
    nodes_expanded: int; max_frontier: int; runtime_ms: float
    steps: list[Step]   # per expansion: node, g, h, f, open list snapshot, closed set (for step-through UI)
```

### 7.3 Heuristic value of each node

For a chosen goal, every node `n` has a heuristic value `h(n)`:

- **Min Time:** `h(n) = straight_line_km(n, goal) / v_max_kph × 3600` (seconds), where `v_max_kph` is the fastest possible emergency speed on the map (max `speed_kph × EMERGENCY_SPEED_FACTOR`).
- **All other modes:** `h(n) = straight_line_km(n, goal)`.
- If `h_override` is supplied for that goal, use it instead.

A fixed number stored on a node only works for one goal, but incidents appear at different places. So `h` is **derived from the node coordinates for whichever goal is active** and is shown on every node in the UI. Because every road's `distance_km` is at least the straight line between its ends (validated), `h` never overestimates, so A* stays optimal.

---

## 8. Modes (`engine/costs.py`)

A mode is a cost function `cost(edge, now, vehicle) -> float or None` (`None` = forbidden). The search code does not change between modes.

| Mode | Cost per road | Blocked roads |
|---|---|---|
| **Min Time** | `travel_time_s` (below) | Allowed only with a short known wait (`+ wait penalty`), else forbidden |
| **Min Distance** | `distance_km` | Forbidden |
| **Min Traffic** | `distance_km × TRAFFIC_WEIGHT[level]` | Forbidden |
| **Safest** | `distance_km × (1 + SAFETY_GAIN × risk)` | Forbidden |
| **Avoid Blocked Roads** | `travel_time_s` | Forbidden, and the vehicle never waits |

```
travel_time_s = distance_km / v_eff_kph × 3600 × curve_slow
v_eff_kph     = speed_kph × EMERGENCY_SPEED_FACTOR / eff_mult
eff_mult      = 1 + (TRAFFIC_MULT[level] − 1) × (1 − PRIORITY_RELIEF[priority])
curve_slow    = 1 + 0.5 × min(curve_ratio − 1, 0.6)          # curvier roads are slower
risk          = clamp(base_risk + 0.1 × level + incident_risk, 0, 1)
```

`incident_risk` is 0.4 on roads touching an active accident and returns to 0 when it resolves. Higher-priority incidents get a larger traffic relief (other traffic gives way).

---

## 9. Traffic and incidents

### 9.1 Traffic (`engine/traffic.py`)

Each road is **LOW (0), MEDIUM (1) or HIGH (2)**. Levels multiply travel time by `TRAFFIC_MULT = [1.0, 1.6, 2.5]`.

- **Initial levels:** sampled by road class. Arterials start busier: roughly arterial 30 / 45 / 25 % (LOW / MED / HIGH), other roads 60 / 30 / 10 %.
- **Update** every `TRAFFIC_UPDATE_S` (30 sim-seconds), for each road independently: with probability `p_up` go up one level (if not HIGH); otherwise with probability `p_down` go down one level (if not LOW).

| Period | Road class | `p_up` | `p_down` |
|---|---|---|---|
| Rush hour (08:00-10:30, 17:00-20:30) | arterial | 0.10 | 0.03 |
| Rush hour | other | 0.05 | 0.05 |
| Off-peak | arterial | 0.03 | 0.10 |
| Off-peak | other | 0.02 | 0.10 |

These numbers are assumptions; tune until the map looks plausible. State in the report that traffic is simulated.

### 9.2 Incidents (`engine/incidents.py`)

```python
Incident: id, kind ("accident"|"fire"|"medical"|"crime"), priority (1..3, 3 = critical),
          node_id, created_t, status ("PENDING"|"ASSIGNED"|"RESOLVED"),
          assigned: list[vehicle_id], blocked_edge: int | None
```

- Created by clicking a node or randomly (about one every few sim-minutes, seeded). Incidents occur at nodes.
- An **accident** blocks one random adjacent road with probability 0.5 (`blocked = True`, `clear_at = now + CLEAR_TIME_S`), and raises traffic by one level on adjacent roads.
- Blocks auto-clear at `clear_at`. The user can also block any road by clicking it, with a chosen clear time.
- If a block leaves no route to a goal, the vehicle waits at its node, sends a `NO_ROUTE` notification, and retries at the next replan interval.

---

## 10. Vehicles and replanning (`engine/agents.py`)

**Vehicle states:** `IDLE → DISPATCHED → ON_SCENE → RETURNING → IDLE`. Idle vehicles sit at their home station node. Types: `ambulance`, `fire`, `police`.

**Movement:** each tick the vehicle advances along its current road by `v_eff × dt`, tracked as the road and a fraction travelled, so travel follows the road's cost model (traffic and curves slow it).

**Wait:** if the next road in the plan is blocked with a short `clear_at`, the vehicle waits at the node, logs `WAIT`, and moves on when it clears.

**Replanning (task 5)** runs from the **next node** (a vehicle cannot reverse mid-road) when:
1. A road on its remaining path becomes blocked, or
2. Every `REPLAN_INTERVAL_S` (20 s): re-run A* and switch if the new route is cheaper than the remaining one by at least `REPLAN_GAIN` (10 %).

Each switch publishes a `REROUTE` notification and writes a path-log row.

**On scene:** when all units assigned to an incident are `ON_SCENE`, a timer of `SERVICE_TIME_S[priority]` starts. When it ends the incident is `RESOLVED`, any road block it caused is cleared, and units become `RETURNING` (path to their home station).
**Cooperation:** once a **police** unit is on scene at an incident that caused a block, the remaining `clear_at` time is halved.

---

## 11. Priority dispatch (`engine/dispatch.py`)

### 11.1 Rules: which units are needed

| Incident | Priority 1-2 | Priority 3 |
|---|---|---|
| medical | 1 ambulance | 2 ambulances |
| fire | 1 fire + 1 ambulance | 2 fire + 1 ambulance |
| accident | 1 police + 1 ambulance | 1 police + 1 ambulance + 1 fire |
| crime | 1 police | 2 police |

Store this as a plain dictionary so it is easy to explain and test.

### 11.2 Priority queue

Pending incidents are served in order of **priority (3 first), then creation time**. Every tick, try to dispatch the head of the queue; if there are not enough idle units, the incident stays pending and a `PENDING` notification is sent.

### 11.3 CSP: choose the best batch

For one incident:

- **Variables:** one per required slot (for example `ambulance_1`, `police_1`).
- **Domains:** idle vehicles of the right type.
- **Constraints:** type match; all assigned vehicles are different.
- **Cost of a full assignment:** compute each vehicle's ETA to the incident node with A* in the **selected mode** (cache within the tick). Choose the assignment that minimizes the **largest ETA**, then the **sum of ETAs**.
- **Solver:** backtracking with forward checking (remove a used vehicle from the other slots' domains; backtrack when a domain becomes empty). Pick the slot with the smallest domain first (MRV). The fleet is small, so enumerating all consistent assignments and keeping the best is fine.

Each chosen vehicle becomes `DISPATCHED`, plans its route with A*, and a `DISPATCH` notification lists the units and ETAs.

---

## 12. Notifications and path logs (`engine/notifications.py`)

**Notification** = `t, type, priority, vehicle_id, incident_id, message`.

| Type | When |
|---|---|
| `INCIDENT_ALERT` | New incident |
| `DISPATCH` | Batch assigned (units and ETAs) |
| `PENDING` | Not enough idle units |
| `REROUTE` | Vehicle changed route (reason, old and new ETA) |
| `WAIT` | Vehicle waits for a road to clear |
| `NO_ROUTE` | No path to the goal right now |
| `ROAD_BLOCKED` / `ROAD_CLEARED` | Block created or cleared |
| `ARRIVAL` | Vehicle on scene or back at base |
| `RESOLVED` | Incident finished |

Keep an in-memory list for the UI and write `logs/<run_id>/notifications.csv`.

**Path log** (`logs/<run_id>/path_log.csv`), one row per vehicle per node reached or action taken:
`t, vehicle_id, incident_id, mode, algorithm, edge (u-v), from_node, to_node, traffic_level, action (MOVE | WAIT | REROUTE), cost_so_far, eta_remaining`.

---

## 13. UI (`ui/pygame_app.py`)

- **Graph view:** nodes as circles at their coordinates with name labels; stations marked `H`, `F`, `P`. Roads as lines colored green (LOW), amber (MEDIUM), red (HIGH), blocked roads dark gray with a marker, each labeled with its distance. Incidents are markers sized by priority; vehicles are colored dots moving along roads. The selected vehicle's path is highlighted.
- **Heuristic display:** when a goal is active, every node shows its `h` value.
- **Step-through search (task 8):** press `N` to expand one node at a time; show the **open list** (node, g, h, f) and the **closed list** in a panel, with the frontier, explored nodes and final path in different colors. `R` resets, `Enter` runs to completion.
- **Sidebar:**
  1. Mode buttons (5) and algorithm buttons (5).
  2. Simulation speed and pause.
  3. Incident queue and fleet status (one compact list).
  4. **Search info:** nodes expanded, max frontier, cost, ETA, runtime; and a comparison table of all five algorithms for a chosen origin and destination.
  5. **Notification feed** (newest first, colored by type).
  6. Path log of the selected vehicle.
- **Input:** `Space` pause, `+`/`-` speed, `1`-`5` mode, `F1`-`F5` algorithm, `N` step, `Enter` run, `R` reset, `C` compare (click an algorithm row to highlight its path). `O` / `D` then click a node to set origin / destination. Press `I`, choose incident kind with `M`/`F`/`A`/`C`, priority with `1`-`3`, then click a node. Press `B` then click a road to block it. Click a vehicle to select it.

---

## 14. Environment classification and agent types

| Property | Classification |
|---|---|
| Observability | Fully observable (live traffic and incidents are visible to all vehicles) |
| Determinism | Stochastic (random traffic changes and incidents) |
| Episodic / sequential | Sequential |
| Static / dynamic | Dynamic |
| Discrete / continuous | Discrete (graph, tick-based time) |
| Agents | Multi-agent, cooperative with shared resources |
| Known / unknown | Known map, unknown future events |

Agent types to describe: **goal-based** (route to the incident), **utility-based** (mode cost minimization), **model-based** (replanning with a world model), and a **dispatcher agent** using rules and CSP.

---

## 15. Configuration (`config.py`)

```python
SEED = 42
GRAPH_FILE = "data/city_graph.json"

START_TIME = "08:00"
TIME_SCALE = 20                        # sim-seconds per real second (adjustable in UI)
TRAFFIC_UPDATE_S = 30
TRAFFIC_MULT = [1.0, 1.6, 2.5]
TRAFFIC_WEIGHT = [1, 2, 4]
EMERGENCY_SPEED_FACTOR = 1.2
PRIORITY_RELIEF = {1: 0.2, 2: 0.4, 3: 0.6}
SAFETY_GAIN = 3.0

MAX_WAIT_S = 120
REPLAN_INTERVAL_S = 20
REPLAN_GAIN = 0.10
CLEAR_TIME_S = 300
SERVICE_TIME_S = {1: 120, 2: 180, 3: 240}
FLEET = {                              # {vehicle type: {station node id: count}}
    "ambulance": {0: 2, 9: 1},
    "fire":      {10: 1, 17: 1},
    "police":    {4: 1, 12: 2},
}
```

All values are starting points to tune.

---

## 16. Build phases and acceptance

- [x] **Phase 1: Graph.** `city_graph.json`, `graph.py`, `validate_graph.py`, Pygame viewer drawing nodes, roads and labels.
  *Accept:* the sample graph loads and passes validation; roads and stations render correctly.
- [x] **Phase 2: Search and modes.** `search.py`, `costs.py`, `h` labels on nodes, step-through view, algorithm comparison table.
  *Accept:* on all node pairs, A* cost equals UCS cost in every mode; A* expands no more nodes than UCS; BFS returns the fewest roads; blocked roads never appear in a path.
- [x] **Phase 3: Traffic, incidents, vehicles, replanning.** `traffic.py`, `incidents.py`, `agents.py`.
  *Accept:* traffic states are reproducible for a seed and rush-hour updates raise traffic; vehicles move along roads and slow with traffic; blocking a road on a vehicle's path triggers a reroute or a wait.
- [x] **Phase 4: Dispatch, notifications, logs.** `dispatch.py`, `notifications.py`.
  *Accept:* two simultaneous incidents are served in priority order; the CSP result matches brute force on small cases; both CSV logs are written.
- [x] **Phase 5: Polish and report.** Sidebar panels, click-to-incident and click-to-block, environment classification write-up.
  *Accept:* every required task is demonstrable from the UI in a 5-minute demo.

---

## 17. Optional extensions

Hospital transport leg for ambulances, a larger or randomly generated graph, one-way roads, priority aging and preemption, time-expanded search, a reservation table and green corridor, or porting the graph to a real OpenStreetMap area. The real-map design is in `README_FULL.md`.

---

## 18. Known simplifications

- The city is an abstract graph, not a real map.
- Roads are two-way and share one traffic state per road.
- Traffic is simulated, not observed.
- Waiting for a block is estimated from the current time, which slightly overstates the wait for vehicles that arrive later.
- `curve_ratio` is one number per road, so it cannot describe where on the road the bends are.

## 19. Run and reference

Start the Pygame application with `conda run -n rescue python ui/pygame_app.py`.

Reference documents are in `docs/USER_GUIDE.md`, `docs/ARCHITECTURE.md`, `docs/DATA_REFERENCE.md`, `docs/ASSUMPTIONS.md`, and `docs/ENVIRONMENT_CLASSIFICATION.md`.
