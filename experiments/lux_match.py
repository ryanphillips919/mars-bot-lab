"""Run a seeded match through the official Lux AI Season 2 episode runner."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Mapping


ROOT = Path(__file__).resolve().parents[1]
STARTER = ROOT / "engine" / "upstream" / "kits" / "python" / "main.py"


def outcome(scores: Mapping[str, float]) -> str:
    """Use the official terminal rewards to report the winning player."""
    left = scores["player_0"]
    right = scores["player_1"]
    if left == right:
        return "draw"
    return "player_0" if left > right else "player_1"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--player-0", type=Path, default=STARTER)
    parser.add_argument("--player-1", type=Path, default=STARTER)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-turns", type=int, default=1000)
    parser.add_argument("--replay", type=Path, default=ROOT / "results/demo/replay.json")
    parser.add_argument("--summary", type=Path, default=ROOT / "results/demo/summary.json")
    args = parser.parse_args()

    for player in (args.player_0, args.player_1):
        if not player.is_file():
            parser.error(f"agent does not exist: {player}; run make setup first")
    if args.max_turns < 1:
        parser.error("--max-turns must be positive")
    if args.replay.suffix != ".json":
        parser.error("--replay must end in .json")

    # Import only when running a real match so result helpers can be tested
    # without installing the simulator on the host Python interpreter.
    from luxai_runner.episode import Episode, EpisodeConfig, ReplayConfig
    from luxai_s2 import LuxAI_S2

    config = EpisodeConfig(
        players=[str(args.player_0.resolve()), str(args.player_1.resolve())],
        env_cls=LuxAI_S2,
        seed=args.seed,
        env_cfg={
            "verbose": 1,
            "validate_action_space": True,
            "max_episode_length": args.max_turns,
        },
        verbosity=1,
        render=False,
        save_replay_path=str(args.replay.resolve()),
        replay_options=ReplayConfig(save_format="json", compressed_obs=True),
    )
    raw_scores = asyncio.run(Episode(cfg=config).run())
    # The engine computes lichen totals with NumPy; its integer scalars are
    # comparable but cannot be encoded by the standard JSON encoder.
    scores = {player: int(raw_scores[player]) for player in ("player_0", "player_1")}
    if not args.replay.is_file():
        raise RuntimeError(f"Lux returned without saving the replay: {args.replay}")

    summary = {
        "engine_revision": (ROOT / "engine" / "REVISION").read_text(encoding="utf-8").strip(),
        "seed": args.seed,
        "max_turns": args.max_turns,
        "players": config.players,
        "scores": scores,
        "winner": outcome(scores),
        "replay": str(args.replay.resolve()),
    }
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

