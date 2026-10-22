"""Objective match telemetry from submissions, normalized actions, events, and state."""

from __future__ import annotations

from collections import Counter
from typing import Any

from mini_mars.bots.strategies import StrategySettings, construction_reason, known_cells
from mini_mars.engine.game import Game


class MatchMetrics:
    def __init__(self, game: Game, bot_specs: tuple[str, str]) -> None:
        self.game = game
        self.bot_specs = bot_specs
        self.submitted = [Counter(), Counter()]
        self.normalized = [Counter(), Counter()]
        self.effect = [Counter(), Counter()]
        self.economy = [Counter(), Counter()]
        self.build_audit = [Counter(), Counter()]
        self.site_audit = [Counter(), Counter()]
        self.discovered = [set(), set()]
        self._reveal()

    def _reveal(self) -> None:
        for player, colony in enumerate(self.game.colonies):
            self.discovered[player].update(point for point, cell in colony.known.items()
                                           if cell["resource"] in ("gold", "iron"))

    def record(self, observations: list[dict], responses: list[Any], actions: dict[str, dict],
               events: list[dict], before: dict[str, tuple[int, int]]) -> None:
        for player, response in enumerate(responses):
            if isinstance(response, dict) and isinstance(response.get("actions"), list):
                for action in response["actions"]:
                    kind = action.get("type") if isinstance(action, dict) else None
                    self.submitted[player][kind if isinstance(kind, str) else "<malformed>"] += 1
            spec = self.bot_specs[player]
            if spec in {"coordinated", "independent", "coordinated-nearest",
                        "coordinated-no-endgame", "coordinated-no-explore",
                        "coordinated-payback-build"}:
                settings = StrategySettings(endgame_enabled=spec != "coordinated-no-endgame",
                                            build_policy="payback" if spec == "coordinated-payback-build"
                                            else "heuristic")
                cells = known_cells(observations[player])
                for rover in observations[player]["rovers"]:
                    reason = construction_reason(observations[player], rover, cells, settings)
                    self.build_audit[player][reason] += 1
                    site = construction_reason(observations[player], rover, cells, settings,
                                               ignore_bank=True)
                    self.site_audit[player][site] += 1
                    if reason == "eligible" and actions[rover["id"]]["type"] != "BUILD":
                        self.build_audit[player]["eligible_not_submitted"] += 1

        effected: set[str] = set()
        for rover_id, action in actions.items():
            player = self.game.rovers[rover_id].player
            kind = action["type"]
            self.normalized[player][kind] += 1
            if kind == "MOVE" and before[rover_id] != self.game.rovers[rover_id].position:
                self.effect[player]["MOVE"] += 1
                effected.add(rover_id)
        for event in events:
            kind = event["type"]
            if kind in {"mine", "deposit", "build"}:
                rover_id = event.get("rover_id")
                player = self.game.rovers[rover_id].player if rover_id else event["player"]
                action_kind = kind.upper()
                self.effect[player][action_kind] += 1
                if rover_id:
                    effected.add(rover_id)
                elif kind == "build":
                    builder = next((identity for identity, action in actions.items()
                                    if action["type"] == "BUILD" and identity not in effected
                                    and self.game.rovers[identity].player == player
                                    and self.game.rovers[identity].position == (event["x"], event["y"])), None)
                    if builder is not None:
                        effected.add(builder)
                if kind == "mine":
                    self.economy[player][f'{event["resource"]}_mined'] += event["quantity"]
                elif kind == "deposit":
                    for resource in ("gold", "iron"):
                        self.economy[player][f"{resource}_deposited"] += event[resource]
                else:
                    self.economy[player]["iron_spent_on_bases"] += self.game.config.base_cost_iron
                    self.economy[player]["bases_built"] += 1
        for rover_id in actions:
            if rover_id not in effected:
                self.economy[self.game.rovers[rover_id].player]["no_effect_rover_turns"] += 1
        self._reveal()

    def report(self) -> list[dict]:
        results = []
        for player, colony in enumerate(self.game.colonies):
            cargo = {resource: sum(getattr(rover, resource) for rover in self.game.rovers.values()
                                   if rover.player == player) for resource in ("gold", "iron")}
            economy = {name: self.economy[player][name] for name in (
                "gold_mined", "gold_deposited", "iron_mined", "iron_deposited",
                "iron_spent_on_bases", "bases_built", "no_effect_rover_turns")}
            economy["gold_in_cargo_at_end"] = cargo["gold"]
            economy["iron_in_cargo_at_end"] = cargo["iron"]
            results.append({
                "economy": economy,
                "actions": {
                    "submitted": dict(sorted(self.submitted[player].items())),
                    "normalized": dict(sorted(self.normalized[player].items())),
                    "effect": dict(sorted(self.effect[player].items())),
                },
                "exploration": {
                    "unique_tiles_revealed": len(colony.known),
                    "map_explored_percent": 100 * len(colony.known) / (self.game.config.width * self.game.config.height),
                    "resource_deposits_discovered": len(self.discovered[player]),
                },
                "construction_audit": dict(sorted(self.build_audit[player].items())),
                "site_audit_ignoring_iron": dict(sorted(self.site_audit[player].items())),
            })
        return results
