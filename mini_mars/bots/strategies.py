"""Small strategies with replaceable path and task-selection functions."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from math import ceil, inf
import random
from typing import Any


Point = tuple[int, int]
DIRECTIONS = (("N", 0, -1), ("S", 0, 1), ("E", 1, 0), ("W", -1, 0))


def known_cells(observation: dict) -> dict[Point, dict]:
    return {(cell["x"], cell["y"]): cell for cell in observation["cells"]}


def bfs(start: Point, cells: dict[Point, dict]) -> tuple[dict[Point, int], dict[Point, str]]:
    """Shortest paths over explored, traversable tiles: O(V + E)."""
    distances = {start: 0}
    first_moves: dict[Point, str] = {}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for direction, dx, dy in DIRECTIONS:
            point = (x + dx, y + dy)
            if point in distances or cells.get(point, {}).get("terrain") != "plain":
                continue
            distances[point] = distances[(x, y)] + 1
            first_moves[point] = first_moves.get((x, y), direction)
            queue.append(point)
    return distances, first_moves


def shortest_base(rover: dict, bases: list[dict], cells: dict[Point, dict]) -> tuple[Point, int, str | None]:
    start = (rover["x"], rover["y"])
    distances, first_moves = bfs(start, cells)
    options = [((base["x"], base["y"]), distances[(base["x"], base["y"])])
               for base in bases if (base["x"], base["y"]) in distances]
    if not options:
        return start, inf, None
    point, distance = min(options, key=lambda item: (item[1], item[0]))
    return point, distance, first_moves.get(point)


def base_distance(point: Point, bases: list[dict], cells: dict[Point, dict]) -> int:
    distances, _ = bfs(point, cells)
    return min((distances.get((base["x"], base["y"]), inf) for base in bases), default=inf)


def home_distances(bases: list[dict], cells: dict[Point, dict]) -> dict[Point, int]:
    """Multi-source BFS; every known route to any friendly base is considered."""
    starts = [(base["x"], base["y"]) for base in bases]
    distances = {point: 0 for point in starts}
    queue = deque(starts)
    while queue:
        x, y = queue.popleft()
        for _, dx, dy in DIRECTIONS:
            point = (x + dx, y + dy)
            if point in distances or cells.get(point, {}).get("terrain") != "plain":
                continue
            distances[point] = distances[(x, y)] + 1
            queue.append(point)
    return distances


def remaining_turns(observation: dict) -> int:
    return observation["constants"]["turns"] - observation["turn"]


def feasible_mining_units(observation: dict, rover: dict, point: Point, cell: dict,
                          travel: int, cells: dict[Point, dict], endgame: bool,
                          home: dict[Point, int]) -> int:
    constants = observation["constants"]
    free = constants["cargo_capacity"] - sum(rover["cargo"].values())
    units = min(free, cell["quantity"])
    if not endgame:
        return units
    mining_turns = remaining_turns(observation) - travel - home.get(point, inf) - 1
    units = min(units, max(0, mining_turns) * constants["mine_rate"])
    if cell["resource"] == "iron":
        # Optimistic lower bound for enough iron, a deposit, a build, and one
        # scored gold deposit. Extra travel can only make the investment slower.
        bank = observation["bank"]["iron"]
        carried = sum(item["cargo"]["iron"] for item in observation.get("rovers", []))
        deficit = max(0, constants["base_cost_iron"] - bank - carried)
        minimum_trip = (travel + max(1, ceil(deficit / constants["mine_rate"])) +
                        home.get(point, inf) + ceil(deficit / constants["cargo_capacity"]) + 3)
        if deficit == 0 or remaining_turns(observation) < minimum_trip or not any(
                item["resource"] == "gold" and item["quantity"] > 0 for item in cells.values()):
            return 0
    return units


def move(rover_id: str, direction: str | None) -> dict:
    return {"rover_id": rover_id, "type": "MOVE", "direction": direction} if direction else {
        "rover_id": rover_id, "type": "WAIT"}


def simple(rover_id: str, kind: str) -> dict:
    return {"rover_id": rover_id, "type": kind}


def protect_scored_cargo(observation: dict, rover: dict, action: dict,
                         cells: dict[Point, dict], bases: list[dict]) -> tuple[dict, Point | None]:
    """Keep a feasible gold delivery feasible after this action, including DEPOSIT."""
    if not rover["cargo"]["gold"] or action["type"] == "DEPOSIT":
        return action, None
    base, distance, direction = shortest_base(rover, bases, cells)
    left = remaining_turns(observation)
    if distance + 1 > left:  # No feasible delivery can be rescued here.
        return action, None
    next_point = (rover["x"], rover["y"])
    if action["type"] == "MOVE":
        delta = next(((dx, dy) for name, dx, dy in DIRECTIONS
                      if name == action.get("direction")), None)
        if delta is not None:
            next_point = (next_point[0] + delta[0], next_point[1] + delta[1])
    # A MOVE, MINE, BUILD, or WAIT all consume one action. A base needs one
    # additional DEPOSIT action, including when the rover is already there.
    if base_distance(next_point, bases, cells) + 1 > left - 1:
        return move(rover["id"], direction), base
    return action, None


def unknown_near(point: Point, cells: dict[Point, dict], width: int, height: int, radius: int) -> int:
    x, y = point
    return sum((nx, ny) not in cells for dx in range(-radius, radius + 1)
               for dy in range(-radius + abs(dx), radius - abs(dx) + 1)
               if 0 <= (nx := x + dx) < width and 0 <= (ny := y + dy) < height)


def exploration_targets(observation: dict, cells: dict[Point, dict]) -> list[tuple[Point, int]]:
    constants = observation["constants"]
    return [(point, count) for point, cell in cells.items() if cell["terrain"] == "plain"
            and (count := unknown_near(point, cells, observation["width"], observation["height"],
                                       constants["vision_radius"])) > 0]


class RandomBot:
    def __init__(self, seed: int) -> None:
        self.rng = random.Random(seed)

    def decide(self, observation: dict) -> list[dict]:
        cells = known_cells(observation)
        bases = {(base["x"], base["y"]) for base in observation["bases"]}
        occupied_bases = bases | {(base["x"], base["y"]) for base in observation["enemies"]["bases"]}
        iron_budget = observation["bank"]["iron"]
        base_cost = observation["constants"]["base_cost_iron"]
        actions = []
        for rover in observation["rovers"]:
            point = (rover["x"], rover["y"])
            cargo = rover["cargo"]
            choices = [simple(rover["id"], "WAIT")]
            if cells[point]["quantity"] > 0 and sum(cargo.values()) < observation["constants"]["cargo_capacity"]:
                choices.append(simple(rover["id"], "MINE"))
            if point in bases and sum(cargo.values()) > 0:
                choices.append(simple(rover["id"], "DEPOSIT"))
            if iron_budget >= base_cost and point not in occupied_bases:
                choices.append(simple(rover["id"], "BUILD"))
            for direction, dx, dy in DIRECTIONS:
                if cells.get((point[0] + dx, point[1] + dy), {}).get("terrain") == "plain":
                    choices.append(move(rover["id"], direction))
            chosen = self.rng.choice(choices)
            if chosen["type"] == "BUILD":
                iron_budget -= base_cost
                occupied_bases.add(point)
            actions.append(chosen)
        return actions


class GreedyMiner:
    """Each rover independently chooses a nearby gold deposit, then returns."""

    def __init__(self, endgame: bool = True, cargo_safety: bool = True) -> None:
        self.endgame = endgame
        self.cargo_safety = cargo_safety
        self.diagnostic_targets: dict[str, Point] = {}

    def deposit_rank(self, point: Point, cell: dict, distance: int,
                     rover: dict, bases: list[dict], capacity: int,
                     home: dict[Point, int]) -> tuple:
        return (0 if cell["resource"] == "gold" else 1, distance, point)

    def decide(self, observation: dict) -> list[dict]:
        cells = known_cells(observation)
        deposits = [(point, cell) for point, cell in cells.items()
                    if cell["terrain"] == "plain" and cell["quantity"] > 0 and cell["resource"]]
        frontiers = exploration_targets(observation, cells)
        capacity = observation["constants"]["cargo_capacity"]
        bases = observation["bases"]
        home = home_distances(bases, cells)
        actions = []
        targets: dict[str, Point] = {}
        self.diagnostic_targets = {}
        for rover in observation["rovers"]:
            rover_id = rover["id"]
            cargo = sum(rover["cargo"].values())
            base, home_distance, base_move = shortest_base(rover, bases, cells)
            start = (rover["x"], rover["y"])
            if cargo and start == base:
                actions.append(simple(rover_id, "DEPOSIT"))
                continue
            if self.endgame and cargo and home_distance + 1 > remaining_turns(observation):
                actions.append(simple(rover_id, "WAIT"))
                continue
            if cargo >= capacity or (self.endgame and rover["cargo"]["gold"] and
                                     home_distance + 1 >= remaining_turns(observation)):
                actions.append(move(rover_id, base_move))
                targets[rover_id] = base
                continue
            distances, first_moves = bfs(start, cells)
            reachable = [(self.deposit_rank(point, cell, distances[point], rover, bases, capacity, home), point)
                         for point, cell in deposits if point in distances and
                         feasible_mining_units(observation, rover, point, cell, distances[point], cells,
                                               self.endgame, home) > 0]
            if reachable:
                _, target = min(reachable)
                targets[rover_id] = target
                actions.append(simple(rover_id, "MINE") if target == start
                               else move(rover_id, first_moves[target]))
            elif cargo:
                actions.append(move(rover_id, base_move))
                targets[rover_id] = base
            else:
                frontier_options = [(distances[point], -unseen, point) for point, unseen in frontiers if point in distances]
                target = min(frontier_options)[2] if frontier_options else None
                actions.append(move(rover_id, first_moves.get(target)))
                if target is not None:
                    targets[rover_id] = target
        self.diagnostic_targets.update(targets)
        if self.endgame and self.cargo_safety:
            for index, rover in enumerate(observation["rovers"]):
                actions[index], override = protect_scored_cargo(observation, rover, actions[index], cells, bases)
                if override is not None:
                    self.diagnostic_targets[rover["id"]] = override
        return actions


class ValueGreedy(GreedyMiner):
    """Keep greedy's choices, but rank same-resource deposits by useful units per turn."""

    def deposit_rank(self, point: Point, cell: dict, distance: int,
                     rover: dict, bases: list[dict], capacity: int,
                     home: dict[Point, int]) -> tuple:
        units = min(cell["quantity"], capacity - sum(rover["cargo"].values()))
        return_distance = home.get(point, inf)
        value = units / (distance + units + return_distance + 1)
        return (0 if cell["resource"] == "gold" else 1, -value, point)


@dataclass(frozen=True)
class StrategySettings:
    """Fixed experiment switches; all variants share the same path and bid code."""

    coordinate: bool = True
    frontier_policy: str = "information-gain"
    endgame_enabled: bool = True
    exploration_weight: float = 0.24
    persistence_bonus: float = 1.2
    iron_enabled: bool = True
    build_enabled: bool = True
    build_policy: str = "heuristic"
    early_iron_weight: float = 0.65
    late_iron_weight: float = 0.05
    visible_enemy_penalty: float = 0.8


def task_candidates(observation: dict, rover: dict, cells: dict[Point, dict],
                    frontiers: list[tuple[Point, int]], prior_target: Point | None,
                    settings: StrategySettings) -> list[tuple[float, str, Point, str | None, tuple]]:
    """Rank useful deposits and scouting cells by estimated reward per turn."""
    start = (rover["x"], rover["y"])
    distances, first_moves = bfs(start, cells)
    capacity = observation["constants"]["cargo_capacity"] - sum(rover["cargo"].values())
    bases = [(base["x"], base["y"]) for base in observation["bases"]]
    home = home_distances(observation["bases"], cells)
    enemy_points = [(enemy["x"], enemy["y"]) for enemy in observation["enemies"]["rovers"]]
    candidates = []
    for point, cell in cells.items():
        if point not in distances or cell["terrain"] != "plain" or cell["quantity"] <= 0 or not cell["resource"]:
            continue
        units = feasible_mining_units(observation, rover, point, cell, distances[point], cells,
                                      settings.endgame_enabled, home)
        if units <= 0:
            continue
        if cell["resource"] == "gold":
            resource_weight = 1.0
        elif not settings.iron_enabled:
            continue
        elif observation["bank"]["iron"] < observation["constants"]["base_cost_iron"] and observation["turn"] < 60:
            resource_weight = settings.early_iron_weight
        else:
            resource_weight = settings.late_iron_weight
        return_distance = home.get(point, inf)
        elapsed = distances[point] + ceil(units / observation["constants"]["mine_rate"]) + return_distance + 1
        value = units * resource_weight / elapsed
        if point == prior_target:
            value *= settings.persistence_bonus
        if any(abs(point[0] - x) + abs(point[1] - y) < distances[point] for x, y in enemy_points):
            value *= settings.visible_enemy_penalty
        candidates.append((value, "resource", point, first_moves.get(point), ()))
    reachable_frontiers = [(point, unseen, distances[point]) for point, unseen in frontiers
                           if point in distances]
    # Both variants have the same resource-versus-exploration trigger. Only the
    # ordering of destinations changes, which isolates frontier selection.
    frontier_bid = max((settings.exploration_weight * unseen / (distance + 2)
                        for _, unseen, distance in reachable_frontiers), default=0)
    for point, unseen in frontiers:
        if point in distances and frontier_bid > 0:
            distance = distances[point]
            if settings.frontier_policy == "nearest":
                preference = (distance, -unseen, point)
            else:
                preference = (-unseen / (distance + 1), distance, point)
            candidates.append((frontier_bid, "explore", point, first_moves.get(point), preference))
    return candidates


def construction_reason(observation: dict, rover: dict, cells: dict[Point, dict],
                        settings: StrategySettings, ignore_bank: bool = False) -> str:
    """Audit the current rover location, not hypothetical future build sites."""
    if not settings.build_enabled:
        return "disabled"
    if not ignore_bank and observation["bank"]["iron"] < observation["constants"]["base_cost_iron"]:
        return "insufficient_iron"
    if settings.build_policy == "heuristic" and observation["turn"] > 65:
        return "turn_cutoff"
    point = (rover["x"], rover["y"])
    bases = [(base["x"], base["y"]) for base in observation["bases"]]
    occupied = bases + [(base["x"], base["y"]) for base in observation["enemies"]["bases"]]
    if point in occupied:
        return "occupied_tile"
    if settings.build_policy == "payback":
        from_site, _ = bfs(point, cells)
        old_home = home_distances(observation["bases"], cells)
        capacity = observation["constants"]["cargo_capacity"]
        rate = observation["constants"]["mine_rate"]
        saved_turns = 0
        deliverable = False
        for target, cell in cells.items():
            if cell["resource"] != "gold" or cell["quantity"] <= 0:
                continue
            new_distance, old_distance = from_site.get(target, inf), old_home.get(target, inf)
            mining = ceil(min(cell["quantity"], capacity) / rate)
            if 1 + new_distance + mining + new_distance + 1 > remaining_turns(observation):
                continue
            deliverable = True
            if old_distance < inf:
                saved_turns += max(0, old_distance - new_distance)
        if not deliverable:
            return "horizon_rejected"
        # A conservative proxy: eight iron mining turns plus the build action.
        return "eligible" if saved_turns >= ceil(observation["constants"]["base_cost_iron"] / rate) + 1 else "payback_rejected"
    if min(abs(base[0] - point[0]) + abs(base[1] - point[1]) for base in bases) < 4:
        return "site_too_close"
    nearby_gold = sum(min(cell["quantity"], 5) for target, cell in cells.items()
                      if cell["resource"] == "gold" and cell["quantity"] > 0
                      and abs(point[0] - target[0]) + abs(point[1] - target[1]) <= 3
                      and min(abs(base[0] - target[0]) + abs(base[1] - target[1]) for base in bases) >= 5)
    if nearby_gold < 10:
        return "heuristic_gold_threshold"
    if settings.endgame_enabled:
        time_left = remaining_turns(observation) - 1  # BUILD consumes this turn.
        from_site, _ = bfs(point, cells)
        if not any(cell["resource"] == "gold" and cell["quantity"] > 0 and
                   (distance := from_site.get(target, inf)) + 1 + distance + 1 <= time_left
                   for target, cell in cells.items()):
            return "horizon_rejected"
    return "eligible"


class CoordinatedGreedy:
    """Assign one rover per high-value task; favor useful return and new bases."""

    def __init__(self, settings: StrategySettings | None = None) -> None:
        self.settings = settings or StrategySettings()
        self.targets: dict[str, Point] = {}
        self.diagnostic_targets: dict[str, Point] = {}

    def _should_build(self, observation: dict, rover: dict, cells: dict[Point, dict]) -> bool:
        return construction_reason(observation, rover, cells, self.settings) == "eligible"

    def decide(self, observation: dict) -> list[dict]:
        self.diagnostic_targets = {}
        cells = known_cells(observation)
        frontiers = exploration_targets(observation, cells)
        capacity = observation["constants"]["cargo_capacity"]
        assigned: dict[str, dict] = {}
        free = []
        build_budget = observation["bank"]["iron"]
        claimed_bases: set[Point] = set()
        for rover in observation["rovers"]:
            rover_id = rover["id"]
            point = (rover["x"], rover["y"])
            base, home_distance, base_move = shortest_base(rover, observation["bases"], cells)
            cargo = sum(rover["cargo"].values())
            if cargo and point == base:
                assigned[rover_id] = simple(rover_id, "DEPOSIT")
            elif self.settings.endgame_enabled and cargo and home_distance + 1 > remaining_turns(observation):
                assigned[rover_id] = simple(rover_id, "WAIT")
            elif cargo >= capacity or (self.settings.endgame_enabled and rover["cargo"]["gold"] and
                                       home_distance + 1 >= remaining_turns(observation)):
                assigned[rover_id] = move(rover_id, base_move)
                self.diagnostic_targets[rover_id] = base
            elif (self.settings.build_enabled and build_budget >= observation["constants"]["base_cost_iron"] and
                  point not in claimed_bases and self._should_build(observation, rover, cells)):
                assigned[rover_id] = simple(rover_id, "BUILD")
                build_budget -= observation["constants"]["base_cost_iron"]
                claimed_bases.add(point)
            else:
                free.append(rover)

        free_by_id = {rover["id"]: rover for rover in free}
        bids = []
        for rover in free:
            for value, kind, point, first_move, preference in task_candidates(
                    observation, rover, cells, frontiers, self.targets.get(rover["id"]), self.settings):
                bids.append((-value, rover["id"], kind, preference, point, first_move))
        bids.sort(key=lambda bid: (bid[0], bid[1], bid[2], bid[3], bid[4]))
        used_tasks: set[Point] = set()
        for _, rover_id, kind, _, point, first_move in bids:
            if rover_id in assigned or (self.settings.coordinate and point in used_tasks):
                continue
            rover = free_by_id[rover_id]
            assigned[rover_id] = (simple(rover_id, "MINE") if kind == "resource" and
                                  (rover["x"], rover["y"]) == point
                                  else move(rover_id, first_move))
            self.targets[rover_id] = point
            self.diagnostic_targets[rover_id] = point
            if self.settings.coordinate:
                used_tasks.add(point)
        for rover in free:
            if rover["id"] not in assigned:
                _, _, base_move = shortest_base(rover, observation["bases"], cells)
                assigned[rover["id"]] = move(rover["id"], base_move) if sum(rover["cargo"].values()) else simple(rover["id"], "WAIT")
                self.targets.pop(rover["id"], None)
        actions = [assigned[rover["id"]] for rover in observation["rovers"]]
        if self.settings.endgame_enabled:
            for index, rover in enumerate(observation["rovers"]):
                actions[index], override = protect_scored_cargo(
                    observation, rover, actions[index], cells, observation["bases"])
                if override is not None:
                    self.diagnostic_targets[rover["id"]] = override
        return actions
