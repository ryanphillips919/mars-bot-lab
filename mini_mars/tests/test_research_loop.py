from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mini_mars.bots.strategies import (CoordinatedGreedy, StrategySettings,
                                      task_candidates)
from mini_mars.engine.game import Config, make_game, observation, reveal, step
from mini_mars.runner.match import run_match
from mini_mars.runner.metrics import MatchMetrics
from mini_mars.runner.reliability import MovementMonitor
from mini_mars.runner.tournament import run_tournament


class ResearchReliabilityTests(unittest.TestCase):
    def test_gold_priority_prevents_exploration_from_starving_known_gold(self):
        config = Config(starting_rovers=1, rock_pairs=0, gold_pairs=0, iron_pairs=0)
        game = make_game(2, config)
        game.cell((1, 1)).resource, game.cell((1, 1)).quantity = "gold", 8
        reveal(game)
        seen = observation(game, 0)
        with patch("mini_mars.bots.strategies.exploration_targets", return_value=[((1, 1), 100)]):
            baseline = CoordinatedGreedy().decide(seen)[0]
            improved = CoordinatedGreedy(StrategySettings(gold_priority=True)).decide(seen)[0]
        self.assertEqual(baseline["type"], "WAIT")
        self.assertEqual(improved["type"], "MINE")

    def test_frontier_scores_are_individual_and_adaptive_to_known_gold(self):
        obs = {"turn": 20, "constants": {"turns": 40, "cargo_capacity": 5,
               "mine_rate": 1, "base_cost_iron": 8}, "bases": [{"x": 0, "y": 0}],
               "bank": {"iron": 0}, "rovers": [{"id": "p0-r0", "x": 0, "y": 0,
               "cargo": {"gold": 0, "iron": 0}}], "enemies": {"rovers": []}}
        cells = {(x, 0): {"terrain": "plain", "resource": None, "quantity": 0} for x in range(5)}
        cells[(1, 0)] = {"terrain": "plain", "resource": "gold", "quantity": 5}
        frontiers = [((2, 0), 2), ((4, 0), 4)]
        rover = obs["rovers"][0]
        shared = task_candidates(obs, rover, cells, frontiers, None, StrategySettings())
        scored = task_candidates(obs, rover, cells, frontiers, None,
                                 StrategySettings(frontier_value_mode="individual"))
        adaptive = task_candidates(obs, rover, cells, frontiers, None,
                                   StrategySettings(frontier_value_mode="individual",
                                                    adaptive_exploration=True))
        explore = lambda bids: {point: value for value, kind, point, _, _ in bids if kind == "explore"}
        self.assertEqual(len(set(explore(shared).values())), 1)
        self.assertNotEqual(explore(scored)[(2, 0)], explore(scored)[(4, 0)])
        self.assertAlmostEqual(explore(adaptive)[(2, 0)], explore(scored)[(2, 0)] / 4)

    def test_seed_50004_economic_failure_is_measured_and_repaired(self):
        with tempfile.TemporaryDirectory() as folder:
            baseline = run_match(("greedy", "coordinated"), 50004, scenario="short-horizon",
                                 output_dir=Path(folder) / "baseline", save_replay=False)
            improved = run_match(("greedy", "coordinated-harvest-first"), 50004,
                                 scenario="short-horizon", output_dir=Path(folder) / "improved",
                                 save_replay=False)
            self.assertEqual(baseline["scores"][1], 0)
            self.assertGreater(improved["scores"][1], 0)
            behavior = baseline["behavior"][1]
            self.assertIsNotNone(behavior["milestones"]["first_gold_discovery_turn"])
            self.assertIsNone(behavior["milestones"]["first_gold_mine_turn"])
            self.assertIsNone(behavior["milestones"]["first_gold_deposit_turn"])
            self.assertGreater(behavior["economic_diagnostics"]["exploration_moves_with_deliverable_gold_known"], 0)
            self.assertEqual(behavior["economic_diagnostics"]["zero_score_after_deliverable_gold_known"], 1)
            self.assertEqual(behavior["economic_diagnostics"]["mine_or_deposit_action_percent"], 0)
            self.assertIsNotNone(improved["behavior"][1]["milestones"]["first_gold_deposit_turn"])

    def test_per_frontier_values_break_scarce_map_backtracking(self):
        # On this map, equal frontier bids make a rover reverse between two
        # tiles as other rovers reserve and release its distant target.
        with tempfile.TemporaryDirectory() as folder:
            old = run_match(("greedy", "coordinated-harvest-first"), 67049,
                            scenario="scarce", output_dir=Path(folder) / "old", save_replay=False)
            scored = run_match(("greedy", "coordinated-harvest-scored"), 67049,
                               scenario="scarce", output_dir=Path(folder) / "scored", save_replay=False)
            self.assertGreater(old["movement_warnings"][1].get("back_and_forth", 0), 0)
            self.assertEqual(scored["movement_warnings"][1].get("back_and_forth", 0), 0)
            self.assertEqual(scored["movement_warnings"][1].get("small_tile_cycle", 0), 0)
            self.assertGreater(scored["scores"][1], 0)
            self.assertEqual(scored["decision_errors"], [0, 0])

    def test_idle_with_known_work_and_stranded_gold_warn(self):
        game = make_game(3, Config(turns=12, starting_rovers=1, rock_pairs=0,
                                   gold_pairs=0, iron_pairs=0, full_information=True))
        game.cell((2, 1)).resource, game.cell((2, 1)).quantity = "gold", 5
        reveal(game)
        metrics = MatchMetrics(game, ("greedy", "greedy"))
        monitor = MovementMonitor()
        while game.turn < game.config.turns:
            seen = [observation(game, p) for p in (0, 1)]
            responses = [{"turn": game.turn, "actions": []} for _ in (0, 1)]
            before = {rid: rover.position for rid, rover in game.rovers.items()}
            trace = {}
            events, diagnostics = step(game, dict(enumerate(responses)), trace)
            self.assertFalse(diagnostics)
            metrics.record(seen, responses, trace, events, before)
            monitor.record(game, seen, responses, trace, events, before, metrics.last_opportunities)
        self.assertEqual(monitor.report()[0].get("idle_with_work"), 1)
        game.rovers["p0-r0"].gold = 2
        monitor.finish(game)
        self.assertEqual(monitor.report()[0].get("stranded_gold"), 1)

    def test_reported_bot_error_is_not_hidden_as_a_clean_wait(self):
        with tempfile.TemporaryDirectory() as folder:
            script = Path(folder) / "reported_error.py"
            script.write_text('import json,sys\nfor line in sys.stdin:\n '
                              'print(json.dumps({"turn":json.loads(line)["turn"],'
                              '"actions":[],"bot_error":"KeyError"}),flush=True)\n')
            result = run_match((f"{__import__('sys').executable} {script}", "greedy"), 7,
                               config=Config(turns=2), output_dir=Path(folder) / "match",
                               save_replay=False)
            self.assertEqual(result["decision_errors"], [2, 0])
            self.assertEqual(result["invalid_actions"], [0, 0])
            self.assertEqual(result["crashes"], [0, 0])
            report = run_tournament(f"{__import__('sys').executable} {script}", "greedy", 1, 7,
                                    config=Config(turns=2), output_dir=Path(folder) / "tournament")
            self.assertEqual(report["complete_pairs"], 0)
            self.assertEqual(report["reliability"]["a"]["faulted_games"], 2)
            self.assertEqual(report["reliability"]["a"]["decision_errors"], 4)


if __name__ == "__main__":
    unittest.main()
