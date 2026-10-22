"""Run Mini Mars bots through persistent JSON Lines subprocesses."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import selectors
import shlex
import subprocess
import sys
import tempfile
import time
from typing import Any

from mini_mars.engine.game import Config, initial_map, make_game, observation, outcome, snapshot, step


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "mini_mars" / "results"
ALIASES = {"random", "greedy", "coordinated"}
MAX_LINE = 1_000_000


def source_hashes() -> dict[str, str]:
    files = ("mini_mars/engine/game.py", "mini_mars/bots/strategies.py",
             "mini_mars/bots/entry.py", "mini_mars/runner/match.py",
             "mini_mars/runner/tournament.py")
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in files}


def command_for(spec: str, seed: int) -> list[str]:
    if spec in ALIASES:
        return [sys.executable, "-m", "mini_mars.bots.entry", spec, "--seed", str(seed)]
    command = shlex.split(spec.replace("{seed}", str(seed)))
    if not command:
        raise ValueError("bot command cannot be empty")
    return command


class BotProcess:
    def __init__(self, command: list[str], log_path: Path) -> None:
        self.command = command
        self.log = log_path.open("wb")
        self.process: subprocess.Popen | None = None
        self.buffer = bytearray()
        self.dead = False
        try:
            self.process = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.PIPE,
                                            stdout=subprocess.PIPE, stderr=self.log, bufsize=0)
        except OSError:
            self.log.close()
            raise

    def send(self, value: dict) -> bool:
        if self.dead or self.process is None or self.process.poll() is not None:
            self.dead = True
            return False
        try:
            assert self.process.stdin is not None
            self.process.stdin.write((json.dumps(value, separators=(",", ":")) + "\n").encode("utf-8"))
            self.process.stdin.flush()
            return True
        except (BrokenPipeError, OSError):
            self.dead = True
            return False

    def read_line(self) -> bytes | None:
        if b"\n" not in self.buffer:
            return None
        line, _, rest = self.buffer.partition(b"\n")
        self.buffer = bytearray(rest)
        return bytes(line)

    def stop(self) -> None:
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=.2)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
            if self.process.stdin:
                self.process.stdin.close()
            if self.process.stdout:
                self.process.stdout.close()
        self.log.close()


def exchange(bots: list[BotProcess], observations: list[dict], timeout_seconds: float) -> tuple[list[Any], list[float], list[str | None]]:
    """Send to both bots before collecting either response."""
    responses: list[Any] = [None, None]
    latencies = [0.0, 0.0]
    faults: list[str | None] = [None, None]
    sent_at = [0.0, 0.0]
    pending: set[int] = set()
    selector = selectors.DefaultSelector()
    try:
        for player, bot in enumerate(bots):
            sent_at[player] = time.perf_counter()
            if not bot.send(observations[player]):
                faults[player] = "bot process exited before responding"
                continue
            pending.add(player)
            assert bot.process is not None and bot.process.stdout is not None
            selector.register(bot.process.stdout, selectors.EVENT_READ, player)

        while pending:
            now = time.perf_counter()
            for player in list(pending):
                line = bots[player].read_line()
                if line is None:
                    continue
                pending.remove(player)
                selector.unregister(bots[player].process.stdout)
                latencies[player] = (now - sent_at[player]) * 1000
                try:
                    responses[player] = json.loads(line)
                except (UnicodeDecodeError, json.JSONDecodeError):
                    faults[player] = "invalid JSON response"
            if not pending:
                break
            expired = [player for player in pending if now - sent_at[player] >= timeout_seconds]
            for player in expired:
                pending.remove(player)
                selector.unregister(bots[player].process.stdout)
                faults[player] = "bot response timed out"
                latencies[player] = timeout_seconds * 1000
                bots[player].dead = True
                bots[player].stop()
            if not pending:
                break
            remaining = min(sent_at[player] + timeout_seconds - now for player in pending)
            for key, _ in selector.select(max(0, remaining)):
                player = key.data
                bot = bots[player]
                assert bot.process is not None and bot.process.stdout is not None
                chunk = os.read(bot.process.stdout.fileno(), 65536)
                if not chunk:
                    pending.remove(player)
                    selector.unregister(bot.process.stdout)
                    faults[player] = "bot process exited without a response"
                    bot.dead = True
                else:
                    bot.buffer.extend(chunk)
                    if len(bot.buffer) > MAX_LINE:
                        pending.remove(player)
                        selector.unregister(bot.process.stdout)
                        faults[player] = "bot response exceeded 1 MB"
                        bot.dead = True
                        bot.stop()
    finally:
        selector.close()
    return responses, latencies, faults


def run_match(bot_specs: tuple[str, str], seed: int, bot_seeds: tuple[int, int] | None = None,
              config: Config | None = None, output_dir: Path | None = None,
              save_replay: bool = True, timeout_seconds: float = 1.0) -> dict[str, Any]:
    config = config or Config()
    if timeout_seconds <= 0:
        raise ValueError("bot timeout must be positive")
    bot_seeds = bot_seeds or (seed * 1009, seed * 1009 + 1)
    if output_dir is None:
        root = RESULTS / "matches"
        root.mkdir(parents=True, exist_ok=True)
        output_dir = Path(tempfile.mkdtemp(prefix=f"seed-{seed}-", dir=root))
    else:
        output_dir.mkdir(parents=True, exist_ok=True)
    game = make_game(seed, config)
    replay = {"format": "mini-mars-replay-v1", "seed": seed, "config": asdict(config),
              "map": initial_map(game), "frames": [snapshot(game)]}
    commands = [command_for(spec, bot_seeds[player]) for player, spec in enumerate(bot_specs)]
    bots: list[BotProcess] = []
    invalid = [0, 0]
    timeouts = [0, 0]
    crashes = [0, 0]
    latency_sum = [0.0, 0.0]
    decisions = [0, 0]
    process_fault_seen = [False, False]
    started = time.perf_counter()
    try:
        for player in (0, 1):
            bots.append(BotProcess(commands[player], output_dir / f"bot-{player}.stderr.log"))
        for _ in range(config.turns):
            observations = [observation(game, player) for player in (0, 1)]
            responses, latencies, faults = exchange(bots, observations, timeout_seconds)
            events, diagnostics = step(game, {player: responses[player] for player in (0, 1)})
            for diagnostic in diagnostics:
                invalid[diagnostic["player"]] += 1
            for player in (0, 1):
                if latencies[player] > 0:
                    decisions[player] += 1
                    latency_sum[player] += latencies[player]
                if faults[player]:
                    diagnostics.append({"player": player, "rover_id": None, "reason": faults[player]})
                    if faults[player] != "invalid JSON response" and not process_fault_seen[player]:
                        if "timed out" in faults[player]:
                            timeouts[player] += 1
                        else:
                            crashes[player] += 1
                        process_fault_seen[player] = True
            if save_replay:
                replay["frames"].append(snapshot(game, events, diagnostics))
    finally:
        for bot in bots:
            bot.stop()

    duration = (time.perf_counter() - started) * 1000
    summary: dict[str, Any] = {
        "game": "mini-mars", "seed": seed, "config": asdict(config),
        "python_version": sys.version.split()[0], "source_sha256": source_hashes(),
        "bots": list(bot_specs), "commands": commands, "bot_seeds": list(bot_seeds),
        "turns": game.turn, **outcome(game), "invalid_actions": invalid,
        "timeouts": timeouts, "crashes": crashes,
        "decision_latency_ms": [latency_sum[player] / decisions[player] if decisions[player] else 0
                                for player in (0, 1)],
        "decision_latency_sum_ms": latency_sum, "decisions": decisions,
        "wall_time_ms": duration,
        "replay": str((output_dir / "replay.json").resolve()) if save_replay else None,
        "output_dir": str(output_dir.resolve()),
    }
    if save_replay:
        replay["result"] = outcome(game)
        (output_dir / "replay.json").write_text(json.dumps(replay, separators=(",", ":")), encoding="utf-8")
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary
