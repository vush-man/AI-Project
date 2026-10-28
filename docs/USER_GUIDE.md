# User Guide

## Start the application

From the project directory, use the `rescue` Conda environment:

```powershell
conda run -n rescue python ui/pygame_app.py
```

The simulation starts at 08:00 with a seeded traffic state and begins generating seeded incidents after a few simulated minutes. CSV logs are saved in a timestamped directory under `logs/`.

Validate the graph with:

```powershell
conda run -n rescue python scripts/validate_graph.py --graph data/city_graph.json
```

## Keyboard and mouse

| Input | Action |
|---|---|
| `1`–`5` | Choose route mode: travel time, distance, traffic, safest, avoid blocked |
| `F1`–`F5` | Choose BFS, DFS, UCS, Greedy, or A* |
| `N` | Show the next search expansion |
| `Enter` | Run the selected search to completion |
| `R` | Clear search display and restart step-through |
| `C` | Compare all five algorithms for the selected origin and destination |
| `Space` | Pause or resume simulation |
| `+` / `-` | Increase or decrease simulation speed |
| `O`, then click a node | Set search origin |
| `D`, then click a node | Set search destination |
| `I`, optional kind/priority keys, then click a node | Add an incident; `M` medical, `F` fire, `A` accident, `C` crime; `1`–`3` priority |
| `B`, then click a road | Block that road for the configured clearance duration |
| Click a vehicle | Select it and show its route and recent path-log rows |
| `Esc` | Close the application |

Mode numbers and incident priority numbers share keys. While choosing an incident, `1`–`3` set incident priority; otherwise they change route mode.

## Read the display

- The interface uses a dark background. Traffic levels stay green, amber, and red; the selected route is bright blue.
- Green, amber and red roads represent low, medium and high traffic. Gray roads are blocked.
- A blue highlighted road is the selected search path. During step-through, cyan rings show the open set, purple rings show explored nodes, and a gold ring marks the current expansion.
- After pressing `C`, click an algorithm row in the comparison table to highlight that algorithm's path in blue.
- `h=` labels show each node's heuristic toward the selected destination.
- Station markers use `H`, `F`, and `P`. Incident rings grow with priority; vehicle dots show current positions.
- The sidebar shows selected mode and algorithm, search counters, algorithm comparison, fleet states, pending/active incidents, and the latest notifications.

