import unittest

from experiments.match import read_result


def example_result():
    raw = {
        "map_seed": 42,
        "map_width": 32,
        "map_height": 32,
        "stats": {"0": {"score": 0, "rank": 2}, "1": {"score": 0, "rank": 1}},
        "terminated": {"0": False, "1": False},
    }
    replay = {
        "ENGINE_VERSION": "1.2.2.finals",
        "map_generator_seed": 42,
        "number_of_players": 2,
        "full_frames": [{}, {}],
        "game_statistics": {
            "number_turns": 1,
            "player_statistics": [
                {"player_id": 0, "final_production": 0, "rank": 2},
                {"player_id": 1, "final_production": 0, "rank": 1},
            ],
        },
    }
    return raw, replay


class HaliteResultTest(unittest.TestCase):
    def test_uses_engine_rank_to_break_equal_scores(self):
        raw, replay = example_result()
        result = read_result(raw, replay, 42, 32, 32)
        self.assertEqual(result["scores"], {"player_0": 0, "player_1": 0})
        self.assertEqual(result["winner"], "player_1")

    def test_rejects_terminated_bot(self):
        raw, replay = example_result()
        raw["terminated"]["0"] = True
        with self.assertRaisesRegex(ValueError, "terminated"):
            read_result(raw, replay, 42, 32, 32)

    def test_rejects_incomplete_or_disagreeing_replay(self):
        raw, replay = example_result()
        replay["full_frames"].pop()
        with self.assertRaisesRegex(ValueError, "complete turn sequence"):
            read_result(raw, replay, 42, 32, 32)
        replay["full_frames"].append({})
        replay["game_statistics"]["player_statistics"][0]["final_production"] = 4
        with self.assertRaisesRegex(ValueError, "replay score differs"):
            read_result(raw, replay, 42, 32, 32)


if __name__ == "__main__":
    unittest.main()
