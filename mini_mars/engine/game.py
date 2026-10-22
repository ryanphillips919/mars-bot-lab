"""Mini Mars rules. No bot strategy or subprocess code lives here."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import random
from typing import Any


Point = tuple[int, int]
DIRECTIONS: dict[str, Point] = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}
ACTIONS = {"MOVE", "MINE", "DEPOSIT", "BUILD", "WAIT"}


@dataclass(frozen=True)
class Config:
    width: int = 15
    height: int = 15
    turns: int = 100
    starting_rovers: int = 3
    cargo_capacity: int = 5
    mine_rate: int = 1
    base_cost_iron: int = 8
    vision_radius: int = 2
    rock_pairs: int = 8
    gold_pairs: int = 9
    iron_pairs: int = 6
    deposit_min: int = 5
    deposit_max: int = 12
    full_information: bool = False

    def __post_init__(self) -> None:
        if self.width < 7 or self.height < 7 or self.turns < 1 or self.starting_rovers < 1:
            raise ValueError("map dimensions must be at least 7 and turns/rovers positive")
        if min(self.cargo_capacity, self.mine_rate, self.base_cost_iron, self.vision_radius,
               self.deposit_min) < 1 or self.deposit_max < self.deposit_min:
            raise ValueError("resource and vision constants must be positive")
        if self.mine_rate > self.cargo_capacity:
            raise ValueError("mine rate cannot exceed rover capacity")
        if min(self.rock_pairs, self.gold_pairs, self.iron_pairs) < 0:
            raise ValueError("map feature counts cannot be negative")

    def public(self) -> dict[str, int]:
        return {key: getattr(self, key) for key in (
            "width", "height", "turns", "starting_rovers", "cargo_capacity",
            "mine_rate", "base_cost_iron", "vision_radius")}


@dataclass
class Cell:
    terrain: str = "plain"
    resource: str | None = None
    quantity: int = 0


@dataclass
class Rover:
    id: str
    player: int
    x: int
    y: int
    iron: int = 0
    gold: int = 0

    @property
    def position(self) -> Point:
        return self.x, self.y

    @property
    def load(self) -> int:
        return self.iron + self.gold

    def public(self) -> dict[str, Any]:
        return {"id": self.id, "x": self.x, "y": self.y,
                "cargo": {"iron": self.iron, "gold": self.gold}}


@dataclass
class Colony:
    id: int
    bases: list[Point]
    iron: int = 0
    gold: int = 0
    known: dict[Point, dict[str, Any]] = field(default_factory=dict)
    visible: set[Point] = field(default_factory=set)


@dataclass
class Game:
    config: Config
    seed: int
    cells: list[list[Cell]]
    colonies: list[Colony]
    rovers: dict[str, Rover]
    turn: int = 0

    def cell(self, point: Point) -> Cell:
        return self.cells[point[1]][point[0]]

    def in_bounds(self, point: Point) -> bool:
        return 0 <= point[0] < self.config.width and 0 <= point[1] < self.config.height

    def traversable(self, point: Point) -> bool:
        return self.in_bounds(point) and self.cell(point).terrain == "plain"


def neighbors(point: Point, width: int, height: int) -> list[Point]:
    x, y = point
    return [(nx, ny) for dx, dy in DIRECTIONS.values()
            if 0 <= (nx := x + dx) < width and 0 <= (ny := y + dy) < height]


def reachable(start: Point, cells: list[list[Cell]]) -> set[Point]:
    height, width = len(cells), len(cells[0])
    found = {start}
    queue = deque([start])
    while queue:
        for point in neighbors(queue.popleft(), width, height):
            if point not in found and cells[point[1]][point[0]].terrain == "plain":
                found.add(point)
                queue.append(point)
    return found


def make_game(seed: int, config: Config | None = None) -> Game:
    config = config or Config()
    rng = random.Random(seed)
    width, height = config.width, config.height
    homes = [(1, 1), (width - 2, height - 2)]
    reserved = {(x, y) for x in range(width) for y in range(height)
                if any(abs(x - bx) + abs(y - by) <= 2 for bx, by in homes)}
    pairs = []
    for y in range(height):
        for x in range(width):
            point = (x, y)
            mirror = (width - 1 - x, height - 1 - y)
            if point < mirror and point not in reserved and mirror not in reserved:
                pairs.append((point, mirror))
    needed = config.rock_pairs + config.gold_pairs + config.iron_pairs
    if needed > len(pairs):
        raise ValueError("too many map features for this map size")

    for _ in range(1000):
        chosen_rocks = rng.sample(pairs, config.rock_pairs)
        cells = [[Cell() for _ in range(width)] for _ in range(height)]
        for pair in chosen_rocks:
            for x, y in pair:
                cells[y][x].terrain = "rock"
        if len(reachable(homes[0], cells)) == width * height - 2 * config.rock_pairs:
            break
    else:
        raise ValueError("could not generate a connected map")

    available = [pair for pair in pairs if pair not in chosen_rocks]
    if config.gold_pairs + config.iron_pairs > len(available):
        raise ValueError("not enough open tiles for deposits")
    for kind, count in (("gold", config.gold_pairs), ("iron", config.iron_pairs)):
        selected = rng.sample(available, count)
        for pair in selected:
            available.remove(pair)
            quantity = rng.randint(config.deposit_min, config.deposit_max)
            for x, y in pair:
                cells[y][x].resource = kind
                cells[y][x].quantity = quantity

    colonies = [Colony(id=player, bases=[home]) for player, home in enumerate(homes)]
    rovers = {f"p{player}-r{index}": Rover(f"p{player}-r{index}", player, *home)
              for player, home in enumerate(homes)
              for index in range(config.starting_rovers)}
    game = Game(config, seed, cells, colonies, rovers)
    reveal(game)
    return game


def reveal(game: Game) -> None:
    radius = game.config.vision_radius
    for colony in game.colonies:
        visible: set[Point] = set()
        if game.config.full_information:
            visible = {(x, y) for y in range(game.config.height) for x in range(game.config.width)}
        else:
            for rover in game.rovers.values():
                if rover.player != colony.id:
                    continue
                for dx in range(-radius, radius + 1):
                    for dy in range(-radius + abs(dx), radius - abs(dx) + 1):
                        point = (rover.x + dx, rover.y + dy)
                        if game.in_bounds(point):
                            visible.add(point)
        colony.visible = visible
        for point in visible:
            cell = game.cell(point)
            colony.known[point] = {"terrain": cell.terrain, "resource": cell.resource,
                                   "quantity": cell.quantity, "last_seen": game.turn}


def observation(game: Game, player: int) -> dict[str, Any]:
    colony = game.colonies[player]
    visible = colony.visible
    cells = [{"x": x, "y": y, **info, "visible": (x, y) in visible}
             for (x, y), info in sorted(colony.known.items(), key=lambda item: (item[0][1], item[0][0]))]
    return {
        "turn": game.turn, "player": player,
        "width": game.config.width, "height": game.config.height,
        "cells": cells,
        "rovers": [rover.public() for rover in game.rovers.values() if rover.player == player],
        "bases": [{"x": x, "y": y} for x, y in colony.bases],
        "bank": {"iron": colony.iron, "gold": colony.gold}, "score": colony.gold,
        "enemies": {
            "rovers": [{"player": rover.player, **rover.public()} for rover in game.rovers.values()
                       if rover.player != player and rover.position in visible],
            "bases": [{"player": enemy.id, "x": x, "y": y}
                      for enemy in game.colonies if enemy.id != player
                      for x, y in enemy.bases if (x, y) in visible],
        },
        "constants": game.config.public(),
    }


def _invalid(diagnostics: list[dict[str, Any]], player: int, rover_id: str | None, reason: str) -> dict[str, str]:
    diagnostics.append({"player": player, "rover_id": rover_id, "reason": reason})
    return {"type": "WAIT"}


def _normalize(game: Game, submissions: dict[int, Any], diagnostics: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    actions = {rover_id: {"type": "WAIT"} for rover_id in game.rovers}
    for player in (0, 1):
        response = submissions.get(player)
        if not isinstance(response, dict) or not isinstance(response.get("actions"), list):
            _invalid(diagnostics, player, None, "response must contain an actions list")
            continue
        if response.get("turn") != game.turn:
            _invalid(diagnostics, player, None, "response turn does not match observation")
            continue
        seen: set[str] = set()
        duplicates: set[str] = set()
        for action in response["actions"]:
            if not isinstance(action, dict) or not isinstance(action.get("rover_id"), str):
                _invalid(diagnostics, player, None, "action must identify a rover")
                continue
            rover_id = action["rover_id"]
            rover = game.rovers.get(rover_id)
            if rover is None or rover.player != player:
                _invalid(diagnostics, player, rover_id, "unknown or enemy rover")
                continue
            if rover_id in seen:
                duplicates.add(rover_id)
                actions[rover_id] = _invalid(diagnostics, player, rover_id, "duplicate rover action")
                continue
            seen.add(rover_id)
            kind = action.get("type")
            if not isinstance(kind, str) or kind not in ACTIONS:
                actions[rover_id] = _invalid(diagnostics, player, rover_id, "unknown action type")
            elif kind == "MOVE":
                direction = action.get("direction")
                if not isinstance(direction, str) or direction not in DIRECTIONS:
                    actions[rover_id] = _invalid(diagnostics, player, rover_id, "invalid move direction")
                else:
                    dx, dy = DIRECTIONS[direction]
                    if not game.traversable((rover.x + dx, rover.y + dy)):
                        actions[rover_id] = _invalid(diagnostics, player, rover_id, "move blocked by rock or map edge")
                    else:
                        actions[rover_id] = {"type": "MOVE", "direction": direction}
            elif kind == "MINE" and (rover.load >= game.config.cargo_capacity or
                                      game.cell(rover.position).quantity <= 0 or
                                      game.cell(rover.position).resource not in ("iron", "gold")):
                actions[rover_id] = _invalid(diagnostics, player, rover_id, "no mineable resource or cargo full")
            elif kind == "DEPOSIT" and rover.position not in game.colonies[player].bases:
                actions[rover_id] = _invalid(diagnostics, player, rover_id, "not at a friendly base")
            elif kind == "BUILD" and (not game.traversable(rover.position) or
                                       rover.position in [base for colony in game.colonies for base in colony.bases]
                                       or game.colonies[player].iron < game.config.base_cost_iron):
                actions[rover_id] = _invalid(diagnostics, player, rover_id, "base tile occupied or insufficient banked iron")
            else:
                actions[rover_id] = {"type": kind}
        for rover_id in duplicates:
            actions[rover_id] = {"type": "WAIT"}
    return actions


def step(game: Game, submissions: dict[int, Any],
         action_trace: dict[str, dict[str, str]] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Apply one simultaneous turn. Return events and invalid-action diagnostics."""
    if game.turn >= game.config.turns:
        raise ValueError("game has already ended")
    diagnostics: list[dict[str, Any]] = []
    actions = _normalize(game, submissions, diagnostics)
    if action_trace is not None:
        action_trace.update(actions)
    events: list[dict[str, Any]] = []

    # Every action was checked against the same pre-turn state. Stacking is allowed.
    for rover_id, action in actions.items():
        if action["type"] == "MOVE":
            rover = game.rovers[rover_id]
            dx, dy = DIRECTIONS[action["direction"]]
            rover.x += dx
            rover.y += dy

    # A contested deposit gives each winning rover one unit. Rotation avoids a
    # permanent player-0 priority for the last unit and uses no process hash seed.
    miners: dict[Point, list[Rover]] = {}
    for rover_id, action in actions.items():
        if action["type"] == "MINE":
            rover = game.rovers[rover_id]
            miners.setdefault(rover.position, []).append(rover)
    for point, contenders in sorted(miners.items()):
        contenders.sort(key=lambda rover: (rover.player, rover.id))
        offset = (game.turn + point[0] + point[1]) % len(contenders)
        contenders = contenders[offset:] + contenders[:offset]
        cell = game.cell(point)
        for rover in contenders:
            quantity = min(game.config.mine_rate, cell.quantity,
                           game.config.cargo_capacity - rover.load)
            if quantity <= 0:
                events.append({"type": "mine_contested", "rover_id": rover.id, "x": point[0], "y": point[1]})
                continue
            cell.quantity -= quantity
            setattr(rover, cell.resource, getattr(rover, cell.resource) + quantity)
            events.append({"type": "mine", "rover_id": rover.id, "resource": cell.resource,
                           "x": point[0], "y": point[1], "quantity": quantity})

    # Buildings use iron available before this turn's deposits. Player priority
    # alternates if both colonies attempt to build on the same tile.
    builders = [game.rovers[rover_id] for rover_id, action in actions.items() if action["type"] == "BUILD"]
    builders.sort(key=lambda rover: ((rover.player - game.turn) % 2, rover.id))
    for rover in builders:
        colony = game.colonies[rover.player]
        if rover.position in [base for owner in game.colonies for base in owner.bases]:
            _invalid(diagnostics, rover.player, rover.id, "base tile claimed by another build")
        elif colony.iron < game.config.base_cost_iron:
            _invalid(diagnostics, rover.player, rover.id, "banked iron reserved by another build")
        else:
            colony.iron -= game.config.base_cost_iron
            colony.bases.append(rover.position)
            events.append({"type": "build", "player": rover.player, "x": rover.x, "y": rover.y})

    for rover_id, action in actions.items():
        if action["type"] == "DEPOSIT":
            rover = game.rovers[rover_id]
            colony = game.colonies[rover.player]
            colony.iron += rover.iron
            colony.gold += rover.gold
            if rover.load:
                events.append({"type": "deposit", "rover_id": rover.id,
                               "iron": rover.iron, "gold": rover.gold})
            rover.iron = rover.gold = 0

    game.turn += 1
    reveal(game)
    return events, diagnostics


def outcome(game: Game) -> dict[str, Any]:
    scores = [colony.gold for colony in game.colonies]
    return {"scores": scores, "winner": None if scores[0] == scores[1] else scores.index(max(scores))}


def snapshot(game: Game, events: list[dict[str, Any]] | None = None,
             diagnostics: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "turn": game.turn,
        "rovers": [{"player": rover.player, **rover.public()} for rover in game.rovers.values()],
        "colonies": [{"id": colony.id, "bank": {"iron": colony.iron, "gold": colony.gold},
                      "bases": [{"x": x, "y": y} for x, y in colony.bases],
                      "known": [{"x": x, "y": y, **info, "visible": (x, y) in colony.visible}
                                for (x, y), info in sorted(colony.known.items())]}
                     for colony in game.colonies],
        "deposits": [{"x": x, "y": y, "resource": cell.resource, "quantity": cell.quantity}
                     for y, row in enumerate(game.cells) for x, cell in enumerate(row) if cell.resource],
        "events": events or [], "diagnostics": diagnostics or [],
    }


def initial_map(game: Game) -> dict[str, Any]:
    return {"rocks": [{"x": x, "y": y} for y, row in enumerate(game.cells)
                      for x, cell in enumerate(row) if cell.terrain == "rock"],
            "deposits": [{"x": x, "y": y, "resource": cell.resource, "quantity": cell.quantity}
                         for y, row in enumerate(game.cells) for x, cell in enumerate(row) if cell.resource]}
