"""Paired-seed tournament evaluation without conflating strategy and runtime."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import random
import sys
import tempfile
import time
from typing import Any

from mini_mars.engine.game import Config
from mini_mars.scenarios import resolve_config
from .match import RESULTS, run_match, source_hashes, source_revision


def paired_bootstrap_interval(differences: list[float], samples: int = 5000) -> list[float] | None:
    """Seed-level percentile interval for the mean A-minus-B gold difference."""
    if not differences:
        return None
    rng = random.Random(20261021)
    count = len(differences)
    means = sorted(sum(differences[rng.randrange(count)] for _ in range(count)) / count
                   for _ in range(samples))

    def percentile(p: float) -> float:
        position = p * (samples - 1)
        lower = int(position)
        weight = position - lower
        return means[lower] * (1 - weight) + means[min(lower + 1, samples - 1)] * weight

    return [percentile(.025), percentile(.975)]


def run_tournament(bot_a: str, bot_b: str, matches: int, seed: int,
                   config: Config | None = None, output_dir: Path | None = None,
                   save_replays: bool = False, timeout_seconds: float = 1.0,
                   scenario: str | None = None) -> dict[str, Any]:
    """`matches` means map seeds; each seed produces two swapped games."""
    if matches < 1:
        raise ValueError("matches must be positive")
    scenario, config = resolve_config(config, scenario)
    if output_dir is None:
        root = RESULTS / "tournaments"
        root.mkdir(parents=True, exist_ok=True)
        output_dir = Path(tempfile.mkdtemp(prefix=f"seed-{seed}-", dir=root))
    else:
        output_dir.mkdir(parents=True, exist_ok=True)
    records = []
    wins = {"a": 0, "b": 0, "ties": 0}
    totals = {"a": 0, "b": 0, "difference": 0, "latency_a": 0.0, "latency_b": 0.0,
              "decisions_a": 0, "decisions_b": 0, "invalid_a": 0, "invalid_b": 0,
              "timeouts_a": 0, "timeouts_b": 0, "crashes_a": 0, "crashes_b": 0}
    failed = 0
    paired_differences: list[float] = []
    started = time.perf_counter()
    for map_seed in range(seed, seed + matches):
        identity_seeds = (map_seed * 1009, map_seed * 1009 + 1)
        pair_games: list[tuple[dict, dict, int, int]] = []
        for swapped in (False, True):
            folder = output_dir / f"seed-{map_seed}-{'swapped' if swapped else 'normal'}"
            specs = (bot_b, bot_a) if swapped else (bot_a, bot_b)
            seeds = identity_seeds[::-1] if swapped else identity_seeds
            try:
                result = run_match(specs, map_seed, seeds, config, folder, save_replays,
                                   timeout_seconds, scenario=scenario)
            except Exception as error:
                failed += 1
                records.append({"seed": map_seed, "swapped": swapped, "error": repr(error)})
                continue
            a_slot = 1 if swapped else 0
            b_slot = 1 - a_slot
            score_a, score_b = result["scores"][a_slot], result["scores"][b_slot]
            record = {"seed": map_seed, "swapped": swapped, "score_a": score_a,
                            "score_b": score_b, "winner": "tie" if score_a == score_b else
                            ("a" if score_a > score_b else "b"), "summary": result["output_dir"] + "/summary.json"}
            records.append(record)
            pair_games.append((record, result, a_slot, b_slot))
        if len(pair_games) != 2:
            continue
        paired_differences.append(sum(record["score_a"] - record["score_b"]
                                      for record, _, _, _ in pair_games) / 2)
        for record, result, a_slot, b_slot in pair_games:
            if record["score_a"] > record["score_b"]:
                wins["a"] += 1
            elif record["score_b"] > record["score_a"]:
                wins["b"] += 1
            else:
                wins["ties"] += 1
            totals["a"] += record["score_a"]
            totals["b"] += record["score_b"]
            totals["difference"] += record["score_a"] - record["score_b"]
            for label, slot in (("a", a_slot), ("b", b_slot)):
                totals[f"latency_{label}"] += result["decision_latency_sum_ms"][slot]
                totals[f"decisions_{label}"] += result["decisions"][slot]
                for name in ("invalid_actions", "timeouts", "crashes"):
                    key = {"invalid_actions": "invalid", "timeouts": "timeouts", "crashes": "crashes"}[name]
                    totals[f"{key}_{label}"] += result[name][slot]
    played = len(paired_differences) * 2
    report = {
        "game": "mini-mars", "bot_a": bot_a, "bot_b": bot_b, "first_seed": seed,
        "scenario": scenario, "source_sha256": source_hashes(),
        "source_revision": source_revision(), "python_version": sys.version.split()[0],
        "paired_seeds": matches, "games_played": played, "failed_matches": failed,
        "complete_pairs": len(paired_differences), "failed_pairs": matches - len(paired_differences),
        "paired_score_differences_a_minus_b": paired_differences,
        "paired_bootstrap_ci95_a_minus_b": paired_bootstrap_interval(paired_differences),
        "config": asdict(config), "wins": wins,
        "win_rate_a": (wins["a"] + wins["ties"] / 2) / played if played else None,
        "win_rate_b": (wins["b"] + wins["ties"] / 2) / played if played else None,
        "average_gold": {"a": totals["a"] / played if played else None,
                         "b": totals["b"] / played if played else None},
        "average_score_difference_a_minus_b": totals["difference"] / played if played else None,
        "paired_average_score_difference_a_minus_b": (
            sum(paired_differences) / len(paired_differences) if paired_differences else None),
        "average_decision_latency_ms": {
            label: totals[f"latency_{label}"] / totals[f"decisions_{label}"]
            if totals[f"decisions_{label}"] else None for label in ("a", "b")},
        "invalid_actions": {label: totals[f"invalid_{label}"] for label in ("a", "b")},
        "timeouts": {label: totals[f"timeouts_{label}"] for label in ("a", "b")},
        "bot_crashes": {label: totals[f"crashes_{label}"] for label in ("a", "b")},
        "wall_time_ms": (time.perf_counter() - started) * 1000,
        "records": records, "output_dir": str(output_dir.resolve()),
    }
    (output_dir / "tournament.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
