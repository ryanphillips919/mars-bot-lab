from __future__ import annotations

import copy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mini_mars.bots.strategies import CoordinatedGreedy, GreedyMiner, StrategySettings, ValueGreedy
from mini_mars.engine.game import initial_map, make_game, observation, reachable, reveal
from mini_mars.runner.benchmark import MATRIX, PRIMARY, select_validation_cases
from mini_mars.runner.match import run_match, source_hashes
from mini_mars.runner.tournament import paired_bootstrap_interval, run_tournament
from mini_mars.scenarios import SCENARIOS


class ScenarioTests(unittest.TestCase):
    def test_preset_maps_reproduce_and_full_info_changes_only_observation(self):
        for name, config in SCENARIOS.items():
            for seed in (42, 10000, 20000):
                game = make_game(seed, config)
                self.assertEqual(initial_map(game), initial_map(make_game(seed, config)))
                rocks = sum(cell.terrain == "rock" for row in game.cells for cell in row)
                gold = sum(cell.resource == "gold" for row in game.cells for cell in row)
                iron = sum(cell.resource == "iron" for row in game.cells for cell in row)
                self.assertEqual((rocks, gold, iron),
                                 (2 * config.rock_pairs, 2 * config.gold_pairs, 2 * config.iron_pairs), name)
                self.assertEqual(len(reachable((1, 1), game.cells)), config.width * config.height - rocks)
                if name == "full-info":
                    self.assertEqual(initial_map(game), initial_map(make_game(seed, SCENARIOS["default"])))
        fog = make_game(42, SCENARIOS["default"])
        full = make_game(42, SCENARIOS["full-info"])
        self.assertEqual(initial_map(fog), initial_map(full))
        for player in (0, 1):
            hidden = observation(fog, player)
            seen = observation(full, player)
            self.assertLess(len(hidden["cells"]), 225)
            self.assertEqual(len(seen["cells"]), 225)
            self.assertTrue(all(cell["visible"] for cell in seen["cells"]))
            self.assertEqual(hidden["enemies"], {"rovers": [], "bases": []})
            self.assertEqual(len(seen["enemies"]["rovers"]), 3)
            self.assertEqual(len(seen["enemies"]["bases"]), 1)
            self.assertNotIn("map", hidden)
            self.assertNotIn("seed", hidden)
        point = (7, 7)
        full.cell(point).resource, full.cell(point).quantity = "gold", 3
        fog.cell(point).resource, fog.cell(point).quantity = "gold", 3
        reveal(full)
        reveal(fog)
        self.assertEqual(next(cell for cell in observation(full, 0)["cells"]
                              if (cell["x"], cell["y"]) == point)["quantity"], 3)
        self.assertNotIn(point, {(cell["x"], cell["y"]) for cell in observation(fog, 0)["cells"]})

    def test_scenario_metadata_and_default_cli_compatible_runner(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            custom = run_match(("greedy", "coordinated"), 5, config=replace(SCENARIOS["default"], turns=2),
                               output_dir=out / "custom")
            self.assertEqual(custom["scenario"], "custom")
            full = run_match(("value", "independent"), 5, config=replace(SCENARIOS["full-info"], turns=2),
                             output_dir=out / "full")
            self.assertEqual(full["scenario"], "custom")
            self.assertIn("git_head", full["source_revision"])
            replay = json.loads(Path(full["replay"]).read_text())
            self.assertEqual(replay["scenario"], "custom")
            self.assertTrue(replay["config"]["full_information"])


class StrategyTests(unittest.TestCase):
    def test_variants_are_deterministic_for_same_observations(self):
        game = make_game(42)
        seen = observation(game, 0)
        variants = (GreedyMiner, ValueGreedy,
                    lambda: CoordinatedGreedy(StrategySettings(coordinate=False)),
                    CoordinatedGreedy,
                    lambda: CoordinatedGreedy(StrategySettings(exploration_weight=0)),
                    lambda: CoordinatedGreedy(StrategySettings(iron_enabled=False, build_enabled=False)))
        for make_bot in variants:
            first, second = make_bot(), make_bot()
            self.assertEqual(first.decide(copy.deepcopy(seen)), second.decide(copy.deepcopy(seen)))
            self.assertEqual(first.decide(copy.deepcopy(seen)), second.decide(copy.deepcopy(seen)))


class BenchmarkTests(unittest.TestCase):
    def test_seed_level_bootstrap_and_selection_are_repeatable(self):
        differences = [2, -1, 4, 0, 3]
        self.assertEqual(paired_bootstrap_interval(differences), paired_bootstrap_interval(differences))
        cases = [{"case": list(case), "complete_pairs": 20, "paired_mean_b_minus_a": 3.0}
                 for case in MATRIX]
        cases[0]["paired_mean_b_minus_a"] = .1
        cases[3]["paired_mean_b_minus_a"] = 9.0
        cases[6]["paired_mean_b_minus_a"] = 0.0  # negative control must not be promoted
        smoke = {"stage": "smoke", "source_sha256": source_hashes(), "cases": cases}
        self.assertEqual(select_validation_cases(smoke), sorted(set(PRIMARY) | {0, 3}))

    def test_tournament_keeps_complete_swapped_pairs(self):
        with tempfile.TemporaryDirectory() as directory:
            report = run_tournament("value", "coordinated", 2, 31,
                                    config=replace(SCENARIOS["default"], turns=5),
                                    output_dir=Path(directory))
            self.assertEqual(report["complete_pairs"], 2)
            self.assertEqual(report["games_played"], 4)
            self.assertEqual([record["swapped"] for record in report["records"]],
                             [False, True, False, True])
            expected = [(report["records"][i]["score_a"] - report["records"][i]["score_b"] +
                         report["records"][i+1]["score_a"] - report["records"][i+1]["score_b"]) / 2
                        for i in (0, 2)]
            self.assertEqual(report["paired_score_differences_a_minus_b"], expected)
            self.assertEqual(report["paired_bootstrap_ci95_a_minus_b"], paired_bootstrap_interval(expected))

    def test_failed_game_removes_entire_pair_from_statistics(self):
        with tempfile.TemporaryDirectory() as directory:
            first = {"scores": [5, 2], "output_dir": directory}
            with patch("mini_mars.runner.tournament.run_match",
                       side_effect=[first, RuntimeError("bot failed")]):
                report = run_tournament("greedy", "value", 1, 19,
                                        output_dir=Path(directory) / "tournament")
            self.assertEqual(report["failed_matches"], 1)
            self.assertEqual(report["failed_pairs"], 1)
            self.assertEqual(report["complete_pairs"], 0)
            self.assertEqual(report["games_played"], 0)
            self.assertIsNone(report["paired_bootstrap_ci95_a_minus_b"])
            self.assertEqual(report["wins"], {"a": 0, "b": 0, "ties": 0})


if __name__ == "__main__":
    unittest.main()
