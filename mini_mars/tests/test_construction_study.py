"""Experiment configuration and base-usage measurement checks."""
import tempfile
import unittest
from pathlib import Path
from mini_mars.runner.construction_study import configurations, run_study
from mini_mars.runner.match import run_match
from mini_mars.scenarios import expansion_config


class ConstructionStudyTests(unittest.TestCase):
    def test_matrix_is_complete(self):
        configs = list(configurations())
        self.assertEqual(len(configs), 54)
        self.assertEqual(len({(c.width, c.turns, c.base_cost_iron, c.resource_layout)
                              for c in configs}), 54)

    def test_initial_bank_control_funds_both_players(self):
        c = expansion_config(15, 100, 4, initial_banked_iron=4)
        self.assertEqual(c.initial_banked_iron, c.base_cost_iron)

    def test_paired_screen_smoke(self):
        with tempfile.TemporaryDirectory() as directory:
            study = run_study("screen", case_limit=1,
                              candidates=["coordinated-planned-build"],
                              count=1, output_root=Path(directory))
            self.assertEqual(len(study["cases"]), 2)
            for row in study["cases"]:
                self.assertEqual(row["attempted_games"], 2)
                self.assertEqual(row["complete_pairs"], 1)
                self.assertIn("base_usage", row["behavior_per_game"]["b"])


if __name__ == "__main__":
    unittest.main()
