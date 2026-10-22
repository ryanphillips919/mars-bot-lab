from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from mini_mars.ascii_replay import render
from mini_mars.bots.strategies import CoordinatedGreedy, GreedyMiner
from mini_mars.engine.game import Config, make_game, observation, reveal
from mini_mars.runner.match import run_match
from mini_mars.runner.tournament import run_tournament


class RunnerTests(unittest.TestCase):
    def test_protocol_match_replay_and_deterministic_result(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Config(turns=20)
            first = run_match(("greedy", "coordinated"), 42, config=config,
                              output_dir=Path(directory) / "a")
            second = run_match(("greedy", "coordinated"), 42, config=config,
                               output_dir=Path(directory) / "b")
            self.assertEqual(first["scores"], second["scores"])
            self.assertEqual(first["winner"], second["winner"])
            self.assertEqual(first["invalid_actions"], [0, 0])
            self.assertEqual(first["source_sha256"], second["source_sha256"])
            replay = json.loads(Path(first["replay"]).read_text())
            self.assertEqual(len(replay["frames"]), 21)
            self.assertIn("?", render(replay, 0, "0"))
            self.assertIn("Gold P0", render(replay, 20, "omniscient"))

    def test_invalid_bot_response_becomes_wait(self):
        with tempfile.TemporaryDirectory() as directory:
            broken = "python3 -c 'import sys; [print(\"not-json\", flush=True) for line in sys.stdin]'"
            result = run_match((broken, "greedy"), 7, config=Config(turns=3),
                               output_dir=Path(directory))
            self.assertEqual(result["turns"], 3)
            self.assertGreater(result["invalid_actions"][0], 0)
            self.assertEqual(result["scores"][0], 0)
            self.assertEqual(result["crashes"][0], 0)

    def test_timeout_is_recorded_once_and_match_finishes(self):
        with tempfile.TemporaryDirectory() as directory:
            sleeping = "python3 -c 'import time; time.sleep(2)'"
            result = run_match((sleeping, "greedy"), 7, config=Config(turns=2),
                               output_dir=Path(directory), timeout_seconds=.2)
            self.assertEqual(result["turns"], 2)
            self.assertEqual(result["timeouts"], [1, 0])
            self.assertEqual(result["crashes"], [0, 0])

    def test_coordinator_builds_once_when_remote_gold_pays_back(self):
        game = make_game(5)
        for rover_id in ("p0-r0", "p0-r1"):
            game.rovers[rover_id].x = game.rovers[rover_id].y = 7
        game.cell((7, 7)).terrain = "plain"
        for point in ((8, 7), (7, 8)):
            cell = game.cell(point)
            cell.terrain, cell.resource, cell.quantity = "plain", "gold", 8
        game.colonies[0].iron = 8
        reveal(game)
        actions = CoordinatedGreedy().decide(observation(game, 0))
        self.assertEqual(sum(action["type"] == "BUILD" for action in actions), 1)

    def test_greedy_does_not_target_unreachable_known_deposit(self):
        game = make_game(5)
        seen = observation(game, 0)
        seen["cells"].append({"x": 13, "y": 2, "terrain": "plain", "resource": "gold",
                              "quantity": 8, "last_seen": 0, "visible": False})
        actions = GreedyMiner().decide(seen)
        self.assertEqual(len(actions), 3)
        self.assertTrue(all(action["type"] in {"MOVE", "WAIT"} for action in actions))

    def test_tournament_swaps_positions_and_keeps_bot_seeds(self):
        with tempfile.TemporaryDirectory() as directory:
            report = run_tournament("greedy", "coordinated", 1, 19, Config(turns=5),
                                    Path(directory))
            self.assertEqual(report["games_played"], 2)
            self.assertEqual([item["swapped"] for item in report["records"]], [False, True])
            normal = json.loads((Path(directory) / "seed-19-normal" / "summary.json").read_text())
            swapped = json.loads((Path(directory) / "seed-19-swapped" / "summary.json").read_text())
            self.assertEqual(normal["bots"], swapped["bots"][::-1])
            self.assertEqual(normal["bot_seeds"], swapped["bot_seeds"][::-1])
            self.assertEqual(sum(report["wins"].values()), 2)


if __name__ == "__main__":
    unittest.main()
