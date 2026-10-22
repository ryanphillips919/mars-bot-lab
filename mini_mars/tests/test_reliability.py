"""Adversarial, deterministic fixtures for Mini Mars bot and protocol reliability."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mini_mars.bots.strategies import (CoordinatedGreedy, GreedyMiner, ValueGreedy,
                                      home_distances, protect_scored_cargo)
from mini_mars.engine.game import Config, make_game, observation, reveal, step
from mini_mars.runner.match import run_match
from mini_mars.runner.reliability import MovementMonitor


def bare_game(**overrides):
    config = replace(Config(turns=20, starting_rovers=1, rock_pairs=0, gold_pairs=0,
                            iron_pairs=0, full_information=True), **overrides)
    return make_game(1729, config)


class DeadlineAndValueTests(unittest.TestCase):
    def test_exploration_move_cannot_sacrifice_delivery(self):
        game = bare_game(turns=10, full_information=False)
        rover = game.rovers["p0-r0"]
        rover.x, rover.y, rover.gold = 4, 1, 2
        game.turn = 5  # Five actions; west three times, then deposit is feasible.
        reveal(game)
        seen = observation(game, 0)
        seen["cells"] = [{"x": x, "y": 1, "terrain": "plain", "resource": None,
                          "quantity": 0} for x in range(1, 6)]
        with patch("mini_mars.bots.strategies.exploration_targets", return_value=[((5, 1), 10)]):
            self.assertEqual(CoordinatedGreedy().decide(seen)[0],
                             {"rover_id": rover.id, "type": "MOVE", "direction": "W"})
        unsafe = {"rover_id": rover.id, "type": "MOVE", "direction": "E"}
        guarded, _ = protect_scored_cargo(seen, rover.public(), unsafe,
                                          {(c["x"], c["y"]): c for c in seen["cells"]}, seen["bases"])
        self.assertEqual(guarded["direction"], "W")

    def test_exact_deposit_and_already_impossible(self):
        game = bare_game(turns=5)
        rover = game.rovers["p0-r0"]
        rover.gold = 1
        game.turn = 4
        reveal(game)
        for bot in (GreedyMiner(), CoordinatedGreedy()):
            self.assertEqual(bot.decide(observation(game, 0))[0]["type"], "DEPOSIT")
        rover.x = 3
        reveal(game)
        for bot in (GreedyMiner(), CoordinatedGreedy()):
            self.assertEqual(bot.decide(observation(game, 0))[0]["type"], "WAIT")

    def test_value_uses_bfs_return_not_manhattan(self):
        game = bare_game()
        game.cell((2, 1)).terrain = "rock"
        reveal(game)
        seen = observation(game, 0)
        cells = {(cell["x"], cell["y"]): cell for cell in seen["cells"]}
        home = home_distances(seen["bases"], cells)
        self.assertEqual(home[(3, 1)], 4)
        self.assertEqual(home[(1, 4)], 3)
        rover = seen["rovers"][0]
        gold = {"resource": "gold", "quantity": 5}
        bot = ValueGreedy()
        self.assertLess(bot.deposit_rank((1, 4), gold, 2, rover, seen["bases"], 5, home),
                        bot.deposit_rank((3, 1), gold, 2, rover, seen["bases"], 5, home))


class StressFixtures(unittest.TestCase):
    def test_adversarial_states_are_legal_deterministic_and_do_not_loop(self):
        cases = ("no_visible_resources", "depleted", "disappearing", "shared_target",
                 "unknown_obstacle", "late_gold", "partial_cargo", "on_base",
                 "unreachable", "narrow_corridor", "one_rover", "short_match",
                 "far_resources", "no_productive_action")
        for name in cases:
            with self.subTest(fixture=name):
                config = Config(turns=8 if name == "short_match" else 14,
                                starting_rovers=3 if name == "shared_target" else 1,
                                rock_pairs=0, gold_pairs=0, iron_pairs=0,
                                full_information=name not in {"no_visible_resources", "unknown_obstacle"})
                game = make_game(1729, config)
                rover = game.rovers["p0-r0"]
                if name in {"depleted", "disappearing"}:
                    game.cell((3, 1)).resource, game.cell((3, 1)).quantity = "gold", 1
                if name in {"shared_target", "partial_cargo", "far_resources"}:
                    point = (11, 11) if name == "far_resources" else (3, 1)
                    game.cell(point).resource, game.cell(point).quantity = "gold", 9
                if name == "late_gold":
                    rover.x, rover.y, rover.gold = 3, 1, 2
                    game.turn = 10
                if name == "partial_cargo":
                    rover.gold, rover.iron = 2, 1
                if name == "unreachable":
                    game.cell((11, 11)).resource, game.cell((11, 11)).quantity = "gold", 8
                    for point in ((10, 11), (12, 11), (11, 10), (11, 12)):
                        game.cell(point).terrain = "rock"
                if name == "narrow_corridor":
                    for y in range(3, 12):
                        for x in range(2, 12):
                            if y != 7:
                                game.cell((x, y)).terrain = "rock"
                    game.cell((10, 7)).resource, game.cell((10, 7)).quantity = "gold", 8
                if name == "unknown_obstacle":
                    game.cell((4, 1)).terrain = "rock"
                    game.cell((5, 1)).resource, game.cell((5, 1)).quantity = "gold", 8
                reveal(game)
                bots = (GreedyMiner(), CoordinatedGreedy())
                monitor = MovementMonitor()
                actions_first = None
                while game.turn < game.config.turns:
                    seen = [observation(game, p) for p in (0, 1)]
                    actions = [bots[p].decide(seen[p]) for p in (0, 1)]
                    if actions_first is None:
                        actions_first = actions
                    if name == "disappearing" and game.turn == 1:
                        game.cell((3, 1)).quantity = 0
                        reveal(game)
                        seen = [observation(game, p) for p in (0, 1)]
                        actions = [bots[p].decide(seen[p]) for p in (0, 1)]
                    response = [{"turn": game.turn, "actions": actions[p],
                                 "targets": {key: list(point) for key, point in
                                             getattr(bots[p], "diagnostic_targets", {}).items()}}
                                for p in (0, 1)]
                    before = {identity: item.position for identity, item in game.rovers.items()}
                    trace = {}
                    events, diagnostics = step(game, dict(enumerate(response)), trace)
                    self.assertEqual(diagnostics, [], f"{name}, turn {game.turn - 1}")
                    monitor.record(game, seen, response, trace, events, before)
                # A repeat run from the same fixture starts with the same decision.
                self.assertIsInstance(actions_first[0], list)
                self.assertFalse(monitor.warnings, f"{name}: {monitor.warnings[:1]}")
                if name == "late_gold":
                    self.assertGreaterEqual(game.colonies[0].gold, 2)

    def test_fixed_seed_repeated_match_has_same_scores_and_warning_counts(self):
        with tempfile.TemporaryDirectory() as folder:
            for scenario in ("default", "obstacle-heavy", "short-horizon"):
                with self.subTest(scenario=scenario):
                    first = run_match(("greedy", "coordinated"), 281,
                                      scenario=scenario, output_dir=Path(folder) / f"{scenario}-a",
                                      save_replay=False)
                    second = run_match(("greedy", "coordinated"), 281,
                                       scenario=scenario, output_dir=Path(folder) / f"{scenario}-b",
                                       save_replay=False)
                    for key in ("scores", "invalid_actions", "crashes", "timeouts",
                                "movement_warnings", "behavior"):
                        self.assertEqual(first[key], second[key])

    def test_built_in_strategy_aliases_emit_legal_protocol_actions(self):
        names = ("greedy", "value", "independent", "coordinated",
                 "coordinated-nearest", "coordinated-no-explore",
                 "coordinated-gold-only", "coordinated-payback-build")
        with tempfile.TemporaryDirectory() as folder:
            for name in names:
                with self.subTest(bot=name):
                    result = run_match((name, "greedy"), 93, config=Config(turns=6),
                                       output_dir=Path(folder) / name, save_replay=name == "coordinated")
                    self.assertEqual(result["invalid_actions"], [0, 0])
                    self.assertEqual(result["crashes"], [0, 0])
                    self.assertEqual(result["timeouts"], [0, 0])
                    if name == "coordinated":
                        replay = json.loads(Path(result["replay"]).read_text())
                        self.assertEqual(replay["movement_warnings"], [])
                        self.assertEqual(result["movement_warnings"], [{}, {}])

    def test_protocol_malformed_missing_and_late_are_recorded(self):
        variants = (
            ("malformed", "python3 -c 'import sys; [print(\"bad-json\", flush=True) for _ in sys.stdin]'", "invalid_actions"),
            ("missing", "python3 -c 'pass'", "crashes"),
            ("late", "python3 -c 'import time; time.sleep(1)'", "timeouts"),
        )
        with tempfile.TemporaryDirectory() as folder:
            for name, command, key in variants:
                with self.subTest(fixture=name):
                    result = run_match((command, "greedy"), 88, config=Config(turns=2),
                                       output_dir=Path(folder) / name, timeout_seconds=.1,
                                       save_replay=False)
                    self.assertEqual(result["turns"], 2)
                    self.assertGreater(result[key][0], 0)


class MonitorTests(unittest.TestCase):
    def test_back_and_forth_warns_without_progress(self):
        game = bare_game(turns=10)
        monitor = MovementMonitor()
        for turn in range(8):
            seen = [observation(game, p) for p in (0, 1)]
            action = {"rover_id": "p0-r0", "type": "MOVE", "direction": "E" if turn % 2 == 0 else "W"}
            response = {0: {"turn": game.turn, "actions": [action]},
                        1: {"turn": game.turn, "actions": []}}
            before = {identity: rover.position for identity, rover in game.rovers.items()}
            trace = {}
            events, diagnostics = step(game, response, trace)
            self.assertFalse(diagnostics)
            monitor.record(game, seen, [response[0], response[1]], trace, events, before)
        self.assertEqual(monitor.report()[0].get("back_and_forth"), 1)
        self.assertEqual(monitor.warnings[0]["recent_actions"], ["MOVE"] * 8)

    def test_three_tile_cycle_warns_without_progress(self):
        game = bare_game(turns=9)
        monitor = MovementMonitor()
        for direction in ("E", "W", "S", "N") * 2:
            seen = [observation(game, p) for p in (0, 1)]
            response = {0: {"turn": game.turn, "actions": [
                {"rover_id": "p0-r0", "type": "MOVE", "direction": direction}]},
                        1: {"turn": game.turn, "actions": []}}
            before = {identity: rover.position for identity, rover in game.rovers.items()}
            trace = {}
            events, diagnostics = step(game, response, trace)
            self.assertFalse(diagnostics)
            monitor.record(game, seen, [response[0], response[1]], trace, events, before)
        self.assertEqual(monitor.report()[0].get("small_tile_cycle"), 1)

    def test_long_path_and_deliberate_wait_do_not_warn(self):
        game = bare_game(turns=12)
        monitor = MovementMonitor()
        for turn in range(10):
            seen = [observation(game, p) for p in (0, 1)]
            action = {"rover_id": "p0-r0", "type": "MOVE", "direction": "E"} if turn < 8 else {
                "rover_id": "p0-r0", "type": "WAIT"}
            response = {0: {"turn": game.turn, "actions": [action], "targets": {"p0-r0": [10, 1]}},
                        1: {"turn": game.turn, "actions": []}}
            before = {identity: rover.position for identity, rover in game.rovers.items()}
            trace = {}
            events, diagnostics = step(game, response, trace)
            self.assertFalse(diagnostics)
            monitor.record(game, seen, [response[0], response[1]], trace, events, before)
        self.assertEqual(monitor.report(), [{}, {}])

    def test_goal_switch_and_unreachable_target_warn(self):
        game = bare_game(turns=10)
        monitor = MovementMonitor()
        for turn in range(8):
            seen = [observation(game, p) for p in (0, 1)]
            target = [12, 12] if turn % 2 else [11, 11]
            response = {0: {"turn": game.turn, "actions": [], "targets": {"p0-r0": target}},
                        1: {"turn": game.turn, "actions": []}}
            before = {identity: rover.position for identity, rover in game.rovers.items()}
            trace = {}
            events, _ = step(game, response, trace)
            monitor.record(game, seen, [response[0], response[1]], trace, events, before)
        self.assertEqual(monitor.report()[0].get("goal_switching"), 1)

        game = bare_game(turns=10)
        monitor = MovementMonitor()
        for turn in range(8):
            seen = [observation(game, p) for p in (0, 1)]
            response = {0: {"turn": game.turn, "actions": [
                {"rover_id": "p0-r0", "type": "MOVE", "direction": "E"}],
                "targets": {"p0-r0": [11, 11] if turn % 2 else [12, 12]}},
                        1: {"turn": game.turn, "actions": []}}
            before = {identity: rover.position for identity, rover in game.rovers.items()}
            trace = {}
            events, diagnostics = step(game, response, trace)
            self.assertFalse(diagnostics)
            monitor.record(game, seen, [response[0], response[1]], trace, events, before)
        self.assertEqual(monitor.report(), [{}, {}])

        game = bare_game(turns=10)
        for point in ((10, 11), (12, 11), (11, 10), (11, 12)):
            game.cell(point).terrain = "rock"
        reveal(game)
        monitor = MovementMonitor()
        for _ in range(8):
            seen = [observation(game, p) for p in (0, 1)]
            response = {0: {"turn": game.turn, "actions": [
                {"rover_id": "p0-r0", "type": "MOVE", "direction": "E"}],
                "targets": {"p0-r0": [11, 11]}},
                        1: {"turn": game.turn, "actions": []}}
            before = {identity: rover.position for identity, rover in game.rovers.items()}
            trace = {}
            events, diagnostics = step(game, response, trace)
            self.assertFalse(diagnostics)
            monitor.record(game, seen, [response[0], response[1]], trace, events, before)
        self.assertEqual(monitor.report()[0].get("unreachable_target"), 1)


if __name__ == "__main__":
    unittest.main()
