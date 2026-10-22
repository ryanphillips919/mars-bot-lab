"""Reproducible in-process decision timing on synthetic fully visible maps."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time

from mini_mars.bots.competition_starter import StarterBot
from mini_mars.bots.strategies import CoordinatedGreedy, StrategySettings
from mini_mars.engine.game import Config, make_game, observation

from .match import ROOT, source_hashes, source_revision


FIXTURES = ((15, 3, 8, 9, 6), (25, 10, 20, 30, 15), (35, 30, 40, 60, 30))


def measure(repetitions: int = 30) -> dict:
    if repetitions < 1:
        raise ValueError("repetitions must be positive")
    rows = []
    for size, rover_count, rocks, gold, iron in FIXTURES:
        config = Config(width=size, height=size, starting_rovers=rover_count,
                        rock_pairs=rocks, gold_pairs=gold, iron_pairs=iron,
                        full_information=True)
        seen = observation(make_game(20261022, config), 0)
        timings = {}
        for name, factory in (
                ("starter", StarterBot),
                ("coordinated-harvest-first", lambda: CoordinatedGreedy(
                    StrategySettings(gold_priority=True))),
                ("coordinated-harvest-stable", lambda: CoordinatedGreedy(
                    StrategySettings(gold_priority=True, stable_targets=True)))):
            samples = []
            for _ in range(repetitions):
                bot = factory()  # Identical initial persistent state each time.
                started = time.perf_counter_ns()
                bot.decide(seen)
                samples.append((time.perf_counter_ns() - started) / 1_000_000)
            timings[name] = {"median_ms": statistics.median(samples),
                             "maximum_ms": max(samples)}
        rows.append({"config": asdict(config), "seed": 20261022,
                     "repetitions_per_bot": repetitions, "timings": timings})
    script = Path(__file__)
    return {"format": "mini-mars-decision-profile-v1", "python_version": sys.version.split()[0],
            "source_revision": source_revision(), "source_sha256": source_hashes(),
            "profile_script_sha256": hashlib.sha256(script.read_bytes()).hexdigest(),
            "method": "perf_counter_ns around decide() only; fresh bot each repetition; no subprocess, JSON, or engine step",
            "fixtures": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repetitions", type=int, default=30)
    parser.add_argument("--output", type=Path, help="write a new JSON file; never overwrite")
    args = parser.parse_args()
    result = json.dumps(measure(args.repetitions), indent=2) + "\n"
    if args.output:
        path = args.output if args.output.is_absolute() else ROOT / args.output
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as file:
            file.write(result)
        print(path)
    else:
        print(result, end="")
