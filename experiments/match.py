"""Run two bots through the pinned Halite III engine and retain the evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
HALITE_ROOT = ROOT / "engine" / "halite"
DEFAULT_ENGINE = HALITE_ROOT / "build-source" / "halite"
CPP_STARTER = HALITE_ROOT / "cpp-build" / "MyBot"


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def command_files(command: str) -> dict[str, str]:
    """Hash paths visible in a bot command, including a PATH executable."""
    parts = shlex.split(command)
    files: dict[str, str] = {}
    for index, part in enumerate(parts):
        candidate = Path(part)
        if index == 0 and not candidate.is_file():
            executable = shutil.which(part)
            if executable:
                candidate = Path(executable)
        if candidate.is_file():
            resolved = candidate.resolve()
            files[str(resolved)] = digest(resolved)
    return files


def read_result(raw: dict[str, Any], replay: dict[str, Any], seed: int, width: int, height: int) -> dict[str, Any]:
    """Validate the engine result against its replay and return comparable scores."""
    if raw.get("map_seed") != seed or raw.get("map_width") != width or raw.get("map_height") != height:
        raise ValueError("engine result does not match the requested map")
    if replay.get("map_generator_seed") != seed or replay.get("number_of_players") != 2:
        raise ValueError("replay does not match the requested two-player map")
    if not replay.get("ENGINE_VERSION"):
        raise ValueError("replay is missing the engine version")

    stats = raw.get("stats", {})
    if set(stats) != {"0", "1"}:
        raise ValueError("engine result must have scores and ranks for both players")
    scores = {f"player_{player}": int(stats[player]["score"]) for player in ("0", "1")}
    ranks = {f"player_{player}": int(stats[player]["rank"]) for player in ("0", "1")}
    if sorted(ranks.values()) != [1, 2]:
        raise ValueError("engine result must have distinct first and second ranks")

    game_stats = replay.get("game_statistics", {})
    turns = game_stats.get("number_turns")
    frames = replay.get("full_frames")
    if not isinstance(turns, int) or turns < 1 or not isinstance(frames, list) or len(frames) != turns + 1:
        raise ValueError("replay does not contain a complete turn sequence")
    replay_players = {str(item["player_id"]): item for item in game_stats.get("player_statistics", [])}
    if set(replay_players) != {"0", "1"}:
        raise ValueError("replay statistics must contain both players")
    for player in ("0", "1"):
        if replay_players[player]["final_production"] != scores[f"player_{player}"]:
            raise ValueError(f"replay score differs for player {player}")
        if replay_players[player]["rank"] != ranks[f"player_{player}"]:
            raise ValueError(f"replay rank differs for player {player}")

    terminated = raw.get("terminated", {})
    if any(terminated.get(player) is True for player in ("0", "1")):
        raise ValueError("at least one bot was terminated by the engine")
    winner = min(ranks, key=ranks.__getitem__)
    return {"scores": scores, "ranks": ranks, "winner": winner, "turns": turns, "terminated": terminated}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, default=DEFAULT_ENGINE)
    parser.add_argument("--player-0", default=shlex.join([str(CPP_STARTER), "101"]), help="shell command for player 0")
    parser.add_argument("--player-1", default=shlex.join([str(CPP_STARTER), "202"]), help="shell command for player 1")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--width", type=int, default=32)
    parser.add_argument("--height", type=int, default=32)
    parser.add_argument("--turn-limit", type=int, help="override the engine's map-size-dependent limit")
    parser.add_argument("--output-root", type=Path, default=ROOT / "results" / "halite")
    args = parser.parse_args()

    if not args.engine.is_file():
        parser.error(f"engine does not exist: {args.engine}; run make setup first")
    if not 0 <= args.seed < 2**32:
        parser.error("--seed must be a 32-bit unsigned integer")
    if args.width < 1 or args.height < 1:
        parser.error("map dimensions must be positive")
    if args.turn_limit is not None and args.turn_limit < 1:
        parser.error("--turn-limit must be positive")
    for command in (args.player_0, args.player_1):
        if not command.strip():
            parser.error("bot commands must not be empty")

    engine = args.engine.resolve()
    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    run_dir = Path(tempfile.mkdtemp(prefix=f"seed-{args.seed}-", dir=output_root))
    command = [
        str(engine), "--results-as-json", "--no-compression",
        "--seed", str(args.seed), "--width", str(args.width), "--height", str(args.height),
        "--replay-directory", str(run_dir),
    ]
    if args.turn_limit is not None:
        command.extend(["--turn-limit", str(args.turn_limit)])
    command.extend([args.player_0, args.player_1])

    started = time.perf_counter()
    completed = subprocess.run(command, cwd=run_dir, capture_output=True, text=True, check=False)
    wall_time_ms = round((time.perf_counter() - started) * 1000)
    raw_path = run_dir / "engine-result.json"
    stderr_path = run_dir / "engine-stderr.log"
    raw_path.write_text(completed.stdout, encoding="utf-8")
    stderr_path.write_text(completed.stderr, encoding="utf-8")
    if completed.returncode:
        raise RuntimeError(f"Halite exited {completed.returncode}; outputs retained in {run_dir}")

    try:
        raw = json.loads(completed.stdout)
        replay_path = Path(raw["replay"])
        if not replay_path.is_absolute():
            replay_path = run_dir / replay_path
        replay_path = replay_path.resolve()
        if not replay_path.is_file() or not replay_path.is_relative_to(run_dir):
            raise ValueError(f"replay is missing from run directory: {replay_path}")
        replay = json.loads(replay_path.read_text(encoding="utf-8"))
        outcome = read_result(raw, replay, args.seed, args.width, args.height)
    except (KeyError, ValueError, json.JSONDecodeError) as error:
        raise RuntimeError(f"invalid Halite result; outputs retained in {run_dir}: {error}") from error

    revision = (HALITE_ROOT / "REVISION").read_text(encoding="utf-8").strip() if engine == DEFAULT_ENGINE.resolve() else None
    summary = {
        "engine": "halite-iii",
        "engine_revision": revision,
        "engine_version": replay.get("ENGINE_VERSION"),
        "engine_binary": str(engine),
        "engine_sha256": digest(engine),
        "seed": args.seed,
        "map_width": args.width,
        "map_height": args.height,
        "map_generator": raw.get("map_generator"),
        "turn_limit": args.turn_limit,
        "players": [args.player_0, args.player_1],
        "player_command_files": [command_files(args.player_0), command_files(args.player_1)],
        **outcome,
        "replay": str(replay_path),
        "replay_sha256": digest(replay_path),
        "engine_result": str(raw_path),
        "engine_stderr": str(stderr_path),
        "engine_execution_time_ms": raw.get("execution_time"),
        "wall_time_ms": wall_time_ms,
    }
    summary_path = run_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
