"""Objective match telemetry from submissions, normalized actions, events, and state."""

from __future__ import annotations

from collections import Counter
from typing import Any

from mini_mars.bots.strategies import (StrategySettings, bfs, construction_reason,
                                      home_distances, known_cells)
from mini_mars.engine.game import Game


class MatchMetrics:
    def __init__(self, game: Game, bot_specs: tuple[str, str]) -> None:
        self.game = game
        self.bot_specs = bot_specs
        self.submitted = [Counter(), Counter()]
        self.normalized = [Counter(), Counter()]
        self.effect = [Counter(), Counter()]
        self.economy = [Counter(), Counter()]
        self.economic_diagnostics = [Counter(), Counter()]
        self.milestones = [{"first_gold_discovery_turn": None, "first_gold_mine_turn": None,
                            "first_gold_deposit_turn": None,
                            "first_resource_discovery_turn": None,
                            "first_resource_mine_turn": None,
                            "first_resource_deposit_turn": None} for _ in (0, 1)]
        self.ever_deliverable_gold_known = [False, False]
        self.ever_feasible_carried_gold: dict[str, bool] = {}
        self.previous_targets: list[dict[str, tuple[int, int]]] = [{}, {}]
        self.economic_idle_streak = [0, 0]
        self.longest_economic_idle_streak = [0, 0]
        self.last_opportunities: dict[str, bool] = {}
        self.build_audit = [Counter(), Counter()]
        self.base_usage = [Counter(), Counter()]
        self.base_events = [[], []]
        self.site_audit = [Counter(), Counter()]
        self.discovered = [set(), set()]
        self._reveal()

    def _reveal(self) -> None:
        for player, colony in enumerate(self.game.colonies):
            self.discovered[player].update(point for point, cell in colony.known.items()
                                           if cell["resource"] in ("gold", "iron"))
            if self.milestones[player]["first_gold_discovery_turn"] is None and any(
                    cell["resource"] == "gold" for cell in colony.known.values()):
                self.milestones[player]["first_gold_discovery_turn"] = self.game.turn
            if self.milestones[player]["first_resource_discovery_turn"] is None and any(
                    cell["resource"] in ("gold", "iron") for cell in colony.known.values()):
                self.milestones[player]["first_resource_discovery_turn"] = self.game.turn

    def record(self, observations: list[dict], responses: list[Any], actions: dict[str, dict],
               events: list[dict], before: dict[str, tuple[int, int]]) -> None:
        self.last_opportunities = {}
        for player, response in enumerate(responses):
            if isinstance(response, dict) and isinstance(response.get("actions"), list):
                for action in response["actions"]:
                    kind = action.get("type") if isinstance(action, dict) else None
                    self.submitted[player][kind if isinstance(kind, str) else "<malformed>"] += 1
            spec = self.bot_specs[player]
            if spec in {"coordinated", "independent", "coordinated-nearest",
                        "coordinated-harvest-first",
                        "coordinated-harvest-scored",
                        "coordinated-harvest-stable", "coordinated-harvest-cargo",
                        "coordinated-harvest-reliable",
                        "coordinated-stable",
                        "coordinated-frontier-scored", "coordinated-adaptive",
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

            obs = observations[player]
            cells = known_cells(obs)
            home = home_distances(obs["bases"], cells)
            new_tiles = self.game.colonies[player].known.keys() - cells.keys()
            new_gold = {point for point in new_tiles
                        if self.game.colonies[player].known[point]["resource"] == "gold"}
            targets = response.get("targets", {}) if isinstance(response, dict) else {}
            if not isinstance(targets, dict):
                targets = {}
            bases = {(base["x"], base["y"]) for base in obs["bases"]}
            resource_claims = Counter()
            for rover in obs["rovers"]:
                rid = rover["id"]
                start = before[rid]
                end = self.game.rovers[rid].position
                distance, _ = bfs(start, cells)
                free = obs["constants"]["cargo_capacity"] - sum(rover["cargo"].values())
                left = obs["constants"]["turns"] - obs["turn"]
                if not rover["cargo"]["gold"]:
                    self.ever_feasible_carried_gold.pop(rid, None)
                deliverable = free > 0 and any(
                    cell["terrain"] == "plain" and cell["resource"] == "gold" and cell["quantity"] > 0
                    and point in distance and distance[point] + home.get(point, float("inf")) + 2 <= left
                    for point, cell in cells.items())
                self.last_opportunities[rid] = deliverable
                if deliverable:
                    self.ever_deliverable_gold_known[player] = True
                    self.economic_diagnostics[player]["rover_turns_with_deliverable_gold_known"] += 1
                if (rover["cargo"]["gold"] and home.get(start, float("inf")) + 1 <= left):
                    self.ever_feasible_carried_gold[rid] = True
                raw_target = targets.get(rid)
                target = tuple(raw_target) if isinstance(raw_target, list) and len(raw_target) == 2 and all(
                    isinstance(value, int) for value in raw_target) else None
                prior = self.previous_targets[player].get(rid)
                if target is not None:
                    if prior is not None and target != prior:
                        self.economic_diagnostics[player]["target_changes"] += 1
                    self.previous_targets[player][rid] = target
                    if target in cells and cells[target]["resource"] in ("gold", "iron") and cells[target]["quantity"] > 0:
                        resource_claims[target] += 1
                else:
                    self.previous_targets[player].pop(rid, None)
                if actions[rid]["type"] != "MOVE" or start == end:
                    continue
                radius = obs["constants"]["vision_radius"]
                if any(abs(point[0] - end[0]) + abs(point[1] - end[1]) <= radius for point in new_tiles):
                    self.economic_diagnostics[player]["moves_revealing_new_tiles"] += 1
                if any(abs(point[0] - end[0]) + abs(point[1] - end[1]) <= radius for point in new_gold):
                    self.economic_diagnostics[player]["moves_revealing_new_gold"] += 1
                if rover["cargo"]["gold"] and home.get(end, float("inf")) > home.get(start, float("inf")):
                    self.economic_diagnostics[player]["moves_away_from_base_with_gold"] += 1
                if target in bases and home.get(end, float("inf")) < home.get(start, float("inf")):
                    self.economic_diagnostics[player]["moves_toward_base"] += 1
                elif target in cells and cells[target]["resource"] in ("gold", "iron") and target in distance:
                    after_distance = bfs(end, cells)[0].get(target, float("inf"))
                    if after_distance < distance[target]:
                        self.economic_diagnostics[player]["moves_toward_known_resource"] += 1
                        if cells[target]["resource"] == "gold":
                            self.economic_diagnostics[player]["moves_toward_known_gold"] += 1
                elif target is not None and deliverable:
                    self.economic_diagnostics[player]["exploration_moves_with_deliverable_gold_known"] += 1
            self.economic_diagnostics[player]["duplicate_resource_target_rover_turns"] += sum(
                count - 1 for count in resource_claims.values() if count > 1)

        effected: set[str] = set()
        economic_effect = [False, False]
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
                economic_effect[player] = True
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
                    if self.milestones[player]["first_resource_mine_turn"] is None:
                        self.milestones[player]["first_resource_mine_turn"] = observations[player]["turn"]
                    if event["resource"] == "gold" and self.milestones[player]["first_gold_mine_turn"] is None:
                        self.milestones[player]["first_gold_mine_turn"] = observations[player]["turn"]
                elif kind == "deposit":
                    deposit_point = self.game.rovers[rover_id].position
                    base_index = self.game.colonies[player].bases.index(deposit_point)
                    self.base_usage[player][f"base_{base_index}_gold"] += event["gold"]
                    self.base_usage[player][f"base_{base_index}_deliveries"] += 1
                    for resource in ("gold", "iron"):
                        self.economy[player][f"{resource}_deposited"] += event[resource]
                    if self.milestones[player]["first_resource_deposit_turn"] is None:
                        self.milestones[player]["first_resource_deposit_turn"] = observations[player]["turn"]
                    if event["gold"] and self.milestones[player]["first_gold_deposit_turn"] is None:
                        self.milestones[player]["first_gold_deposit_turn"] = observations[player]["turn"]
                else:
                    self.base_events[player].append({"turn": observations[player]["turn"],
                                                      "x": event["x"], "y": event["y"]})
                    self.economy[player]["iron_spent_on_bases"] += self.game.config.base_cost_iron
                    self.economy[player]["bases_built"] += 1
        for rover_id in actions:
            if rover_id not in effected:
                self.economy[self.game.rovers[rover_id].player]["no_effect_rover_turns"] += 1
        for player in (0, 1):
            self.economic_idle_streak[player] = 0 if economic_effect[player] else self.economic_idle_streak[player] + 1
            self.longest_economic_idle_streak[player] = max(
                self.longest_economic_idle_streak[player], self.economic_idle_streak[player])
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
            diagnostics = {name: self.economic_diagnostics[player][name] for name in (
                "rover_turns_with_deliverable_gold_known", "moves_revealing_new_tiles",
                "moves_revealing_new_gold", "moves_toward_known_gold", "moves_toward_base",
                "moves_toward_known_resource", "moves_away_from_base_with_gold",
                "exploration_moves_with_deliverable_gold_known", "target_changes",
                "duplicate_resource_target_rover_turns")}
            actions_total = sum(self.normalized[player].values())
            diagnostics["mine_or_deposit_action_percent"] = (100 * (
                self.normalized[player]["MINE"] + self.normalized[player]["DEPOSIT"]) /
                actions_total if actions_total else 0)
            diagnostics["zero_score_after_deliverable_gold_known"] = int(
                colony.gold == 0 and self.ever_deliverable_gold_known[player])
            diagnostics["max_consecutive_turns_without_mine_deposit_build"] = self.longest_economic_idle_streak[player]
            diagnostics["stranded_gold_rovers_after_feasible_return"] = sum(
                rover.gold > 0 and self.ever_feasible_carried_gold.get(rover.id, False)
                for rover in self.game.rovers.values() if rover.player == player)
            useful_actions = self.effect[player]["MINE"] + self.effect[player]["DEPOSIT"]
            diagnostics["banked_gold_per_effective_mine_or_deposit"] = (
                colony.gold / useful_actions if useful_actions else 0)
            results.append({
                "economy": economy,
                "economic_diagnostics": diagnostics,
                "milestones": self.milestones[player],
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
                "base_usage": dict(sorted(self.base_usage[player].items())),
                "base_construction_events": self.base_events[player],
                "construction_audit": dict(sorted(self.build_audit[player].items())),
                "site_audit_ignoring_iron": dict(sorted(self.site_audit[player].items())),
            })
        return results
