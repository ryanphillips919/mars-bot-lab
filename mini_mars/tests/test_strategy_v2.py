from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mini_mars.bots.strategies import (CoordinatedGreedy, GreedyMiner, StrategySettings,
                                      construction_reason, feasible_mining_units, home_distances,
                                      known_cells, task_candidates)
from mini_mars.engine.game import Config, initial_map, make_game, observation, reveal, step
from mini_mars.runner.metrics import MatchMetrics
from mini_mars.runner.tournament import run_tournament
from mini_mars.scenarios import SCENARIOS


class StrategyV2Tests(unittest.TestCase):
    def test_short_horizon_changes_only_turn_limit(self):
        short = SCENARIOS["short-horizon"]
        self.assertEqual(short, replace(SCENARIOS["default"], turns=40))
        self.assertEqual(initial_map(make_game(42, short)), initial_map(make_game(42)))

    def test_frontier_policies_rank_different_locations_with_same_bid(self):
        cells = {(x, 0): {"terrain": "plain", "resource": None, "quantity": 0} for x in range(5)}
        seen = {"turn": 0, "constants": {"turns": 100, "cargo_capacity": 5,
                  "mine_rate": 1, "base_cost_iron": 8}, "bases": [{"x": 0, "y": 0}],
                "bank": {"iron": 0}, "enemies": {"rovers": []}}
        rover = {"id": "p0-r0", "x": 0, "y": 0, "cargo": {"gold": 0, "iron": 0}}
        frontiers = [((1, 0), 1), ((4, 0), 10)]
        nearest = task_candidates(seen, rover, cells, frontiers, None,
                                  StrategySettings(frontier_policy="nearest"))
        gain = task_candidates(seen, rover, cells, frontiers, None, StrategySettings())
        self.assertEqual({item[2]: item[0] for item in nearest},
                         {item[2]: item[0] for item in gain})
        self.assertEqual(min(nearest, key=lambda item: item[4])[2], (1, 0))
        self.assertEqual(min(gain, key=lambda item: item[4])[2], (4, 0))

    def test_endgame_deposit_boundary_and_infeasible_trip(self):
        config = Config(turns=5, rock_pairs=0, gold_pairs=0, iron_pairs=0,
                        full_information=True)
        game = make_game(7, config)
        rover = game.rovers["p0-r0"]
        rover.gold = 2
        game.turn = 4
        reveal(game)
        for bot in (GreedyMiner(), CoordinatedGreedy()):
            action = bot.decide(observation(game, 0))[0]
            self.assertEqual(action["type"], "DEPOSIT")
        rover.x, rover.y = 2, 1
        game.turn = 3  # Two actions remain: MOVE, then DEPOSIT.
        reveal(game)
        for bot in (GreedyMiner(), CoordinatedGreedy()):
            self.assertEqual(bot.decide(observation(game, 0))[0],
                             {"rover_id": rover.id, "type": "MOVE", "direction": "W"})
        rover.x, rover.y = 3, 1
        game.turn = 4
        reveal(game)
        for bot in (GreedyMiner(), CoordinatedGreedy()):
            self.assertEqual(bot.decide(observation(game, 0))[0]["type"], "WAIT")

        rover.x, rover.y, rover.gold = 2, 1, 0
        game.cell((2, 1)).resource, game.cell((2, 1)).quantity = "gold", 3
        game.turn = 2  # MINE, MOVE, DEPOSIT fits exactly.
        reveal(game)
        for bot in (GreedyMiner(), CoordinatedGreedy()):
            self.assertEqual(bot.decide(observation(game, 0))[0]["type"], "MINE")
        game.turn = 3  # Same trip no longer fits.
        reveal(game)
        for bot in (GreedyMiner(), CoordinatedGreedy()):
            self.assertNotEqual(bot.decide(observation(game, 0))[0]["type"], "MINE")

    def test_build_can_happen_at_a_suitable_site(self):
        game = make_game(5, replace(SCENARIOS["default"], full_information=True))
        rover = game.rovers["p0-r0"]
        rover.x = rover.y = 7
        game.cell((7, 7)).terrain = "plain"
        for point in ((8, 7), (7, 8)):
            cell = game.cell(point)
            cell.terrain, cell.resource, cell.quantity = "plain", "gold", 8
        game.colonies[0].iron = 8
        reveal(game)
        seen = observation(game, 0)
        self.assertEqual(construction_reason(seen, rover.public(), known_cells(seen),
                                             StrategySettings()), "eligible")
        self.assertEqual(construction_reason(seen, rover.public(), known_cells(seen),
                                             StrategySettings(build_policy="payback")), "eligible")
        actions = CoordinatedGreedy().decide(seen)
        self.assertEqual(actions[0]["type"], "BUILD")
        submissions = {0: {"turn": game.turn, "actions": actions},
                       1: {"turn": game.turn, "actions": []}}
        metrics = MatchMetrics(game, ("coordinated", "greedy"))
        before = {identity: item.position for identity, item in game.rovers.items()}
        observations = [seen, observation(game, 1)]
        trace = {}
        events, diagnostics = step(game, submissions, trace)
        metrics.record(observations, [submissions[0], submissions[1]], trace, events, before)
        self.assertFalse(diagnostics)
        self.assertIn("build", [event["type"] for event in events])
        self.assertEqual(metrics.report()[0]["actions"]["effect"].get("BUILD"), 1)
        self.assertEqual(metrics.report()[0]["economy"]["iron_spent_on_bases"], 8)

    def test_iron_trip_requires_time_to_afford_and_use_a_base(self):
        config = Config(turns=40, rock_pairs=0, gold_pairs=0, iron_pairs=0,
                        full_information=True)
        game = make_game(7, config)
        iron = game.cell((2, 1))
        iron.resource, iron.quantity = "iron", 8
        gold = game.cell((4, 1))
        gold.resource, gold.quantity = "gold", 8
        game.turn = 35
        reveal(game)
        seen = observation(game, 0)
        cells = known_cells(seen)
        rover = seen["rovers"][0]
        self.assertEqual(feasible_mining_units(seen, rover, (2, 1), cells[(2, 1)], 1,
                                                cells, True, home_distances(seen["bases"], cells)), 0)

    def test_endgame_return_uses_bfs_detour_not_manhattan(self):
        config = Config(turns=6, rock_pairs=0, gold_pairs=0, iron_pairs=0,
                        full_information=True)
        game = make_game(8, config)
        rover = game.rovers["p0-r0"]
        rover.x, rover.y, rover.gold = 3, 1, 2
        game.cell((2, 1)).terrain = "rock"
        game.turn = 2  # Four actions: Manhattan suggests three; BFS needs five.
        reveal(game)
        seen = observation(game, 0)
        self.assertEqual(GreedyMiner().decide(seen)[0]["type"], "WAIT")
        self.assertEqual(CoordinatedGreedy().decide(seen)[0]["type"], "WAIT")


class MetricsV2Tests(unittest.TestCase):
    def test_same_seed_repeats_scores_and_behavior(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = replace(SCENARIOS["short-horizon"], turns=8)
            first = run_tournament("coordinated-nearest", "coordinated", 1, 49,
                                   config=config, output_dir=root / "first")
            second = run_tournament("coordinated-nearest", "coordinated", 1, 49,
                                    config=config, output_dir=root / "second")
            for key in ("paired_score_differences_a_minus_b", "wins", "behavior_totals",
                        "reliability", "paired_bootstrap_ci95_a_minus_b"):
                self.assertEqual(first[key], second[key])

    def test_submitted_normalized_and_effect_counts_are_distinct(self):
        game = make_game(3, Config(turns=2, gold_pairs=0, iron_pairs=0, rock_pairs=0))
        game.cell((1, 1)).resource, game.cell((1, 1)).quantity = "gold", 2
        reveal(game)
        metrics = MatchMetrics(game, ("greedy", "greedy"))
        first = {0: {"turn": 0, "actions": [
            {"rover_id": "p0-r0", "type": "MINE"},
            {"rover_id": "p0-r1", "type": "WAIT"},
            {"rover_id": "p0-r2", "type": "MOVE", "direction": "BAD"}]},
                 1: {"turn": 0, "actions": []}}
        before = {key: rover.position for key, rover in game.rovers.items()}
        seen = [observation(game, player) for player in (0, 1)]
        trace = {}
        events, diagnostics = step(game, first, trace)
        self.assertEqual(len(diagnostics), 1)
        metrics.record(seen, [first[0], first[1]], trace, events, before)
        report = metrics.report()[0]
        self.assertEqual(report["actions"]["submitted"], {"MINE": 1, "MOVE": 1, "WAIT": 1})
        self.assertEqual(report["actions"]["normalized"], {"MINE": 1, "WAIT": 2})
        self.assertEqual(report["actions"]["effect"], {"MINE": 1})
        self.assertEqual(report["economy"]["no_effect_rover_turns"], 2)

        second = {0: {"turn": 1, "actions": [{"rover_id": "p0-r0", "type": "DEPOSIT"}]},
                  1: {"turn": 1, "actions": []}}
        before = {key: rover.position for key, rover in game.rovers.items()}
        seen = [observation(game, player) for player in (0, 1)]
        trace = {}
        events, _ = step(game, second, trace)
        metrics.record(seen, [second[0], second[1]], trace, events, before)
        economy = metrics.report()[0]["economy"]
        self.assertEqual((economy["gold_mined"], economy["gold_deposited"],
                          economy["gold_in_cargo_at_end"]), (1, 1, 0))

    def test_faulted_game_excludes_pair_but_reports_reliability(self):
        with tempfile.TemporaryDirectory() as directory:
            def fake(*args, **kwargs):
                fault = "swapped" in str(args[4])
                return {"scores": [9, 1], "output_dir": str(args[4]),
                        "invalid_actions": [int(fault), 0], "timeouts": [0, 0],
                        "crashes": [0, 0], "protocol_fault_turns": [0, 0]}
            with patch("mini_mars.runner.tournament.run_match", side_effect=fake):
                report = run_tournament("greedy", "value", 1, 19, output_dir=Path(directory))
            self.assertEqual(report["complete_pairs"], 0)
            self.assertEqual(report["failed_pairs"], 1)
            self.assertEqual(report["faulted_matches"], 1)
            self.assertEqual(report["reliability"]["b"]["faulted_games"], 1)
            self.assertIsNone(report["win_rate_a"])


if __name__ == "__main__":
    unittest.main()
