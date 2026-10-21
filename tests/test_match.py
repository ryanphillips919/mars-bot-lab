import contextlib
import io
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from experiments.match import main


class MatchCommandTest(unittest.TestCase):
    def test_writes_replay_and_serializable_summary_from_episode(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            agent = root / "agent.py"
            agent.write_text("# test agent\n", encoding="utf-8")
            replay = root / "replays" / "game.json"
            summary = root / "results" / "game.json"
            observed = {}

            class EngineScore:
                def __init__(self, value):
                    self.value = value

                def __int__(self):
                    return self.value

            class EpisodeConfig:
                def __init__(self, **kwargs):
                    self.__dict__.update(kwargs)

            class ReplayConfig:
                def __init__(self, **kwargs):
                    self.__dict__.update(kwargs)

            class Episode:
                def __init__(self, cfg):
                    observed["config"] = cfg

                async def run(self):
                    replay.parent.mkdir(parents=True)
                    replay.write_text("{}", encoding="utf-8")
                    return {"player_0": EngineScore(7), "player_1": EngineScore(3)}

            runner = types.ModuleType("luxai_runner")
            episode_module = types.ModuleType("luxai_runner.episode")
            episode_module.Episode = Episode
            episode_module.EpisodeConfig = EpisodeConfig
            episode_module.ReplayConfig = ReplayConfig
            simulator = types.ModuleType("luxai_s2")
            simulator.LuxAI_S2 = type("LuxAI_S2", (), {})
            modules = {
                "luxai_runner": runner,
                "luxai_runner.episode": episode_module,
                "luxai_s2": simulator,
            }
            argv = [
                "match", "--player-0", str(agent), "--player-1", str(agent),
                "--seed", "13", "--replay", str(replay), "--summary", str(summary),
            ]
            with patch.dict(sys.modules, modules), patch.object(sys, "argv", argv):
                with contextlib.redirect_stdout(io.StringIO()):
                    main()

            data = json.loads(summary.read_text(encoding="utf-8"))
            self.assertEqual(data["scores"], {"player_0": 7, "player_1": 3})
            self.assertEqual(data["winner"], "player_0")
            self.assertEqual(data["seed"], 13)
            self.assertEqual(len(data["engine_revision"]), 40)
            self.assertEqual(observed["config"].players, [str(agent), str(agent)])
            self.assertEqual(observed["config"].replay_options.save_format, "json")
            self.assertTrue(replay.is_file())


if __name__ == "__main__":
    unittest.main()

