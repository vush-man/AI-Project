# Environment and Agent Classification

## Environment properties

| Property | Classification | Reason in this simulation |
|---|---|---|
| Observability | Fully observable | Vehicles share the graph's current traffic, closures, incidents, and unit states. |
| Determinism | Stochastic | Seeded traffic transitions and generated incidents introduce uncertainty while keeping a run reproducible. |
| Episodic / sequential | Sequential | A route and dispatch decision changes vehicle positions, availability, and future choices. |
| Static / dynamic | Dynamic | Traffic and road closures change as simulation time advances. |
| Discrete / continuous | Discrete state with continuous quantities | Nodes, traffic levels, and incidents are discrete; time and distance progress within each tick. |
| Agents | Cooperative multi-agent | Units share incidents and response goals, while competing for a limited fleet. |
| Known / unknown | Known map, unknown future events | The road and movement model is known; future traffic and incident events are not. |

## Agent types

- **Goal-based vehicle agents** select routes to an incident or home station.
- **Utility-based route choice** minimizes the selected mode's cost (travel time, distance, traffic, risk, or blocked-road avoidance).
- **Model-based behavior** tracks current graph state and replans after relevant road or route changes.
- **Rule-based dispatcher** translates incident kind and priority into required unit types.
- **CSP dispatcher** assigns distinct available vehicles to required slots, using backtracking, forward checking by used-unit removal, and minimum remaining values. It minimizes maximum ETA and then total ETA.

