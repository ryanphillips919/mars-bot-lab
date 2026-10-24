"""Regression tests for controlled large-map construction experiments."""
import unittest
from dataclasses import replace

from mini_mars.engine.game import Config, initial_map, make_game, reachable
from mini_mars.scenarios import expansion_config


class ExpandedMapTests(unittest.TestCase):
    def test_reproducible_connected_and_symmetric(self):
        for size in (15, 30, 50):
            for layout in ("uniform", "clustered"):
                with self.subTest(size=size, layout=layout):
                    cfg = expansion_config(size, 200, 6, layout)
                    a = make_game(811, cfg)
                    b = make_game(811, cfg)
                    self.assertEqual(initial_map(a), initial_map(b))
                    self.assertEqual(len(reachable((1, 1), a.cells)),
                                     size * size - 2 * cfg.rock_pairs)
                    for y, row in enumerate(a.cells):
                        for x, cell in enumerate(row):
                            mirror = a.cells[size - 1 - y][size - 1 - x]
                            self.assertEqual((cell.terrain, cell.resource, cell.quantity),
                                             (mirror.terrain, mirror.resource, mirror.quantity))
                    self.assertEqual(sum(c.resource == "gold" for row in a.cells for c in row),
                                     cfg.gold_pairs * 2)

    def test_density_and_initial_iron(self):
        base = expansion_config(15, 100, 8)
        large = expansion_config(50, 400, 4)
        fixed = expansion_config(50, 400, 4, density_mode="fixed")
        self.assertEqual((base.gold_pairs, base.iron_pairs), (9, 6))
        self.assertGreater(large.gold_pairs, base.gold_pairs)
        self.assertEqual((fixed.gold_pairs, fixed.iron_pairs), (9, 6))
        cfg = replace(base, initial_banked_iron=8)
        game = make_game(17, cfg)
        self.assertEqual([colony.iron for colony in game.colonies], [8, 8])

    def test_invalid_configurations(self):
        for kwargs in ({"resource_layout": "diagonal"},
                       {"initial_banked_iron": -1}):
            with self.assertRaises(ValueError):
                Config(**kwargs)
        with self.assertRaises(ValueError):
            expansion_config(20, 100, 8, density_mode="unknown")


if __name__ == "__main__":
    unittest.main()
