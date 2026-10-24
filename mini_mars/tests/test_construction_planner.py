"""Focused tests for active construction planning and timing."""
import unittest
from mini_mars.bots.construction import PlannedConstructionBot
from mini_mars.engine.game import Config, make_game, observation, reveal, step
from mini_mars.bots.strategies import StrategySettings, construction_reason, known_cells


def remote_gold_game(initial_iron=4):
    cfg = Config(turns=120, rock_pairs=0, gold_pairs=0, iron_pairs=0,
                 base_cost_iron=4, initial_banked_iron=initial_iron,
                 full_information=True)
    game = make_game(1, cfg)
    game.cell((11, 11)).resource = "gold"
    game.cell((11, 11)).quantity = 80
    game.cell((2, 1)).resource = "iron"
    game.cell((2, 1)).quantity = 40
    reveal(game)
    return game


class PlannedConstructionTests(unittest.TestCase):
    def test_funded_colony_selects_site_and_builds(self):
        game = remote_gold_game()
        bot = PlannedConstructionBot()
        observed_build = False
        for _ in range(55):
            obs = observation(game, 0)
            actions = bot.decide(obs)
            self.assertEqual(len(actions), game.config.starting_rovers)
            _, diagnostics = step(game, {0: {"turn": game.turn, "actions": actions},
                                         1: {"turn": game.turn, "actions": []}})
            self.assertFalse(diagnostics)
            if len(game.colonies[0].bases) > 1:
                observed_build = True
                break
        self.assertTrue(observed_build, "planner never built despite funded rich remote gold")

    def test_unfunded_worker_can_mine_and_deposit_iron(self):
        game = remote_gold_game(initial_iron=0)
        bot = PlannedConstructionBot()
        mined_iron = False
        for _ in range(65):
            turn = game.turn
            actions = bot.decide(observation(game, 0))
            events, diagnostics = step(game, {0: {"turn": turn, "actions": actions},
                                              1: {"turn": turn, "actions": []}})
            self.assertFalse(diagnostics)
            mined_iron |= any(e["type"] == "mine" and e["resource"] == "iron" for e in events)
            if len(game.colonies[0].bases) > 1:
                break
        self.assertTrue(mined_iron)

    def test_legacy_and_scaled_thresholds_are_distinct(self):
        game = remote_gold_game()
        game.turn = 80
        rover = game.rovers["p0-r0"]
        cells = known_cells(observation(game, 0))
        self.assertEqual(construction_reason(observation(game, 0), rover.public(), cells,
                                              StrategySettings()), "turn_cutoff")
        self.assertNotEqual(construction_reason(observation(game, 0), rover.public(), cells,
                                               StrategySettings(horizon_scaled=True)), "turn_cutoff")


if __name__ == "__main__":
    unittest.main()
