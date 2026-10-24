"""Focused tests for active construction planning and timing."""
import unittest
from unittest.mock import patch
import mini_mars.bots.construction as construction
from mini_mars.bots.construction import PlannedConstructionBot
from mini_mars.engine.game import Config, make_game, observation, reveal, step
from mini_mars.bots.strategies import StrategySettings, construction_reason, known_cells


def remote_gold_game(initial_iron=4, full_information=True):
    cfg = Config(turns=120, rock_pairs=0, gold_pairs=0, iron_pairs=0,
                 base_cost_iron=4, initial_banked_iron=initial_iron,
                 full_information=full_information)
    game = make_game(1, cfg)
    game.cell((11, 11)).resource = "gold"
    game.cell((11, 11)).quantity = 80
    game.cell((2, 1)).resource = "iron"
    game.cell((2, 1)).quantity = 40
    reveal(game)
    return game


class PlannedConstructionTests(unittest.TestCase):
    def test_fog_discovery_to_useful_base_lifecycle(self):
        game = remote_gold_game(initial_iron=0, full_information=False)
        bot = PlannedConstructionBot()
        self.assertFalse(any(cell["resource"] == "gold" for cell in observation(game, 0)["cells"]))
        discovered = planned = mined = deposited_iron = built = delivered = False
        while game.turn < game.config.turns:
            turn = game.turn
            obs = observation(game, 0)
            discovered |= any(cell["resource"] == "gold" for cell in obs["cells"])
            actions = bot.decide(obs)
            if bot.plan is not None:
                planned = True
                self.assertTrue(discovered)
                self.assertGreater(bot.plan.projected_saved_turns, bot.plan.acquisition_turns)
            events, diagnostics = step(game, {0: {"turn": turn, "actions": actions},
                                              1: {"turn": turn, "actions": []}})
            self.assertFalse(diagnostics)
            for event in events:
                if event["type"] == "mine" and event["resource"] == "iron" and event["rover_id"].startswith("p0"):
                    mined = True
                if event["type"] == "deposit" and event["rover_id"].startswith("p0"):
                    deposited_iron |= event["iron"] > 0
                    if game.rovers[event["rover_id"]].position in game.colonies[0].bases[1:]:
                        delivered |= event["gold"] > 0
                if event["type"] == "build" and event["player"] == 0:
                    built = True
        self.assertTrue(all((discovered, planned, mined, deposited_iron, built, delivered)))
        from mini_mars.bots.strategies import CoordinatedGreedy
        control = remote_gold_game(initial_iron=0, full_information=False)
        collector = CoordinatedGreedy(StrategySettings(
            gold_priority=True, iron_enabled=False, build_enabled=False,
            stable_targets=True, horizon_scaled=True))
        while control.turn < control.config.turns:
            turn = control.turn
            step(control, {0: {"turn": turn, "actions": collector.decide(observation(control, 0))},
                           1: {"turn": turn, "actions": []}})
        self.assertGreater(game.colonies[0].gold, control.colonies[0].gold)

    def test_complete_unfunded_lifecycle_improves_banked_gold(self):
        from mini_mars.bots.strategies import CoordinatedGreedy

        def play(bot):
            game = remote_gold_game(initial_iron=0)
            iron_mined = builds = constructed_gold = 0
            while game.turn < game.config.turns:
                turn = game.turn
                actions = bot.decide(observation(game, 0))
                events, diagnostics = step(game, {0: {"turn": turn, "actions": actions},
                                                  1: {"turn": turn, "actions": []}})
                self.assertFalse(diagnostics)
                for event in events:
                    if event["type"] == "mine" and event["resource"] == "iron" and event["rover_id"].startswith("p0"):
                        iron_mined += event["quantity"]
                    if event["type"] == "build" and event["player"] == 0:
                        builds += 1
                    if event["type"] == "deposit" and event["rover_id"].startswith("p0"):
                        point = game.rovers[event["rover_id"]].position
                        if point in game.colonies[0].bases[1:]:
                            constructed_gold += event["gold"]
            return game.colonies[0].gold, iron_mined, builds, constructed_gold

        planned = play(PlannedConstructionBot())
        gold_only = play(CoordinatedGreedy(StrategySettings(iron_enabled=False, build_enabled=False)))
        self.assertEqual(planned[1:3], (4, 1))
        self.assertGreater(planned[3], 0)
        self.assertGreater(planned[0], gold_only[0])

    def test_rejects_plan_without_payback_or_iron(self):
        bot = PlannedConstructionBot()
        game = remote_gold_game(initial_iron=0)
        game.cell((2, 1)).quantity = 3
        reveal(game)
        self.assertIsNone(bot._choose_plan(observation(game, 0), known_cells(observation(game, 0))))
        game.cell((2, 1)).quantity = 0
        reveal(game)
        self.assertIsNone(bot._choose_plan(observation(game, 0), known_cells(observation(game, 0))))
        game.colonies[0].iron = 4
        game.turn = 110
        self.assertIsNone(bot._choose_plan(observation(game, 0), known_cells(observation(game, 0))))

    def test_iron_search_shares_home_distance_map(self):
        game = remote_gold_game(initial_iron=0)
        for x in range(3, 11):
            game.cell((x, 1)).resource = "iron"
            game.cell((x, 1)).quantity = 10
        reveal(game)
        original = construction.home_distances
        with patch.object(construction, "home_distances", wraps=original) as calls:
            PlannedConstructionBot().decide(observation(game, 0))
        self.assertLess(calls.call_count, 8)

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
        # 75 is past the historical cutoff (65), but before 65% of 120 (78).
        game.turn = 75
        rover = game.rovers["p0-r0"]
        cells = known_cells(observation(game, 0))
        self.assertEqual(construction_reason(observation(game, 0), rover.public(), cells,
                                              StrategySettings()), "turn_cutoff")
        self.assertNotEqual(construction_reason(observation(game, 0), rover.public(), cells,
                                               StrategySettings(horizon_scaled=True)), "turn_cutoff")


if __name__ == "__main__":
    unittest.main()
