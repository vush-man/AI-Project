"""Pygame simulation, graph viewer and search teaching interface."""
from __future__ import annotations

import argparse
from datetime import datetime
import math
from pathlib import Path
import sys

import pygame

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from config import (BACKGROUND, BLOCKED_ROAD_COLOR, GRAPH_FILE, MAP_SIZE,
                    MUTED_TEXT_COLOR, PATH_COLOR, ROAD_COLORS, SEED,
                    SIDEBAR_BACKGROUND, TEXT_COLOR, TIME_SCALE, WINDOW_SIZE)  # noqa: E402
from engine.costs import MODES, edge_cost, heuristic, make_heuristic_fn  # noqa: E402
from engine.graph import Graph  # noqa: E402
from engine.search import ALGORITHMS, SearchResult, search  # noqa: E402
from engine.sim import Simulation  # noqa: E402

STATION_COLORS = {"hospital": (235, 90, 100), "fire": (250, 137, 54), "police": (90, 150, 245), "junction": (112, 128, 150)}
LABELS = {"hospital": "H", "fire": "F", "police": "P"}


def node_point(node, surface_size):
    left, right, top, bottom = 65, surface_size[0] - 65, 70, surface_size[1] - 70
    xs, ys = [1, 9], [1, 7]
    x = left + (node.x - xs[0]) / (xs[1] - xs[0]) * (right - left)
    y = bottom - (node.y - ys[0]) / (ys[1] - ys[0]) * (bottom - top)
    return round(x), round(y)


def draw_graph(surface: pygame.Surface, graph: Graph, font: pygame.font.Font,
               path_nodes=None, goal_id=None, sim: Simulation | None = None, search_step=None) -> None:
    surface.fill(BACKGROUND)
    path_nodes = path_nodes or []
    path_pairs = {frozenset((a, b)) for a, b in zip(path_nodes, path_nodes[1:])}
    open_nodes = {item[0] for item in search_step.open_list} if search_step else set()
    closed_nodes = set(search_step.closed) if search_step else set()
    for edge in graph.edges.values():
        p1, p2 = node_point(graph.nodes[edge.u], surface.get_size()), node_point(graph.nodes[edge.v], surface.get_size())
        is_path = frozenset((edge.u, edge.v)) in path_pairs
        color = PATH_COLOR if is_path else BLOCKED_ROAD_COLOR if edge.blocked else ROAD_COLORS.get(edge.traffic, ROAD_COLORS[0])
        width = 7 if is_path else 4
        pygame.draw.line(surface, color, p1, p2, width)
        if edge.blocked:
            mid = ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)
            pygame.draw.line(surface, (245, 245, 245), (mid[0] - 5, mid[1] - 5), (mid[0] + 5, mid[1] + 5), 2)
            pygame.draw.line(surface, (245, 245, 245), (mid[0] - 5, mid[1] + 5), (mid[0] + 5, mid[1] - 5), 2)
        label = font.render(f"{edge.distance_km:.1f}km", True, MUTED_TEXT_COLOR)
        surface.blit(label, ((p1[0] + p2[0]) // 2 + 3, (p1[1] + p2[1]) // 2 + 3))
    for node in graph.nodes.values():
        pos, color = node_point(node, surface.get_size()), STATION_COLORS[node.type]
        if sim:
            at_node = [i for i in sim.incidents.incidents if i.node_id == node.id and i.status != "RESOLVED"]
            if at_node:
                pygame.draw.circle(surface, (245, 89, 222), pos, 21 + max(i.priority for i in at_node) * 2, 3)
        pygame.draw.circle(surface, color, pos, 15 if node.type != "junction" else 11)
        if node.id in open_nodes:
            pygame.draw.circle(surface, (45, 205, 219), pos, 19, 2)
        if node.id in closed_nodes:
            pygame.draw.circle(surface, (180, 136, 235), pos, 22, 2)
        if search_step and node.id == search_step.node:
            pygame.draw.circle(surface, (255, 202, 75), pos, 26, 3)
        marker = font.render(LABELS.get(node.type, str(node.id)), True, (255, 255, 255))
        surface.blit(marker, marker.get_rect(center=pos))
        name = font.render(node.name, True, TEXT_COLOR)
        label_x = pos[0] - name.get_width() - 13 if pos[0] > surface.get_width() - 140 else pos[0] + 13
        surface.blit(name, (label_x, pos[1] - 22))
        if goal_id is not None:
            h = heuristic(graph, node.id, goal_id, sim.mode if sim else MODES[1])
            h_label = font.render(f"h={h:.1f}", True, (124, 187, 255))
            surface.blit(h_label, (pos[0] + 11, pos[1] + 5))
    if sim:
        colors = {"ambulance": (220, 30, 50), "fire": (250, 110, 25), "police": (25, 70, 210)}
        for vehicle in sim.fleet.vehicles:
            point = _vehicle_point(graph, vehicle, surface.get_size())
            pygame.draw.circle(surface, colors[vehicle.type], point, 6)


def draw_text(surface, text, x, y, font, color=TEXT_COLOR):
    surface.blit(font.render(text, True, color), (x, y))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", default=GRAPH_FILE)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--frames", type=int, default=0, help="exit after this many frames (useful for headless smoke checks)")
    parser.add_argument("--log-dir", help="override the timestamped CSV log directory")
    args = parser.parse_args()
    if args.frames < 0:
        parser.error("--frames cannot be negative")
    graph = Graph.load(args.graph)
    log_dir = Path(args.log_dir) if args.log_dir else ROOT / "logs" / datetime.now().strftime("run_%Y%m%d_%H%M%S")
    sim = Simulation(graph, seed=args.seed, log_dir=log_dir)
    pygame.init()
    screen = pygame.display.set_mode(WINDOW_SIZE)
    pygame.display.set_caption("Emergency Response & Rescue Agent")
    font = pygame.font.Font(None, 19)
    title_font = pygame.font.Font(None, 25)
    clock = pygame.time.Clock()
    mode_index, algorithm_index, origin, destination = 0, 4, 0, 19
    result: SearchResult | None = None
    comparison = []
    comparison_selected = algorithm_index
    comparison_row_rects = []
    step_index = -1
    paused, speed, click_mode = False, 1.0, None
    selected_vehicle = None
    incident_kind, incident_priority = "medical", 2
    frame_count = 0
    running = True
    while running:
        dt_real = clock.tick(30) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    paused = not paused
                elif event.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                    speed = min(8.0, speed * 1.5)
                elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    speed = max(0.125, speed / 1.5)
                elif click_mode == "incident" and event.key in (pygame.K_m, pygame.K_f, pygame.K_a, pygame.K_c):
                    incident_kind = {pygame.K_m: "medical", pygame.K_f: "fire", pygame.K_a: "accident", pygame.K_c: "crime"}[event.key]
                elif click_mode == "incident" and event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                    incident_priority = event.key - pygame.K_0
                elif pygame.K_1 <= event.key <= pygame.K_5:
                    mode_index = event.key - pygame.K_1
                    sim.set_mode(MODES[mode_index])
                    result, comparison = None, []
                    comparison_row_rects = []
                elif pygame.K_F1 <= event.key <= pygame.K_F5:
                    algorithm_index = event.key - pygame.K_F1
                    result = None
                    if comparison:
                        comparison_selected = algorithm_index
                elif event.key == pygame.K_o:
                    click_mode = "origin"
                elif event.key == pygame.K_d:
                    click_mode = "destination"
                elif event.key == pygame.K_i:
                    click_mode = "incident"
                elif event.key == pygame.K_b:
                    click_mode = "block"
                elif event.key == pygame.K_c:
                    comparison = [search(graph, origin, destination, alg, lambda e, t, v: edge_cost(sim.mode, e, t, v), make_heuristic_fn(graph, destination, sim.mode), sim.now) for alg in ALGORITHMS]
                    comparison_selected = algorithm_index
                    result, step_index = None, -1
                    comparison_row_rects = []
                elif event.key == pygame.K_n:
                    comparison, comparison_row_rects = [], []
                    if result is None:
                        result = search(graph, origin, destination, ALGORITHMS[algorithm_index], lambda e, t, v: edge_cost(sim.mode, e, t, v), make_heuristic_fn(graph, destination, sim.mode), sim.now)
                        step_index = -1
                    step_index = min(step_index + 1, len(result.steps) - 1)
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    comparison, comparison_row_rects = [], []
                    result = search(graph, origin, destination, ALGORITHMS[algorithm_index], lambda e, t, v: edge_cost(sim.mode, e, t, v), make_heuristic_fn(graph, destination, sim.mode), sim.now)
                    step_index = len(result.steps) - 1
                elif event.key == pygame.K_r:
                    result, step_index, comparison, comparison_row_rects = None, -1, [], []
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                if mx >= MAP_SIZE[0]:
                    for index, rect in enumerate(comparison_row_rects):
                        if rect.collidepoint(mx, my):
                            comparison_selected = algorithm_index = index
                            result, step_index = None, -1
                            break
                    continue
                if click_mode in ("origin", "destination", "incident"):
                    nearest = min(graph.nodes, key=lambda n: math.dist((mx, my), node_point(graph.nodes[n], MAP_SIZE)))
                    if click_mode == "origin":
                        origin = nearest
                        result, comparison = None, []
                        comparison_row_rects = []
                    elif click_mode == "destination":
                        destination = nearest
                        result, comparison = None, []
                        comparison_row_rects = []
                    else:
                        sim.add_incident(incident_kind, incident_priority, nearest)
                    click_mode = None
                elif click_mode == "block":
                    point = (mx, my)
                    edge = min(graph.edges.values(), key=lambda e: _point_segment_distance(point, node_point(graph.nodes[e.u], MAP_SIZE), node_point(graph.nodes[e.v], MAP_SIZE)))
                    if _point_segment_distance(point, node_point(graph.nodes[edge.u], MAP_SIZE), node_point(graph.nodes[edge.v], MAP_SIZE)) <= 16:
                        sim.incidents.block_edge(edge.id, sim.now)
                        click_mode = None
                else:
                    candidates = [(math.dist((mx, my), _vehicle_point(graph, vehicle, MAP_SIZE)), vehicle)
                                  for vehicle in sim.fleet.vehicles]
                    if candidates:
                        distance, vehicle = min(candidates, key=lambda row: row[0])
                        if distance <= 16:
                            selected_vehicle = vehicle
        if not paused:
            sim.step(dt_real * speed * TIME_SCALE)
        if comparison and 0 <= comparison_selected < len(comparison):
            result_path = comparison[comparison_selected].path_nodes
        else:
            result_path = result.path_nodes if result and step_index >= len(result.steps) - 1 else (selected_vehicle.path_nodes if selected_vehicle and result is None else [])
        active_step = result.steps[step_index] if result and 0 <= step_index < len(result.steps) and step_index < len(result.steps) - 1 else None
        screen.fill(BACKGROUND)
        map_surface = screen.subsurface((0, 0, MAP_SIZE[0], MAP_SIZE[1]))
        draw_graph(map_surface, graph, font, result_path, destination, sim, active_step)
        sidebar = screen.subsurface((MAP_SIZE[0], 0, WINDOW_SIZE[0] - MAP_SIZE[0], WINDOW_SIZE[1]))
        sidebar.fill(SIDEBAR_BACKGROUND)
        comparison_row_rects = []
        x, y = 775, 18
        draw_text(sidebar, "RESCUE SIMULATION", 0, y, title_font); y += 32
        draw_text(sidebar, "Roads: LOW green / MED amber / HIGH red / blue path", 0, y, font); y += 20
        sim_hour = int(sim.hour)
        sim_minute = int((sim.hour - sim_hour) * 60)
        draw_text(sidebar, f"Time {sim_hour:02d}:{sim_minute:02d}   Speed {speed:g}x", 0, y, font); y += 22
        draw_text(sidebar, f"{'PAUSED' if paused else 'RUNNING'}  | Space pause, +/- speed", 0, y, font); y += 28
        draw_text(sidebar, "MODES (1–5)", 0, y, title_font); y += 22
        for index, mode in enumerate(MODES):
            draw_text(sidebar, f"{'▶ ' if index == mode_index else '  '}{index+1}. {mode}", 0, y, font); y += 19
        y += 5
        draw_text(sidebar, "SEARCH (F1 BFS ... F5 A*)", 0, y, title_font); y += 22
        draw_text(sidebar, f"{ALGORITHMS[algorithm_index]}  {origin} → {destination}", 0, y, font); y += 19
        draw_text(sidebar, "N step | Enter run | R reset | C compare", 0, y, font); y += 22
        if result:
            step = result.steps[min(max(step_index, 0), len(result.steps)-1)] if result.steps else None
            draw_text(sidebar, f"Expanded {result.nodes_expanded}  Frontier max {result.max_frontier}", 0, y, font); y += 18
            draw_text(sidebar, f"Cost {result.cost:.2f}  ETA {result.eta_s:.1f}s  Dist {result.distance_km:.1f}km", 0, y, font); y += 18
            draw_text(sidebar, f"Runtime {result.runtime_ms:.2f}ms  Step {step_index+1}/{len(result.steps)}", 0, y, font); y += 22
            if step:
                draw_text(sidebar, f"Open: {[(n, round(g,1)) for n,g,_,_ in step.open_list[:4]]}", 0, y, font); y += 18
                draw_text(sidebar, f"Closed: {step.closed[-8:]}", 0, y, font); y += 18
        if comparison:
            draw_text(sidebar, "ALGORITHM COMPARISON · click row for path", 0, y, font); y += 19
            for index, (alg, row) in enumerate(zip(ALGORITHMS, comparison)):
                if index == comparison_selected:
                    pygame.draw.rect(sidebar, PATH_COLOR, (0, y - 1, sidebar.get_width(), 18), border_radius=3)
                text_color = (255, 255, 255) if index == comparison_selected else TEXT_COLOR
                draw_text(sidebar, f"{alg:6} exp {row.nodes_expanded:2} cost {row.cost:.1f} {row.runtime_ms:.2f}ms", 4, y, font, text_color)
                comparison_row_rects.append(pygame.Rect(MAP_SIZE[0], y - 1, sidebar.get_width(), 18))
                y += 18
        y = max(y + 5, 425)
        draw_text(sidebar, "FLEET / INCIDENTS", 0, y, title_font); y += 22
        for vehicle in sim.fleet.vehicles[:7]:
            draw_text(sidebar, f"{vehicle.id:8} {vehicle.type:9} {vehicle.state:10} @ {vehicle.node_id}", 0, y, font); y += 17
        for incident in [i for i in sim.incidents.incidents if i.status != "RESOLVED"][-3:]:
            draw_text(sidebar, f"{incident.id} P{incident.priority} {incident.kind} {incident.status}", 0, y, font, (255, 125, 228)); y += 17
        if selected_vehicle:
            draw_text(sidebar, f"Selected: {selected_vehicle.id} path {selected_vehicle.path_nodes}", 0, min(y, 615), font); y += 18
            recent = [row for row in sim.notifications.path_rows if row.get("vehicle_id") == selected_vehicle.id][-2:]
            for row in recent:
                draw_text(sidebar, f"{row['action']} {row['from_node']}→{row['to_node']} t={row['t']:.0f}", 0, min(y, 650), font); y += 17
        y = min(y + 5, 625)
        draw_text(sidebar, "LATEST NOTIFICATIONS", 0, y, title_font); y += 22
        for note in reversed(sim.notifications.items[-6:]):
            line = f"{note.type}: {note.message}"
            note_color = (255, 125, 228) if "INCIDENT" in note.type else (255, 130, 112) if "BLOCK" in note.type else (105, 220, 157) if note.type in ("DISPATCH", "ARRIVAL", "RESOLVED") else MUTED_TEXT_COLOR
            draw_text(sidebar, line[:43], 0, y, font, note_color); y += 17
        prompt = f"I: M/F/A/C type, 1–3 priority; click node ({incident_kind}, P{incident_priority})" if click_mode == "incident" else "O/D + click node | I incident | B block road"
        draw_text(sidebar, prompt[:52], 0, 724, font)
        pygame.display.flip()
        frame_count += 1
        if args.frames and frame_count >= args.frames:
            running = False
    sim.notifications.flush()
    pygame.quit()


def _point_segment_distance(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    if dx == 0 and dy == 0:
        return math.dist(p, a)
    t = max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)))
    return math.dist(p, (a[0] + t * dx, a[1] + t * dy))


def _vehicle_point(graph, vehicle, size):
    point = node_point(graph.nodes[vehicle.node_id], size)
    if vehicle.path_index < len(vehicle.path_edges) and vehicle.road_progress_km > 0:
        edge = graph.edges[vehicle.path_edges[vehicle.path_index]]
        a, b = node_point(graph.nodes[edge.u], size), node_point(graph.nodes[edge.v], size)
        fraction = vehicle.road_progress_km / edge.distance_km
        if vehicle.node_id == edge.v:
            fraction = 1 - fraction
        return round(a[0] + (b[0] - a[0]) * fraction), round(a[1] + (b[1] - a[1]) * fraction)
    return point


def _trace_step_path(result, index):
    # Trace best-known parents is not part of SearchResult; highlight explored prefix during stepping.
    return result.path_nodes[: min(len(result.path_nodes), max(1, index + 1))]


if __name__ == "__main__":
    main()
