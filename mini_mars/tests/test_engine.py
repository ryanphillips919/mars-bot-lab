from __future__ import annotations

import unittest

from mini_mars.engine.game import Config, initial_map, make_game, observation, outcome, reachable, step


def submit(game, player_actions=None):
    player_actions = player_actions or {}
    return {player: {"turn": game.turn, "actions": player_actions.get(player, [])} for player in (0, 1)}


class MapTests(unittest.TestCase):
    def test_seeded_map_is_connected_balanced_and_reproducible(self):
        for seed in range(10):
            game = make_game(seed)
            self.assertEqual(initial_map(game), initial_map(make_game(seed)))
            open_tiles = sum(cell.terrain == "plain" for row in game.cells for cell in row)
            self.assertEqual(len(reachable((1, 1), game.cells)), open_tiles)
            for y, row in enumerate(game.cells):
                for x, cell in enumerate(row):
                    mirror = game.cells[game.config.height - 1 - y][game.config.width - 1 - x]
                    self.assertEqual((cell.terrain, cell.resource, cell.quantity),
                                     (mirror.terrain, mirror.resource, mirror.quantity))
            for kind in ("gold", "iron"):
                self.assertTrue(any(cell.resource == kind for row in game.cells for cell in row))

    def test_fog_remembers_last_seen_quantity_and_hides_enemy(self):
        game = make_game(42)
        first = observation(game, 0)
        self.assertLess(len(first["cells"]), game.config.width * game.config.height)
        self.assertEqual(first["enemies"]["rovers"], [])
        self.assertEqual(first["enemies"]["bases"], [])
        self.assertNotIn("seed", first)
        self.assertNotIn("map", first)
        known = {(cell["x"], cell["y"]) for cell in first["cells"]}
        self.assertNotIn((game.config.width - 2, game.config.height - 2), known)
        # Change a known tile while no friendly rover sees it: memory stays stale.
        game.rovers["p0-r0"].x = game.rovers["p0-r1"].x = game.rovers["p0-r2"].x = 8
        game.rovers["p0-r0"].y = game.rovers["p0-r1"].y = game.rovers["p0-r2"].y = 8
        from mini_mars.engine.game import reveal
        reveal(game)
        game.cell((1, 1)).resource = "gold"
        game.cell((1, 1)).quantity = 3
        stale = next(cell for cell in observation(game, 0)["cells"] if (cell["x"], cell["y"]) == (1, 1))
        self.assertFalse(stale["visible"])
        self.assertIsNone(stale["resource"])
        game.rovers["p0-r0"].x = game.rovers["p0-r0"].y = 1
        reveal(game)
        refreshed = next(cell for cell in observation(game, 0)["cells"] if (cell["x"], cell["y"]) == (1, 1))
        self.assertEqual(refreshed["quantity"], 3)


class RuleTests(unittest.TestCase):
    def setUp(self):
        self.game = make_game(5)

    def test_move_bounds_rocks_and_stacking(self):
        game = self.game
        game.rovers["p0-r0"].x = 0
        game.rovers["p0-r0"].y = 0
        _, invalid = step(game, submit(game, {0: [{"rover_id": "p0-r0", "type": "MOVE", "direction": "N"}]}))
        self.assertEqual(game.rovers["p0-r0"].position, (0, 0))
        self.assertEqual(len(invalid), 1)
        game.rovers["p0-r0"].x = game.rovers["p0-r1"].x = 1
        game.rovers["p0-r0"].y = game.rovers["p0-r1"].y = 1
        step(game, submit(game, {0: [{"rover_id": rid, "type": "MOVE", "direction": "N"}
                                    for rid in ("p0-r0", "p0-r1")]}))
        self.assertEqual(game.rovers["p0-r0"].position, game.rovers["p0-r1"].position)
        rock = next((x, y) for y, row in enumerate(game.cells) for x, cell in enumerate(row)
                    if cell.terrain == "rock" and any(game.traversable((x + dx, y + dy))
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))))
        rx, ry = rock
        for direction, dx, dy in (("E", 1, 0), ("W", -1, 0), ("S", 0, 1), ("N", 0, -1)):
            start = (rx - dx, ry - dy)
            if game.traversable(start):
                game.rovers["p0-r0"].x, game.rovers["p0-r0"].y = start
                _, invalid = step(game, submit(game, {0: [{"rover_id": "p0-r0", "type": "MOVE", "direction": direction}]}))
                self.assertEqual(game.rovers["p0-r0"].position, start)
                self.assertTrue(invalid)
                break

    def test_mining_capacity_depletion_and_contested_last_unit(self):
        game = self.game
        point = (1, 1)
        game.cell(point).resource = "gold"
        game.cell(point).quantity = 1
        game.rovers["p1-r0"].x = game.rovers["p1-r0"].y = 1
        actions = {0: [{"rover_id": "p0-r0", "type": "MINE"}],
                   1: [{"rover_id": "p1-r0", "type": "MINE"}]}
        events, invalid = step(game, submit(game, actions))
        self.assertEqual(sum(rover.gold for rover in game.rovers.values()), 1)
        self.assertEqual(game.cell(point).quantity, 0)
        self.assertEqual(len([event for event in events if event["type"] == "mine_contested"]), 1)
        self.assertEqual(invalid, [])
        game.cell(point).quantity = 1
        step(game, submit(game, actions))
        self.assertEqual(game.rovers["p0-r0"].gold, game.rovers["p1-r0"].gold)
        game.cell(point).quantity = 0
        _, invalid = step(game, submit(game, {1: [{"rover_id": "p1-r0", "type": "MINE"}]}))
        self.assertTrue(invalid)
        rover = game.rovers["p0-r0"]
        rover.gold = game.config.cargo_capacity
        game.cell(point).quantity = 1
        _, invalid = step(game, submit(game, {0: [{"rover_id": rover.id, "type": "MINE"}]}))
        self.assertEqual(rover.gold, game.config.cargo_capacity)
        self.assertTrue(invalid)

    def test_deposit_build_cost_and_win_condition(self):
        game = self.game
        rover = game.rovers["p0-r0"]
        rover.gold, rover.iron = 4, 8
        self.assertEqual(outcome(game), {"scores": [0, 0], "winner": None})
        step(game, submit(game, {0: [{"rover_id": rover.id, "type": "DEPOSIT"}]}))
        self.assertEqual((game.colonies[0].gold, game.colonies[0].iron), (4, 8))
        self.assertEqual((rover.gold, rover.iron), (0, 0))
        self.assertEqual(outcome(game), {"scores": [4, 0], "winner": 0})
        rover.x, rover.y = (2, 1)
        events, _ = step(game, submit(game, {0: [{"rover_id": rover.id, "type": "BUILD"}]}))
        self.assertIn((2, 1), game.colonies[0].bases)
        self.assertEqual(game.colonies[0].iron, 0)
        self.assertEqual(events[0]["type"], "build")
        rover.gold = 2
        step(game, submit(game, {0: [{"rover_id": rover.id, "type": "DEPOSIT"}]}))
        self.assertEqual(game.colonies[0].gold, 6)
        game.colonies[1].gold = 6
        self.assertIsNone(outcome(game)["winner"])

    def test_invalid_actions_wait_and_duplicate_is_neutralized(self):
        game = self.game
        start = game.rovers["p0-r0"].position
        actions = [{"rover_id": "p0-r0", "type": "MOVE", "direction": "N"},
                   {"rover_id": "p0-r0", "type": "MOVE", "direction": "S"},
                   {"rover_id": "p0-r1", "type": []},
                   {"rover_id": "p0-r2", "type": "MOVE", "direction": []}]
        _, diagnostics = step(game, submit(game, {0: actions}))
        self.assertEqual(game.rovers["p0-r0"].position, start)
        self.assertGreaterEqual(len(diagnostics), 3)

    def test_simultaneous_build_cannot_use_iron_deposited_this_turn(self):
        game = self.game
        game.rovers["p0-r0"].iron = 8
        game.rovers["p0-r1"].x = 2
        game.rovers["p0-r1"].y = 1
        actions = {0: [{"rover_id": "p0-r0", "type": "DEPOSIT"},
                       {"rover_id": "p0-r1", "type": "BUILD"}]}
        _, invalid = step(game, submit(game, actions))
        self.assertEqual(game.colonies[0].iron, 8)
        self.assertNotIn((2, 1), game.colonies[0].bases)
        self.assertTrue(invalid)


if __name__ == "__main__":
    unittest.main()
