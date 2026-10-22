"""Small strategies with replaceable path and task-selection functions."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
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
        return start, 0, None
    point, distance = min(options, key=lambda item: (item[1], item[0]))
    return point, distance, first_moves.get(point)


def move(rover_id: str, direction: str | None) -> dict:
    return {"rover_id": rover_id, "type": "MOVE", "direction": direction} if direction else {
        "rover_id": rover_id, "type": "WAIT"}


def simple(rover_id: str, kind: str) -> dict:
    return {"rover_id": rover_id, "type": kind}


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

    def deposit_rank(self, point: Point, cell: dict, distance: int,
                     rover: dict, bases: list[dict], capacity: int) -> tuple:
        return (0 if cell["resource"] == "gold" else 1, distance, point)

    def decide(self, observation: dict) -> list[dict]:
        cells = known_cells(observation)
        deposits = [(point, cell) for point, cell in cells.items()
                    if cell["terrain"] == "plain" and cell["quantity"] > 0 and cell["resource"]]
        frontiers = exploration_targets(observation, cells)
        capacity = observation["constants"]["cargo_capacity"]
        bases = observation["bases"]
        actions = []
        for rover in observation["rovers"]:
            rover_id = rover["id"]
            cargo = sum(rover["cargo"].values())
            base, _, base_move = shortest_base(rover, bases, cells)
            start = (rover["x"], rover["y"])
            if cargo and start == base:
                actions.append(simple(rover_id, "DEPOSIT"))
                continue
            if cargo >= capacity:
                actions.append(move(rover_id, base_move))
                continue
            distances, first_moves = bfs(start, cells)
            reachable = [(self.deposit_rank(point, cell, distances[point], rover, bases, capacity), point)
                         for point, cell in deposits if point in distances]
            if reachable:
                _, target = min(reachable)
                actions.append(simple(rover_id, "MINE") if target == start
                               else move(rover_id, first_moves[target]))
            elif cargo:
                actions.append(move(rover_id, base_move))
            else:
                targets = [(distances[point], -unseen, point) for point, unseen in frontiers if point in distances]
                target = min(targets)[2] if targets else None
                actions.append(move(rover_id, first_moves.get(target)))
        return actions


class ValueGreedy(GreedyMiner):
    """Keep greedy's choices, but rank same-resource deposits by useful units per turn."""

    def deposit_rank(self, point: Point, cell: dict, distance: int,
                     rover: dict, bases: list[dict], capacity: int) -> tuple:
        units = min(cell["quantity"], capacity - sum(rover["cargo"].values()))
        return_distance = min(abs(point[0] - base["x"]) + abs(point[1] - base["y"])
                              for base in bases)
        value = units / (distance + units + return_distance + 1)
        return (0 if cell["resource"] == "gold" else 1, -value, point)


@dataclass(frozen=True)
class StrategySettings:
    """Fixed experiment switches; all variants share the same path and bid code."""

    coordinate: bool = True
    exploration_weight: float = 0.24
    persistence_bonus: float = 1.2
    iron_enabled: bool = True
    build_enabled: bool = True
    early_iron_weight: float = 0.65
    late_iron_weight: float = 0.05
    visible_enemy_penalty: float = 0.8


def task_candidates(observation: dict, rover: dict, cells: dict[Point, dict],
                    frontiers: list[tuple[Point, int]], prior_target: Point | None,
                    settings: StrategySettings) -> list[tuple[float, str, Point, str | None]]:
    """Rank useful deposits and scouting cells by estimated reward per turn."""
    start = (rover["x"], rover["y"])
    distances, first_moves = bfs(start, cells)
    capacity = observation["constants"]["cargo_capacity"] - sum(rover["cargo"].values())
    bases = [(base["x"], base["y"]) for base in observation["bases"]]
    enemy_points = [(enemy["x"], enemy["y"]) for enemy in observation["enemies"]["rovers"]]
    candidates = []
    for point, cell in cells.items():
        if point not in distances or cell["terrain"] != "plain" or cell["quantity"] <= 0 or not cell["resource"]:
            continue
        units = min(capacity, cell["quantity"])
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
        return_distance = min(abs(point[0] - base[0]) + abs(point[1] - base[1]) for base in bases)
        elapsed = distances[point] + units + return_distance + 1
        value = units * resource_weight / elapsed
        if point == prior_target:
            value *= settings.persistence_bonus
        if any(abs(point[0] - x) + abs(point[1] - y) < distances[point] for x, y in enemy_points):
            value *= settings.visible_enemy_penalty
        candidates.append((value, "resource", point, first_moves.get(point)))
    for point, unseen in frontiers:
        if point in distances and settings.exploration_weight > 0:
            value = settings.exploration_weight * unseen / (distances[point] + 2)
            if point == prior_target:
                value *= settings.persistence_bonus
            candidates.append((value, "explore", point, first_moves.get(point)))
    return candidates


class CoordinatedGreedy:
    """Assign one rover per high-value task; favor useful return and new bases."""

    def __init__(self, settings: StrategySettings | None = None) -> None:
        self.settings = settings or StrategySettings()
        self.targets: dict[str, Point] = {}

    def _should_build(self, observation: dict, rover: dict, cells: dict[Point, dict]) -> bool:
        if observation["bank"]["iron"] < observation["constants"]["base_cost_iron"] or observation["turn"] > 65:
            return False
        point = (rover["x"], rover["y"])
        bases = [(base["x"], base["y"]) for base in observation["bases"]]
        occupied = bases + [(base["x"], base["y"]) for base in observation["enemies"]["bases"]]
        if point in occupied:
            return False
        nearby_gold = sum(min(cell["quantity"], 5) for target, cell in cells.items()
                          if cell["resource"] == "gold" and cell["quantity"] > 0
                          and abs(point[0] - target[0]) + abs(point[1] - target[1]) <= 3
                          and min(abs(base[0] - target[0]) + abs(base[1] - target[1]) for base in bases) >= 5)
        return nearby_gold >= 10 and min(abs(base[0] - point[0]) + abs(base[1] - point[1]) for base in bases) >= 4

    def decide(self, observation: dict) -> list[dict]:
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
            base, _, base_move = shortest_base(rover, observation["bases"], cells)
            cargo = sum(rover["cargo"].values())
            if cargo and point == base:
                assigned[rover_id] = simple(rover_id, "DEPOSIT")
            elif cargo >= capacity:
                assigned[rover_id] = move(rover_id, base_move)
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
            for value, kind, point, first_move in task_candidates(
                    observation, rover, cells, frontiers, self.targets.get(rover["id"]), self.settings):
                bids.append((-value, rover["id"], kind, point, first_move))
        bids.sort(key=lambda bid: (bid[0], bid[1], bid[2], bid[3]))
        used_tasks: set[Point] = set()
        for _, rover_id, kind, point, first_move in bids:
            if rover_id in assigned or (self.settings.coordinate and point in used_tasks):
                continue
            rover = free_by_id[rover_id]
            assigned[rover_id] = (simple(rover_id, "MINE") if kind == "resource" and
                                  (rover["x"], rover["y"]) == point
                                  else move(rover_id, first_move))
            self.targets[rover_id] = point
            if self.settings.coordinate:
                used_tasks.add(point)
        for rover in free:
            if rover["id"] not in assigned:
                _, _, base_move = shortest_base(rover, observation["bases"], cells)
                assigned[rover["id"]] = move(rover["id"], base_move) if sum(rover["cargo"].values()) else simple(rover["id"], "WAIT")
                self.targets.pop(rover["id"], None)
        return [assigned[rover["id"]] for rover in observation["rovers"]]
