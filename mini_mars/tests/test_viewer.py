from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from mini_mars.viewer import discover_matches, replay_for


class ViewerTests(unittest.TestCase):
    def test_discovers_only_saved_replays_inside_their_match_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            results = root / "matches"
            results.mkdir()
            good = results / "good"
            good.mkdir()
            (good / "replay.json").write_text('{"format":"mini-mars-replay-v1"}')
            (good / "summary.json").write_text(json.dumps({
                "game": "mini-mars", "seed": 42, "replay": str(good / "replay.json"),
            }))
            missing = results / "no-replay"
            missing.mkdir()
            (missing / "summary.json").write_text(json.dumps({
                "game": "mini-mars", "replay": str(missing / "replay.json"),
            }))
            escape = results / "escape"
            escape.mkdir()
            (root / "replay.json").write_text("{}")
            (escape / "summary.json").write_text(json.dumps({
                "game": "mini-mars", "replay": str(root / "replay.json"),
            }))
            self.assertEqual([match["id"] for match in discover_matches(results)], ["good"])
            self.assertIsNone(replay_for(escape, {"replay": "../../replay.json"}, results))
            self.assertIsNone(replay_for(good, {"replay": "summary.json"}, results))


if __name__ == "__main__":
    unittest.main()
