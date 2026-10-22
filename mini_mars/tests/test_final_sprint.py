"""Deterministic adversarial checks for rules and persistent bot decisions."""

from __future__ import annotations

import random
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mini_mars.bots.entry import BOT_NAMES
from mini_mars.bots.strategies import CoordinatedGreedy, StrategySettings, home_distances
from mini_mars.engine.game import Config, make_game, observation, outcome, reveal, snapshot, step
from mini_mars.runner.match import ALIASES, run_match
from mini_mars.runner.metrics import MatchMetrics


class AssignmentAndCargoTests(unittest.TestCase):
    def test_coordinator_shares_one_home_distance_map_per_decision(self):
        game = make_game(43, Config(starting_rovers=6, full_information=True))
        bot = CoordinatedGreedy(StrategySettings(gold_priority=True))
        with patch("mini_mars.bots.strategies.home_distances", wraps=home_distances) as route_map:
            actions = bot.decide(observation(game, 0))
        self.assertEqual(len(actions), 6)
        self.assertEqual(route_map.call_count, 1)

    def test_every_builtin_alias_completes_a_protocol_match(self):
        self.assertEqual(set(BOT_NAMES), ALIASES)
        with tempfile.TemporaryDirectory() as folder:
            for name in BOT_NAMES:
                with self.subTest(bot=name):
                    result = run_match((name, "greedy"), 48, config=Config(turns=8),
                                       output_dir=Path(folder) / name, save_replay=False)
                    for key in ("invalid_actions", "crashes", "timeouts", "decision_errors"):
                        self.assertEqual(result[key], [0, 0])

    def test_busy_resource_is_reserved_during_a_teammate_deposit(self):
        game = make_game(44, Config(rock_pairs=0, gold_pairs=0, iron_pairs=0,
                                    starting_rovers=2, full_information=True))
        game.cell((1, 1)).resource, game.cell((1, 1)).quantity = "gold", 8
        game.cell((3, 1)).resource, game.cell((3, 1)).quantity = "gold", 8
        game.rovers["p0-r0"].gold = 1
        game.rovers["p0-r1"].x, game.rovers["p0-r1"].y = 2, 1
        reveal(game)
        old = CoordinatedGreedy(StrategySettings(gold_priority=True))
        stable = CoordinatedGreedy(StrategySettings(gold_priority=True, stable_targets=True))
        for bot in (old, stable):
            bot.targets["p0-r0"] = (1, 1)
            bot.target_kinds["p0-r0"] = "resource"
        self.assertEqual(old.decide(observation(game, 0))[1]["direction"], "W")
        actions = stable.decide(observation(game, 0))
        self.assertEqual(actions[0]["type"], "DEPOSIT")
        self.assertEqual(actions[1], {"rover_id": "p0-r1", "type": "MOVE", "direction": "E"})
        self.assertEqual(stable.diagnostic_targets["p0-r1"], (3, 1))

    def test_partial_gold_returns_when_extra_unit_requires_large_detour(self):
        game = make_game(45, Config(rock_pairs=0, gold_pairs=0, iron_pairs=0,
                                    starting_rovers=1, full_information=True))
        rover = game.rovers["p0-r0"]
        rover.x, rover.y, rover.gold = 5, 1, 4
        game.cell((12, 1)).resource, game.cell((12, 1)).quantity = "gold", 11
        reveal(game)
        old = CoordinatedGreedy(StrategySettings(gold_priority=True))
        cargo = CoordinatedGreedy(StrategySettings(gold_priority=True,
                                                   marginal_cargo_return=True))
        self.assertEqual(old.decide(observation(game, 0))[0]["direction"], "E")
        self.assertEqual(cargo.decide(observation(game, 0))[0]["direction"], "W")
        self.assertEqual(cargo.diagnostic_targets[rover.id], (1, 1))
        rover.x, rover.y = 12, 1
        reveal(game)
        self.assertEqual(cargo.decide(observation(game, 0))[0]["type"], "MINE")

    def test_stable_policy_clears_target_when_cargo_forces_return(self):
        game = make_game(46, Config(rock_pairs=0, gold_pairs=0, iron_pairs=0,
                                    starting_rovers=1, full_information=True))
        rover = game.rovers["p0-r0"]
        rover.x, rover.y, rover.gold = 5, 1, game.config.cargo_capacity
        reveal(game)
        bot = CoordinatedGreedy(StrategySettings(gold_priority=True, stable_targets=True))
        bot.targets[rover.id] = (12, 1)
        bot.target_kinds[rover.id] = "resource"
        self.assertEqual(bot.decide(observation(game, 0))[0]["direction"], "W")
        self.assertNotIn(rover.id, bot.targets)
        self.assertNotIn(rover.id, bot.target_kinds)

    def test_seeded_assignment_loops_are_reproduced_and_removed(self):
        cases = ((64008, "full-info", "coordinated-nearest", "coordinated", "coordinated-stable"),
                 (67049, "scarce", "greedy", "coordinated-harvest-first",
                  "coordinated-harvest-stable"))
        with tempfile.TemporaryDirectory() as folder:
            for seed, scenario, opponent, old_name, stable_name in cases:
                with self.subTest(seed=seed):
                    old = run_match((opponent, old_name), seed, scenario=scenario,
                                    output_dir=Path(folder) / f"old-{seed}", save_replay=False)
                    fixed = run_match((opponent, stable_name), seed, scenario=scenario,
                                      output_dir=Path(folder) / f"fixed-{seed}", save_replay=False)
                    self.assertGreater(old["movement_warnings"][1].get("back_and_forth", 0), 0)
                    self.assertEqual(fixed["movement_warnings"][1].get("back_and_forth", 0), 0)
                    self.assertEqual(fixed["decision_errors"], [0, 0])
                    self.assertEqual(fixed["invalid_actions"], [0, 0])


class RandomizedEngineInvariantTests(unittest.TestCase):
    def test_diagnostics_identify_duplicate_targets_and_feasible_stranded_gold(self):
        game = make_game(47, Config(turns=2, rock_pairs=0, gold_pairs=0, iron_pairs=0,
                                    starting_rovers=2, full_information=True))
        game.cell((2, 1)).resource, game.cell((2, 1)).quantity = "gold", 5
        game.rovers["p0-r0"].x, game.rovers["p0-r0"].y = 2, 1
        game.rovers["p0-r0"].gold = 2
        reveal(game)
        metrics = MatchMetrics(game, ("test", "test"))
        for turn in range(2):
            seen = [observation(game, player) for player in (0, 1)]
            responses = [{"turn": turn, "actions": [],
                          "targets": {"p0-r0": [2, 1], "p0-r1": [2, 1] if turn == 0 else [3, 1]}},
                         {"turn": turn, "actions": []}]
            before = {identity: rover.position for identity, rover in game.rovers.items()}
            normalized = {}
            events, _ = step(game, dict(enumerate(responses)), normalized)
            metrics.record(seen, responses, normalized, events, before)
        report = metrics.report()[0]
        self.assertEqual(report["economic_diagnostics"]["duplicate_resource_target_rover_turns"], 1)
        self.assertEqual(report["economic_diagnostics"]["target_changes"], 1)
        self.assertEqual(report["economic_diagnostics"]["stranded_gold_rovers_after_feasible_return"], 1)
        self.assertEqual(report["economic_diagnostics"]["max_consecutive_turns_without_mine_deposit_build"], 2)
        self.assertEqual(report["milestones"]["first_resource_discovery_turn"], 0)

    def test_conservation_capacity_legality_and_seed_replay(self):
        # The same generated action sequence is applied to two identical games.
        # Deliberately invalid actions exercise normalization as well as rules.
        randomizer = random.Random(20261022)
        for case in range(60):
            capacity = randomizer.randint(2, 6)
            config = Config(width=randomizer.choice((9, 11, 15)),
                            height=randomizer.choice((9, 11, 15)), turns=20,
                            starting_rovers=randomizer.randint(1, 4),
                            cargo_capacity=capacity,
                            mine_rate=randomizer.randint(1, min(3, capacity)),
                            base_cost_iron=randomizer.randint(2, 8),
                            vision_radius=randomizer.randint(1, 3),
                            rock_pairs=randomizer.randint(0, 4),
                            gold_pairs=randomizer.randint(1, 4),
                            iron_pairs=randomizer.randint(1, 4))
            seed = 80000 + case
            first, repeat = make_game(seed, config), make_game(seed, config)
            # Vary start positions, mixed cargo, and friendly base placement.
            open_points = [(x, y) for y, row in enumerate(first.cells)
                           for x, cell in enumerate(row) if cell.terrain == "plain"]
            rover_state = {identity: (randomizer.choice(open_points),
                                      randomizer.randrange(capacity + 1))
                           for identity in first.rovers}
            extra_base = randomizer.choice(open_points)
            for game in (first, repeat):
                game.colonies[0].iron = case % 9
                game.colonies[1].iron = (case * 3) % 9
                for identity, (point, gold) in rover_state.items():
                    rover = game.rovers[identity]
                    rover.x, rover.y, rover.gold = *point, gold
                if extra_base not in game.colonies[0].bases and extra_base not in game.colonies[1].bases:
                    game.colonies[0].bases.append(extra_base)
                reveal(game)

            def total(resource):
                return (sum(cell.quantity for row in first.cells for cell in row
                            if cell.resource == resource)
                        + sum(getattr(rover, resource) for rover in first.rovers.values())
                        + sum(getattr(colony, resource) for colony in first.colonies)
                        + (config.base_cost_iron *
                           sum(len(colony.bases) - 1 for colony in first.colonies)
                           if resource == "iron" else 0))

            initial = {resource: total(resource) for resource in ("gold", "iron")}
            with self.subTest(seed=seed):
                for _ in range(config.turns):
                    submissions = {}
                    for player in (0, 1):
                        actions = []
                        for rover in observation(first, player)["rovers"]:
                            kind = randomizer.choice(("MOVE", "MINE", "DEPOSIT", "BUILD", "WAIT", "BOGUS"))
                            action = {"rover_id": rover["id"], "type": kind}
                            if kind == "MOVE":
                                action["direction"] = randomizer.choice(("N", "S", "E", "W", "X"))
                            actions.append(action)
                            if randomizer.randrange(30) == 0:
                                actions.append(action.copy())
                        submissions[player] = {"turn": first.turn, "actions": actions}
                    events, diagnostics = step(first, submissions)
                    repeated_events, repeated_diagnostics = step(repeat, submissions)
                    self.assertEqual((events, diagnostics), (repeated_events, repeated_diagnostics))
                    self.assertEqual(snapshot(first), snapshot(repeat))
                    for resource in initial:
                        self.assertEqual(total(resource), initial[resource])
                    for rover in first.rovers.values():
                        self.assertTrue(first.traversable(rover.position))
                        self.assertGreaterEqual(rover.load, 0)
                        self.assertLessEqual(rover.load, config.cargo_capacity)
                    self.assertEqual(outcome(first)["scores"],
                                     [colony.gold for colony in first.colonies])


if __name__ == "__main__":
    unittest.main()
