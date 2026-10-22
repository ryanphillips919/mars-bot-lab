from __future__ import annotations

from dataclasses import replace
import json
import subprocess
import sys
import unittest

from mini_mars.bots.competition_starter import StarterBot
from mini_mars.engine.game import Config, initial_map, make_game, observation, reachable, reveal, step
from mini_mars.scenarios import SCENARIOS


class StarterTests(unittest.TestCase):
    def test_full_cargo_on_gold_returns_without_decision_error(self):
        game = make_game(19, Config(turns=6, rock_pairs=0, gold_pairs=0, iron_pairs=0,
                                    starting_rovers=1, full_information=True))
        rover = game.rovers["p0-r0"]
        rover.x, rover.y, rover.gold = 2, 1, game.config.cargo_capacity
        game.cell((2, 1)).resource, game.cell((2, 1)).quantity = "gold", 5
        game.turn = 2
        reveal(game)
        bot = StarterBot()
        self.assertEqual(bot.decide(observation(game, 0))[0],
                         {"rover_id": "p0-r0", "type": "MOVE", "direction": "W"})
        self.assertEqual(bot.decide(observation(game, 0))[0],
                         {"rover_id": "p0-r0", "type": "MOVE", "direction": "W"})

    def test_exact_last_deposit_and_no_known_resource_wait(self):
        game = make_game(20, Config(turns=4, rock_pairs=0, gold_pairs=0, iron_pairs=0,
                                    starting_rovers=1, full_information=True))
        rover = game.rovers["p0-r0"]
        rover.gold = 1
        game.turn = 3
        reveal(game)
        self.assertEqual(StarterBot().decide(observation(game, 0))[0]["type"], "DEPOSIT")
        rover.gold = 0
        self.assertEqual(StarterBot().decide(observation(game, 0))[0]["type"], "WAIT")

    def test_direct_json_lines_entry_survives_bad_observation(self):
        valid = observation(make_game(21, Config(turns=2)), 0)
        partial = {"turn": 7, "rovers": [{"id": "p0-r0"}]}
        malformed = {**valid, "turn": 8, "rovers": None}
        process = subprocess.run([sys.executable, "-m", "mini_mars.bots.competition_starter"],
                                 input="\n".join(json.dumps(item) for item in (valid, partial, malformed, valid)) + "\n",
                                 text=True, capture_output=True, check=True)
        first, second, third, fourth = [json.loads(line) for line in process.stdout.splitlines()]
        self.assertEqual(first["turn"], 0)
        self.assertNotIn("bot_error", first)
        self.assertEqual(second["turn"], 7)
        self.assertEqual(second["actions"], [{"rover_id": "p0-r0", "type": "WAIT"}])
        self.assertEqual(second["bot_error"], "KeyError")
        self.assertEqual(third, {"turn": 8, "actions": [], "bot_error": "TypeError"})
        self.assertNotIn("bot_error", fourth)

    def test_new_presets_generate_symmetric_reachable_maps(self):
        for name in ("abundant", "open", "limited-vision", "low-capacity", "iron-rich"):
            for seed in (62000, 62007, 63001):
                with self.subTest(scenario=name, seed=seed):
                    game = make_game(seed, SCENARIOS[name])
                    self.assertEqual(initial_map(game), initial_map(make_game(seed, SCENARIOS[name])))
                    open_count = game.config.width * game.config.height - 2 * game.config.rock_pairs
                    self.assertEqual(len(reachable((1, 1), game.cells)), open_count)
                    for y, row in enumerate(game.cells):
                        for x, cell in enumerate(row):
                            mirror = game.cell((game.config.width - 1 - x, game.config.height - 1 - y))
                            self.assertEqual((cell.terrain, cell.resource, cell.quantity),
                                             (mirror.terrain, mirror.resource, mirror.quantity))

    def test_starter_actions_remain_legal_under_adversarial_presets(self):
        for name in ("abundant", "open", "limited-vision", "low-capacity", "iron-rich", "short-horizon"):
            with self.subTest(scenario=name):
                game = make_game(62001, replace(SCENARIOS[name], turns=12))
                bots = (StarterBot(), StarterBot())
                while game.turn < game.config.turns:
                    responses = {p: {"turn": game.turn, "actions": bots[p].decide(observation(game, p))}
                                 for p in (0, 1)}
                    _, diagnostics = step(game, responses)
                    self.assertEqual(diagnostics, [])


if __name__ == "__main__":
    unittest.main()
