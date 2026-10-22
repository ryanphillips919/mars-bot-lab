"""Conservative, replay-oriented rover stall warnings; never changes actions."""

from __future__ import annotations

from collections import Counter, defaultdict, deque
from math import inf

from mini_mars.bots.strategies import bfs, known_cells


class MovementMonitor:
    def __init__(self, window: int = 8) -> None:
        if window < 6:
            raise ValueError("movement window must be at least six turns")
        self.window = window
        self.history = defaultdict(lambda: deque(maxlen=window))
        self.last_warning: dict[tuple[str, str], int] = {}
        self.counts = [Counter(), Counter()]
        self.warnings: list[dict] = []

    def record(self, game, observations: list[dict], responses: list[dict],
               actions: dict[str, dict], events: list[dict], before: dict) -> None:
        event_rovers = {event["rover_id"] for event in events
                        if event["type"] in {"mine", "deposit"} and "rover_id" in event}
        event_rovers.update(rover_id for rover_id, action in actions.items()
                            if action["type"] == "BUILD" and any(
                                event["type"] == "build" and event["player"] == game.rovers[rover_id].player
                                and (event["x"], event["y"]) == before[rover_id] for event in events))
        for rover_id, action in actions.items():
            rover = game.rovers[rover_id]
            player = rover.player
            pos = rover.position
            old_known = known_cells(observations[player])
            new_known = game.colonies[player].known
            radius = game.config.vision_radius
            newly_seen = any(point not in old_known and abs(point[0] - pos[0]) + abs(point[1] - pos[1]) <= radius
                             for point in new_known)
            response = responses[player]
            raw_target = response.get("targets", {}).get(rover_id) if isinstance(response, dict) and isinstance(response.get("targets", {}), dict) else None
            target = tuple(raw_target) if isinstance(raw_target, list) and len(raw_target) == 2 and all(isinstance(n, int) for n in raw_target) else None
            history = self.history[rover_id]
            prior_target = history[-1]["target"] if history else None
            distance_before = distance_after = inf
            if target is not None:
                distance_before = bfs(before[rover_id], new_known)[0].get(target, inf)
                distance_after = bfs(pos, new_known)[0].get(target, inf)
            progress = (rover_id in event_rovers or newly_seen or
                        (target is not None and target == prior_target and distance_after < distance_before))
            history.append({"turn": game.turn - 1, "before": before[rover_id], "position": pos,
                            "action": action["type"], "target": target, "progress": progress,
                            "unreachable": target is not None and distance_after == inf})
            if len(history) < self.window or any(item["progress"] for item in history):
                continue
            recent = list(history)
            positions = [item["position"] for item in recent]
            moves = sum(item["action"] == "MOVE" for item in recent)
            changes = sum(recent[i]["target"] != recent[i - 1]["target"]
                          and recent[i]["target"] is not None and recent[i - 1]["target"] is not None
                          for i in range(1, len(recent)))
            reasons = []
            if moves >= 6 and len(set(positions)) == 2 and all(positions[i] == positions[i - 2]
                                                               for i in range(2, len(positions))):
                reasons.append("back_and_forth")
            elif moves >= 6 and len(set(positions)) <= 3:
                reasons.append("small_tile_cycle")
            # A long, non-repeating path can retarget as new information arrives;
            # warn about switching only when it also revisits a tile.
            if changes >= 4 and len(set(positions)) < len(positions):
                reasons.append("goal_switching")
            if (target is not None and all(item["target"] == target and item["unreachable"] for item in recent[-4:])
                    and moves >= 4):
                reasons.append("unreachable_target")
            for reason in reasons:
                key = (rover_id, reason)
                if game.turn - self.last_warning.get(key, -self.window) < self.window:
                    continue
                self.last_warning[key] = game.turn
                self.counts[player][reason] += 1
                self.warnings.append({"player": player, "rover_id": rover_id,
                                      "turn_start": recent[0]["turn"], "turn_end": recent[-1]["turn"],
                                      "reason": reason, "recent_positions": [list(recent[0]["before"])] +
                                      [list(point) for point in positions],
                                      "recent_actions": [item["action"] for item in recent],
                                      "current_target": list(target) if target else None})

    def report(self) -> list[dict[str, int]]:
        return [dict(sorted(counts.items())) for counts in self.counts]
