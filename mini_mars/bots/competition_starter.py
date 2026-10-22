"""Small Mini Mars scoring bot; adapt the marked rules and I/O for Lucid.

Run directly with ``python3 -m mini_mars.bots.competition_starter`` or use the
``starter`` runner alias. No advanced bid, construction, or opponent model.
"""

from __future__ import annotations

from collections import deque
import json
import sys


DIRS = (("N", 0, -1), ("S", 0, 1), ("E", 1, 0), ("W", -1, 0))


def paths(start: tuple[int, int], passable: set[tuple[int, int]]):
    """Known-grid BFS, O(V + E); replace with the real game's movement graph."""
    distance, first = {start: 0}, {}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for direction, dx, dy in DIRS:
            point = (x + dx, y + dy)
            if point in passable and point not in distance:
                distance[point] = distance[(x, y)] + 1
                first[point] = first.get((x, y), direction)
                queue.append(point)
    return distance, first


def action(rover_id: str, kind: str, direction: str | None = None) -> dict:
    result = {"rover_id": rover_id, "type": kind}
    if kind == "MOVE":
        result["direction"] = direction
    return result


class StarterBot:
    """Bank gold, preserve the return deadline, then scout for reachable work."""

    def __init__(self) -> None:
        self.targets: dict[str, tuple[str, tuple[int, int]]] = {}
        self.diagnostic_targets: dict[str, tuple[int, int]] = {}

    def decide(self, obs: dict) -> list[dict]:
        # Replace these Mini Mars field names and scoring assumptions at Lucid.
        cells = {(cell["x"], cell["y"]): cell for cell in obs["cells"]}
        passable = {point for point, cell in cells.items() if cell["terrain"] == "plain"}
        bases = {(base["x"], base["y"]) for base in obs["bases"]}
        gold = {point: cell["quantity"] for point, cell in cells.items()
                if point in passable and cell["resource"] == "gold" and cell["quantity"] > 0}
        capacity = obs["constants"]["cargo_capacity"]
        left = obs["constants"]["turns"] - obs["turn"]
        radius = obs["constants"]["vision_radius"]
        width, height = obs["width"], obs["height"]
        home = {}
        for base in bases:
            distances, _ = paths(base, passable)
            for point, distance in distances.items():
                home[point] = min(home.get(point, float("inf")), distance)
        reserved = set()
        results = []
        self.diagnostic_targets = {}
        for rover in obs["rovers"]:
            rid = rover["id"]
            here = (rover["x"], rover["y"])
            load = sum(rover["cargo"].values())
            carried_gold = rover["cargo"]["gold"]
            distance, first = paths(here, passable)
            reachable_bases = [base for base in bases if base in distance]
            base = min(reachable_bases, key=lambda point: (distance[point], point)) if reachable_bases else None
            to_base = distance[base] if base is not None else float("inf")

            if load and here in bases:
                chosen = action(rid, "DEPOSIT")
                self.targets.pop(rid, None)
            elif carried_gold and to_base + 1 >= left:
                chosen = action(rid, "MOVE", first.get(base)) if to_base + 1 <= left and base != here else action(rid, "WAIT")
                if base is not None:
                    self.diagnostic_targets[rid] = base
            elif gold.get(here, 0) and load < capacity and home.get(here, float("inf")) + 2 <= left:
                chosen = action(rid, "MINE")
                self.targets[rid] = ("gold", here)
                reserved.add(here)
                self.diagnostic_targets[rid] = here
            else:
                prior = self.targets.get(rid)
                target = prior[1] if load < capacity and prior and prior[0] == "gold" and prior[1] in gold and prior[1] in distance and prior[1] not in reserved and distance[prior[1]] + home.get(prior[1], float("inf")) + 2 <= left else None
                if target is None:
                    choices = [point for point in gold if load < capacity and point in distance and point not in reserved
                               and distance[point] + home.get(point, float("inf")) + 2 <= left]
                    target = min(choices, key=lambda point: (distance[point], -gold[point], point)) if choices else None
                if target is not None:
                    self.targets[rid] = ("gold", target)
                    reserved.add(target)
                    chosen = action(rid, "MOVE", first[target])
                    self.diagnostic_targets[rid] = target
                elif load and base is not None:
                    chosen = action(rid, "MOVE", first.get(base))
                    self.targets.pop(rid, None)
                    self.diagnostic_targets[rid] = base
                else:
                    frontier = self._frontier(prior, here, distance, set(cells), width, height, radius)
                    if frontier is not None and frontier != here:
                        self.targets[rid] = ("frontier", frontier)
                        self.diagnostic_targets[rid] = frontier
                        chosen = action(rid, "MOVE", first[frontier])
                    else:
                        self.targets.pop(rid, None)
                        chosen = action(rid, "WAIT")

            # Recheck the selected action, including its post-move position.
            # Mini Mars scores only deposited gold, and DEPOSIT costs one turn.
            if carried_gold and chosen["type"] != "DEPOSIT" and to_base + 1 <= left:
                next_point = here
                if chosen["type"] == "MOVE":
                    delta = next(((dx, dy) for name, dx, dy in DIRS if name == chosen["direction"]), (0, 0))
                    next_point = (here[0] + delta[0], here[1] + delta[1])
                if home.get(next_point, float("inf")) + 1 > left - 1:
                    chosen = action(rid, "MOVE", first.get(base))
                    self.diagnostic_targets[rid] = base

            results.append(self._legal_or_wait(chosen, rid, here, passable, gold, bases, load, capacity))
        return results

    @staticmethod
    def _frontier(prior, here, distance, known, width, height, radius):
        def unknown(point):
            x, y = point
            return sum((nx, ny) not in known for dx in range(-radius, radius + 1)
                       for dy in range(-radius + abs(dx), radius - abs(dx) + 1)
                       if 0 <= (nx := x + dx) < width and 0 <= (ny := y + dy) < height)
        if prior and prior[0] == "frontier" and prior[1] in distance and prior[1] != here and unknown(prior[1]):
            return prior[1]
        candidates = [point for point in distance if point != here and unknown(point)]
        return min(candidates, key=lambda point: (distance[point], -unknown(point), point)) if candidates else None

    @staticmethod
    def _legal_or_wait(chosen, rid, here, passable, gold, bases, load, capacity):
        kind = chosen["type"]
        if kind == "MOVE":
            delta = next(((dx, dy) for name, dx, dy in DIRS if name == chosen.get("direction")), None)
            valid = delta is not None and (here[0] + delta[0], here[1] + delta[1]) in passable
        elif kind == "MINE":
            valid = gold.get(here, 0) > 0 and load < capacity
        elif kind == "DEPOSIT":
            valid = here in bases and load > 0
        else:
            valid = kind == "WAIT"
        return chosen if valid else action(rid, "WAIT")


def main() -> None:
    bot = StarterBot()
    for line in sys.stdin:
        obs = None
        try:
            obs = json.loads(line)
            if not isinstance(obs, dict):
                raise ValueError("observation must be an object")
            response = {"turn": obs["turn"], "actions": bot.decide(obs)}
            if bot.diagnostic_targets:
                response["targets"] = {rid: list(point) for rid, point in bot.diagnostic_targets.items()}
        except Exception as error:
            print(f"starter input error: {error}", file=sys.stderr, flush=True)
            turn = obs.get("turn", -1) if isinstance(obs, dict) else -1
            rovers = obs.get("rovers") if isinstance(obs, dict) else None
            if not isinstance(rovers, list):
                rovers = []
            response = {"turn": turn, "actions": [action(rover["id"], "WAIT") for rover in rovers
                                                    if isinstance(rover, dict) and isinstance(rover.get("id"), str)],
                        "bot_error": type(error).__name__}
        print(json.dumps(response, separators=(",", ":")), flush=True)


if __name__ == "__main__":
    main()
